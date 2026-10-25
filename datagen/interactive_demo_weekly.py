"""Read-only weekly wires for a fixed interactive-demo export.

The export owns one SQLite read snapshot. Immutable learning records and publication
fragments are read once, then scoped in memory; this cache never serves live requests.
No application, forecasting worker, migrations, refreshes, or SDK calls are started.
"""
from __future__ import annotations

from collections import defaultdict
from contextlib import nullcontext
from datetime import date, datetime
import json
from pathlib import Path
import sqlite3
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
for directory in ('backend', 'src', 'agent'):
    if str(ROOT / directory) not in sys.path:
        sys.path.insert(0, str(ROOT / directory))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.clock import FrozenClock
from app.forecasting.company_fixture import company_fixture_snapshot_factory
from app.forecasting.persistence import iso
from app.forecasting.weekly_history import weekly_history
from app.schemas.weekly_history import WeeklyHistoryResponse
from app.services.usage import daily_usage


class _ExportHistory:
    """Compact immutable evidence for one export snapshot and information cutoff."""

    def __init__(self, connection, cutoff):
        self.cutoff = cutoff
        self.targets = defaultdict(list)
        self.truths = []
        self.synthetic = False
        # Neither removed field participates in the weekly history contract. Removing
        # raw JSON members preserves prediction tokens without SQL numeric rebuilding.
        rows = connection.execute("""SELECT kind, CASE WHEN kind='issued_targets'
                THEN json_remove(payload,'$.intervals','$.procedure_dependencies') ELSE payload END AS body
            FROM forecast_inputs WHERE tenant_id='northstar' AND available_at<=? AND received_at<=?
                AND kind IN ('issued_targets','truth_revisions') ORDER BY available_at,received_at,rowid""",
            (cutoff, cutoff))
        for row in rows:
            payload = json.loads(row['body'])
            record = {'kind': row['kind'], 'payload': payload}
            if row['kind'] == 'truth_revisions':
                self.truths.append(record)
            else:
                self.synthetic = self.synthetic or bool(payload.get('is_synthetic'))
                self.targets[(payload.get('scope_type'), payload.get('scope_id'))].append(record)
        self.publications = {}
        self.views = {}
        current = connection.execute("SELECT run_id FROM forecast_publications WHERE tenant_id='northstar'").fetchone()
        current_id = current[0] if current else None
        # Each immutable bundle is scanned once in SQLite. Python receives only small
        # publication objects plus the current run's raw target/weekly JSON fragments.
        rows = connection.execute("""SELECT runs.id AS run_id, jobs.sequence,
                json_extract(view.value,'$.scope') AS scope,
                json_extract(view.value,'$.publication') AS publication,
                CASE WHEN runs.id=? THEN json_extract(view.value,'$.target') END AS target,
                CASE WHEN runs.id=? THEN json_extract(view.value,'$.weekly') END AS weekly,
                CASE WHEN runs.id=? THEN json_extract(view.value,'$.run_id') END AS view_run_id
            FROM forecast_runs AS runs JOIN forecast_jobs AS jobs ON jobs.id=runs.job_id,
                json_each(runs.bundle,'$.views') AS view
            WHERE jobs.tenant_id='northstar' ORDER BY jobs.sequence,view.key""",
            (current_id, current_id, current_id))
        for row in rows:
            scope = json.loads(row['scope'])
            key = (scope['type'], scope.get('id'))
            publication = json.loads(row['publication']) if row['publication'] is not None else {}
            self.publications.setdefault((row['run_id'], *key), {
                'published_at': publication.get('published_at'), 'sequence': row['sequence']})
            if row['run_id'] == current_id and key not in self.views:
                self.views[key] = {'scope': scope, 'publication': publication,
                    **{field: json.loads(row[field]) for field in ('target', 'weekly') if row[field] is not None},
                    **({'run_id': row['view_run_id']} if row['view_run_id'] is not None else {})}

    def weekly_history_inputs(self, cutoff, tenant_id='northstar', *, scope_type, scope_id):
        if iso(cutoff) != self.cutoff or tenant_id != 'northstar':
            raise ValueError('Export history belongs to a different cutoff or company.')
        return {'records': [*self.targets[(scope_type, scope_id)], *self.truths], 'synthetic': self.synthetic}

    def weekly_publication_metadata(self, run_ids, scope_type, scope_id):
        return {run_id: self.publications[(run_id, scope_type, scope_id)] for run_id in dict.fromkeys(run_ids)
                if (run_id, scope_type, scope_id) in self.publications}

    def weekly_current_view(self, scope_type, scope_id, tenant_id='northstar'):
        if tenant_id != 'northstar':
            raise ValueError('Export history belongs to a different company.')
        return self.views.get((scope_type, scope_id))


def export_weekly_history(db_path, source_dir, as_of, scopes, start_date, end_date_exclusive):
    """Return JSON-ready WeeklyHistoryResponse wires in the supplied scope order.

    Scopes are ``(type, id)`` pairs or ``{'type': ..., 'id': ...}`` dictionaries.
    The current UI defaults to four past + current + three future weeks. Callers
    may supply a wider explicit Monday-bounded interval of up to 26 weeks.
    """
    stamp = iso(as_of)
    instant = datetime.fromisoformat(stamp.replace('Z', '+00:00'))
    begin = date.fromisoformat(start_date) if isinstance(start_date, str) else start_date
    end = date.fromisoformat(end_date_exclusive) if isinstance(end_date_exclusive, str) else end_date_exclusive
    if begin.weekday() or end.weekday() or not 7 <= (end - begin).days <= 182:
        raise ValueError('Choose Monday boundaries covering 1 to 26 full calendar weeks.')
    selected = [(scope['type'], scope.get('id')) if isinstance(scope, dict) else tuple(scope) for scope in scopes]
    if len(selected) != len(set(selected)):
        raise ValueError('Export scopes must be unique.')
    for kind, scope_id in selected:
        if kind not in ('company', 'team', 'person', 'shared') or not scope_id:
            raise ValueError('Choose a known named forecast scope.')
        if kind == 'company' and scope_id != 'northstar':
            raise ValueError('Company scope_id must match the current company.')
    db = Path(db_path).resolve(strict=True)
    source = Path(source_dir).resolve(strict=True)

    def connect():
        connection = sqlite3.connect(db.as_uri() + '?mode=ro', uri=True, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute('PRAGMA query_only=ON')
        return connection

    engine = create_engine('sqlite://', creator=connect)
    try:
        with Session(engine) as session:
            connection = session.connection().connection.driver_connection
            connection.execute('BEGIN')
            clock = FrozenClock(instant)
            history = _ExportHistory(connection, stamp)
            # One session preserves the source_completion receipt/generation cache
            # across all scopes. The real adapter executes once, never once per person.
            factory = company_fixture_snapshot_factory(lambda: nullcontext(session), source, clock)
            service = SimpleNamespace(now=lambda: instant, store=history, snapshot_factory=factory)
            session.info['forecast_service'] = service
            output = []
            for kind, scope_id in selected:
                ledger = ({'buckets': [], 'dataset_revision': 'shared-ledger-scope-unavailable', 'synthetic': False}
                          if kind == 'shared' else daily_usage(session, scope_type=kind,
                              scope_id=None if kind == 'company' else scope_id, start_date=begin,
                              end_date_exclusive=end, provider=None, model=None, clock=clock))
                result = weekly_history(service, ledger, scope_type=kind, scope_id=scope_id,
                                        start_date=begin, end_date_exclusive=end)
                output.append(WeeklyHistoryResponse.model_validate(result).model_dump(mode='json'))
            return output
    finally:
        engine.dispose()
