"""Observed-outcome HTTP ingress through immutable refresh and learning receipts.

All data are synthetic mechanics fixtures. These checks establish wiring and
qualification boundaries, not real-world accuracy or promotion eligibility.
"""
from copy import deepcopy
from datetime import datetime, timezone
import json

from fastapi.testclient import TestClient
import pytest

from app.config import Settings
from app.core.clock import FrozenClock, SequentialIdFactory
from app.main import create_app
from forecasting.learning import current_error_records
from test_architecture_learning_boundaries import snapshot_factory


DIMENSIONS = ('quantity', 'unit', 'basis', 'timezone', 'scope_type', 'scope_id', 'start', 'end')


def _publish(client, service, worker, key):
    response = client.post('/api/forecast-refreshes', headers={'Idempotency-Key': key})
    assert response.status_code == 202, response.text
    job = response.json()
    assert worker.process_one(job_id=job['id'])
    assert client.get('/api/forecast-refreshes/' + job['id']).json()['status'] == 'succeeded'
    return job, service.store.get_run(job['run_id'])['bundle']


@pytest.fixture
def issued_outcome(tmp_path):
    clock = FrozenClock(datetime(2026, 10, 26, tzinfo=timezone.utc))
    app = create_app(Settings(db_path=tmp_path / 'outcomes.db', forecast_provider='engine',
                              forecast_worker=False, droid_runner='fake'),
                     clock=clock, id_factory=SequentialIdFactory())
    service = app.state.forecast_service
    service.snapshot_factory = snapshot_factory
    with TestClient(app) as client:
        first, bundle = _publish(client, service, app.state.forecast_worker, 'issue-original')
        target = next(record['payload'] for record in service.store.input_records(clock.now())
                      if record['kind'] == 'issued_targets'
                      and record['payload']['run_id'] == first['run_id']
                      and record['payload']['scope_type'] == 'company'
                      and record['payload']['aggregation'] == 'weekly'
                      and record['payload']['lead_days'] == 0)
        clock.advance(days=7)
        yield client, service, app.state.forecast_worker, clock, target, first, bundle


def _envelope(target, clock, **changes):
    payload = {key: target[key] for key in DIMENSIONS}
    payload.update(target_id=target['target_id'], revision=1,
                   available_at=clock.now().isoformat(), mature_at=clock.now().isoformat(),
                   status='mature', value=target['prediction'] + 12.,
                   source_id='synthetic-observed-ledger', is_synthetic=True, complete=True,
                   provenance={'kind': 'observed', 'reference': 'synthetic-ledger:week-2026-10-26'})
    payload.update(changes)
    return payload


def _post(client, payload):
    # Explicit JSON also exercises non-finite inputs, which normal client.json
    # refuses before the application can reject them.
    return client.post('/api/forecast-outcomes', content=json.dumps(payload),
                       headers={'Content-Type': 'application/json'})


def _truth(service):
    return service.store.input_records('2100-01-01T00:00:00Z', kinds='truth_revisions')


def _current(service, job, clock, target):
    snapshot = service.store.get_snapshot(job['snapshot_id'])
    current = current_error_records(snapshot.get('forecast_errors', []), cutoff=clock.now().isoformat())
    return snapshot, current[target['target_id']]


def test_outcome_http_ingress_scores_on_next_refresh_and_preserves_issued_run(issued_outcome):
    client, service, worker, clock, target, issued, original = issued_outcome
    assert target['quantity'] == 'spend'
    original_snapshot = service.store.get_snapshot(issued['snapshot_id'])
    payload = _envelope(target, clock)
    response = _post(client, payload)
    assert response.status_code == 201, response.text
    persisted = _truth(service)
    assert len(persisted) == 1
    assert persisted[0]['payload']['provenance'] == payload['provenance']
    assert persisted[0]['payload']['is_synthetic'] is True
    assert service.store.input_records(clock.now(), kinds='forecast_errors') == []

    job, bundle = _publish(client, service, worker, 'score-outcome')
    snapshot, score = _current(service, job, clock, target)
    assert score['state'] == 'scored'
    assert score['actual'] == payload['value']
    assert score['absolute_error'] == pytest.approx(12.)
    assert score['is_synthetic'] is True
    assert snapshot['observations'] == snapshot_factory(now=clock.now().isoformat(), tenant_id='northstar')['observations']
    assert bundle['model_registry']['decision']['promote'] is False
    assert service.store.get_run(issued['run_id'])['bundle'] == original
    assert service.store.get_snapshot(issued['snapshot_id']) == original_snapshot


def test_outcome_retries_are_idempotent_and_conflicts_cannot_rewrite_truth(issued_outcome):
    client, service, _, clock, target, _, _ = issued_outcome
    payload = _envelope(target, clock)
    assert _post(client, payload).status_code == 201
    first = deepcopy(_truth(service))
    clock.advance(minutes=1)
    assert _post(client, payload).status_code == 201
    assert _truth(service) == first
    response = _post(client, {**payload, 'value': payload['value'] + 1})
    assert response.status_code == 409, response.text
    assert _truth(service) == first


def test_outcome_correction_appends_score_without_mutating_prior_receipts(issued_outcome):
    client, service, worker, clock, target, _, _ = issued_outcome
    assert _post(client, _envelope(target, clock)).status_code == 201
    first, original = _publish(client, service, worker, 'first-score')
    frozen, score = _current(service, first, clock, target)
    assert score['absolute_error'] == pytest.approx(12.)

    clock.advance(minutes=1)
    correction = _envelope(target, clock, revision=2, value=target['prediction'] + 5.)
    assert _post(client, correction).status_code == 201
    second, _ = _publish(client, service, worker, 'corrected-score')
    revised, current = _current(service, second, clock, target)
    assert current['truth_revision'] == 2
    assert current['absolute_error'] == pytest.approx(5.)
    assert len(_truth(service)) == 2
    assert score in revised['forecast_errors']
    assert service.store.get_snapshot(first['snapshot_id']) == frozen
    assert service.store.get_run(first['run_id'])['bundle'] == original


@pytest.mark.parametrize('status', ['pending', 'disputed'])
def test_outcome_withdrawal_removes_predecessor_from_current_scoring(issued_outcome, status):
    client, service, worker, clock, target, _, _ = issued_outcome
    assert _post(client, _envelope(target, clock)).status_code == 201
    first, _ = _publish(client, service, worker, 'before-withdrawal')
    frozen, original = _current(service, first, clock, target)

    clock.advance(minutes=1)
    withdrawal = _envelope(target, clock, revision=2, status=status, complete=False, value=999.)
    assert _post(client, withdrawal).status_code == 201
    second, _ = _publish(client, service, worker, 'after-withdrawal')
    revised, current = _current(service, second, clock, target)
    assert current['state'] == 'withdrawn'
    assert current['actual'] is None and current['absolute_error'] is None
    assert original in revised['forecast_errors']
    assert service.store.get_snapshot(first['snapshot_id']) == frozen


def test_future_maturity_is_awaiting_until_a_later_refresh(issued_outcome):
    client, service, worker, clock, target, _, _ = issued_outcome
    payload = _envelope(target, clock, mature_at='2026-11-03T00:00:00Z')
    assert _post(client, payload).status_code == 201
    first, _ = _publish(client, service, worker, 'before-maturity')
    frozen, waiting = _current(service, first, clock, target)
    assert waiting['state'] == 'awaiting_maturity'
    assert waiting['actual'] is None and waiting['absolute_error'] is None

    clock.advance(days=1)
    second, _ = _publish(client, service, worker, 'after-maturity')
    revised, scored = _current(service, second, clock, target)
    assert scored['state'] == 'scored' and scored['absolute_error'] == pytest.approx(12.)
    assert waiting in revised['forecast_errors']
    assert service.store.get_snapshot(first['snapshot_id']) == frozen


def test_server_receipt_time_blocks_backdated_outcome_from_historical_refresh(issued_outcome):
    client, service, worker, clock, target, _, _ = issued_outcome
    payload = _envelope(target, clock)
    cutoff = clock.now().isoformat()
    clock.advance(minutes=2)
    assert _post(client, payload).status_code == 201
    record = _truth(service)[0]
    assert datetime.fromisoformat(record['received_at'].replace('Z', '+00:00')) == clock.now()
    assert not service.current_snapshot(cutoff=cutoff).get('truth_revisions')
    historical = service.refresh('historical-after-receipt', scheduled_for=cutoff)
    assert worker.process_one(job_id=historical['id'])
    frozen = service.store.get_snapshot(historical['snapshot_id'])
    assert not frozen.get('truth_revisions') and not frozen.get('forecast_errors')

    current, _ = _publish(client, service, worker, 'current-after-receipt')
    _, scored = _current(service, current, clock, target)
    assert scored['state'] == 'scored'
    assert service.store.get_snapshot(historical['snapshot_id']) == frozen


@pytest.mark.parametrize('field,value', [
    ('quantity', 'requests'), ('unit', 'EUR'), ('basis', 'invoiced'),
    ('timezone', 'America/Los_Angeles'), ('scope_type', 'team'), ('scope_id', 'wrong-company'),
    ('start', '2026-10-27'), ('end', '2026-11-03'),
    ('complete', False), ('complete', 1), ('is_synthetic', False), ('is_synthetic', 'true'),
    ('revision', 0), ('revision', True), ('revision', '1'),
    ('value', float('inf')), ('value', float('nan')), ('value', True),
    pytest.param('value', 10 ** 400, id='numeric-overflow'),
    ('source_id', ''), ('status', 'estimated'),
    ('provenance', {'kind': 'predicted', 'reference': 'model-output'}),
    ('provenance', {'kind': 'observed', 'reference': ''}),
    ('available_at', '2026-11-02T00:00:01Z'),
    ('available_at', '2026-11-02T00:00:00'),
    ('received_at', '2026-11-01T00:00:00Z'),
    ('mature_at', '2026-11-01T23:59:59Z'),
    ('mature_at', '2026-11-02T00:00:00'),
])
def test_invalid_outcome_is_rejected_before_persistence(issued_outcome, field, value):
    client, service, _, clock, target, _, _ = issued_outcome
    response = _post(client, _envelope(target, clock, **{field: value}))
    assert response.status_code == 422, response.text
    assert _truth(service) == []


@pytest.mark.parametrize('field', ['complete', 'is_synthetic', 'quantity', 'provenance', 'source_id'])
def test_outcome_requires_explicit_dimensions_completeness_and_provenance(issued_outcome, field):
    client, service, _, clock, target, _, _ = issued_outcome
    payload = _envelope(target, clock)
    del payload[field]
    response = _post(client, payload)
    assert response.status_code == 422, response.text
    assert _truth(service) == []


def test_unknown_target_cannot_enter_learning(issued_outcome):
    client, service, worker, clock, target, _, _ = issued_outcome
    response = _post(client, _envelope(target, clock, target_id='never-issued'))
    assert response.status_code == 404, response.text
    assert _truth(service) == []
    refreshed, bundle = _publish(client, service, worker, 'no-qualified-outcome')
    snapshot = service.store.get_snapshot(refreshed['snapshot_id'])
    assert not snapshot.get('truth_revisions') and not snapshot.get('forecast_errors')
    assert bundle['model_registry']['decision']['promote'] is False


def test_outcome_cannot_mature_before_the_target_period_ends(issued_outcome):
    client, service, _, clock, target, _, _ = issued_outcome
    payload = _envelope(target, clock, available_at='2026-10-30T00:00:00Z',
                        mature_at='2026-10-31T00:00:00Z')
    response = _post(client, payload)
    assert response.status_code == 422, response.text
    assert _truth(service) == []


@pytest.mark.parametrize('frozen_snapshot_available', [True, False])
def test_legacy_target_quantity_requires_its_original_frozen_snapshot(issued_outcome, frozen_snapshot_available):
    client, service, _, clock, target, _, _ = issued_outcome
    legacy = {**target, 'target_id': 'synthetic-legacy-target'}
    del legacy['quantity']
    if not frozen_snapshot_available:
        legacy.pop('snapshot_id', None)
    service.store.append_input('issued_targets', legacy['target_id'], '1', legacy,
                               available_at=legacy['issued_at'])
    payload = _envelope(target, clock, target_id=legacy['target_id'])
    response = _post(client, payload)
    assert response.status_code == (201 if frozen_snapshot_available else 422), response.text
    if frozen_snapshot_available:
        assert _truth(service)[0]['payload']['quantity'] == 'spend'
    else:
        assert _truth(service) == []
