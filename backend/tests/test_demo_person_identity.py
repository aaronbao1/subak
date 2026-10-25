"""Demo directory identities are shared by native API, compatibility API, and SDK tools."""

from dataclasses import replace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.agent.toolbox import BackendToolbox
from app.db.models import AgentRun, Person
from app.db.session import transaction
from app.forecasting.fixtures import build_northstar_snapshot
from app.main import create_app
from app.seed.northstar import seed


EXPECTED_TEAMS = {
    "maya": "research", "priya": "research", "owen": "product",
    "liam": "product", "zoe": "engineering", "noah": "engineering",
}


@pytest.fixture
def demo_app(settings, clock, id_factory):
    application = create_app(
        replace(settings, forecast_demo=True, forecast_worker=False),
        clock=clock, id_factory=id_factory,
    )
    with application.state.session_factory() as session:
        seed(session, clock=clock, ids=id_factory)
    yield application
    application.state.engine.dispose()


def _toolbox(application):
    with transaction(application.state.session_factory) as session:
        session.add(AgentRun(
            id="run_identity", task_type="interpret_corpus", input={}, runner_kind="fake",
            status="running", started_at=application.state.clock.now(),
        ))
    return BackendToolbox(
        session_factory=application.state.session_factory,
        run_id="run_identity", source="fake_runner", runner_kind="fake",
        clock=application.state.clock, ids=application.state.id_factory,
        forecast_provider=application.state.forecast_provider,
        forecast_service=application.state.forecast_service,
    )


def test_demo_native_and_compat_directory_resolve_the_forecast_people(demo_app):
    with TestClient(demo_app) as client:
        native = client.get("/api/people").json()
        compat = client.get("/compat/api/people").json()
        assert {row["id"]: row["team"] for row in native} == EXPECTED_TEAMS
        assert {row["id"]: row["teamId"] for row in compat} == EXPECTED_TEAMS
        for row in native:
            response = client.get(f"/api/people/{row['id']}")
            assert response.status_code == 200
            assert response.json() == row
            assert row["is_simulated"] is True
            assert row["email"] is None and row["role"] is None
        assert {row["id"] for row in client.get("/api/people?team=research").json()} == {"maya", "priya"}
        assert client.get("/api/people/not-a-person").status_code == 404
        # Reading the demo directory never rewrites or duplicates repository identities.
        with demo_app.state.session_factory() as session:
            stored = set(session.scalars(select(Person.id)))
        assert len(stored) == 15
        assert stored.isdisjoint(EXPECTED_TEAMS)
        assert client.get(f"/api/people/{next(iter(stored))}").status_code == 404


def test_demo_sdk_people_tool_uses_the_same_canonical_directory(demo_app):
    toolbox = _toolbox(demo_app)
    result = toolbox.list_people()
    assert result["count"] == 6
    assert {row["id"]: row["team"] for row in result["items"]} == EXPECTED_TEAMS
    assert {row["id"] for row in toolbox.list_people(team="product")["items"]} == {"owen", "liam"}


def test_demo_canonical_person_can_be_tagged_and_cited_by_native_signals(demo_app):
    passage = "Maya Chen moves to product team from 2026-10-27 at 1 exposure."
    with TestClient(demo_app) as client:
        response = client.post("/api/documents", headers={"X-Actor-Id": "importer", "X-Actor-Role": "importer"}, json={
            "doc_key": "demo-maya-move", "title": "Maya team move", "origin": "upload",
            "doc_type": "plan", "plan_status": "approved", "authored_at": "2026-10-23T12:00:00Z",
            "team_tags": ["research"], "person_tags": ["maya"], "content": passage, "is_simulated": True,
        })
        assert response.status_code == 201, response.text
        document = response.json()["document"]
        assert document["person_tags"] == ["maya"]
        signal = client.post("/api/signals", headers={"X-Actor-Id": "analyst", "X-Actor-Role": "finance_analyst"}, json={
            "scope": "person", "team": "research", "person_ids": ["maya"], "change_type": "expansion",
            "status": "current", "summary": "Maya's team move is planned.", "uncertainty": "Future effective date.",
            "citations": [{"document_id": document["id"], "quote": passage}],
        })
        assert signal.status_code == 201, signal.text
        assert signal.json()["person_ids"] == ["maya"]
        evidence = next(item for item in client.get("/api/forecast-evidence").json()["items"]
                        if item["envelope"]["source_id"] == "native:document:demo-maya-move")
        assert evidence["drivers"][0]["scope"] == {"person_id": "maya"}
        assert evidence["drivers"][0]["status"] == "eligible"
        assert evidence["envelope"]["payload"]["signal_refs"][0]["id"] == signal.json()["id"]


@pytest.mark.parametrize("passage,original,correction,expected_scope", [
    ("Workload is 2.4 work_units per day from 2026-10-26 through 2026-11-15.",
     {"project_tags": ["atlas"]}, {"project_tags": ["beacon"]}, {"project_id": "beacon"}),
    ("Moves to product team from 2026-10-27 at 1 exposure.",
     {"person_tags": ["maya"]}, {"person_tags": ["priya"]}, {"person_id": "priya"}),
    ("Atlas workload is 2.4 work_units per day from 2026-10-26 through 2026-11-15.",
     {"project_tags": ["atlas"], "is_simulated": False}, {"is_simulated": True}, {"project_id": "atlas"}),
], ids=["project-scope", "person-scope", "synthetic-provenance"])
def test_native_source_scope_or_provenance_correction_creates_new_forecast_evidence(
    demo_app, passage, original, correction, expected_scope,
):
    headers = {"X-Actor-Id": "importer", "X-Actor-Role": "importer"}
    body = {
        "doc_key": "corrected-source", "title": "Corrected source", "origin": "upload",
        "doc_type": "plan", "plan_status": "approved", "authored_at": "2026-10-23T12:00:00Z",
        "team_tags": ["research"], "content": passage, "is_simulated": True, **original,
    }
    with TestClient(demo_app) as client:
        initial = client.post("/api/documents", headers=headers, json=body)
        assert initial.status_code == 201, initial.text
        revised = client.post("/api/documents", headers=headers, json={**body, **correction})
        assert revised.status_code == 201, revised.text
        assert revised.json()["document"]["version"] == 2
        evidence = next(item for item in client.get("/api/forecast-evidence").json()["items"]
                        if item["envelope"]["source_id"] == "native:document:corrected-source")
        assert evidence["envelope"]["payload"]["document"]["version"] == 2
        assert evidence["drivers"][0]["scope"] == expected_scope
        assert evidence["drivers"][0]["status"] == "eligible"
        assert evidence["envelope"]["is_synthetic"] is True
        assert evidence["drivers"][0]["is_synthetic"] is True
        # Replaying the original export cannot restore outdated scope/provenance.
        assert client.post("/api/documents", headers=headers, json=body).status_code == 200
        latest = next(item for item in client.get("/api/forecast-evidence").json()["items"]
                      if item["envelope"]["source_id"] == "native:document:corrected-source")
        assert latest == evidence


def test_demo_directory_uses_only_effective_unambiguous_memberships(demo_app, clock):
    def snapshot_factory(**kwargs):
        snapshot = build_northstar_snapshot(**kwargs)
        snapshot["memberships"] = [
            row for row in snapshot["memberships"] if row["person_id"] != "maya"
        ] + [
            {"person_id": "maya", "team_id": "research", "effective_from": "2026-01-01", "effective_to": "2026-10-24", "exposure": 1},
            {"person_id": "maya", "team_id": "product", "effective_from": "2026-10-27", "effective_to": None, "exposure": 1},
            {"person_id": "priya", "team_id": "engineering", "effective_from": "2026-10-01", "effective_to": None, "exposure": 1},
        ]
        return snapshot

    demo_app.state.forecast_service.snapshot_factory = snapshot_factory
    with TestClient(demo_app) as client:
        for path, team_field in (("/api/people", "team"), ("/compat/api/people", "teamId")):
            rows = {row["id"]: row for row in client.get(path).json()}
            assert rows["maya"][team_field] == "unattributed"
            assert rows["priya"][team_field] == "unattributed"
            assert rows["owen"][team_field] == "product"
        clock.advance(days=3)
        assert client.get("/api/people/maya").json()["team"] == "product"


def test_normal_mode_keeps_repository_people_on_all_directory_surfaces(seeded, client):
    native = client.get("/api/people").json()
    compat = client.get("/compat/api/people").json()
    tool = _toolbox(seeded).list_people()
    assert len(native) == len(compat) == tool["count"] == 15
    assert {row["id"] for row in native} == {row["id"] for row in compat} == {row["id"] for row in tool["items"]}
    assert set(EXPECTED_TEAMS).isdisjoint(row["id"] for row in native)
    assert client.get("/api/people/maya").status_code == 404
