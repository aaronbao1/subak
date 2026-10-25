#!/usr/bin/env python3
"""Generate the simulated company dataset.

    python3 datagen/generate.py                 # writes datagen/out/
    python3 datagen/generate.py --out /tmp/x    # elsewhere
    python3 datagen/generate.py --seed 7        # a different company with the same storylines

Stdlib only; runs on Python 3.9+. Deterministic for a given seed.
"""
from __future__ import annotations

import argparse
import random
import shutil
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from uberdata import config as C  # noqa: E402
from uberdata import exports  # noqa: E402
from uberdata.db import write_sqlite  # noqa: E402
from uberdata.events import build_storylines  # noqa: E402
from uberdata.people import build_people, build_teams  # noqa: E402
from uberdata.usage import budgets as build_budgets  # noqa: E402
from uberdata.usage import build_calendar, generate_usage  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent / "out"), help="output directory (default datagen/out)")
    ap.add_argument("--seed", type=int, default=C.SEED)
    ap.add_argument("--no-holdout", action="store_true", help="skip the synthetic future truth (Oct 25 - Dec 31)")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)
    C.SEED = args.seed
    t0 = time.time()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for sub in ("backend", "frontend", "forecasting", "csv"):  # generated output only; never anything outside --out
        shutil.rmtree(out / sub, ignore_errors=True)
    rnd = random.Random(args.seed)

    teams = build_teams()
    people = build_people(teams, rnd)
    story = build_storylines(teams, people, rnd)
    calendar = build_calendar(C.YEAR_START, C.HORIZON_END)
    usage_rows, seat_rows = generate_usage(teams, people, story.events, calendar, rnd, C.YEAR_START, C.AS_OF)
    if args.no_holdout:
        holdout_rows, holdout_seats = [], []
    else:
        holdout_rows, holdout_seats = generate_usage(teams, people, story.events, calendar, random.Random(args.seed + 1),
                                                     C.AS_OF + timedelta(days=1), C.HORIZON_END, holdout=True)
    budgets = build_budgets(teams, usage_rows, seat_rows, rnd)
    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    write_sqlite(out / "uber_ai_spend.sqlite", teams=teams, people=people, story=story, calendar=calendar, usage_rows=usage_rows,
                 seat_rows=seat_rows, holdout_rows=holdout_rows, holdout_seats=holdout_seats, budgets=budgets, generated_at=generated_at)
    backend_ref = exports.export_backend(out, teams=teams, people=people, story=story, usage_rows=usage_rows, seat_rows=seat_rows, budgets=budgets)
    fe_stats = exports.export_frontend(out, teams=teams, people=people, story=story, usage_rows=usage_rows, seat_rows=seat_rows, budgets=budgets)
    fc_stats = exports.export_forecasting(out, teams=teams, usage_rows=usage_rows, seat_rows=seat_rows, holdout_rows=holdout_rows, holdout_seats=holdout_seats)
    exports.export_csv(out, teams=teams, people=people, story=story, calendar=calendar, usage_rows=usage_rows, seat_rows=seat_rows, budgets=budgets)
    exports.write_answer_key(out, teams=teams, people=people, story=story, calendar=calendar, usage_rows=usage_rows)
    summary = exports.write_summary(out, teams=teams, people=people, story=story, calendar=calendar, usage_rows=usage_rows, seat_rows=seat_rows,
                                    holdout_rows=holdout_rows, budgets=budgets, backend_ref=backend_ref, fe_stats=fe_stats, fc_stats=fc_stats,
                                    elapsed=time.time() - t0)
    if not args.quiet:
        print(summary)
        print(f"written to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
