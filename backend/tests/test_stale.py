"""Proposals based on outdated budgets must be reviewed against the current state before applying."""

from __future__ import annotations

from budget_helpers import (
    APPROVER,
    APPROVER_2,
    DROID,
    addition_body,
    allocations,
    decide,
    draft,
    reasons,
    seed_budget,
    transfer_body,
)

AFTER_A = {"research": "85000.00", "product": "50000.00", "engineering": "65000.00"}


def _two_pending_then_apply_first(client):
    a = draft(client, transfer_body()).json()
    b = draft(client, addition_body()).json()
    assert decide(client, a["id"]).status_code == 201  # budget moves to v2
    return a, b


def test_apply_against_changed_version_is_409_stale_and_budget_unchanged(app, client):
    seed_budget(app)
    _, b = _two_pending_then_apply_first(client)
    r = decide(client, b["id"])
    assert r.status_code == 409
    err = r.json()["error"]
    assert err["code"] == "stale_proposal"
    assert err["details"]["base_version"] == 1
    assert err["details"]["current_version"] == 2
    assert err["details"]["current"]["allocations"]["research"] == "85000.00"
    assert err["details"]["proposal_before"]["allocations"]["research"] == "60000.00"
    state = client.get("/api/budget").json()
    assert state["state_version"] == 2 and state["envelope_total"] == "200000.00"
    assert allocations(client) == AFTER_A
    assert client.get(f"/api/proposals/{b['id']}").json()["status"] == "stale"
    # Retrying the same approval does not sneak through.
    again = decide(client, b["id"])
    assert again.status_code == 409 and again.json()["error"]["code"] == "proposal_not_pending"
    assert allocations(client) == AFTER_A


def test_stale_attempt_recorded_in_decision_events(app, client):
    seed_budget(app)
    _, b = _two_pending_then_apply_first(client)
    decide(client, b["id"])
    events = client.get("/api/decision-events", params={"proposal_id": b["id"]}).json()
    assert len(events) == 1
    assert events[0]["event"] == "stale_rejected"
    assert events[0]["actor_id"] == "fin-alice"
    assert events[0]["details"]["base_version"] == 1 and events[0]["details"]["current_version"] == 2
    assert client.get(f"/api/proposals/{b['id']}").json()["blocked_attempts"][0]["event"] == "stale_rejected"
    # A stale attempt is not a decision.
    assert len(client.get("/api/decisions").json()) == 1


def test_get_proposal_reports_is_stale(app, client):
    seed_budget(app)
    _, b = _two_pending_then_apply_first(client)
    p = client.get(f"/api/proposals/{b['id']}").json()
    assert p["status"] == "pending_review"
    assert p["is_stale"] is True
    assert (p["base_version"], p["current_version"]) == (1, 2)


def test_rebase_creates_new_pending_proposal_requiring_fresh_review(app, client):
    seed_budget(app)
    _, b = _two_pending_then_apply_first(client)
    decide(client, b["id"])  # marks stale
    r = client.post(f"/api/proposals/{b['id']}/rebase", json={}, headers=DROID)
    assert r.status_code == 201, r.text
    new = r.json()
    assert new["id"] != b["id"]
    assert new["status"] == "pending_review" and new["is_stale"] is False
    assert new["base_version"] == 2
    assert new["rebased_from_proposal_id"] == b["id"]
    assert new["action_type"] == "addition"
    assert new["before"]["allocations"] == {"engineering": "65000.00", "product": "50000.00", "research": "85000.00"}
    assert new["after"]["total"] == "250000.00"
    assert new["after"]["allocations"] == {"engineering": "80000.00", "product": "50000.00", "research": "120000.00"}
    assert client.get(f"/api/proposals/{b['id']}").json()["replaced_by_proposal_id"] == new["id"]
    # Rebasing applied nothing; a fresh decision is required.
    assert allocations(client) == AFTER_A
    d = decide(client, new["id"], headers=APPROVER_2)
    assert d.status_code == 201
    assert client.get("/api/budget").json()["state_version"] == 3


def test_rebase_of_pending_outdated_proposal_marks_original_stale(app, client):
    seed_budget(app)
    _, b = _two_pending_then_apply_first(client)
    r = client.post(f"/api/proposals/{b['id']}/rebase", headers=DROID)
    assert r.status_code == 201
    assert client.get(f"/api/proposals/{b['id']}").json()["status"] == "stale"


def test_rebase_that_no_longer_fits_is_explained(app, client):
    seed_budget(app)
    big = draft(client, transfer_body([{"from_team": "product", "to_team": "research", "amount": "60000.00"}])).json()
    other = draft(client, transfer_body([{"from_team": "product", "to_team": "engineering", "amount": "30000.00"}])).json()
    assert decide(client, other["id"]).status_code == 201  # product now 50k
    r = client.post(f"/api/proposals/{big['id']}/rebase", headers=DROID)
    assert r.status_code == 422
    assert "negative_allocation_result" in reasons(r)
    # Nothing was created or changed.
    assert client.get(f"/api/proposals/{big['id']}").json()["status"] == "pending_review"
    assert len(client.get("/api/proposals").json()) == 2


def test_rebase_of_current_proposal_is_409(app, client):
    seed_budget(app)
    p = draft(client, transfer_body()).json()
    r = client.post(f"/api/proposals/{p['id']}/rebase", headers=DROID)
    assert r.status_code == 409 and r.json()["error"]["code"] == "proposal_not_stale"


def test_rebaser_becomes_requester_and_cannot_approve(app, client):
    seed_budget(app)
    _, b = _two_pending_then_apply_first(client)
    new = client.post(f"/api/proposals/{b['id']}/rebase", headers=APPROVER).json()
    assert new["requester"]["id"] == "fin-alice"
    r = decide(client, new["id"], headers=APPROVER)
    assert r.status_code == 403 and r.json()["error"]["code"] == "self_approval_forbidden"
