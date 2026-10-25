"""Read-only completion receipts from the explicitly selected company source adapter.

Ordinary imports never gain completeness from row presence. A request may reuse one
live adapter read, but only while its import receipts and cutoff remain unchanged.
"""
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import json

from sqlalchemy import select

from app.db.models import ImportBatch


def _instant(value):
    return datetime.fromisoformat(str(value).replace('Z', '+00:00')).astimezone(timezone.utc)


def _receipts(session):
    return tuple(tuple(row) for row in session.execute(select(
        ImportBatch.id, ImportBatch.content_hash, ImportBatch.status,
        ImportBatch.created_at, ImportBatch.record_count).order_by(ImportBatch.id)))


def _generation(session):
    # This backend uses SQLite. data_version detects commits on other connections;
    # total_changes detects this connection's writes, including a flushed correction
    # that leaves batch identity and dollar totals unchanged.
    connection = session.connection().connection.driver_connection
    return (id(connection), connection.execute('PRAGMA data_version').fetchone()[0],
            connection.total_changes)


class SourceCompletion:
    def __init__(self, snapshot, now):
        manifest = snapshot['company_fixture_manifest']
        self.revision = manifest['revision']
        self.days = set()
        self.amounts = defaultdict(lambda: Decimal('0.00'))
        self.batch_ids = {str(row['source_id']).removeprefix('repository:batch:')
                          for row in snapshot.get('source_revisions', [])
                          if row.get('kind') == 'repository_import'}
        checks = {item['date']: item for item in manifest['days']}
        required = snapshot.get('required_sources', [])
        if required != ['company-fixture:posted-ledger']:
            return
        for row in snapshot.get('coverage', []):
            day = date.fromisoformat(row['date'])
            check = checks.get(row['date'], {})
            if (row.get('source_id') == required[0] and row.get('complete') is True
                    and row.get('revision') == self.revision and _instant(row['available_at']) <= now
                    and day < now.date() and check.get('complete') is True
                    and check.get('expected_record_count') == check.get('posted_record_count')
                    and all(check.get(key) == 0 for key in
                            ('missing_record_count', 'mismatched_record_count', 'unexpected_record_count'))):
                self.days.add(day)
        for row in snapshot.get('observations', []):
            day = date.fromisoformat(row['date'])
            if (day not in self.days or row.get('complete') is not True
                    or row.get('source_id') != required[0] or row.get('revision') != self.revision
                    or row.get('recorded_currency') != 'USD' or _instant(row['available_at']) > now):
                continue
            amount = Decimal(row['recorded_amount'])
            if not amount.is_finite() or amount < 0:
                self.days.discard(day)
                continue
            self.amounts[('company', None, day)] += amount
            if row.get('team_id'):
                self.amounts[('team', row['team_id'], day)] += amount
            if row.get('person_id'):
                self.amounts[('person', row['person_id'], day)] += amount
        self.revision = hashlib.sha256(json.dumps({
            'manifest': self.revision, 'coverage': snapshot.get('coverage', []),
            'receipts': snapshot.get('source_revisions', []),
        }, sort_keys=True, default=str).encode()).hexdigest()

    def amount(self, scope_type, scope_id, day):
        if day not in self.days:
            return None
        return self.amounts.get((scope_type, scope_id, day))

    def accepts_records(self, rows):
        return all(row.import_batch_id in self.batch_ids and row.source_kind == 'northstar_billing'
                   for row in rows)

    def is_current(self, session):
        return _generation(session) == self.native_generation

    def period_through(self, team_id, start, end_exclusive, now, recorded):
        end = min(end_exclusive, now.date())
        if start >= end:
            return None
        values = [self.amount('team', team_id, start + timedelta(days=i))
                  for i in range((end - start).days)]
        if any(value is None for value in values) or sum(values, Decimal('0.00')) != recorded:
            return None
        return end - timedelta(days=1)


def source_completion(session, now):
    """Return matching current receipts, or conservatively retain unknown coverage."""
    service = session.info.get('forecast_service')
    factory = getattr(service, 'snapshot_factory', None)
    if factory is None:
        return None
    now = now.astimezone(timezone.utc)
    generation = _generation(session)
    receipts = _receipts(session)
    key = (id(factory), now, receipts, generation)
    cached = session.info.get('_source_completion')
    if cached and cached[0] == key and not (session.new or session.dirty or session.deleted):
        return cached[1]
    result = None
    try:
        snapshot = factory(now=now.isoformat(), tenant_id='northstar')
        manifest = snapshot.get('company_fixture_manifest')
        if (isinstance(manifest, dict) and manifest.get('revision') and _receipts(session) == receipts
                and _generation(session) == generation):
            batches = {row[0]: row for row in receipts}
            references = snapshot.get('source_revisions', [])
            matching = isinstance(references, list) and bool(references)
            matched_native = 0
            for ref in references if isinstance(references, list) else []:
                if ref.get('kind') != 'repository_import':
                    continue
                matched_native += 1
                batch = batches.get(str(ref.get('source_id', '')).removeprefix('repository:batch:'))
                matching = matching and bool(batch and batch[2] == 'imported'
                    and ref.get('revision') == batch[1] and _instant(ref['received_at']) == batch[3]
                    and batch[3] <= now)
            if matching and matched_native:
                result = SourceCompletion(snapshot, now)
                result.native_generation = generation
    except (ValueError, TypeError, KeyError, ArithmeticError):
        # A failed/malformed receipt cannot make a previously unknown day complete.
        result = None
    session.info['_source_completion'] = (key, result)
    return result
