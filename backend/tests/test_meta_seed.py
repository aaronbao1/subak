"""/api/meta, the Northstar seed, and the guarded demo reset."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.seed.northstar import seed


def test_meta_reports_modes_and_labels(seeded, client):
    m = client.get("/api/meta").json()
    assert m["period"]["id"] == "2026-P1" and m["unit"] == "USD"
    assert m["runner_kind"] == "fake" and m["forecast_mode"] == "placeholder"
    assert m["identity_mode"] == "demo_headers_unauthenticated"
    statuses = {r["component"]: r["status"] for r in m["real_vs_simulated"]}
    assert statuses["northstar_spend_budgets_corpus"] == "simulated"
    assert statuses["projections"] == "placeholder" and statuses["droid_runner"] == "fake"


def test_meta_answers_on_empty_database(client):
    r = client.get("/api/meta")
    assert r.status_code == 200 and r.json()["period"] is None


def test_seed_is_idempotent_and_matches_northstar(seeded, client):
    s = seeded.state.session_factory()
    try:
        assert seed(s, clock=seeded.state.clock, ids=seeded.state.id_factory) is False
    finally:
        s.close()
    budget = client.get("/api/budget").json()
    assert {a["team"]: a["amount"] for a in budget["allocations"]} == {
        "research": "60000.00", "product": "80000.00", "engineering": "60000.00"}
    docs = client.get("/api/documents").json()["items"]
    assert len(docs) == 13
    by_key = {(d["doc_key"], d["version"]): d for d in docs}
    people = {p["id"] for p in client.get("/api/people").json()}
    tagged = {d["doc_key"]: d["person_tags"] for d in docs if d["person_tags"]}
    assert len(tagged) == 6 and all(set(t) <= people for t in tagged.values())
    assert by_key[("company-model-announcement-slack", 1)]["integration"] == "slack"
    assert by_key[("research-harness-asana", 1)]["integration"] == "asana"
    assert by_key[("research-eval-plan", 1)]["integration"] is None and by_key[("research-eval-plan", 1)]["person_tags"] == []
    assert by_key[("research-timeline-thread", 1)]["superseded_by"]["doc_key"] == "research-eval-plan"
    assert by_key[("product-launch-plan", 1)]["is_current"] is False
    assert by_key[("marketing-ideas-slack", 1)]["plan_status"] == "informal"
    assert all(d["is_simulated"] for d in docs)


def test_reset_disabled_by_default(seeded, client):
    r = client.post("/api/admin/reset")
    assert r.status_code == 403 and r.json()["error"]["code"] == "reset_disabled"


def test_reset_restores_seed_state(tmp_path, clock, id_factory):
    app = create_app(Settings(db_path=tmp_path / "r.db", allow_reset=True), clock=clock, id_factory=id_factory)
    try:
        with TestClient(app) as c:
            assert c.post("/api/admin/reset").status_code == 200
            droid = {"X-Actor-Id": "d", "X-Actor-Role": "droid_agent"}
            approver = {"X-Actor-Id": "a", "X-Actor-Role": "finance_approver", "Idempotency-Key": "k1"}
            p = c.post("/api/proposals", headers=droid, json={
                "action_type": "transfer", "base_version": 1, "rationale": "r",
                "lines": [{"from_team": "product", "to_team": "research", "amount": "1000.00"}]}).json()
            assert c.post(f"/api/proposals/{p['id']}/decision", headers=approver,
                          json={"outcome": "approve", "rationale": "ok"}).status_code == 201
            assert c.get("/api/budget").json()["state_version"] == 2
            assert c.post("/api/admin/reset").status_code == 200
            assert c.get("/api/budget").json()["state_version"] == 1
            assert c.get("/api/spend/summary").json()["company_total"] == "95000.00"
            assert c.get("/api/decisions").json() == []
    finally:
        app.state.engine.dispose()
