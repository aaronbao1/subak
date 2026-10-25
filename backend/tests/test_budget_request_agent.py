"""Read-only request and project-update context for allocation advice."""
from datetime import date, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.agent.tools import TOOL_NAMES, TOOLS
from app.db.models import ForecastSnapshot, Proposal
from test_agent import ANALYST, _toolbox, run

IMPORTER = {"X-Actor-Id": "request-import", "X-Actor-Role": "importer"}


def _update(client, *, content="Research needs $500 for the evaluation launch."):
    result = client.post("/api/documents", headers=IMPORTER, json={
        "doc_key": "research-new-update", "title": "Research launch update", "origin": "email_export",
        "doc_type": "update", "plan_status": "draft", "authored_at": "2026-10-24T11:00:00Z",
        "team_tags": ["research"], "project_tags": ["evaluation-launch"], "content": content,
        "is_simulated": True,
    })
    assert result.status_code == 201, result.text
    return result.json()["document"]


def _request(client, key, amount):
    period = client.get("/api/budget").json()["period"]
    result = client.post("/api/budget-requests", headers=ANALYST, json={
        "client_request_id": key, "team_id": "research", "title": f"Research {key}",
        "narrative": f"Request {amount} for the evaluation project.", "requested_amount": amount,
        "unit": "USD", "period_start": period["starts_on"],
        "period_end_exclusive": (date.fromisoformat(period["ends_on"]) + timedelta(days=1)).isoformat(),
        "source_ref": f"email:{key}",
    })
    assert result.status_code == 201, result.text
    return result.json()


def test_request_tool_is_read_only_and_surfaces_new_sources_without_current_signal(seeded):
    with TestClient(seeded) as client:
        run(client, "interpret_corpus")
        source = _update(client)
        before = client.get("/api/budget").json()
        with seeded.state.session_factory() as session:
            snapshots = session.scalar(select(func.count()).select_from(ForecastSnapshot))
            proposals = session.scalar(select(func.count()).select_from(Proposal))
        tools = _toolbox(seeded)
        context = tools.call("list_budget_requests", {"team": "research"})
        current = next(doc for doc in context["source_updates"]["items"] if doc["id"] == source["id"])
        assert current["version"] == 1 and current["has_current_signal"] is False
        assert "$500" in current["excerpt"] and current["plan_status"] == "draft"
        assert context["source_updates"]["truncated"] is False
        assert client.get("/api/budget").json() == before
        with seeded.state.session_factory() as session:
            assert session.scalar(select(func.count()).select_from(ForecastSnapshot)) == snapshots
            assert session.scalar(select(func.count()).select_from(Proposal)) == proposals
        assert next(tool for tool in TOOLS if tool.name == "list_budget_requests").kind == "read"
        assert not any(name in TOOL_NAMES for name in ("approve_budget_request", "apply_budget_request"))


def test_fake_allocation_considers_new_update_even_when_team_already_has_current_signals(seeded):
    with TestClient(seeded) as client:
        run(client, "interpret_corpus")
        source = _update(client)
        response = run(client, params={"mode": "addition", "amount": "50.00", "prioritize": "research"})
        assert response.status_code == 201, response.text
        result = response.json()
        assert "list_budget_requests" in [step["tool"] for step in result["steps"]]
        update = next(row for row in result["output"]["findings"] if row["type"] == "source_update" and row["document_id"] == source["id"])
        assert update["version"] == 1 and update["has_current_signal"] is False
        proposal = client.get(f"/api/proposals/{result['proposals'][0]['id']}").json()
        assert proposal["envelope_increase"] == "50.00"  # $500 source prose does not override finance's instruction.
        assert any(ref["kind"] == "document" and ref["id"] == source["id"] for ref in proposal["evidence_refs"])
        assert "review" in result["summary"].lower()


def test_current_requests_are_considered_without_overriding_finance_amount_or_claiming_fulfillment(seeded):
    with TestClient(seeded) as client:
        run(client, "interpret_corpus")
        first = _request(client, "eval", "21000.00")
        second = _request(client, "launch", "8000.00")
        before = client.get("/api/budget").json()
        tools = _toolbox(seeded)
        listed = tools.call("list_budget_requests", {"team": "research"})
        assert {row["id"] for row in listed["items"]} == {first["id"], second["id"]}
        assert all(row["status"] == "submitted" and row["source"]["reference"].startswith("email:") for row in listed["items"])
        assert all(row["assessment"]["amount_included_in_forecast"] is False for row in listed["items"])
        result = run(client, params={"mode": "addition", "amount": "50.00", "prioritize": "research"}).json()
        considered = [row for row in result["output"]["findings"] if row["type"] == "budget_request_considered"]
        assert {row["id"] for row in considered} == {first["id"], second["id"]}
        assert all(row["funding_linked"] is False for row in considered)
        assert "$21,000.00 requested" in result["summary"] and "do not change the published forecast" in result["summary"]
        assert "submitted" in result["summary"] and "email:eval" in result["summary"]
        assert first["period"]["label"] in result["summary"]
        proposal = client.get(f"/api/proposals/{result['proposals'][0]['id']}").json()
        assert proposal["envelope_increase"] == "50.00"
        assert all(ref["kind"] != "budget_request" for ref in proposal["evidence_refs"])
        assert client.get("/api/budget").json() == before
        assert client.get(f"/api/budget-requests/{first['id']}").json()["status"] == "submitted"


def test_answer_question_lists_pending_requests_without_drafting(seeded):
    with TestClient(seeded) as client:
        request = _request(client, "project", "500.00")
        result = run(client, task_type="answer_question", instruction="Which requests should finance consider?").json()
        assert result["proposals"] == []
        assert "$500.00 requested" in result["summary"]
        assert any(row.get("id") == request["id"] for row in result["output"]["findings"])
