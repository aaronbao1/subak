from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import pytest

from forecasting.store import ArtifactStore, AccessDenied, ArtifactCorrupt


def test_store_preserves_exact_immutable_outputs_across_restart(tmp_path):
    store = ArtifactStore(tmp_path / 'artifacts.sqlite')
    payload = {'value': Decimal('0.0000123'), 'schema_version': '1.0'}
    artifact_id = store.put('tenant-a', 'forecast', payload, required_sources=('billing',))
    payload['value'] = Decimal('999')
    reopened = ArtifactStore(tmp_path / 'artifacts.sqlite')
    assert reopened.get('tenant-a', artifact_id, allowed_sources={'billing'})['payload']['value'] == '0.0000123'
    assert reopened.put('tenant-a', 'forecast', {'value': '0.0000123', 'schema_version': '1.0'}, required_sources=('billing',)) == artifact_id


def test_tenant_and_current_source_access_guard_cached_artifact(tmp_path):
    store = ArtifactStore(tmp_path / 'artifacts.sqlite')
    key = store.put('a', 'forecast', {'total': '3'}, required_sources=('private',))
    with pytest.raises(AccessDenied):
        store.get('b', key, allowed_sources={'private'})
    with pytest.raises(AccessDenied):
        store.get('a', key, allowed_sources=set())
    assert store.get('a', key, allowed_sources={'private'})['payload']['total'] == '3'
    store.revoke('a', key, reason='retention deletion')
    with pytest.raises(AccessDenied):
        store.get('a', key, allowed_sources={'private'})


def test_atomic_dedup_and_hash_integrity(tmp_path):
    store = ArtifactStore(tmp_path / 'artifacts.sqlite')
    with ThreadPoolExecutor(max_workers=4) as pool:
        ids = list(pool.map(lambda _: store.put('a', 'forecast', {'v': 1}), range(12)))
    assert len(set(ids)) == 1
    import sqlite3
    with sqlite3.connect(store.path) as conn:
        conn.execute('UPDATE artifacts SET document=? WHERE artifact_id=?', ('{}', ids[0]))
    with pytest.raises(ArtifactCorrupt):
        store.get('a', ids[0], allowed_sources=set())


def test_nonfinite_json_and_unsafe_identifiers_rejected(tmp_path):
    store = ArtifactStore(tmp_path / 'artifacts.sqlite')
    with pytest.raises(ValueError):
        store.put('a', 'forecast', {'v': float('nan')})
    with pytest.raises(ValueError):
        store.put('', 'forecast', {'v': 1})


def test_original_storage_time_survives_idempotent_write_and_schema_upgrade(tmp_path):
    from datetime import datetime
    import sqlite3
    path=tmp_path/'old.sqlite'
    with sqlite3.connect(path) as c:
        c.execute('CREATE TABLE artifacts (artifact_id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, document TEXT NOT NULL, revoked INTEGER NOT NULL DEFAULT 0, reason TEXT)')
    store=ArtifactStore(path)
    key=store.put('a','forecast',{'x':'0.01'})
    original=store.get('a',key,allowed_sources=set())
    assert datetime.fromisoformat(original['stored_at']).tzinfo is not None
    assert store.put('a','forecast',{'x':'0.01'})==key
    assert ArtifactStore(path).get('a',key,allowed_sources=set())['stored_at']==original['stored_at']
