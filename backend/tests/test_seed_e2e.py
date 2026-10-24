"""End to end: seed twice through the CLI -> totals unchanged; fake Droid drafts outcome B; finance approves."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.seed import __main__ as seed_cli
from app.seed.northstar import SPEND_FILE, seed

ANALYST = {"X-Actor-Id": "fin-ana", "X-Actor-Role": "finance_analyst"}
APPROVER = {"X-Actor-Id": "fin-alice", "X-Actor-Role": "finance_approver"}
IMPORTER = {"X-Actor-Id": "imp-1", "X-Actor-Role": "importer"}
INITIAL = {"research": "60000.00", "product": "80000.00", "engineering": "60000.00"}
SPEND = {"research": "45000.00", "product": "20000.00", "engineering": "30000.00"}
OUTCOME_B = {"research": "95000.00", "product": "80000.00", "engineering": "75000.00"}


def _totals(client) -> dict:
    s = client.get("/api/spend/summary").json()
    b = client.get("/api/budget").json()
    return {
        "spend": {t["team"]: t["recorded_spend"] for t in s["teams"]},
        "company_total": s["company_total"],
        "coverage": s["coverage"]["status"],
        "records": s["coverage"]["record_count"],
        "allocations": {a["team"]: a["amount"] for a in b["allocations"]},
        "envelope": b["envelope_total"],
        "version": b["state_version"],
        "documents": len(client.get("/api/documents").json()["items"]),
        "imports": len(client.get("/api/imports").json()),
    }


def test_seed_cli_twice_then_agent_proposal_approved_end_to_end(tmp_path, monkeypatch, capsys, clock, id_factory):
    db = tmp_path / "e2e.db"
    monkeypatch.setenv("BACKEND_DB_PATH", str(db))
    assert seed_cli.main([]) == 0
    assert seed_cli.main([]) == 0
    out = capsys.readouterr().out
    assert out.count("seeded: ") == 2 and "already seeded" in out

    app = create_app(Settings(db_path=db, droid_runner="fake", forecast_provider="placeholder"),
                     clock=clock, id_factory=id_factory)
    try:
        with TestClient(app) as client:
            first = _totals(client)
            assert first["spend"] == SPEND and first["company_total"] == "95000.00"
            assert first["coverage"] == "complete"
            assert first["allocations"] == INITIAL and first["envelope"] == "200000.00" and first["version"] == 1
            assert first["documents"] == 6 and first["imports"] == 1

            # Seed a third time in-process and re-post the seed export through the API: nothing changes.
            s = app.state.session_factory()
            try:
                assert seed(s, clock=app.state.clock, ids=app.state.id_factory) is False
            finally:
                s.close()
            r = client.post("/api/imports", data={"source_kind": "northstar_billing"},
                            files={"file": (SPEND_FILE.name, SPEND_FILE.read_bytes(), "text/csv")}, headers=IMPORTER)
            assert r.status_code == 200 and r.json()["status"] == "duplicate"
            assert {k: v for k, v in _totals(client).items() if k != "imports"} == {
                k: v for k, v in first.items() if k != "imports"}

            # Fake Droid drafts outcome B; nothing is applied until finance approves.
            run = client.post("/api/agent/runs", headers=ANALYST, json={
                "task_type": "propose_allocation",
                "params": {"mode": "addition", "amount": "50000.00", "prioritize": "research"}}).json()
            assert run["runner_kind"] == "fake" and run["status"] == "succeeded"
            assert run["applied_changes"] is False
            [proposal] = run["proposals"]
            assert proposal["status"] == "pending_review"
            assert _totals(client)["allocations"] == INITIAL

            p = client.get(f"/api/proposals/{proposal['id']}").json()
            assert p["action_type"] == "addition" and p["envelope_increase"] == "50000.00"
            assert p["base_version"] == 1

            r = client.post(f"/api/proposals/{proposal['id']}/decision",
                            headers={**APPROVER, "Idempotency-Key": "e2e-approve-b"},
                            json={"outcome": "approve", "rationale": "approved research plan; +50k envelope"})
            assert r.status_code == 201, r.text
            decision = r.json()
            assert decision["from_version"] == 1 and decision["to_version"] == 2

            after = _totals(client)
            assert after["allocations"] == OUTCOME_B and after["envelope"] == "250000.00" and after["version"] == 2
            assert after["spend"] == SPEND and after["company_total"] == "95000.00"  # budgets moved, spend did not

            # Replaying the same approval applies nothing a second time.
            r = client.post(f"/api/proposals/{proposal['id']}/decision",
                            headers={**APPROVER, "Idempotency-Key": "e2e-approve-b"},
                            json={"outcome": "approve", "rationale": "approved research plan; +50k envelope"})
            assert r.status_code == 200 and r.json()["replayed"] is True
            assert _totals(client)["version"] == 2

            history = client.get("/api/decisions").json()
            assert len(history) == 1 and history[0]["actor"]["id"] == "fin-alice"
    finally:
        app.state.engine.dispose()

    # Persisted: a fresh app on the same file still sees outcome B; seeding again is still a no-op.
    assert seed_cli.main([]) == 0
    app2 = create_app(Settings(db_path=db), clock=clock, id_factory=id_factory)
    try:
        with TestClient(app2) as client:
            again = _totals(client)
            assert again["allocations"] == OUTCOME_B and again["envelope"] == "250000.00"
            assert again["company_total"] == "95000.00"
    finally:
        app2.state.engine.dispose()
