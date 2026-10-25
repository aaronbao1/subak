"""Compact repository captures retain source history across real write paths."""
from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import importlib.util
import json
from pathlib import Path
import sqlite3
import threading

import pytest
from sqlalchemy import select

from app.core.clock import FrozenClock
from app.db.models import ImportBatch, UsageRecord
from app.forecasting.persistence import iso
from app.seed.northstar import seed_reference
from app.services.imports import run_import


NOW = '2026-10-24T12:00:00Z'
ARCHIVE_TABLES = ('forecast_repository_captures', 'forecast_repository_row_versions')


@pytest.fixture
def archive_app(app, clock, id_factory):
    with app.state.session_factory() as session:
        seed_reference(session, clock=clock, ids=id_factory)
        session.commit()
    return app


def billing(*rows):
    header = 'record_id,occurred_at,source_account,cost_category,amount,unit\n'
    return (header + ''.join(
        f'{key},{occurred},ws-research,direct_api,{amount},USD\n'
        for key, occurred, amount in rows
    )).encode()


def import_rows(app, *rows, clock=None):
    with app.state.session_factory() as session:
        result = run_import(
            session, source_kind='northstar_billing', raw=billing(*rows),
            filename='archive.csv', actor_id='test',
            clock=clock or app.state.clock, ids=app.state.id_factory,
        )
        session.commit()
        return result


def archives(app):
    return app.state.forecast_service.store.input_records(
        '2099-01-01T00:00:00Z', kinds=('repository_state',), source_id='repository',
    )


def archive_rows(app):
    with sqlite3.connect(app.state.settings.db_path) as connection:
        return {table: connection.execute(f'SELECT * FROM {table} ORDER BY rowid').fetchall()
                for table in ARCHIVE_TABLES}


def observations(snapshot):
    return {row['provenance']['source_record_key']: row for row in snapshot['observations']}


def test_repeated_imports_keep_compact_history_and_issued_snapshot(archive_app, clock):
    app, service = archive_app, archive_app.state.forecast_service
    cutoffs = []
    for index in range(3):
        import_rows(app, (f'repeated-{index}', '2026-10-20T00:00:00Z', str(index + 1)))
        cutoffs.append(iso(clock.now()))
        if index == 0:
            job = service.refresh('retain-first-import')
            issued = service.store.get_snapshot(job['snapshot_id'])
        clock.advance(minutes=1)

    receipts = archives(app)
    assert all(row['payload']['repository_capture_version'] == 2 for row in receipts)
    assert all('repository_material' not in row['payload'] and 'observations' not in row['payload']
               for row in receipts)
    for index, cutoff in enumerate(cutoffs):
        replay = service.current_snapshot(cutoff=cutoff)
        assert set(observations(replay)) == {f'repeated-{n}' for n in range(index + 1)}
        assert all(row['team_id'] == 'research' for row in replay['observations'])
        assert replay['coverage'] == []
    assert service.store.get_snapshot(job['snapshot_id']) == issued
    assert set(observations(issued)) == {'repeated-0'}

    # New imports append their new native rows, not another copy of prior rows.
    with sqlite3.connect(app.state.settings.db_path) as connection:
        assert connection.execute(
            "SELECT count(*) FROM forecast_repository_row_versions WHERE collection='records'"
        ).fetchone()[0] == 3
    before = archive_rows(app)
    import_rows(app, ('repeated-2', '2026-10-20T00:00:00Z', '3'))
    assert archive_rows(app) == before
    assert archives(app) == receipts


def test_archive_receipt_uses_trusted_clock_and_future_events_wait(archive_app, clock):
    app, service = archive_app, archive_app.state.forecast_service
    stale_clock = FrozenClock(datetime.fromisoformat(NOW.replace('Z', '+00:00')))
    clock.advance(days=3)
    import_rows(
        app,
        ('known-at-receipt', '2026-10-23T00:00:00Z', '5.00'),
        ('known-future-event', '2026-10-28T00:00:00Z', '7.00'),
        clock=stale_clock,
    )
    receipt = archives(app)[-1]
    assert receipt['payload']['repository_capture_version'] == 2
    assert receipt['received_at'] == receipt['available_at'] == iso(clock.now())
    assert service.current_snapshot(cutoff='2026-10-26T00:00:00Z')['observations'] == []
    assert set(observations(service.current_snapshot(cutoff=iso(clock.now())))) == {'known-at-receipt'}
    later = observations(service.current_snapshot(cutoff='2026-10-28T00:00:00Z'))
    assert set(later) == {'known-at-receipt', 'known-future-event'}
    assert later['known-future-event']['quantity'] == '7.00'
    assert later['known-future-event']['team_id'] == 'research'


def test_legacy_full_capture_replays_unchanged_after_first_compact_capture(tmp_path, clock, id_factory):
    from app.config import Settings
    from app.db.base import create_all, make_engine, make_session_factory
    from app.forecasting.persistence import ForecastStore
    from app.forecasting.repository import _material
    from app.main import create_app

    path = tmp_path / 'legacy-archive.sqlite'
    engine = make_engine(path)
    create_all(engine)
    factory = make_session_factory(engine)
    # An unbound legacy session writes native records without a compact capture.
    with factory() as session:
        seed_reference(session, clock=clock, ids=id_factory)
        run_import(
            session, source_kind='northstar_billing',
            raw=billing(('legacy-record', '2026-10-20T00:00:00Z', '9.00')),
            filename='legacy.csv', actor_id='test', clock=clock, ids=id_factory,
        )
        session.commit()
        material = _material(session, clock.now(), include_future=True)
    store = ForecastStore(path)
    legacy = store.append_input(
        'repository_state', 'repository', 'legacy-full-capture',
        {'repository_capture_version': 1, 'repository_material': material},
        available_at=clock.now(), received_at=clock.now(),
    )
    with sqlite3.connect(path) as connection:
        original_payload = connection.execute(
            'SELECT payload FROM forecast_inputs WHERE id=?', (legacy['id'],),
        ).fetchone()[0]
    clock.advance(days=1)
    with factory() as session:
        record = session.scalar(select(UsageRecord).where(UsageRecord.source_record_key == 'legacy-record'))
        record.team_id = 'engineering'
        session.commit()
    engine.dispose()

    app = create_app(Settings(db_path=path, forecast_worker=False), clock=clock, id_factory=id_factory)
    try:
        service = app.state.forecast_service
        receipts = archives(app)
        assert [row['payload']['repository_capture_version'] for row in receipts] == [1, 2]
        old = service.current_snapshot(cutoff=NOW)
        assert old['repository_archive']['id'] == legacy['id']
        assert observations(old)['legacy-record']['team_id'] == 'research'
        assert observations(service.current_snapshot(cutoff=iso(clock.now())))['legacy-record']['team_id'] == 'engineering'
        with sqlite3.connect(path) as connection:
            assert connection.execute(
                'SELECT payload FROM forecast_inputs WHERE id=?', (legacy['id'],),
            ).fetchone()[0] == original_payload
    finally:
        app.state.engine.dispose()


def test_import_rollback_removes_native_rows_and_compact_capture_rows(archive_app, clock):
    app = archive_app
    before_receipts, before_rows = archives(app), archive_rows(app)
    clock.advance(minutes=1)
    with app.state.session_factory() as session:
        outcome = run_import(
            session, source_kind='northstar_billing',
            raw=billing(('rolled-back', '2026-10-20T00:00:00Z', '3.00')),
            filename='rollback.csv', actor_id='test', clock=clock, ids=app.state.id_factory,
        )
        batch_id = outcome.batch.id
        assert session.scalar(select(UsageRecord).where(UsageRecord.source_record_key == 'rolled-back')) is not None
        connection = session.connection().connection.driver_connection
        assert connection.execute('SELECT count(*) FROM forecast_repository_captures').fetchone()[0] > len(
            before_rows['forecast_repository_captures']
        )
        session.rollback()
    assert archives(app) == before_receipts
    assert archive_rows(app) == before_rows
    with app.state.session_factory() as session:
        assert session.get(ImportBatch, batch_id) is None
        assert session.scalar(select(UsageRecord).where(UsageRecord.source_record_key == 'rolled-back')) is None


def test_app_reset_removes_old_archive_material_and_reseeds(archive_app, client):
    app = archive_app
    app.state.settings = replace(app.state.settings, allow_reset=True)
    import_rows(app, ('before-reset', '2026-10-20T00:00:00Z', '3.00'))
    assert any('before-reset' in str(row) for row in archive_rows(app)['forecast_repository_row_versions'])
    old_receipt_ids = {row['id'] for row in archives(app)}
    response = client.post('/api/admin/reset')
    assert response.status_code == 200, response.text
    assert not old_receipt_ids.intersection(row['id'] for row in archives(app))
    assert not any('before-reset' in str(row) for row in archive_rows(app)['forecast_repository_row_versions'])
    assert archives(app)[-1]['payload']['repository_capture_version'] == 2
    replay = app.state.forecast_service.current_snapshot(cutoff=iso(app.state.clock.now()))
    assert replay['observations']
    assert 'before-reset' not in observations(replay)


def test_datagen_reset_removes_compact_repository_history(archive_app, tmp_path):
    app = archive_app
    import_rows(app, ('before-datagen-reset', '2026-10-20T00:00:00Z', '3.00'))
    assert archive_rows(app)['forecast_repository_captures']
    output = tmp_path / 'dataset'
    (output / 'backend' / 'billing').mkdir(parents=True)
    (output / 'backend' / 'corpus').mkdir()
    reference = {
        'company': {'name': 'Replacement'},
        'periods': [{'id': 'replacement-q4', 'label': 'Q4', 'starts_on': '2026-10-01', 'ends_on': '2026-12-31'}],
        'teams': [{'id': 'replacement', 'name': 'Replacement'}],
        'team_mappings': {'northstar_billing': {'ws-research': 'replacement'}},
        'people': [], 'budgets': {'replacement-q4': {'replacement': '100'}},
    }
    (output / 'backend' / 'reference.json').write_text(json.dumps(reference))
    (output / 'backend' / 'billing' / 'replacement.csv').write_bytes(
        billing(('replacement-record', '2026-10-23T00:00:00Z', '4.00'))
    )
    spec = importlib.util.spec_from_file_location(
        'archive_datagen_loader', Path(__file__).parents[2] / 'datagen' / 'load_backend.py',
    )
    loader = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loader)
    assert loader.main(['--db', str(app.state.settings.db_path), '--out-dir', str(output), '--reset']) == 0
    assert archives(app) == []
    assert all(rows == [] for rows in archive_rows(app).values())
    with app.state.session_factory() as session:
        assert list(session.scalars(select(UsageRecord.source_record_key))) == ['replacement-record']


def test_synchronize_serializes_source_read_with_native_mutation_capture(archive_app, clock, monkeypatch):
    import app.forecasting.repository as repository

    app, service = archive_app, archive_app.state.forecast_service
    import_rows(app, ('concurrent-record', '2026-10-20T00:00:00Z', '3.00'))
    material_read, release_read, writer_started, writer_committed = (threading.Event() for _ in range(4))
    sync_thread = []
    original_material = repository._material

    def paused_material(*args, **kwargs):
        result = original_material(*args, **kwargs)
        if sync_thread and threading.get_ident() == sync_thread[0]:
            material_read.set()
            assert release_read.wait(5)
        return result

    monkeypatch.setattr(repository, '_material', paused_material)

    def synchronize():
        sync_thread.append(threading.get_ident())
        return repository.synchronize_repository_inputs(service.store, service.snapshot_factory, now=clock.now())

    def mutate():
        writer_started.set()
        with app.state.session_factory() as session:
            record = session.scalar(select(UsageRecord).where(UsageRecord.source_record_key == 'concurrent-record'))
            record.team_id = 'engineering'
            repository.capture_repository_inputs(session, now=clock.now())
            session.commit()
        writer_committed.set()

    with ThreadPoolExecutor(max_workers=2) as pool:
        syncing = pool.submit(synchronize)
        assert material_read.wait(5)
        writing = pool.submit(mutate)
        try:
            assert writer_started.wait(5)
            committed_during_capture = writer_committed.wait(.1)
        finally:
            release_read.set()
        syncing.result(timeout=5)
        writing.result(timeout=5)

    current = observations(service.current_snapshot())['concurrent-record']
    replay = observations(service.current_snapshot(cutoff=iso(clock.now())))['concurrent-record']
    assert current['team_id'] == replay['team_id'] == 'engineering'
    assert not committed_during_capture


def test_synchronize_uses_requested_store_when_factory_is_bound_elsewhere(archive_app, tmp_path, clock):
    from app.forecasting.persistence import ForecastStore
    from app.forecasting.repository import repository_snapshot_factory, synchronize_repository_inputs

    app, service = archive_app, archive_app.state.forecast_service
    import_rows(app, ('separate-store', '2026-10-20T00:00:00Z', '3.00'))
    before_inputs, before_material = archives(app), archive_rows(app)
    target = ForecastStore(tmp_path / 'separate-forecast.sqlite')
    receipt = synchronize_repository_inputs(target, service.snapshot_factory, now=clock.now())
    assert target.input_records(clock.now()) == [receipt]
    assert receipt['id'] not in {row['id'] for row in before_inputs}
    assert archives(app) == before_inputs
    assert archive_rows(app) == before_material
    reader = repository_snapshot_factory(app.state.session_factory, clock=clock.now, store=target)
    assert observations(reader(now=clock.now(), as_of=True))['separate-store']['team_id'] == 'research'
