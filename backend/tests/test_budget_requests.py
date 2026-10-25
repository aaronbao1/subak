"""Request intake is durable evidence; funding exists only in confirmed native decisions."""
from sqlalchemy import func, select

from app.db.models import BudgetRequest, CorpusDocument, ForecastSnapshot, Proposal
from budget_helpers import APPROVER, APPROVER_2, INITIAL, allocations, decide, seed_budget


def body(**changes):
    return {"client_request_id": "request-atlas", "team_id": "research", "title": "Atlas expansion",
            "request_kind": "project", "project_name": "Atlas", "narrative": "Add evaluation capacity.",
            "requested_amount": "50.00", "unit": "USD", "period_start": "2026-10-01",
            "period_end_exclusive": "2027-01-01", "source_ref": "team intake", **changes}


def submit(client, **changes):
    return client.post("/api/budget-requests", json=body(**changes), headers=APPROVER)


def draft(client, request_id, **changes):
    return client.post(f"/api/budget-requests/{request_id}/draft",
                       json={"base_version": 1, "action_type": "addition", **changes},
                       headers={**APPROVER, "Idempotency-Key": "request-draft"})


def test_explicit_request_persists_no_budget_forecast_or_corpus_mutation(app, client, session):
    seed_budget(app)
    before = {m: session.scalar(select(func.count()).select_from(m)) for m in (ForecastSnapshot, CorpusDocument, Proposal)}
    response = submit(client)
    assert response.status_code == 201, response.text
    row = response.json()
    assert row["requested_amount"] == "50.00"
    assert row["status"] == "submitted"
    assert row["source"]["submitted_by"] == "fin-alice"
    assert row["period"]["end_date_exclusive"] == "2027-01-01"
    assert row["assessment"]["team_allocation"] == "60000.00"
    assert row["assessment"]["requested_allocation"] == "60050.00"
    assert row["assessment"]["amount_included_in_forecast"] is False
    assert allocations(client) == INITIAL
    assert {m: session.scalar(select(func.count()).select_from(m)) for m in before} == before
    assert client.get("/api/budget-requests").json()["items"][0] == row


def test_request_retries_are_durable_conflicting_intent_rejected(app, client):
    seed_budget(app)
    first = submit(client)
    again = submit(client)
    assert first.status_code == 201 and again.status_code == 200
    assert first.json()["id"] == again.json()["id"]
    changed = submit(client, requested_amount="40.00")
    assert changed.status_code == 409


def test_context_update_without_amount_never_infers_a_request(app, client):
    seed_budget(app)
    result = submit(client, requested_amount=None).json()
    assert result["status"] == "submitted"
    assert result["requested_amount"] is None
    assert result["remaining_requested_amount"] is None
    assert result["assessment"]["requested_allocation"] is None
    assert draft(client, result["id"]).status_code == 422


def test_draft_and_independent_decision_are_separate_and_recoverable(app, client):
    seed_budget(app)
    request = submit(client).json()
    response = draft(client, request["id"])
    assert response.status_code == 201, response.text
    result = response.json()
    proposal = result["proposal"]
    assert result["request"]["status"] == "pending_review"
    assert result["request"]["approved_amount"] == "0.00"
    assert proposal["after"]["allocations"]["research"] == "60050.00"
    assert {ref["kind"] for ref in proposal["evidence_refs"]} >= {"budget_request", "forecast_snapshot"}
    assert allocations(client) == INITIAL
    replay = draft(client, request["id"])
    assert replay.status_code == 200 and replay.json()["proposal"]["id"] == proposal["id"]
    recovery = client.get("/api/allocation-drafts/request-draft", headers=APPROVER)
    assert recovery.json()["id"] == proposal["id"]
    decision = decide(client, proposal["id"], headers=APPROVER_2)
    assert decision.status_code == 201, decision.text
    updated = client.get(f"/api/budget-requests/{request['id']}").json()
    assert updated["status"] == "approved_applied"
    assert updated["approved_amount"] == "50.00"
    assert updated["remaining_requested_amount"] == "0.00"
    assert updated["decision_ids"] == [decision.json()["id"]]
    assert draft(client, request["id"]).json()["proposal"]["id"] == proposal["id"]


def test_revised_partial_decision_follows_lineage_without_claiming_fulfillment(app, client):
    seed_budget(app)
    request = submit(client).json()
    original = draft(client, request["id"]).json()["proposal"]
    revised = client.post(f"/api/proposals/{original['id']}/revise", headers=APPROVER,
                         json={"base_version": 1, "action_type": "addition", "envelope_increase": "20.00",
                               "lines": [{"to_team": "research", "amount": "20.00"}],
                               "rationale": "Approve a smaller first phase."})
    assert revised.status_code == 201, revised.text
    pid = revised.json()["id"]
    assert decide(client, pid, headers=APPROVER_2).status_code == 201
    row = client.get(f"/api/budget-requests/{request['id']}").json()
    assert row["status"] == "partially_funded"
    assert row["approved_amount"] == "20.00" and row["remaining_requested_amount"] == "30.00"
    assert set(row["linked_proposal_ids"]) == {original["id"], pid}


def test_transfer_requires_explicit_supported_source_without_silent_cap(app, client):
    seed_budget(app)
    request = submit(client).json()
    missing = draft(client, request["id"], action_type="transfer")
    assert missing.status_code == 422
    response = draft(client, request["id"], action_type="transfer", source_team_id="product")
    assert response.status_code == 201, response.text
    assert response.json()["proposal"]["lines"] == [{"from_team": "product", "to_team": "research", "amount": "50.00"}]


def test_bad_input_and_unknown_scope_fail_without_records(app, client, session):
    seed_budget(app)
    for changes in ({"requested_amount": "-1"}, {"requested_amount": 50.0}, {"requested_amount": "0"},
                    {"team_id": "not-a-team"}, {"period_end_exclusive": "2026-12-31"}, {"narrative": "  "}):
        response = submit(client, **changes)
        assert response.status_code == 422, response.text
    assert session.scalar(select(func.count()).select_from(BudgetRequest)) == 0


def test_compat_intake_has_explicit_default_dashboard_identity(app, client):
    seed_budget(app)
    response = client.post("/compat/api/budget-requests", json=body())
    assert response.status_code == 201, response.text
    request = response.json()
    assert request["source"]["submitted_by"] == "dashboard-analyst"
    native = client.post("/api/budget-requests", json=body(client_request_id="native"))
    assert native.status_code == 401
    result = client.post(f"/compat/api/budget-requests/{request['id']}/draft",
                         json={"base_version": 1, "action_type": "addition"},
                         headers={"Idempotency-Key": "compat-request-draft"})
    assert result.status_code == 201, result.text
    assert result.json()["proposal"]["requester"]["id"] == "dashboard-analyst"
    assert client.get("/compat/api/budget-requests").json()["items"][0]["status"] == "pending_review"


def test_assessment_missing_forecast_is_unknown_and_never_adds_request_to_projection(app, client):
    from app.schemas.forecasts import ForecastResult
    seed_budget(app)
    class WrongPeriod:
        def get_forecast(self, period_id, team_ids):
            return ForecastResult(provider="test", availability="available", target_period="different",
                                  projections=[{"team": t, "amount": "0"} for t in team_ids], method_label="test")
    app.state.forecast_provider = WrongPeriod()
    request = submit(client).json()
    a = request["assessment"]
    assert a["forecast_status"] == "unavailable" and a["forecast_amount"] is None
    assert a["projected_headroom"] is None and a["available_donors"] == []
    response = draft(client, request["id"], action_type="transfer", source_team_id="product")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "request_source_headroom_insufficient"


def test_rejected_receipt_and_stale_draft_never_mark_approved(app, client):
    seed_budget(app)
    request = submit(client).json()
    proposal = draft(client, request["id"]).json()["proposal"]
    rejected = decide(client, proposal["id"], outcome="reject", headers=APPROVER_2)
    assert rejected.status_code == 201, rejected.text
    row = client.get(f"/api/budget-requests/{request['id']}").json()
    assert row["status"] == "rejected" and row["approved_amount"] == "0.00"
    assert row["remaining_requested_amount"] == "50.00"


def test_partial_full_team_decision_then_remaining_request_reaches_exact_total(app, client):
    seed_budget(app)
    request = submit(client, requested_amount="75.00").json()
    result = client.post("/api/allocation-drafts", headers={**APPROVER, "Idempotency-Key": "partial-full-plan"},
                         json={"base_version": 1, "period_start": "2026-10-01", "period_end_exclusive": "2027-01-01",
                               "unit": "USD", "allocations": {**INITIAL, "research": "60050.25"},
                               "rationale": "First phase of Atlas", "request_ids": [request["id"]]})
    assert result.status_code == 201, result.text
    assert decide(client, result.json()["id"], headers=APPROVER_2).status_code == 201
    partial = client.get(f"/api/budget-requests/{request['id']}").json()
    assert partial["status"] == "partially_funded" and partial["approved_amount"] == "50.25"
    assert partial["remaining_requested_amount"] == "24.75"
    assert partial["assessment"]["requested_allocation"] == "60075.00"
    remaining = draft(client, request["id"], base_version=2)
    assert remaining.status_code == 201, remaining.text
    assert remaining.json()["proposal"]["envelope_increase"] == "24.75"
    assert decide(client, remaining.json()["proposal"]["id"], headers=APPROVER_2).status_code == 201
    final = client.get(f"/api/budget-requests/{request['id']}").json()
    assert final["status"] == "approved_applied" and final["approved_amount"] == "75.00"
    assert final["remaining_requested_amount"] == "0.00"
    assert len(final["decision_ids"]) == 2
    assert final["assessment"]["requested_allocation"] == "60075.00"


def test_known_stale_issued_forecast_withholds_assessment_headroom(app, client):
    from app.schemas.forecasts import ForecastResult
    seed_budget(app)
    class StaleIssued:
        def get_forecast(self, period_id, team_ids):
            return ForecastResult(provider="engine", availability="available", target_period=period_id,
                                  projections=[{"team": t, "amount": "1.00"} for t in team_ids],
                                  method_label="issued", forecast_run_id="stale-run", input_revision="old-input-revision")
    app.state.forecast_provider = StaleIssued()
    assessment = submit(client).json()["assessment"]
    assert assessment["forecast_status"] == "unavailable"
    assert assessment["forecast_amount"] is None and assessment["projected_headroom"] is None
    assert assessment["available_donors"] == []
    assert "stale" in assessment["qualification"].lower()


def test_revision_cannot_silently_drop_request_forecast_dependency(app, client):
    seed_budget(app)
    request = submit(client).json()
    original = draft(client, request["id"]).json()["proposal"]
    revised = client.post(f"/api/proposals/{original['id']}/revise", headers=APPROVER,
                         json={"base_version": 1, "action_type": "addition", "envelope_increase": "20.00",
                               "lines": [{"to_team": "research", "amount": "20.00"}],
                               "rationale": "Review smaller amount, retain evidence basis."})
    assert revised.status_code == 201, revised.text
    required = {(r["kind"], r["id"]) for r in original["evidence_refs"]
                if r["kind"] in {"budget_request", "forecast_snapshot"}}
    assert required <= {(r["kind"], r["id"]) for r in revised.json()["evidence_refs"]}


def test_request_amount_that_overflows_resulting_budget_cannot_poison_inbox(app, client, session):
    seed_budget(app)
    response = submit(client, requested_amount="999999999999999.99")
    assert response.status_code == 422, response.text
    assert session.scalar(select(func.count()).select_from(BudgetRequest)) == 0
    assert client.get("/api/budget-requests").json() == {"items": []}


def test_ambiguous_native_funding_withholds_remaining_and_blocks_double_draft(app, client):
    seed_budget(app)
    first = submit(client).json()
    second = submit(client, client_request_id="second-request").json()
    proposal = client.post("/api/proposals", headers=APPROVER,
                          json={"base_version": 1, "action_type": "addition", "envelope_increase": "100.00",
                                "lines": [{"to_team": "research", "amount": "100.00"}], "rationale": "Fund both projects",
                                "evidence_refs": [{"kind": "budget_request", "id": r["id"]} for r in (first, second)]})
    assert proposal.status_code == 201, proposal.text
    assert decide(client, proposal.json()["id"], headers=APPROVER_2).status_code == 201
    for request in (first, second):
        row = client.get(f"/api/budget-requests/{request['id']}").json()
        assert row["status"] == "needs_revision"
        assert row["remaining_requested_amount"] is None
        assert row["assessment"]["requested_allocation"] is None
        assert "attribution is unresolved" in row["assessment"]["qualification"]
        attempted = draft(client, request["id"], base_version=2)
        assert attempted.status_code == 409
        assert attempted.json()["error"]["code"] == "request_funding_attribution_unclear"


def test_chat_revision_inherits_request_dependency_and_retires_stale_child(app, client, session):
    from app.core.actors import Actor
    from app.services import proposals as proposal_svc
    seed_budget(app)
    request = submit(client).json()
    original = draft(client, request["id"]).json()["proposal"]
    child = client.post("/api/proposals", headers=APPROVER,
                        json={"base_version": 1, "action_type": "addition", "envelope_increase": "20.00",
                              "lines": [{"to_team": "research", "amount": "20.00"}], "rationale": "Revise to first phase"}).json()
    snapshot_id = next(r["id"] for r in original["evidence_refs"] if r["kind"] == "forecast_snapshot")
    snapshot = session.get(ForecastSnapshot, snapshot_id)
    snapshot.payload = {**snapshot.payload, "input_revision": "now-stale"}
    session.commit()
    assert proposal_svc.link_revision(session, original["id"], child["id"],
                                     actor=Actor("fin-alice", "finance_approver"), clock=app.state.clock)
    session.commit()
    updated = client.get(f"/api/proposals/{child['id']}").json()
    assert updated["status"] == "stale"
    assert {r["kind"] for r in updated["evidence_refs"]} >= {"budget_request", "forecast_snapshot"}
    assert decide(client, child["id"], headers=APPROVER_2).status_code == 409
    row = client.get(f"/api/budget-requests/{request['id']}").json()
    assert row["status"] == "needs_revision" and row["approved_amount"] == "0.00"


def test_amountless_source_clarified_to_explicit_request_receives_unambiguous_funding(app, client):
    seed_budget(app)
    update = submit(client, requested_amount=None).json()
    request = submit(client, client_request_id="clarified-funding", source_ref=f"budget-request:{update['id']}",
                     evidence_refs=[{"kind": "budget_request", "id": update["id"]}]).json()
    proposal = draft(client, request["id"]).json()["proposal"]
    assert decide(client, proposal["id"], headers=APPROVER_2).status_code == 201
    funded = client.get(f"/api/budget-requests/{request['id']}").json()
    assert funded["status"] == "approved_applied" and funded["approved_amount"] == "50.00"
    assert funded["remaining_requested_amount"] == "0.00"
    source = client.get(f"/api/budget-requests/{update['id']}").json()
    assert source["status"] == "submitted" and source["approved_amount"] == "0.00"
    assert source["remaining_requested_amount"] is None
    assert source["decision_ids"] == []
    assert funded["evidence_refs"][0]["id"] == update["id"]
    assert [r["id"] for r in proposal["evidence_refs"] if r["kind"] == "budget_request"] == [request["id"]]
