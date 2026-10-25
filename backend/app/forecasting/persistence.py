"""SQLite persistence with append-only evidence and fenced durable job claims.

Separate connections and BEGIN IMMEDIATE serialize claim/publication decisions across
processes. Immutable-table triggers also protect against accidental ad-hoc updates.
"""
from __future__ import annotations

from contextlib import contextmanager, nullcontext
from datetime import datetime, timedelta, timezone
import hashlib
from copy import deepcopy
import fcntl
import os
import json
from pathlib import Path
import sqlite3
import threading
import uuid


_operation_holds = threading.local()


class ImmutableConflict(ValueError):
    pass


def iso(value: str | datetime) -> str:
    if not isinstance(value, (str, datetime)):
        raise ValueError('timestamp must be an ISO string or datetime')
    dt = datetime.fromisoformat(value.replace('Z', '+00:00')) if isinstance(value, str) else value
    if dt.tzinfo is None:
        raise ValueError('timezone-aware UTC timestamp required')
    return dt.astimezone(timezone.utc).isoformat(timespec='microseconds').replace('+00:00', 'Z')


def later(value: str, seconds: int) -> str:
    return iso(datetime.fromisoformat(iso(value).replace('Z', '+00:00')) + timedelta(seconds=seconds))


def encode(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def identity(value) -> str:
    return hashlib.sha256(encode(value).encode()).hexdigest()


class ForecastStore:
    def __init__(self, path: Path | str, *, on_input=None):
        self.path = str(path)
        self.on_input = on_input
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.migrate()

    @contextmanager
    def transaction(self):
        conn = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA foreign_keys=ON')
        conn.execute('PRAGMA busy_timeout=10000')
        try:
            conn.execute('BEGIN IMMEDIATE')
            yield conn
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    @contextmanager
    def read_transaction(self):
        """Read one committed snapshot without reserving SQLite's writer lock."""
        conn = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA query_only=ON')
        conn.execute('PRAGMA busy_timeout=10000')
        try:
            conn.execute('BEGIN')
            yield conn
        finally:
            conn.rollback()
            conn.close()

    @contextmanager
    def operation(self, *, exclusive=False):
        # Shared across threads and processes. A reset waits for whole forecast
        # operations, including builders that temporarily hold no SQL transaction.
        lock_path = str(Path(self.path).resolve()) + '.forecast.lock'
        holds = getattr(_operation_holds, 'paths', None)
        if holds is None:
            holds = _operation_holds.paths = {}
        if lock_path in holds:
            if exclusive and not holds[lock_path]:
                raise RuntimeError('cannot upgrade an active forecast operation to reset')
            yield
            return
        descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
            holds[lock_path] = exclusive
            yield
        finally:
            holds.pop(lock_path, None)
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)

    def migrate(self, *, connection=None):
        from .archive import migrate_archive

        with (self.transaction() if connection is None else nullcontext(connection)) as c:
            c.execute('CREATE TABLE IF NOT EXISTS forecast_schema_versions(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)')
            c.execute('''CREATE TABLE IF NOT EXISTS forecast_inputs(
                id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, kind TEXT NOT NULL, source_id TEXT NOT NULL,
                revision TEXT NOT NULL, available_at TEXT NOT NULL, received_at TEXT NOT NULL, payload TEXT NOT NULL,
                UNIQUE(tenant_id,kind,source_id,revision))''')
            c.execute('''CREATE INDEX IF NOT EXISTS forecast_inputs_source_cutoff
                ON forecast_inputs(tenant_id,kind,source_id,available_at,received_at)''')
            c.execute('''CREATE TABLE IF NOT EXISTS forecast_input_snapshots(
                id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, cutoff TEXT NOT NULL, payload TEXT NOT NULL)''')
            c.execute('''CREATE TABLE IF NOT EXISTS forecast_jobs(
                sequence INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE NOT NULL, tenant_id TEXT NOT NULL,
                idempotency_key TEXT NOT NULL, snapshot_id TEXT NOT NULL REFERENCES forecast_input_snapshots(id),
                run_id TEXT UNIQUE NOT NULL, created_at TEXT NOT NULL, scheduled_for TEXT,
                status TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0, max_attempts INTEGER NOT NULL DEFAULT 3,
                next_attempt_at TEXT NOT NULL, lease_token TEXT, lease_owner TEXT, lease_until TEXT,
                last_error TEXT, completed_at TEXT, UNIQUE(tenant_id,idempotency_key))''')
            c.execute('''CREATE TABLE IF NOT EXISTS forecast_runs(
                id TEXT PRIMARY KEY, job_id TEXT NOT NULL UNIQUE REFERENCES forecast_jobs(id),
                snapshot_id TEXT NOT NULL REFERENCES forecast_input_snapshots(id), generated_at TEXT NOT NULL, bundle TEXT NOT NULL)''')
            c.execute('''CREATE TABLE IF NOT EXISTS forecast_publications(
                tenant_id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES forecast_runs(id),
                sequence INTEGER NOT NULL, published_at TEXT NOT NULL)''')
            c.execute('''CREATE TABLE IF NOT EXISTS forecast_scenarios(
                id TEXT PRIMARY KEY, parent_run_id TEXT NOT NULL REFERENCES forecast_runs(id),
                created_at TEXT NOT NULL, drivers TEXT NOT NULL, bundle TEXT NOT NULL)''')
            job_columns = {r[1] for r in c.execute('PRAGMA table_info(forecast_jobs)')}
            for name, sqltype in [('job_type', "TEXT NOT NULL DEFAULT 'refresh'"), ('parent_run_id', 'TEXT'), ('job_payload', 'TEXT')]:
                if name not in job_columns:
                    c.execute(f'ALTER TABLE forecast_jobs ADD COLUMN {name} {sqltype}')
            c.execute("CREATE TRIGGER IF NOT EXISTS forecast_jobs_immutable_payload BEFORE UPDATE OF id,tenant_id,idempotency_key,snapshot_id,run_id,created_at,scheduled_for,job_type,parent_run_id,job_payload ON forecast_jobs BEGIN SELECT RAISE(ABORT, 'immutable forecast job payload'); END")
            columns = {r[1] for r in c.execute('PRAGMA table_info(forecast_publications)')}
            if 'information_cutoff' not in columns:
                c.execute("ALTER TABLE forecast_publications ADD COLUMN information_cutoff TEXT NOT NULL DEFAULT ''")
                c.execute('UPDATE forecast_publications SET information_cutoff=(SELECT cutoff FROM forecast_input_snapshots WHERE id=(SELECT snapshot_id FROM forecast_runs WHERE id=forecast_publications.run_id))')
            for table in ('forecast_inputs', 'forecast_input_snapshots', 'forecast_runs', 'forecast_scenarios'):
                for action in ('UPDATE', 'DELETE'):
                    c.execute(f"CREATE TRIGGER IF NOT EXISTS {table}_immutable_{action.lower()} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT, 'immutable forecast record'); END")
            c.execute("INSERT OR IGNORE INTO forecast_schema_versions VALUES(1, strftime('%Y-%m-%dT%H:%M:%fZ','now'))")
            c.execute("INSERT OR IGNORE INTO forecast_schema_versions VALUES(2, strftime('%Y-%m-%dT%H:%M:%fZ','now'))")
            c.execute("INSERT OR IGNORE INTO forecast_schema_versions VALUES(3, strftime('%Y-%m-%dT%H:%M:%fZ','now'))")
            migrate_archive(c)
            c.execute("INSERT OR IGNORE INTO forecast_schema_versions VALUES(4, strftime('%Y-%m-%dT%H:%M:%fZ','now'))")

    def _append_input(self, c, kind, source_id, revision, payload, available_at, received_at, tenant_id):
        value = encode(payload)
        old = c.execute('SELECT * FROM forecast_inputs WHERE tenant_id=? AND kind=? AND source_id=? AND revision=?', (tenant_id, kind, source_id, str(revision))).fetchone()
        if old:
            if old['payload'] != value or old['available_at'] != iso(available_at):
                raise ImmutableConflict('source revision already exists with different content')
            return self._input(old)
        row_id = 'input_' + uuid.uuid4().hex
        c.execute('INSERT INTO forecast_inputs VALUES(?,?,?,?,?,?,?,?)', (row_id, tenant_id, kind, source_id, str(revision), iso(available_at), iso(received_at or available_at), value))
        record = self._input(c.execute('SELECT * FROM forecast_inputs WHERE id=?', (row_id,)).fetchone())
        if self.on_input is not None:
            self.on_input(c, record)
        return record

    def append_input(self, kind, source_id, revision, payload, *, available_at, received_at=None, tenant_id='northstar'):
        with self.transaction() as c:
            return self._append_input(c, kind, source_id, revision, payload, available_at, received_at, tenant_id)

    @staticmethod
    def _input(row):
        result = dict(row)
        result['payload'] = json.loads(result['payload'])
        return result

    def find_input(self, kind, source_id, revision, *, tenant_id='northstar'):
        with self.read_transaction() as c:
            row = c.execute('SELECT * FROM forecast_inputs WHERE tenant_id=? AND kind=? AND source_id=? AND revision=?', (tenant_id, kind, source_id, str(revision))).fetchone()
        return self._input(row) if row else None

    def input_records(self, cutoff, tenant_id='northstar', *, latest=False, kinds=None, source_id=None, exclude_kinds=()):
        """Select usable source revisions before loading their JSON payloads.

        Latest selection retains the historical API's first-source encounter
        order, including rowid as the final tie breaker for equal timestamps.
        """
        cutoff = iso(cutoff)
        conditions = ['tenant_id=?', 'available_at<=?', 'received_at<=?']
        params = [tenant_id, cutoff, cutoff]
        if kinds is not None:
            kinds = (kinds,) if isinstance(kinds, str) else tuple(kinds)
            if not kinds:
                return []
            conditions.append('kind IN (' + ','.join('?' for _ in kinds) + ')')
            params.extend(kinds)
        if exclude_kinds:
            excluded = (exclude_kinds,) if isinstance(exclude_kinds, str) else tuple(exclude_kinds)
            conditions.append('kind NOT IN (' + ','.join('?' for _ in excluded) + ')')
            params.extend(excluded)
        if source_id is not None:
            conditions.append('source_id=?')
            params.append(source_id)
        where = ' AND '.join(conditions)
        if latest:
            # Window only metadata: repository captures can be large, and old
            # payloads must not be read/decoded merely to discard their revisions.
            query = f'''WITH ranked AS (
                SELECT rowid AS input_rowid,
                    ROW_NUMBER() OVER (
                        PARTITION BY kind,source_id
                        ORDER BY available_at DESC,received_at DESC,rowid DESC) AS latest_rank,
                    FIRST_VALUE(rowid) OVER (
                        PARTITION BY kind,source_id
                        ORDER BY available_at,received_at,rowid) AS first_rowid
                FROM forecast_inputs WHERE {where})
                SELECT current.* FROM ranked
                JOIN forecast_inputs AS current ON current.rowid=ranked.input_rowid
                JOIN forecast_inputs AS first ON first.rowid=ranked.first_rowid
                WHERE ranked.latest_rank=1
                ORDER BY first.available_at,first.received_at,first.rowid'''
        else:
            query = f'''SELECT * FROM forecast_inputs WHERE {where}
                ORDER BY available_at,received_at,rowid'''
        with self.read_transaction() as c:
            rows = c.execute(query, params).fetchall()
        return [self._input(r) for r in rows]

    def save_snapshot(self, snapshot):
        value = encode(snapshot)
        with self.transaction() as c:
            old = c.execute('SELECT payload FROM forecast_input_snapshots WHERE id=?', (snapshot['id'],)).fetchone()
            if old and old[0] != value:
                raise ImmutableConflict('snapshot cannot change')
            c.execute('INSERT OR IGNORE INTO forecast_input_snapshots VALUES(?,?,?,?)', (snapshot['id'], snapshot['tenant_id'], iso(snapshot['information_cutoff']), value))
        return json.loads(value)

    def get_snapshot(self, snapshot_id):
        with self.read_transaction() as c:
            row = c.execute('SELECT payload FROM forecast_input_snapshots WHERE id=?', (snapshot_id,)).fetchone()
        if not row:
            raise KeyError(snapshot_id)
        return json.loads(row[0])

    @staticmethod
    def _job(row):
        if not row:
            return None
        value = dict(row)
        value['job_payload'] = json.loads(value['job_payload']) if value.get('job_payload') else None
        return value

    def enqueue(self, tenant_id, idempotency_key, snapshot_id, now, *, scheduled_for=None, job_type='refresh', parent_run_id=None, job_payload=None):
        with self.transaction() as c:
            old = c.execute('SELECT * FROM forecast_jobs WHERE tenant_id=? AND idempotency_key=?', (tenant_id, idempotency_key)).fetchone()
            if old:
                return self._job(old)
            job_id, run_id = 'job_' + uuid.uuid4().hex, ('scenario_' if job_type == 'scenario' else 'run_') + uuid.uuid4().hex
            c.execute('''INSERT INTO forecast_jobs(id,tenant_id,idempotency_key,snapshot_id,run_id,created_at,scheduled_for,status,next_attempt_at,job_type,parent_run_id,job_payload)
                VALUES(?,?,?,?,?,?,?,'queued',?,?,?,?)''', (job_id, tenant_id, idempotency_key, snapshot_id, run_id, iso(now), iso(scheduled_for) if scheduled_for else None, iso(now), job_type, parent_run_id, encode(job_payload) if job_payload is not None else None))
            return self._job(c.execute('SELECT * FROM forecast_jobs WHERE id=?', (job_id,)).fetchone())

    def get_job(self, job_id):
        with self.read_transaction() as c:
            row = c.execute('SELECT * FROM forecast_jobs WHERE id=?', (job_id,)).fetchone()
        if not row:
            raise KeyError(job_id)
        return self._job(row)

    def find_job(self, tenant_id, key):
        with self.read_transaction() as c:
            return self._job(c.execute('SELECT * FROM forecast_jobs WHERE tenant_id=? AND idempotency_key=?', (tenant_id, key)).fetchone())

    def claim(self, owner, now, *, lease_seconds=300, job_id=None):
        now = iso(now)
        with self.transaction() as c:
            c.execute("UPDATE forecast_jobs SET status='failed',last_error='lease expired after maximum attempts',lease_token=NULL,lease_owner=NULL,lease_until=NULL WHERE status='running' AND lease_until<=? AND attempts>=max_attempts", (now,))
            row = c.execute("SELECT * FROM forecast_jobs WHERE attempts<max_attempts AND ((status='queued' AND next_attempt_at<=?) OR (status='running' AND lease_until<=?)) AND (? IS NULL OR id=?) ORDER BY sequence LIMIT 1", (now, now, job_id, job_id)).fetchone()
            if not row:
                return None
            c.execute("UPDATE forecast_jobs SET status='running',attempts=attempts+1,lease_token=?,lease_owner=?,lease_until=? WHERE id=?", (uuid.uuid4().hex, owner, later(now, lease_seconds), row['id']))
            return self._job(c.execute('SELECT * FROM forecast_jobs WHERE id=?', (row['id'],)).fetchone())

    def find_run_job(self, run_id):
        with self.read_transaction() as c:
            return self._job(c.execute('SELECT * FROM forecast_jobs WHERE run_id=?', (run_id,)).fetchone())

    def list_jobs(self, *, job_type=None, tenant_id='northstar'):
        with self.read_transaction() as c:
            rows = c.execute('SELECT * FROM forecast_jobs WHERE tenant_id=? AND (? IS NULL OR job_type=?) ORDER BY sequence', (tenant_id, job_type, job_type)).fetchall()
        return [self._job(row) for row in rows]

    def heartbeat(self, job_id, token, now, *, lease_seconds=300):
        with self.transaction() as c:
            return bool(c.execute("UPDATE forecast_jobs SET lease_until=? WHERE id=? AND status='running' AND lease_token=? AND lease_until>?", (later(now, lease_seconds), job_id, token, iso(now))).rowcount)

    def fail(self, job_id, token, error, now, *, retry_seconds=5):
        with self.transaction() as c:
            row = c.execute("SELECT * FROM forecast_jobs WHERE id=? AND status='running' AND lease_token=? AND lease_until>?", (job_id, token, iso(now))).fetchone()
            if not row:
                return False
            state = 'failed' if row['attempts'] >= row['max_attempts'] else 'queued'
            c.execute('UPDATE forecast_jobs SET status=?,last_error=?,next_attempt_at=?,lease_token=NULL,lease_owner=NULL,lease_until=NULL WHERE id=?', (state, str(error)[:2000], later(now, retry_seconds), job_id))
            return True

    def complete(self, job_id, token, bundle, now, *, issued_targets=()):
        bundle = deepcopy(bundle)
        with self.transaction() as c:
            row = c.execute("SELECT * FROM forecast_jobs WHERE id=? AND status='running' AND lease_token=? AND lease_until>?", (job_id, token, iso(now))).fetchone()
            if not row:
                return False
            if row['job_type'] == 'refresh':
                cutoff = c.execute('SELECT cutoff FROM forecast_input_snapshots WHERE id=?', (row['snapshot_id'],)).fetchone()[0]
                current = c.execute('SELECT information_cutoff,sequence FROM forecast_publications WHERE tenant_id=?', (row['tenant_id'],)).fetchone()
                publishes = current is None or (cutoff, row['sequence']) > (current['information_cutoff'], current['sequence'])
                for view in bundle.get('views', []):
                    view.setdefault('publication', {})['issued_at'] = iso(now)
                    # A completed issuance can lose the publication fence. Its
                    # immutable receipt must not claim that it was ever served.
                    view['publication']['published_at'] = iso(now) if publishes else None
            encoded = encode(bundle)
            if row['job_type'] == 'interpretation':
                native = json.loads(row['job_payload'])['envelope']
                self._append_input(c, 'evidence', native['source_id'], str(native['revision']), bundle, native['available_at'], row['created_at'], row['tenant_id'])
            elif row['job_type'] == 'scenario':
                payload = json.loads(row['job_payload'])
                c.execute('INSERT INTO forecast_scenarios VALUES(?,?,?,?,?)', (row['run_id'], row['parent_run_id'], iso(now), encode(payload['drivers']), encoded))
            if row['job_type'] != 'refresh':
                c.execute("UPDATE forecast_jobs SET status='succeeded',completed_at=?,lease_token=NULL,lease_owner=NULL,lease_until=NULL WHERE id=?", (iso(now), job_id))
                return True
            c.execute('INSERT INTO forecast_runs VALUES(?,?,?,?,?)', (row['run_id'], job_id, row['snapshot_id'], iso(now), encoded))
            for target in issued_targets:
                target = dict(target, issued_at=iso(now))
                self._append_input(c, 'issued_targets', target['target_id'], '1', target, now, now, row['tenant_id'])
            c.execute("UPDATE forecast_jobs SET status='succeeded',completed_at=?,lease_token=NULL,lease_owner=NULL,lease_until=NULL WHERE id=?", (iso(now), job_id))
            c.execute('''INSERT INTO forecast_publications(tenant_id,run_id,sequence,published_at,information_cutoff) VALUES(?,?,?,?,?) ON CONFLICT(tenant_id) DO UPDATE
                SET run_id=excluded.run_id,sequence=excluded.sequence,published_at=excluded.published_at,information_cutoff=excluded.information_cutoff
                WHERE excluded.information_cutoff>forecast_publications.information_cutoff OR (excluded.information_cutoff=forecast_publications.information_cutoff AND excluded.sequence>forecast_publications.sequence)''', (row['tenant_id'], row['run_id'], row['sequence'], iso(now), cutoff))
            return True

    def weekly_history_inputs(self, cutoff, tenant_id='northstar', *, scope_type, scope_id):
        """Decode scoped targets and all truth receipts; retain the legacy global revision inputs."""
        cutoff = iso(cutoff)
        with self.read_transaction() as c:
            rows = c.execute("""SELECT * FROM forecast_inputs
                WHERE tenant_id=? AND available_at<=? AND received_at<=?
                  AND (kind='truth_revisions' OR (kind='issued_targets'
                    AND json_extract(payload,'$.scope_type')=?
                    AND json_extract(payload,'$.scope_id')=?))
                ORDER BY available_at,received_at,rowid""",
                (tenant_id, cutoff, cutoff, scope_type, scope_id)).fetchall()
            # Python bool semantics, including historical non-boolean JSON values.
            synthetic = c.execute("""SELECT EXISTS(SELECT 1 FROM forecast_inputs
                WHERE tenant_id=? AND kind='issued_targets' AND available_at<=? AND received_at<=?
                AND CASE json_type(payload,'$.is_synthetic')
                    WHEN 'true' THEN 1 WHEN 'false' THEN 0 WHEN 'null' THEN 0
                    WHEN 'integer' THEN json_extract(payload,'$.is_synthetic')<>0
                    WHEN 'real' THEN json_extract(payload,'$.is_synthetic')<>0
                    WHEN 'text' THEN json_extract(payload,'$.is_synthetic')<>''
                    WHEN 'array' THEN json_array_length(payload,'$.is_synthetic')>0
                    WHEN 'object' THEN EXISTS(SELECT 1 FROM json_each(payload,'$.is_synthetic'))
                    ELSE 0 END)""", (tenant_id, cutoff, cutoff)).fetchone()[0]
        return {'records': [self._input(row) for row in rows], 'synthetic': bool(synthetic)}

    def weekly_publication_metadata(self, run_ids, scope_type, scope_id):
        """Read only matching immutable serving-run publication receipts and job tie-breakers."""
        result = {}
        with self.read_transaction() as c:
            for run_id in dict.fromkeys(run_ids):
                row = c.execute("""SELECT json_extract(view.value,'$.publication') AS publication,
                        jobs.sequence AS sequence
                    FROM forecast_runs AS runs JOIN forecast_jobs AS jobs ON jobs.id=runs.job_id,
                        json_each(runs.bundle,'$.views') AS view
                    WHERE runs.id=? AND json_extract(view.value,'$.scope.type')=?
                      AND json_extract(view.value,'$.scope.id')=? LIMIT 1""",
                    (run_id, scope_type, scope_id)).fetchone()
                if row is not None:
                    publication = json.loads(row['publication']) if row['publication'] is not None else {}
                    result[run_id] = {'published_at': publication.get('published_at'), 'sequence': row['sequence']}
        return result

    def weekly_current_view(self, scope_type, scope_id, tenant_id='northstar'):
        """Read only the currently served scoped weekly outlook, preserving raw JSON numbers."""
        with self.read_transaction() as c:
            row = c.execute("""SELECT json_extract(view.value,'$.scope') AS scope,
                    json_extract(view.value,'$.target') AS target,
                    json_extract(view.value,'$.weekly') AS weekly,
                    json_extract(view.value,'$.publication') AS publication,
                    json_extract(view.value,'$.run_id') AS run_id
                FROM forecast_publications AS current JOIN forecast_runs AS runs ON runs.id=current.run_id,
                    json_each(runs.bundle,'$.views') AS view
                WHERE current.tenant_id=? AND json_extract(view.value,'$.scope.type')=?
                  AND json_extract(view.value,'$.scope.id')=? LIMIT 1""",
                (tenant_id, scope_type, scope_id)).fetchone()
        if row is None:
            return None
        return {key: (json.loads(row[key]) if key != 'run_id' and row[key] is not None else row[key])
                for key in ('scope', 'target', 'weekly', 'publication', 'run_id') if row[key] is not None}

    def publication(self, tenant_id='northstar'):
        with self.read_transaction() as c:
            row = c.execute('SELECT * FROM forecast_publications WHERE tenant_id=?', (tenant_id,)).fetchone()
        return dict(row) if row else None

    def get_run(self, run_id):
        with self.read_transaction() as c:
            row = c.execute('SELECT * FROM forecast_runs WHERE id=?', (run_id,)).fetchone()
        if not row:
            raise KeyError(run_id)
        result = dict(row)
        result['bundle'] = json.loads(result['bundle'])
        return result

    def save_scenario(self, parent_run_id, drivers, bundle, now):
        scenario_id = bundle.get('scenario_id') or 'scenario_' + uuid.uuid4().hex
        with self.transaction() as c:
            c.execute('INSERT INTO forecast_scenarios VALUES(?,?,?,?,?)', (scenario_id, parent_run_id, iso(now), encode(drivers), encode(bundle)))
        return self.get_scenario(scenario_id)

    def get_scenario(self, scenario_id):
        with self.read_transaction() as c:
            row = c.execute('SELECT * FROM forecast_scenarios WHERE id=?', (scenario_id,)).fetchone()
        if not row:
            raise KeyError(scenario_id)
        result = dict(row)
        for key in ('drivers', 'bundle'):
            result[key] = json.loads(result[key])
        return result

    def get_issued_quarter_inputs(self, run_id):
        """Read only the immutable fields needed by the native quarter adapter.

        SQLite scans the archived JSON, but Python never decodes learning history,
        calculations or daily paths. Quarter objects remain opaque JSON fragments:
        rebuilding their numeric scalars with SQLite JSON can change cent rounding.
        Missing keys stay missing, particularly membership dates and revision IDs.
        """
        def value(part):
            if part['type'] in ('array', 'object'):
                return json.loads(part['value'])
            if part['type'] in ('true', 'false'):
                return part['type'] == 'true'
            return part['value']

        with self.read_transaction() as c:
            metadata = c.execute('''SELECT id,job_id,snapshot_id,generated_at
                FROM forecast_runs WHERE id=?''', (run_id,)).fetchone()
            if metadata is None:
                raise KeyError(run_id)
            bundle = {part['key']: value(part) for part in c.execute('''
                SELECT part.key,part.type,part.value FROM forecast_runs AS run,
                    json_each(run.bundle) AS part
                WHERE run.id=? AND part.key IN ('run_id','procedure_version')''', (run_id,))}
            views = {}
            for part in c.execute('''
                SELECT view.key AS view_index,part.key,part.type,part.value
                FROM forecast_runs AS run,json_each(run.bundle,'$.views') AS view,
                    json_each(view.value) AS part
                WHERE run.id=? AND part.key IN ('scope','quarter_outlook','included_drivers',
                    'target','publication','run_id','snapshot_id')
                ORDER BY CAST(view.key AS INTEGER)''', (run_id,)):
                views.setdefault(part['view_index'], {})[part['key']] = value(part)
            bundle['views'] = list(views.values())
            snapshot_id = metadata['snapshot_id']
            if c.execute('SELECT 1 FROM forecast_input_snapshots WHERE id=?', (snapshot_id,)).fetchone() is None:
                raise KeyError(snapshot_id)
            snapshot = {}
            for part in c.execute('''
                SELECT part.key,part.type,
                    CASE WHEN part.type='array' AND part.key IN ('observations','source_revisions')
                    THEN (SELECT json_group_array(json((
                        SELECT json_group_object(field.key,field.value)
                        FROM json_each(entry.value) AS field
                        WHERE (part.key='observations' AND field.key IN ('person_id','team_id','date'))
                           OR (part.key='source_revisions' AND field.key IN ('kind','id'))
                    ))) FROM json_each(part.value) AS entry)
                    ELSE part.value END AS value
                FROM forecast_input_snapshots AS snapshot,json_each(snapshot.payload) AS part
                WHERE snapshot.id=? AND part.key IN (
                    'observations','memberships','source_revisions','is_synthetic',
                    'repository_revision','tenant_id','information_cutoff')''', (snapshot_id,)):
                snapshot[part['key']] = value(part)
        return {**dict(metadata), 'bundle': bundle}, snapshot
