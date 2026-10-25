"""An applied decision survives an app restart against the same SQLite file."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app
from budget_helpers import decide, draft, seed_budget, transfer_body


def test_applied_decision_survives_app_restart_same_db_file(app, client, settings, clock, id_factory):
    seed_budget(app)
    p = draft(client, transfer_body()).json()
    d = decide(client, p["id"], key="persist-1").json()
    app.state.engine.dispose()

    app2 = create_app(settings, clock=clock, id_factory=id_factory)
    try:
        with TestClient(app2) as c2:
            state = c2.get("/api/budget").json()
            assert state["state_version"] == 2
            assert {a["team"]: a["amount"] for a in state["allocations"]} == {
                "research": "85000.00", "product": "50000.00", "engineering": "65000.00"}
            assert state["last_decision_id"] == d["id"]
            assert c2.get(f"/api/proposals/{p['id']}").json()["status"] == "applied"
            # Replaying the same click after restart still applies nothing new.
            again = decide(c2, p["id"], key="persist-1")
            assert again.status_code == 200 and again.json()["replayed"] is True
            assert c2.get("/api/budget").json()["state_version"] == 2
    finally:
        app2.state.engine.dispose()
