"""Regression coverage for financial identity and context replay boundaries."""
from dataclasses import FrozenInstanceError, replace
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from forecasting import context
from forecasting.contracts import ContractError, ForecastResult, Target, digest

ORIGIN = datetime(2026, 10, 1, tzinfo=timezone.utc)
VALUES = ((date(2026, 10, 1), Decimal('10')),)


def monetary_target():
    return Target('cost', 'tenant', 'provider_reported_cost', 'USD', 'USD',
                  ('billing',), ('variable',))


def usage_target():
    return Target('usage', 'tenant', 'metered_usage', 'tokens', None,
                  ('meter',), ('input',), support='nonnegative')


@pytest.mark.parametrize('field,value', [
    ('target_id', 12), ('tenant_id', True), ('unit', 12), ('target_id', '  '),
    ('additive', 'false'), ('additive', 0), ('additive', None),
    ('sources', 'abc'), ('categories', 'abc'),
    ('sources', (12,)), ('categories', (12,)),
    ('sources', ('',)), ('categories', ('  ',)),
    ('reporting_timezone', 12), ('currency', 123), ('currency', '123'),
    ('source_partition_policy', 12), ('source_partition_policy', ''),
    ('attribution_version', 12), ('version', 1), ('measure', []),
])
def test_target_rejects_malformed_values_at_both_boundaries(field, value):
    direct = dict(monetary_target().__dict__, **{field: value})
    serialized = dict(monetary_target().to_dict(), **{field: value})
    for construct, payload in ((Target, direct), (Target.from_dict, serialized)):
        with pytest.raises(ContractError):
            if construct is Target:
                construct(**payload)
            else:
                construct(payload)


@pytest.mark.parametrize('target', [monetary_target(), usage_target(),
    replace(monetary_target(), additive=False, source_partition_policy='verified-v1')])
def test_valid_targets_preserve_native_types_and_round_trip(target):
    decoded = Target.from_dict(target.to_dict())
    assert decoded == target
    assert type(decoded.additive) is bool
    assert isinstance(decoded.sources, tuple)


@pytest.mark.parametrize('basis', ['billed', 'cash'])
def test_usage_is_incurred_physical_flow(basis):
    with pytest.raises(ContractError, match='incurred'):
        replace(usage_target(), period_basis=basis)
    with pytest.raises(ContractError, match='incurred'):
        Target.from_dict(dict(usage_target().to_dict(), period_basis=basis))


@pytest.mark.parametrize('fixed', [Decimal('100'), Decimal('0')])
def test_usage_result_rejects_monetary_fixed_obligations(fixed):
    with pytest.raises(ContractError, match='fixed'):
        ForecastResult('result', 'request', usage_target(), 'snapshot', ORIGIN,
                       date(2026, 10, 1), date(2026, 11, 1), Decimal('0'),
                       Decimal('0'), Decimal('10'), fixed, 'ready', 'mean', 'point')


def add_event(ledger, event_id, status='approved', execution='planned', supersedes=()):
    text = 'The project has a launch plan.'
    ledger.add_source(context.SourceDocument('tenant', event_id, 'v1', text, ORIGIN), ('finance',))
    ref = context.Citation(event_id, 'v1', 0, len(text), text)
    event = context.ContextEvent('tenant', event_id, event_id, 'project', 'launch',
                                 'launch', status, ORIGIN, (ref,), supersedes,
                                 approval_verified=True, execution_status=execution)
    ledger.add_event(event)
    return event


@pytest.mark.parametrize('status,execution', [('cancelled', 'cancelled'),
                                            ('approved', 'cancelled'),
                                            ('cancelled', 'unknown')])
def test_equal_payload_cancellation_conflicts_with_active_assertion(status, execution):
    ledger = context.ContextLedger()
    add_event(ledger, 'active')
    add_event(ledger, 'cancelled', status, execution)
    assert ledger.resolve('tenant', 'finance', ORIGIN).conflicts == (('active', 'cancelled'),)


def test_equal_payload_approved_and_observed_assertions_are_compatible():
    ledger = context.ContextLedger()
    add_event(ledger, 'approved')
    add_event(ledger, 'observed', 'observed', 'observed')
    assert ledger.resolve('tenant', 'finance', ORIGIN).conflicts == ()


def test_revoked_superseded_metadata_is_hidden_without_resurrection():
    ledger = context.ContextLedger()
    add_event(ledger, 'private-project')
    add_event(ledger, 'cancel', 'cancelled', 'cancelled', ('private-project',))
    ledger.set_access('tenant', 'private-project', 'v1', ())
    result = ledger.resolve('tenant', 'finance', ORIGIN)
    assert result.superseded == ()
    assert [event.event_id for event in result.events] == ['cancel']
    assert result.events[0].supersedes == ()
    ledger.set_access('tenant', 'cancel', 'v1', ())
    result = ledger.resolve('tenant', 'finance', ORIGIN)
    assert result.events == ()
    assert result.superseded == ()
    assert result.restricted_event_count == 1


def scenario_types():
    assert hasattr(context, 'WorkloadBaseline'), 'missing immutable baseline-bound scenario API'
    return context.WorkloadBaseline, context.WorkloadAdjustment, context.apply_workload_adjustment


def test_bound_scenario_replay_cannot_compound_the_same_workload_assumption():
    Baseline, Adjustment, apply = scenario_types()
    baseline = Baseline('forecast-artifact', usage_target(), ORIGIN, VALUES)
    assumption = context.NumericAssumption('finance', 'Double future workload', Decimal('2'))
    adjustment = Adjustment('adjustment-1', 'assumption-1', assumption)
    kwargs = {'adjustment': adjustment, 'configured_mappings': ('user_workload_multiplier',)}
    result = apply(baseline, **kwargs)
    assert result.values == ((date(2026, 10, 1), Decimal('20')),)
    assert baseline.values == VALUES
    assert result.adjustments == (adjustment,)
    assert result.baseline.baseline_id == 'forecast-artifact'
    assert apply(baseline, **kwargs).scenario_id == result.scenario_id
    assert result.scenario_id == digest(result)
    with pytest.raises(ValueError, match='already applied'):
        apply(result, **kwargs)
    with pytest.raises(ValueError, match='already applied'):
        apply(result, adjustment=replace(adjustment, adjustment_id='renamed'),
              configured_mappings=('user_workload_multiplier',))
    with pytest.raises(FrozenInstanceError):
        baseline.baseline_id = 'other'
    other = replace(baseline, values=((date(2026, 10, 1), Decimal('11')),))
    assert apply(other, **kwargs).scenario_id != result.scenario_id
    assert replace(result, adjustments=(replace(adjustment, assumption_id='different'),)).scenario_id != result.scenario_id


def test_bound_scenario_rejects_untyped_baselines_and_missing_material_ids():
    Baseline, Adjustment, apply = scenario_types()
    assumption = context.NumericAssumption('finance', 'Double workload', Decimal('2'))
    with pytest.raises(ValueError):
        Baseline('forecast', monetary_target(), ORIGIN, VALUES)
    with pytest.raises(ValueError):
        Baseline('', usage_target(), ORIGIN, VALUES)
    with pytest.raises(ValueError):
        Adjustment('adjustment', '', assumption)
    with pytest.raises(ValueError):
        apply(VALUES, adjustment=Adjustment('adjustment', 'assumption', assumption),
              configured_mappings=('user_workload_multiplier',))


@pytest.mark.parametrize('field', ['supplied_by', 'rationale'])
def test_numeric_assumption_identity_cannot_contain_mutable_values(field):
    args = dict(supplied_by='finance', rationale='Double workload', multiplier=Decimal('2'))
    args[field] = ['mutable']
    with pytest.raises(ValueError):
        context.NumericAssumption(**args)


def test_bound_scenario_keeps_disclosure_immutable():
    Baseline, Adjustment, apply = scenario_types()
    result = apply(Baseline('forecast', usage_target(), ORIGIN, VALUES),
                   adjustment=Adjustment('adjustment', 'assumption',
                       context.NumericAssumption('finance', 'Double workload', Decimal('2'))),
                   configured_mappings=('user_workload_multiplier',))
    with pytest.raises(ValueError):
        replace(result, limitations=['mutable'])


@pytest.mark.parametrize('operation', ['product', 'sum'])
def test_exact_arithmetic_ignores_ambient_exponent_limits(operation):
    from decimal import Overflow, localcontext
    from forecasting.contracts import exact_product, exact_sum
    with localcontext() as current:
        current.Emax = 20
        current.traps[Overflow] = False
        if operation == 'product':
            actual = exact_product(Decimal('1e20'), Decimal('1e20'))
            assert actual == Decimal('1e40')
        else:
            actual = exact_sum((Decimal('9e20'), Decimal('9e20')))
            assert actual == Decimal('1.8e21')


@pytest.mark.parametrize('operation', ['product', 'sum'])
def test_exact_arithmetic_never_silently_underflows(operation):
    from decimal import localcontext
    from forecasting.contracts import exact_product, exact_sum
    with localcontext() as current:
        current.Emin = -20
        current.prec = 2
        current.clamp = 1
        if operation == 'product':
            actual = exact_product(Decimal('1e-20'), Decimal('1e-40'))
        else:
            actual = exact_sum((Decimal('1e-60'),))
        assert actual == Decimal('1e-60')
        assert current.Emin == -20
        assert current.prec == 2
        assert current.clamp == 1


def test_bound_scenario_keeps_values_and_identity_under_changed_decimal_context():
    from decimal import localcontext
    Baseline, Adjustment, apply = scenario_types()
    result = apply(Baseline('forecast', usage_target(), ORIGIN,
                           ((date(2026, 10, 1), Decimal('1e-20')),)),
                   adjustment=Adjustment('adjustment', 'assumption',
                       context.NumericAssumption('finance', 'Tiny workload', Decimal('1e-40'))),
                   configured_mappings=('user_workload_multiplier',))
    initial_id = result.scenario_id
    assert result.values == ((date(2026, 10, 1), Decimal('1e-60')),)
    with localcontext() as current:
        current.Emin = -20
        assert result.scenario_id == initial_id
        assert result.values == ((date(2026, 10, 1), Decimal('1e-60')),)
