"""Regression checks for finite risk and exact delivered-target replay."""
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone

import pytest

from forecasting.evaluation import (LabelVersion, LockedSelection, Opportunity,
                                    evaluate_rolling, summarize_opportunities)
from forecasting.models import Series
from forecasting.uncertainty import CalibrationPoint, JointPaths, cumulative_interval

UTC = timezone.utc
START = date(2025, 1, 1)


def midnight(day):
    return datetime.combine(day, datetime.min.time(), UTC)


def test_expected_excess_rejects_finite_input_subtraction_overflow():
    law = JointPaths(('p',), ('team',), (((1e308,),),), (1.,))
    with pytest.raises(ValueError, match='numerical'):
        law.expected_excess(-1e308)


def test_zero_weight_extremes_do_not_create_nan_excess():
    law = JointPaths(('zero', 'real'), ('team',), (((1e308,),), ((3.,),)), (0., 1.))
    assert law.expected_excess(-1e308) == 1e308


@pytest.mark.parametrize('prediction,actual,point', [(-1e308, 1e308, 0.), (0., 1e308, 1e308)])
def test_conformal_derived_overflow_has_no_available_endpoints(prediction, actual, point):
    records = tuple(CalibrationPoint(str(i), START + timedelta(days=i), START + timedelta(days=i+1),
                                    prediction, actual, midnight(START + timedelta(days=i+1)), 'p', 't')
                    for i in range(20))
    result = cumulative_interval(point, records, cutoff=midnight(START + timedelta(days=30)),
                                 horizon=1, procedure_id='p', scope='t')
    assert result.status == 'numerical_failure'
    assert result.lower is None and result.upper is None
    assert result.capabilities == () and result.event_probability is None


@pytest.mark.parametrize('alpha,want', [(0., 10.), (.8, 50.), (.9, 100.), (.95, 100.)])
def test_expected_shortfall_consumes_fractional_threshold_atom(alpha, want):
    law = JointPaths(('quiet', 'burst'), ('t',), (((0.,),), ((100.,),)), (.9, .1))
    assert law.expected_shortfall(alpha) == pytest.approx(want)
    assert law.expected_excess(50) == 5


def test_expected_shortfall_preserves_signed_constant_and_ignores_zero_mass():
    law = JointPaths(('refund', 'zero'), ('t',), (((-20.,),), ((1e308,),)), (1., 0.))
    assert law.expected_shortfall(.99) == -20
    constant = JointPaths(('p',), ('t',), (((1e308,),),), (1.,))
    assert constant.expected_shortfall(.9999999999999999) == 1e308


@pytest.mark.parametrize('alpha', [-.1, 1., float('inf'), float('nan')])
def test_expected_shortfall_requires_confidence_in_half_open_unit_interval(alpha):
    law = JointPaths(('p',), ('t',), (((1.,),),), (1.,))
    with pytest.raises(ValueError):
        law.expected_shortfall(alpha)


def test_unidentified_repeated_candidate_trials_cannot_win_by_lucky_retry():
    selection = LockedSelection(('a', 'b'), 3, seed=1)
    selection.record('a', 100, phase='D')
    with pytest.raises(ValueError, match='duplicate|aggregate'):
        selection.record('a', 0, phase='D')
    selection.record('b', 5, phase='D')
    assert selection.freeze() == 'b'


def replay_fixture():
    dates = tuple(START + timedelta(days=i) for i in range(50))
    series = Series('team', dates, tuple(float(i % 7 + 1) for i in range(50)))
    daily = tuple(LabelVersion(str(i), 'team', day, day+timedelta(days=1),
                               midnight(day+timedelta(days=3)), midnight(day+timedelta(days=3)), value)
                  for i, (day, value) in enumerate(zip(dates, series.values)))
    origin = dates[40]
    truth = LabelVersion('team:'+origin.isoformat(), 'team', origin, origin+timedelta(days=3),
                         midnight(dates[45]), midnight(dates[45]), 12.)
    return series, daily, origin, truth


def test_delayed_replay_predicts_bridge_and_scores_only_exact_target_dates():
    series, daily, origin, truth = replay_fixture()
    report = evaluate_rolling((series,), (origin,), 3, ('seasonal_naive',), midnight(START+timedelta(days=49)),
                              labels=(truth,), observation_labels=daily,
                              history_ends={origin: origin-timedelta(days=2)}, max_history_lag_days=2)
    row = report['candidates']['seasonal_naive']['rows'][0]
    # Mature prefix ends on day index 37. The next week is 4,5,6,7,1,2,3;
    # indexes 38,39 bridge to origin index 40, so the target is 6+7+1.
    assert row['prediction'] == 14
    assert row['actual'] == 12 and row['target_start'] == origin.isoformat()
    assert report['candidates']['seasonal_naive']['summary']['availability'] == 1
    manifest = report['model_manifests'][0]
    assert manifest['history_end'] == (origin-timedelta(days=2)).isoformat()
    assert manifest['history_lag_days'] == 2
    assert manifest['prediction_dates'] == [(origin+timedelta(days=i)).isoformat() for i in range(3)]


def test_stale_history_without_explicit_bridge_is_unavailable():
    series, daily, origin, truth = replay_fixture()
    report = evaluate_rolling((series,), (origin,), 3, ('last_observation',), midnight(START+timedelta(days=49)),
                              labels=(truth,), observation_labels=daily)
    assert report['candidates']['last_observation']['summary']['availability'] == 0


def test_declared_watermark_cannot_skip_immature_last_observation():
    series, daily, origin, truth = replay_fixture()
    report = evaluate_rolling((series,), (origin,), 3, ('last_observation',), midnight(START+timedelta(days=49)),
                              labels=(truth,), observation_labels=daily, history_ends={origin: origin-timedelta(days=1)},
                              max_history_lag_days=2)
    assert report['candidates']['last_observation']['summary']['availability'] == 0


def test_bridge_requires_explicit_bounded_lag_policy():
    series, daily, origin, truth = replay_fixture()
    with pytest.raises(ValueError, match='lag'):
        evaluate_rolling((series,), (origin,), 3, ('last_observation',), midnight(START+timedelta(days=49)),
                         labels=(truth,), observation_labels=daily, history_ends={origin: origin-timedelta(days=2)})


def test_accuracy_reports_keep_delivery_and_cohort_denominators():
    base = Opportunity('on', 'team', 'c', START, START+timedelta(days=1), 'on_time', 10., 12., 'mature')
    rows = (base, replace(base, opportunity_id='late', output_status='late', prediction=100.),
            replace(base, opportunity_id='stale', output_status='stale', prediction=50.),
            replace(base, opportunity_id='missing', output_status='unavailable', prediction=None),
            replace(base, opportunity_id='pending', label_status='pending', actual=None, cohort='cold'))
    report = summarize_opportunities(rows)
    assert report['on_time_point']['n'] == 1 and report['on_time_point']['mae'] == 2
    assert report['all_issued_point']['n'] == 3
    assert report['point'] == report['all_issued_point']
    assert report['issued'] == 4 and report['on_time_issued'] == 2
    assert report['mature'] == 4 and report['unissued'] == 1
    assert report['cohorts']['warm']['scheduled'] == 4
    assert report['cohorts']['warm']['on_time_point']['n'] == 1
    assert report['cohorts']['cold']['scheduled'] == 1
    assert report['cohorts']['cold']['all_issued_point']['n'] == 0


def test_expected_excess_below_threshold_does_not_subtract_opposite_extremes():
    law = JointPaths(('p',), ('team',), (((-1e308,),),), (1.,))
    assert law.expected_excess(1e308) == 0.


@pytest.mark.parametrize('model', ['last_observation', 'trailing_mean', 'seasonal_naive'])
@pytest.mark.parametrize('scale', [1, 10])
def test_delayed_replay_matches_scalar_serving_exact_future_target(tmp_path, model, scale):
    from decimal import Decimal
    from forecasting.contracts import ForecastRequest, Target, digest
    from forecasting.service import ForecastService
    from forecasting.snapshot import DailyValue, Snapshot
    from forecasting.store import ArtifactStore

    series, observations, origin, truth = replay_fixture()
    series = replace(series, values=tuple(v/scale for v in series.values))
    observations = tuple(replace(v, value=v.value/scale) for v in observations)
    end = origin-timedelta(days=2)
    target = Target('target', 'tenant', 'provider_reported_cost', 'USD', 'USD',
                    ('billing',), ('variable',), support='signed')
    daily = tuple(DailyValue('team', day, Decimal(str(value)))
                  for day, value in zip(series.dates, series.values) if day < end)
    fields = dict(target=target, as_of=midnight(origin), history_start=START, history_end=end,
                  daily=daily, company_daily=tuple(DailyValue('company', r.date, r.value) for r in daily),
                  ready=True, limitations=(), source_manifest=(), attribution_digest='mapping', coverage_digest='coverage')
    snapshot = Snapshot(digest(fields), **fields)
    request = ForecastRequest('request', target, midnight(origin), origin, origin+timedelta(days=3),
                              output='remainder', model=model)
    served = ForecastService(ArtifactStore(tmp_path/'store.sqlite')).run(
        request, snapshot, allowed_sources={'billing'}, max_history_lag_days=2)
    replay = evaluate_rolling((series,), (origin,), 3, (model,), midnight(START+timedelta(days=49)),
                              labels=(truth,), observation_labels=observations,
                              history_ends={origin: end}, max_history_lag_days=2)
    row = replay['candidates'][model]['rows'][0]
    assert row['prediction'] == float(served['result']['future'])
    assert set(served['entities']['team']['daily']) == {
        (origin+timedelta(days=i)).isoformat() for i in range(3)}


def test_direct_cumulative_bridge_is_unavailable_instead_of_scoring_gap_total():
    dates = tuple(START+timedelta(days=i) for i in range(100))
    series = Series('team', dates, (5.,)*100)
    origin = dates[90]
    report = evaluate_rolling((series,), (origin,), 3, ('tabular_direct_cumulative',), midnight(dates[-1]),
                              labels=(), history_ends={origin: origin-timedelta(days=2)}, max_history_lag_days=2)
    row = report['candidates']['tabular_direct_cumulative']['rows'][0]
    assert row['prediction'] is None and row['output_status'] == 'unavailable'
    assert 'direct cumulative' in row['failure']


def test_target_only_bridge_overflow_retains_unavailable_opportunity_and_other_candidates():
    series = Series('team', tuple(START+timedelta(days=i) for i in range(7)),
                    (-1e308, 1e308, 1e308, 0., 0., 0., 0.))
    origin = START+timedelta(days=8)
    report = evaluate_rolling((series,), (origin,), 2, ('seasonal_naive', 'last_observation'),
                              midnight(START+timedelta(days=31)), labels=(),
                              history_ends={origin: START+timedelta(days=7)}, max_history_lag_days=1)
    unavailable = report['candidates']['seasonal_naive']
    assert unavailable['summary']['scheduled'] == 1
    assert unavailable['summary']['availability'] == 0
    assert unavailable['summary']['unissued'] == 1
    assert unavailable['summary']['all_issued_point']['n'] == 0
    assert unavailable['rows'][0]['prediction'] is None
    assert unavailable['rows'][0]['output_status'] == 'unavailable'
    assert 'nonfinite cumulative target' in unavailable['rows'][0]['failure']
    other = report['candidates']['last_observation']
    assert other['summary']['scheduled'] == 1 and other['summary']['availability'] == 1
    assert other['rows'][0]['prediction'] == 0


@pytest.mark.parametrize('n,q,want', [(10, .8, 8), (30, .9, 27)])
def test_legacy_equal_weight_quantile_uses_normalized_atom_boundary(n, q, want):
    from forecasting.uncertainty import empirical_quantile
    assert empirical_quantile(tuple(range(1, n+1)), (1/n,)*n, q) == want


def test_weighted_quantile_normalizes_exact_masses_without_converting_decimal_values():
    from decimal import Decimal
    from forecasting import uncertainty
    # The caller's Decimal support is finite even above float range; a rank
    # calculation has no reason to narrow the returned value to binary float.
    first, second = Decimal('1e400'), Decimal('2e400')
    assert uncertainty.weighted_quantile((first, second), (1, 1), .5) is first
    assert uncertainty.weighted_quantile((first, second), (1, 1), 1.) is second
    assert uncertainty.weighted_quantile((second, first), (0, 1), 0.) is first
