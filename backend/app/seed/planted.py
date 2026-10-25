"""Planted-error pack for the Northstar seed (all values simulated).

The files live in `backend/seed/planted/` and the expected outcomes in `backend/seed/answer_key.md`.
They are NOT part of the default seed: the default seed keeps the shared 45k/20k/30k = 95k table (616
daily records) and the six-document corpus that the contract fixtures are built from.

- `load_planted(session, ...)` adds the data traps to an already-seeded database (four imports and two
  extra corpus documents). Every step goes through the normal services, so loading twice adds nothing.
- `run_planted_checks()` replays the whole pack, including the outdated-proposal and self-approval
  scenarios, against a fresh temporary database through the HTTP API, and compares each result with the
  answer key. `python -m app.seed --check-planted` prints the table; `tests/test_planted.py` enforces it.
"""

from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.config import BACKEND_ROOT, Settings
from app.core.clock import Clock, IdFactory
from app.schemas.documents import DocumentIn
from app.seed import daily_spend
from app.services import corpus as corpus_svc
from app.services import imports as import_svc

PLANTED_DIR = BACKEND_ROOT / "seed" / "planted"
PLANTED_CORPUS_DIR = PLANTED_DIR / "corpus"
ANSWER_KEY = BACKEND_ROOT / "seed" / "answer_key.md"

DUPLICATE_FILE = "01_duplicate_billing_export.csv"
REEXPORT_FILE = "02_reexported_billing_export.csv"
CODEX_FILE = "03_codex_research_session.jsonl"
UNMAPPED_FILE = "04_unmapped_provider_project.csv"
OUTDATED_PROPOSAL_FILE = "05_outdated_proposal.json"

CODEX_ACCOUNT = "codex-research-laptops"
UNMAPPED_ACCOUNT = "proj-fable-eval-sandbox"
PLANTED_ACTOR = "seed-planted"
# The re-export (P1b) repeats every record of the generated daily seed export.
EXPECTED_SEED_RECORDS = len(daily_spend.rows())


@dataclass(frozen=True)
class PlantedImport:
    filename: str
    source_kind: str
    form: dict[str, str] = field(default_factory=dict)


# Order matters: the duplicate and re-export run right after the seed export they repeat.
PLANTED_IMPORTS: tuple[PlantedImport, ...] = (
    PlantedImport(DUPLICATE_FILE, "northstar_billing"),
    PlantedImport(REEXPORT_FILE, "northstar_billing"),
    # Real Codex telemetry format with fabricated counters, so it is labeled simulated, not measured.
    PlantedImport(CODEX_FILE, "codex_sessions",
                  {"source_account": CODEX_ACCOUNT, "value_kind_default": "simulated"}),
    PlantedImport(UNMAPPED_FILE, "northstar_billing"),
)


def planted_path(name: str) -> Path:
    return PLANTED_DIR / name


def load_planted(session: Session, *, clock: Clock, ids: IdFactory) -> list[dict[str, Any]]:
    """Add the planted data traps to a seeded database. Returns one summary row per step."""
    rows: list[dict[str, Any]] = []
    for item in PLANTED_IMPORTS:
        outcome = import_svc.run_import(
            session, source_kind=item.source_kind, raw=planted_path(item.filename).read_bytes(),
            filename=item.filename, actor_id=PLANTED_ACTOR, clock=clock, ids=ids,
            source_label=f"planted: {item.filename}", source_account=item.form.get("source_account"),
            value_kind_default=item.form.get("value_kind_default"),
        )
        batch = outcome.batch
        session.commit()
        rows.append({"step": item.filename, "status": batch.status, "records_added": batch.record_count,
                     "skipped_duplicates": batch.skipped_duplicate_records,
                     "unmapped": batch.unmapped_record_count})
    rows.extend(load_planted_corpus(session, clock=clock, ids=ids))
    return rows


def load_planted_corpus(session: Session, *, clock: Clock, ids: IdFactory) -> list[dict[str, Any]]:
    rows = []
    for path in sorted(PLANTED_CORPUS_DIR.glob("*.md")):
        data = DocumentIn(**corpus_svc.parse_markdown_document(path.read_text(encoding="utf-8")))
        result = corpus_svc.ingest_document(session, data, clock=clock, ids=ids)
        session.commit()
        rows.append({"step": path.name, "status": "created" if result.created else "unchanged",
                     "doc_key": result.document.doc_key, "version": result.document.version})
    return rows


# ---- answer-key checks ------------------------------------------------------------------------------


@dataclass
class Check:
    id: str
    name: str
    expected: Any
    actual: Any

    @property
    def passed(self) -> bool:
        return self.expected == self.actual


IMPORTER = {"X-Actor-Id": "imp-planted", "X-Actor-Role": "importer"}
ANALYST = {"X-Actor-Id": "fin-ana", "X-Actor-Role": "finance_analyst"}
APPROVER = {"X-Actor-Id": "fin-alice", "X-Actor-Role": "finance_approver"}


def _upload(client, item: PlantedImport):
    return client.post(
        "/api/imports", data={"source_kind": item.source_kind, **item.form},
        files={"file": (item.filename, planted_path(item.filename).read_bytes(), "text/plain")},
        headers=IMPORTER,
    )


def _team_spend(summary: dict) -> dict[str, str]:
    return {t["team"]: t["recorded_spend"] for t in summary["teams"]}


def _alloc(client) -> tuple[int, str, dict[str, str]]:
    b = client.get("/api/budget").json()
    return b["state_version"], b["envelope_total"], {a["team"]: a["amount"] for a in b["allocations"]}


def _codes(body: dict) -> list[str]:
    return sorted(w["code"] for w in body.get("warnings", []))


def _scenario(client) -> list[Check]:
    checks: list[Check] = []
    add = lambda cid, name, expected, actual: checks.append(Check(cid, name, expected, actual))  # noqa: E731
    base = client.get("/api/spend/summary").json()
    research_tokens_before = next(t["tokens"] for t in base["teams"] if t["team"] == "research")
    research_unpriced_before = next(t["unpriced_tokens"] for t in base["teams"] if t["team"] == "research")
    add("P0", "seed baseline team spend",
        {"research": "45000.00", "product": "20000.00", "engineering": "30000.00", "company": "95000.00"},
        {**_team_spend(base), "company": base["company_total"]})

    # P1 duplicate import file: byte-identical copy of the seed export.
    r = _upload(client, PLANTED_IMPORTS[0])
    b = r.json()
    add("P1", "identical export is a duplicate batch",
        {"http": 200, "status": "duplicate", "records_added": 0, "linked_to_original": True},
        {"http": r.status_code, "status": b["status"], "records_added": b["record_count"],
         "linked_to_original": b["duplicate_of_batch_id"] is not None})

    # P1b overlapping re-export: same records, different bytes (column order, row order, CRLF).
    r = _upload(client, PLANTED_IMPORTS[1])
    b = r.json()
    add("P1b", "re-export with a new hash dedupes per record key",
        {"http": 201, "records_added": 0, "skipped_duplicates": EXPECTED_SEED_RECORDS, "spend_added": "0.00"},
        {"http": r.status_code, "records_added": b["record_count"],
         "skipped_duplicates": b["skipped_duplicate_records"], "spend_added": b["spend_added"]})
    s = client.get("/api/spend/summary").json()
    add("P1c", "totals unchanged after both duplicates", "95000.00", s["company_total"])

    # P2 cumulative-counter trap: repeated total_token_usage snapshots.
    r = _upload(client, PLANTED_IMPORTS[2])
    b = r.json()
    s = client.get("/api/spend/summary").json()
    research = next(t for t in s["teams"] if t["team"] == "research")
    gained = {k: research["tokens"][k] - research_tokens_before[k] for k in research_tokens_before}
    add("P2", "cumulative counters become deltas; repeats add nothing",
        {"records_added": 3, "repeated_snapshots_skipped": 3,
         "tokens_added": {"input_tokens": 52000, "cached_input_tokens": 18000, "output_tokens": 7600,
                          "reasoning_tokens": 1500},
         # cached is part of input and reasoning is part of output: 52,000 + 7,600, not all four added.
         "unpriced_tokens_added": 59600,
         "research_spend": "45000.00", "spend_added": "0.00"},
        {"records_added": b["record_count"], "repeated_snapshots_skipped": b["stats"].get("repeated_snapshots_skipped"),
         "tokens_added": gained, "unpriced_tokens_added": research["unpriced_tokens"] - research_unpriced_before,
         "research_spend": research["recorded_spend"], "spend_added": b["spend_added"]})
    r = _upload(client, PLANTED_IMPORTS[2])
    add("P2b", "re-uploading the session file is a duplicate", "duplicate", r.json()["status"])

    # P3 unmapped provider project (with a `team` column that must not be trusted).
    r = _upload(client, PLANTED_IMPORTS[3])
    b = r.json()
    s = client.get("/api/spend/summary").json()
    add("P3", "unmapped project is unattributed and coverage is partial",
        {"unmapped_accounts": {UNMAPPED_ACCOUNT: 1}, "warnings": ["team_column_ignored", "unmapped_source_account"],
         "unattributed": "1800.00", "attributed_total": "95000.00", "company_total": "96800.00",
         "coverage": "partial", "research_spend": "45000.00"},
        {"unmapped_accounts": b["unmapped_accounts"], "warnings": _codes(b),
         "unattributed": s["unattributed"]["recorded_spend"], "attributed_total": s["attributed_total"],
         "company_total": s["company_total"], "coverage": s["coverage"]["status"],
         "research_spend": _team_spend(s)["research"]})
    r = client.put("/api/team-mappings", headers=ANALYST, json={
        "source_kind": "northstar_billing", "source_account": UNMAPPED_ACCOUNT, "team_id": "research",
        "effective_from": "2026-01-01"})
    s = client.get("/api/spend/summary").json()
    add("P3b", "explicit finance mapping re-attributes the record",
        {"http": 200, "research_spend": "46800.00", "unattributed": "0.00", "company_total": "96800.00"},
        {"http": r.status_code, "research_spend": _team_spend(s)["research"],
         "unattributed": s["unattributed"]["recorded_spend"], "company_total": s["company_total"]})

    # P4 conflicting / superseded documents (planted Slack restatement of the old timeline).
    state = client.app.state
    s = state.session_factory()
    try:
        load_planted_corpus(s, clock=state.clock, ids=state.id_factory)
    finally:
        s.close()
    items = client.get("/api/documents").json()["items"]
    docs = {d["doc_key"]: d for d in sorted(items, key=lambda d: d["version"])}  # latest version per key
    key_by_id = {d["id"]: d["doc_key"] for d in items}
    run = client.post("/api/agent/runs", headers=ANALYST, json={"task_type": "interpret_corpus"}).json()
    sigs = client.get("/api/signals").json()["items"]
    research_current = [s for s in sigs if s["team"] == "research" and s["status"] == "current"]
    not_interpreted = sorted(key_by_id.get(w.get("document_id"), "?") for w in (run.get("output") or {}).get("warnings", [])
                             if w["code"] == "document_not_interpreted")
    add("P4", "approved plan wins over older thread and informal restatement",
        {"documents": 8, "slack_plan_status": "informal", "thread_superseded_by": "research-eval-plan",
         "research_current_cites": ["research-eval-plan"], "thread_signal": "superseded",
         "not_interpreted_by_fake_runner": ["ap-late-invoice-email", "research-standup-slack"]},
        {"documents": len(items), "slack_plan_status": docs["research-standup-slack"]["plan_status"],
         "thread_superseded_by": (docs["research-timeline-thread"]["superseded_by"] or {}).get("doc_key"),
         "research_current_cites": sorted({c["doc_key"] for s in research_current for c in s["citations"]}),
         "thread_signal": next((s["status"] for s in sigs if any(
             c["doc_key"] == "research-timeline-thread" for c in s["citations"])), None),
         "not_interpreted_by_fake_runner": not_interpreted})

    # P5 proposal built on outdated budgets.
    planted = json.loads(planted_path(OUTDATED_PROPOSAL_FILE).read_text(encoding="utf-8"))
    old = client.post("/api/proposals", headers=planted["drafted_by"], json=planted["request"]).json()
    run = client.post("/api/agent/runs", headers=ANALYST, json={
        "task_type": "propose_allocation",
        "params": {"mode": "addition", "amount": "50000.00", "prioritize": "research"}}).json()
    new_id = run["proposals"][0]["id"]
    r = client.post(f"/api/proposals/{new_id}/decision", headers={**APPROVER, "Idempotency-Key": "planted-b"},
                    json={"outcome": "approve", "rationale": "outcome B reviewed against the approved research plan"})
    after_b = _alloc(client)
    r = client.post(f"/api/proposals/{old['id']}/decision", headers={**APPROVER, "Idempotency-Key": "planted-old"},
                    json={"outcome": "approve", "rationale": "approving the October draft"})
    err = r.json()["error"]
    events = client.get("/api/decision-events", params={"proposal_id": old["id"]}).json()
    events = events["items"] if isinstance(events, dict) else events
    add("P5", "approving the outdated draft is refused as stale; budget unchanged",
        {"addition_applied": (2, "250000.00", {"research": "95000.00", "product": "80000.00",
                                               "engineering": "75000.00"}),
         "http": 409, "code": "stale_proposal", "base_version": 1, "current_version": 2,
         "budget_after": (2, "250000.00", {"research": "95000.00", "product": "80000.00", "engineering": "75000.00"}),
         "proposal_status": "stale", "event": "stale_rejected"},
        {"addition_applied": after_b, "http": r.status_code, "code": err["code"],
         "base_version": err["details"].get("base_version"), "current_version": err["details"].get("current_version"),
         "budget_after": _alloc(client),
         "proposal_status": client.get(f"/api/proposals/{old['id']}").json()["status"],
         "event": events[0]["event"] if events else None})
    r = client.post("/api/proposals", headers=planted["drafted_by"], json=planted["request"])
    add("P5b", "re-submitting the outdated draft is refused up front", (409, "stale_base_version"),
        (r.status_code, r.json()["error"]["code"]))

    # P6 self-approval: the approver who rebases the stale draft becomes its requester.
    rebased = client.post(f"/api/proposals/{old['id']}/rebase", headers=APPROVER).json()
    r = client.post(f"/api/proposals/{rebased['id']}/decision", headers={**APPROVER, "Idempotency-Key": "planted-self"},
                    json={"outcome": "approve", "rationale": "my own rebase"})
    add("P6", "rebased draft needs fresh review; its requester cannot approve it",
        {"rebased_base_version": 2, "rebased_status": "pending_review", "http": 403,
         "code": "self_approval_forbidden", "budget_version": 2},
        {"rebased_base_version": rebased.get("base_version"), "rebased_status": rebased.get("status"),
         "http": r.status_code, "code": r.json()["error"]["code"], "budget_version": _alloc(client)[0]})
    return checks


def run_planted_checks(workdir: Path | None = None) -> list[Check]:
    """Replay the planted pack on a fresh temporary database (fake runner, placeholder forecast)."""
    from fastapi.testclient import TestClient

    from app.main import create_app
    from app.seed.northstar import seed

    with tempfile.TemporaryDirectory() as tmp:
        db = Path(workdir or tmp) / "planted-check.db"
        app = create_app(Settings(db_path=db, droid_runner="fake", forecast_provider="placeholder"))
        try:
            with TestClient(app) as client:
                s = app.state.session_factory()
                try:
                    seed(s, clock=app.state.clock, ids=app.state.id_factory)
                finally:
                    s.close()
                return _scenario(client)
        finally:
            app.state.engine.dispose()


def format_checks(checks: list[Check]) -> str:
    lines = []
    for c in checks:
        lines.append(f"{'PASS' if c.passed else 'FAIL'}  {c.id:<4} {c.name}")
        if not c.passed:
            lines.append(f"      expected: {c.expected}")
            lines.append(f"      actual:   {c.actual}")
    passed = sum(c.passed for c in checks)
    lines.append(f"{passed}/{len(checks)} planted checks match the answer key ({ANSWER_KEY.name})")
    return "\n".join(lines)
