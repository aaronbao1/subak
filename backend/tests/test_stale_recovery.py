"""Stale-proposal recovery: finance hits 409 stale_proposal, Droid explains what changed and offers a
rebased draft (a NEW pending_review proposal) through the draft-level `rebase_proposal` tool.

FakeDroidRunner only; the SDK path is covered in test_sdk_runner.py. Nothing here calls Factory.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.agent.runner import ToolError
from app.db.models import AgentRunStep
from budget_helpers import APPROVER, DROID, addition_body, decide, draft, transfer_body
from evals.scenarios import RunCtx, score_stale
from test_agent import _toolbox

ANALYST = {"X-Actor-Id": "fin-ana", "X-Actor-Role": "finance_analyst"}
AFTER_A = {"research": "85000.00", "product": "50000.00", "engineering": "65000.00"}


def run(client, params, headers=ANALYST):
    return client.post("/api/agent/runs", json={"task_type": "propose_allocation", "params": params},
                       headers=headers)


def allocations(client) -> dict[str, str]:
    return {a["team"]: a["amount"] for a in client.get("/api/budget").json()["allocations"]}


def _stale_b(client) -> str:
    """Outcome A (transfer) and B (addition) both drafted on v1; A is applied; approving B is refused."""
    a = draft(client, transfer_body()).json()
    b = draft(client, addition_body()).json()
    assert decide(client, a["id"]).status_code == 201
    r = decide(client, b["id"])
    assert r.status_code == 409 and r.json()["error"]["code"] == "stale_proposal"
    return b["id"]


def test_recovery_explains_changes_and_offers_rebased_pending_draft(seeded, client):
    b = _stale_b(client)
    r = run(client, {"stale_proposal_id": b})
    assert r.status_code == 201, r.text
    out = r.json()
    assert out["status"] == "succeeded" and out["applied_changes"] is False
    assert out["params"] == {"stale_proposal_id": b}
    assert [s["tool"] for s in out["steps"]] == ["list_budget_requests", "rebase_proposal"]

    # a NEW pending draft on the current version, same lines; the original stays stale and unapplied
    assert len(out["proposals"]) == 1
    new = client.get(f"/api/proposals/{out['proposals'][0]['id']}").json()
    assert new["status"] == "pending_review" and new["rebased_from_proposal_id"] == b
    assert new["base_version"] == 2 and new["action_type"] == "addition"
    assert new["requester"]["role"] == "droid_agent"
    assert new["before"]["allocations"] == AFTER_A
    assert new["after"] == {"total": "250000.00",
                            "allocations": {"research": "120000.00", "product": "50000.00",
                                            "engineering": "80000.00"}}
    assert new["rationale"].startswith("Rebased by Droid") and f"Original rationale ({b})" in new["rationale"]
    assert client.get(f"/api/proposals/{b}").json()["status"] == "stale"
    assert allocations(client) == AFTER_A  # nothing applied by the run

    # First-layer text names the financial result; implementation details remain available in findings.
    summary = out["summary"]
    assert "$50,000.00" in summary and "$250,000.00" in summary and "fresh finance review" in summary
    assert "nothing has been applied" in summary.lower()
    assistant_texts = [e["data"]["text"] for e in out["events"] if e["type"] == "assistant_text"]
    assert assistant_texts == [summary]
    for text in [summary] + assistant_texts:
        assert "prop_" not in text and "version" not in text and "pending_review" not in text
    ctx = next(f for f in out["output"]["findings"] if f["type"] == "stale_context")
    assert ctx["base_version"] == 1 and ctx["current_version"] == 2 and ctx["total_change"] == "0.00"
    assert len(ctx["decisions_since_base"]) == 1
    assert {change["team"]: (change["at_base"], change["now"]) for change in ctx["changes"]}["product"] == ("80000.00", "50000.00")
    score = score_stale({"stale_recovery": RunCtx(fixture="stale_recovery", runner="fake", ran=True, run=out,
                                                setup={"stale_proposal_id": b}, budget_before={"state_version": 2},
                                                proposals=[new])})
    assert next(check for check in score if check.name == "explains_version_and_review").passed
    drafted = next(e for e in out["events"] if e["type"] == "proposal_drafted")["data"]
    assert drafted["applied"] is False and drafted["rebased_from_proposal_id"] == b

    # finance reviews the rebased draft afresh; an approver can apply it
    ok = decide(client, new["id"])
    assert ok.status_code == 201, ok.text
    assert allocations(client) == {"research": "120000.00", "product": "50000.00", "engineering": "80000.00"}


def test_recovery_of_a_proposal_that_is_not_stale_drafts_nothing(seeded, client):
    p = draft(client, addition_body()).json()
    out = run(client, {"stale_proposal_id": p["id"]}).json()
    assert out["status"] == "succeeded" and out["proposals"] == []
    assert "No proposal drafted" in out["summary"] and "does not need refreshing" in out["summary"]
    assert "Nothing was changed" in out["summary"]
    assert p["id"] not in out["summary"] and "version" not in out["summary"] and "pending_review" not in out["summary"]
    w = next(w for w in out["output"]["warnings"] if w["code"] == "no_proposal_drafted")
    assert w["details"]["code"] == "proposal_not_stale"
    assert client.get(f"/api/proposals/{p['id']}").json()["status"] == "pending_review"
    assert allocations(client) == {"research": "60000.00", "product": "80000.00", "engineering": "60000.00"}


def test_recovery_when_intent_no_longer_fits_explains_and_creates_nothing(seeded, client):
    a = draft(client, transfer_body()).json()  # takes 30k from product
    drain = draft(client, transfer_body(lines=[{"from_team": "product", "to_team": "engineering",
                                                "amount": "60000.00"}])).json()
    assert decide(client, drain["id"]).status_code == 201  # product 80k -> 20k
    assert decide(client, a["id"]).json()["error"]["code"] == "stale_proposal"
    before = client.get("/api/proposals").json()
    out = run(client, {"stale_proposal_id": a["id"]}).json()
    assert out["status"] == "succeeded" and out["proposals"] == []
    assert "no longer fit" in out["summary"] and "finance review" in out["summary"]
    assert "negative_allocation_result" not in out["summary"] and "prop_" not in out["summary"]
    ctx = next(f for f in out["output"]["findings"] if f["type"] == "stale_context")
    assert {change["team"]: (change["at_base"], change["now"]) for change in ctx["changes"]}["product"] == ("80000.00", "20000.00")
    warning = next(w for w in out["output"]["warnings"] if w["code"] == "no_proposal_drafted")
    assert "negative_allocation_result" in warning["message"]
    assert len(client.get("/api/proposals").json()) == len(before)
    assert client.get(f"/api/proposals/{a['id']}").json()["status"] == "stale"


def test_recovery_params_are_validated(seeded, client):
    r = run(client, {"stale_proposal_id": "prop_missing"})
    assert r.status_code == 422
    assert r.json()["error"]["details"]["reasons"][0]["code"] == "unknown_proposal"
    p = draft(client, addition_body()).json()
    r = run(client, {"stale_proposal_id": p["id"], "mode": "transfer"})
    assert r.status_code == 422
    assert r.json()["error"]["details"]["reasons"][0]["code"] == "conflicting_params"


def test_rebase_tool_counts_against_the_draft_budget_and_records_a_step(seeded, client):
    b = _stale_b(client)
    tb = _toolbox(seeded, rebase_target=b)
    tb._writes["draft_proposal"] = 3
    with pytest.raises(ToolError) as exc:
        tb.rebase_proposal(b)
    assert exc.value.code == "write_budget_exhausted"
    tb._writes["draft_proposal"] = 0
    res = tb.rebase_proposal(b, rationale="budget moved")
    assert res["proposal"]["status"] == "pending_review" and tb.proposal_ids == [res["proposal"]["id"]]
    assert res["stale_context"]["original"]["id"] == b
    assert client.get(f"/api/proposals/{b}").json()["status"] == "stale"
    s = seeded.state.session_factory()
    try:
        steps = s.scalars(select(AgentRunStep).where(AgentRunStep.run_id == "run_t")).all()
        assert [st.tool for st in steps] == ["rebase_proposal"] and "not applied" in steps[0].result_summary
    finally:
        s.close()
    # a refusal still carries what changed
    tb2 = _toolbox(seeded, run_id="run_t2", rebase_target=res["proposal"]["id"])
    with pytest.raises(ToolError) as exc:
        tb2.rebase_proposal(res["proposal"]["id"])
    assert exc.value.code == "proposal_not_stale"
    assert exc.value.details["stale_context"]["is_outdated"] is False


def test_droid_still_cannot_decide_the_rebased_draft(seeded, client):
    b = _stale_b(client)
    out = run(client, {"stale_proposal_id": b}).json()
    pid = out["proposals"][0]["id"]
    r = decide(client, pid, headers=DROID)
    assert r.status_code == 403 and r.json()["error"]["code"] == "role_forbidden"
    assert allocations(client) == AFTER_A
    # the run's initiator is in the lineage, so they cannot approve it either (if they were an approver)
    r = decide(client, pid, headers={"X-Actor-Id": "fin-ana", "X-Actor-Role": "finance_approver"})
    assert r.status_code == 403
    assert decide(client, pid, headers=APPROVER).status_code == 201


def test_rebase_is_limited_to_the_proposal_the_run_was_asked_to_recover(seeded, client):
    """An outdated pending proposal by finance must not be flipped to `stale` by a Droid run that was
    not asked to recover it (rebasing marks the original stale and drops it from the review queue)."""
    a = draft(client, transfer_body()).json()
    mine = draft(client, addition_body(), headers=ANALYST).json()  # finance's own draft on v1
    assert decide(client, a["id"]).status_code == 201  # budget now v2; `mine` is outdated but pending
    for target in (None, a["id"]):
        tb = _toolbox(seeded, run_id=f"run_{target or 'none'}", rebase_target=target)
        with pytest.raises(ToolError) as exc:
            tb.rebase_proposal(mine["id"])
        assert exc.value.code == "rebase_not_permitted"
        assert tb.proposal_ids == []
    assert client.get(f"/api/proposals/{mine['id']}").json()["status"] == "pending_review"
    # the API wires the run's stale_proposal_id in as the only target; plain drafting runs get none
    from app.agent.fake_runner import FakeDroidRunner

    seen = {}

    class Spy(FakeDroidRunner):
        def run(self, task, tools):
            seen[task.type] = tools.rebase_target
            return super().run(task, tools)

    seeded.state.droid_runner = Spy()
    try:
        run(client, {"stale_proposal_id": mine["id"]})
        client.post("/api/agent/runs", json={"task_type": "answer_question", "instruction": "x"}, headers=ANALYST)
    finally:
        seeded.state.droid_runner = None
    assert seen == {"propose_allocation": mine["id"], "answer_question": None}


def test_stale_context_lists_only_decisions_of_the_proposals_period(seeded, client):
    from datetime import date

    from app.agent.toolbox import stale_context
    from app.db.models import Decision, PlanningPeriod, Proposal

    b = _stale_b(client)
    s = seeded.state.session_factory()
    try:
        now = seeded.state.clock.now()
        s.add(PlanningPeriod(id="2027-P1", label="next", starts_on=date(2027, 1, 1), ends_on=date(2027, 3, 31)))
        other = Proposal(period_id="2027-P1", unit="USD", action_type="transfer", base_version=1,
                         envelope_increase="0.00", lines=[], before={}, after={}, rationale="r", status="applied",
                         created_by_actor="fin-x", created_by_role="finance_analyst", origin="finance_manual")
        s.add(other)
        s.flush()
        s.add(Decision(proposal_id=other.id, outcome="approved_applied", actor_id="fin-y",
                       actor_role="finance_approver", rationale="ok", idempotency_key="other-period",
                       request_fingerprint="f", from_version=1, to_version=2, before={}, after={}, decided_at=now))
        s.commit()
        ctx = stale_context(s, s.get(Proposal, b))

        assert other.id not in [m["proposal_id"] for m in ctx["decisions_since_base"]]
        assert len(ctx["decisions_since_base"]) == 1
    finally:
        s.close()
