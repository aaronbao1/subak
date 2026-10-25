"""Read actual repository imports without manufacturing daily completeness.

The legacy repository records money and optional token counters, but has neither
daily source manifests or exposure ledgers. The native people directory supplies
known identities; its current team metadata is not employment history. Money is
an already billed observation, never a token quantity. The optional synchronization entry point is
explicitly a write operation; normal snapshot/actuals reads never append inputs.
"""
from __future__ import annotations

from copy import deepcopy
from contextlib import nullcontext
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import json
import sqlite3

from sqlalchemy import select

from app.db.models import ImportBatch, Person, PlanningPeriod, Team, TeamMapping, UsageRecord

from .persistence import identity, iso
from .service import empty_snapshot


def _instant(value):
    return datetime.fromisoformat(iso(value).replace('Z', '+00:00'))


def _value(value):
    if isinstance(value, datetime):
        return iso(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return format(value, 'f')
    return value


def _row(record):
    return {column.name: _value(getattr(record, column.name)) for column in record.__table__.columns}


def _material(session, now, *, include_future=False):
    """Cut off receipt time as well as event time; failed/duplicate batches book nothing."""
    cutoff = _instant(now)
    batches = list(session.scalars(select(ImportBatch).where(
        ImportBatch.status == 'imported', ImportBatch.created_at <= cutoff).order_by(ImportBatch.id)))
    batch_ids = [row.id for row in batches]
    query = select(UsageRecord).where(UsageRecord.import_batch_id.in_(batch_ids), UsageRecord.created_at <= cutoff)
    if not include_future:
        query = query.where(UsageRecord.occurred_at <= cutoff)
    observations = list(session.scalars(query.order_by(UsageRecord.id))) if batch_ids else []
    return {
        'batches': [_row(row) for row in batches],
        'records': [_row(row) for row in observations],
        'people': [_row(row) for row in session.scalars(select(Person).where(Person.created_at <= cutoff).order_by(Person.id))],
        'teams': [_row(row) for row in session.scalars(select(Team).where(Team.created_at <= cutoff).order_by(Team.id))],
        'mappings': [_row(row) for row in session.scalars(select(TeamMapping).where(TeamMapping.created_at <= cutoff).order_by(TeamMapping.id))],
        'periods': [_row(row) for row in session.scalars(select(PlanningPeriod).where(PlanningPeriod.created_at <= cutoff).order_by(PlanningPeriod.id))],
    }


def repository_revision(session, now):
    """Stable current input fingerprint, callable inside the caller's write lock.

    Mutable legacy attribution is included so new imports or mapping edits stale
    existing proposals even before an optional bridge synchronization occurs.
    """
    return identity(_material(session, now))


def repository_snapshot_factory(session_factory, *, clock=None, store=None):
    """Return the ``ForecastService`` snapshot callable over repository records.

    ``clock`` is the application's trusted current clock, not the requested
    information cutoff. Legacy mappings and directory rows have no update history; historical reads
    therefore leave attribution unknown rather than backdating today's mapping.
    The service explicitly identifies historical reads with ``as_of=True`` and
    current reads with ``as_of=False``. Direct callers omitting that flag use a
    strict cutoff comparison. Full source captures restore the latest repository
    state actually received before cutoff; legacy partial archives require an
    exact cutoff match. Later mutations never rewrite earlier source captures.
    """
    clock = clock or (lambda: datetime.now(timezone.utc))

    def snapshot_factory(*, now, tenant_id='northstar', as_of: bool | None = None):
        cutoff = _instant(now)
        historical = cutoff < _instant(clock()) if as_of is None else as_of
        snapshot = empty_snapshot(now=iso(now), tenant_id=tenant_id)
        material = None
        if historical and store is not None:
            archives = [row for row in store.input_records(now, tenant_id)
                        if row['kind'] == 'repository_state' and row['source_id'] == 'repository']
            if archives:
                archived = archives[-1]
                if archived['payload'].get('repository_capture_version') == 1:
                    material = deepcopy(archived['payload']['repository_material'])
                    material['records'] = [r for r in material['records'] if _instant(r['occurred_at']) <= cutoff]
                    historical = False  # These are frozen, previously known assignments.
                elif archived['available_at'] == iso(now) and archived['received_at'] == iso(now):
                    snapshot.update(deepcopy(archived['payload']))
                    snapshot['repository_archive'] = {key: archived[key] for key in
                                                      ('id', 'revision', 'available_at', 'received_at')}
                    return snapshot
                if material is not None:
                    snapshot['repository_archive'] = {key: archived[key] for key in
                                                      ('id', 'revision', 'available_at', 'received_at')}
        if material is None:
            with session_factory() as session:
                material = _material(session, now)
        snapshot['repository_revision'] = identity(material)
        snapshot['limitations'] = [
            'Repository imports have no daily source completeness attestations; missing days and late usage remain unknown.',
            'Person attribution uses known directory identities recorded on usage; project attribution and work exposure remain unknown.',
        ]
        if historical:
            snapshot['limitations'].append('Historical attribution is unknown: mutable repository team mappings and people have no revision history.')
        snapshot['people'] = [{'id': p['id'], 'name': p['id'] if historical else p['name'],
                               'team_id': None if historical else p['team_id'],
                               'active': None if historical else p['active'],
                               'is_simulated': None if historical else p['is_simulated']}
                              for p in material.get('people', [])]
        # Directory team_id is current metadata, not an effective-dated employment
        # or exposure ledger. Do not manufacture canonical memberships from it.
        snapshot['teams'] = [{'id': t['id'], 'name': t['id'] if historical else t['name']} for t in material['teams']]
        # PlanningPeriod ends_on is inclusive; canonical end is exclusive. Use an
        # actual active repository period only, otherwise the UTC quarter fallback.
        periods = [p for p in material['periods'] if p['starts_on'] <= cutoff.date().isoformat() <= p['ends_on']]
        if periods:
            period = sorted(periods, key=lambda p: (p['starts_on'], p['id']))[-1]
            snapshot.update(period_id=period['id'], period_start=period['starts_on'],
                            period_end=(date.fromisoformat(period['ends_on']) + timedelta(days=1)).isoformat())
        batches = {b['id']: b for b in material['batches']}
        configurations, pricing, revisions = {}, {}, []
        for batch in material['batches']:
            revisions.append({'kind': 'repository_import', 'source_id': 'repository:batch:' + batch['id'],
                              'revision': batch['content_hash'], 'available_at': batch['created_at'],
                              'received_at': batch['created_at']})
        ignored = []
        for record in material['records']:
            if historical:
                # Raw provenance must not leak today's mutable attribution any
                # more than the canonical component can use it numerically.
                record = {**record, 'team_id': None, 'person_id': None}
            if not record['counts_toward_spend'] or record['amount'] is None:
                ignored.append({'id': record['id'], 'reason': 'nonspend_or_unpriced', 'provenance': record})
                continue
            if record['unit'] != 'USD':
                ignored.append({'id': record['id'], 'reason': 'unsupported_currency', 'provenance': record})
                continue
            if Decimal(record['amount']) < 0:
                ignored.append({'id': record['id'], 'reason': 'unsupported_negative_adjustment', 'provenance': record})
                continue
            batch = batches[record['import_batch_id']]
            configuration = 'repository-spend:' + record['cost_category']
            pool = 'repository-spend:' + record['source_kind'] + ':' + record['cost_category']
            configurations[configuration] = {'id': configuration, 'unit': 'usd', 'quantity': 'recorded_spend'}
            pricing[pool] = {'id': pool, 'version': 'identity-v1', 'billing_pool': pool,
                             'configuration_id': configuration, 'meter': 'usd', 'unit': 'usd', 'currency': 'USD',
                             'rate': '1', 'mode': 'linear', 'complete_pool': False,
                             'period_start': snapshot['period_start'], 'period_end': snapshot['period_end'],
                             'known_at': batch['created_at'], 'basis': 'identity_of_recorded_money_only'}
            snapshot['observations'].append({
                'observation_id': 'repository:usage:' + record['id'], 'date': record['occurred_at'][:10],
                'quantity': record['amount'], 'recorded_amount': record['amount'], 'recorded_currency': 'USD',
                'person_id': None if historical else record.get('person_id'),
                'team_id': None if historical else record['team_id'], 'project_id': None,
                'configuration_id': configuration, 'meter': 'usd', 'billing_pool': pool,
                'source_id': 'repository:usage', 'revision': batch['content_hash'],
                'available_at': max(record['created_at'], batch['created_at']),
                'complete': False, 'mature': False, 'exposure': None,
                'provenance': {**record, 'imported_at': batch['created_at'], 'content_hash': batch['content_hash']},
            })
        snapshot['configurations'] = list(configurations.values())
        snapshot['pricing'] = list(pricing.values())
        snapshot['source_revisions'] = revisions
        snapshot['repository_excluded_records'] = ignored
        if any(r['reason'] == 'nonspend_or_unpriced' for r in ignored):
            snapshot['limitations'].append('Included or unpriced token telemetry is retained as provenance and is not converted into spend.')
        if any(r['reason'] == 'unsupported_currency' for r in ignored):
            snapshot['limitations'].append('Unsupported currency records are excluded from the USD target; no exchange rate is assumed.')
        if any(r['reason'] == 'unsupported_negative_adjustment' for r in ignored):
            snapshot['limitations'].append('Negative monetary adjustments are retained in repository provenance but unsupported by the nonnegative forecast target.')
        snapshot['is_synthetic'] = any(r['value_kind'] == 'simulated' for r in material['records'])
        return snapshot

    snapshot_factory.supports_as_of = True
    def capture_payload(*, now, tenant_id='northstar'):
        with session_factory() as session:
            connection = session.connection().connection.driver_connection
            if not connection.in_transaction:
                connection.execute('BEGIN')
            frozen_factory = repository_snapshot_factory(lambda: nullcontext(session), clock=lambda: now)
            snapshot = frozen_factory(now=now, tenant_id=tenant_id, as_of=False)
            return _capture_payload(snapshot, _material(session, now, include_future=True))
    snapshot_factory.capture_payload = capture_payload
    def capture_inputs(*, now, tenant_id='northstar'):
        with session_factory() as session:
            receipt = capture_repository_inputs(session, now=now, tenant_id=tenant_id)
            session.commit()
            return receipt
    snapshot_factory.capture_inputs = capture_inputs
    return snapshot_factory


def _capture_payload(snapshot, material):
    payload = {k: v for k, v in snapshot.items() if k not in {
        'information_cutoff', 'history_complete_through', 'forecast_start', 'generated_at', 'id'}}
    payload.update(repository_capture_version=1, repository_material=material)
    return payload


def synchronize_repository_inputs(store, snapshot_factory, *, now, tenant_id='northstar'):
    """Explicitly archive a connector-shaped immutable repository revision.

    Receipt is synchronization time, never backdated to historical event/import
    time. Existing issued snapshots remain immutable. Caller runs this on startup
    or after successful input mutations, outside normal read paths.
    """
    if hasattr(snapshot_factory, 'capture_payload'):
        payload = snapshot_factory.capture_payload(now=now, tenant_id=tenant_id)
    else:
        options = {'as_of': False} if getattr(snapshot_factory, 'supports_as_of', False) else {}
        snapshot = snapshot_factory(now=now, tenant_id=tenant_id, **options)
        # Clock/publication fields are not source content and must not break dedupe.
        payload = {k: v for k, v in snapshot.items() if k not in {
            'information_cutoff', 'history_complete_through', 'forecast_start', 'generated_at', 'id'}}
    rows = [row for row in store.input_records(now, tenant_id)
            if row['kind'] == 'repository_state' and row['source_id'] == 'repository']
    previous = rows[-1] if rows else None
    if previous is not None and previous['payload'] == payload:
        return previous
    # Content may legitimately return to a previous state after a mapping edit.
    # Chain versions rather than collapsing that correction into an old receipt.
    revision = identity({'payload': payload, 'predecessor': previous['revision'] if previous else None})
    return store.append_input('repository_state', 'repository', revision, payload,
                              available_at=now, received_at=now, tenant_id=tenant_id)


def capture_repository_inputs(session, *, now, tenant_id='northstar'):
    """Append source state in the caller's repository write transaction.

    Main binds ``forecast_store`` in sessionmaker.info. Unbound standalone legacy
    sessions remain supported. No second connection, nested transaction, commit,
    or read-side capture occurs; rollback removes both mutation and receipt.
    """
    store = session.info.get('forecast_store')
    if store is None:
        return None
    session.flush()
    connection = session.connection().connection.driver_connection
    if not connection.in_transaction:
        connection.execute('BEGIN IMMEDIATE')
    trusted_clock = session.info.get('forecast_clock')
    if trusted_clock is not None:
        now = max(_instant(now), _instant(trusted_clock()))
    factory = repository_snapshot_factory(lambda: nullcontext(session), clock=lambda: now)
    snapshot = factory(now=now, tenant_id=tenant_id, as_of=False)
    payload = _capture_payload(snapshot, _material(session, now, include_future=True))
    previous_factory = connection.row_factory
    connection.row_factory = sqlite3.Row
    try:
        previous = connection.execute('''SELECT * FROM forecast_inputs WHERE tenant_id=?
            AND kind='repository_state' AND source_id='repository'
            ORDER BY available_at DESC,received_at DESC,rowid DESC LIMIT 1''', (tenant_id,)).fetchone()
        if previous is not None and json.loads(previous['payload']) == payload:
            return store._input(previous)
        revision = identity({'payload': payload, 'predecessor': previous['revision'] if previous else None})
        return store._append_input(connection, 'repository_state', 'repository', revision,
                                   payload, now, now, tenant_id)
    finally:
        connection.row_factory = previous_factory
