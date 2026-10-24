"""Budget envelope, allocations and immutable version snapshots (design.md §3.6).

Invariants (checked after every write, see `assert_invariant`):
- sum(allocations) == envelope total, exactly, in Decimal.
- no allocation is negative.
- state_version starts at 1 and only ever increases by one per applied decision.
"""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Mapping

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import Clock, IdFactory
from app.core.errors import DomainError
from app.core.money import money_str, parse_money
from app.db.models import (
    BudgetAllocation,
    BudgetEnvelope,
    BudgetSnapshot,
    Decision,
    PlanningPeriod,
    Proposal,
    Team,
    UsageRecord,
)
from app.services.coverage import resolve_period

ZERO = Decimal("0.00")
SUPPORTED_UNITS = ("USD",)


def figures(total: Decimal, allocations: Mapping[str, Decimal]) -> dict:
    """Canonical JSON form used for proposal/decision before/after and snapshots."""
    return {"total": money_str(total), "allocations": {t: money_str(a) for t, a in sorted(allocations.items())}}


def figures_to_decimal(data: Mapping) -> tuple[Decimal, dict[str, Decimal]]:
    return Decimal(data["total"]), {t: Decimal(a) for t, a in data["allocations"].items()}


def get_envelope(session: Session, period_id: str) -> BudgetEnvelope | None:
    return session.scalar(select(BudgetEnvelope).where(BudgetEnvelope.period_id == period_id))


def require_envelope(session: Session, period_id: str) -> BudgetEnvelope:
    env = get_envelope(session, period_id)
    if env is None:
        raise DomainError("no_budget", 404, f"no budget envelope exists for period {period_id!r}")
    return env


def resolve_envelope(session: Session, period_id: str | None, clock: Clock) -> tuple[PlanningPeriod, BudgetEnvelope]:
    period = resolve_period(session, period_id, clock.now())
    return period, require_envelope(session, period.id)


def allocation_map(env: BudgetEnvelope) -> dict[str, Decimal]:
    return {a.team_id: a.amount for a in env.allocations}


def current_figures(env: BudgetEnvelope) -> dict:
    return figures(env.total_amount, allocation_map(env))


def assert_invariant(env: BudgetEnvelope) -> None:
    allocs = allocation_map(env)
    total = sum(allocs.values(), ZERO)
    negative = {t: money_str(a) for t, a in allocs.items() if a < ZERO}
    if total != env.total_amount or negative:
        raise DomainError(
            "budget_invariant_violated",
            500,
            "allocations must be non-negative and sum exactly to the envelope total",
            {"envelope_total": money_str(env.total_amount), "allocated_total": money_str(total),
             "negative_allocations": negative},
        )


def create_envelope(
    session: Session,
    *,
    period_id: str,
    unit: str,
    allocations: Mapping[str, object],
    clock: Clock,
    ids: IdFactory,
) -> BudgetEnvelope:
    """Create the version-1 budget for a period (used by seeding). Total = sum of allocations."""
    if session.get(PlanningPeriod, period_id) is None:
        raise DomainError("unknown_period", 404, f"unknown period {period_id!r}")
    if unit not in SUPPORTED_UNITS:
        raise DomainError("currency_mismatch", 422, f"only {SUPPORTED_UNITS} budgets are supported in v1")
    if get_envelope(session, period_id) is not None:
        raise DomainError("budget_exists", 409, f"a budget envelope already exists for {period_id!r}")
    parsed: dict[str, Decimal] = {}
    for team_id, raw in allocations.items():
        if session.get(Team, team_id) is None:
            raise DomainError("unknown_team", 422, f"unknown team {team_id!r}")
        amount = parse_money(raw)
        if amount < ZERO:
            raise DomainError("negative_allocation_result", 422, f"allocation for {team_id!r} is negative")
        parsed[team_id] = amount
    now = clock.now()
    total = sum(parsed.values(), ZERO)
    env = BudgetEnvelope(
        id=ids.new_id("env_"), period_id=period_id, unit=unit, total_amount=total,
        state_version=1, created_at=now, updated_at=now,
    )
    session.add(env)
    session.flush()
    for team_id, amount in sorted(parsed.items()):
        session.add(BudgetAllocation(id=ids.new_id("alloc_"), envelope_id=env.id, team_id=team_id,
                                     amount=amount, created_at=now))
    session.flush()
    session.refresh(env)
    assert_invariant(env)
    session.add(BudgetSnapshot(
        id=ids.new_id("snap_"), envelope_id=env.id, state_version=1, total_amount=total,
        allocations=current_figures(env)["allocations"], decision_id=None, created_at=now,
    ))
    session.flush()
    return env


def recorded_spend_by_team(session: Session, period_id: str) -> dict[str, Decimal]:
    """Spend that counts (never included or unpriced usage), per mapped team."""
    rows = session.execute(
        select(UsageRecord.team_id, UsageRecord.amount).where(
            UsageRecord.period_id == period_id,
            UsageRecord.counts_toward_spend.is_(True),
            UsageRecord.team_id.is_not(None),
            UsageRecord.amount.is_not(None),
        )
    ).all()
    totals: dict[str, Decimal] = defaultdict(lambda: ZERO)
    for team_id, amount in rows:
        totals[team_id] += amount
    return dict(totals)


def last_decision_id(session: Session, env: BudgetEnvelope) -> str | None:
    return session.scalar(
        select(BudgetSnapshot.decision_id).where(
            BudgetSnapshot.envelope_id == env.id, BudgetSnapshot.state_version == env.state_version
        )
    )


def budget_state(session: Session, period: PlanningPeriod, env: BudgetEnvelope) -> dict:
    spend = recorded_spend_by_team(session, period.id)
    allocs = allocation_map(env)
    return {
        "period": period,
        "unit": env.unit,
        "envelope_total": env.total_amount,
        "allocated_total": sum(allocs.values(), ZERO),
        "state_version": env.state_version,
        "allocations": [
            {"team": t, "amount": a, "recorded_spend": spend.get(t, ZERO), "remaining": a - spend.get(t, ZERO)}
            for t, a in sorted(allocs.items())
        ],
        "updated_at": env.updated_at,
        "last_decision_id": last_decision_id(session, env),
    }


def history(session: Session, period: PlanningPeriod, env: BudgetEnvelope) -> dict:
    snaps = session.scalars(
        select(BudgetSnapshot).where(BudgetSnapshot.envelope_id == env.id).order_by(BudgetSnapshot.state_version)
    ).all()
    out = []
    for s in snaps:
        decision = None
        if s.decision_id:
            d = session.get(Decision, s.decision_id)
            p = session.get(Proposal, d.proposal_id)
            decision = {
                "id": d.id, "proposal_id": d.proposal_id, "action_type": p.action_type,
                "actor_id": d.actor_id, "actor_role": d.actor_role, "rationale": d.rationale,
                "decided_at": d.decided_at,
            }
        out.append({
            "state_version": s.state_version, "total_amount": s.total_amount,
            "allocations": {t: Decimal(a) for t, a in s.allocations.items()},
            "created_at": s.created_at, "decision": decision,
        })
    return {"period": period, "unit": env.unit, "current_version": env.state_version, "snapshots": out}
