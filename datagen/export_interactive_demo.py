#!/usr/bin/env python3
"""Export the generated company as static, visitor-local demo inputs.

Only allowlisted read DTOs are fetched. No application startup, agent, refresh, approval,
holdout data, credentials or stored conversation history is involved. Weekly history is
read from the immutable native archives through the offline helper. The source backend
must be the already-prepared generated company, not a real account.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
import gzip
import hashlib
import json
from pathlib import Path
import re
import shutil
import sqlite3
import sys
import tempfile
from time import perf_counter
from urllib.parse import urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "backend"), str(ROOT / "src"), str(ROOT / "agent"), str(ROOT / "datagen")]

READS = {
    "company": "company", "teams": "teams", "people": "people", "spending": "spending",
    "budgets": "budgets", "forecasts": "forecasts", "context": "context", "documents": "documents",
    "forecast-views": "forecast-views?compact=true", "forecast-evidence": "forecast-evidence",
    "budget-requests": "budget-requests", "allocation-state": "allocation-state",
}
REQUEST_KEYS = {"company-source-update-v1:" + key for key in
                ("uber-task-0002", "uber-msg-0025", "uber-msg-0034")}
FORBIDDEN_KEYS = {"apikey", "factoryapikey", "accesstoken", "refreshtoken", "clientsecret", "password",
                  "authorization", "privatekey", "providerusage", "agentusage", "errorhistory",
                  "agentruns", "agentrunsteps", "agentrunevents", "assistantmessages", "threads", "sdkusage"}
SECRET_PATTERNS = [re.compile(pattern) for pattern in (
    r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
    r"\b(?:sk-|fk-|ghp_|github_pat_|xox[baprs]-)[A-Za-z0-9_-]{20,}",
    r"\bAKIA[A-Z0-9]{16}\b", r"\bBearer\s+[A-Za-z0-9._~+/-]{20,}",
    r"\beyJ[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}\b",
    r"https?://[^\s/@]+:[^\s/@]+@", r"/(?:Users|home|tmp|private)/[^\s]+",
    r"https?://(?:localhost|127\.0\.0\.1)(?::\d+)?\b",
)]


def encode(value):
    return (json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n").encode()


def scan_public_payloads(payloads):
    """Report paths only: diagnostic output must never echo a potential credential."""
    violations = []
    def walk(value, path):
        if isinstance(value, dict):
            for key, item in value.items():
                target = f"{path}.{key}"
                if re.sub(r"[^a-z]", "", key.lower()) in FORBIDDEN_KEYS and item not in (None, "", [], {}):
                    violations.append(target)
                walk(item, target)
        elif isinstance(value, list):
            for index, item in enumerate(value):
                walk(item, f"{path}[{index}]")
        elif isinstance(value, str) and any(pattern.search(value) for pattern in SECRET_PATTERNS):
            violations.append(path)
    for name, value in payloads.items():
        walk(value, name)
    if violations:
        raise ValueError("Potential private data in public export at paths: " + ", ".join(violations[:20]))


def validate_finances(payloads):
    company, state = payloads["company"], payloads["allocation-state"]
    assert company["id"] == "northstar" and company["budgetUnit"] == "usd"
    period = company["currentPeriod"]
    assert (period["start"], period["end"]) == ("2026-10-01", "2026-12-31")
    assert len(payloads["teams"]) == 16 and len(payloads["people"]) == 130
    assert len(payloads["documents"]) == 249
    assert len({row["id"] for row in payloads["documents"]}) == 249
    assert len({row["id"] for row in payloads["teams"]}) == 16
    assert len({row["id"] for row in payloads["people"]}) == 130
    assert all(row["teamId"] in {team["id"] for team in payloads["teams"]} for row in payloads["people"])
    assert len(payloads["budgets"]) == 16
    team_ids = {row["id"] for row in payloads["teams"]}
    person_ids = {row["id"] for row in payloads["people"]}
    assert {row["teamId"] for row in payloads["budgets"]} == team_ids
    assert {row["teamId"] for row in payloads["forecasts"] if not row.get("personId")} == team_ids
    assert {row["personId"] for row in payloads["forecasts"] if row.get("personId")} == person_ids
    assert len(payloads["forecasts"]) == len({row["id"] for row in payloads["forecasts"]}) == 146
    assert all(row["period"]["start"] == period["start"] and row["period"]["end"] == period["end"]
               for row in payloads["budgets"] + payloads["forecasts"])
    envelope = Decimal(state["envelope_total"])
    allocations = sum((Decimal(str(row["allocated"])) for row in payloads["budgets"]), Decimal(0))
    assert envelope == allocations == Decimal("430000.00")
    assert state["unit"] == "USD" and state["period"]["start_date"] == period["start"]
    assert state["period"]["end_date_exclusive"] == "2027-01-01"
    assert {row["teamId"]: Decimal(str(row["allocated"])) for row in payloads["budgets"]} == {
        row["team_id"]: Decimal(row["amount"]) for row in state["allocations"]}
    assert all(row["unit"] == "usd" for row in payloads["budgets"] + payloads["forecasts"] + payloads["spending"])
    assert all(period["start"] <= row["date"] < "2026-10-25" for row in payloads["spending"])
    recorded = sum((Decimal(str(row["amount"])) for row in payloads["spending"]
                    if row["component"] not in ("included_usage", "unpriced_usage")
                    and row["provenance"] != "usage_only"), Decimal(0))
    assert recorded == Decimal("123300.08"), recorded
    bundle = payloads["forecast-views"]
    views = [view for view in bundle["views"] if view["scope"]["type"] == "company"
             and view["scope"]["id"] == company["id"]]
    assert len(views) == 1 and len(bundle["views"]) == 148
    view = views[0]
    assert all(view["target"].get(key) == value for key, value in
               {"unit": "USD", "quantity": "spend", "basis": "planning", "timezone": "UTC"}.items())
    quarter = view["quarter_outlook"]
    assert quarter["start"] == period["start"] and quarter["end"] == "2027-01-01"
    assert quarter["complete"] is True and quarter.get("partial") is not True
    assert Decimal(str(quarter["base"])) == Decimal("464485.19875")
    assert Decimal(str(quarter["recorded"])) == recorded
    assert view["run_id"] == bundle["run_id"]
    indexed_views = {(row["scope"]["type"], row["scope"]["id"]): row for row in bundle["views"]}
    assert len(indexed_views) == 148
    assert all(row["run_id"] == bundle["run_id"] and row["snapshot_id"] == view["snapshot_id"]
               and row["target"] == view["target"] for row in bundle["views"])
    for row in payloads["forecasts"]:
        scoped = indexed_views[("person", row["personId"]) if row.get("personId") else ("team", row["teamId"])]
        if row["status"] == "available":
            point = scoped["quarter_outlook"]
            assert point["complete"] is True and point.get("partial") is not True
            assert point["start"] == period["start"] and point["end"] == "2027-01-01"
            assert Decimal(str(row["projected"])) == Decimal(str(point["base"])).quantize(Decimal(".01"), rounding=ROUND_HALF_UP)
        else:
            assert row.get("projected") is None
    assert payloads["proposals"] == [] and payloads["decisions"] == []
    requests = payloads["budget-requests"]["items"]
    assert {row["client_request_id"] for row in requests} == REQUEST_KEYS
    assert all(row["requested_amount"] is None and row["status"] == "submitted"
               and row["linked_proposal_ids"] == [] and row["decision_ids"] == []
               and Decimal(row["approved_amount"]) == 0 for row in requests)
    assert all(row["assessment"]["budget_version"] == state["state_version"]
               and Decimal(row["assessment"]["envelope_total"]) == envelope
               and (row["assessment"]["forecast_status"] != "available"
                    or row["assessment"]["forecast_run_id"] == bundle["run_id"]) for row in requests)
    return {"companyForecast": str(quarter["base"]), "recordedSpend": str(recorded),
            "budgetEnvelope": str(envelope), "forecastRunId": bundle["run_id"],
            "inputSnapshotId": view["snapshot_id"], "teamCount": 16, "personCount": 130,
            "documentCount": 249, "requestCount": 3, "forecastScopeCount": len(bundle["views"])}


def fetch_json(base_url, endpoint):
    request = Request(base_url.rstrip("/") + "/api/" + endpoint, headers={"Accept-Encoding": "gzip"})
    with urlopen(request, timeout=180) as response:
        body = response.read()
        if response.headers.get("Content-Encoding") == "gzip":
            body = gzip.decompress(body)
    return json.loads(body)


def export(args):
    parsed = urlparse(args.base_url)
    if parsed.scheme not in ("http", "https") or parsed.hostname not in ("127.0.0.1", "localhost", "::1"):
        raise ValueError("Export only from the local, explicitly prepared generated-company backend")
    if parsed.username or parsed.password:
        raise ValueError("Credential-bearing backend URLs are not accepted")
    began = perf_counter()
    payloads = {}
    for name, endpoint in READS.items():
        payloads[name] = fetch_json(args.base_url, endpoint)
        print(f"Read {name}", flush=True)
    # Only seeded generated context updates belong in a fresh visitor's session.
    payloads["budget-requests"]["items"] = [row for row in payloads["budget-requests"]["items"]
                                             if row["client_request_id"] in REQUEST_KEYS]
    payloads["proposals"], payloads["decisions"] = [], []
    # Interpretation job failures are runtime history, not generated source evidence.
    payloads["forecast-evidence"]["items"] = [row for row in payloads["forecast-evidence"]["items"]
                                               if "interpretation_job_id" not in row]
    finance = validate_finances(payloads)
    from interactive_demo_weekly import export_weekly_history
    scopes = [("company", payloads["company"]["id"])]
    scopes += [("team", row["id"]) for row in payloads["teams"]]
    scopes += [("person", row["id"]) for row in payloads["people"]]
    payloads["weekly-history"] = export_weekly_history(
        args.database, args.source, datetime.fromisoformat(args.as_of.replace("Z", "+00:00")),
        scopes, args.weekly_start, args.weekly_end)
    assert len(payloads["weekly-history"]) == len(scopes)
    # The export is one issuance/budget snapshot; a concurrent publication or decision fails closed.
    end_state = fetch_json(args.base_url, "allocation-state")
    assert end_state == payloads["allocation-state"], "Budget changed while exporting; retry"
    with sqlite3.connect(args.database.resolve().as_uri() + "?mode=ro", uri=True, timeout=5) as connection:
        published_run = connection.execute(
            "SELECT run_id FROM forecast_publications WHERE tenant_id=?", (payloads["company"]["id"],)).fetchone()
    assert published_run and published_run[0] == finance["forecastRunId"], "Forecast changed while exporting; retry"
    scan_public_payloads(payloads)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".demo-export-", dir=output.parent))
    try:
        files = {}
        for name, value in payloads.items():
            body = encode(value)
            filename = name + ".json"
            (staging / filename).write_bytes(body)
            files[name] = {"path": filename, "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}
        manifest = {"schemaVersion": 1, "asOf": args.as_of, "sourceKind": "generated-company",
                    "isSynthetic": True, "initialVisitorState": "empty-conversations-and-decisions",
                    "weeklyRange": {"startDate": args.weekly_start, "endDateExclusive": args.weekly_end},
                    "weeklyScopeCount": len(scopes), "financialParity": finance, "files": files}
        (staging / "manifest.json").write_bytes(encode(manifest))
        if output.exists():
            old = set(path.name for path in output.iterdir())
            expected = {name + ".json" for name in payloads} | {"manifest.json"}
            if not old <= expected:
                raise ValueError("Output contains unrelated files; use a dedicated empty demo directory")
        output.mkdir(exist_ok=True)
        for path in staging.iterdir():
            path.replace(output / path.name)
        print(json.dumps({"output": str(output), "files": len(files), "bytes": sum(f["bytes"] for f in files.values()),
                          "seconds": round(perf_counter() - began, 2), "financialParity": finance}, indent=2))
    finally:
        shutil.rmtree(staging)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8789/compat")
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "frontend/public/demo")
    parser.add_argument("--as-of", default="2026-10-25T00:00:00Z")
    parser.add_argument("--weekly-start", default="2026-09-21")
    parser.add_argument("--weekly-end", default="2026-12-28")
    export(parser.parse_args())


if __name__ == "__main__":
    main()
