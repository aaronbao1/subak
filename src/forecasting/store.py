"""Content-addressed immutable artifacts with current tenant/source authorization.

This local reference store expects an authenticated caller to supply current source
permissions. It does not infer authority from claims inside an artifact or request.
"""
from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any, Iterable


class AccessDenied(PermissionError):
    pass


class ArtifactCorrupt(ValueError):
    pass


def _json_default(value: Any) -> Any:
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError('nonfinite decimal')
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if is_dataclass(value):
        return asdict(value)
    raise TypeError('unsupported JSON value: ' + type(value).__name__)


def canonical_json(value: Any) -> str:
    return json.dumps(value, default=_json_default, sort_keys=True,
                      separators=(',', ':'), ensure_ascii=False, allow_nan=False)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode('utf-8')).hexdigest()


class ArtifactStore:
    def __init__(self, path: str | Path):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute('CREATE TABLE IF NOT EXISTS artifacts ('
                         'artifact_id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, '
                         'document TEXT NOT NULL, revoked INTEGER NOT NULL DEFAULT 0, reason TEXT, stored_at TEXT)')
            if 'stored_at' not in {row[1] for row in conn.execute('PRAGMA table_info(artifacts)')}:
                conn.execute('ALTER TABLE artifacts ADD COLUMN stored_at TEXT')

    def _connect(self):
        return sqlite3.connect(self.path, timeout=30)

    def put(self, tenant_id: str, kind: str, payload: Any,
            required_sources: Iterable[str] = (), *, required_artifacts: Iterable[str] = ()) -> str:
        if not isinstance(tenant_id, str) or not tenant_id.strip() or not isinstance(kind, str) or not kind.strip():
            raise ValueError('nonempty tenant and artifact kind required')
        sources = set(required_sources)
        dependencies = tuple(sorted(set(required_artifacts)))
        if any(not isinstance(ref,str) or not ref for ref in dependencies):
            raise ValueError('valid material artifact identities required')
        pending,visited = list(dependencies),set()
        while pending:
            ref = pending.pop()
            if ref in visited: continue
            visited.add(ref)
            dependency = self._read(tenant_id,ref)
            sources.update(dependency['required_sources'])
            pending.extend(dependency.get('required_artifacts',()))
        sources = sorted(sources)
        if any(not isinstance(source, str) or not source for source in sources):
            raise ValueError('invalid source identity')
        document_fields = {'schema_version':'1.0','tenant_id':tenant_id,
                           'kind':kind,'required_sources':sources,'payload':payload}
        if dependencies: document_fields['required_artifacts'] = dependencies
        document = canonical_json(document_fields)
        artifact_id = hashlib.sha256(document.encode('utf-8')).hexdigest()
        with self._connect() as conn:
            conn.execute('INSERT OR IGNORE INTO artifacts(artifact_id,tenant_id,document,stored_at) VALUES (?,?,?,?)',
                         (artifact_id, tenant_id, document, datetime.now(timezone.utc).isoformat()))
        return artifact_id

    def get(self, tenant_id: str, artifact_id: str, *, allowed_sources: Iterable[str]) -> dict:
        sources = frozenset(allowed_sources)
        pending,visited = [artifact_id],set()
        result = None
        while pending:
            ref = pending.pop()
            if ref in visited: continue
            visited.add(ref)
            value = self._read(tenant_id,ref)
            if not set(value['required_sources']).issubset(sources):
                raise AccessDenied('current source access required')
            if ref == artifact_id: result = value
            pending.extend(value.get('required_artifacts',()))
        return result

    def _read(self, tenant_id: str, artifact_id: str) -> dict:
        with self._connect() as conn:
            row = conn.execute('SELECT document,revoked,stored_at FROM artifacts WHERE tenant_id=? AND artifact_id=?',
                               (tenant_id, artifact_id)).fetchone()
        if row is None or row[1]:
            raise AccessDenied('artifact unavailable for current tenant/access policy')
        document = row[0]
        if hashlib.sha256(document.encode('utf-8')).hexdigest() != artifact_id:
            raise ArtifactCorrupt('artifact content digest mismatch')
        value = json.loads(document)
        if value['tenant_id'] != tenant_id:
            raise AccessDenied('current tenant access required')
        # Storage metadata is not fabricated for pre-migration artifacts.
        value['stored_at']=row[2]
        return value

    def revoke(self, tenant_id: str, artifact_id: str, *, reason: str) -> None:
        if not reason:
            raise ValueError('revocation reason required')
        with self._connect() as conn:
            cursor = conn.execute('UPDATE artifacts SET revoked=1,reason=? WHERE tenant_id=? AND artifact_id=?',
                                  (reason, tenant_id, artifact_id))
            if cursor.rowcount != 1:
                raise AccessDenied('artifact unavailable for current tenant')
