"""ForecastingPackageProvider (FORECAST_PROVIDER=forecasting_package) on a small synthetic database.

Never uses datagen holdout files: every series here is synthetic. Covers backtest model selection,
exact sums (team = spend to date + daily; persons + team-level = team), the half-open period end
(Dec 31 is forecast), the partial latest day kept out of history, seat fees kept out of the series,
cache reuse while only today's rows change, refits on a new complete day or late rows, the refresh
endpoint, and failing closed when the package is missing.
"""

from __future__ import annotations

import itertools
import threading
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

pytest.importorskip("forecasting")

from app.config import Settings  # noqa: E402
from app.core.clock import FrozenClock, SequentialIdFactory  # noqa: E402
from app.db import models as m  # noqa: E402
from app.db.session import transaction  # noqa: E402
from app.main import create_app  # noqa: E402
from app.providers import forecasting_pkg as fp  # noqa: E402
from app.providers.forecast import BUCKET, TeamAttribution  # noqa: E402

D = Decimal
NOW = datetime(2026, 10, 24, 12, 0, tzinfo=timezone.utc)
TODAY = NOW.date()
HIST_START = date(2026, 5, 1)
_keys = itertools.count()


def _alpha(d: date) -> int:      # weekly shape, dollars
    return 100 if d.weekday() < 5 else 20


def _usage(batch_id: str, team: str | None, person: str | None, at: datetime, amount: str,
           category: str = "direct_api") -> m.UsageRecord:
    period = ("2026-Q4" if at.date() >= date(2026, 10, 1) else "2026-Q3" if at.date() >= date(2026, 7, 1)
              else "2026-Q2")
    return m.UsageRecord(import_batch_id=batch_id, source_kind="northstar_billing",
                         source_record_key=f"k{next(_keys)}", team_id=team, person_id=person, period_id=period,
                         occurred_at=at, value_kind="simulated", cost_category=category,
                         counts_toward_spend=True, amount=amount)


def _seed(sf) -> None:
    with transaction(sf) as s:
        s.add_all([
            m.PlanningPeriod(id="2026-Q2", label="Q2", starts_on=date(2026, 4, 1), ends_on=date(2026, 6, 30)),
            m.PlanningPeriod(id="2026-Q3", label="Q3", starts_on=date(2026, 7, 1), ends_on=date(2026, 9, 30)),
            m.PlanningPeriod(id="2026-Q4", label="Q4", starts_on=date(2026, 10, 1), ends_on=date(2026, 12, 31)),
            m.Team(id="alpha", name="Alpha"), m.Team(id="beta", name="Beta"), m.Team(id="gamma", name="Gamma"),
        ])
        s.flush()
        s.add_all([m.Person(id="alpha-ann", team_id="alpha", name="Ann"),
                   m.Person(id="alpha-bob", team_id="alpha", name="Bob"),
                   m.Person(id="beta-cy", team_id="beta", name="Cy")])
        batch = m.ImportBatch(id="b1", source_kind="northstar_billing", content_hash="h", status="imported",
                              imported_by="test", value_kind_default="simulated")
        s.add(batch)
        s.flush()
        d = HIST_START
        while d < TODAY:
            at = datetime(d.year, d.month, d.day, 9, tzinfo=timezone.utc)
            a = _alpha(d)
            s.add(_usage("b1", "alpha", "alpha-ann", at, f"{a * 3 // 4}.00"))
            s.add(_usage("b1", "alpha", "alpha-bob", at, f"{a - a * 3 // 4}.00"))
            s.add(_usage("b1", "beta", "beta-cy", at, "40.00"))
            s.add(_usage("b1", "beta", None, at, "10.00"))  # team-level spend
            if d.day == 1:  # monthly seat fee: must stay out of the daily series
                s.add(_usage("b1", "alpha", "alpha-ann", datetime(d.year, d.month, 1, tzinfo=timezone.utc),
                             "30.00", "subscription_fee"))
            d += timedelta(days=1)
        # The latest day is partial and huge: it counts as spend to date, never as model history.
        s.add(_usage("b1", "alpha", "alpha-ann", datetime(2026, 10, 24, 8, tzinfo=timezone.utc), "5000.00"))


def _add(sf, *rows) -> None:
    with transaction(sf) as s:
        for team, person, at, amount in rows:
            s.add(_usage("b1", team, person, at, amount))


@pytest.fixture
def pkg_app(tmp_path):
    app = create_app(Settings(db_path=tmp_path / "fp.db", forecast_provider="forecasting_package"),
                     clock=FrozenClock(NOW), id_factory=SequentialIdFactory())
    _seed(app.state.session_factory)
    prov = app.state.forecast_provider
    prov.wait_idle()       # the startup prefetch ran on an empty database; compute on the seeded one
    prov.refresh()
    yield app
    app.state.engine.dispose()


@pytest.fixture
def pc(pkg_app):
    with TestClient(pkg_app) as c:
        yield c


def _forecast(client) -> dict:
    r = client.get("/api/forecasts")
    assert r.status_code == 200
    return r.json()


def _team(body, team) -> dict:
    return next(p for p in body["projections"] if p["team"] == team)


def _spent(sf, team) -> D:
    with sf() as s:
        return sum((r.amount for r in s.query(m.UsageRecord).filter_by(team_id=team, period_id="2026-Q4")), D("0"))


# ---- pure pieces -------------------------------------------------------------------------------


def test_build_series_zero_fills_interior_gaps_and_stops_before_history_end():
    rows = {"t": {date(2026, 1, 2): 150, date(2026, 1, 5): 300, date(2026, 1, 9): 999}}
    dates, values, filled = fp.build_series(rows, date(2026, 1, 9))["t"]
    assert dates[0] == date(2026, 1, 2) and dates[-1] == date(2026, 1, 8)  # no invented days before the first row
    assert values == [1.5, 0, 0, 3.0, 0, 0, 0] and filled == 5
    assert fp.build_series({"t": {date(2026, 1, 9): 1}}, date(2026, 1, 9)) == {}


def test_backtest_origins_keep_the_horizon_inside_history():
    origins = fp.backtest_origins(date(2026, 10, 24), 69, date(2026, 1, 1))
    assert len(origins) == 8 and origins[0] == date(2026, 8, 16)
    assert all(o + timedelta(days=69) <= date(2026, 10, 24) for o in origins)
    assert fp.backtest_origins(date(2026, 10, 24), 69, date(2026, 8, 12)) == []


def test_select_models_prefers_more_scored_origins_then_lowest_wape_then_order():
    def summ(scored, wape):
        return {"summary": {"companies": {"t": {"scored": scored, "point": {"wape": wape, "mae": 1.0, "bias": 0.0}}}}}
    bt = {"candidates": {"a": summ(8, 0.30), "b": summ(8, 0.10), "c": summ(7, 0.01), "d": summ(8, 0.10)}}
    assert fp.select_models(bt, ["t"], ["a", "b", "c", "d"])["t"]["model"] == "b"
    assert fp.select_models({"candidates": {}}, ["t"], ["a"]) == {"t": {}}


def test_split_daily_is_exact_per_day_with_team_level_bucket():
    ta = TeamAttribution(team="t", people={"p1": D("10.00"), "p2": D("20.01")}, team_level=D("5.00"))
    weights, parts = fp.split_daily([(date(2026, 1, 1), 1001), (date(2026, 1, 2), 0), (date(2026, 1, 3), 7)], ta)
    assert [k for k, _ in weights] == ["p1", "p2", BUCKET]
    for i, total in enumerate([1001, 0, 7]):
        assert sum(parts[k][i] for k, _ in weights) == total


def test_to_cents_floors_negative_days_at_zero():
    assert fp.to_cents([1.004, -3.2, 2.675]) == [100, 0, 268]


# ---- provider on a database --------------------------------------------------------------------


def test_backtest_selects_per_team_models_on_history_only(pkg_app):
    run = pkg_app.state.forecast_provider._runs["2026-Q4"]
    assert run.history_end == TODAY and run.horizon == 69 and run.origins == 8
    alpha, beta = run.teams["alpha"], run.teams["beta"]
    assert alpha.scored == 8 and alpha.model == "weekday_mean" and alpha.validated and alpha.wape == pytest.approx(0, abs=1e-9)
    assert beta.model == "last_observation" and beta.wape == pytest.approx(0, abs=1e-9)  # flat: first in order
    assert alpha.history_start == HIST_START and alpha.history_days == (TODAY - HIST_START).days
    # seat fees are not in the daily series (Nov 1 forecast = the plain weekday shape)
    assert alpha.future[date(2026, 11, 2)] == 100_00 and alpha.future[date(2026, 11, 1)] == 20_00
    assert alpha.seat_cents == 30_00 and alpha.seat_month == "2026-10"
    assert run.skipped == {"gamma": "no counted spend history before 2026-10-24"}


def test_projection_is_spend_to_date_plus_future_and_includes_dec31(pc, pkg_app):
    body = _forecast(pc)
    assert body["provider"] == "forecasting_package" and body["value_kind"] == "estimated"
    assert body["availability"] == "partial" and body["missing_teams"] == ["gamma"]
    assert "gamma: no counted spend history" in body["reason"]
    assert body["as_of"] == "2026-10-24"
    sf = pkg_app.state.session_factory
    for team in ("alpha", "beta"):
        tp = _team(body, team)
        days = [dt["date"] for dt in tp["daily"]]
        assert days[0] == "2026-10-25" and days[-1] == "2026-12-31" and len(days) == 68
        assert D(tp["amount"]) == _spent(sf, team) + sum(D(dt["amount"]) for dt in tp["daily"])
    alpha = {dt["date"]: D(dt["amount"]) for dt in _team(body, "alpha")["daily"]}
    assert alpha["2026-10-26"] == D("100.00")         # partial Oct 24 ($5,000) did not leak into the model
    assert alpha["2026-11-01"] == D("50.00")          # Sunday $20 + carried seat fee $30
    assert alpha["2026-12-31"] == D("100.00")
    text = " | ".join(_team(body, "alpha")["assumptions"])
    assert "weekday_mean chosen by rolling backtest on history only" in text and "69-day horizon" in text
    assert "WAPE 0.0%" in text and "announced context events are not applied" in text
    assert "2026-10-24 is partial and not used for fitting" in text and "seat fees carried from 2026-10" in text


def test_person_projections_sum_exactly_to_the_team(pc):
    body = _forecast(pc)
    by_team = defaultdict(list)
    for pp in body["person_projections"]:
        by_team[pp["team"]].append(pp)
    assert sorted(by_team) == ["alpha", "beta"] and len(by_team["alpha"]) == 2
    for team, people in by_team.items():
        tp = _team(body, team)
        team_daily = {dt["date"]: D(dt["amount"]) for dt in tp["daily"]}
        per_day = defaultdict(D)
        for pp in people:
            assert D(pp["spent_to_date"]) + sum(D(dt["amount"]) for dt in pp["daily"]) == D(pp["amount"])
            for dt in pp["daily"]:
                per_day[dt["date"]] += D(dt["amount"])
        total = sum(D(pp["amount"]) for pp in people)
        if team == "alpha":   # no team-level spend: persons are the whole team, every day
            assert total == D(tp["amount"]) and per_day == team_daily
        else:                 # beta: the remainder is the team-level share (spend to date + its days)
            assert total < D(tp["amount"]) and all(per_day[d] <= v for d, v in team_daily.items())


def test_live_rows_today_raise_the_projection_without_a_refit(pc, pkg_app):
    prov = pkg_app.state.forecast_provider
    run = prov._runs["2026-Q4"]
    before = D(_team(_forecast(pc), "alpha")["amount"])
    _add(pkg_app.state.session_factory, ("alpha", "alpha-bob", datetime(2026, 10, 24, 11, tzinfo=timezone.utc), "500.00"))
    after = D(_team(_forecast(pc), "alpha")["amount"])
    prov.wait_idle()
    assert after == before + D("500.00")
    assert prov._runs["2026-Q4"] is run and not run.stale   # same model run: no new complete day


def test_new_complete_day_serves_the_old_run_then_refits(pc, pkg_app):
    prov = pkg_app.state.forecast_provider
    run = prov._runs["2026-Q4"]
    _add(pkg_app.state.session_factory, ("alpha", "alpha-ann", datetime(2026, 10, 25, 1, tzinfo=timezone.utc), "7.00"))
    body = _forecast(pc)
    tp = _team(body, "alpha")
    assert body["as_of"] == "2026-10-25" and tp["daily"][0]["date"] == "2026-10-26"
    assert any("a refit on the newer data is running" in a for a in tp["assumptions"])
    prov.wait_idle()
    fresh = prov._runs["2026-Q4"]
    assert fresh is not run and fresh.history_end == date(2026, 10, 25) and fresh.horizon == 68
    tp = _team(_forecast(pc), "alpha")
    assert not any("refit" in a for a in tp["assumptions"])
    assert D(tp["amount"]) == _spent(pkg_app.state.session_factory, "alpha") + sum(D(d["amount"]) for d in tp["daily"])


def test_late_rows_on_a_complete_day_invalidate_the_run(pc, pkg_app):
    prov = pkg_app.state.forecast_provider
    run = prov._runs["2026-Q4"]
    _forecast(pc)
    prov.wait_idle()
    assert prov._runs["2026-Q4"] is run
    _add(pkg_app.state.session_factory, ("beta", "beta-cy", datetime(2026, 10, 10, 9, tzinfo=timezone.utc), "1.00"))
    _forecast(pc)
    prov.wait_idle()
    assert run.stale and prov._runs["2026-Q4"] is not run and not prov._runs["2026-Q4"].stale


def test_repeated_requests_reuse_the_built_result(pc, pkg_app):
    prov = pkg_app.state.forecast_provider
    _forecast(pc)
    n = len(prov._results)
    assert _forecast(pc) == _forecast(pc) and len(prov._results) == n


def test_refresh_endpoint_reports_models(pc):
    r = pc.post("/api/forecasts/refresh")
    assert r.status_code == 200
    body = r.json()
    assert body["refreshed"] is True and body["period"] == "2026-Q4" and body["history_end"] == "2026-10-24"
    assert body["horizon_days"] == 69
    assert {t["team"]: t["model"] for t in body["teams"]} == {"alpha": "weekday_mean", "beta": "last_observation"}
    assert body["skipped"] == [{"team": "gamma", "reason": "no counted spend history before 2026-10-24"}]


def test_refresh_endpoint_with_placeholder_is_a_no_op(seeded, client):
    body = client.post("/api/forecasts/refresh").json()
    assert body["refreshed"] is False and body["provider"] == "placeholder"


def test_compat_forecasts_are_labeled_as_model_estimates(pc):
    items = pc.get("/compat/api/forecasts").json()
    alpha = next(f for f in items if f["teamId"] == "alpha" and "personId" not in f)
    assert alpha["status"] == "available" and alpha["origin"] == "forecasting_service"
    assert not any("simulated projection" in x for x in alpha["limitations"])
    assert any("person projections (team projection split" in a for a in alpha["assumptions"])
    gamma = next(f for f in items if f["teamId"] == "gamma")
    assert gamma["status"] == "unavailable"


def test_meta_labels_projections_as_model_output(pc):
    rows = {r["component"]: r for r in pc.get("/api/meta").json()["real_vs_simulated"]}
    assert rows["projections"]["status"] == "real" and "rolling backtest" in rows["projections"]["detail"]


def test_fails_closed_without_the_package(pc, monkeypatch):
    monkeypatch.setattr(fp, "_forecasting", lambda: None)
    body = _forecast(pc)
    assert body["availability"] == "unavailable" and body["projections"] == []
    assert "forecasting package not installed" in body["reason"]


def test_before_the_first_run_it_says_computing_not_zero(pkg_app):
    from app.services import forecasts as svc

    prov = fp.ForecastingPackageProvider()
    prov.bind(pkg_app.state.session_factory, FrozenClock(NOW), prefetch=False)
    prov._submit = lambda *a, **k: None   # keep the background run from racing the assertion
    with pkg_app.state.session_factory() as s:
        period = s.get(m.PlanningPeriod, "2026-Q4")
        result = svc.forecast_for_period(s, prov, period, clock=FrozenClock(NOW))
    assert result.availability == "unavailable" and result.projections == []
    assert "forecast computing" in result.reason


def test_settings_accept_the_provider():
    s = Settings.from_env({"FORECAST_PROVIDER": "forecasting_package"})
    assert s.forecast_provider == "forecasting_package"


# ---- in-place changes, uncertainty text, refresh ordering --------------------------------------------


def test_in_place_reattribution_invalidates_the_model_run(pc, pkg_app):
    """A team mapping change moves existing rows with an UPDATE: no new rowid, same history_end. The
    per-team history fingerprint still catches it, and the refit is fitted on the new team histories."""
    prov = pkg_app.state.forecast_provider
    run = prov._runs["2026-Q4"]
    _forecast(pc)
    prov.wait_idle()
    assert prov._runs["2026-Q4"] is run and not run.stale
    with transaction(pkg_app.state.session_factory) as s:
        for rec in s.query(m.UsageRecord).filter(m.UsageRecord.team_id == "beta",
                                                 m.UsageRecord.occurred_at < datetime(2026, 10, 1, tzinfo=timezone.utc)):
            rec.team_id, rec.person_id = "alpha", None
    _forecast(pc)
    prov.wait_idle()
    fresh = prov._runs["2026-Q4"]
    assert run.stale and fresh is not run and not fresh.stale
    assert fresh.teams["alpha"].history_start == run.teams["alpha"].history_start
    assert fresh.fingerprint != run.fingerprint


def test_unrelated_writes_do_not_invalidate_the_model_run(pc, pkg_app):
    prov = pkg_app.state.forecast_provider
    run = prov._runs["2026-Q4"]
    with transaction(pkg_app.state.session_factory) as s:
        s.get(m.Team, "gamma").name = "Gamma renamed"   # a teams write that changes no model input
    _forecast(pc)
    prov.wait_idle()
    assert prov._runs["2026-Q4"] is run and not run.stale


def test_team_deactivation_invalidates_the_model_run(pc, pkg_app):
    prov = pkg_app.state.forecast_provider
    run = prov._runs["2026-Q4"]
    with transaction(pkg_app.state.session_factory) as s:
        s.get(m.Team, "beta").active = False
    _forecast(pc)
    prov.wait_idle()
    assert run.stale and "beta" not in prov._runs["2026-Q4"].teams


def test_uncertainty_labels_mae_as_a_horizon_total(pc):
    tp = _team(_forecast(pc), "alpha")
    if "not validated" in tp["uncertainty"]:
        pytest.skip("no backtest on this synthetic history")
    assert "/day" not in tp["uncertainty"] and "-day total" in tp["uncertainty"]


def test_refresh_waits_for_a_queued_background_run_and_wins(pkg_app):
    """refresh() runs on the same single model worker: a background run that started earlier (and read
    older data) finishes first, so it can never overwrite the newer forced run."""
    prov = pkg_app.state.forecast_provider
    gate, started = threading.Event(), threading.Event()
    real = prov._compute
    order = []

    def slow(period_id, lib):
        started.set()
        gate.wait(5)
        order.append("background")
        return real(period_id, lib)

    prov._compute = slow
    prov._submit("2026-Q4", key=("test-bg",))
    started.wait(5)
    prov._compute = lambda period_id, lib: (order.append("refresh"), real(period_id, lib))[1]
    done = []
    t = threading.Thread(target=lambda: done.append(prov.refresh("2026-Q4")))
    t.start()
    gate.set()
    t.join(30)
    prov.wait_idle()
    assert order == ["background", "refresh"] and done and prov._runs["2026-Q4"] is done[0]
