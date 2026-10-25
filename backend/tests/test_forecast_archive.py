"""Immutable repository archives store changed rows, not repeated full states."""
from copy import deepcopy
import sqlite3

import pytest


def material(**collections):
    result = {name: [] for name in ('batches', 'records', 'people', 'teams', 'mappings', 'periods')}
    result.update(collections)
    return result


@pytest.fixture
def archive_db():
    from app.forecasting.archive import migrate_archive
    connection = sqlite3.connect(':memory:', isolation_level=None)
    connection.execute('PRAGMA foreign_keys=ON')
    connection.execute('BEGIN IMMEDIATE')
    migrate_archive(connection)
    connection.commit()
    connection.execute('BEGIN IMMEDIATE')
    yield connection
    connection.close()


def test_append_only_imports_archive_each_record_once(archive_db):
    from app.forecasting.archive import capture_material, resolve_material
    receipts = []
    for count in range(1, 5):
        state = material(records=[{'id': str(i), 'amount': '12.34'} for i in range(count)])
        receipts.append(capture_material(archive_db, state, tenant_id='northstar'))
    assert archive_db.execute('SELECT COUNT(*) FROM forecast_repository_row_versions').fetchone()[0] == 4
    assert resolve_material(archive_db, receipts[0], tenant_id='northstar') == material(
        records=[{'id': '0', 'amount': '12.34'}])
    assert resolve_material(archive_db, receipts[-1], tenant_id='northstar') == state


def test_noop_and_empty_baseline_have_stable_capture(archive_db):
    from app.forecasting.archive import capture_material, resolve_material
    first = capture_material(archive_db, material(), tenant_id='northstar')
    again = capture_material(archive_db, material(), tenant_id='northstar')
    assert first == again
    assert archive_db.execute('SELECT COUNT(*) FROM forecast_repository_captures').fetchone()[0] == 1
    assert resolve_material(archive_db, first, tenant_id='northstar') == material()


def test_changed_deleted_and_restored_rows_replay_exact_states(archive_db):
    from app.forecasting.archive import capture_material, resolve_material
    original = material(people=[{'id': 'ada', 'name': 'Ada'}])
    states = [original, material(people=[{'id': 'ada', 'name': 'New Name'}]), material(), original]
    refs = [capture_material(archive_db, state, tenant_id='northstar') for state in states]
    assert len({ref['archive_sequence'] for ref in refs}) == 4
    assert [resolve_material(archive_db, ref, tenant_id='northstar') for ref in refs] == states
    assert archive_db.execute('SELECT COUNT(*) FROM forecast_repository_row_versions WHERE payload IS NULL').fetchone()[0] == 1


def test_capture_sorts_all_collections_and_preserves_future_events(archive_db):
    from app.forecasting.archive import capture_material, resolve_material
    state = material(**{name: [{'id': 'z'}, {'id': 'a'}]
                        for name in ('batches', 'people', 'teams', 'mappings', 'periods')})
    state['records'] = [{'id': 'future', 'occurred_at': '2099-01-01T00:00:00Z'}]
    before = deepcopy(state)
    ref = capture_material(archive_db, state, tenant_id='northstar')
    rebuilt = resolve_material(archive_db, ref, tenant_id='northstar')
    for name in ('batches', 'people', 'teams', 'mappings', 'periods'):
        assert rebuilt[name] == [{'id': 'a'}, {'id': 'z'}]
    assert rebuilt['records'] == [{'id': 'future', 'occurred_at': '2099-01-01T00:00:00Z'}]
    assert state == before


def test_reconstruction_is_tenant_scoped(archive_db):
    from app.forecasting.archive import capture_material, resolve_material
    one = capture_material(archive_db, material(people=[{'id': 'same', 'name': 'One'}]), tenant_id='one')
    two = capture_material(archive_db, material(people=[{'id': 'same', 'name': 'Two'}]), tenant_id='two')
    assert resolve_material(archive_db, one, tenant_id='one')['people'][0]['name'] == 'One'
    assert resolve_material(archive_db, two, tenant_id='two')['people'][0]['name'] == 'Two'
    with pytest.raises(ValueError):
        resolve_material(archive_db, one, tenant_id='two')


def test_capture_joins_the_callers_rollback(archive_db):
    from app.forecasting.archive import capture_material
    capture_material(archive_db, material(records=[{'id': 'lost'}]), tenant_id='northstar')
    archive_db.rollback()
    assert archive_db.execute('SELECT COUNT(*) FROM forecast_repository_captures').fetchone()[0] == 0
    assert archive_db.execute('SELECT COUNT(*) FROM forecast_repository_row_versions').fetchone()[0] == 0


@pytest.mark.parametrize('table', ['forecast_repository_captures', 'forecast_repository_row_versions'])
@pytest.mark.parametrize('action', ['UPDATE', 'DELETE'])
def test_archive_tables_reject_mutation(archive_db, table, action):
    from app.forecasting.archive import capture_material
    capture_material(archive_db, material(records=[{'id': 'frozen'}]), tenant_id='northstar')
    sql = f'DELETE FROM {table}' if action == 'DELETE' else f'UPDATE {table} SET tenant_id=tenant_id'
    with pytest.raises(sqlite3.IntegrityError, match='immutable'):
        archive_db.execute(sql)


@pytest.mark.parametrize('table', ['forecast_repository_captures', 'forecast_repository_row_versions'])
def test_sqlite_replace_cannot_bypass_archive_immutability(archive_db, table):
    from app.forecasting.archive import capture_material, resolve_material
    state = material(records=[{'id': 'frozen'}])
    ref = capture_material(archive_db, state, tenant_id='northstar')
    archive_db.execute('PRAGMA recursive_triggers=OFF')
    with pytest.raises(sqlite3.IntegrityError, match='immutable'):
        archive_db.execute(f'INSERT OR REPLACE INTO {table} SELECT * FROM {table}')
    assert resolve_material(archive_db, ref, tenant_id='northstar') == state


def test_sqlite_hidden_rowid_replace_cannot_remove_a_different_entity(archive_db):
    from app.forecasting.archive import capture_material, resolve_material
    state = material(records=[{'id': 'frozen'}])
    ref = capture_material(archive_db, state, tenant_id='northstar')
    archive_db.execute('PRAGMA recursive_triggers=OFF')
    with pytest.raises(sqlite3.IntegrityError, match='immutable'):
        archive_db.execute('''INSERT OR REPLACE INTO forecast_repository_row_versions(
            rowid,tenant_id,collection,entity_id,capture_sequence,row_hash,payload)
            SELECT rowid,tenant_id,collection,'different',capture_sequence,row_hash,payload
            FROM forecast_repository_row_versions''')
    assert resolve_material(archive_db, ref, tenant_id='northstar') == state


def test_v1_material_remains_readable_without_aliasing(archive_db):
    from app.forecasting.archive import resolve_material
    legacy = {'repository_capture_version': 1, 'repository_material': material(people=[{'id': 'ada'}])}
    rebuilt = resolve_material(archive_db, legacy, tenant_id='northstar')
    rebuilt['people'][0]['id'] = 'changed'
    assert legacy['repository_material']['people'] == [{'id': 'ada'}]


@pytest.mark.parametrize('replacement', [
    {'archive_sequence': 999}, {'repository_material_hash': 'wrong'},
    {'material_schema_version': 999}, {'repository_capture_version': 999},
])
def test_invalid_archive_references_fail_explicitly(archive_db, replacement):
    from app.forecasting.archive import capture_material, resolve_material
    ref = capture_material(archive_db, material(), tenant_id='northstar')
    with pytest.raises(ValueError):
        resolve_material(archive_db, {**ref, **replacement}, tenant_id='northstar')


def test_missing_archive_row_is_not_silently_replaced_from_current_state(archive_db):
    from app.forecasting.archive import capture_material, resolve_material
    ref = capture_material(archive_db, material(records=[{'id': 'missing'}]), tenant_id='northstar')
    archive_db.execute('DROP TRIGGER forecast_repository_row_versions_immutable_delete')
    archive_db.execute('DELETE FROM forecast_repository_row_versions')
    with pytest.raises(ValueError, match='hash'):
        resolve_material(archive_db, ref, tenant_id='northstar')


def test_capture_requires_existing_transaction(archive_db):
    from app.forecasting.archive import capture_material
    archive_db.commit()
    with pytest.raises(ValueError, match='transaction'):
        capture_material(archive_db, material(), tenant_id='northstar')


def test_invalid_material_does_not_allocate_partial_capture(archive_db):
    from app.forecasting.archive import capture_material
    with pytest.raises(ValueError):
        capture_material(archive_db, material(records=[{'id': 'same'}, {'id': 'same'}]), tenant_id='northstar')
    assert archive_db.execute('SELECT COUNT(*) FROM forecast_repository_captures').fetchone()[0] == 0
