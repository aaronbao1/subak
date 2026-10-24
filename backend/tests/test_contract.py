"""Contract: every committed fixture validates, and the export is deterministic and up to date."""

from __future__ import annotations

import json

import pytest

from app.config import BACKEND_ROOT
from app.contract import export

CONTRACT = BACKEND_ROOT / "contract"
REQUIRED = {
    "meta", "teams", "budget_state_initial", "spend_summary", "spend_summary_incomplete", "spend_records_research",
    "import_result", "import_duplicate", "forecast_available", "forecast_unavailable", "overview",
    "overview_forecast_unavailable", "documents", "document_detail_research_plan",
    "document_versions_product_launch", "signals", "proposal_transfer_pending", "proposal_addition_pending",
    "decision_applied_transfer", "decision_applied_addition", "decision_replayed", "decision_rejected",
    "budget_state_after_transfer", "budget_state_after_addition", "decision_history", "error_stale_proposal",
    "proposal_rebased", "error_self_approval", "error_role_forbidden_droid_decides",
    "error_validation_negative_allocation", "error_validation_addition_mismatch", "error_idempotency_key_reused",
    "error_citation_not_found",
}


@pytest.fixture(scope="module")
def rendered():
    return export.render()


def _committed():
    return {p.stem: json.loads(p.read_text()) for p in (CONTRACT / "fixtures").glob("*.json") if p.stem != "index"}


def test_every_fixture_validates_against_schema():
    fixtures = _committed()
    assert REQUIRED <= set(fixtures)
    for name, fx in fixtures.items():
        export.validate_fixture(fx)
        assert fx["name"] == name
        if fx["schema"] == "ErrorBody":
            assert fx["status"] >= 400 and set(fx["response"]["error"]) == {"code", "message", "details"}
        else:
            assert fx["status"] < 300


def test_export_is_deterministic_and_matches_committed_fixtures(rendered):
    assert export.render() == rendered
    assert export.diff(CONTRACT, rendered) == [], "run: .venv/bin/python -m app.contract.export"


def test_fixture_values_match_northstar_story():
    f = _committed()
    allocs = lambda name: {a["team"]: a["amount"] for a in f[name]["response"]["allocations"]}  # noqa: E731
    assert allocs("budget_state_initial") == {"research": "60000.00", "product": "80000.00", "engineering": "60000.00"}
    assert allocs("budget_state_after_transfer") == {"research": "85000.00", "product": "50000.00",
                                                     "engineering": "65000.00"}
    assert f["budget_state_after_transfer"]["response"]["envelope_total"] == "200000.00"
    assert allocs("budget_state_after_addition") == {"research": "95000.00", "product": "80000.00",
                                                     "engineering": "75000.00"}
    assert f["budget_state_after_addition"]["response"]["envelope_total"] == "250000.00"
    assert f["spend_summary"]["response"]["company_total"] == "95000.00"
    assert f["spend_summary_incomplete"]["response"]["coverage"]["status"] == "partial"
    assert f["forecast_unavailable"]["response"]["projections"] == []
    assert f["decision_replayed"]["response"]["replayed"] is True
    assert f["proposal_transfer_pending"]["response"]["envelope_increase"] == "0.00"
    assert f["proposal_addition_pending"]["response"]["action_type"] == "addition"
    assert f["error_stale_proposal"]["response"]["error"]["details"]["current_version"] == 2


def test_openapi_lists_every_route():
    spec = json.loads((CONTRACT / "openapi.json").read_text())
    for path in ("/api/spend/summary", "/api/spend/records", "/api/coverage", "/api/budget", "/api/forecasts",
                 "/api/overview", "/api/documents", "/api/signals", "/api/signals/{signal_id}", "/api/proposals",
                 "/api/proposals/{proposal_id}/decision", "/api/decisions", "/api/meta"):
        assert path in spec["paths"], path
