"""Compare real normal-import v1 full captures with v2 changed-row captures.

Run from the repository root with PYTHONPATH=src:backend:agent and the installed
backend interpreter. Uses fresh temporary databases and deterministic records;
timings depend on the host. The v1 implementation is a benchmark-only baseline.
"""
from contextlib import nullcontext
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from statistics import median
import tempfile
from time import perf_counter
from unittest.mock import patch

from app.config import Settings
from app.core.clock import FrozenClock, SequentialIdFactory
from app.forecasting.persistence import identity
from app.forecasting import repository
from app.main import create_app
from app.services.imports import import_and_commit
from reference_data import seed_reference


def legacy_capture(session, *, now, tenant_id='northstar'):
    """The pre-v2 source capture, kept here only as a reproducible baseline."""
    store = session.info.get('forecast_store')
    if store is None:
        return None
    session.flush()
    connection = session.connection().connection.driver_connection
    if not connection.in_transaction:
        connection.execute('BEGIN IMMEDIATE')
    trusted_clock = session.info.get('forecast_clock')
    if trusted_clock is not None:
        now = max(repository._instant(now), repository._instant(trusted_clock()))
    factory = repository.repository_snapshot_factory(lambda: nullcontext(session), clock=lambda: now)
    snapshot = factory(now=now, tenant_id=tenant_id, as_of=False)
    payload = repository._capture_payload(snapshot, repository._material(session, now, include_future=True))
    previous_factory = connection.row_factory
    connection.row_factory = sqlite3.Row
    try:
        previous = connection.execute("SELECT * FROM forecast_inputs WHERE tenant_id=? AND kind='repository_state' AND source_id='repository' ORDER BY available_at DESC,received_at DESC,rowid DESC LIMIT 1", (tenant_id,)).fetchone()
        if previous is not None and json.loads(previous['payload']) == payload:
            return store._input(previous)
        revision = identity({'payload': payload, 'predecessor': previous['revision'] if previous else None})
        return store._append_input(connection, 'repository_state', 'repository', revision,
                                   payload, now, now, tenant_id)
    finally:
        connection.row_factory = previous_factory


def benchmark(import_count, capture):
    capture_times = []
    def measured_capture(*args, **kwargs):
        start = perf_counter()
        result = capture(*args, **kwargs)
        capture_times.append(perf_counter() - start)
        return result
    with tempfile.TemporaryDirectory() as directory, patch.object(repository, 'capture_repository_inputs', measured_capture):
        clock = FrozenClock(datetime(2026, 10, 25, 12, tzinfo=timezone.utc))
        ids = SequentialIdFactory()
        path = Path(directory) / 'benchmark.sqlite'
        app = create_app(Settings(db_path=path, droid_runner='fake', forecast_provider='engine',
                                  forecast_demo=False, forecast_worker=False), clock=clock, id_factory=ids)
        with app.state.session_factory() as session:
            seed_reference(session)
        for batch in range(import_count):
            raw = 'record_id,occurred_at,source_account,provider,cost_category,amount,unit\n'
            raw += ''.join(f'b{batch}-r{row},2026-10-20T00:00:00Z,ws-research,anthropic,direct_api,1.00,USD\n' for row in range(20))
            with app.state.session_factory() as session:
                outcome = import_and_commit(session, source_kind='northstar_billing', raw=raw.encode(), filename=f'b{batch}.csv',
                                             actor_id='benchmark', clock=clock, ids=ids)
                assert outcome.batch.status == 'imported'
        service = app.state.forecast_service
        with service.store.transaction() as connection:
            receipts, receipt_bytes = connection.execute("SELECT COUNT(*),SUM(LENGTH(payload)) FROM forecast_inputs WHERE kind='repository_state'").fetchone()
            versions, version_bytes = connection.execute('SELECT COUNT(*),COALESCE(SUM(LENGTH(payload)),0) FROM forecast_repository_row_versions').fetchone()
            sqlite_bytes = connection.execute('PRAGMA page_count').fetchone()[0] * connection.execute('PRAGMA page_size').fetchone()[0]
        elapsed = []
        for _ in range(3):
            start = perf_counter()
            snapshot = service.current_snapshot()
            elapsed.append(perf_counter() - start)
        historical = service.current_snapshot(cutoff=clock.now())
        numerical_keys = ('observations', 'pricing', 'configurations', 'coverage', 'memberships', 'people', 'teams')
        assert all(snapshot[k] == historical[k] for k in numerical_keys)
        assert len(snapshot['observations']) == import_count * 20
        result = {'mode': 'v1' if capture is legacy_capture else 'v2', 'imports': import_count,
                  'records': import_count * 20, 'receipts': receipts, 'row_versions': versions,
                  'receipt_payload_bytes': receipt_bytes, 'row_payload_bytes': version_bytes,
                  'all_archive_payload_bytes': receipt_bytes + version_bytes,
                  'sqlite_allocated_bytes': sqlite_bytes,
                  'last_five_capture_seconds_median': median(capture_times[-5:]),
                  'current_snapshot_seconds_median': median(elapsed)}
        app.state.engine.dispose()
        return result


if __name__ == '__main__':
    current = repository.capture_repository_inputs
    print(json.dumps([benchmark(n, method) for n in (10, 60) for method in (legacy_capture, current)], indent=2))
