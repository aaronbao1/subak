"""Finance decisions: exact Northstar outcomes, rejection, idempotency, explainable history."""

from __future__ import annotations

from budget_helpers import (
    APPROVER,
    APPROVER_2,
    DROID,
    INITIAL,
    addition_body,
    allocations,
    decide,
    draft,
    seed_budget,
    transfer_body,
)

OUTCOME_A = {"research": "85000.00", "product": "50000.00", "engineering": "65000.00"}
OUTCOME_B = {"research": "95000.00", "product": "80000.00", "engineering": "75000.00"}


def test_apply_transfer_outcome_a_85_50_65_total_200(app, client):
    seed_budget(app)
    p = draft(client, transfer_body()).json()
    r = decide(client, p["id"])
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["outcome"] == "approved_applied"
    assert d["action_type"] == "transfer"
    assert (d["from_version"], d["to_version"]) == (1, 2)
    assert d["after"]["total"] == "200000.00"
    assert d["replayed"] is False
    state = client.get("/api/budget").json()
    assert state["state_version"] == 2
    assert state["envelope_total"] == "200000.00"
    assert allocations(client) == OUTCOME_A
    assert d["budget_state"]["state_version"] == 2
    assert client.get(f"/api/proposals/{p['id']}").json()["status"] == "applied"


def test_apply_addition_outcome_b_95_80_75_total_250(app, client):
    seed_budget(app)
    p = draft(client, addition_body()).json()
    d = decide(client, p["id"]).json()
    assert d["outcome"] == "approved_applied"
    assert d["action_type"] == "addition"
    assert d["before"]["total"] == "200000.00"
    assert d["after"]["total"] == "250000.00"
    state = client.get("/api/budget").json()
    assert state["envelope_total"] == "250000.00"
    assert state["allocated_total"] == "250000.00"
    assert state["state_version"] == 2
    assert allocations(client) == OUTCOME_B


def test_reject_leaves_allocations_and_version_unchanged(app, client):
    seed_budget(app)
    p = draft(client, addition_body()).json()
    before_history = client.get("/api/budget/history").json()
    r = decide(client, p["id"], "reject", rationale="no new money this period")
    assert r.status_code == 201
    d = r.json()
    assert d["outcome"] == "rejected"
    assert d["to_version"] is None and d["after"] is None
    assert d["from_version"] == 1
    assert allocations(client) == INITIAL
    state = client.get("/api/budget").json()
    assert state["state_version"] == 1 and state["envelope_total"] == "200000.00"
    assert client.get("/api/budget/history").json() == before_history
    assert client.get(f"/api/proposals/{p['id']}").json()["status"] == "rejected"
    # A rejected proposal cannot be approved afterwards.
    again = decide(client, p["id"], headers=APPROVER_2)
    assert again.status_code == 409 and again.json()["error"]["code"] == "proposal_not_pending"
    assert allocations(client) == INITIAL


def test_same_idempotency_key_replays_without_second_apply(app, client):
    seed_budget(app)
    p = draft(client, addition_body()).json()
    first = decide(client, p["id"], key="click-1")
    second = decide(client, p["id"], key="click-1")
    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json()["replayed"] is True
    assert second.json()["id"] == first.json()["id"]
    assert (second.json()["from_version"], second.json()["to_version"]) == (1, 2)
    state = client.get("/api/budget").json()
    assert state["state_version"] == 2
    assert state["envelope_total"] == "250000.00"  # applied once, not 300k
    assert len(client.get("/api/decisions").json()) == 1
    assert len(client.get("/api/budget/history").json()["snapshots"]) == 2


def test_second_decision_on_applied_proposal_is_409_not_pending(app, client):
    seed_budget(app)
    p = draft(client, transfer_body()).json()
    assert decide(client, p["id"], key="a").status_code == 201
    r = decide(client, p["id"], key="b")  # double click with a fresh key
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "proposal_not_pending"
    assert r.json()["error"]["details"]["status"] == "applied"
    assert allocations(client) == OUTCOME_A
    assert client.get("/api/budget").json()["state_version"] == 2


def test_reused_key_with_different_payload_is_409(app, client):
    seed_budget(app)
    p1 = draft(client, transfer_body()).json()
    p2 = draft(client, addition_body()).json()
    assert decide(client, p1["id"], key="k").status_code == 201
    r = decide(client, p2["id"], key="k")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "idempotency_key_reused"
    r = decide(client, p1["id"], key="k", rationale="different reason")
    assert r.json()["error"]["code"] == "idempotency_key_reused"


def test_missing_idempotency_key_is_400(app, client):
    seed_budget(app)
    p = draft(client, transfer_body()).json()
    r = client.post(f"/api/proposals/{p['id']}/decision", json={"outcome": "approve", "rationale": "ok"},
                    headers=APPROVER)
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "idempotency_key_required"
    assert allocations(client) == INITIAL


def test_decision_rationale_required(app, client):
    seed_budget(app)
    p = draft(client, transfer_body()).json()
    r = decide(client, p["id"], rationale="   ")
    assert r.status_code == 422
    assert allocations(client) == INITIAL


def test_decision_on_unknown_proposal_is_404(app, client):
    seed_budget(app)
    r = decide(client, "missing")
    assert r.status_code == 404


def test_decision_history_has_actor_role_time_rationale_evidence_before_after(app, client):
    seed_budget(app)
    p = draft(client, transfer_body(rationale="research expansion per approved plan",
                                    evidence_refs=[{"kind": "spend_summary", "id": "2026-P1"}])).json()
    d = decide(client, p["id"], rationale="matches approved research plan; launch moved",
               evidence_refs=[{"kind": "spend_summary", "id": "2026-P1", "note": "45/20/30 recorded"}]).json()
    hist = client.get("/api/decisions").json()
    assert len(hist) == 1
    h = hist[0]
    assert h["id"] == d["id"]
    assert h["actor"] == {"id": "fin-alice", "role": "finance_approver"}
    assert h["requester"] == {"id": "droid", "role": "droid_agent"}
    assert h["decided_at"].startswith("2026-10-24T12:00:00")
    assert h["rationale"] == "matches approved research plan; launch moved"
    assert h["evidence_refs"][0]["note"] == "45/20/30 recorded"
    assert h["proposal_evidence_refs"][0]["id"] == "2026-P1"
    assert h["before"]["allocations"] == INITIAL
    assert h["after"]["allocations"] == OUTCOME_A
    assert [ln["amount"] for ln in h["lines"]] == ["25000.00", "5000.00"]
    assert client.get(f"/api/decisions/{d['id']}").json()["id"] == d["id"]
    assert client.get("/api/decisions", params={"proposal_id": p["id"]}).json()[0]["id"] == d["id"]
    assert client.get("/api/decisions/nope").status_code == 404


def test_requester_may_reject_own_proposal(app, client):
    seed_budget(app)
    p = draft(client, transfer_body(), headers=APPROVER).json()
    r = decide(client, p["id"], "reject", headers=APPROVER, rationale="withdrawing my own draft")
    assert r.status_code == 201
    assert allocations(client) == INITIAL


def test_droid_drafted_proposal_approved_by_finance(app, client):
    seed_budget(app)
    p = draft(client, addition_body(), headers=DROID).json()
    assert decide(client, p["id"], headers=APPROVER_2).status_code == 201
    assert allocations(client) == OUTCOME_B
