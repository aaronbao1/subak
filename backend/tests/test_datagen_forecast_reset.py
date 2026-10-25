"""Bulk dataset replacement cannot retain or publish the preceding company's runs."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date
import importlib.util
import json
from pathlib import Path
import threading

import pytest
from sqlalchemy import select

from app.db.base import create_all, make_engine, make_session_factory
from app.db.models import PlanningPeriod, Team, UsageRecord
from app.core.errors import DomainError
from app.forecasting.persistence import ForecastStore
from app.forecasting.service import ForecastService
from app.forecasting.worker import ForecastWorker


spec = importlib.util.spec_from_file_location('datagen_loader_under_test', Path(__file__).parents[2] / 'datagen' / 'load_backend.py')
loader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(loader)
NOW = '2026-10-24T12:00:00Z'


def dataset(tmp_path, *, bad_billing=False):
    out = tmp_path / 'generated'
    (out / 'backend' / 'billing').mkdir(parents=True)
    (out / 'backend' / 'corpus').mkdir()
    reference = {'company': {'name': 'Tiny simulated company'},
                 'periods': [{'id': 'tiny-q4', 'label': 'Tiny Q4', 'starts_on': '2026-10-01', 'ends_on': '2026-12-31'}],
                 'teams': [{'id': 'tiny', 'name': 'Tiny'}],
                 'team_mappings': {'northstar_billing': {'ws-tiny': 'tiny'}},
                 'people': [{'id': 'tiny-alice', 'team': 'tiny', 'name': 'Alice', 'email': 'alice@tiny.example', 'is_simulated': True}],
                 'budgets': {'tiny-q4': {'tiny': '100'}}}
    (out / 'backend' / 'reference.json').write_text(json.dumps(reference))
    csv = 'invalid,header\na,b\n' if bad_billing else (
        'record_id,occurred_at,source_account,user_email,cost_category,value_kind,amount,unit\n'
        'tiny-1,2026-10-23T00:00:00Z,ws-tiny,alice@tiny.example,direct_api,simulated,5.00,USD\n')
    (out / 'backend' / 'billing' / 'tiny.csv').write_text(csv)
    return out


def prior_state(path, *, period='old-q4'):
    engine = make_engine(path)
    create_all(engine)
    factory = make_session_factory(engine)
    with factory() as session:
        session.add(PlanningPeriod(id=period, label='Old quarter', starts_on=date(2026, 10, 1), ends_on=date(2026, 12, 31)))
        session.add(Team(id='old-team', name='Old team'))
        session.commit()
    store = ForecastStore(path)
    store.append_input('evidence', 'old-company', '1', {'old': True}, available_at=NOW)
    store.save_snapshot({'id': 'old-snapshot', 'tenant_id': 'northstar', 'information_cutoff': NOW})
    job = store.enqueue('northstar', 'old-refresh', 'old-snapshot', NOW)
    claim = store.claim('old-worker', NOW)
    store.complete(claim['id'], claim['lease_token'], {'views': []}, NOW)
    engine.dispose()
    return store, job['run_id']


def args(path, out, *, reset=True):
    return ['--db', str(path), '--out-dir', str(out), *(['--reset'] if reset else [])]


def test_reset_clears_old_publication_and_keeps_bulk_import_unarchived(tmp_path):
    path, out = tmp_path / 'dataset.sqlite', dataset(tmp_path)
    store, old_run = prior_state(path)
    assert loader.main(args(path, out)) == 0
    assert store.publication() is None
    assert store.input_records('2099-01-01T00:00:00Z') == []
    with pytest.raises(KeyError):
        store.get_run(old_run)
    engine = make_engine(path)
    with make_session_factory(engine)() as session:
        assert list(session.scalars(select(PlanningPeriod.id))) == ['tiny-q4']
        assert list(session.scalars(select(Team.id))) == ['tiny']
        record, = session.scalars(select(UsageRecord)).all()
        assert record.person_id == 'tiny-alice' and str(record.amount) == '5.00'
    engine.dispose()


def test_without_reset_existing_dataset_and_publication_are_unchanged(tmp_path):
    path, out = tmp_path / 'dataset.sqlite', dataset(tmp_path)
    store, old_run = prior_state(path, period='tiny-q4')
    before = store.input_records(NOW)
    assert loader.main(args(path, out, reset=False)) == 0
    assert store.publication()['run_id'] == old_run
    assert store.input_records(NOW) == before


def test_rejected_import_rolls_back_reset_and_restores_previous_company(tmp_path):
    path, out = tmp_path / 'dataset.sqlite', dataset(tmp_path, bad_billing=True)
    store, old_run = prior_state(path)
    assert loader.main(args(path, out)) == 1
    assert store.publication()['run_id'] == old_run
    assert store.input_records(NOW)[0]['source_id'] == 'old-company'
    engine = make_engine(path)
    with make_session_factory(engine)() as session:
        assert list(session.scalars(select(Team.id))) == ['old-team']
        assert session.get(PlanningPeriod, 'old-q4') is not None
    engine.dispose()


def test_invalid_directory_exception_restores_preceding_publication(tmp_path):
    path, out = tmp_path / 'dataset.sqlite', dataset(tmp_path)
    store, old_run = prior_state(path)
    reference_path = out / 'backend' / 'reference.json'
    reference = json.loads(reference_path.read_text())
    reference['people'][0]['email'] = 'invalid-email'
    reference_path.write_text(json.dumps(reference))
    with pytest.raises(DomainError, match='invalid people'):
        loader.main(args(path, out))
    assert store.publication()['run_id'] == old_run
    engine = make_engine(path)
    with make_session_factory(engine)() as session:
        assert list(session.scalars(select(Team.id))) == ['old-team']
    engine.dispose()


def test_worker_waits_for_whole_bulk_reset_and_load(tmp_path, monkeypatch):
    path, out = tmp_path / 'dataset.sqlite', dataset(tmp_path)
    store, _ = prior_state(path)
    loading, release, worker_started, worker_done = (threading.Event() for _ in range(4))
    original = loader.import_svc.run_import
    def paused_import(*args, **kwargs):
        # Reference/corpus commits already released their SQLite write locks.
        # Only a maintenance operation lock can fence this inter-phase gap.
        loading.set()
        assert release.wait(5)
        return original(*args, **kwargs)
    monkeypatch.setattr(loader.import_svc, 'run_import', paused_import)
    worker = ForecastWorker(ForecastService(store, now=lambda: NOW))
    def poll():
        worker_started.set()
        result = worker.process_one()
        worker_done.set()
        return result
    with ThreadPoolExecutor(max_workers=2) as pool:
        bulk = pool.submit(loader.main, args(path, out))
        try:
            assert loading.wait(5)
            polling = pool.submit(poll)
            assert worker_started.wait(5)
            assert not worker_done.wait(.05)
        finally:
            release.set()
        assert bulk.result(timeout=5) == 0
        assert polling.result(timeout=5) is False
