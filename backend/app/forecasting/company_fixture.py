"""Opt-in, read-only adapter for an explicitly generated company billing manifest.

This is not an attestation for arbitrary repository imports. The caller selects a
fixed datagen source directory and replays its receipts into a separate database.
Only exact native ledger cents are forecast; tokens, project labels and narrative
event multipliers never manufacture money or workload exposure.
"""
from __future__ import annotations

from collections import defaultdict
import csv
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from functools import wraps
import hashlib
import io
import json
from pathlib import Path
from threading import RLock

from sqlalchemy import select

from app.db.models import ImportBatch, Person, PlanningPeriod, Team, UsageRecord
from .persistence import identity, iso
from .service import empty_snapshot


SOURCE_KIND = 'northstar_billing'
SOURCE_ID = 'company-fixture:posted-ledger'
CONFIGURATION = 'company-fixture:posted-usd'
POOL = 'company-fixture:posted-usd'
ZERO = Decimal('0.00')
CHARGED = {'subscription_fee', 'direct_api', 'billable_overage'}


def _instant(value):
    return datetime.fromisoformat(iso(value).replace('Z', '+00:00'))


def _money(value):
    if value in (None, ''):
        return None
    result = Decimal(str(value))
    if not result.is_finite() or result < 0 or result != result.quantize(Decimal('0.01')):
        raise ValueError('Company fixture requires nonnegative posted USD cents.')
    return result


def _load_manifest(directory):
    directory = Path(directory)
    reference_raw = (directory / 'backend' / 'reference.json').read_bytes()
    reference = json.loads(reference_raw)
    if reference.get('company', {}).get('simulated') is not True:
        raise ValueError('Company fixture adapter requires an explicitly simulated source.')
    as_of = date.fromisoformat(reference['company']['as_of'])
    start = min(date.fromisoformat(p['starts_on']) for p in reference['periods'])
    people = {p['email'].lower(): p for p in reference['people']}
    mappings = reference['team_mappings'][SOURCE_KIND]
    digest = hashlib.sha256(reference_raw)
    expected, by_day = {}, defaultdict(set)
    paths = sorted((directory / 'backend' / 'billing').glob('*.csv'))
    if not paths:
        raise ValueError('Company fixture billing manifest is empty.')
    for path in paths:
        raw = path.read_bytes(); digest.update(path.name.encode()); digest.update(raw)
        for row in csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))):
            key = row['record_id']
            stamp = _instant(row['occurred_at'])
            day = stamp.date()
            person = people.get(row['user_email'].lower())
            team = mappings.get(row['source_account'])
            category = row['cost_category']
            if (key in expected or not start <= day <= as_of or person is None or team is None
                    or person['team'] != team or row['unit'] != 'USD'
                    or row['value_kind'] != 'simulated' or category not in CHARGED | {'included_usage'}):
                raise ValueError('Company fixture has duplicate, unsupported or unattributed source records.')
            amount = _money(row['amount'])
            if (category in CHARGED) != (amount is not None):
                raise ValueError('Company fixture charge and included-usage values disagree.')
            expected[key] = (day.isoformat(), team, person['id'], amount, row['unit'], category,
                             row['source_account'], iso(stamp), _money(row.get('notional_value')),
                             row['provider'] or None, row['model'] or None)
            by_day[day.isoformat()].add(key)
    employment = {}
    people_path = directory / 'csv' / 'people.csv'
    if people_path.exists():
        raw = people_path.read_bytes(); digest.update(raw)
        employment = {p['id']: p for p in csv.DictReader(io.StringIO(raw.decode()))}
    declared_complete = reference['company'].get('complete_through')
    if declared_complete is not None:
        if declared_complete != as_of.isoformat():
            raise ValueError('Company fixture complete-through attestation must name its source as-of day.')
        calendar_path = directory / 'csv' / 'calendar.csv'
        if not calendar_path.exists():
            raise ValueError('Complete company fixture requires its generated calendar.')
        raw = calendar_path.read_bytes()
        calendar = [row for row in csv.DictReader(io.StringIO(raw.decode())) if row['day'] == declared_complete]
        if len(calendar) != 1 or calendar[0].get('is_partial') != '0' or calendar[0].get('is_future') != '0':
            raise ValueError('Company fixture calendar does not attest a complete source as-of day.')
        digest.update(raw)
    return reference, start, as_of, expected, by_day, employment, digest.hexdigest()


def company_fixture_snapshot_factory(session_factory, source_directory, clock):
    """Return a ForecastService factory over one fixed, explicit source manifest.

    No database tables or source files are written. Recreate the factory to choose
    a different source. Historical issuance must happen during chronological
    replay; saved ForecastService input snapshots preserve each issued vintage.
    This adapter does not fabricate historical versions of mutable native rows.
    """
    reference, first, source_as_of, expected, expected_days, employment, manifest_hash = _load_manifest(source_directory)
    snapshot_lock = RLock()
    source_complete_through = date.fromisoformat(reference['company'].get(
        'complete_through', (source_as_of - timedelta(days=1)).isoformat()))
    reference_people = {p['id']: p for p in reference['people']}

    def snapshot_factory(*, now=None, tenant_id='northstar', as_of=None):
        del as_of  # All reads enforce both receipt and occurrence cutoffs.
        if now is None:
            now = clock() if callable(clock) else clock.now()
        cutoff = _instant(now); stamp = iso(cutoff)
        snapshot = empty_snapshot(now=stamp, tenant_id=tenant_id)
        snapshot['is_synthetic'] = True
        # The source manifest is only a declaration of the generated source. It
        # does not itself make any unreceived native observation usable.
        seen = defaultdict(set)
        mismatches, unexpected = defaultdict(int), defaultdict(int)
        latest_receipt = {}
        groups = defaultdict(lambda: {'amount': ZERO, 'available_at': '', 'record_count': 0})
        batches = {}
        manifest_received_at = None
        with session_factory() as session:
            connection = session.connection().connection.driver_connection
            if not connection.in_transaction:
                connection.execute('BEGIN')
            known_people = list(session.scalars(select(Person).where(Person.created_at <= cutoff).order_by(Person.id)))
            known_people = [p for p in known_people if p.id in reference_people and
                            employment.get(p.id, {}).get('start_date', first.isoformat()) <= cutoff.date().isoformat()]
            person_receipts = {p.id: iso(p.created_at) for p in known_people}
            snapshot['people'] = [{'id': p.id, 'name': p.name, 'team_id': reference_people[p.id]['team'],
                                   'is_simulated': True} for p in known_people]
            teams = list(session.scalars(select(Team).where(Team.created_at <= cutoff).order_by(Team.id)))
            team_receipts = {t.id: iso(t.created_at) for t in teams}
            snapshot['teams'] = [{'id': t.id, 'name': t.name} for t in teams]
            periods = list(session.scalars(select(PlanningPeriod).where(
                PlanningPeriod.created_at <= cutoff, PlanningPeriod.starts_on <= cutoff.date(),
                PlanningPeriod.ends_on >= cutoff.date()).order_by(PlanningPeriod.starts_on, PlanningPeriod.id)))
            if periods:
                period = periods[-1]
                snapshot.update(period_id=period.id, period_start=period.starts_on.isoformat(),
                                period_end=(period.ends_on + timedelta(days=1)).isoformat())
            columns = [UsageRecord.source_record_key, UsageRecord.source_kind, UsageRecord.occurred_at,
                       UsageRecord.created_at, UsageRecord.team_id, UsageRecord.person_id, UsageRecord.amount,
                       UsageRecord.unit, UsageRecord.cost_category, UsageRecord.counts_toward_spend,
                       UsageRecord.value_kind, UsageRecord.source_account, UsageRecord.notional_value,
                       UsageRecord.provider, UsageRecord.model, UsageRecord.counter_reset,
                       ImportBatch.id.label('batch_id'), ImportBatch.created_at.label('received_at'),
                       ImportBatch.content_hash]
            query = select(*columns).join(ImportBatch, UsageRecord.import_batch_id == ImportBatch.id).where(
                ImportBatch.status == 'imported', ImportBatch.created_at <= cutoff,
                UsageRecord.created_at <= cutoff, UsageRecord.occurred_at <= cutoff,
                UsageRecord.occurred_at >= datetime.combine(first, datetime.min.time(), timezone.utc))
            for row in session.execute(query.execution_options(yield_per=5000)).mappings():
                day = row['occurred_at'].date().isoformat()
                received = max(iso(row['created_at']), iso(row['received_at']),
                               person_receipts.get(row['person_id'], ''), team_receipts.get(row['team_id'], ''))
                latest_receipt[day] = max(latest_receipt.get(day, ''), received)
                batches[row['batch_id']] = {'kind': 'repository_import', 'source_id': 'repository:batch:' + row['batch_id'],
                    'revision': row['content_hash'], 'available_at': iso(row['received_at']), 'received_at': iso(row['received_at'])}
                key = row['source_record_key']
                original = expected.get(key) if row['source_kind'] == SOURCE_KIND else None
                if original is None:
                    unexpected[day] += 1
                else:
                    manifest_received_at = min(manifest_received_at or received, received)
                    seen[original[0]].add(key)
                    actual = (day, row['team_id'], row['person_id'], row['amount'], row['unit'],
                              row['cost_category'], row['source_account'], iso(row['occurred_at']),
                              row['notional_value'], row['provider'], row['model'])
                    if (actual != original or row['value_kind'] != 'simulated' or row['counter_reset']
                            or row['person_id'] not in person_receipts or row['team_id'] not in team_receipts
                            or row['counts_toward_spend'] != (row['cost_category'] in CHARGED)):
                        mismatches[original[0]] += 1
                        if day != original[0]:
                            unexpected[day] += 1
                if (row['counts_toward_spend'] and row['amount'] is not None and row['unit'] == 'USD'
                        and row['amount'] >= ZERO):
                    aggregate = groups[(day, row['team_id'], row['person_id'])]
                    aggregate['amount'] += row['amount']
                    aggregate['available_at'] = max(aggregate['available_at'], received)
                    aggregate['record_count'] += 1
        checks, coverage = [], []
        day = first
        last = min(source_as_of, cutoff.date())
        complete_through = first - timedelta(days=1)
        while day <= last:
            key = day.isoformat(); expected_ids = expected_days.get(key, set())
            missing = len(expected_ids - seen[key])
            day_end = iso(datetime.combine(day + timedelta(days=1), datetime.min.time(), timezone.utc))
            complete = (manifest_received_at is not None and day <= source_complete_through and day_end <= stamp and missing == 0
                        and mismatches[key] == 0 and unexpected[key] == 0)
            available = (max(day_end, latest_receipt.get(key, manifest_received_at)) if complete else
                         latest_receipt.get(key, manifest_received_at or first.isoformat() + 'T00:00:00Z'))
            coverage.append({'date': key, 'source_id': SOURCE_ID, 'complete': complete,
                             'available_at': available, 'revision': manifest_hash, 'is_synthetic': True})
            checks.append({'date': key, 'complete': complete, 'expected_record_count': len(expected_ids),
                           'posted_record_count': len(seen[key]) + unexpected[key], 'missing_record_count': missing,
                           'mismatched_record_count': mismatches[key], 'unexpected_record_count': unexpected[key]})
            if complete:
                complete_through = day
                # A full source/day inventory attests absent person spend as zero;
                # directory membership alone never establishes such a zero.
                for person in snapshot['people']:
                    p = employment.get(person['id'], {})
                    if p.get('start_date', first.isoformat()) > key or person['team_id'] not in team_receipts:
                        continue
                    group_key = (key, person['team_id'], person['id'])
                    if group_key not in groups:
                        groups[group_key] = {'amount': ZERO, 'available_at': max(available,
                            person_receipts[person['id']], team_receipts[person['team_id']]), 'record_count': 0}
            day += timedelta(days=1)
        complete_days = {r['date']: r for r in coverage if r['complete']}
        observations = []
        for (day, team_id, person_id), values in sorted(groups.items(), key=lambda item: tuple(str(v or '') for v in item[0])):
            known = complete_days.get(day)
            observations.append({'observation_id': SOURCE_ID + ':' + day + ':' + str(team_id) + ':' + str(person_id),
                'date': day, 'person_id': person_id, 'team_id': team_id, 'project_id': None,
                'configuration_id': CONFIGURATION, 'meter': 'usd', 'billing_pool': POOL,
                'quantity': format(values['amount'], '.2f'), 'recorded_amount': format(values['amount'], '.2f'),
                'recorded_currency': 'USD', 'exposure': None, 'source_id': SOURCE_ID,
                'revision': manifest_hash, 'available_at': max(values['available_at'], known['available_at']) if known else values['available_at'],
                'complete': bool(known), 'mature': bool(known), 'is_synthetic': True,
                'provenance': {'kind': 'posted_repository_cents', 'record_count': values['record_count'],
                               'source_manifest': manifest_hash}})
        snapshot.update(history_complete_through=complete_through.isoformat(), required_sources=[SOURCE_ID],
                        coverage=coverage, observations=observations,
                        configurations=[{'id': CONFIGURATION, 'unit': 'usd', 'quantity': 'recorded_spend'}],
                        pricing=[{'id': POOL, 'version': 'identity-v1', 'billing_pool': POOL,
                                  'configuration_id': CONFIGURATION, 'meter': 'usd', 'unit': 'usd', 'currency': 'USD',
                                  'mode': 'linear', 'rate': '1', 'fixed': 0, 'complete_pool': True,
                                  # USD-to-USD is an identity, not a vendor tariff
                                  # expiring at the displayed quarter boundary.
                                  'effective_from': first.isoformat(), 'effective_to': '9999-12-31',
                                  'known_at': first.isoformat() + 'T00:00:00Z',
                                  'basis': 'identity_of_recorded_money_only'}],
                        source_revisions=sorted(batches.values(), key=lambda r: r['source_id']))
        snapshot['company_fixture_manifest'] = {'source_company_id': reference['company']['id'],
            'revision': manifest_hash, 'source_as_of': source_as_of.isoformat(),
            'source_complete_through': source_complete_through.isoformat(),
            'history_start': first.isoformat(), 'days': checks}
        snapshot['limitations'] = [
            'Explicit simulated company source manifest; completeness applies only to exact received source rows.',
            ('The regenerated source explicitly attests its full as-of day; later days are unknown and no holdout truth is used.'
             if source_complete_through == source_as_of else
             'The source as-of day is partial; later days are unknown and no holdout truth is used.'),
            'Posted USD cents include monthly seat charges once; included usage and token counters do not add dollars.',
            'Future seats follow aggregate weekday continuation; no separate fixed contract obligation is inferred.',
            'No work exposure or project cost allocation is supplied; unsupported corpus drivers remain context only.',
            'Historical replay requires chronological native receipts; issued ForecastService snapshots preserve prior vintages.',
        ]
        snapshot['company_fixture_revision'] = identity({'source': manifest_hash, 'observations': observations, 'coverage': coverage})
        return snapshot

    @wraps(snapshot_factory)
    def serialized_snapshot(*, now=None, tenant_id='northstar', as_of=None):
        # Multiple dashboard reads share this factory. SQLite releases the GIL
        # while iterating rows, so concurrent full scans can amplify contention.
        # Serialize computation only; every call still reads a fresh native snapshot.
        with snapshot_lock:
            return snapshot_factory(now=now, tenant_id=tenant_id, as_of=as_of)

    serialized_snapshot.supports_as_of = True
    return serialized_snapshot
