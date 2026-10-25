"""Joint laws preserve common historical blocks, semantics, and path identities."""
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from forecasting.contracts import Target
from forecasting.models import Series
from forecasting.joint import (
    JointUnavailable, OutputQualification, ProcedureSpec, ScenarioBundle,
    ScenarioSpec, SeriesAxis, fit_joint_blocks,
)


def target():
    return Target('usage', 'tenant', 'metered_usage', 'tokens', None,
                  ('source',), ('usage',), support='nonnegative')


def axis(entity='a', **changes):
    return replace(SeriesAxis(entity, 'input', 'model-v1', 'pool', 'tokens'), **changes)


def bundle(**changes):
    defaults = dict(target=target(), snapshot_id='snapshot',
                    as_of=datetime(2024, 1, 5, tzinfo=timezone.utc),
                    dates=(date(2024, 1, 5), date(2024, 1, 6)),
                    axes=(axis('a'), axis('b')), path_ids=('p0', 'p1'),
                    values=(((0., 100.), (100., 0.)), ((100., 0.), (0., 100.))),
                    weights=(.5, .5), procedure=ProcedureSpec('fixture'))
    defaults.update(changes)
    return ScenarioBundle(**defaults)


def histories(values=(1, 3, 2, 7, 4, 9, 6, 10, 8, 12, 11, 15)):
    dates = tuple(date(2024, 1, 1) + timedelta(days=i) for i in range(len(values)))
    return (Series('a', dates, values), Series('b', dates, tuple(2*x for x in values)))


def fit(hist=None, **changes):
    hist = histories() if hist is None else hist
    origin = hist[0].dates[-1] + timedelta(days=1) if hist else date(2024,1,13)
    defaults = dict(target=target(), snapshot_id='snapshot',
                    as_of=datetime.combine(origin, datetime.min.time(), timezone.utc),
                    dates=(origin, origin + timedelta(days=1)), axes=(axis('a'), axis('b')),
                    n_paths=30, seed=17, baseline='last_observation', min_blocks=3)
    defaults.update(changes)
    return fit_joint_blocks(hist, **defaults)


def test_totals_quantiles_and_entity_aggregation_preserve_same_paths():
    b = bundle(axes=(axis('a'), axis('a', meter='output')))
    assert b.totals() == (200., 200.)
    assert b.quantile(.95) == 200.  # sum of daily marginal q95 would be 400
    derived = b.aggregate_entities()
    assert derived.values == (((100., 100.),), ((100., 100.),))
    assert derived.path_ids == b.path_ids and derived.weights == b.weights
    assert derived.parent_ids == (b.bundle_id,)
    assert derived.totals() == b.totals()


@pytest.mark.parametrize('changes', [
    {'axes': (axis(), axis('b', unit='requests'))},
    {'axes': (axis(), axis())},
    {'dates': (date(2024, 1, 5), date(2024, 1, 7))},
    {'as_of': datetime(2024, 1, 6, tzinfo=timezone.utc)},
    {'values': (((1.,), (2.,)), ((1.,), (2.,)))},
    {'values': (((-1., 0.), (0., 0.)), ((0., 0.), (0., 0.)))},
    {'values': (((1e308, 1e308), (0., 0.)), ((0., 0.), (0., 0.)))},
    {'weights': (.4, .4)},
])
def test_invalid_units_axes_dates_origins_support_and_derived_overflow_rejected(changes):
    with pytest.raises(ValueError):
        bundle(**changes)


def test_ids_bind_config_snapshot_scenario_and_nested_inputs_are_immutable():
    config = {'nested': {'window': [2, 3]}}
    p = ProcedureSpec('test', config=config)
    b = bundle(procedure=p)
    config['nested']['window'].append(4)
    assert p.config['nested']['window'] == (2, 3)
    with pytest.raises(TypeError):
        p.config['nested']['x'] = 1
    assert len({b.bundle_id, replace(b, snapshot_id='other').bundle_id,
                replace(b, procedure=ProcedureSpec('test', config={'window': 4})).bundle_id,
                replace(b, scenario=ScenarioSpec('stress')).bundle_id}) == 4


def test_sensitivity_has_no_probability_weights_or_quantile():
    with pytest.raises(ValueError):
        bundle(scenario=ScenarioSpec('stress', 'sensitivity'))
    b = bundle(scenario=ScenarioSpec('stress', 'sensitivity'), weights=())
    with pytest.raises(ValueError):
        b.quantile(.95)
    assert b.totals() == (200., 200.)


def test_money_bundle_never_roundtrips_through_float():
    money = Target('cost', 'tenant', 'contract_priced_estimate', 'USD', 'USD',
                   ('source',), ('cost',))
    large = Decimal('1000000000000000000000000000000.000000000001')
    values = (((large, Decimal('-1')),),)
    b = bundle(target=money, axes=(axis(unit='USD'),), path_ids=('p',),
               values=values, weights=(1.,))
    assert b.totals() == (Decimal('999999999999999999999999999999.000000000001'),)
    assert isinstance(b.quantile(.9), Decimal)
    with pytest.raises(ValueError):
        replace(b, values=(((1., 2.),),))


def test_fitted_residual_blocks_are_honest_shared_and_repeatable():
    b = fit()
    assert isinstance(b, ScenarioBundle)
    assert b == fit()
    assert b.bundle_id != fit(seed=18).bundle_id
    assert b.procedure.procedure_id == 'joint_residual_blocks'
    assert b.support_transform == 'clip_nonnegative'
    assert b.procedure.config['block_count'] == 5
    # Rolling last-observation prefixes: residual pair is (v[t]-v[t-1],v[t+1]-v[t-1]).
    # Actual starts are 1,3,5,7,9; current last observation is 15.
    allowed = {(17.,16.), (20.,17.), (20.,17.), (19.,17.), (19.,18.)}
    assert all(tuple(p[0]) in allowed for p in b.values)
    assert all(tuple(2*x for x in p[0]) == p[1] for p in b.values)
    assert len(set(p[0] for p in b.values)) > 1
    assert all(q.status == 'available_assumption_conditional' for q in b.qualifications)
    assert b.bundle_id != fit(axes=(axis('a', configuration='v2'), axis('b'))).bundle_id


def test_projection_is_declared_and_preserves_shared_draws():
    b = fit(histories((100, 0, 0, 100, 0, 0, 100, 0, 0)))
    assert b.procedure.config['projection_count'] > 0
    assert all(x >= 0 for p in b.values for a in p for x in a)
    assert b.support_transform == 'clip_nonnegative'


def test_direct_block_fallback_is_a_distinct_fitted_law_and_insufficient_is_typed():
    b = fit(histories((1, 2, 3, 4, 5, 6)), baseline='trailing_mean', baseline_config={'window':7})
    assert b.procedure.procedure_id == 'joint_direct_blocks'
    assert set(p[0] for p in b.values).issubset({(1.,2.),(3.,4.),(5.,6.)})
    unavailable = fit(histories((1, 2, 3, 4, 5, 6)), baseline='trailing_mean',
                      baseline_config={'window':7}, allow_direct_fallback=False)
    assert isinstance(unavailable, JointUnavailable)
    assert isinstance(fit(histories((1, 2))), JointUnavailable)


def test_future_history_misalignment_and_unknown_axes_cannot_enter_fit():
    hist = histories()
    with pytest.raises(ValueError):
        fit(hist, as_of=datetime(2024,1,10,tzinfo=timezone.utc))
    with pytest.raises(ValueError):
        fit((hist[0], Series('b', hist[1].dates[1:], hist[1].values[1:])))
    with pytest.raises(ValueError):
        fit(axes=(axis('x'), axis('b')))


def test_output_qualification_is_independent_by_output():
    b = bundle(qualifications=(OutputQualification('tokens', 'available_assumption_conditional'),
                               OutputQualification('cash', 'unavailable', ('missing terms',))))
    assert b.qualifications[0].status != b.qualifications[1].status


def test_cold_start_returns_typed_unavailable():
    result = fit(hist=(), as_of=datetime(2024,1,13,tzinfo=timezone.utc),
                 dates=(date(2024,1,13),date(2024,1,14)))
    assert isinstance(result, JointUnavailable)


def test_configuration_rejects_nonfinite_decimal():
    with pytest.raises(ValueError):
        ProcedureSpec('invalid', config={'scale': Decimal('NaN')})


def test_explicit_delayed_history_preserves_actual_origin_and_joint_bridge():
    hist = histories(tuple(range(1, 31)))
    b = fit(hist, as_of=datetime(2024,2,1,tzinfo=timezone.utc),
            dates=(date(2024,2,1), date(2024,2,2)), history_end=date(2024,1,31), max_history_lag_days=1)
    assert b.as_of == datetime(2024,2,1,tzinfo=timezone.utc)
    assert b.dates == (date(2024,2,1), date(2024,2,2))
    assert set(p[0] for p in b.values) == {(32.,33.)}
    assert all(p[1] == (64.,66.) for p in b.values)
    assert b.procedure.config['modeled_dates'] == (date(2024,1,31),date(2024,2,1),date(2024,2,2))
    with pytest.raises(ValueError):
        fit(hist, as_of=datetime(2024,2,1,tzinfo=timezone.utc),
            dates=(date(2024,2,1),date(2024,2,2)))


def test_independently_generated_laws_do_not_reuse_global_path_ids():
    first, second = fit(seed=1), fit(seed=2)
    assert not set(first.path_ids).intersection(second.path_ids)
    assert not set(first.path_ids).intersection(fit(seed=1, snapshot_id='other').path_ids)


@pytest.mark.parametrize('lag', [-1, 31, True])
def test_bridge_rejects_invalid_lag_policy(lag):
    with pytest.raises(ValueError):
        fit(max_history_lag_days=lag)


def test_company_daily_law_is_derived_on_same_path_ids():
    original = bundle()
    company = original.aggregate_company()
    assert company.values == (((100.,100.),), ((100.,100.),))
    assert company.path_ids == original.path_ids
    assert company.parent_ids == (original.bundle_id,)
    assert company.totals() == original.totals()


def test_mixed_evidence_is_preserved_but_cannot_be_empirically_promoted():
    b = bundle(evidence_class='mixed')
    assert b.evidence_class == 'mixed'
    with pytest.raises(ValueError):
        replace(b, qualifications=(OutputQualification('native_usage', 'empirically_qualified', evidence_scope='enterprise', evidence_ids=('eval',)),))


def test_empirical_qualification_requires_evidence_and_public_trace_is_not_enterprise():
    with pytest.raises(ValueError):
        OutputQualification('native_usage', 'empirically_qualified')
    q = OutputQualification('native_usage', 'empirically_qualified',
                            evidence_scope='public_trace', evidence_ids=('evaluation-123',))
    b = bundle(evidence_class='public_trace', qualifications=(q,))
    assert b.qualifications[0].evidence_ids == ('evaluation-123',)
    with pytest.raises(ValueError):
        replace(b, qualifications=(replace(q, evidence_scope='enterprise'),))


@pytest.mark.parametrize('n,q,want', [(10,.8,8.), (10,.9,9.), (30,.9,27.)])
def test_equal_weight_quantiles_select_exact_cdf_boundary(n, q, want):
    b = bundle(axes=(axis(),), dates=(date(2024,1,5),),
               path_ids=tuple(str(i) for i in range(n)),
               values=tuple(((float(i),),) for i in range(1,n+1)),
               weights=(1./n,)*n)
    assert b.quantile(q) == want


def test_unequal_weight_quantiles_distinguish_boundary_from_next_atom():
    b = bundle(axes=(axis(),), dates=(date(2024,1,5),),
               path_ids=('1','2','3','4'),
               values=(((1.,),),((2.,),),((3.,),),((4.,),)),
               weights=(.3,.4,.1,.2))
    assert b.quantile(.8) == 3.
    assert b.quantile(.8000000000000002) == 4.


def test_boundary_quantile_preserves_exact_decimal_money():
    money = Target('cost', 'tenant', 'contract_priced_estimate', 'USD', 'USD',
                   ('source',), ('cost',))
    b = bundle(target=money, axes=(axis(unit='USD'),), dates=(date(2024,1,5),),
               path_ids=tuple(str(i) for i in range(10)), weights=(.1,)*10,
               values=tuple(((Decimal(str(i)+'.000000000000000000000000001'),),) for i in range(1,11)))
    assert b.quantile(.8) == Decimal('8.000000000000000000000000001')


@pytest.mark.parametrize('typed,string', [
    (Decimal('1.5'), '1.5'),
    (date(2024,1,1), '2024-01-01'),
    (datetime(2024,1,1,tzinfo=timezone.utc), '2024-01-01T00:00:00+00:00'),
])
def test_configuration_identity_preserves_types_inside_nested_containers(typed, string):
    first = ProcedureSpec('typed', config={'nested': [{'value': typed}]})
    second = ProcedureSpec('typed', config={'nested': [{'value': string}]})
    assert first.identity != second.identity
    assert bundle(procedure=first).bundle_id != bundle(procedure=second).bundle_id
    # Keep external financial/date serialization compatible.
    assert first.to_dict() == second.to_dict()
