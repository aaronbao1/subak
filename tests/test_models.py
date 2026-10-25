"""Numerical behavior, target semantics, and capability rejection checks."""
from datetime import date, timedelta
import math

import pytest

from forecasting.models import (
    MODEL_REGISTRY, ModelUnavailable, Series, eligibility, forecast,
)


def history(values, entity='a', start=date(2024, 1, 1)):
    return Series(entity, tuple(start + timedelta(days=i) for i in range(len(values))), tuple(values))


def future(series, n):
    return tuple(series.dates[-1] + timedelta(days=i + 1) for i in range(n))


@pytest.mark.parametrize('name,config,want', [
    ('last_observation', {}, (8., 8.)),
    ('trailing_mean', {'window': 3}, (14/3, 14/3)),
    ('exponential_smoothing', {'alpha': .5}, (5.5, 5.5)),
])
def test_baselines_have_hand_calculated_means(name, config, want):
    s = history([2., 4., 8.])
    p = forecast(s, future(s, 2), name, config)
    assert p.daily_values == pytest.approx(want)
    assert p.cumulative_value == pytest.approx(sum(want))
    assert p.statistic == 'mean'
    assert p.coherence == 'daily_sum'


def test_weekday_and_seasonal_naive_use_requested_calendar_dates():
    s = history(list(range(1, 8)) + list(range(11, 18)))
    dates = future(s, 10)
    assert forecast(s, dates, 'seasonal_naive').daily_values == (11.,12.,13.,14.,15.,16.,17.,11.,12.,13.)
    assert forecast(s, dates, 'weekday_mean', {'window':14}).daily_values == (6.,7.,8.,9.,10.,11.,12.,6.,7.,8.)


def test_exact_leap_day_month_remainder_and_empty_horizon():
    s = history([3.] * 28, start=date(2024, 2, 1))
    p = forecast(s, (date(2024, 2, 29),), 'last_observation')
    assert p.dates == (date(2024, 2, 29),)
    assert p.cumulative_value == 3.
    assert forecast(s, (), 'last_observation').cumulative_value == 0.


@pytest.mark.parametrize('dates,values', [
    ((date(2024,1,1),date(2024,1,3)), (1.,2.)),
    ((date(2024,1,1),date(2024,1,1)), (1.,2.)),
    ((date(2024,1,1),), (float('nan'),)),
    ((date(2024,1,1),), (float('inf'),)),
    ((), ()),
])
def test_missing_duplicate_nonfinite_or_empty_history_is_not_zero_filled(dates, values):
    with pytest.raises(ValueError):
        Series('a', dates, values)


def test_invalid_future_dates_and_unknown_config_are_rejected():
    s = history([1.] * 30)
    for dates in [(s.dates[-1],), (future(s, 3)[0],future(s,3)[2])]:
        with pytest.raises(ModelUnavailable):
            forecast(s, dates, 'last_observation')
    with pytest.raises(ModelUnavailable, match='config'):
        forecast(s, future(s, 2), 'last_observation', {'future_actuals':[100.]})


def test_history_minimum_is_explicit_and_window_cannot_cross_gaps():
    s = history([4.] * 6)
    e = eligibility(s, 'seasonal_naive')
    assert not e.eligible and e.required_history == 7
    with pytest.raises(ModelUnavailable, match='history'):
        forecast(s, future(s, 2), 'seasonal_naive')
    with pytest.raises(ModelUnavailable, match='history'):
        forecast(s, future(s,2), 'trailing_mean', {'window':7})


def test_signed_refunds_survive_unless_target_declares_nonnegative():
    s = history([0., -4., -2.])
    p = forecast(s, future(s,2), 'last_observation')
    assert p.daily_values == (-2., -2.)
    with pytest.raises(ModelUnavailable, match='nonnegative'):
        forecast(s, future(s,2), 'last_observation', {'nonnegative':True})


def test_state_model_learns_linear_trend_instead_of_aliasing_last_value():
    s = history([2.+3.*i for i in range(50)])
    p = forecast(s, future(s,3), 'local_linear_trend', {'damping':1.})
    assert p.daily_values == pytest.approx((152.,155.,158.))
    assert p.daily_values != forecast(s, future(s,3), 'last_observation').daily_values
    assert p.metadata['state_slope'] == pytest.approx(3.)


def test_damping_limits_long_horizon_trend_and_records_assumption():
    s = history([float(i) for i in range(30)])
    damped = forecast(s, future(s,30), 'local_linear_trend', {'damping':.8})
    full = forecast(s, future(s,30), 'local_linear_trend', {'damping':1.})
    assert damped.daily_values[-1] < full.daily_values[-1]
    assert damped.statistic == 'mean'
    assert 'conditional' in ' '.join(damped.limitations).lower()


def test_regularized_calendar_fit_predicts_original_scale_and_constant_series():
    s = history([10.+2.*i for i in range(56)])
    p = forecast(s, future(s,2), 'calendar_regression', {'ridge_alpha':.00001})
    assert p.daily_values == pytest.approx((122.,124.), rel=.002)
    c = history([4.] * 56)
    assert forecast(c, future(c,3), 'calendar_regression').daily_values == pytest.approx((4.,4.,4.))
    scaled = history([100*x for x in s.values])
    q = forecast(scaled, future(scaled,2), 'calendar_regression', {'ridge_alpha':.00001})
    assert q.daily_values == pytest.approx(tuple(100*x for x in p.daily_values))
    assert p.metadata['regularization'] > 0


def test_pooled_ridge_trains_with_auditable_members_and_rejects_future_panel():
    s = history([20.+i for i in range(70)], 'small')
    peer = history([200.+10*i for i in range(70)], 'large')
    p = forecast(s, future(s,3), 'pooled_ridge', panel=(s,peer))
    assert p.daily_values[-1] > s.values[-1]
    assert p.metadata['training_entities'] == ('large','small')
    renamed = history(s.values, 'x')
    other = history(peer.values, 'y')
    assert forecast(renamed, future(renamed,3), 'pooled_ridge', panel=(other,renamed)).daily_values == pytest.approx(p.daily_values)
    with pytest.raises(ModelUnavailable, match='future'):
        forecast(s, future(s,3), 'pooled_ridge', panel=(history([1.]*71,'future'),))


def test_local_model_is_invariant_to_unrelated_panel_members():
    s = history([float(i) for i in range(30)])
    peer = history([999.] * 30, 'peer')
    assert forecast(s, future(s,3), 'local_linear_trend').daily_values == forecast(s, future(s,3), 'local_linear_trend', panel=(peer,)).daily_values


def test_tabular_direct_mean_learns_weekday_pattern_without_recursive_actuals():
    s = history([100. if i % 7 < 5 else 10. for i in range(140)])
    p = forecast(s, future(s,7), 'tabular_mean')
    assert p.statistic == 'mean'
    assert p.daily_values[:5] == pytest.approx((100.,)*5, abs=3)
    assert p.daily_values[5:] == pytest.approx((10.,)*2, abs=3)
    assert p.metadata['horizon_strategy'] == 'direct'
    assert p.metadata['training_rows'] > 0
    assert p.cumulative_value == pytest.approx(sum(p.daily_values))


def test_direct_cumulative_has_no_fabricated_daily_allocation():
    s = history([5.] * 100)
    p = forecast(s, future(s,14), 'tabular_direct_cumulative')
    assert p.daily_values is None
    assert p.cumulative_value == pytest.approx(70.)
    assert p.coherence == 'direct_cumulative_only'
    assert p.statistic == 'mean'
    assert 'nested' in ' '.join(p.limitations)


def test_nonnegative_projection_is_disclosed_as_point_not_mean():
    s = history([float(30-i) for i in range(30)])
    p = forecast(s, future(s,5), 'local_linear_trend', {'damping':1.,'nonnegative':True})
    assert min(p.daily_values) == 0.
    assert p.statistic == 'point'
    assert p.metadata['projection_count'] > 0


@pytest.mark.parametrize('name', ['neural','foundation','session','llm','lognormal','croston','tsb','compound_arrival_severity','multivariate_var','gaussian_process','reconciliation_mint','online_change_detector','quantile_sum'])
def test_optional_unimplemented_models_never_return_baseline_aliases(name):
    s = history([3.] * 100)
    with pytest.raises(ModelUnavailable):
        forecast(s, future(s,7), name)


def test_missing_dependency_is_explicit_capability_failure(monkeypatch):
    import forecasting.models as module
    monkeypatch.setattr(module, '_dependency_versions', lambda: {})
    s = history([3.] * 60)
    with pytest.raises(ModelUnavailable, match='dependency'):
        forecast(s, future(s,7), 'tabular_mean')
    assert forecast(s, future(s,2), 'last_observation').cumulative_value == 6.


def test_unsupported_registry_families_explain_missing_capabilities():
    for name in ('tsb','compound_arrival_severity','multivariate_var','gaussian_process','reconciliation_mint','online_change_detector'):
        assert not MODEL_REGISTRY[name].supported
        assert MODEL_REGISTRY[name].unavailable_reason


def test_prediction_rejects_incoherent_and_nonfinite_outputs():
    from forecasting.models import Prediction
    d = (date(2024,1,1),)
    with pytest.raises(ValueError):
        Prediction('x',d,(1.,),2.,'mean','daily_sum')
    with pytest.raises(ValueError):
        Prediction('x',d,(float('nan'),),1.,'mean','daily_sum')
    with pytest.raises(ValueError):
        Prediction('x',d,None,1.,'median','direct_cumulative_only')


def test_horizon_training_rows_cannot_borrow_unobserved_future_labels():
    s = history([1.] * 42)
    with pytest.raises(ModelUnavailable, match='training rows'):
        forecast(s, future(s,30), 'tabular_direct_cumulative')


def test_bounded_configuration_and_nonfinite_parameters_are_rejected():
    s = history([1.] * 60)
    for cfg in ({'n_estimators':501},{'seed':-1},{'max_depth':7},{'learning_rate':float('nan')},{'nonnegative':'yes'}):
        with pytest.raises(ModelUnavailable):
            forecast(s,future(s,2),'tabular_mean',cfg)


def test_local_models_preserve_zero_and_refund_scale_without_log_transforms():
    s = history([0.,-2.,4.,0.,5.,0.,-3.] * 5)
    scaled = history([100*v for v in s.values])
    for name in ('last_observation','trailing_mean','weekday_mean','seasonal_naive','exponential_smoothing','local_linear_trend'):
        p=forecast(s,future(s,7),name)
        q=forecast(scaled,future(scaled,7),name)
        assert q.daily_values == pytest.approx(tuple(100*v for v in p.daily_values))


def test_panel_duplicates_and_conflicting_target_history_are_rejected():
    s=history([1.] * 70)
    peer=history([2.] * 70,'b')
    with pytest.raises(ModelUnavailable,match='duplicate'):
        forecast(s,future(s,2),'pooled_ridge',panel=(peer,peer))
    with pytest.raises(ModelUnavailable,match='differs'):
        forecast(s,future(s,2),'pooled_ridge',panel=(history([2.] * 70),))


def test_weekday_window_cannot_omit_required_weekdays():
    s = history([1.] * 30)
    with pytest.raises(ModelUnavailable, match='window'):
        forecast(s,future(s,7),'weekday_mean',{'window':1})


def test_overflow_is_unavailable_instead_of_a_numeric_success():
    s = history([1e308] * 30)
    with pytest.raises(ModelUnavailable):
        forecast(s,future(s,30),'last_observation')


def test_pooled_peer_history_does_not_erase_target_cold_start():
    target = history([0.], 'new-team', start=date(2024,3,10))
    established = history([100.]*70, 'established')
    # A complete one-day measured zero is valid data, but is not a qualified
    # warm history. A large peer panel cannot silently supply ordinary confidence.
    with pytest.raises(ModelUnavailable, match='insufficient history'):
        forecast(target,future(target,7),'pooled_ridge',panel=(established,))
    with pytest.raises(ModelUnavailable, match='insufficient history'):
        forecast(target,future(target,7),'tabular_mean',panel=(established,))


def test_mutable_model_alias_and_unqualified_runtime_migration_are_rejected():
    s = history([3.] * 70)
    for alias in ('foundation:latest', 'neural:latest', 'pooled_ridge@latest'):
        with pytest.raises(ModelUnavailable, match='unknown model'):
            forecast(s,future(s,7),alias)
    with pytest.raises(ModelUnavailable, match='config'):
        forecast(s,future(s,7),'pooled_ridge',{'model_version':'latest'})


@pytest.mark.parametrize('field,value', [
    ('future_roster', {'new-team':['person']}),
    ('future_covariates', {'headcount':[10,20]}),
    ('approval_probability', .9),
])
def test_unqualified_future_roster_covariates_and_approval_probability_rejected(field,value):
    s = history([3.] * 70)
    # Fixed historical panels do not implement dated reorganization scenarios
    # or learned effects from plan probabilities. Unknown inputs cannot vanish.
    with pytest.raises(ModelUnavailable,match='config'):
        forecast(s,future(s,7),'pooled_ridge',{field:value})
