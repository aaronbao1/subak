"""Full-team targets draft native proposals; only an independent native decision applies them."""

from __future__ import annotations

import pytest

from app.db.models import Team
from budget_helpers import APPROVER, APPROVER_2, INITIAL, allocations, decide, reasons, seed_budget

TARGET = {"research": "85000.00", "product": "50000.00", "engineering": "65000.00"}


def allocation_body(**changes):
    return {
        "base_version": 1,
        "period_start": "2026-10-01",
        "period_end_exclusive": "2027-01-01",
        "unit": "USD",
        "allocations": TARGET,
        "rationale": "Reallocate deferred launch funding to evaluation and infrastructure.",
        **changes,
    }


def submit(client, body=None, *, key="allocation-draft-1", headers=APPROVER):
    return client.post(
        "/api/allocation-drafts", json=allocation_body() if body is None else body,
        headers={**headers, **({"Idempotency-Key": key} if key is not None else {})},
    )


def test_full_target_creates_native_transfer_then_independent_receipt_applies_once(app, client):
    seed_budget(app)
    response = submit(client)
    assert response.status_code == 201, response.text
    proposal = response.json()
    assert proposal["action_type"] == "transfer"
    assert proposal["origin"] == "finance_manual"
    assert proposal["requester"] == {"id": "fin-alice", "role": "finance_approver"}
    assert proposal["status"] == "pending_review"
    assert proposal["before"]["total"] == proposal["after"]["total"] == "200000.00"
    assert proposal["after"]["allocations"] == TARGET
    assert proposal["lines"] == [
        {"from_team": "product", "to_team": "engineering", "amount": "5000.00"},
        {"from_team": "product", "to_team": "research", "amount": "25000.00"},
    ]
    assert allocations(client) == INITIAL
    blocked = decide(client, proposal["id"], headers=APPROVER)
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "self_approval_forbidden"
    decision = decide(client, proposal["id"], headers=APPROVER_2, key="review-target")
    assert decision.status_code == 201, decision.text
    assert decision.json()["outcome"] == "approved_applied"
    assert decision.json()["after"] == {"total": "200000.00", "allocations": TARGET}
    assert allocations(client) == TARGET
    assert client.get("/api/budget").json()["state_version"] == 2
    replay = decide(client, proposal["id"], headers=APPROVER_2, key="review-target")
    assert replay.status_code == 200
    assert replay.json()["id"] == decision.json()["id"]
    assert client.get("/api/budget").json()["state_version"] == 2


def test_full_target_increase_is_native_addition(app, client):
    seed_budget(app)
    target = {"research": "95000.00", "product": "80000.00", "engineering": "75000.00"}
    response = submit(client, allocation_body(allocations=target))
    assert response.status_code == 201, response.text
    proposal = response.json()
    assert proposal["action_type"] == "addition"
    assert proposal["envelope_increase"] == "50000.00"
    assert proposal["after"] == {"total": "250000.00", "allocations": target}
    receipt = decide(client, proposal["id"], headers=APPROVER_2)
    assert receipt.status_code == 201, receipt.text
    assert allocations(client) == target
    assert client.get("/api/budget").json()["envelope_total"] == "250000.00"


@pytest.mark.parametrize(("changes", "reason"), [
    ({"allocations": {"research": "85000.00", "product": "50000.00"}}, "allocation_team_mismatch"),
    ({"allocations": {**TARGET, "extra": "0.00"}}, "allocation_team_mismatch"),
    ({"allocations": {**TARGET, "research": "-1.00"}}, "negative_allocation"),
    ({"allocations": {**TARGET, "research": 85000.0}}, "float_not_allowed"),
    ({"allocations": {**TARGET, "research": 85000}}, "money_string_required"),
    ({"allocations": {**TARGET, "research": "85000.001"}}, "too_many_decimals"),
    ({"allocations": {**TARGET, "research": "NaN"}}, "invalid_amount"),
    ({"allocations": INITIAL}, "no_allocation_change"),
    ({"allocations": {**INITIAL, "research": "59999.99"}}, "envelope_decrease_unsupported"),
    ({"allocations": {**TARGET, "research": "90000.00"}}, "mixed_addition_and_transfer"),
    ({"period_start": "2026-10-02"}, "period_mismatch"),
    ({"period_end_exclusive": "2026-12-31"}, "period_mismatch"),
    ({"rationale": "  "}, "rationale_required"),
])
def test_invalid_targets_do_not_create_proposals_or_mutate_budget(app, client, changes, reason):
    seed_budget(app)
    response = submit(client, allocation_body(**changes))
    assert response.status_code == 422, response.text
    assert reason in reasons(response)
    assert allocations(client) == INITIAL
    assert client.get("/api/proposals").json() == []


def test_inactive_allocated_team_cannot_be_edited(app, client, session):
    seed_budget(app)
    session.get(Team, "product").active = False
    session.commit()
    response = submit(client)
    assert response.status_code == 422, response.text
    assert "inactive_team" in reasons(response)


def test_stale_target_requires_new_budget_version(app, client):
    seed_budget(app)
    first = submit(client).json()
    assert decide(client, first["id"], headers=APPROVER_2).status_code == 201
    stale = submit(client, allocation_body(allocations=INITIAL), key="stale-target")
    assert stale.status_code == 409, stale.text
    assert stale.json()["error"]["code"] == "stale_base_version"
    assert allocations(client) == TARGET


def test_submission_key_replays_same_native_proposal_even_after_apply(app, client):
    seed_budget(app)
    first = submit(client)
    assert first.status_code == 201, first.text
    retry = submit(client)
    assert retry.status_code == 200, retry.text
    assert retry.json()["id"] == first.json()["id"]
    assert len(client.get("/api/proposals").json()) == 1
    assert decide(client, first.json()["id"], headers=APPROVER_2).status_code == 201
    applied_retry = submit(client)
    assert applied_retry.status_code == 200, applied_retry.text
    assert applied_retry.json()["id"] == first.json()["id"]
    assert applied_retry.json()["status"] == "applied"
    assert client.get("/api/budget").json()["state_version"] == 2


def test_submission_key_cannot_be_reused_for_another_intent(app, client):
    seed_budget(app)
    assert submit(client).status_code == 201
    response = submit(client, allocation_body(rationale="Another allocation rationale"))
    assert response.status_code == 409, response.text
    assert response.json()["error"]["code"] == "idempotency_key_reused"
    assert len(client.get("/api/proposals").json()) == 1


def test_idempotency_key_is_required_and_finance_role_is_enforced(app, client):
    seed_budget(app)
    missing = submit(client, key=None)
    assert missing.status_code == 400, missing.text
    assert missing.json()["error"]["code"] == "idempotency_key_required"
    forbidden = submit(client, headers={"X-Actor-Id": "importer", "X-Actor-Role": "importer"})
    assert forbidden.status_code == 403, forbidden.text
    assert client.get("/api/proposals").json() == []


def test_reconciliation_is_scoped_to_actor_and_finds_saved_native_proposal(app, client):
    seed_budget(app)
    before = client.get("/api/allocation-drafts/allocation-draft-1", headers=APPROVER)
    assert before.status_code == 404
    created = submit(client)
    assert created.status_code == 201, created.text
    recovered = client.get("/api/allocation-drafts/allocation-draft-1", headers=APPROVER)
    assert recovered.status_code == 200, recovered.text
    assert recovered.json()["id"] == created.json()["id"]
    other_actor = client.get("/api/allocation-drafts/allocation-draft-1", headers=APPROVER_2)
    assert other_actor.status_code == 404
    independent = submit(client, headers=APPROVER_2)
    assert independent.status_code == 201, independent.text
    assert independent.json()["id"] != created.json()["id"]


def test_allocation_state_preserves_exact_money_period_identity_and_spend_coverage(app, client):
    seed_budget(app, with_spend=True, client=client)
    response = client.get("/api/allocation-state")
    assert response.status_code == 200, response.text
    state = response.json()
    assert state["period"] == {"id": "2026-P1", "start_date": "2026-10-01",
                               "end_date_exclusive": "2027-01-01", "label": "Northstar planning period"}
    assert state["unit"] == "USD"
    assert state["state_version"] == 1
    assert state["envelope_total"] == state["allocated_total"] == "200000.00"
    assert state["unallocated_amount"] == "0.00"
    research = next(row for row in state["allocations"] if row["team_id"] == "research")
    assert research["amount"] == "60000.00"
    assert research["recorded_spend"] == "45000.00"
    assert research["remaining"] == "15000.00"
    native = client.get("/api/budget").json()
    assert state["spend_coverage"] == native["spend_coverage"]
    assert state["last_decision_id"] is None
    assert "internal planning" in state["note"]


def test_many_donors_can_fund_zero_allocations_exactly_and_preserve_spend_warnings(app, client):
    seed_budget(app, with_spend=True, client=client)
    target = {"engineering": "0.00", "research": "0.00", "product": "200000.00"}
    response = submit(client, allocation_body(allocations=target))
    assert response.status_code == 201, response.text
    proposal = response.json()
    assert proposal["after"] == {"total": "200000.00", "allocations": target}
    warned_teams = {warning["team"] for warning in proposal["warnings"]
                    if warning["code"] == "allocation_below_recorded_spend"}
    assert warned_teams == {"research", "engineering"}
    assert allocations(client) == INITIAL


def test_concurrent_retries_save_only_one_proposal(app, client):
    from concurrent.futures import ThreadPoolExecutor

    seed_budget(app)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: submit(client), range(2)))
    assert sorted(result.status_code for result in results) == [200, 201], [result.text for result in results]
    assert results[0].json()["id"] == results[1].json()["id"]
    assert len(client.get("/api/proposals").json()) == 1


def save_request(session, *, request_id="request-research", team="research", period="2026-P1"):
    from app.db.models import BudgetRequest

    row = BudgetRequest(id=request_id, client_request_id=request_id, submitted_by="team-owner",
                        fingerprint="test-evidence", team_id=team, period_id=period, title="Expand evaluations",
                        request_kind="budget_request", narrative="A team submitted this request for finance review.",
                        requested_amount="25000.00", unit="USD", evidence_refs=[])
    session.add(row)
    session.commit()
    return row


def test_request_linked_manual_targets_cite_requests_without_claiming_forecast_assessment(app, client, session):
    from sqlalchemy import func, select
    from app.db.models import BudgetRequest, ForecastSnapshot

    seed_budget(app)
    save_request(session)
    response = submit(client, allocation_body(request_ids=["request-research", "request-research"]))
    assert response.status_code == 201, response.text
    proposal = response.json()
    assert proposal["evidence_refs"] == [{"kind": "budget_request", "id": "request-research",
                                           "version": None, "note": None}]
    assert "manual_allocation_targets" in {warning["code"] for warning in proposal["warnings"]}
    assert session.scalar(select(func.count()).select_from(ForecastSnapshot)) == 0
    assert session.scalar(select(func.count()).select_from(BudgetRequest)) == 1
    assert allocations(client) == INITIAL


def test_unknown_request_reference_is_rejected_without_drafting(app, client):
    seed_budget(app)
    response = submit(client, allocation_body(request_ids=["missing-request"]))
    assert response.status_code == 422, response.text
    assert "unknown_budget_request" in reasons(response)
    assert client.get("/api/proposals").json() == []


def test_multiple_requests_for_same_team_do_not_double_count_a_single_team_delta(app, client, session):
    seed_budget(app)
    save_request(session)
    save_request(session, request_id="request-research-2")
    response = submit(client, allocation_body(request_ids=["request-research", "request-research-2"]))
    assert response.status_code == 422, response.text
    assert "request_team_ambiguous" in reasons(response)
    assert client.get("/api/proposals").json() == []


def test_request_from_other_period_cannot_be_cited(app, client, session):
    from datetime import date
    from app.db.models import PlanningPeriod

    seed_budget(app)
    session.add(PlanningPeriod(id="2027-P1", label="Next period", starts_on=date(2027, 1, 1),
                               ends_on=date(2027, 3, 31)))
    session.commit()
    save_request(session, period="2027-P1")
    response = submit(client, allocation_body(request_ids=["request-research"]))
    assert response.status_code == 422, response.text
    assert "request_period_mismatch" in reasons(response)


def test_valid_individual_amounts_cannot_overflow_company_money_limit(app, client):
    seed_budget(app)
    response = submit(client, allocation_body(allocations={**INITIAL, "research": "999999999999999.99"}))
    assert response.status_code == 422, response.text
    assert "amount_too_large" in reasons(response)
    assert client.get("/api/proposals").json() == []


def test_compat_allocation_state_draft_and_recovery_use_dashboard_actor(app, client):
    seed_budget(app)
    state = client.get("/compat/api/allocation-state")
    assert state.status_code == 200, state.text
    assert state.json()["envelope_total"] == "200000.00"
    created = client.post("/compat/api/allocation-drafts", json=allocation_body(),
                          headers={"Idempotency-Key": "dashboard-plan"})
    assert created.status_code == 201, created.text
    assert created.json()["requester"] == {"id": "dashboard-analyst", "role": "finance_analyst"}
    recovered = client.get("/compat/api/allocation-drafts/dashboard-plan")
    assert recovered.status_code == 200, recovered.text
    assert recovered.json()["id"] == created.json()["id"]
    assert allocations(client) == INITIAL


@pytest.mark.parametrize("headers", [{"X-Actor-Id": "partial"},
                                    {"X-Actor-Id": "importer", "X-Actor-Role": "importer"}])
def test_compat_cannot_override_missing_or_forbidden_explicit_actor(app, client, headers):
    seed_budget(app)
    response = client.post("/compat/api/allocation-drafts", json=allocation_body(),
                           headers={**headers, "Idempotency-Key": "dashboard-plan"})
    assert response.status_code in (401, 403), response.text
    assert client.get("/api/proposals").json() == []


def test_native_draft_does_not_inherit_compat_default_actor(app, client):
    seed_budget(app)
    response = client.post("/api/allocation-drafts", json=allocation_body(),
                           headers={"Idempotency-Key": "native-plan"})
    assert response.status_code == 401, response.text


def test_unsized_context_update_cannot_be_linked_as_a_funding_request(app, client, session):
    seed_budget(app)
    request = save_request(session)
    request.request_kind = "project_update"
    request.requested_amount = None
    session.commit()
    response = submit(client, allocation_body(request_ids=[request.id]))
    assert response.status_code == 422, response.text
    assert "request_amount_required" in reasons(response)
    assert client.get("/api/proposals").json() == []


@pytest.mark.parametrize(("amount", "funding_text"), [("25000.00", "USD 25000.00"), (None, "no additional allocation amount")])
def test_submitted_request_citation_resolves_without_creating_corpus_or_forecast_rows(
    app, client, session, amount, funding_text,
):
    from sqlalchemy import func, select
    from app.db.models import CorpusDocument, ForecastSnapshot

    seed_budget(app)
    request = save_request(session)
    request.requested_amount = amount
    request.source_ref = "meeting-note-42"
    request.created_at = app.state.clock.now()
    session.commit()
    response = client.get(f"/compat/api/documents/{request.id}")
    assert response.status_code == 200, response.text
    document = response.json()
    assert document is not None
    assert document["id"] == request.id
    assert document["title"] == "Expand evaluations"
    assert document["date"] == "2026-10-24"
    assert document["teamIds"] == ["research"]
    assert document["kind"] == "correspondence"
    assert document["integration"] == "document"
    assert document["origin"] == "Submitted budget request"
    assert request.narrative in document["body"]
    assert funding_text in document["body"]
    assert "2026-10-01" in document["body"] and "2026-12-31" in document["body"]
    assert "meeting-note-42" in document["body"]
    assert "not included in the forecast" in document["body"]
    assert session.scalar(select(func.count()).select_from(CorpusDocument)) == 0
    assert session.scalar(select(func.count()).select_from(ForecastSnapshot)) == 0
    assert client.get("/compat/api/documents").json() == []
