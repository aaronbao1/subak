"""Bounded authority: Droid drafts only, only finance approvers decide, no self-approval."""

from __future__ import annotations

from budget_helpers import (
    ANALYST,
    APPROVER,
    APPROVER_2,
    DROID,
    IMPORTER_H,
    INITIAL,
    addition_body,
    allocations,
    decide,
    draft,
    seed_budget,
    transfer_body,
)


def test_self_approval_forbidden(app, client):
    seed_budget(app)
    p = draft(client, transfer_body(), headers=APPROVER).json()
    r = decide(client, p["id"], headers=APPROVER)
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "self_approval_forbidden"
    assert allocations(client) == INITIAL
    events = client.get("/api/decision-events", params={"proposal_id": p["id"]}).json()
    assert [e["event"] for e in events] == ["self_approval_blocked"]
    # A different approver can approve it.
    assert decide(client, p["id"], headers=APPROVER_2).status_code == 201


def test_droid_role_cannot_decide(app, client):
    seed_budget(app)
    p = draft(client, addition_body(), headers=DROID).json()
    for outcome in ("approve", "reject"):
        r = decide(client, p["id"], outcome, headers=DROID)
        assert r.status_code == 403
        assert r.json()["error"]["code"] == "role_forbidden"
    assert allocations(client) == INITIAL
    assert client.get(f"/api/proposals/{p['id']}").json()["status"] == "pending_review"
    events = client.get("/api/decision-events").json()
    assert [e["event"] for e in events] == ["role_blocked", "role_blocked"]
    assert all(e["details"]["actor_role"] == "droid_agent" for e in events)


def test_analyst_and_importer_cannot_decide(app, client):
    seed_budget(app)
    p = draft(client, transfer_body()).json()
    for headers in (ANALYST, IMPORTER_H):
        r = decide(client, p["id"], headers=headers)
        assert r.status_code == 403 and r.json()["error"]["code"] == "role_forbidden"
    assert allocations(client) == INITIAL


def test_non_approver_cannot_replay_an_existing_decision_key(app, client):
    seed_budget(app)
    p = draft(client, transfer_body()).json()
    assert decide(client, p["id"], key="shared").status_code == 201
    r = decide(client, p["id"], key="shared", headers=DROID)
    assert r.status_code == 403


def test_missing_or_unknown_identity_rejected(app, client):
    seed_budget(app)
    p = draft(client, transfer_body()).json()
    r = client.post(f"/api/proposals/{p['id']}/decision", json={"outcome": "approve", "rationale": "x"},
                    headers={"Idempotency-Key": "z"})
    assert r.status_code == 401
    r = client.post(f"/api/proposals/{p['id']}/decision", json={"outcome": "approve", "rationale": "x"},
                    headers={"X-Actor-Id": "eve", "X-Actor-Role": "admin", "Idempotency-Key": "z"})
    assert r.status_code == 403 and r.json()["error"]["code"] == "unknown_role"


def test_revise_replaces_pending_proposal(app, client):
    seed_budget(app)
    p = draft(client, transfer_body()).json()
    r = client.post(f"/api/proposals/{p['id']}/revise", headers=ANALYST, json=transfer_body(
        [{"from_team": "product", "to_team": "research", "amount": "20000.00"}],
        rationale="trim: only the approved eval expansion"))
    assert r.status_code == 201, r.text
    new = r.json()
    assert new["revises_proposal_id"] == p["id"]
    assert new["requester"]["id"] == "ana"
    old = client.get(f"/api/proposals/{p['id']}").json()
    assert old["status"] == "revised" and old["replaced_by_proposal_id"] == new["id"]
    # The revised original can no longer be decided.
    assert decide(client, p["id"]).json()["error"]["code"] == "proposal_not_pending"
    assert decide(client, new["id"]).status_code == 201
    assert allocations(client) == {"research": "80000.00", "product": "60000.00", "engineering": "60000.00"}


def test_revise_is_finance_only_and_cannot_touch_decided(app, client):
    seed_budget(app)
    p = draft(client, transfer_body()).json()
    assert client.post(f"/api/proposals/{p['id']}/revise", headers=DROID, json=transfer_body()).status_code == 403
    decide(client, p["id"], "reject", rationale="no")
    r = client.post(f"/api/proposals/{p['id']}/revise", headers=ANALYST, json=transfer_body(base_version=1))
    assert r.status_code == 409 and r.json()["error"]["code"] == "proposal_not_pending"


def test_original_requester_cannot_approve_a_revision_of_their_request(app, client):
    seed_budget(app)
    p = draft(client, transfer_body(), headers=APPROVER).json()
    new = client.post(f"/api/proposals/{p['id']}/revise", headers=APPROVER_2, json=transfer_body(
        [{"from_team": "product", "to_team": "research", "amount": "10000.00"}])).json()
    r = decide(client, new["id"], headers=APPROVER)
    assert r.status_code == 403 and r.json()["error"]["code"] == "self_approval_forbidden"
    r = decide(client, new["id"], headers=APPROVER_2)
    assert r.status_code == 403  # the reviser authored the revision
    assert allocations(client) == INITIAL
    third = {"X-Actor-Id": "fin-carol", "X-Actor-Role": "finance_approver"}
    assert decide(client, new["id"], headers=third).status_code == 201


def _start_run(client, headers, **params):
    body = {"task_type": "propose_allocation",
            "params": {"mode": "transfer", "amount": "30000.00", "prioritize": "research", **params}}
    r = client.post("/api/agent/runs", json=body, headers=headers)
    assert r.status_code in (200, 201), r.text
    return r.json()


def test_approver_cannot_approve_a_droid_draft_from_a_run_they_started(seeded, client):
    out = _start_run(client, APPROVER)
    pid = out["proposals"][0]["id"]
    r = decide(client, pid, headers=APPROVER)
    assert r.status_code == 403
    err = r.json()["error"]
    assert err["code"] == "self_approval_forbidden" and err["details"]["via_agent_run"] is True
    assert allocations(client) == INITIAL
    events = client.get("/api/decision-events", params={"proposal_id": pid}).json()
    assert [e["event"] for e in events] == ["self_approval_blocked"]
    # The requester may still reject it, and a different approver may approve it.
    assert decide(client, pid, headers=APPROVER_2).status_code == 201


def test_approver_who_reran_droid_onto_an_existing_draft_is_also_a_requester(seeded, client):
    first = _start_run(client, ANALYST)
    again = _start_run(client, APPROVER)  # identical intent: the pending draft is reused
    pid = first["proposals"][0]["id"]
    assert again["proposals"][0]["id"] == pid
    r = decide(client, pid, headers=APPROVER)
    assert r.status_code == 403 and r.json()["error"]["code"] == "self_approval_forbidden"
    assert decide(client, pid, headers=APPROVER_2).status_code == 201


def test_rebased_droid_draft_still_blocks_the_run_initiator(seeded, client):
    out = _start_run(client, APPROVER)
    pid = out["proposals"][0]["id"]
    # Another change lands first, so the Droid draft goes stale and an analyst rebases it.
    other = draft(client, addition_body(base_version=1), headers=ANALYST).json()
    assert decide(client, other["id"], headers=APPROVER_2).status_code == 201
    rebased = client.post(f"/api/proposals/{pid}/rebase", headers=ANALYST, json={})
    assert rebased.status_code == 201, rebased.text
    r = decide(client, rebased.json()["id"], headers=APPROVER)
    assert r.status_code == 403 and r.json()["error"]["code"] == "self_approval_forbidden"
