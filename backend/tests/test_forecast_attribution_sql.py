"""Exact, grouped attribution and the SQLite integer-overflow escape hatch."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models import ImportBatch, Person, PlanningPeriod, Team, UsageRecord
from app.services.forecasts import attribution_for_period


@pytest.fixture
def ledger():
    # Leave SQLite's FK enforcement off in this isolated fixture so historical orphaned
    # team/person references can exercise the existing defensive attribution semantics.
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        period = PlanningPeriod(id="current", label="Current", starts_on=date(2026, 10, 1),
                                ends_on=date(2026, 12, 31))
        session.add_all([
            period,
            PlanningPeriod(id="other", label="Other", starts_on=date(2026, 1, 1),
                           ends_on=date(2026, 3, 31)),
            Team(id="alpha", name="Alpha"), Team(id="beta", name="Beta"),
            Team(id="inactive", name="Inactive", active=False),
            Person(id="aa", name="First", team_id="alpha"),
            Person(id="ab", name="Second", team_id="alpha"),
            Person(id="az", name="Last", team_id="alpha"),
            Person(id="unused", name="Unused", team_id="alpha"),
            Person(id="inactive-person", name="Inactive", team_id="alpha", active=False),
            Person(id="beta-person", name="Beta", team_id="beta"),
            ImportBatch(id="batch", source_kind="test", content_hash="test", status="imported",
                        imported_by="test", value_kind_default="measured"),
        ])
        session.flush()
        yield session, period
    engine.dispose()


def add_usage(session, key, amount, *, team="alpha", person="aa", day=2, period="current",
              counted=True):
    session.add(UsageRecord(
        id=key, import_batch_id="batch", source_kind="test", source_record_key=key,
        team_id=team, person_id=person, period_id=period,
        occurred_at=datetime(2026, 10, day, tzinfo=timezone.utc),
        amount=None if amount is None else Decimal(amount), value_kind="measured",
        cost_category="direct_api" if counted else "included_usage", counts_toward_spend=counted,
    ))


@contextmanager
def usage_queries(session):
    queries = []

    def record(_connection, _cursor, statement, parameters, _context, _many):
        if statement.lstrip().upper().startswith("SELECT") and "FROM usage_records" in statement:
            queries.append((statement, parameters))

    engine = session.get_bind()
    event.listen(engine, "before_cursor_execute", record)
    try:
        yield queries
    finally:
        event.remove(engine, "before_cursor_execute", record)


def test_normal_attribution_uses_a_single_covering_query(ledger):
    session, period = ledger
    for index in range(300):
        add_usage(session, f"cent-{index}", "0.01")
    session.flush()

    with usage_queries(session) as queries:
        result = attribution_for_period(session, period, ["alpha", "beta"])

    assert result.teams["alpha"].people["aa"] == Decimal("3.00")
    assert len(queries) == 1
    statement, parameters = queries[0]
    plan = session.connection().exec_driver_sql("EXPLAIN QUERY PLAN " + statement, parameters).all()
    assert any("USING COVERING INDEX ix_usage_records_spend_to_date" in row[-1] for row in plan)
    assert not any("USE TEMP B-TREE" in row[-1] for row in plan)
    # Grouping keeps the number of rows crossing into Python independent of usage volume.
    assert len(session.connection().exec_driver_sql(statement, parameters).all()) == 1


def test_attribution_preserves_cents_refunds_membership_and_as_of(ledger):
    session, period = ledger
    for key, amount in [("tenths", "0.10"), ("fifths", "0.20"), ("refund", "-0.03"),
                        ("binary-fraction", "0.29"), ("second-fraction", "0.58")]:
        add_usage(session, key, amount)
    add_usage(session, "second", "-1.25", person="ab", day=3)
    add_usage(session, "no-person", "1.23", person=None, day=4)
    add_usage(session, "inactive-person", "2.34", person="inactive-person", day=5)
    add_usage(session, "unknown-person", "3.45", person="missing-person", day=6)
    add_usage(session, "other-team-person", "4.56", person="beta-person", day=7)
    add_usage(session, "beta", "0.01", team="beta", person="beta-person", day=8)
    add_usage(session, "inactive-team", "500.00", team="inactive", day=9)
    add_usage(session, "unknown-team", "600.00", team="missing-team", day=10)
    add_usage(session, "unmapped", "700.00", team=None, person=None, day=11)
    add_usage(session, "null", None, day=29)
    add_usage(session, "nonspend", "800.00", counted=False, day=30)
    add_usage(session, "wrong-period", "900.00", period="other", day=31)
    session.flush()

    result = attribution_for_period(session, period, ["alpha", "beta"])

    assert result.as_of == date(2026, 10, 11)
    assert result.period_start == date(2026, 10, 1)
    assert result.period_end == date(2026, 12, 31)
    assert set(result.teams) == {"alpha", "beta"}
    assert result.teams["alpha"].people == {
        "aa": Decimal("1.14"), "ab": Decimal("-1.25"), "az": Decimal("0"), "unused": Decimal("0"),
    }
    assert result.teams["alpha"].team_level == Decimal("11.58")
    assert result.teams["beta"].people == {"beta-person": Decimal("0.01")}
    assert result.teams["beta"].team_level == Decimal("0")


@pytest.mark.parametrize("excluded_rows", [False, True])
def test_empty_spend_keeps_zero_active_people_and_no_as_of(ledger, excluded_rows):
    session, period = ledger
    if excluded_rows:
        add_usage(session, "null", None)
        add_usage(session, "nonspend", "100.00", counted=False)
        add_usage(session, "other-period", "100.00", period="other")
    session.flush()

    result = attribution_for_period(session, period, ["alpha", "beta"])

    assert result.as_of is None
    assert result.teams["alpha"].people == dict.fromkeys(["aa", "ab", "az", "unused"], Decimal("0"))
    assert all(team.team_level == Decimal("0") for team in result.teams.values())


def test_no_selected_teams_still_observes_unmapped_spend_date(ledger):
    session, period = ledger
    add_usage(session, "unknown", "0.01", team="missing-team", day=12)
    session.flush()

    result = attribution_for_period(session, period, [])

    assert result.teams == {}
    assert result.as_of == date(2026, 10, 12)


@pytest.mark.parametrize(("amount", "expected"), [
    ("999999999999999.99", "99999999999999999.00"),
    ("-999999999999999.99", "-99999999999999999.00"),
])
def test_integer_overflow_restarts_from_decimal_rows_without_counting_earlier_groups_twice(
    ledger, amount, expected,
):
    session, period = ledger
    # Two complete groups precede the overflowing group, so SQLite has already delivered
    # a result when the later group fails. A fallback must discard that partial aggregate.
    add_usage(session, "early-a", "0.29", person="aa")
    add_usage(session, "early-b", "0.58", person="ab")
    for index in range(100):
        add_usage(session, f"huge-{index}", amount, person="az", day=20)
    add_usage(session, "team-level", "-0.03", person=None, day=21)
    add_usage(session, "unknown", "0.01", team="unknown", day=22)
    add_usage(session, "excluded", "100.00", counted=False, day=30)
    session.flush()

    with usage_queries(session) as queries:
        result = attribution_for_period(session, period, ["alpha", "beta"])

    assert result.teams["alpha"].people == {
        "aa": Decimal("0.29"), "ab": Decimal("0.58"), "az": Decimal(expected), "unused": Decimal("0"),
    }
    assert result.teams["alpha"].team_level == Decimal("-0.03")
    assert result.as_of == date(2026, 10, 22)
    assert len(queries) == 2  # Attempt the efficient grouped path, then stream the exact source rows.

    # Confirm the boundary condition is real SQLite behavior, including a successfully
    # consumed group before the overflow, rather than a simulated exception.
    statement, parameters = queries[0]
    cursor = session.connection().connection.cursor()
    try:
        cursor.execute(statement, parameters)
        assert cursor.fetchone() is not None
        with pytest.raises(sqlite3.OperationalError, match="integer overflow"):
            cursor.fetchall()
    finally:
        cursor.close()


def test_overflow_before_first_group_with_offsetting_refunds_remains_exact(ledger):
    session, period = ledger
    # The final net total fits int64, but intermediate positive/negative subtotals do not.
    for index in range(100):
        add_usage(session, f"charge-{index}", "999999999999999.99", day=2)
        add_usage(session, f"refund-{index}", "-999999999999999.99", day=3)
    add_usage(session, "remaining-cent", "0.01", day=4)
    session.flush()

    with usage_queries(session) as queries:
        result = attribution_for_period(session, period, ["alpha"])

    assert result.teams["alpha"].people["aa"] == Decimal("0.01")
    assert result.as_of == date(2026, 10, 4)
    assert len(queries) == 2


def test_unrelated_sqlite_errors_propagate_without_fallback(ledger):
    session, period = ledger
    add_usage(session, "charge", "1.00")
    session.flush()

    class UnavailableAggregate:
        def step(self, value):
            pass

        def finalize(self):
            raise RuntimeError("aggregate unavailable")

    session.connection().connection.create_aggregate("sum", 1, UnavailableAggregate)
    with usage_queries(session) as queries:
        with pytest.raises(OperationalError, match="user-defined aggregate"):
            attribution_for_period(session, period, ["alpha"])

    assert len(queries) == 1
