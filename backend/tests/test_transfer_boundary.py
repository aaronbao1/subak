"""Persisted transfer intent constrains every runner before any draft is saved."""

from copy import deepcopy

import pytest
from sqlalchemy import select

from app.agent.runner import AgentRunOutput, AgentTask, ToolError
from app.agent.toolbox import BackendToolbox
from app.db.models import AgentRun, Proposal
from app.db.session import transaction
from app.services.agent_runs import execute


PARAMS = {"mode": "transfer", "source_team": "product", "prioritize": "research", "amount": "50.00"}


def _proposal(*, source="product", destination="research", amount="50.00", addition=False):
    line = {"to_team": destination, "amount": amount}
    if not addition:
        line["from_team"] = source
    body = {"action_type": "addition" if addition else "transfer", "base_version": 1,
            "lines": [line], "rationale": "Transfer requested funds for finance review."}
    if addition:
        body["envelope_increase"] = amount
    return body


class _DraftingRunner:
    kind = "fake"

    def __init__(self, proposal):
        self.proposal = proposal
        self.refusal = None

    def run(self, task, tools):
        # A runner may mutate its own task object; authorization comes from the stored request.
        task.params["source_team"] = "engineering"
        try:
            tools.draft_proposal(self.proposal)
        except ToolError as exc:
            self.refusal = exc
        return AgentRunOutput(summary="Attempted the allocation draft.")


def _run(seeded, proposal, params=None):
    task = AgentTask(type="propose_allocation", params=deepcopy(params if params is not None else PARAMS))
    run_id = seeded.state.id_factory.new_id("run_")
    with transaction(seeded.state.session_factory) as session:
        session.add(AgentRun(id=run_id, task_type=task.type,
                             input={"task": task.model_dump(mode="json")}, runner_kind="fake",
                             status="running", started_at=seeded.state.clock.now()))
    toolbox = BackendToolbox(session_factory=seeded.state.session_factory, run_id=run_id,
                             source="fake_runner", runner_kind="fake", clock=seeded.state.clock,
                             ids=seeded.state.id_factory, forecast_provider=seeded.state.forecast_provider)
    runner = _DraftingRunner(proposal)
    execute(seeded.state, run_id, runner, task, toolbox)
    with seeded.state.session_factory() as session:
        proposals = session.scalars(select(Proposal).where(Proposal.agent_run_id == run_id)).all()
        result = [(item.action_type, item.lines, item.status) for item in proposals]
    return runner, toolbox, result


@pytest.mark.parametrize("proposal", [
    pytest.param(_proposal(source="engineering"), id="different-source"),
    pytest.param(_proposal(destination="engineering"), id="different-destination"),
    pytest.param(_proposal(source="research", destination="product"), id="reversed-direction"),
    pytest.param(_proposal(addition=True), id="addition-instead-of-transfer"),
    pytest.param(_proposal(amount="50.01"), id="above-requested-cap"),
    pytest.param({**_proposal(), "lines": [
        {"from_team": "product", "to_team": "research", "amount": "25.00"},
        {"from_team": "engineering", "to_team": "research", "amount": "25.00"},
    ]}, id="additional-donor"),
])
def test_explicit_transfer_refuses_runner_substitution_before_persistence(seeded, proposal):
    runner, toolbox, proposals = _run(seeded, proposal)
    assert runner.refusal is not None
    assert runner.refusal.code == "allocation_context_mismatch"
    assert proposals == []
    assert toolbox.proposal_ids == []


@pytest.mark.parametrize("amount", ["50.00", "25.00"])
def test_explicit_transfer_saves_requested_teams_at_or_below_cap(seeded, amount):
    runner, toolbox, proposals = _run(seeded, _proposal(amount=amount))
    assert runner.refusal is None
    assert proposals == [("transfer", [
        {"from_team": "product", "to_team": "research", "amount": amount},
    ], "pending_review")]
    assert len(toolbox.proposal_ids) == 1


def test_transfer_without_explicit_source_preserves_generic_donor_selection(seeded):
    runner, _, proposals = _run(seeded, _proposal(source="engineering"),
                                {"mode": "transfer", "prioritize": "research", "amount": "50.00"})
    assert runner.refusal is None
    assert proposals[0][1] == [{"from_team": "engineering", "to_team": "research", "amount": "50.00"}]


@pytest.mark.parametrize("proposal", [_proposal(addition=True, amount="500.00"), _proposal(amount="50.00")])
def test_explicit_addition_cannot_be_changed_by_request_or_source_text(seeded, proposal):
    runner, toolbox, proposals = _run(seeded, proposal,
                                    {"mode": "addition", "prioritize": "research", "amount": "50.00"})
    assert runner.refusal is not None and runner.refusal.code == "allocation_context_mismatch"
    assert proposals == [] and toolbox.proposal_ids == []


def test_explicit_source_with_insufficient_budget_does_not_save_a_draft(seeded):
    runner, toolbox, proposals = _run(seeded, _proposal(amount="80000.01"),
                                    {**PARAMS, "amount": "80000.01"})
    assert runner.refusal is not None
    assert runner.refusal.code == "validation_failed"
    assert "negative_allocation_result" in {reason["code"] for reason in runner.refusal.details["reasons"]}
    assert proposals == []
    assert toolbox.proposal_ids == []


@pytest.mark.parametrize("runner_kind", ["fake", "sdk"])
@pytest.mark.parametrize("proposal,refused", [
    pytest.param(_proposal(source="engineering"), True, id="different-source"),
    pytest.param(_proposal(destination="engineering"), True, id="different-destination"),
    pytest.param(_proposal(addition=True), True, id="wrong-action"),
    pytest.param(_proposal(amount="50.01"), True, id="above-cap"),
    pytest.param(_proposal(), False, id="requested-transfer"),
])
def test_api_preserves_explicit_transfer_for_injected_runners(seeded, client, runner_kind, proposal, refused):
    runner = _DraftingRunner(proposal)
    runner.kind = runner_kind
    seeded.state.droid_runner = runner
    before = client.get("/api/budget").json()
    response = client.post("/api/agent/runs", json={"task_type": "propose_allocation", "params": PARAMS},
                           headers={"X-Actor-Id": "finance", "X-Actor-Role": "finance_analyst"})
    assert response.status_code == 201, response.text
    result = response.json()
    assert result["params"] == PARAMS
    assert result["runner_kind"] == runner_kind
    assert client.get("/api/budget").json() == before
    if refused:
        assert runner.refusal is not None
        assert runner.refusal.code == "allocation_context_mismatch"
        assert result["proposals"] == []
        assert result["output"]["proposal_ids"] == []
        failure = next(event for event in result["events"] if event["type"] == "tool_result")
        assert failure["data"]["code"] == "allocation_context_mismatch"
        assert failure["data"]["is_error"] is True
        with seeded.state.session_factory() as session:
            assert session.scalar(select(Proposal.id)) is None
    else:
        assert runner.refusal is None
        assert len(result["proposals"]) == 1
        draft = client.get(f"/api/proposals/{result['proposals'][0]['id']}").json()
        assert draft["action_type"] == "transfer"
        assert draft["lines"] == [{"from_team": "product", "to_team": "research", "amount": "50.00"}]
        assert draft["status"] == "pending_review"
