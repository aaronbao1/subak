#!/usr/bin/env python3
"""Verify a completed company preview using read-only backup and bounded API checks.

The prepared database is opened only with mode=ro. App startup and TestClient run
against a disposable SQLite backup because startup may capture repository inputs.
Evidence is written only after every assertion succeeds. No live runner is used.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
from time import perf_counter

from company_preview import FINAL, ISSUANCES, FrozenClock, Settings, make_app, save
from fastapi.testclient import TestClient


TOKENS = ('input_tokens', 'cached_input_tokens', 'output_tokens', 'reasoning_tokens')
WIRE_TOKENS = ('inputTokens', 'cachedInputTokens', 'outputTokens', 'reasoningTokens')
COMPONENTS = {'direct_api': 'api', 'billable_overage': 'extra_usage',
              'subscription_fee': 'subscription', 'included_usage': 'included_usage'}
ZERO = Decimal('0.00')
MODULUS = 1 << 256


def instant(value):
    parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


def stamp(value):
    return instant(value).isoformat(timespec='microseconds').replace('+00:00', 'Z')


def money(value):
    return None if value in ('', None) else Decimal(str(value))


def normalize(row):
    """Independent financial/token identity shared by source and native rows."""
    return (row['source_record_key'], stamp(row['occurred_at']), row['source_kind'], row['source_account'],
            row['person_id'], row['team_id'], row['period_id'], row['cost_category'],
            bool(row['counts_toward_spend']), money(row['amount']), row['unit'], row['value_kind'],
            money(row['notional_value']), row['provider'] or None, row['model'] or None,
            *(None if row[field] in ('', None) else int(row[field]) for field in TOKENS))


def source_rows(source, reference):
    people = {p['email'].lower(): p for p in reference['people']}
    mappings = reference['team_mappings']['northstar_billing']
    for path in sorted((source / 'backend' / 'billing').glob('*.csv')):
        with path.open(newline='') as handle:
            for row in csv.DictReader(handle):
                person = people[row['user_email'].lower()]
                day = row['occurred_at'][:10]
                periods = [p['id'] for p in reference['periods'] if p['starts_on'] <= day <= p['ends_on']]
                assert len(periods) == 1, ('source period', row['record_id'])
                yield {**row, 'source_record_key': row['record_id'], 'source_kind': 'northstar_billing',
                       'person_id': person['id'], 'team_id': mappings[row['source_account']],
                       'period_id': periods[0], 'counts_toward_spend': row['cost_category'] != 'included_usage'}


def summarize(rows, *, native=False):
    ids, category_counts, charges = set(), Counter(), defaultdict(lambda: ZERO)
    token_sums, token_present = Counter(), Counter()
    digest_sum = digest_xor = 0
    notional = ZERO
    daily, received_daily, groups = defaultdict(lambda: ZERO), defaultdict(lambda: ZERO), {}
    models, providers = set(), set()
    for row in rows:
        normalized = normalize(row)
        key = normalized[0]
        assert key not in ids, ('duplicate source identity', key)
        ids.add(key)
        digest = int.from_bytes(hashlib.sha256(json.dumps(normalized, default=str, separators=(',', ':')).encode()).digest(), 'big')
        digest_sum = (digest_sum + digest) % MODULUS; digest_xor ^= digest
        day, category = row['occurred_at'][:10], row['cost_category']
        category_counts[category] += 1
        value = money(row['amount']) if row['counts_toward_spend'] else ZERO
        assert row['unit'] == 'USD' and row['value_kind'] == 'simulated'
        assert value is not None and value >= ZERO
        charges[category] += value
        if category == 'included_usage':
            assert money(row['amount']) is None
            notional += money(row['notional_value']) or ZERO
        for field in TOKENS:
            if row[field] not in ('', None):
                token_sums[field] += int(row[field]); token_present[field] += 1
        if row['cached_input_tokens'] not in ('', None):
            assert int(row['cached_input_tokens']) <= int(row['input_tokens'])
        if row['reasoning_tokens'] not in ('', None):
            assert int(row['reasoning_tokens']) <= int(row['output_tokens'])
        if row['model']: models.add(row['model'])
        if row['provider']: providers.add(row['provider'])
        scopes = [('company', 'northstar'), ('team', row['team_id']), ('person', row['person_id'])]
        assert row['team_id'] and row['person_id']
        for scope in scopes:
            daily[(*scope, day)] += value
        if native:
            received = max(instant(row['created_at']), instant(row['batch_created_at']))
            expected_receipt = next(cutoff for cutoff in ISSUANCES if instant(row['occurred_at']) < cutoff)
            assert received == expected_receipt, ('chronological receipt', key, received, expected_receipt)
            assert instant(row['created_at']) == instant(row['batch_created_at'])
            assert row['batch_status'] == 'imported' and not row['counter_reset']
            received_daily[(stamp(received), day, row['team_id'], row['person_id'])] += value
        if day >= '2026-10-01':
            group_key = (row['team_id'], row['person_id'], day, COMPONENTS[category],
                         row['provider'] or 'unknown', row['model'] or '', row['value_kind'])
            group = groups.setdefault(group_key, {'amount': ZERO, 'notional': ZERO, 'count': 0,
                                                  'tokens': Counter(), 'present': Counter()})
            group['amount'] += value; group['count'] += 1
            group['notional'] += money(row['notional_value']) or ZERO
            for field in TOKENS:
                if row[field] not in ('', None):
                    group['tokens'][field] += int(row[field]); group['present'][field] += 1
    summary = {'records': len(ids), 'category_records': dict(category_counts),
               'charged_total': str(sum(charges.values(), ZERO)),
               'charges_by_category': {k: str(v) for k, v in sorted(charges.items())},
               'included_notional': str(notional), 'token_totals': dict(token_sums),
               'token_present_records': dict(token_present),
               'total_tokens': token_sums['input_tokens'] + token_sums['output_tokens'],
               'models': sorted(models), 'providers': sorted(providers),
               'normalized_row_digest_sum': f'{digest_sum:064x}', 'normalized_row_digest_xor': f'{digest_xor:064x}'}
    return summary, ids, daily, received_daily, groups


def total(daily, scope, start, end):
    begin, stop = date.fromisoformat(start), date.fromisoformat(end)
    return sum((daily.get((*scope, (begin + timedelta(days=offset)).isoformat()), ZERO)
                for offset in range((stop - begin).days)), ZERO)


def verify(directory, source):
    began = perf_counter()
    runtime = json.loads((directory / 'runtime.json').read_text())
    publications = json.loads((directory / 'publications.json').read_text())
    assert instant(runtime['clock']) == FINAL and runtime['published_vintages'] == len(publications) == 6, 'Preparation is not final.'
    assert len({p['run_id'] for p in publications}) == 6
    assert runtime['live_request_performed'] is False and runtime['runner_used_for_preparation'] == 'fake'
    assert runtime['publication']['run_id'] == publications[-1]['run_id']
    reference = json.loads((source / 'backend' / 'reference.json').read_text())
    source_as_of = reference['company']['as_of']
    complete_variant = reference['company'].get('complete_through') == source_as_of
    expected_complete_through = (source_as_of if complete_variant else
                                 (date.fromisoformat(source_as_of) - timedelta(days=1)).isoformat())
    source_summary, source_ids, source_daily, _, source_groups = summarize(source_rows(source, reference))
    assert source_summary['records'] == sum(item['records'] for item in reference['billing_files'])
    assert source_summary['records'] >= 330000
    assert len(reference['teams']) == 16 and len(reference['people']) == 130
    assert len(list((source / 'backend' / 'corpus').glob('*.md'))) == 249
    assert len(source_summary['models']) == 14
    checks = {'full_source_records': True, 'source_token_subsets': True}
    with TemporaryDirectory(prefix='company-preview-verification-') as scratch:
        temporary = Path(scratch)
        original = sqlite3.connect((directory / 'app.db').resolve().as_uri() + '?mode=ro', uri=True)
        backup = sqlite3.connect(temporary / 'app.db')
        try:
            original.backup(backup)
        finally:
            original.close(); backup.close()
        connection = sqlite3.connect((temporary / 'app.db').as_uri() + '?mode=ro', uri=True)
        connection.row_factory = sqlite3.Row
        try:
            native_rows = connection.execute('''SELECT u.*, b.created_at AS batch_created_at,
                b.status AS batch_status FROM usage_records u JOIN import_batches b ON b.id=u.import_batch_id''')
            native_summary, native_ids, daily, received_daily, native_groups = summarize(native_rows, native=True)
            assert native_summary == source_summary and native_ids == source_ids
            assert daily == source_daily and native_groups == source_groups
            assert {table: connection.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
                    for table in ('teams', 'people', 'corpus_documents')} == {'teams': 16, 'people': 130, 'corpus_documents': 249}
            assert Decimal(runtime['charged_total']) == Decimal(source_summary['charged_total'])
            assert runtime['records'] == source_summary['records']
            checks.update(native_source_identity=True, native_money_tokens_conserved=True, native_receipts_chronological=True)
            saved_runs = {row['id']: hashlib.sha256(row['bundle'].encode()).hexdigest()
                          for row in connection.execute('SELECT id,bundle FROM forecast_runs')}
            active = connection.execute("SELECT * FROM forecast_publications WHERE tenant_id='northstar'").fetchone()
            assert active['run_id'] == publications[-1]['run_id'] and instant(active['published_at']) == FINAL
            truths = [json.loads(row['payload']) for row in connection.execute("SELECT payload FROM forecast_inputs WHERE kind='truth_revisions'")]
            targets = {value['target_id']: value for row in connection.execute("SELECT payload FROM forecast_inputs WHERE kind='issued_targets'")
                       for value in [json.loads(row['payload'])]}
            publication_run_ids = {v['run_id'] for v in publications}
            checked_truths = 0
            for truth in truths:
                target = targets[truth['target_id']]
                assert target['run_id'] in saved_runs
                assert truth['status'] == 'mature' and truth['complete'] is True and truth['is_synthetic'] is True
                assert truth['provenance']['kind'] == 'observed' and truth['provenance']['reference']
                assert instant(truth['available_at']) <= FINAL and instant(truth['mature_at']) >= instant(truth['end'])
                assert truth['end'] <= '2026-10-19', 'Current partial week must not settle.'
                assert all(truth[key] == target[key] for key in ('quantity', 'unit', 'basis', 'timezone', 'scope_type', 'scope_id', 'start', 'end'))
                expected = total(daily, (truth['scope_type'], truth['scope_id']), truth['start'], truth['end'])
                assert Decimal(str(truth['value'])) == expected, ('exact scope outcome', truth['target_id'])
                checked_truths += 1
            assert checked_truths > 0
            final_bundle = None
            for vintage, expected_cutoff in zip(publications, ISSUANCES):
                assert instant(vintage['information_cutoff']) == instant(vintage['issued_at']) == expected_cutoff
                row = connection.execute('SELECT * FROM forecast_runs WHERE id=?', (vintage['run_id'],)).fetchone()
                assert row['snapshot_id'] == vintage['snapshot_id']
                assert instant(row['generated_at']) == expected_cutoff
                snapshot = json.loads(connection.execute('SELECT payload FROM forecast_input_snapshots WHERE id=?', (row['snapshot_id'],)).fetchone()[0])
                assert instant(snapshot['information_cutoff']) == expected_cutoff
                assert hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest() == vintage['snapshot_hash']
                expected = defaultdict(lambda: ZERO)
                for (received, day, team, person), value in received_daily.items():
                    if instant(received) <= expected_cutoff and day < snapshot['forecast_start']:
                        expected[(day, team, person)] += value
                actual = {}
                for observed in snapshot['observations']:
                    assert instant(observed['available_at']) <= expected_cutoff and observed['date'] < snapshot['forecast_start']
                    assert observed.get('exposure') is None and observed.get('project_id') is None
                    key = (observed['date'], observed['team_id'], observed['person_id'])
                    assert key not in actual
                    actual[key] = Decimal(observed['recorded_amount'])
                    assert Decimal(observed['quantity']) == actual[key] == expected.get(key, ZERO)
                assert all(actual.get(key, ZERO) == value for key, value in expected.items())
                assert all(instant(t['available_at']) <= expected_cutoff for t in snapshot.get('truth_revisions', []))
                assert all(r['date'] <= expected_complete_through for r in snapshot['coverage'] if r['complete'])
                bundle = json.loads(row['bundle'])
                company = next(v for v in bundle['views'] if v['scope']['type'] == 'company')
                assert company['scope']['id'] == 'northstar'
                assert instant(company['publication']['published_at']) == expected_cutoff
                assert instant(company['publication']['issued_at']) == expected_cutoff
                assert instant(company['publication']['information_cutoff']) == expected_cutoff
                assert company['weekly'] == vintage['weekly'] and company['quarter_outlook'] == vintage['quarter']
                assert all(point['base'] is not None for point in company['weekly'])
                if expected_cutoff == FINAL:
                    final_bundle = bundle
                    assert snapshot['history_complete_through'] == expected_complete_through
                    assert next(c for c in snapshot['coverage'] if c['date'] == source_as_of)['complete'] is complete_variant
                    assert (company['quarter_outlook']['base'] is not None) is complete_variant
                    assert abs(Decimal(str(company['components']['recorded'])) - total(daily, ('company', 'northstar'), '2026-10-01', '2026-10-25')) < Decimal('0.00000001')
            assert final_bundle is not None
            checks.update(immutable_vintage_snapshots=True, issued_observations_exact_native_cents=True,
                          exact_mature_outcomes_all_scopes=True, final_quarter_completeness_honest=True)
        finally:
            connection.close()
        # Startup may write captures to this disposable copy only.
        app = make_app(temporary, source, FrozenClock(FINAL), settings=Settings(droid_runner='fake'), worker=False)
        scope_ids = [('company', 'northstar')]
        scope_ids.extend(('team', t['id']) for t in reference['teams'][:2])
        scope_ids.extend(('person', p['id']) for p in reference['people'][:2])
        api_summaries = []
        with TestClient(app) as client:
            def get(path, **params):
                response = client.get(path, params=params)
                assert response.status_code == 200, (path, response.status_code, response.text[:500])
                return response.json()
            company = get('/compat/api/company')
            assert company['id'] == 'northstar' and company['name'] == 'Uber'
            assert len(get('/compat/api/people')) == 130
            teams = get('/compat/api/teams')
            assert len(teams) == 16 and len({t['color'] for t in teams}) == 16
            for scope in scope_ids:
                kind, ident = scope
                history = get('/compat/api/forecast-weekly-history', scope_type=kind, scope_id=ident,
                              start_date='2026-09-21', end_date_exclusive='2026-11-16')
                closed = [w for w in history['weeks'] if w['state'] == 'closed']
                assert len(closed) == 4 and history['scope'] == {'type': kind, 'id': ident}
                for week in closed:
                    expected = total(daily, scope, week['start'], week['end_exclusive'])
                    assert week['actual']['status'] == 'mature' and week['actual']['source'] == 'observed_outcome'
                    assert Decimal(week['actual']['amount']) == expected
                    prior = week['prior_forecast']; assert prior and prior['run_id'] in publication_run_ids
                    selected_run = next(p['run_id'] for p in publications
                                        if instant(p['information_cutoff']).date().isoformat() == week['start'])
                    assert prior['run_id'] == selected_run
                    assert instant(prior['issued_at']) <= instant(week['start'])
                    assert week['variance']['status'] == 'available'
                    assert Decimal(week['variance']['amount']) == expected - Decimal(prior['amount'])
                current = next(w for w in history['weeks'] if w['state'] == 'current')
                assert current['actual']['status'] == 'partial'
                assert current['variance']['amount'] is None and current['variance']['status'] == 'unavailable'
                assert Decimal(current['actual']['amount']) == total(daily, scope, '2026-10-19', '2026-10-26')
                future = [w for w in history['weeks'] if w['state'] == 'future']
                assert future and all(w['actual']['amount'] is None and w['outlook'] and w['outlook']['amount'] is not None for w in future)
                assert all(w['outlook']['run_id'] == publications[-1]['run_id'] for w in future)
                api_summaries.append({'scope_type': kind, 'scope_id': ident,
                    'closed_actuals': [w['actual']['amount'] for w in closed], 'current_actual': current['actual']['amount'],
                    'future_outlook_weeks': len(future)})
            ledger = get('/api/usage/daily', scope_type='company', start_date='2026-09-21', end_date_exclusive='2026-10-26')
            for bucket in ledger['buckets']:
                expected = daily.get(('company', 'northstar', bucket['date']))
                assert money(bucket['recorded_spend']) == expected
            compat = get('/compat/api/spending')
            assert len(compat) == len(native_groups)
            seen = set()
            for row in compat:
                key = (row['teamId'], row.get('personId'), row['date'], row['component'], row['provider'], row.get('model') or '', 'simulated')
                assert key not in seen and key in native_groups
                seen.add(key); expected = native_groups[key]
                assert Decimal(str(row['amount'])) == expected['amount']
                assert row['provenance'] == 'simulated' and row['unit'] == 'usd'
                for native_field, wire_field in zip(TOKENS, WIRE_TOKENS):
                    value = expected['tokens'][native_field] if expected['present'][native_field] == expected['count'] else None
                    assert row.get(wire_field) == value
                total_tokens = None if row.get('inputTokens') is None or row.get('outputTokens') is None else row['inputTokens'] + row['outputTokens']
                assert row.get('tokens') == total_tokens
                if row['component'] == 'included_usage':
                    assert row['amount'] == 0 and money(row.get('includedUsageNotional')) == expected['notional']
            assert sum((Decimal(str(r['amount'])) for r in compat), ZERO) == total(daily, ('company', 'northstar'), '2026-10-01', '2026-10-25')
            checks.update(company_api_identity=True, representative_weekly_apis=True, current_variance_withheld=True,
                          future_weekly_outlook_usable=True, daily_api_exact_native_money=True,
                          compat_q4_money_model_provider_token_conservation=True, distinct_team_colors=True)
        app.state.engine.dispose()
        with sqlite3.connect((temporary / 'app.db').as_uri() + '?mode=ro', uri=True) as final_connection:
            after = {row[0]: hashlib.sha256(row[1].encode()).hexdigest() for row in final_connection.execute('SELECT id,bundle FROM forecast_runs')}
            assert after == saved_runs, 'Read/API verification changed an issued forecast.'
        checks['issued_runs_unchanged_after_api_reads'] = True
    report = {'passed': True, 'checks': checks, 'immutable_vintages': 6, 'stored_runs': len(saved_runs),
              'mature_outcomes_checked': checked_truths, 'native_records': source_summary['records'],
              'teams': 16, 'people': 130, 'documents': 249, 'charged_total': source_summary['charged_total'],
              'representative_api_scopes': api_summaries, 'elapsed_seconds': round(perf_counter() - began, 3),
              'partial_source_day': None if complete_variant else source_as_of,
              'history_complete_through': expected_complete_through,
              'quarter_outlook': ('available from explicitly regenerated complete source days' if complete_variant else
                                  'unavailable because the current source day is partial'),
              'verification_database': 'disposable SQLite backup; prepared database opened mode=ro only',
              'live_request_performed': False,
              'limitations': ['Generated company source; no real-world forecast accuracy claim.',
                              'No live Factory/Droid call or connector access was performed.',
                              'Work exposure and project cost allocation are not supplied; aggregate weekday continuation is used.']}
    save(directory / 'source-counts.json', source_summary)
    save(directory / 'verification.json', report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--source', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.directory.resolve(), args.source.resolve()), indent=2))


if __name__ == '__main__':
    main()
