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
        ("1e30", "amount_too_large"),
        ("99999999999999999999999999.99", "amount_too_large"),
        ("-1000000000000000", "amount_too_large"),
        (10**40, "amount_too_large"),
        (Decimal("1E+27"), "amount_too_large"),
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


def test_parse_money_accepts_largest_bound():
    assert money_str(parse_money("999999999999999.99")) == "999999999999999.99"


@pytest.mark.parametrize("amount", ["1e30", "99999999999999999999999999.99"])
def test_huge_amounts_are_422_not_500(seeded, client, amount):
    headers = {"X-Actor-Id": "fin-ana", "X-Actor-Role": "finance_analyst"}
    transfer = {"action_type": "transfer", "base_version": 1, "rationale": "x",
                "lines": [{"from_team": "product", "to_team": "research", "amount": amount}]}
    addition = {"action_type": "addition", "base_version": 1, "rationale": "x", "envelope_increase": amount,
                "lines": [{"to_team": "research", "amount": amount}]}
    for body in (transfer, addition):
        r = client.post("/api/proposals", json=body, headers=headers)
        assert r.status_code == 422, r.text
        assert "amount_too_large" in r.text
    r = client.post("/api/agent/runs", headers=headers, json={
        "task_type": "propose_allocation", "params": {"mode": "transfer", "amount": amount, "prioritize": "research"}})
    assert r.status_code == 422, r.text
