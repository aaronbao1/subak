"""Audit reproductions exercise durable replay and public numerical boundaries."""
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, localcontext
from itertools import permutations

import pytest

from forecasting.consumers import FinanceError, forecast_evidence
from forecasting.context import ContextLedger
from forecasting.contracts import digest
from forecasting.evaluation import point_metrics, interval_metrics, quantile_metrics
from forecasting.integration import run_demo
from forecasting.joint import JointUnavailable
from forecasting.models import ModelUnavailable, Series, forecast
from forecasting.snapshot import Coverage, Snapshot, DailyValue, build_snapshot
from forecasting.source_store import SourceStore
from forecasting.store import ArtifactStore, AccessDenied
from forecasting.uncertainty import CalibrationPoint, cumulative_interval
from test_context import event, T as CONTEXT_TIME
from test_ingestion import obs, ext, T
from test_joint import fit, histories
from test_service_models import fixture
from test_snapshot import target


@pytest.mark.parametrize('order', tuple(permutations((0, 1, 2))))
def test_coverage_replay_preserves_earlier_finality_transitions(tmp_path, order):
    store = SourceStore(tmp_path/'sources.sqlite')
    original = ext([obs()])
    start, end = date(2026, 9, 1), date(2026, 9, 2)
    for offset in order:
        stamp = T + timedelta(days=offset)
        delivery = replace(original, receipt=replace(original.receipt, fetched_at=stamp))
        coverage = Coverage('billing', start, end, 'complete',
                            'finalized' if offset == 0 else 'provisional', stamp)
        store.acquire(delivery, (coverage,), evidence_class='authorized_local_file', adapter='normalized')
    ledger, coverage = store.load('org', 'billing', evidence_class='authorized_local_file', adapter='normalized')
    early = build_snapshot(target(), ledger, T, start, end, coverage=coverage)
    later = build_snapshot(target(), ledger, T+timedelta(days=1), start, end, coverage=coverage)
    assert early.ready is True
    assert later.ready is False
    assert 'maturity_provisional:billing:2026-09-01' in later.limitations


def test_delayed_same_time_coverage_conflict_rejects_atomically(tmp_path):
    store = SourceStore(tmp_path/'sources.sqlite')
    original = ext([obs()])
    base = Coverage('billing', date(2026, 9, 1), date(2026, 9, 2), 'complete', 'finalized', T)
    for offset in (0, 2):
        delivery = replace(original, receipt=replace(original.receipt, fetched_at=T+timedelta(days=offset)))
        store.acquire(delivery, (base,), evidence_class='authorized_local_file', adapter='normalized')
    with pytest.raises(ValueError, match='conflicting coverage'):
        store.acquire(original, (replace(base, maturity='provisional'),),
                      evidence_class='authorized_local_file', adapter='normalized')


@pytest.mark.parametrize('nonnegative', (False, True))
def test_nonfinite_fitted_forecast_cannot_be_projected_to_zero(nonnegative):
    series = Series('a', tuple(date(2024, 1, 1)+timedelta(days=i) for i in range(4)), (0., 1e308, 0., 0.))
    with pytest.raises(ModelUnavailable, match='nonfinite|finite|numerical'):
        forecast(series, (date(2024, 1, 5),), 'local_linear_trend', {'nonnegative': nonnegative})


@pytest.mark.parametrize('baseline', ('pooled_ridge', 'tabular_mean'))
def test_learned_joint_baseline_reaches_later_eligible_origins(baseline):
    hist = histories(tuple(10.+i%7 for i in range(180)))
    origin = hist[0].dates[-1]+timedelta(days=1)
    result = fit(hist, dates=tuple(origin+timedelta(days=i) for i in range(30)),
                 baseline=baseline, baseline_config={'n_estimators': 2} if baseline == 'tabular_mean' else {},
                 n_paths=2, min_blocks=2, allow_direct_fallback=False)
    assert not isinstance(result, JointUnavailable)
    assert result.procedure.config['block_count'] >= 2
    assert result.procedure.config['allow_direct_fallback'] is False


def test_identical_authorized_reaffirmation_retires_predecessor_only():
    ledger = ContextLedger()
    event(ledger, canonical='initiative')
    event(ledger, 'forward', canonical='initiative')
    event(ledger, 'renewed', canonical='initiative', day=1, supersedes=('old',))
    current = ledger.resolve('northstar', 'finance', CONTEXT_TIME+timedelta(days=1))
    assert tuple(e.event_id for e in current.events) == ('renewed',)
    assert current.superseded == ('forward', 'old')
    ledger.set_access('northstar', 'renewed', 'v1', ())
    denied = ledger.resolve('northstar', 'finance', CONTEXT_TIME+timedelta(days=1))
    assert denied.events == () and denied.restricted_event_count == 1


@pytest.mark.parametrize('same_time', (False, True))
def test_later_canonical_cancellation_retires_earlier_authority_reaffirmation(same_time):
    ledger = ContextLedger()
    event(ledger, canonical='initiative')
    event(ledger, 'renewed', canonical='initiative', day=0 if same_time else 1, supersedes=('old',))
    event(ledger, 'forward', canonical='initiative', day=0 if same_time else 2)
    event(ledger, 'cancelled', value='cancel', status='cancelled',
          day=0 if same_time else 3, supersedes=('forward',))
    current = ledger.resolve('northstar', 'finance', CONTEXT_TIME+timedelta(days=4))
    assert tuple(e.event_id for e in current.events) == ('cancelled',)
    assert current.superseded == ('forward', 'old', 'renewed')
    assert current.conflicts == ()
    # A subsequently forwarded old statement does not reinstate its authority.
    event(ledger, 'stale-forward', canonical='initiative', day=4)
    assert tuple(e.event_id for e in ledger.resolve('northstar', 'finance',
                 CONTEXT_TIME+timedelta(days=4)).events) == ('cancelled',)
    # A new explicit authority action may reinstate the old value.
    event(ledger, 'reinstated', canonical='initiative', day=5, supersedes=('cancelled',))
    reinstated = ledger.resolve('northstar', 'finance', CONTEXT_TIME+timedelta(days=5))
    assert tuple(e.event_id for e in reinstated.events) == ('reinstated',)


def test_demo_scenario_withdraws_with_its_material_forecast(tmp_path):
    report = run_demo(tmp_path)
    store = ArtifactStore(tmp_path/'forecasts.sqlite')
    store.revoke('northstar', report['forecast']['artifact_id'], reason='parent withdrawn')
    with pytest.raises(AccessDenied):
        store.get('northstar', report['scenario_artifact_id'], allowed_sources={'billing'})


def test_consumer_derives_bound_provenance_and_rejects_override(tmp_path):
    report = run_demo(tmp_path)
    payload = report['forecast']
    assert forecast_evidence(payload).provenance == 'synthetic_fixture'
    with pytest.raises(FinanceError, match='provenance'):
        forecast_evidence(payload, provenance='authorized_local_file')


def test_partial_incurred_gap_with_zero_late_is_not_complete(tmp_path):
    service, snap, request = fixture(tmp_path, [5.]*100)
    origin = request.as_of+timedelta(days=2)
    body = {k: v for k, v in vars(snap).items() if k not in {'snapshot_id', 'schema_version'}}
    body['as_of'] = origin
    delayed = Snapshot(digest(body), **body)
    gap = dict(body, history_start=snap.history_end, history_end=origin.date(),
               daily=(DailyValue('team', snap.history_end, Decimal(5)),),
               company_daily=(DailyValue('company', snap.history_end, Decimal(5)),),
               ready=False, limitations=('coverage_partial:billing',))
    supplement = Snapshot(digest(gap), **gap)
    request = replace(request, as_of=origin, period_start=snap.history_start,
                      period_end=origin.date()+timedelta(days=7), output='full_period')
    payload = service.run(request, delayed, allowed_sources={'billing'}, max_history_lag_days=2,
                          recorded_supplement=supplement, late_estimate=Decimal(0))
    assert payload['result']['recorded'] == '505.0'
    assert payload['incurred_complete'] is False
    assert forecast_evidence(payload).complete is False


@pytest.mark.parametrize('top_level', ('absent', True, False))
def test_manifest_incurred_incompleteness_cannot_be_overridden(top_level):
    from test_consumers import payload
    value = payload()
    value['manifest']['incurred_complete'] = False
    if top_level != 'absent':
        value['incurred_complete'] = top_level
    assert forecast_evidence(value).complete is False


@pytest.mark.parametrize('bad', ('false', 0, 1, None))
def test_manifest_completeness_requires_boolean(bad):
    from test_consumers import payload
    value = payload()
    value['manifest']['incurred_complete'] = bad
    with pytest.raises(ValueError, match='bool|Bool'):
        forecast_evidence(value)


@pytest.mark.parametrize('bad', ('false', 0, 1, None))
def test_context_approval_requires_actual_boolean(bad):
    with pytest.raises(ValueError, match='bool|Bool'):
        event(ContextLedger(), verified=bad)


@pytest.mark.parametrize('method', ('grant_authority', 'set_dependency'))
@pytest.mark.parametrize('bad', ('false', 0, 1, None))
def test_finance_policy_flags_require_actual_booleans(tmp_path, method, bad):
    from test_consumers import setup
    store = setup(tmp_path)
    kwargs = {'policy_version': 'v', 'may_approve': bad} if method == 'grant_authority' else {'version': 'v', 'material': bad}
    with pytest.raises(ValueError, match='bool|Bool'):
        getattr(store, method)('actor', **kwargs)


@pytest.mark.parametrize('bad', ('false', 0, 1, None))
def test_joint_fallback_flag_requires_actual_boolean(bad):
    with pytest.raises(ValueError, match='bool|Bool'):
        fit(allow_direct_fallback=bad)


@pytest.mark.parametrize('bad', ('false', 0, 1, None))
def test_consumer_completeness_and_capability_flags_require_booleans(bad):
    from test_consumers import payload
    value = payload()
    value['capabilities']['point'] = bad
    with pytest.raises(ValueError, match='bool|Bool'):
        forecast_evidence(value)
    value['capabilities']['point'] = True
    value['incurred_complete'] = bad
    with pytest.raises(ValueError, match='bool|Bool'):
        forecast_evidence(value)


@pytest.mark.parametrize('bad', ('false', 0, 1, None))
@pytest.mark.parametrize('boundary', ('execution', 'finance', 'commercial'))
def test_other_material_completeness_flags_are_strict_booleans(boundary, bad):
    from forecasting.consumers import ForecastEvidence
    from test_state import event as execution_event
    from test_commercial import usage
    with pytest.raises(ValueError, match='bool|Bool'):
        if boundary == 'execution':
            execution_event('start', 'root_start', qualifying=bad)
        elif boundary == 'commercial':
            usage(complete=bad)
        else:
            ForecastEvidence('tenant', 'result', date(2026, 10, 1), date(2026, 11, 1),
                             'USD', ('variable',), bad, 'full_period', ())


def test_conformal_rank_uses_decimal_rendered_alpha_without_ambient_context():
    start = date(2024, 1, 1)
    cutoff = datetime(2025, 1, 1, tzinfo=timezone.utc)
    rows = tuple(CalibrationPoint(str(i), start+timedelta(days=i), start+timedelta(days=i+1),
                                 0, i+1, cutoff, 'p', 'company') for i in range(149))
    with localcontext() as context:
        context.prec = 2
        result = cumulative_interval(1000, rows, cutoff=cutoff, horizon=1,
                                     procedure_id='p', scope='company', alpha=.18)
    assert result.rank == 123
    assert (result.lower, result.upper) == (877, 1123)


def test_large_representable_point_rmse_does_not_overflow_its_square():
    result = point_metrics((1e200,), (0.,))
    assert result['rmse'] == 1e200


def test_wape_keeps_nonzero_truth_when_its_mean_underflows():
    tiny = float.fromhex('0x0.0000000000001p-1022')
    assert point_metrics((tiny, tiny), (tiny, 0.))['wape'] == 1.


@pytest.mark.parametrize('metric', (
    lambda: point_metrics((1e308,), (-1e308,)),
    lambda: interval_metrics((-1e308,), (1e308,), (0.,), .1),
    lambda: quantile_metrics({.5: (1e308,)}, (-1e308,)),
))
def test_unrepresentable_derived_metrics_fail_explicitly(metric):
    with pytest.raises(ValueError, match='finite|numerical'):
        metric()
