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
        with (self.transaction() if connection is None else nullcontext(connection)) as c:
            c.execute('CREATE TABLE IF NOT EXISTS forecast_schema_versions(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)')
            c.execute('''CREATE TABLE IF NOT EXISTS forecast_inputs(
                id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, kind TEXT NOT NULL, source_id TEXT NOT NULL,
                revision TEXT NOT NULL, available_at TEXT NOT NULL, received_at TEXT NOT NULL, payload TEXT NOT NULL,
                UNIQUE(tenant_id,kind,source_id,revision))''')
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
        with self.transaction() as c:
            row = c.execute('SELECT * FROM forecast_inputs WHERE tenant_id=? AND kind=? AND source_id=? AND revision=?', (tenant_id, kind, source_id, str(revision))).fetchone()
        return self._input(row) if row else None

    def input_records(self, cutoff, tenant_id='northstar', *, latest=False):
        with self.transaction() as c:
            rows = c.execute('SELECT * FROM forecast_inputs WHERE tenant_id=? AND available_at<=? AND received_at<=? ORDER BY available_at,received_at,rowid', (tenant_id, iso(cutoff), iso(cutoff))).fetchall()
        result = [self._input(r) for r in rows]
        if latest:
            latest_rows = {}
            for r in result:
                latest_rows[(r['kind'], r['source_id'])] = r
            return list(latest_rows.values())
        return result

    def save_snapshot(self, snapshot):
        value = encode(snapshot)
        with self.transaction() as c:
            old = c.execute('SELECT payload FROM forecast_input_snapshots WHERE id=?', (snapshot['id'],)).fetchone()
            if old and old[0] != value:
                raise ImmutableConflict('snapshot cannot change')
            c.execute('INSERT OR IGNORE INTO forecast_input_snapshots VALUES(?,?,?,?)', (snapshot['id'], snapshot['tenant_id'], iso(snapshot['information_cutoff']), value))
        return json.loads(value)

    def get_snapshot(self, snapshot_id):
        with self.transaction() as c:
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
        with self.transaction() as c:
            row = c.execute('SELECT * FROM forecast_jobs WHERE id=?', (job_id,)).fetchone()
        if not row:
            raise KeyError(job_id)
        return self._job(row)

    def find_job(self, tenant_id, key):
        with self.transaction() as c:
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
        with self.transaction() as c:
            return self._job(c.execute('SELECT * FROM forecast_jobs WHERE run_id=?', (run_id,)).fetchone())

    def list_jobs(self, *, job_type=None, tenant_id='northstar'):
        with self.transaction() as c:
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
        if not bundle.get('is_scenario'):
            for view in bundle.get('views', []):
                view.setdefault('publication', {})['issued_at'] = iso(now)
                view['publication']['published_at'] = iso(now)
        encoded = encode(bundle)
        with self.transaction() as c:
            row = c.execute("SELECT * FROM forecast_jobs WHERE id=? AND status='running' AND lease_token=? AND lease_until>?", (job_id, token, iso(now))).fetchone()
            if not row:
                return False
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
            cutoff = c.execute('SELECT cutoff FROM forecast_input_snapshots WHERE id=?', (row['snapshot_id'],)).fetchone()[0]
            c.execute('''INSERT INTO forecast_publications(tenant_id,run_id,sequence,published_at,information_cutoff) VALUES(?,?,?,?,?) ON CONFLICT(tenant_id) DO UPDATE
                SET run_id=excluded.run_id,sequence=excluded.sequence,published_at=excluded.published_at,information_cutoff=excluded.information_cutoff
                WHERE excluded.information_cutoff>forecast_publications.information_cutoff OR (excluded.information_cutoff=forecast_publications.information_cutoff AND excluded.sequence>forecast_publications.sequence)''', (row['tenant_id'], row['run_id'], row['sequence'], iso(now), cutoff))
            return True

    def publication(self, tenant_id='northstar'):
        with self.transaction() as c:
            row = c.execute('SELECT * FROM forecast_publications WHERE tenant_id=?', (tenant_id,)).fetchone()
        return dict(row) if row else None

    def get_run(self, run_id):
        with self.transaction() as c:
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
        with self.transaction() as c:
            row = c.execute('SELECT * FROM forecast_scenarios WHERE id=?', (scenario_id,)).fetchone()
        if not row:
            raise KeyError(scenario_id)
        result = dict(row)
        for key in ('drivers', 'bundle'):
            result[key] = json.loads(result[key])
        return result
