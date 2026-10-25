"""Concrete final-review failures: identity, arithmetic, work bounds and isolation."""
from dataclasses import fields, replace
from datetime import timedelta
from decimal import Decimal, localcontext, ROUND_DOWN, ROUND_UP
from unittest.mock import patch

import pytest

from forecasting.contracts import ContractError, digest
from forecasting.joint import SeriesAxis
from forecasting.joint_service import _summaries
from forecasting.snapshot import Snapshot, DailyValue
from forecasting.state import ExposureSpell, HurdleParameters, ExecutionMark, generate_recurrent_scenarios
from test_joint_service import fixture, axes, commercial_options
from test_state import ORIGIN, DATES, TARGET, spell, event


def snapshot_with(snapshot, **changes):
    body = {f.name: getattr(snapshot, f.name) for f in fields(snapshot)
            if f.name not in {'snapshot_id', 'schema_version'}}
    body.update(changes)
    return Snapshot(digest(body), **body)


@pytest.mark.parametrize('ready,lag', [(True, 0), (False, 0), (True, 2), (False, 2)])
def test_multi_axis_actuals_share_forecast_entity_even_when_unavailable(tmp_path, ready, lag):
    service, snapshot, request = fixture(tmp_path, output='full_period', lag=lag)
    dimensions = (SeriesAxis('team:a', 'input', 'model', 'pool', 'tokens'),
                  SeriesAxis('team:a', 'output', 'model', 'pool', 'tokens'))
    mapping = {'a': dimensions[0].axis_id, 'b': dimensions[1].axis_id}
    snapshot = snapshot_with(snapshot, ready=ready,
        daily=tuple(replace(row, entity_id=mapping[row.entity_id]) for row in snapshot.daily))
    request = replace(request, period_start=snapshot.history_start)
    supplement = None
    if lag:
        daily = tuple(DailyValue(dim.axis_id, snapshot.history_end+timedelta(days=i), Decimal(v))
                      for dim,v in zip(dimensions,(2,3)) for i in range(lag))
        supplement = snapshot_with(snapshot, history_start=snapshot.history_end,
            history_end=request.as_of.date(), daily=daily,
            company_daily=tuple(DailyValue('company', snapshot.history_end+timedelta(days=i), Decimal(5)) for i in range(lag)))
    result = service.run_joint(request, snapshot, allowed_sources={'usage'}, axes=dimensions,
        n_paths=2, max_history_lag_days=lag, recorded_supplement=supplement)
    assert set(result['entities']) == {'team:a'}
    assert Decimal(result['entities']['team:a']['recorded']) == (310 if lag else 300)
    assert result['entities']['team:a']['future'] == ('20' if ready else None)
    assert Decimal(result['result']['recorded']) == (310 if lag else 300)
    if ready:
        assert Decimal(result['usage']['mean']) == (330 if lag else 320)


@pytest.mark.parametrize('hostile', [False, True])
def test_native_and_money_excess_are_context_independent(tmp_path, hostile):
    service, snapshot, request = fixture(tmp_path)
    options = dict(axes=axes(), allowed_sources={'usage'}, n_paths=2, threshold=Decimal('19.99'),
        commercial_options=commercial_options(request), monetary_threshold=Decimal('22.99'))
    normal = service.run_joint(request, snapshot, **options)
    with localcontext() as context:
        context.prec = 3
        context.rounding = ROUND_UP
        if hostile:
            context.Emax, context.Emin, context.clamp = 1, -1, 1
            for signal in context.traps: context.traps[signal] = True
        changed = service.run_joint(request, snapshot, **options)
    assert changed['usage']['expected_excess'] == '0.01'
    assert changed['monetary']['expected_excess'] == '0.01'
    assert changed['artifact_id'] == normal['artifact_id']


def test_rational_projection_has_fixed_rounding_exponents_and_traps():
    for rounding in (ROUND_DOWN, ROUND_UP):
        with localcontext() as context:
            context.prec, context.rounding, context.Emax, context.Emin, context.clamp = 3, rounding, 1, -1, 1
            for signal in context.traps: context.traps[signal] = True
            summary = _summaries((0, 1, 1), (1/3,)*3, (.5,), None, .95)
            large = _summaries((Decimal('1e100'),), (1,), (.5,), Decimal('1e100'), .95)
        assert summary['mean'] == '0.' + '6'*49 + '7'
        assert Decimal(large['mean']) == Decimal('1e100')


def test_effective_structural_population_obeys_service_limit(tmp_path):
    service, snapshot, request = fixture(tmp_path)
    service.max_entities = 2
    exposures = tuple(ExposureSpell('access-'+p, p, 'c', request.period_start, request.period_end,
                                    request.as_of, True) for p in ('x', 'y', 'z'))
    with pytest.raises(ValueError, match='population|entity'):
        service.run_joint(request, snapshot, allowed_sources={'usage'}, n_paths=1,
            state_inputs={'exposures': exposures, 'events': (),
                          'parameters': (HurdleParameters('c', 1, marks=(ExecutionMark(1),)),)})


def recurrent(**changes):
    options = dict(exposures=(spell(access=True),), events=(),
        parameters=(HurdleParameters('team', 1, marks=(ExecutionMark(1),)),),
        as_of=ORIGIN, dates=DATES, path_count=1, seed=0, target=TARGET, snapshot_id='s')
    options.update(changes)
    return generate_recurrent_scenarios(**options)


@pytest.mark.parametrize('changes', [
    {'path_count': 10**9},
    {'path_count': 100, 'parameters': (HurdleParameters('team', 1, (10000,), (ExecutionMark(1),)),)},
    {'path_count': 10000, 'parameters': (HurdleParameters('team', 0, marks=tuple(ExecutionMark(1, billed_configuration=str(i)) for i in range(67))),)},
    {'path_count': 10000, 'exposures': (spell(access=False),),
     'events': tuple(event('start'+str(i), 'root_start', root=str(i)) for i in range(4)),
     'continuation_marks': (ExecutionMark(1),)},
])
def test_structural_bounds_reject_before_axis_or_rng_allocations(changes):
    # Sentinels prevent an accidental giant allocation on the red version.
    with patch('forecasting.joint.SeriesAxis', side_effect=AssertionError('axis allocation reached')), \
         patch('forecasting.state.random.Random', side_effect=AssertionError('rng allocation reached')):
        with pytest.raises(ValueError, match='bound|budget'):
            recurrent(**changes)


def test_finite_history_overflow_preserves_actuals_but_bad_axes_reject(tmp_path):
    service, snapshot, request = fixture(tmp_path, output='full_period')
    snapshot = snapshot_with(snapshot,
        daily=tuple(replace(row, value=Decimal('1e308')) for row in snapshot.daily),
        company_daily=tuple(replace(row, value=Decimal('2e308')) for row in snapshot.company_daily))
    request = replace(request, period_start=snapshot.history_start,
        period_end=request.period_start+timedelta(days=1), model='last_observation')
    result = service.run_joint(request, snapshot, allowed_sources={'usage'}, axes=axes(), n_paths=1)
    assert Decimal(result['result']['recorded']) == Decimal('1.2e310')
    assert result['result']['future'] is None
    assert result['usage']['qualification']['status'] == 'unavailable'
    assert any('numerical' in reason for reason in result['result']['limitations'])
    with pytest.raises(ContractError):
        service.run_joint(request, snapshot, allowed_sources={'usage'}, axes=(axes()[0], axes()[0]), n_paths=1)


def test_structural_generated_overflow_degrades_but_malformed_state_rejects(tmp_path):
    service, snapshot, request = fixture(tmp_path, output='full_period')
    request = replace(request, period_start=snapshot.history_start)
    exposure = ExposureSpell('a', 'a', 'c', request.as_of.date(), request.period_end, request.as_of, True)
    inputs = dict(exposures=(exposure,), events=(), parameters=(HurdleParameters('c', 1, marks=(ExecutionMark(1e308),)),))
    result = service.run_joint(request, snapshot, allowed_sources={'usage'}, n_paths=1, state_inputs=inputs)
    assert Decimal(result['result']['recorded']) == 300
    assert result['result']['future'] is None
    with pytest.raises(ValueError, match='cohort'):
        service.run_joint(request, snapshot, allowed_sources={'usage'}, n_paths=1,
            state_inputs=dict(inputs, parameters=(HurdleParameters('other', 1),)))


def test_small_structural_budgets_include_effective_days_and_continuations(monkeypatch):
    # One accessible day * two proposals plus one ongoing root * three days = 5.
    monkeypatch.setattr('forecasting.state.MAX_RECURRENT_ROOT_WORK', 5)
    exposure = replace(spell(access=True), end=DATES[1])
    options = dict(exposures=(exposure,), events=(event('start', 'root_start'),),
        parameters=(HurdleParameters('team', 1, (2,), (ExecutionMark(1),)),),
        continuation_marks=(ExecutionMark(3),))
    result = recurrent(**options)
    assert len(result.paths[0].roots) == 2
    assert result.bundle.totals() == (11.,)
    with pytest.raises(ValueError, match='root work'):
        recurrent(**dict(options, path_count=2))
    # Inaccessible people generate no new roots, even with large count support.
    result = recurrent(exposures=(spell(access=False),),
        parameters=(HurdleParameters('team', 1, (10000,), (ExecutionMark(1),)),))
    assert result.paths[0].roots == () and result.bundle.totals() == (0.,)


def test_small_path_and_multiconfiguration_cell_boundaries(monkeypatch):
    monkeypatch.setattr('forecasting.state.MAX_RECURRENT_PATHS', 2)
    monkeypatch.setattr('forecasting.state.MAX_RECURRENT_CELLS', 12)
    marks = (ExecutionMark(1, billed_configuration='one'), ExecutionMark(1, billed_configuration='two'))
    result = recurrent(path_count=2, parameters=(HurdleParameters('team', 1, marks=marks),))
    assert len(result.paths) == 2 and len(result.bundle.axes) == 2
    assert result.bundle.totals() == (3., 3.)
    with pytest.raises(ValueError, match='cell resource budget'):
        recurrent(path_count=2, parameters=(HurdleParameters('team', 1, marks=marks+(ExecutionMark(1, billed_configuration='three'),)),))
    with pytest.raises(ValueError, match='bounded positive path count'):
        recurrent(path_count=3)


def test_exact_money_helpers_ignore_hostile_traps_and_preserve_digits():
    from decimal import ROUND_FLOOR
    from forecasting.contracts import exact_sum, exact_product
    with localcontext() as context:
        context.prec, context.rounding, context.Emax, context.Emin = 3, ROUND_FLOOR, 1, -1
        for signal in context.traps: context.traps[signal] = True
        total = exact_sum((Decimal('1e100'), Decimal('-1e100')))
        product = exact_product(Decimal('123456789012345678901234567890.01'), Decimal('100.01'))
    assert total == 0 and not total.is_signed()
    assert product == Decimal('12346913469124691346912469134679.9001')


def test_derived_overflow_is_typed_separately_from_invalid_bundle_contracts():
    from forecasting.joint import DerivedNumericalUnavailable
    from test_joint import bundle
    with pytest.raises(DerivedNumericalUnavailable, match='nonfinite derived total'):
        bundle(values=(((1e308, 1e308), (0., 0.)), ((0., 0.), (0., 0.))))
    for changes in ({'weights': (1e308, 1e308)},
                    {'values': (((float('inf'), 0.), (0., 0.)), ((0., 0.), (0., 0.)))}):
        with pytest.raises(ContractError) as caught:
            bundle(**changes)
        assert not isinstance(caught.value, DerivedNumericalUnavailable)
