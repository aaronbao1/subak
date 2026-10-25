#!/usr/bin/env python3
"""Live usage feed: keep posting fresh token usage into the running backend so the dashboard climbs.

    python3 datagen/live.py                         # every 2 s, ~40x real time, against http://127.0.0.1:8787
    python3 datagen/live.py --interval 1 --speed 120 --people 20
    python3 datagen/live.py --dry-run --once        # print one batch, post nothing

Each tick samples a handful of the simulated people (weighted by how heavy they are), spreads their
usage across their providers and models exactly like the historical generator, writes one small CSV
in the backend's `northstar_billing` format (with `user_email` so the spend is attributed to the person)
and POSTs it to `/api/imports`. Record ids carry the tick timestamp, so every batch is new usage and
nothing is ever double counted. Stdlib only; runs on Python 3.9+.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import random
import sys
import time
import urllib.error
import urllib.request
import uuid
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from uberdata import config as C  # noqa: E402
from uberdata.exports import BILLING_HEADER, billing_row  # noqa: E402
from uberdata.people import build_people, build_teams  # noqa: E402
from uberdata.usage import split_person_tokens, trend  # noqa: E402

WORKDAY_SECONDS = 10 * 3600.0


def multipart(fields: dict, filename: str, content: bytes) -> tuple[bytes, str]:
    boundary = f"----uberlive{uuid.uuid4().hex}"
    buf = io.BytesIO()
    for k, v in fields.items():
        buf.write(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode())
    buf.write(f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{filename}\"\r\nContent-Type: text/csv\r\n\r\n".encode())
    buf.write(content)
    buf.write(f"\r\n--{boundary}--\r\n".encode())
    return buf.getvalue(), f"multipart/form-data; boundary={boundary}"


def post_import(api: str, csv_bytes: bytes, filename: str, label: str) -> dict:
    body, ctype = multipart({"source_kind": "northstar_billing", "source_label": label}, filename, csv_bytes)
    req = urllib.request.Request(f"{api}/api/imports", data=body, method="POST",
                                 headers={"Content-Type": ctype, "X-Actor-Id": "live-feed", "X-Actor-Role": "importer"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def get_json(api: str, path: str):
    with urllib.request.urlopen(f"{api}{path}", timeout=60) as r:
        return json.loads(r.read())


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--api", default="http://127.0.0.1:8787", help="backend base URL")
    ap.add_argument("--interval", type=float, default=2.0, help="seconds between batches")
    ap.add_argument("--speed", type=float, default=40.0, help="simulated seconds of work per real second")
    ap.add_argument("--people", type=int, default=12, help="people sampled per batch")
    ap.add_argument("--seed", type=int, default=C.SEED, help="must match the generated dataset so the people exist")
    ap.add_argument("--calendar", action="store_true", help="apply weekend/holiday factors for today (off: always a busy weekday)")
    ap.add_argument("--dry-run", action="store_true", help="print batches instead of posting them")
    ap.add_argument("--once", action="store_true", help="one batch, then exit")
    args = ap.parse_args(argv)

    rnd = random.Random()  # live data is intentionally not reproducible
    teams = build_teams()
    people = build_people(teams, random.Random(args.seed))
    team_by_id = {t.id: t for t in teams}
    today = datetime.now(timezone.utc).date()
    active = [p for p in people if p.start_date <= today and not p.end_date]
    weights = [p.base_tokens_k * team_by_id[p.team_id].intensity for p in active]
    company_rate = sum(p.base_tokens_k * 1000.0 * trend(today, team_by_id[p.team_id]) for p in active) / WORKDAY_SECONDS
    day_factor = 1.0
    if args.calendar:
        hol = C.HOLIDAYS.get(today) or C.RECHARGE_DAYS.get(today)
        day_factor = (hol[1] if hol else 1.0) * (C.DEFAULT_WEEKEND_FACTOR if today.weekday() >= 5 else C.WEEKDAY_FACTOR[today.weekday()])
    print(f"live feed -> {args.api}  people={len(active)} active of {len(people)}  company rate ~{company_rate * args.speed * day_factor / 1e3:,.0f}k tokens per real second"
          f"  ({args.people} people per batch every {args.interval:g}s){'  [dry run]' if args.dry_run else ''}")

    totals = defaultdict(float)
    tick = 0
    tokens_total = cost_total = 0.0
    try:
        while True:
            tick += 1
            now = datetime.now(timezone.utc)
            budget_tokens = company_rate * args.interval * args.speed * day_factor * rnd.lognormvariate(0, 0.15)
            picks = rnd.choices(active, weights=weights, k=args.people)
            picks = list({p.id: p for p in picks}.values())
            pick_w = sum(p.base_tokens_k for p in picks)
            rows = []
            for p in picks:
                share = p.base_tokens_k / pick_w
                total = budget_tokens * share * rnd.lognormvariate(0, 0.35)
                rows.extend(split_person_tokens(p, team_by_id[p.team_id], today, total, rnd, []))
            stamp = now.strftime("%Y%m%dT%H%M%S%fZ")
            buf = io.StringIO()
            w = csv.writer(buf)
            w.writerow(BILLING_HEADER)
            email = {p.id: p.email for p in picks}
            for i, r in enumerate(rows):
                row = billing_row(r, email[r.person_id])
                row[0] = f"live-{stamp}-{i:03d}-{r.person_id}-{r.model_id}"
                row[1] = now.isoformat(timespec="seconds").replace("+00:00", "Z")
                row[-1] = f"{r.person_id} via {r.tool} (live feed)"
                w.writerow(row)
            tok = sum(r.input_tokens + r.output_tokens for r in rows)
            cost = sum(r.cost_usd for r in rows)
            tokens_total += tok
            cost_total += cost
            for r in rows:
                totals[r.provider] += r.cost_usd
            models = sorted({r.model_name for r in rows})
            line = (f"[{now.strftime('%H:%M:%S')}] batch {tick:>4}: {len(picks):>2} people, {len(rows):>3} rows, {tok / 1e6:6.2f}M tokens, ${cost:7.2f}"
                    f"  | cumulative {tokens_total / 1e6:8.1f}M tokens ${cost_total:9.2f}  | {len(models)} models, {len({r.team_id for r in rows})} teams")
            if args.dry_run:
                print(line)
                print(buf.getvalue()[:1200])
            else:
                try:
                    res = post_import(args.api, buf.getvalue().encode("utf-8"), f"live-{stamp}.csv", "Live usage feed (simulated)")
                except urllib.error.HTTPError as exc:
                    print(f"{line}\n  import failed: HTTP {exc.code} {exc.read()[:400]!r}")
                    return 1
                except urllib.error.URLError as exc:
                    print(f"{line}\n  backend unreachable at {args.api}: {exc.reason}")
                    return 1
                stats = {}
                if isinstance(res, dict):
                    stats = res.get("stats") or (res.get("error_details") or {}).get("stats") or {}
                status = res.get("status") if isinstance(res, dict) else "?"
                print(f"{line}  -> {status} ({res.get('record_count', '?')} recs, {stats.get('person_resolved', '?')} attributed)")
                if status != "imported":
                    print(json.dumps(res, indent=1)[:1500])
                    return 1
                if tick % 10 == 0:
                    try:
                        spend = get_json(args.api, f"/compat/api/spending?from={today.isoformat()}&to={today.isoformat()}")
                        print(f"    server: today's spend now ${sum(r['amount'] for r in spend):,.2f} across {len({r['teamId'] for r in spend})} teams; "
                              + ", ".join(f"{k} ${v:,.0f}" for k, v in sorted(totals.items(), key=lambda kv: -kv[1])))
                    except Exception as exc:  # noqa: BLE001 - status line only
                        print(f"    (could not read /compat/api/spending: {exc})")
            if args.once:
                break
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print(f"\nstopped after {tick} batches: {tokens_total / 1e6:,.1f}M tokens, ${cost_total:,.2f} added")
    return 0


if __name__ == "__main__":
    sys.exit(main())
