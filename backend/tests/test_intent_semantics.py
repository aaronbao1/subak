"""Requested meaning survives parsing, clarification, revision, and deterministic execution."""

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.agent.fake_runner import _transfer_lines
from app.agent.runner import AgentRunOutput
from app.compat.intent import parse
from app.core.actors import Actor
from app.db.models import AgentRun
from app.schemas.agent import AgentRunCreate
from app.services.agent_runs import start_run

TEAMS = [("engineering", "Engineering"), ("product", "Product"), ("research", "Research")]
GAPS = {"research": Decimal("25000"), "engineering": Decimal("5000"), "product": Decimal("-30000")}
OPEN = [
    {"id": "prop_one", "base_version": 1, "mode": "addition", "amount": "50000.00", "prioritize": "research"},
    {"id": "prop_two", "base_version": 2, "mode": "transfer", "amount": "10000.00", "prioritize": "research", "source_team": "product"},
]
FINANCE = {"X-Actor-Id": "fin-ana", "X-Actor-Role": "finance_analyst"}


@pytest.mark.parametrize("text", [
    "Why did you add $50,000 to Research?",
    "Did you move $50 from Product to Research?",
    "Explain why you increased funding",
    "How much would adding $50 cost?",
    "Do not add funding",
    "Don't increase Research's budget",
    "Explain the context of this allocation",
    "Why did you revise the proposal context?",
    "What changed our spending outlook?",
    "What has changed in our forecast?",
    "What's new in our spending?",
    "Tell me what changed our spending outlook",
])
def test_explanations_and_negated_actions_do_not_draft_or_ask_for_funding(text):
    result = parse(text, teams=TEAMS, gaps=GAPS)
    assert result.run is not None and result.run["task_type"] == "answer_question"
    assert result.ask is None


@pytest.mark.parametrize("text", [
    "What changed in the documents?",
    "Read the documents and tell me what changed",
    "Interpret the company corpus",
])
def test_explicit_document_interpretation_remains_available(text):
    result = parse(text, teams=TEAMS, gaps=GAPS, conversation_context={"intent": "explain"})
    assert result.run["task_type"] == "interpret_corpus"


@pytest.mark.parametrize("separator", [";", ",", "."])
def test_negated_funding_does_not_cancel_an_explicit_redistribution(separator):
    result = parse(f"Do not add funding{separator} redistribute $50 from Product to Research", teams=TEAMS, gaps=GAPS)
    assert result.run["params"] == {"mode": "transfer", "amount": "50.00", "source_team": "product", "prioritize": "research"}


def test_pending_amount_keeps_the_requested_team():
    first = parse("Add funding for Research", teams=TEAMS, gaps=GAPS)
    assert first.run is None and first.conversation_context["pending_slot"] == "amount"
    second = parse("50k", teams=TEAMS, gaps=GAPS, conversation_context=first.conversation_context)
    assert second.run["params"] == {"mode": "addition", "amount": "50000.00", "prioritize": "research"}
    assert second.conversation_context.get("pending_slot") is None


def test_pending_new_allocation_does_not_revise_an_unrelated_open_proposal():
    first = parse("Add funding for Research", teams=TEAMS, gaps=GAPS, open_proposals=OPEN[:1])
    second = parse("50k", teams=TEAMS, gaps=GAPS, open_proposals=OPEN[:1],
                   conversation_context=first.conversation_context)
    assert second.revises is None
    assert second.run["params"]["amount"] == "50000.00"


def test_selected_proposal_is_revised_with_multiple_open():
    result = parse("Make it 40k instead", teams=TEAMS, gaps=GAPS, open_proposals=OPEN,
                   conversation_context={"intent": "allocation", "selected_proposal_id": "prop_one", "selected_proposal_version": 1})
    assert result.revises == "prop_one"
    assert result.run["params"] == {"mode": "addition", "amount": "40000.00", "prioritize": "research"}


@pytest.mark.parametrize("text", ["Make it 40k instead", "40k"])
def test_unambiguous_followup_revises_the_only_open_proposal(text):
    result = parse(text, teams=TEAMS, gaps=GAPS, open_proposals=OPEN[:1])
    assert result.revises == "prop_one"
    assert result.run["params"]["amount"] == "40000.00"


@pytest.mark.parametrize("text", ["Make it 40k instead", "40k"])
def test_followup_with_multiple_unselected_proposals_asks_which(text):
    result = parse(text, teams=TEAMS, gaps=GAPS, open_proposals=OPEN)
    assert result.run is None and "Which proposal" in result.ask


def test_revision_keeps_explicit_transfer_source():
    result = parse("Make it $50 instead", teams=TEAMS, gaps=GAPS, open_proposals=OPEN,
                   conversation_context={"intent": "allocation", "selected_proposal_id": "prop_two", "selected_proposal_version": 2})
    assert result.revises == "prop_two"
    assert result.run["params"] == {"mode": "transfer", "amount": "50.00", "source_team": "product", "prioritize": "research"}


def test_selected_version_mismatch_cannot_revise_another_snapshot():
    result = parse("Make it 40k instead", teams=TEAMS, gaps=GAPS, open_proposals=OPEN,
                   conversation_context={"intent": "allocation", "selected_proposal_id": "prop_one", "selected_proposal_version": 99})
    assert result.run is None and result.ask
    assert "version" in result.ask.lower()


def test_date_followup_retains_requested_date_without_drafting_allocation():
    result = parse("Move the start date to November 2", teams=TEAMS, gaps=GAPS, open_proposals=OPEN,
                   conversation_context={"intent": "allocation", "selected_proposal_id": "prop_two", "selected_proposal_version": 2})
    assert result.run is None and result.ask
    assert result.conversation_context["pending_slot"] == "effective_date"
    assert "november 2" in str(result.conversation_context).lower()


def test_bare_date_revision_does_not_lose_the_requested_date():
    result = parse("Make it November 2 instead", teams=TEAMS, gaps=GAPS, open_proposals=OPEN,
                   conversation_context={"intent": "allocation", "selected_proposal_id": "prop_one", "selected_proposal_version": 1})
    assert result.run is None and result.conversation_context["pending_slot"] == "effective_date"
    assert "November 2" in result.conversation_context["effective_date_text"]


@pytest.mark.parametrize("text", ["Move the project start to November 10", "Make it two weeks later"])
def test_scenario_date_followup_cannot_become_a_budget_transfer(text):
    result = parse(text, teams=TEAMS, gaps=GAPS,
                   conversation_context={"intent": "scenario", "pending_slot": "effective_date"})
    assert result.run is None and result.ask
    assert result.conversation_context["effective_date_text"] == text


def test_selected_draft_action_with_period_labels_is_not_a_date_edit():
    result = parse("Transfer $50 from Product to Research for 2026-10-19 through 2026-10-25", teams=TEAMS, gaps=GAPS,
                   open_proposals=OPEN, conversation_context={"intent": "allocation", "selected_proposal_id": "prop_two",
                                                            "selected_proposal_version": 2})
    assert result.ask is None and result.run["params"]["amount"] == "50.00"
    assert result.revises == "prop_two"


def test_explicit_allocation_action_leaves_explanation_mode():
    result = parse("Add $50 to Research", teams=TEAMS, gaps=GAPS, conversation_context={"intent": "explain"})
    assert result.run["params"]["amount"] == "50.00"
    assert result.conversation_context["intent"] == "allocation"


def test_explanation_selection_does_not_turn_new_action_into_revision():
    result = parse("Add $50 to Research", teams=TEAMS, gaps=GAPS, open_proposals=OPEN,
                   conversation_context={"intent": "explain", "selected_proposal_id": "prop_one", "selected_proposal_version": 1})
    assert result.run["params"]["amount"] == "50.00" and result.revises is None


def test_exact_source_cannot_be_replaced_by_another_team_with_more_headroom():
    alloc = {"product": Decimal("100"), "engineering": Decimal("100"), "research": Decimal("100")}
    projected = {"product": Decimal("110"), "engineering": Decimal("10"), "research": Decimal("150")}
    moves, _ = _transfer_lines("research", alloc, {}, projected, Decimal("50"), source_team="product")
    assert moves == []


def test_explicit_transfer_moves_only_between_the_requested_pair():
    alloc = {"product": Decimal("100"), "engineering": Decimal("100"), "research": Decimal("100")}
    projected = {"product": Decimal("20"), "engineering": Decimal("180"), "research": Decimal("120")}
    moves, _ = _transfer_lines("research", alloc, {}, projected, Decimal("50"), source_team="product")
    assert moves == [("product", "research", Decimal("50"))]


def test_transfer_source_survives_public_run_validation(seeded):
    with TestClient(seeded) as client:
        result = client.post("/api/agent/runs", headers=FINANCE, json={"task_type": "propose_allocation", "params": {
            "mode": "transfer", "source_team": "product", "prioritize": "research", "amount": "50.00"}})
        assert result.status_code == 201, result.text
        run = result.json()
        assert run["params"]["source_team"] == "product"
        proposal = client.get(f"/api/proposals/{run['proposals'][0]['id']}").json()
        assert [(line["from_team"], line["to_team"], line["amount"]) for line in proposal["lines"]] == [("product", "research", "50.00")]


def test_created_callback_can_persist_receipt_before_execution(seeded):
    seen = []

    class Runner:
        kind = "fake"

        def run(self, task, tools):
            assert len(seen) == 1
            return AgentRunOutput(summary="Read-only check")

    def created(run_id):
        with seeded.state.session_factory() as session:
            assert session.get(AgentRun, run_id).status == "running"
        seen.append(run_id)

    seeded.state.droid_runner = Runner()
    run_id, finished = start_run(seeded.state, AgentRunCreate(task_type="answer_question"),
                                 actor=Actor("fin-ana", "finance_analyst"), on_created=created)
    assert finished and seen == [run_id]


def test_in_transaction_callback_can_abort_duplicate_run_creation(seeded):
    seen = []

    def claim(session, run_id):
        assert session.get(AgentRun, run_id).status == "running"
        with seeded.state.session_factory() as observer:
            assert observer.get(AgentRun, run_id) is None
        seen.append(run_id)
        raise ValueError("Another run already owns this message receipt")

    with pytest.raises(ValueError, match="already owns"):
        start_run(seeded.state, AgentRunCreate(task_type="answer_question"), actor=Actor("fin-ana", "finance_analyst"),
                  on_created_in_session=claim)
    assert len(seen) == 1
    with seeded.state.session_factory() as session:
        assert session.get(AgentRun, seen[0]) is None


def test_explicit_transfer_does_not_require_recipient_projected_overrun():
    # The coherent engine-backed preview has all teams under their quarter allocations.
    alloc = {"product": Decimal("80000"), "research": Decimal("60040")}
    projected = {"product": Decimal("754.93"), "research": Decimal("295.94")}
    recorded = {"product": Decimal("180.50"), "research": Decimal("147.40")}
    moves, _ = _transfer_lines("research", alloc, recorded, projected, Decimal("50"), source_team="product")
    assert moves == [("product", "research", Decimal("50"))]


def test_explicit_transfer_still_respects_donor_projection_and_recorded_spend():
    alloc = {"product": Decimal("100"), "research": Decimal("100")}
    projected = {"product": Decimal("60"), "research": Decimal("20")}
    moves, _ = _transfer_lines("research", alloc, {"product": Decimal("75")}, projected,
                               Decimal("50"), source_team="product")
    assert moves == [("product", "research", Decimal("25"))]


def test_automatic_redistribution_still_requires_projected_recipient_need():
    alloc = {"product": Decimal("100"), "research": Decimal("100")}
    projected = {"product": Decimal("20"), "research": Decimal("20")}
    moves, _ = _transfer_lines("research", alloc, {}, projected, Decimal("50"))
    assert moves == []


@pytest.mark.parametrize("text,mode", [
    ("Move $50 from Product to Research without adding funding", "transfer"),
    ("Add $50 for Research", "addition"),
])
def test_explicit_new_action_drops_closed_previous_selection(text, mode):
    result = parse(text, teams=TEAMS, gaps=GAPS, open_proposals=OPEN,
                   conversation_context={"intent": "allocation", "selected_proposal_id": "prop_closed",
                                         "selected_proposal_version": 1,
                                         "draft": {"mode": "addition", "amount": "40.00", "prioritize": "research"}})
    assert result.ask is None and result.run["params"]["mode"] == mode
    assert result.run["params"]["amount"] == "50.00" and result.revises is None
    assert "selected_proposal_id" not in result.conversation_context


@pytest.mark.parametrize("text", ["Make it 40k instead", "40k", "Revise this proposal: add $40 for Research"])
def test_closed_selection_is_still_rejected_for_revision_followups(text):
    result = parse(text, teams=TEAMS, gaps=GAPS, open_proposals=OPEN,
                   conversation_context={"intent": "allocation", "selected_proposal_id": "prop_closed",
                                         "selected_proposal_version": 1})
    assert result.run is None and "not open for revision" in result.ask
