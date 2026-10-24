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
    "error_citation_not_found", "agent_run_interpret", "agent_run_propose_addition", "agent_run_propose_transfer",
    "agent_runs", "error_runner_unavailable", "forecast_partial", "overview_forecast_partial", "proposal_revised",
    "proposal_revised_original", "error_decide_revised_original", "decision_applied_revised", "decision_detail",
    "agent_run_detail", "agent_run_answer_question", "signal_patched", "signal_deleted", "team_mapping_upserted",
    "document_ingested", "document_duplicate", "coverage_incomplete",
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
        if fx["schema"] == "NoContent":
            assert fx["status"] == 204 and fx["response"] is None
        elif fx["schema"] == "ErrorBody":
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
    b = f["agent_run_propose_addition"]["response"]
    assert b["applied_changes"] is False and b["proposals"][0]["status"] == "pending_review"
    assert f["error_runner_unavailable"]["status"] == 503


def test_openapi_lists_every_route():
    spec = json.loads((CONTRACT / "openapi.json").read_text())
    for path in ("/api/spend/summary", "/api/spend/records", "/api/coverage", "/api/budget", "/api/forecasts",
                 "/api/overview", "/api/documents", "/api/signals", "/api/signals/{signal_id}", "/api/proposals",
                 "/api/proposals/{proposal_id}/decision", "/api/decisions", "/api/meta", "/api/agent/runs",
                 "/api/agent/runs/{run_id}", "/api/agent/runs/{run_id}/events", "/api/agent/tools"):
        assert path in spec["paths"], path


def _spec() -> dict:
    return json.loads((CONTRACT / "openapi.json").read_text())


def _template_for(spec: dict, method: str, path: str) -> str:
    """The OpenAPI path template a concrete fixture path was served by (most literal match wins)."""
    import re

    matches = [t for t, item in spec["paths"].items()
               if method.lower() in item and re.fullmatch(re.sub(r"\\{[^/]+\\}", "[^/]+", re.escape(t)), path)]
    assert matches, f"no OpenAPI path for {method} {path}"
    return min(matches, key=lambda t: t.count("{"))


def test_fixture_schema_names_are_openapi_components():
    comps = set(_spec()["components"]["schemas"])
    for name, fx in _committed().items():
        schema = fx["schema"]
        if schema == "NoContent":
            continue
        assert schema.removesuffix("[]") in comps, f"{name}: {schema} is not an OpenAPI component"


def test_every_fixture_status_is_declared_in_openapi():
    spec = _spec()
    for name, fx in _committed().items():
        method, path = fx["request"]["method"], fx["request"]["path"]
        op = spec["paths"][_template_for(spec, method, path)][method.lower()]
        assert str(fx["status"]) in op["responses"], f"{name}: {method} {path} -> {fx['status']} undeclared"
        resp = op["responses"][str(fx["status"])]
        if fx["schema"] == "ErrorBody":
            ref = resp["content"]["application/json"]["schema"]["$ref"]
            assert ref.endswith("/ErrorBody"), name
            assert f"`{fx['response']['error']['code']}`" in resp["description"], \
                f"{name}: code {fx['response']['error']['code']} not documented for {method} {path}"


def test_openapi_errors_use_the_error_envelope_not_fastapi_default():
    spec = _spec()
    text = json.dumps(spec)
    assert "HTTPValidationError" not in text
    assert {"ErrorBody", "ErrorDetail", "AgentEventOut"} <= set(spec["components"]["schemas"])
    decision = spec["paths"]["/api/proposals/{proposal_id}/decision"]["post"]["responses"]
    assert {"200", "201", "400", "401", "403", "404", "409", "422"} <= set(decision)
    for code in ("stale_proposal", "idempotency_key_reused", "proposal_not_pending"):
        assert code in decision["409"]["description"]
    assert "self_approval_forbidden" in decision["403"]["description"]
    assert "200" in spec["paths"]["/api/imports"]["post"]["responses"]
    runs = spec["paths"]["/api/agent/runs"]["post"]["responses"]
    assert runs["503"]["content"]["application/json"]["schema"]["$ref"].endswith("/ErrorBody")
    sse = spec["paths"]["/api/agent/runs/{run_id}/events"]["get"]["responses"]["200"]["content"]
    assert sse["text/event-stream"]["schema"]["$ref"].endswith("/AgentEventOut")
