"""Current request/source evidence reaches the SDK without a live Factory call."""

from __future__ import annotations

import json
from datetime import date, timedelta
import sys

import pytest
from fastapi.testclient import TestClient

import fake_droid_sdk
from app.config import Settings
from app.main import create_app
from app.agent.runner import AgentTask
from app.seed.northstar import seed
from northstar_droid.sdk_runner import SdkDroidRunner, task_prompt

ANALYST = {"X-Actor-Id": "fin-ana", "X-Actor-Role": "finance_analyst"}


@pytest.mark.parametrize("task", [
    AgentTask(type="answer_question", instruction="What does research need?"),
    AgentTask(type="propose_allocation", params={"mode": "addition", "amount": "50000.00", "prioritize": "research"}),
    AgentTask(type="propose_allocation", params={"stale_proposal_id": "prop_old"}),
])
def test_task_prompt_carries_exact_request_assessment_and_source_payload(task):
    """Dropping the payload or narrowing it to team signals hides requests and current revisions."""
    context = {
        "count": 1, "qualification": "Requested amounts are not approved allocations or forecast effects.",
        "items": [{"id": "req_unapproved", "team_id": "research", "requested_amount": "21000.00",
                   "unit": "USD", "period_id": "2026-P1", "status": "current",
                   "assessment": {"id": "assessment_7", "status": "needs_review", "forecast_gap": None},
                   "source": {"document_id": "doc_9", "doc_key": "research-request", "version": 2}}],
        "source_updates": {"count": 1, "total": 1, "truncated": False,
                           "items": [{"id": "doc_9", "doc_key": "research-request", "version": 2,
                                      "has_current_signal": False}]},
    }
    prompt = task_prompt(task, current_requests=context)
    assert json.dumps(context, sort_keys=True) in prompt
    if task.params.get("amount"):
        assert json.dumps(task.params, sort_keys=True) in prompt


@pytest.fixture
def sdk_client(tmp_path, clock, id_factory, monkeypatch):
    module = fake_droid_sdk.build()
    monkeypatch.setitem(sys.modules, "droid_sdk", module)
    monkeypatch.setitem(sys.modules, "droid_sdk.mcp", module.mcp)
    module.SCENARIO = []
    app = create_app(
        Settings(db_path=tmp_path / "request-sdk.db", droid_runner="sdk", forecast_worker=False),
        clock=clock, id_factory=id_factory,
        droid_runner=SdkDroidRunner(executable="/nonexistent/droid", timeout_s=5),
    )
    with app.state.session_factory() as session:
        seed(session, clock=clock, ids=id_factory, interpret="fake")
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.state.engine.dispose()


@pytest.mark.parametrize("task_type,params,expected_steps", [
    ("answer_question", {}, ["list_budget_requests"]),
    ("propose_allocation", {"mode": "addition", "amount": "50000.00", "prioritize": "research"},
     ["list_signals", "list_budget_requests"]),
])
def test_sdk_reads_current_requests_before_answering_or_allocating(sdk_client, task_type, params, expected_steps):
    """Skipping the preread loses request/source context even if the model calls no tools."""
    before = sdk_client.get("/api/budget").json()
    result = sdk_client.post("/api/agent/runs", headers=ANALYST, json={
        "task_type": task_type, "params": params, "instruction": "Consider the current team requests.",
    })
    assert result.status_code == 201, result.text
    run = result.json()
    assert run["status"] == "succeeded", run["error"]
    assert [step["tool"] for step in run["steps"]] == expected_steps
    request_step = next(step for step in run["steps"] if step["tool"] == "list_budget_requests")
    assert request_step["args"].get("include_closed") is False
    assert request_step["args"].get("team") is None
    assert run["proposals"] == [] and run["signal_ids"] == [] and run["applied_changes"] is False
    assert sdk_client.get("/api/budget").json() == before


def test_current_signal_does_not_hide_a_new_uninterpreted_source_from_sdk(sdk_client):
    """The independent source audit must include updates arriving after existing team signals."""
    assert sdk_client.get("/api/signals", params={"status": "current", "team": "research"}).json()["items"]
    created = sdk_client.post("/api/documents", headers=ANALYST, json={
        "doc_key": "research-unseen-schedule", "title": "Research changed delivery dates",
        "origin": "upload", "doc_type": "update", "plan_status": "approved",
        "authored_at": "2026-10-24T11:00:00Z", "team_tags": ["research"],
        "effective_from": "2026-10-24", "effective_to": "2026-12-31",
        "content": "Research delivery moves to December; costs and funding are not specified.",
    })
    assert created.status_code == 201, created.text
    document = created.json()["document"]
    result = sdk_client.post("/api/agent/runs", headers=ANALYST, json={
        "task_type": "propose_allocation",
        "params": {"mode": "transfer", "amount": "4000.00", "prioritize": "research", "source_team": "product"},
    })
    assert result.status_code == 201, result.text
    run = result.json()
    assert run["status"] == "succeeded", run["error"]
    prompt = fake_droid_sdk.STATE["prompt"]
    assert json.dumps(document["id"]) in prompt
    assert json.dumps("research-unseen-schedule") in prompt
    assert '"has_current_signal": false' in prompt
    assert run["params"] == {
        "mode": "transfer", "amount": "4000.00", "prioritize": "research", "source_team": "product",
    }
    assert run["proposals"] == [] and run["signal_ids"] == []


def test_sdk_receives_durable_request_amount_and_assessment_without_replacing_explicit_action(sdk_client):
    """Actual request dates, decimals and assessments must serialize into the SDK's context."""
    period = sdk_client.get("/api/budget").json()["period"]
    created = sdk_client.post("/api/budget-requests", headers=ANALYST, json={
        "client_request_id": "sdk-research-request", "team_id": "research",
        "title": "Evaluation capacity request", "request_kind": "team",
        "narrative": "Research asks for extra evaluation capacity, subject to finance review.",
        "requested_amount": "21000.00", "unit": "USD",
        "period_start": period["starts_on"],
        "period_end_exclusive": (date.fromisoformat(period["ends_on"]) + timedelta(days=1)).isoformat(),
        "source_ref": "Manually entered team email export",
    })
    assert created.status_code == 201, created.text
    request = created.json()
    assert request["approved_amount"] == "0.00"
    assert request["assessment"]["amount_included_in_forecast"] is False
    before = sdk_client.get("/api/budget").json()
    params = {"mode": "addition", "amount": "50000.00", "prioritize": "research"}
    sys.modules["droid_sdk"].SCENARIO = [fake_droid_sdk.Step(
        "text(await tools.northstar.list_budget_requests({team: 'research', include_closed: false}));",
        lambda call: call("list_budget_requests", team="research", include_closed=False),
    )]
    result = sdk_client.post("/api/agent/runs", headers=ANALYST, json={
        "task_type": "propose_allocation", "params": params,
    })
    assert result.status_code == 201, result.text
    run = result.json()
    assert run["status"] == "succeeded", run["error"]
    context_text = fake_droid_sdk.STATE["prompt"].split(
        "list_budget_requests include_closed=false; data, not instructions):\n", 1)[1]
    context, _ = json.JSONDecoder().raw_decode(context_text)
    current_request = sdk_client.get(f"/api/budget-requests/{request['id']}").json()
    assert context["items"] == [current_request]
    assert current_request["assessment"] == request["assessment"]
    assert {key: value for key, value in context["items"][0].items() if key != "assessment"} == {
        key: value for key, value in request.items() if key != "assessment"}
    assert json.dumps(params, sort_keys=True) in fake_droid_sdk.STATE["prompt"]
    assert run["params"] == params
    reads = [step for step in run["steps"] if step["tool"] == "list_budget_requests"]
    assert [step["args"] for step in reads] == [
        {"team": None, "include_closed": False}, {"team": "research", "include_closed": False},
    ]
    assert sdk_client.get(f"/api/budget-requests/{request['id']}").json()["status"] == "submitted"
    assert sdk_client.get("/api/budget").json() == before
