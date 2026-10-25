"""Proposal drafting: addition vs transfer, Decimal validation, backend-computed before/after."""

from __future__ import annotations

from datetime import datetime, timezone

from app.db import models as m
from budget_helpers import (
    ANALYST,
    DROID,
    IMPORTER_H,
    INITIAL,
    addition_body,
    allocations,
    draft,
    reasons,
    seed_budget,
    transfer_body,
)


def test_transfer_outcome_a_draft_computes_before_after(app, client):
    seed_budget(app)
    r = draft(client, transfer_body())
    assert r.status_code == 201, r.text
    p = r.json()
    assert p["action_type"] == "transfer"
    assert p["status"] == "pending_review"
    assert p["base_version"] == 1 and p["is_stale"] is False
    assert p["envelope_increase"] == "0.00"
    assert p["before"] == {"total": "200000.00", "allocations": INITIAL}
    assert p["after"] == {"total": "200000.00", "allocations": {
        "engineering": "65000.00", "product": "50000.00", "research": "85000.00"}}
    assert p["deltas"] == {"engineering": "5000.00", "product": "-30000.00", "research": "25000.00"}
    assert p["requester"] == {"id": "droid", "role": "droid_agent"}
    assert p["origin"] == "droid_run"
    assert [ln["from_team"] for ln in p["lines"]] == ["product", "product"]


def test_addition_outcome_b_draft_increases_envelope_exactly(app, client):
    seed_budget(app)
    p = draft(client, addition_body(), headers=ANALYST).json()
    assert p["action_type"] == "addition"
    assert p["envelope_increase"] == "50000.00"
    assert p["after"]["total"] == "250000.00"
    assert p["after"]["allocations"] == {"engineering": "75000.00", "product": "80000.00", "research": "95000.00"}
    assert p["deltas"] == {"engineering": "15000.00", "product": "0.00", "research": "35000.00"}
    assert all(ln["from_team"] is None for ln in p["lines"])
    assert p["origin"] == "finance_manual"


def test_action_type_persisted_and_transfer_has_zero_envelope_increase(app, client, session):
    seed_budget(app)
    t = draft(client, transfer_body()).json()
    a = draft(client, addition_body()).json()
    rows = {p.id: p for p in session.query(m.Proposal).all()}
    assert rows[t["id"]].action_type == "transfer"
    assert str(rows[t["id"]].envelope_increase) == "0.00"
    assert rows[a["id"]].action_type == "addition"
    assert str(rows[a["id"]].envelope_increase) == "50000.00"


def test_drafting_never_changes_the_budget(app, client):
    seed_budget(app)
    draft(client, transfer_body())
    draft(client, addition_body())
    assert allocations(client) == INITIAL
    assert client.get("/api/budget").json()["state_version"] == 1


def test_transfer_with_envelope_change_rejected(app, client):
    seed_budget(app)
    r = draft(client, transfer_body(envelope_increase="50000.00"))
    assert r.status_code == 422
    assert "transfer_with_envelope_change" in reasons(r)
    # An explicit zero is allowed: it states that the envelope does not change.
    assert draft(client, transfer_body(envelope_increase="0.00")).status_code == 201


def test_transfer_exceeding_source_allocation_rejected(app, client):
    seed_budget(app)
    r = draft(client, transfer_body([{"from_team": "product", "to_team": "research", "amount": "80000.01"}]))
    assert r.status_code == 422
    assert reasons(r) == {"negative_allocation_result"}
    # Taking exactly everything is allowed (zero is not negative).
    ok = draft(client, transfer_body([{"from_team": "product", "to_team": "research", "amount": "80000.00"}]))
    assert ok.status_code == 201
    assert ok.json()["after"]["allocations"]["product"] == "0.00"


def test_cumulative_transfers_from_one_team_checked_together(app, client):
    seed_budget(app)
    r = draft(client, transfer_body([
        {"from_team": "product", "to_team": "research", "amount": "50000.00"},
        {"from_team": "product", "to_team": "engineering", "amount": "40000.00"},
    ]))
    assert r.status_code == 422
    assert "negative_allocation_result" in reasons(r)


def test_addition_lines_must_sum_to_increase(app, client):
    seed_budget(app)
    r = draft(client, addition_body([{"to_team": "research", "amount": "35000.00"}]))
    assert r.status_code == 422
    assert reasons(r) == {"addition_lines_do_not_sum_to_increase"}
    over = draft(client, addition_body([{"to_team": "research", "amount": "35000.00"},
                                        {"to_team": "engineering", "amount": "15000.01"}]))
    assert reasons(over) == {"addition_lines_do_not_sum_to_increase"}


def test_addition_requires_positive_increase(app, client):
    seed_budget(app)
    for inc in ("0.00", "-50000.00"):
        r = draft(client, addition_body(increase=inc))
        assert r.status_code == 422
        assert "non_positive_amount" in reasons(r)


def test_unknown_team_rejected(app, client):
    seed_budget(app)
    r = draft(client, transfer_body([{"from_team": "marketing", "to_team": "research", "amount": "1.00"}]))
    assert reasons(r) == {"unknown_team"}
    r = draft(client, addition_body([{"to_team": "unattributed", "amount": "50000.00"}]))
    assert "unknown_team" in reasons(r)


def test_float_and_three_decimal_amounts_rejected(app, client):
    seed_budget(app)
    r = draft(client, transfer_body([{"from_team": "product", "to_team": "research", "amount": 25000.5}]))
    assert r.status_code == 422
    assert reasons(r) == {"float_not_allowed"}
    r = draft(client, transfer_body([{"from_team": "product", "to_team": "research", "amount": "25000.001"}]))
    assert reasons(r) == {"too_many_decimals"}
    r = draft(client, addition_body(increase=50000.0))
    assert "float_not_allowed" in reasons(r)
    r = draft(client, transfer_body([{"from_team": "product", "to_team": "research", "amount": "NaN"}]))
    assert reasons(r) == {"invalid_amount"}


def test_integer_amounts_accepted_and_normalized(app, client):
    seed_budget(app)
    r = draft(client, transfer_body([{"from_team": "product", "to_team": "research", "amount": 25000}]))
    assert r.status_code == 201
    assert r.json()["lines"][0]["amount"] == "25000.00"


def test_same_team_transfer_and_non_positive_line(app, client):
    seed_budget(app)
    r = draft(client, transfer_body([
        {"from_team": "product", "to_team": "product", "amount": "10.00"},
        {"from_team": "product", "to_team": "research", "amount": "0.00"},
    ]))
    assert reasons(r) == {"same_team_transfer", "non_positive_amount"}
    lines = {x["line"] for x in r.json()["error"]["details"]["reasons"]}
    assert lines == {0, 1}


def test_empty_lines_and_duplicate_lines(app, client):
    seed_budget(app)
    assert "empty_lines" in reasons(draft(client, transfer_body([])))
    r = draft(client, transfer_body([
        {"from_team": "product", "to_team": "research", "amount": "10.00"},
        {"from_team": "product", "to_team": "research", "amount": "10.00"},
    ]))
    assert reasons(r) == {"duplicate_line"}


def test_all_reasons_reported_at_once(app, client):
    seed_budget(app)
    r = draft(client, transfer_body(
        [{"from_team": "nope", "to_team": "research", "amount": 1.25}], unit="EUR", rationale="  "))
    assert reasons(r) == {"unknown_team", "float_not_allowed", "currency_mismatch", "rationale_required"}


def test_mixed_addition_and_transfer_lines_rejected(app, client):
    seed_budget(app)
    body = addition_body([{"from_team": "product", "to_team": "research", "amount": "50000.00"}])
    r = draft(client, body)
    assert r.status_code == 422  # an addition line has no source team; schema forbids it


def test_client_cannot_supply_after_state(app, client):
    seed_budget(app)
    r = draft(client, transfer_body(after={"total": "1.00", "allocations": {}}))
    assert r.status_code == 422


def test_base_version_in_future_and_period_mismatch(app, client):
    seed_budget(app)
    assert "base_version_in_future" in reasons(draft(client, transfer_body(base_version=7)))
    assert "period_mismatch" in reasons(draft(client, transfer_body(period="2031-P4")))


def test_drafting_against_outdated_version_is_409_with_current_state(app, client):
    seed_budget(app)
    from budget_helpers import decide

    p = draft(client, transfer_body()).json()
    assert decide(client, p["id"]).status_code == 201
    r = draft(client, addition_body(base_version=1))
    assert r.status_code == 409
    err = r.json()["error"]
    assert err["code"] == "stale_base_version"
    assert err["details"]["current_version"] == 2
    assert err["details"]["current"]["allocations"]["research"] == "85000.00"


def test_importer_cannot_draft(app, client):
    seed_budget(app)
    r = draft(client, transfer_body(), headers=IMPORTER_H)
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "role_forbidden"


def test_warning_when_allocation_falls_below_recorded_spend(app, client):
    seed_budget(app, with_spend=True, client=client)
    # Product has 20k recorded spend; taking 70k leaves 10k.
    r = draft(client, transfer_body([{"from_team": "product", "to_team": "research", "amount": "70000.00"}]))
    assert r.status_code == 201
    w = [x for x in r.json()["warnings"] if x["code"] == "allocation_below_recorded_spend"]
    assert len(w) == 1 and w[0]["team"] == "product"
    # Outcome A leaves product at 50k > 20k: no such warning.
    ok = draft(client, transfer_body()).json()
    assert not [x for x in ok["warnings"] if x["code"] == "allocation_below_recorded_spend"]


def test_evidence_must_exist_and_superseded_document_warns(app, client, session):
    seed_budget(app)
    now = datetime(2026, 10, 8, tzinfo=timezone.utc)
    new = m.CorpusDocument(id="doc-new", doc_key="research-eval-plan", version=1, title="plan", origin="seed",
                           doc_type="plan", plan_status="approved", authored_at=now, content="x",
                           content_hash="h1", is_simulated=True)
    old = m.CorpusDocument(id="doc-old", doc_key="research-timeline-thread", version=1, title="thread",
                           origin="seed", doc_type="correspondence", plan_status="informal", authored_at=now,
                           content="y", content_hash="h2", is_simulated=True)
    session.add_all([new, old])
    session.flush()
    old.superseded_by_document_id = "doc-new"
    session.commit()

    r = draft(client, transfer_body(evidence_refs=[{"kind": "document", "id": "missing"}]))
    assert reasons(r) == {"unknown_evidence"}
    r = draft(client, transfer_body(evidence_refs=[{"kind": "document", "id": "doc-new", "version": 2}]))
    assert reasons(r) == {"unknown_evidence"}

    ok = draft(client, transfer_body(evidence_refs=[{"kind": "document", "id": "doc-new"}])).json()
    assert ok["evidence_refs"][0]["version"] == 1
    assert not [w for w in ok["warnings"] if w["code"].startswith("cites_")]

    warned = draft(client, transfer_body(evidence_refs=[{"kind": "document", "id": "doc-old"}])).json()
    assert "cites_superseded_document" in {w["code"] for w in warned["warnings"]}


def test_no_evidence_warns(app, client):
    seed_budget(app)
    p = draft(client, transfer_body()).json()
    assert "no_evidence_cited" in {w["code"] for w in p["warnings"]}


def test_list_and_get_proposals(app, client):
    seed_budget(app)
    t = draft(client, transfer_body()).json()
    a = draft(client, addition_body()).json()
    listed = client.get("/api/proposals").json()
    assert [p["id"] for p in listed] == [t["id"], a["id"]]
    assert client.get("/api/proposals", params={"status": "applied"}).json() == []
    assert client.get(f"/api/proposals/{t['id']}").json()["id"] == t["id"]
    r = client.get("/api/proposals/nope")
    assert r.status_code == 404 and r.json()["error"]["code"] == "proposal_not_found"
