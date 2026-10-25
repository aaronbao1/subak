"""Static weekly export keeps the live reader's receipts and cannot write its source DB."""
from contextlib import nullcontext
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch
import sqlite3

from app.core.clock import FrozenClock
from app.forecasting.company_fixture import company_fixture_snapshot_factory
from app.forecasting.persistence import ForecastStore
from app.forecasting.weekly_history import weekly_history
from app.schemas.weekly_history import WeeklyHistoryResponse
from app.services.source_completion import source_completion
from app.services.usage import daily_usage
from test_company_fixture_snapshot import company, instant


def test_export_reuses_source_receipts_and_matches_native_wire_for_all_requested_scopes(company):
    from datagen.interactive_demo_weekly import export_weekly_history

    factory, source, engine = company
    db = engine.url.database
    ForecastStore(db)  # Test setup only: exporter must never create forecast tables.
    now = instant('2026-01-04T00:00:00Z')
    begin, end = date(2025, 12, 29), date(2026, 1, 12)
    scopes = [('company', 'northstar'), ('team', 'eng'), ('person', 'a')]
    expected = []
    with factory() as session:
        clock = FrozenClock(now)
        selected = company_fixture_snapshot_factory(lambda: nullcontext(session), source, clock)
        session.info['forecast_service'] = SimpleNamespace(snapshot_factory=selected)
        assert source_completion(session, now) is not None
        svc = SimpleNamespace(now=lambda: now, store=ForecastStore(db))
        for kind, scope_id in scopes:
            ledger = daily_usage(session, scope_type=kind, scope_id=None if kind == 'company' else scope_id,
                                 start_date=begin, end_date_exclusive=end, provider=None, model=None, clock=clock)
            expected.append(WeeklyHistoryResponse.model_validate(weekly_history(svc, ledger, scope_type=kind,
                            scope_id=scope_id, start_date=begin, end_date_exclusive=end)).model_dump(mode='json'))
    calls = []
    def counted_factory(*args, **kwargs):
        real = company_fixture_snapshot_factory(*args, **kwargs)
        def read(**kw):
            calls.append(kw)
            return real(**kw)
        return read
    with patch('datagen.interactive_demo_weekly.company_fixture_snapshot_factory', counted_factory):
        actual = export_weekly_history(db, source, now, scopes, begin, end)
    assert actual == expected
    assert len(calls) == 1
    assert len(actual) == 3
    assert all(wire['weeks'][0]['actual']['amount'] == '1.7' for wire in actual)
    assert all(wire['weeks'][0]['variance']['amount'] is None for wire in actual)


def test_export_connection_is_enforced_read_only(company):
    from datagen.interactive_demo_weekly import export_weekly_history

    _, source, engine = company
    ForecastStore(engine.url.database)
    attempted = []
    def check_read_only(session_factory, directory, clock):
        with session_factory() as session:
            connection = session.connection().connection.driver_connection
            assert connection.execute('PRAGMA query_only').fetchone()[0] == 1
            try:
                connection.execute('CREATE TABLE forbidden_export_write(value TEXT)')
            except sqlite3.OperationalError as exc:
                assert 'readonly' in str(exc).lower()
                attempted.append(True)
            else:
                raise AssertionError('export accepted a database write')
        return company_fixture_snapshot_factory(session_factory, directory, clock)
    with patch('datagen.interactive_demo_weekly.company_fixture_snapshot_factory', check_read_only):
        export_weekly_history(engine.url.database, source, instant('2026-01-04T00:00:00Z'),
                              [{'type': 'company', 'id': 'northstar'}], '2025-12-29', '2026-01-05')
    assert attempted == [True]
