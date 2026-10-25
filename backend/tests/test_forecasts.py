"""ForecastProvider behavior (acceptance check 8): unavailable never breaks spend or budget."""

from __future__ import annotations

import time

import pytest

from app.config import Settings
from app.core.clock import FrozenClock
from app.main import create_app
from app.providers.forecast import PlaceholderForecastProvider
from app.schemas.forecasts import ForecastResult
from app.services import forecasts as svc
from conftest import FROZEN_AT

TEAMS = ["engineering", "product", "research"]


class Boom:
    name = "boom"

    def get_forecast(self, period_id, team_ids):
        raise RuntimeError("model server down")


class Slow:
    name = "slow"

    def get_forecast(self, period_id, team_ids):
        time.sleep(0.5)
        return PlaceholderForecastProvider().get_forecast(period_id, team_ids)


class Garbage:
    name = "garbage"

    def __init__(self, payload):
        self.payload = payload

    def get_forecast(self, period_id, team_ids):
        return self.payload


@pytest.fixture
def make_client(tmp_path, clock, id_factory):
    apps = []

    def _make(provider=None, mode="placeholder"):
        from fastapi.testclient import TestClient
        from app.seed.northstar import seed

        app = create_app(Settings(db_path=tmp_path / f"f{len(apps)}.db", forecast_provider=mode),
                         clock=clock, id_factory=id_factory, forecast_provider=provider)
        apps.append(app)
        s = app.state.session_factory()
        seed(s, clock=clock, ids=id_factory)
        s.close()
        return TestClient(app)

    yield _make
    for a in apps:
        a.state.engine.dispose()


def test_placeholder_returns_shared_projections_labeled_simulated(seeded, client):
    body = client.get("/api/forecasts").json()
    assert body["availability"] == "available"
    assert {p["team"]: p["amount"] for p in body["projections"]} == {
        "research": "85000.00", "product": "50000.00", "engineering": "65000.00"}
    assert body["value_kind"] == "simulated" and body["basis"] == "full_period_total"
    assert "not a forecast model" in body["method_label"]


def test_unavailable_mode_returns_200_unavailable_not_zero(make_client):
    c = make_client(mode="unavailable")
    r = c.get("/api/forecasts")
    assert r.status_code == 200
    body = r.json()
    assert body["availability"] == "unavailable" and body["projections"] == []
    assert body["reason"] == "forecast provider not connected"
    assert c.get("/api/meta").json()["forecast_mode"] == "unavailable"


def test_spend_and_overview_work_when_provider_unavailable(make_client):
    c = make_client(mode="unavailable")
    spend = c.get("/api/spend/summary")
    assert spend.status_code == 200 and spend.json()["company_total"] == "95000.00"
    assert c.get("/api/budget").json()["envelope_total"] == "200000.00"
    ov = c.get("/api/overview").json()
    assert ov["forecast"]["availability"] == "unavailable"
    assert ov["company"]["recorded_spend"] == "95000.00" and ov["company"]["projected_total"] is None
    assert all(t["projected"] is None and t["projected_minus_allocation"] is None for t in ov["teams"])
    assert all(t["allocation"] is not None for t in ov["teams"])
    assert any("forecast unavailable" in n for n in ov["notes"])


def test_provider_exception_becomes_unavailable(make_client):
    c = make_client(provider=Boom())
    body = c.get("/api/forecasts").json()
    assert body["availability"] == "unavailable"
    assert "RuntimeError" in body["reason"] and "model server down" in body["reason"]
    assert c.get("/api/overview").status_code == 200
    assert c.get("/api/spend/summary").status_code == 200


def test_provider_timeout_becomes_unavailable():
    r = svc.get_forecast(Slow(), "2026-P1", TEAMS, clock=FrozenClock(FROZEN_AT), timeout=0.05)
    assert r.availability == "unavailable" and "timed out" in r.reason


@pytest.mark.parametrize("payload, fragment", [
    ({"nonsense": True}, "malformed"),
    (None, "malformed"),
    ({"provider": "g", "availability": "available", "target_period": "2026-P1", "method_label": "m",
      "projections": [{"team": "research", "amount": 85000.5}]}, "malformed"),  # float money
])
def test_malformed_provider_output_becomes_unavailable(payload, fragment):
    r = svc.get_forecast(Garbage(payload), "2026-P1", TEAMS, clock=FrozenClock(FROZEN_AT))
    assert r.availability == "unavailable" and fragment in r.reason


def test_wrong_period_unknown_team_negative_and_duplicate_are_sanitized():
    clock = FrozenClock(FROZEN_AT)
    wrong = ForecastResult(provider="x", availability="available", target_period="2027-P1", method_label="m",
                           projections=[{"team": "research", "amount": "1.00"}])
    assert svc.get_forecast(Garbage(wrong), "2026-P1", TEAMS, clock=clock).availability == "unavailable"
    messy = ForecastResult(provider="x", availability="available", target_period="2026-P1", method_label="m",
                           projections=[{"team": "research", "amount": "85000.00"},
                                        {"team": "research", "amount": "1.00"},
                                        {"team": "marketing", "amount": "5.00"},
                                        {"team": "product", "amount": "-5.00"}])
    r = svc.get_forecast(Garbage(messy), "2026-P1", TEAMS, clock=clock)
    assert r.availability == "partial"
    assert [(p.team, str(p.amount)) for p in r.projections] == [("research", "85000.00")]
    assert r.missing_teams == ["engineering", "product"]
    assert "duplicate" in r.reason and "unknown team" in r.reason and "negative" in r.reason


def test_partial_forecast_has_no_projected_total(make_client):
    partial = ForecastResult(provider="p", availability="available", target_period="2026-P1", method_label="m",
                             projections=[{"team": "research", "amount": "85000.00"}])
    c = make_client(provider=Garbage(partial))
    ov = c.get("/api/overview").json()
    assert ov["forecast"]["availability"] == "partial"
    assert ov["company"]["projected_total"] is None
    teams = {t["team"]: t for t in ov["teams"]}
    assert teams["research"]["projected"] == "85000.00" and teams["product"]["projected"] is None


def test_placeholder_other_period_is_unavailable():
    r = PlaceholderForecastProvider().get_forecast("2027-P1", TEAMS)
    assert r.availability == "unavailable" and r.projections == []


def test_snapshot_persists_and_can_be_cited(seeded, client):
    droid = {"X-Actor-Id": "droid", "X-Actor-Role": "droid_agent"}
    snap = client.post("/api/forecasts/snapshots", headers=droid)
    assert snap.status_code == 201
    sid = snap.json()["id"]
    assert client.get(f"/api/forecasts/snapshots/{sid}").json()["forecast"]["projections"][0]["team"] == "engineering"
    assert client.post("/api/forecasts/snapshots",
                       headers={"X-Actor-Id": "i", "X-Actor-Role": "importer"}).status_code == 403
    assert client.get("/api/forecasts/snapshots/nope").status_code == 404
    body = {"action_type": "transfer", "base_version": 1, "rationale": "r",
            "lines": [{"from_team": "product", "to_team": "research", "amount": "1000.00"}],
            "evidence_refs": [{"kind": "forecast_snapshot", "id": sid}]}
    p = client.post("/api/proposals", json=body, headers=droid)
    assert p.status_code == 201, p.text
    assert p.json()["evidence_refs"][0]["id"] == sid


def test_unavailable_snapshot_cited_adds_warning(make_client):
    c = make_client(mode="unavailable")
    droid = {"X-Actor-Id": "droid", "X-Actor-Role": "droid_agent"}
    sid = c.post("/api/forecasts/snapshots", headers=droid).json()["id"]
    body = {"action_type": "transfer", "base_version": 1, "rationale": "r",
            "lines": [{"from_team": "product", "to_team": "research", "amount": "1000.00"}],
            "evidence_refs": [{"kind": "forecast_snapshot", "id": sid}]}
    p = c.post("/api/proposals", json=body, headers=droid).json()
    assert "forecast_unavailable" in {w["code"] for w in p["warnings"]}
