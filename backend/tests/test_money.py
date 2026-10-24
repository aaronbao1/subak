from decimal import Decimal

import pytest
from sqlalchemy.exc import StatementError

from app.core.money import MoneyError, MoneyType, money_str, parse_money
from app.db.models import PlanningPeriod, Team, BudgetEnvelope
from datetime import date


@pytest.mark.parametrize(
    "value,expected",
    [("60000", "60000.00"), ("60000.5", "60000.50"), (Decimal("0.01"), "0.01"), (85000, "85000.00"), ("-25000.00", "-25000.00")],
)
def test_parse_money_canonical(value, expected):
    assert money_str(parse_money(value)) == expected


@pytest.mark.parametrize(
    "value,code",
    [
        (1.5, "float_not_allowed"),
        ("1.005", "too_many_decimals"),
        ("1.500", "too_many_decimals"),
        ("NaN", "invalid_amount"),
        ("Infinity", "invalid_amount"),
        ("", "invalid_amount"),
        ("abc", "invalid_amount"),
        (True, "invalid_amount"),
        (None, "invalid_amount"),
    ],
)
def test_parse_money_rejects(value, code):
    with pytest.raises(MoneyError) as exc:
        parse_money(value)
    assert exc.value.code == code


def test_money_type_rejects_float_bind_directly():
    with pytest.raises(TypeError):
        MoneyType().process_bind_param(60000.0, None)


def _seed_period_team(session):
    session.add(PlanningPeriod(id="2026-P1", label="p", starts_on=date(2026, 10, 1), ends_on=date(2026, 12, 31)))
    session.flush()


def test_money_type_rejects_float_bind(session):
    _seed_period_team(session)
    session.add(BudgetEnvelope(period_id="2026-P1", unit="USD", total_amount=200000.0))
    with pytest.raises(StatementError) as exc:
        session.flush()
    assert isinstance(exc.value.orig, TypeError)


def test_money_round_trips_as_decimal(session):
    _seed_period_team(session)
    env = BudgetEnvelope(period_id="2026-P1", unit="USD", total_amount="200000")
    session.add(env)
    session.commit()
    session.expire_all()
    got = session.get(BudgetEnvelope, env.id)
    assert got.total_amount == Decimal("200000.00")
    assert isinstance(got.total_amount, Decimal)
    assert money_str(got.total_amount) == "200000.00"
