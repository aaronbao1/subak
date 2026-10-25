"""Per-person placeholder split and daily points (frontend-integration-design §4)."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.agent.toolbox import BackendToolbox
from app.db.models import PlanningPeriod
from app.providers.forecast import (
    BUCKET,
    PLACEHOLDER_PROJECTIONS,
    Attribution,
    PlaceholderForecastProvider,
    TeamAttribution,
    largest_remainder,
    remaining_days,
    split_team,
)
from app.schemas.forecasts import DailyProjection, ForecastResult, PersonProjection, TeamProjection
from app.seed.northstar import PEOPLE
from app.services import forecasts as svc

D = Decimal
START, END = date(2026, 10, 1), date(2026, 12, 31)
TEAMS = ["engineering", "product", "research"]
SPENT = {"research": D("45000.00"), "product": D("20000.00"), "engineering": D("30000.00")}


def _assert_reconciles(result: ForecastResult, attr: Attribution) -> None:
    by_team = defaultdict(list)
    for pp in result.person_projections:
        by_team[pp.team].append(pp)
    for tp in result.projections:
        ta = attr.teams[tp.team]
        people = by_team[tp.team]
        s = sum(ta.people.values(), D("0")) + ta.team_level
        p0 = tp.amount - sum((pp.amount for pp in people), D("0"))
        assert p0 >= ta.team_level
        if ta.team_level == 0:
            assert p0 == 0
        if tp.daily is not None:
            assert s + sum(d.amount for d in tp.daily) == tp.amount
            per_day = defaultdict(Decimal)
            for pp in people:
                assert pp.spent_to_date + sum(d.amount for d in pp.daily) == pp.amount
                for d in pp.daily:
                    per_day[d.date] += d.amount
            for d in tp.daily:
                assert per_day[d.date] <= d.amount
                if ta.team_level == 0:
                    assert per_day[d.date] == d.amount


# ---- seed ------------------------------------------------------------------------------------


@pytest.fixture
def seeded_result(seeded, session, clock):
    period = session.get(PlanningPeriod, "2026-P1")
    attr = svc.attribution_for_period(session, period, TEAMS)
    result = svc.forecast_for_period(session, PlaceholderForecastProvider(), period, clock=clock)
    return attr, result


def test_seed_attribution_matches_team_spend(seeded_result):
    attr, _ = seeded_result
    assert attr.as_of == date(2026, 10, 20)
    for team, total in SPENT.items():
        ta = attr.teams[team]
        assert ta.team_level == 0  # included usage is the only team-level row and counts toward nothing
        assert sum(ta.people.values()) == total
        assert sorted(ta.people) == sorted(p["id"] for p in PEOPLE if p["team"] == team)


def test_seed_person_projections_sum_exactly_to_team_placeholders(seeded_result):
    attr, result = seeded_result
    assert result.availability == "available" and result.reason is None
    assert result.as_of == date(2026, 10, 20)
    assert len(result.person_projections) == 15
    for tp in result.projections:
        people = [pp for pp in result.person_projections if pp.team == tp.team]
        assert tp.amount == PLACEHOLDER_PROJECTIONS[tp.team]
        assert sum(pp.amount for pp in people) == tp.amount  # exact Decimal, no bucket in the seed
        for pp in people:
            assert pp.spent_to_date == attr.teams[tp.team].people[pp.person]
            assert pp.amount == pp.amount.to_integral_value()  # whole dollars -> exact JS sums
            assert "placeholder" in pp.uncertainty and "not a person-level model" in pp.uncertainty
            assert any(f"{pp.share}% of team spend" in a for a in pp.assumptions)
    _assert_reconciles(result, attr)


def test_seed_daily_points_cover_oct21_to_dec31_with_weekday_weight(seeded_result):
    _, result = seeded_result
    expected = [date(2026, 10, 21) + timedelta(days=i) for i in range(72)]
    assert expected[-1] == END
    for tp in result.projections:
        assert [d.date for d in tp.daily] == expected
        assert all(d.amount == d.amount.to_integral_value() and d.amount >= 0 for d in tp.daily)
        # weekday days get ~3x a weekend day (exactly within the 1-dollar quantum per person)
        n_people = sum(1 for pp in result.person_projections if pp.team == tp.team)
        wed = next(d.amount for d in tp.daily if d.date == date(2026, 10, 21))
        sat = next(d.amount for d in tp.daily if d.date == date(2026, 10, 24))
        assert abs(wed - 3 * sat) <= 4 * n_people
    for pp in result.person_projections:
        assert [d.date for d in pp.daily] == expected


def test_split_is_deterministic(seeded, session, clock):
    period = session.get(PlanningPeriod, "2026-P1")
    a = svc.forecast_for_period(session, PlaceholderForecastProvider(), period, clock=clock)
    b = svc.forecast_for_period(session, PlaceholderForecastProvider(), period, clock=clock)
    assert a.model_dump(mode="json") == b.model_dump(mode="json")


def test_get_forecast_tool_strips_daily_but_snapshot_keeps_it(seeded, app):
    from app.db.models import AgentRun
    from app.db.session import transaction

    with transaction(app.state.session_factory) as s:
        s.add(AgentRun(id="run_fc", task_type="propose_allocation", input={}, runner_kind="fake",
                       status="running", started_at=app.state.clock.now()))
    tools = BackendToolbox(session_factory=app.state.session_factory, run_id="run_fc", source="fake_runner",
                           runner_kind="fake", clock=app.state.clock, ids=app.state.id_factory,
                           forecast_provider=PlaceholderForecastProvider())
    out = tools.get_forecast()
    fc = out["forecast"]
    assert fc["person_projections"] and all("daily" not in p for p in fc["person_projections"])
    assert all("daily" not in p for p in fc["projections"])
    assert all({"amount", "spent_to_date", "share"} <= set(p) for p in fc["person_projections"])
    s = app.state.session_factory()
    try:
        snap = svc.snapshot_out(svc.get_snapshot(s, out["id"]))["forecast"]
    finally:
        s.close()
    assert all(len(p.daily) == 72 for p in snap.person_projections)


# ---- property cases --------------------------------------------------------------------------


def _attr(people=None, team_level="0", as_of=date(2026, 10, 20)):
    people = {k: D(v) for k, v in (people or {}).items()}
    return Attribution(as_of=as_of, period_start=START, period_end=END,
                       teams={"research": TeamAttribution("research", people, D(team_level))})


def _run(attr, placeholder="85000.00"):
    days = remaining_days(attr)
    return split_team("research", D(placeholder), attr.teams["research"], days), days


def _check(attr, placeholder, team_daily, people):
    ta = attr.teams["research"]
    p = D(placeholder)
    s = sum(ta.people.values(), D("0")) + ta.team_level
    p0 = p - sum((pp.amount for pp in people), D("0"))
    assert p0 >= ta.team_level
    if team_daily is not None:
        assert s + sum(d.amount for d in team_daily) == p
        for pp in people:
            assert pp.spent_to_date + sum(d.amount for d in pp.daily) == pp.amount
        for i, d in enumerate(team_daily):
            assert sum(pp.daily[i].amount for pp in people) <= d.amount
    return p0


def test_zero_spend_splits_equally_without_bucket():
    attr = _attr({"a": "0", "b": "0", "c": "0"}, as_of=None)
    (team_daily, people, below), days = _run(attr, "100.00")
    assert not below and days[0] == START and len(days) == 92
    assert [pp.amount for pp in people] == [D(34), D(33), D(33)]  # tie -> id ascending
    assert all("equal share" in pp.assumptions[0] for pp in people)
    assert _check(attr, "100.00", team_daily, people) == 0


def test_single_person_gets_everything():
    attr = _attr({"a": "123.45"})
    (team_daily, people, _), _ = _run(attr, "1000.00")
    assert len(people) == 1 and people[0].amount == D("1000.00") and people[0].share == "100.0"
    assert _check(attr, "1000.00", team_daily, people) == 0


def test_team_level_bucket_is_kept_and_never_emitted():
    attr = _attr({"a": "300.00", "b": "100.00"}, team_level="100.00")
    (team_daily, people, _), _ = _run(attr, "1000.00")
    assert [pp.person for pp in people] == ["a", "b"]
    p0 = _check(attr, "1000.00", team_daily, people)
    assert p0 == D("200.00")  # 100 spent + 1/5 of the 500 remaining
    assert [pp.amount for pp in people] == [D("600.00"), D("200.00")]


def test_cents_in_placeholder_go_to_largest_weight_and_first_day():
    attr = _attr({"a": "10.00", "b": "30.00"})
    (team_daily, people, _), _ = _run(attr, "1000.37")
    a, b = people
    assert b.amount - b.amount.to_integral_value() == D("0.37")
    assert a.amount == a.amount.to_integral_value()
    assert b.daily[0].amount - b.daily[0].amount.to_integral_value() == D("0.37")
    assert sum(pp.amount for pp in people) == D("1000.37")
    _check(attr, "1000.37", team_daily, people)


def test_placeholder_below_spend_has_no_person_split():
    attr = Attribution(as_of=date(2026, 10, 20), period_start=START, period_end=END,
                       teams={"research": TeamAttribution("research", {"a": D("90000")}, D("0"))})
    r = PlaceholderForecastProvider().get_forecast("2026-P1", ["research"], attribution=attr)
    assert r.person_projections == [] and r.projections[0].daily is None
    assert "below recorded spend" in r.projections[0].uncertainty


def test_as_of_at_period_end_omits_daily():
    attr = _attr({"a": "10.00", "b": "30.00"}, as_of=END)
    (team_daily, people, _), days = _run(attr, "100.00")
    assert days == [] and team_daily is None and all(pp.daily is None for pp in people)
    assert sum(pp.amount for pp in people) == D("100.00")


def test_largest_remainder_ties_are_stable():
    assert largest_remainder(1, [("b", 1), ("a", 1)]) == {"b": 1, "a": 0}
    assert largest_remainder(2, [("a", 1), ("b", 1), (BUCKET, 1)]) == {"a": 1, "b": 1, BUCKET: 0}
    assert largest_remainder(10, [("a", 0), ("b", 3)]) == {"a": 0, "b": 10}


def test_no_attribution_keeps_old_shape():
    r = PlaceholderForecastProvider().get_forecast("2026-P1", TEAMS)
    assert r.person_projections == [] and r.as_of is None
    assert all(tp.daily is None for tp in r.projections)


# ---- service ---------------------------------------------------------------------------------


class TwoArg:
    name = "two-arg"

    def get_forecast(self, period_id, team_ids):
        return PlaceholderForecastProvider().get_forecast(period_id, team_ids)


def test_provider_without_supports_attribution_still_works(seeded, session, clock):
    period = session.get(PlanningPeriod, "2026-P1")
    r = svc.forecast_for_period(session, TwoArg(), period, clock=clock)
    assert r.availability == "available" and r.person_projections == []


class Tampered:
    """Claims attribution support and returns a person split that does not add up for product."""

    name = "tampered"
    supports_attribution = True

    def get_forecast(self, period_id, team_ids, attribution=None):
        r = PlaceholderForecastProvider().get_forecast(period_id, team_ids, attribution=attribution)
        people = [pp.model_copy(update={"amount": pp.amount + 1}) if pp.person == "product-zara-ali" else pp
                  for pp in r.person_projections]
        return r.model_copy(update={"person_projections": people})


def test_sanitize_drops_non_reconciling_person_split_with_reason(seeded, session, clock):
    period = session.get(PlanningPeriod, "2026-P1")
    r = svc.forecast_for_period(session, Tampered(), period, clock=clock)
    assert {pp.team for pp in r.person_projections} == {"engineering", "research"}
    assert "person split did not reconcile for product" in r.reason
    assert [tp.amount for tp in r.projections] == [D("65000.00"), D("50000.00"), D("85000.00")]


def test_sanitize_drops_unknown_person():
    attr = _attr({"a": "10.00"})
    tp = TeamProjection(team="research", amount=D("100"))
    bad = PersonProjection(person="zz", team="research", amount=D("100"), spent_to_date=D("0"), share="100.0")
    raw = ForecastResult(provider="x", availability="available", target_period="2026-P1", projections=[tp],
                         method_label="m", person_projections=[bad])
    r = svc._sanitize(raw, object(), "2026-P1", ["research"], None, attr)
    assert r.person_projections == [] and "not a member" in r.reason


def test_daily_projection_amounts_serialize_as_money_strings():
    d = DailyProjection(date=date(2026, 10, 21), amount=D("3"))
    assert d.model_dump(mode="json") == {"date": "2026-10-21", "amount": "3.00"}


def test_unavailable_sanitization_withholds_person_money_but_keeps_issued_lineage():
    raw=ForecastResult(provider='engine',availability='available',target_period='2026-P1',
        projections=[TeamProjection(team='unknown-team',amount=D('123'))],
        person_projections=[PersonProjection(person='unknown-person',team='unknown-team',amount=D('123'),spent_to_date=D('0'),share='100.0')],
        as_of=date(2026,10,20),method_label='issued',forecast_run_id='run-kept',input_snapshot_id='snapshot-kept')
    result=svc._sanitize(raw,object(),'2026-P1',['research'],None)
    assert result.availability=='unavailable'
    assert result.projections==[] and result.person_projections==[]
    assert result.as_of is None
    assert result.forecast_run_id=='run-kept' and result.input_snapshot_id=='snapshot-kept'
