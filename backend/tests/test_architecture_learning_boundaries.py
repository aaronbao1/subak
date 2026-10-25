"""Cross-boundary audit: frozen publication, observed truth and issued intervals.

All records here are explicitly synthetic mechanics fixtures; no accuracy or
promotion claim is established by these examples.
"""
from copy import deepcopy
from datetime import date, timedelta

import pytest

from app.forecasting.persistence import ForecastStore
from app.forecasting.service import ForecastService
from app.forecasting.worker import ForecastWorker
from forecasting.learning import archive_issued_targets, current_error_records
from forecasting.planning import build_forecast


NOW = '2026-10-26T00:00:00Z'


def snapshot_factory(*, now, tenant_id):
    origin = date.fromisoformat(now[:10])
    days = [origin - timedelta(days=i) for i in range(1, 57)]
    return {
        'tenant_id': tenant_id, 'information_cutoff': now,
        'forecast_start': str(origin), 'history_complete_through': str(origin - timedelta(days=1)),
        'period_start': '2026-10-01', 'period_end': '2027-01-01',
        'target': {'unit': 'USD', 'quantity': 'spend', 'basis': 'planning', 'timezone': 'UTC'},
        'required_sources': ['synthetic-ledger'], 'people': [], 'drivers': [], 'is_synthetic': True,
        'coverage': [{'date': str(d), 'source_id': 'synthetic-ledger', 'complete': True,
                      'available_at': str(d + timedelta(days=1)) + 'T00:00:00Z'} for d in days],
        'observations': [{'date': str(d), 'source_id': 'synthetic-ledger', 'quantity': 10.,
                          'exposure': 1., 'configuration_id': 'model', 'meter': 'tokens',
                          'billing_pool': 'pool', 'complete': True, 'mature': True,
                          'is_synthetic': True} for d in days],
        'pricing': [{'id': 'linear', 'version': 1, 'billing_pool': 'pool', 'unit': 'tokens',
                     'currency': 'USD', 'period_start': '2026-10-01', 'period_end': '2027-01-01',
                     'mode': 'linear', 'rate': 2., 'fixed': 0., 'allowance': 0., 'complete_pool': True}],
    }


def seed_archive(service, *, received_last=NOW):
    snapshot = service.current_snapshot()
    bundle = build_forecast(snapshot, run_id='template', generated_at=NOW)
    template = next(row for row in archive_issued_targets(bundle, snapshot)
                    if row['scope_type'] == 'company' and row['aggregation'] == 'weekly'
                    and row['lead_days'] == 0)
    for i in range(4):
        begin = date(2026, 9, 28) + timedelta(weeks=i)
        end = begin + timedelta(days=7)
        target = {**deepcopy(template), 'target_id': f'synthetic-prior-{i}', 'run_id': f'prior-{i}',
                  'origin': str(begin), 'start': str(begin), 'end': str(end),
                  'issued_at': str(begin) + 'T00:00:00Z'}
        truth = {'target_id': target['target_id'], 'revision': 1, 'available_at': str(end) + 'T00:00:00Z',
                 'mature_at': str(end) + 'T00:00:00Z', 'status': 'mature',
                 'value': target['prediction'] + i + 1, 'source_id': 'synthetic-observed-outcomes',
                 'is_synthetic': True}
        service.store.append_input('issued_targets', target['target_id'], '1', target,
                                   available_at=target['issued_at'])
        service.store.append_input('truth_revisions', target['target_id'], '1', truth,
                                   available_at=truth['available_at'],
                                   received_at=received_last if i == 3 else truth['available_at'])
    return template


def publish(service, key):
    job = service.refresh(key)
    assert ForecastWorker(service).process_one(job_id=job['id'])
    assert service.store.get_job(job['id'])['status'] == 'succeeded'
    return job, service.store.get_run(job['run_id'])['bundle']


def company_week(bundle):
    return next(view for view in bundle['views'] if view['scope']['type'] == 'company')['weekly'][0]


def test_observed_truth_changes_future_calibration_without_rewriting_issued_bounds(tmp_path):
    clock = [NOW]
    service = ForecastService(ForecastStore(tmp_path / 'audit.db'), snapshot_factory=snapshot_factory,
                              now=lambda: clock[0])
    seed_archive(service)
    first, issued = publish(service, 'calibrated')
    original = deepcopy(issued)
    interval = company_week(issued)['historical_error_interval']['80']
    assert interval['n'] == 4
    assert (interval['lower'], interval['upper']) == pytest.approx((136., 144.))
    assert interval['is_synthetic'] is True
    first_snapshot = service.store.get_snapshot(first['snapshot_id'])
    errors = current_error_records(first_snapshot['forecast_errors'], cutoff=NOW)
    assert sorted(row['absolute_error'] for row in errors.values()) == [1., 2., 3., 4.]
    assert first_snapshot['observations'] == snapshot_factory(now=NOW, tenant_id='northstar')['observations']
    archived = [row['payload'] for row in service.store.input_records(NOW)
                if row['kind'] == 'issued_targets' and row['payload']['run_id'] == first['run_id']
                and row['payload']['scope_type'] == 'company' and row['payload']['aggregation'] == 'weekly'
                and row['payload']['lead_days'] == 0]
    assert archived[0]['intervals']['80'] == interval
    assert archived[0]['implementation_sha256'] == issued['implementation_sha256']

    clock[0] = '2026-10-26T00:01:00Z'
    correction = {'target_id': 'synthetic-prior-3', 'revision': 2,
                  'available_at': clock[0], 'mature_at': clock[0], 'status': 'disputed',
                  'value': 144., 'source_id': 'synthetic-observed-outcomes', 'is_synthetic': True}
    service.store.append_input('truth_revisions', correction['target_id'], '2', correction,
                               available_at=clock[0])
    clock[0] = '2026-11-02T00:00:00Z'
    second, revised = publish(service, 'withdrawn')
    revised_interval = company_week(revised)['historical_error_interval']['80']
    assert revised_interval['n'] == 3 and revised_interval['lower'] is None
    second_snapshot = service.store.get_snapshot(second['snapshot_id'])
    current = current_error_records(second_snapshot['forecast_errors'], cutoff=clock[0])
    assert current['synthetic-prior-3']['state'] == 'withdrawn'
    assert service.store.get_run(first['run_id'])['bundle'] == original
    assert service.store.get_snapshot(first['snapshot_id']) == first_snapshot
    assert revised['model_registry']['decision']['promote'] is False


def test_truth_received_after_cutoff_cannot_backfill_calibration(tmp_path):
    clock = [NOW]
    service = ForecastService(ForecastStore(tmp_path / 'audit.db'), snapshot_factory=snapshot_factory,
                              now=lambda: clock[0])
    seed_archive(service, received_last='2026-10-26T00:01:00Z')
    job, bundle = publish(service, 'as-of')
    interval = company_week(bundle)['historical_error_interval']['80']
    assert interval['n'] == 3 and interval['lower'] is None
    assert len(service.store.get_snapshot(job['snapshot_id'])['forecast_errors']) == 3
    clock[0] = '2026-10-26T00:02:00Z'
    assert len(service.current_snapshot()['truth_revisions']) == 4
    assert len(service.current_snapshot(cutoff=NOW)['truth_revisions']) == 3
    assert company_week(service.store.get_run(job['run_id'])['bundle'])['historical_error_interval']['80'] == interval


def test_only_new_observed_usage_refits_future_rates(tmp_path):
    clock = [NOW]
    service = ForecastService(ForecastStore(tmp_path / 'audit.db'), snapshot_factory=snapshot_factory,
                              now=lambda: clock[0])
    seed_archive(service)
    first, issued = publish(service, 'before-observed-revision')
    assert company_week(issued)['base'] == pytest.approx(140.)
    first_snapshot = service.store.get_snapshot(first['snapshot_id'])
    assert len(first_snapshot['forecast_errors']) == 4

    clock[0] = '2026-11-02T00:00:00Z'
    observed = snapshot_factory(now=clock[0], tenant_id='northstar')['observations']
    for row in observed:
        row.update(quantity=20., revision=2)
    service.store.append_input('observations', 'synthetic-ledger', '2', observed,
                               available_at=clock[0])
    second, refit = publish(service, 'after-observed-revision')
    assert company_week(refit)['base'] == pytest.approx(280.)
    assert len(service.store.get_snapshot(second['snapshot_id'])['forecast_errors']) == 4
    assert company_week(service.store.get_run(first['run_id'])['bundle'])['base'] == pytest.approx(140.)
    assert service.store.get_snapshot(first['snapshot_id']) == first_snapshot
