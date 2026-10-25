"""Durability regressions: removing transaction fences or immutable storage breaks these."""
from concurrent.futures import ThreadPoolExecutor
import sqlite3

import pytest

from app.forecasting.persistence import ForecastStore, ImmutableConflict


@pytest.fixture
def store(tmp_path):
    return ForecastStore(tmp_path / 'forecasts.db')


def snap():
    return {'id': 's1', 'tenant_id': 'northstar', 'observations': [], 'information_cutoff': '2026-10-26T00:00:00Z'}


def test_input_revision_cannot_change_and_snapshot_cannot_rebase(store):
    store.append_input('observations', 'billing', '1', [{'quantity': 2}], available_at='2026-10-25T00:00:00Z')
    with pytest.raises(ImmutableConflict):
        store.append_input('observations', 'billing', '1', [{'quantity': 9}], available_at='2026-10-25T00:00:00Z')
    frozen = store.save_snapshot(snap())
    with pytest.raises(ImmutableConflict):
        store.save_snapshot({**snap(), 'observations': [{'quantity': 99}]})
    reopened = ForecastStore(store.path)
    assert reopened.get_snapshot(frozen['id'])['observations'] == []
    assert len(reopened.input_records('2026-10-26T00:00:00Z')) == 1


def test_duplicate_refresh_and_concurrent_claim_are_single_work(store):
    store.save_snapshot(snap())
    first = store.enqueue('northstar', 'manual:one', 's1', '2026-10-26T00:00:00Z')
    assert store.enqueue('northstar', 'manual:one', 's1', '2026-10-26T00:00:00Z')['id'] == first['id']
    with ThreadPoolExecutor(max_workers=4) as pool:
        claims = list(pool.map(lambda n: ForecastStore(store.path).claim(str(n), '2026-10-26T00:00:00Z'), range(4)))
    assert sum(claim is not None for claim in claims) == 1
    assert next(claim for claim in claims if claim)['attempts'] == 1


def test_expired_claim_is_fenced_and_retry_survives_restart(store):
    store.save_snapshot(snap())
    job = store.enqueue('northstar', 'one', 's1', '2026-10-26T00:00:00Z')
    dead = store.claim('dead', '2026-10-26T00:00:00Z', lease_seconds=5)
    live = ForecastStore(store.path).claim('live', '2026-10-26T00:00:06Z')
    assert live['id'] == job['id'] and live['attempts'] == 2
    assert store.complete(dead['id'], dead['lease_token'], {'views': []}, '2026-10-26T00:00:07Z') is False
    assert store.fail(live['id'], live['lease_token'], 'temporary', '2026-10-26T00:00:07Z', retry_seconds=2)
    assert store.claim('early', '2026-10-26T00:00:08Z') is None
    retried = ForecastStore(store.path).claim('again', '2026-10-26T00:00:10Z')
    assert retried['attempts'] == 3
    assert store.complete(retried['id'], retried['lease_token'], {'views': []}, '2026-10-26T00:00:11Z')


def test_older_completion_never_overwrites_new_publication(store):
    store.save_snapshot(snap())
    old = store.enqueue('northstar', 'old', 's1', '2026-10-26T00:00:00Z')
    old = store.claim('old', '2026-10-26T00:00:00Z')
    new = store.enqueue('northstar', 'new', 's1', '2026-10-26T00:00:01Z')
    new = store.claim('new', '2026-10-26T00:00:01Z')
    store.complete(new['id'], new['lease_token'], {'views': [{'value': 20}]}, '2026-10-26T00:00:02Z')
    store.complete(old['id'], old['lease_token'], {'views': [{'value': 10}]}, '2026-10-26T00:00:03Z')
    assert store.publication()['run_id'] == new['run_id']
    assert store.get_run(old['run_id'])['bundle']['views'][0]['value'] == 10
    with sqlite3.connect(store.path) as conn:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("UPDATE forecast_runs SET bundle='{}'")


def test_delayed_old_source_revision_does_not_replace_new_version(store):
    store.append_input('pricing', 'tariff', '2', {'rate': 2}, available_at='2026-10-25T00:00:00Z', received_at='2026-10-26T00:00:00Z')
    store.append_input('pricing', 'tariff', '1', {'rate': 1}, available_at='2026-10-24T00:00:00Z', received_at='2026-10-27T00:00:00Z')
    assert store.input_records('2026-10-28T00:00:00Z', latest=True)[0]['payload']['rate'] == 2


def test_ingestion_callback_is_atomic_and_duplicate_does_not_invalidate_twice(store):
    with store.transaction() as c:
        c.execute('CREATE TABLE proposal_invalidations(source_id TEXT)')
    def invalidate(c, row):
        c.execute('INSERT INTO proposal_invalidations VALUES(?)', (row['source_id'],))
        if row['source_id'] == 'rollback':
            raise RuntimeError('reject')
    store.on_input = invalidate
    for _ in range(2):
        store.append_input('evidence','one','1',{},available_at='2026-10-25T00:00:00Z')
    with pytest.raises(RuntimeError):
        store.append_input('evidence','rollback','1',{},available_at='2026-10-25T00:00:00Z')
    with store.transaction() as c:
        assert c.execute('SELECT count(*) FROM proposal_invalidations').fetchone()[0] == 1
    assert len(store.input_records('2026-10-28T00:00:00Z')) == 1


def test_heartbeat_prevents_expired_claim_and_exhausted_lease_finishes_failed(store):
    store.save_snapshot(snap())
    job = store.enqueue('northstar','heart','s1','2026-10-26T00:00:00Z')
    claim = store.claim('one','2026-10-26T00:00:00Z',lease_seconds=5)
    assert store.heartbeat(job['id'],claim['lease_token'],'2026-10-26T00:00:04Z',lease_seconds=5)
    assert store.claim('two','2026-10-26T00:00:06Z') is None
    second = store.claim('two','2026-10-26T00:00:10Z',lease_seconds=1)
    third = store.claim('three','2026-10-26T00:00:12Z',lease_seconds=1)
    assert third['attempts'] == 3
    assert store.claim('four','2026-10-26T00:00:14Z') is None
    assert store.get_job(job['id'])['status'] == 'failed'


def test_missed_schedule_cannot_replace_newer_information_cutoff(store):
    store.save_snapshot(snap())
    store.save_snapshot({**snap(),'id':'newer','information_cutoff':'2026-10-30T12:00:00Z'})
    fresh = store.enqueue('northstar','manual','newer','2026-10-30T12:00:00Z')
    fresh = store.claim('fresh','2026-10-30T12:00:00Z')
    store.complete(fresh['id'],fresh['lease_token'],{'views':[]},'2026-10-30T12:00:00Z')
    old = store.enqueue('northstar','weekly','s1','2026-10-30T12:00:01Z')
    old = store.claim('old','2026-10-30T12:00:01Z')
    store.complete(old['id'],old['lease_token'],{'views':[]},'2026-10-30T12:00:02Z')
    assert store.publication()['run_id'] == fresh['run_id']


def test_pure_reads_do_not_acquire_writer_lock_or_observe_uncommitted_changes(store):
    """A concurrent intake write must not block unrelated reads of issued state."""
    with sqlite3.connect(store.path) as connection:
        connection.execute('PRAGMA journal_mode=WAL')
    store.save_snapshot(snap())
    record = store.append_input('evidence', 'one', '1', {'value': 1}, available_at='2026-10-25T00:00:00Z')
    job = store.enqueue('northstar', 'readable', 's1', '2026-10-26T00:00:00Z')
    claim = store.claim('worker', '2026-10-26T00:00:00Z')
    store.complete(job['id'], claim['lease_token'], {'views': []}, '2026-10-26T00:00:01Z')
    scenario = store.save_scenario(job['run_id'], [], {'scenario_id': 'scenario-read'}, '2026-10-26T00:00:02Z')
    expected_publication = store.publication()

    def read_all():
        assert store.publication() == expected_publication
        assert store.get_run(job['run_id'])['bundle'] == {'views': []}
        assert store.get_snapshot('s1') == snap()
        assert store.get_job(job['id'])['status'] == 'succeeded'
        assert store.find_job('northstar', 'readable')['id'] == job['id']
        assert store.find_run_job(job['run_id'])['id'] == job['id']
        assert len(store.list_jobs()) == 1
        assert store.find_input('evidence', 'one', '1') == record
        assert store.input_records('2026-10-26T00:00:00Z') == [record]
        assert store.get_scenario('scenario-read') == scenario
        return True

    with ThreadPoolExecutor(max_workers=1) as pool, sqlite3.connect(store.path, isolation_level=None) as writer:
        writer.execute('BEGIN IMMEDIATE')
        writer.execute("UPDATE forecast_publications SET sequence=999")
        pending = pool.submit(read_all)
        try:
            assert pending.result(timeout=2) is True
        finally:
            writer.rollback()
