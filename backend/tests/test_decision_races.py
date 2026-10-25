"""Concurrent decisions: a losing approver never rewrites a settled proposal, and a revise in flight
cannot be overtaken by an approval of the proposal it replaced."""

from __future__ import annotations

import pytest

from app.core.actors import Actor
from app.core.errors import DomainError
from app.db.models import Proposal
from app.schemas.decisions import DecisionCreate
from app.services import decisions as decision_svc
from budget_helpers import ANALYST, APPROVER, INITIAL, allocations, decide, draft, seed_budget, transfer_body

BOB = Actor("fin-bob", "finance_approver")
OUTCOME_A = {"research": "85000.00", "product": "50000.00", "engineering": "65000.00"}


def _decide_in(session, app, pid, key="race-b"):
    return decision_svc.decide(session, pid, DecisionCreate(outcome="approve", rationale="ok"), actor=BOB,
                               idempotency_key=key, clock=app.state.clock, ids=app.state.id_factory)


def test_losing_concurrent_approval_does_not_mark_applied_proposal_stale(app, client):
    seed_budget(app)
    pid = draft(client, transfer_body()).json()["id"]
    b = app.state.session_factory()
    try:
        held = b.get(Proposal, pid)  # keep a strong ref: B has read it as pending (passed its check)
        assert held.status == "pending_review"
        assert decide(client, pid, headers=APPROVER).status_code == 201  # A wins
        with pytest.raises(DomainError) as exc:
            _decide_in(b, app, pid)
        assert exc.value.code == "proposal_not_pending"
    finally:
        b.close()
    p = client.get(f"/api/proposals/{pid}").json()
    assert p["status"] == "applied"
    assert allocations(client) == OUTCOME_A
    # Because the proposal is not stale, it cannot be rebased into a second copy of the same intent.
    r = client.post(f"/api/proposals/{pid}/rebase", headers=ANALYST, json={})
    assert r.status_code == 409
    assert allocations(client) == OUTCOME_A
    events = [e["event"] for e in client.get("/api/decision-events", params={"proposal_id": pid}).json()]
    assert "stale_rejected" not in events


def test_approval_racing_a_revise_is_rejected_and_budget_untouched(app, client):
    seed_budget(app)
    pid = draft(client, transfer_body()).json()["id"]
    b = app.state.session_factory()
    try:
        held = b.get(Proposal, pid)  # keep a strong ref: B has read it as pending (passed its check)
        assert held.status == "pending_review"
        r = client.post(f"/api/proposals/{pid}/revise", headers=ANALYST, json=transfer_body(
            [{"from_team": "product", "to_team": "research", "amount": "20000.00"}],
            rationale="smaller transfer after review"))
        assert r.status_code == 201
        with pytest.raises(DomainError) as exc:
            _decide_in(b, app, pid)
        assert exc.value.code == "proposal_not_pending"
    finally:
        b.close()
    assert client.get(f"/api/proposals/{pid}").json()["status"] == "revised"
    assert allocations(client) == INITIAL
    assert client.get("/api/budget").json()["state_version"] == 1
    assert client.get("/api/decisions").json() == []


def test_rejection_racing_a_revise_is_rejected(app, client):
    seed_budget(app)
    pid = draft(client, transfer_body()).json()["id"]
    b = app.state.session_factory()
    try:
        held = b.get(Proposal, pid)  # keep a strong ref: B has read it as pending (passed its check)
        assert held.status == "pending_review"
        assert client.post(f"/api/proposals/{pid}/revise", headers=ANALYST,
                           json=transfer_body(rationale="revised")).status_code == 201
        with pytest.raises(DomainError) as exc:
            decision_svc.decide(b, pid, DecisionCreate(outcome="reject", rationale="no"), actor=BOB,
                                idempotency_key="race-r", clock=app.state.clock, ids=app.state.id_factory)
        assert exc.value.code == "proposal_not_pending"
    finally:
        b.close()
    assert client.get(f"/api/proposals/{pid}").json()["status"] == "revised"
