"""Immutable repository captures containing only new or changed row versions.

The caller owns the SQLite transaction and the source receipt. Capture sequence
orders stored states; receipt timestamps still decide which state a reader may use.
"""
from __future__ import annotations

from copy import deepcopy
import json

from .persistence import encode, identity


COLLECTIONS = ('batches', 'records', 'people', 'teams', 'mappings', 'periods')
MATERIAL_SCHEMA_VERSION = 1


def migrate_archive(connection):
    """Add archive storage within the caller's migration transaction."""
    connection.execute('''CREATE TABLE IF NOT EXISTS forecast_repository_captures(
        sequence INTEGER PRIMARY KEY AUTOINCREMENT,
        tenant_id TEXT NOT NULL, material_hash TEXT NOT NULL,
        material_schema_version INTEGER NOT NULL,
        UNIQUE(tenant_id,sequence))''')
    connection.execute('''CREATE TABLE IF NOT EXISTS forecast_repository_row_versions(
        tenant_id TEXT NOT NULL, collection TEXT NOT NULL, entity_id TEXT NOT NULL,
        capture_sequence INTEGER NOT NULL, row_hash TEXT, payload TEXT,
        PRIMARY KEY(tenant_id,collection,entity_id,capture_sequence),
        FOREIGN KEY(tenant_id,capture_sequence)
            REFERENCES forecast_repository_captures(tenant_id,sequence),
        CHECK ((row_hash IS NULL AND payload IS NULL) OR
               (row_hash IS NOT NULL AND payload IS NOT NULL)),
        CHECK (collection IN ('batches','records','people','teams','mappings','periods')))''')
    for table in ('forecast_repository_captures', 'forecast_repository_row_versions'):
        for action in ('UPDATE', 'DELETE'):
            connection.execute(f'''CREATE TRIGGER IF NOT EXISTS {table}_immutable_{action.lower()}
                BEFORE {action} ON {table}
                BEGIN SELECT RAISE(ABORT, 'immutable repository archive'); END''')
    # SQLite REPLACE deletes conflicts without firing DELETE triggers unless the
    # connection enables recursive_triggers. Reject a duplicate key before that
    # deletion so protection also holds for ordinary external SQLite connections.
    connection.execute('''CREATE TRIGGER IF NOT EXISTS forecast_repository_captures_immutable_replace
        BEFORE INSERT ON forecast_repository_captures
        WHEN EXISTS(SELECT 1 FROM forecast_repository_captures WHERE sequence=NEW.sequence)
        BEGIN SELECT RAISE(ABORT, 'immutable repository archive'); END''')
    connection.execute('''CREATE TRIGGER IF NOT EXISTS forecast_repository_row_versions_immutable_replace
        BEFORE INSERT ON forecast_repository_row_versions
        WHEN EXISTS(SELECT 1 FROM forecast_repository_row_versions
            WHERE tenant_id=NEW.tenant_id AND collection=NEW.collection
              AND entity_id=NEW.entity_id AND capture_sequence=NEW.capture_sequence)
        BEGIN SELECT RAISE(ABORT, 'immutable repository archive'); END''')
    connection.execute('''CREATE TRIGGER IF NOT EXISTS forecast_repository_row_versions_immutable_rowid_replace
        BEFORE INSERT ON forecast_repository_row_versions
        WHEN EXISTS(SELECT 1 FROM forecast_repository_row_versions WHERE rowid=NEW.rowid)
        BEGIN SELECT RAISE(ABORT, 'immutable repository archive'); END''')


def _normalized_material(material):
    if not isinstance(material, dict) or set(material) != set(COLLECTIONS):
        raise ValueError('repository material must contain all supported collections')
    result = {}
    for name in COLLECTIONS:
        rows = material[name]
        if not isinstance(rows, list):
            raise ValueError('repository material collections must be lists')
        ids = set()
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get('id'), str) or not row['id']:
                raise ValueError('repository archive rows require string identities')
            if row['id'] in ids:
                raise ValueError('repository archive row identities must be unique')
            ids.add(row['id'])
        result[name] = sorted(rows, key=lambda row: row['id'])
    return result


def _reference(sequence, material_hash):
    return {'repository_capture_version': 2, 'archive_sequence': sequence,
            'repository_material_hash': material_hash,
            'material_schema_version': MATERIAL_SCHEMA_VERSION}


def _latest_versions(connection, tenant_id, sequence, *, with_payload=False):
    columns = 'v.collection,v.entity_id,v.row_hash' + (',v.payload' if with_payload else '')
    return connection.execute(f'''WITH latest AS (
        SELECT collection,entity_id,MAX(capture_sequence) AS capture_sequence
        FROM forecast_repository_row_versions
        WHERE tenant_id=? AND capture_sequence<=? GROUP BY collection,entity_id)
        SELECT {columns} FROM latest AS l
        JOIN forecast_repository_row_versions AS v
          ON v.tenant_id=? AND v.collection=l.collection AND v.entity_id=l.entity_id
          AND v.capture_sequence=l.capture_sequence
        ORDER BY v.collection,v.entity_id''', (tenant_id, sequence, tenant_id)).fetchall()


def capture_material(connection, material, *, tenant_id):
    """Store changed rows and return a compact reference without committing.

    Compare to storage sequence, not receipt-time order. A clock moving backward
    cannot make the changes relative to a different baseline. The first capture
    includes every row, even when a legacy full-payload receipt exists elsewhere.
    """
    if not connection.in_transaction:
        raise ValueError('repository capture requires an existing transaction')
    material = _normalized_material(material)
    material_hash = identity(material)
    previous = connection.execute('''SELECT sequence,material_hash,material_schema_version
        FROM forecast_repository_captures WHERE tenant_id=?
        ORDER BY sequence DESC LIMIT 1''', (tenant_id,)).fetchone()
    if previous is not None:
        if previous[2] != MATERIAL_SCHEMA_VERSION:
            raise ValueError('unsupported repository material schema')
        if previous[1] == material_hash:
            return _reference(previous[0], material_hash)
    old = ({(row[0], row[1]): row[2]
            for row in _latest_versions(connection, tenant_id, previous[0]) if row[2] is not None}
           if previous is not None else {})
    current = {(collection, row['id']): (identity(row), row)
               for collection in COLLECTIONS for row in material[collection]}
    # Serialize before writing so malformed values cannot allocate a partial capture.
    changes = [(collection, entity_id, row_hash, encode(row))
               for (collection, entity_id), (row_hash, row) in current.items()
               if old.get((collection, entity_id)) != row_hash]
    changes.extend((collection, entity_id, None, None)
                   for collection, entity_id in old.keys() - current.keys())
    cursor = connection.execute('''INSERT INTO forecast_repository_captures(
        tenant_id,material_hash,material_schema_version) VALUES(?,?,?)''',
        (tenant_id, material_hash, MATERIAL_SCHEMA_VERSION))
    sequence = cursor.lastrowid
    connection.executemany('''INSERT INTO forecast_repository_row_versions(
        tenant_id,collection,entity_id,capture_sequence,row_hash,payload) VALUES(?,?,?,?,?,?)''',
        [(tenant_id, collection, entity_id, sequence, row_hash, payload)
         for collection, entity_id, row_hash, payload in changes])
    return _reference(sequence, material_hash)


def resolve_material(connection, payload, *, tenant_id):
    """Resolve one selected receipt; never substitute current repository data."""
    version = payload.get('repository_capture_version')
    if version == 1:
        if not isinstance(payload.get('repository_material'), dict):
            raise ValueError('invalid legacy repository material')
        return deepcopy(payload['repository_material'])
    if version != 2 or payload.get('material_schema_version') != MATERIAL_SCHEMA_VERSION:
        raise ValueError('unsupported repository archive version or material schema')
    sequence = payload.get('archive_sequence')
    if type(sequence) is not int or sequence < 1:
        raise ValueError('invalid repository archive sequence')
    capture = connection.execute('''SELECT material_hash,material_schema_version
        FROM forecast_repository_captures WHERE tenant_id=? AND sequence=?''',
        (tenant_id, sequence)).fetchone()
    if capture is None:
        raise ValueError('repository archive capture is missing for tenant')
    if capture[1] != MATERIAL_SCHEMA_VERSION:
        raise ValueError('unsupported repository material schema')
    if capture[0] != payload.get('repository_material_hash'):
        raise ValueError('repository archive reference hash mismatch')
    material = {name: [] for name in COLLECTIONS}
    for collection, entity_id, row_hash, encoded in _latest_versions(
            connection, tenant_id, sequence, with_payload=True):
        # Select the latest version before discarding tombstones, or a deleted
        # row's preceding value would reappear in historical reconstruction.
        if encoded is None:
            continue
        row = json.loads(encoded)
        if not isinstance(row, dict) or row.get('id') != entity_id or identity(row) != row_hash:
            raise ValueError('repository archive row hash or identity mismatch')
        material[collection].append(row)
    if identity(material) != capture[0]:
        raise ValueError('repository archive material hash mismatch')
    return material
