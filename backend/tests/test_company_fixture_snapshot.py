"""The opt-in company manifest attests posted cents, never guessed quantities."""
import csv
import io
import json
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import event, select

from app.core.clock import FrozenClock, SequentialIdFactory
from app.db.base import create_all, make_engine, make_session_factory
from app.db.models import ImportBatch, Person, PlanningPeriod, Team, TeamMapping, UsageRecord
from app.services.imports import run_import


def instant(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


@pytest.fixture
def company(tmp_path):
    source = tmp_path / 'source'
    (source / 'backend' / 'billing').mkdir(parents=True)
    (source / 'csv').mkdir()
    reference = {
        'company': {'id': 'uber-sim', 'name': 'Uber', 'simulated': True, 'as_of': '2026-01-03'},
        'periods': [{'id': 'q1', 'starts_on': '2026-01-01', 'ends_on': '2026-03-31'}],
        'teams': [{'id': 'eng', 'name': 'Engineering'}, {'id': 'other', 'name': 'Other'}],
        'people': [{'id': 'a', 'team': 'eng', 'name': 'A Person', 'email': 'a@example.test'},
                   {'id': 'later', 'team': 'eng', 'name': 'Later Person', 'email': 'later@example.test'}],
        'team_mappings': {'northstar_billing': {'ws-eng': 'eng'}},
    }
    (source / 'backend' / 'reference.json').write_text(json.dumps(reference))
    (source / 'csv' / 'people.csv').write_text(
        'id,team_id,start_date,end_date\na,eng,2025-01-01,\nlater,eng,2026-02-01,\n')
    (source / 'csv' / 'calendar.csv').write_text(
        'day,is_partial,is_future\n2026-01-01,0,0\n2026-01-02,0,0\n2026-01-03,1,0\n')
    header = ['record_id', 'occurred_at', 'source_account', 'user_email', 'provider', 'model',
              'cost_category', 'value_kind', 'amount', 'unit', 'notional_value', 'input_tokens',
              'output_tokens', 'description']
    records = [
        ['api-a', '2026-01-01T12:00:00Z', 'ws-eng', 'a@example.test', 'openai', 'A', 'direct_api', 'simulated', '0.10', 'USD', '', '1000000', '1000000', 'API'],
        ['api-b', '2026-01-01T12:00:00Z', 'ws-eng', 'a@example.test', 'openai', 'B', 'direct_api', 'simulated', '0.20', 'USD', '', '1', '1', 'API'],
        ['seat', '2026-01-01T00:00:00Z', 'ws-eng', 'a@example.test', 'openai', '', 'subscription_fee', 'simulated', '1.00', 'USD', '', '', '', 'Seat'],
        ['included', '2026-01-01T12:00:00Z', 'ws-eng', 'a@example.test', 'openai', 'A', 'included_usage', 'simulated', '', 'USD', '999.00', '100', '100', 'Included'],
        ['partial', '2026-01-03T12:00:00Z', 'ws-eng', 'a@example.test', 'openai', 'A', 'direct_api', 'simulated', '0.40', 'USD', '', '1', '1', 'Partial'],
    ]
    output = io.StringIO(); writer = csv.writer(output); writer.writerow(header); writer.writerows(records)
    raw = output.getvalue().encode()
    (source / 'backend' / 'billing' / 'all.csv').write_bytes(raw)
    engine = make_engine(tmp_path / 'native.sqlite'); create_all(engine)
    factory = make_session_factory(engine)
    created = instant('2026-01-01T00:00:00Z')
    with factory() as session:
        session.add(PlanningPeriod(id='q1', label='Q1', starts_on=date(2026, 1, 1), ends_on=date(2026, 3, 31), created_at=created))
        session.add_all([Team(id=t['id'], name=t['name'], created_at=created) for t in reference['teams']])
        session.flush()
        session.add_all([Person(id=p['id'], team_id=p['team'], name=p['name'], email=p['email'],
                               is_simulated=True, created_at=created) for p in reference['people']])
        session.add(TeamMapping(id='map', source_kind='northstar_billing', source_account='ws-eng',
                               team_id='eng', effective_from=date(2026, 1, 1), created_by='test', created_at=created))
        session.commit()
        # Import the real source through the actual native importer. Future usage
        # in an earlier receipt must still be hidden by occurrence cutoff.
        result = run_import(session, source_kind='northstar_billing', raw=raw, filename='all.csv',
                            actor_id='test', clock=FrozenClock(instant('2026-01-02T00:00:00Z')),
                            ids=SequentialIdFactory())
        assert result.batch.status == 'imported'
        session.commit()
    yield factory, source, engine
    engine.dispose()


def snapshot(company, now='2026-01-04T00:00:00Z'):
    from app.forecasting.company_fixture import company_fixture_snapshot_factory
    factory, source, _ = company
    return company_fixture_snapshot_factory(factory, source, lambda: now)(now=now)


def coverage(result):
    return {row['date']: row['complete'] for row in result['coverage']}


def test_exact_posted_cents_complete_zero_and_partial_source_boundary(company):
    result = snapshot(company)
    observed = {row['date']: row for row in result['observations']}
    assert observed['2026-01-01']['quantity'] == '1.30'
    assert observed['2026-01-02']['quantity'] == '0.00'
    assert observed['2026-01-03']['quantity'] == '0.40'
    assert coverage(result) == {'2026-01-01': True, '2026-01-02': True, '2026-01-03': False}
    assert result['history_complete_through'] == '2026-01-02'
    assert all(row.get('exposure') is None and row['project_id'] is None for row in observed.values())
    assert result['memberships'] == [] and result['drivers'] == []
    assert result['pricing'][0]['rate'] == '1' and result['pricing'][0].get('fixed', 0) == 0
    assert result['company_fixture_manifest']['source_company_id'] == 'uber-sim'
    assert {p['id'] for p in result['people']} == {'a'}


def test_missing_included_row_withdraws_completeness_without_changing_money(company):
    factory, _, _ = company
    with factory() as session:
        row = session.scalar(select(UsageRecord).where(UsageRecord.source_record_key == 'included'))
        session.delete(row); session.commit()
    result = snapshot(company)
    assert coverage(result)['2026-01-01'] is False
    assert next(r for r in result['observations'] if r['date'] == '2026-01-01')['quantity'] == '1.30'
    assert result['company_fixture_manifest']['days'][0]['missing_record_count'] == 1


@pytest.mark.parametrize('field,value', [('amount', Decimal('0.11')), ('team_id', 'other'),
                                         ('person_id', None), ('unit', 'EUR')])
def test_changed_native_record_cannot_inherit_source_completeness(company, field, value):
    factory, _, _ = company
    with factory() as session:
        row = session.scalar(select(UsageRecord).where(UsageRecord.source_record_key == 'api-a'))
        setattr(row, field, value); session.commit()
    result = snapshot(company)
    assert coverage(result)['2026-01-01'] is False
    assert result['company_fixture_manifest']['days'][0]['mismatched_record_count'] == 1


def test_receipt_and_occurrence_cutoffs_prevent_future_leakage(company):
    before = snapshot(company, '2026-01-01T23:59:59Z')
    assert before['observations'] == []
    assert not any(coverage(before).values())
    received = snapshot(company, '2026-01-02T00:00:00Z')
    assert sum(Decimal(r['quantity']) for r in received['observations']) == Decimal('1.30')
    assert all(r['date'] < '2026-01-03' for r in received['observations'])
    assert not coverage(received).get('2026-01-02', False)
    factory, _, _ = company
    with factory() as session:
        batch = session.scalar(select(ImportBatch))
        batch.created_at = instant('2026-01-05T00:00:00Z'); session.commit()
    assert snapshot(company)['observations'] == []


def test_snapshot_is_read_only_and_builds_without_invented_exposure(company):
    from forecasting.planning import build_forecast
    _, _, engine = company
    statements = []
    def record(_conn, _cursor, statement, *_args):
        statements.append(statement.lstrip().split()[0].upper())
    event.listen(engine, 'after_cursor_execute', record)
    try:
        result = snapshot(company)
        bundle = build_forecast(result, run_id='company-test', generated_at='2026-01-04T00:00:00Z')
        assert bundle['views'][0]['components']['recorded'] == pytest.approx(1.70)
        assert bundle['views'][0]['daily'][0]['base'] is not None
        assert bundle['views'][0]['quarter_outlook']['base'] is None
        assert not {'INSERT', 'UPDATE', 'DELETE', 'REPLACE', 'CREATE', 'DROP', 'ALTER'} & set(statements)
    finally:
        event.remove(engine, 'after_cursor_execute', record)


def test_unexpected_row_revokes_manifest_day_but_preserves_native_charge(company):
    factory, _, _ = company
    with factory() as session:
        original = session.scalar(select(UsageRecord).where(UsageRecord.source_record_key == 'api-a'))
        session.add(UsageRecord(id='unexpected', import_batch_id=original.import_batch_id,
            source_kind='northstar_billing', source_record_key='unexpected', source_account='ws-eng',
            team_id='eng', person_id='a', period_id='q1', occurred_at=original.occurred_at,
            created_at=original.created_at, amount=Decimal('2.00'), unit='USD',
            cost_category='direct_api', counts_toward_spend=True, value_kind='simulated'))
        session.commit()
    result = snapshot(company)
    assert coverage(result)['2026-01-01'] is False
    assert next(r for r in result['observations'] if r['date'] == '2026-01-01')['quantity'] == '3.30'
    assert result['company_fixture_manifest']['days'][0]['unexpected_record_count'] == 1


def test_moved_row_withdraws_both_original_day_and_false_empty_day(company):
    factory, _, _ = company
    with factory() as session:
        row = session.scalar(select(UsageRecord).where(UsageRecord.source_record_key == 'api-a'))
        row.occurred_at = instant('2026-01-02T12:00:00Z'); session.commit()
    result = snapshot(company)
    assert coverage(result)['2026-01-01'] is False
    assert coverage(result)['2026-01-02'] is False
    assert sum(Decimal(r['quantity']) for r in result['observations']) == Decimal('1.70')


def test_factory_requires_explicit_simulated_source(company):
    from app.forecasting.company_fixture import company_fixture_snapshot_factory
    factory, source, _ = company
    path = source / 'backend' / 'reference.json'
    reference = json.loads(path.read_text()); reference['company']['simulated'] = False
    path.write_text(json.dumps(reference))
    with pytest.raises(ValueError, match='explicitly simulated'):
        company_fixture_snapshot_factory(factory, source, lambda: '2026-01-04T00:00:00Z')


def test_unchanged_source_revision_does_not_change_with_read_clock(company):
    first = snapshot(company, '2026-01-04T00:00:00Z')
    later = snapshot(company, '2026-01-04T12:00:00Z')
    assert first['company_fixture_revision'] == later['company_fixture_revision']
    assert 'repository_revision' not in first


def test_synthetic_zero_never_predates_directory_receipt(company):
    factory, _, _ = company
    with factory() as session:
        session.get(Person, 'a').created_at = instant('2026-01-03T15:00:00Z')
        session.commit()
    result = snapshot(company)
    zero = next(row for row in result['observations'] if row['date'] == '2026-01-02')
    assert instant(zero['available_at']) >= instant('2026-01-03T15:00:00Z')


def test_unknown_native_directory_cannot_establish_attributed_completeness(company):
    factory, _, _ = company
    with factory() as session:
        session.get(Person, 'a').created_at = instant('2026-01-05T00:00:00Z')
        session.commit()
    result = snapshot(company)
    assert coverage(result)['2026-01-01'] is False


def test_usd_identity_conversion_preserves_weekly_path_across_quarter_boundary(company):
    from forecasting.planning import build_forecast
    result = snapshot(company, '2026-03-30T00:00:00Z')
    bundle = build_forecast(result, run_id='quarter-boundary', generated_at='2026-03-30T00:00:00Z')
    assert all(point['base'] is not None for point in bundle['views'][0]['weekly'])


def test_explicit_full_day_source_attests_as_of_only_after_day_close(company):
    from forecasting.planning import build_forecast
    factory, source, _ = company
    ref_path = source / 'backend' / 'reference.json'
    reference = json.loads(ref_path.read_text())
    reference['company']['complete_through'] = '2026-01-03'
    ref_path.write_text(json.dumps(reference))
    calendar = source / 'csv' / 'calendar.csv'
    calendar.write_text(calendar.read_text().replace('2026-01-03,1,0', '2026-01-03,0,0'))
    # A different source contains full-day posted amounts; the earlier partial
    # fixture is not simply marked complete in the native ledger.
    billing = source / 'backend' / 'billing' / 'all.csv'
    billing.write_text(billing.read_text().replace('simulated,0.40,USD', 'simulated,0.80,USD'))
    with factory() as session:
        session.scalar(select(UsageRecord).where(UsageRecord.source_record_key == 'partial')).amount = Decimal('0.80')
        session.commit()
    before_close = snapshot(company, '2026-01-03T23:59:59Z')
    assert coverage(before_close)['2026-01-03'] is False
    complete = snapshot(company)
    assert coverage(complete)['2026-01-03'] is True
    assert complete['history_complete_through'] == '2026-01-03'
    assert sum(Decimal(r['quantity']) for r in complete['observations']) == Decimal('2.10')
    bundle = build_forecast(complete, run_id='completed-source', generated_at='2026-01-04T00:00:00Z')
    assert bundle['views'][0]['quarter_outlook']['base'] is not None
    assert all(r['date'] < '2026-01-04' for r in complete['observations'])


def test_complete_through_metadata_cannot_relabel_original_partial_calendar(company):
    factory, source, _ = company
    ref_path = source / 'backend' / 'reference.json'
    reference = json.loads(ref_path.read_text()); reference['company']['complete_through'] = '2026-01-03'
    ref_path.write_text(json.dumps(reference))
    with pytest.raises(ValueError, match='calendar'):
        snapshot(company)


def test_datagen_complete_day_opt_in_changes_only_the_final_calendar_flag(monkeypatch):
    from pathlib import Path
    from datetime import timedelta
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / 'datagen'))
    from uberdata import config
    from uberdata.usage import build_calendar
    begin, end = config.AS_OF - timedelta(days=1), config.AS_OF + timedelta(days=1)
    monkeypatch.setattr(config, 'COMPLETE_AS_OF_DAY', False)
    partial = build_calendar(begin, end)
    monkeypatch.setattr(config, 'COMPLETE_AS_OF_DAY', True)
    complete = build_calendar(begin, end)
    assert partial[config.AS_OF].partial is True and complete[config.AS_OF].partial is False
    assert partial[begin] == complete[begin] and partial[end] == complete[end]


def test_one_factory_serializes_concurrent_source_scans_and_rereads_corrections(company):
    from concurrent.futures import ThreadPoolExecutor
    from contextlib import contextmanager
    from threading import Event, Lock
    from app.forecasting.company_fixture import company_fixture_snapshot_factory
    sessions, source, _ = company
    first_entered, release_first, second_entered, second_started = Event(), Event(), Event(), Event()
    counters = {'active': 0, 'peak': 0, 'calls': 0}
    counter_lock = Lock()

    @contextmanager
    def observed_sessions():
        with counter_lock:
            counters['active'] += 1
            counters['calls'] += 1
            number = counters['calls']
            counters['peak'] = max(counters['peak'], counters['active'])
        try:
            if number == 1:
                first_entered.set()
                assert release_first.wait(3)
            else:
                second_entered.set()
            with sessions() as session:
                yield session
        finally:
            with counter_lock:
                counters['active'] -= 1

    now = '2026-01-04T00:00:00Z'
    factory = company_fixture_snapshot_factory(observed_sessions, source, lambda: now)
    def second():
        second_started.set()
        return factory(now=now)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(factory, now=now)
        assert first_entered.wait(2)
        later = pool.submit(second)
        assert second_started.wait(2)
        try:
            assert not second_entered.wait(.2), 'a second full source scan entered concurrently'
        finally:
            release_first.set()
        before, other = first.result(timeout=3), later.result(timeout=3)
    assert counters == {'active': 0, 'peak': 1, 'calls': 2}
    assert before == other
    with sessions() as session:
        row = session.scalar(select(UsageRecord).where(UsageRecord.source_record_key == 'api-a'))
        row.amount = Decimal('0.11')
        session.commit()
    after = factory(now=now)
    assert counters['calls'] == 3
    assert after['company_fixture_revision'] != before['company_fixture_revision']
    assert next(r for r in after['observations'] if r['date'] == '2026-01-01')['quantity'] == '1.31'
    assert coverage(after)['2026-01-01'] is False


def test_factory_exception_releases_serialization_for_another_thread(company):
    from concurrent.futures import ThreadPoolExecutor
    from contextlib import contextmanager
    from app.forecasting.company_fixture import company_fixture_snapshot_factory
    sessions, source, _ = company
    calls = 0
    @contextmanager
    def flaky_sessions():
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError('source temporarily unavailable')
        with sessions() as session:
            yield session
    now = '2026-01-04T00:00:00Z'
    factory = company_fixture_snapshot_factory(flaky_sessions, source, lambda: now)
    with pytest.raises(RuntimeError, match='temporarily unavailable'):
        factory(now=now)
    with ThreadPoolExecutor(max_workers=1) as pool:
        fresh = pool.submit(factory, now=now).result(timeout=3)
    assert fresh['history_complete_through'] == '2026-01-02'
    assert calls == 2
