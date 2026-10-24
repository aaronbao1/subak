"""Budget state, invariant and snapshot history."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.core.errors import DomainError
from app.services import budget as budget_svc
from budget_helpers import APPROVER, INITIAL, decide, draft, seed_budget, transfer_body
from reference_data import seed_reference


def test_initial_state_is_v1_60_80_60_total_200(app, client):
    seed_budget(app)
    r = client.get("/api/budget")
    assert r.status_code == 200
    body = r.json()
    assert body["state_version"] == 1
    assert body["envelope_total"] == "200000.00"
    assert body["allocated_total"] == "200000.00"
    assert body["unit"] == "USD"
    assert body["period"]["id"] == "2026-P1"
    assert {a["team"]: a["amount"] for a in body["allocations"]} == INITIAL
    assert body["last_decision_id"] is None


def test_budget_state_shows_recorded_spend_45_20_30(app, client):
    seed_budget(app, with_spend=True, client=client)
    body = client.get("/api/budget").json()
    spend = {a["team"]: a["recorded_spend"] for a in body["allocations"]}
    # Included usage (ns-003) is never counted as spend.
    assert spend == {"research": "45000.00", "product": "20000.00", "engineering": "30000.00"}
    remaining = {a["team"]: a["remaining"] for a in body["allocations"]}
    assert remaining == {"research": "15000.00", "product": "60000.00", "engineering": "30000.00"}


def test_no_envelope_is_404_not_zero(app, client, session):
    seed_reference(session)
    r = client.get("/api/budget")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "no_budget"


def test_unknown_period_is_404(app, client):
    seed_budget(app)
    r = client.get("/api/budget", params={"period": "1999-P9"})
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "unknown_period"


def test_create_envelope_twice_is_conflict(app, session):
    seed_budget(app)
    with pytest.raises(DomainError) as exc:
        budget_svc.create_envelope(session, period_id="2026-P1", unit="USD", allocations=INITIAL,
                                   clock=app.state.clock, ids=app.state.id_factory)
    assert exc.value.code == "budget_exists"


def test_create_envelope_rejects_float_and_negative(app, session):
    seed_reference(session)
    with pytest.raises(Exception):
        budget_svc.create_envelope(session, period_id="2026-P1", unit="USD", allocations={"research": 1.5},
                                   clock=app.state.clock, ids=app.state.id_factory)
    with pytest.raises(DomainError) as exc:
        budget_svc.create_envelope(session, period_id="2026-P1", unit="USD", allocations={"research": "-1.00"},
                                   clock=app.state.clock, ids=app.state.id_factory)
    assert exc.value.code == "negative_allocation_result"


def test_invariant_detects_tampered_total(app, session):
    seed_budget(app)
    env = budget_svc.get_envelope(session, "2026-P1")
    env.total_amount = Decimal("200000.01")
    with pytest.raises(DomainError) as exc:
        budget_svc.assert_invariant(env)
    assert exc.value.code == "budget_invariant_violated"


def test_history_snapshots_link_to_decisions(app, client):
    seed_budget(app)
    h = client.get("/api/budget/history").json()
    assert [s["state_version"] for s in h["snapshots"]] == [1]
    assert h["snapshots"][0]["decision"] is None

    p = draft(client, transfer_body()).json()
    d = decide(client, p["id"], rationale="approved research plan supersedes old thread").json()

    h = client.get("/api/budget/history").json()
    assert h["current_version"] == 2
    v1, v2 = h["snapshots"]
    assert v1["allocations"] == INITIAL  # immutable: v1 is still the original state
    assert v2["state_version"] == 2
    assert v2["allocations"] == {"research": "85000.00", "product": "50000.00", "engineering": "65000.00"}
    assert v2["decision"]["id"] == d["id"]
    assert v2["decision"]["proposal_id"] == p["id"]
    assert v2["decision"]["action_type"] == "transfer"
    assert v2["decision"]["actor_id"] == APPROVER["X-Actor-Id"]
    assert v2["decision"]["rationale"] == "approved research plan supersedes old thread"
    assert client.get("/api/budget").json()["last_decision_id"] == d["id"]
