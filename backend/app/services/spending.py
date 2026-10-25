"""Spend summaries and record drill-down (design.md §4, §5).

- `recorded_spend` sums only records with `counts_toward_spend` (subscription fees, billable overage,
  direct API). Included usage contributes its list value to `included_usage_notional` only, and
  unpriced usage contributes tokens, never dollars.
- Unattributed records (no team mapping) are their own bucket; they count toward the company total
  but not toward any team. Coverage is embedded so missing data stays visibly incomplete.
- Nothing here depends on the forecast provider.
"""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.errors import DomainError
from app.db.models import COST_CATEGORIES, NON_SPEND_CATEGORIES, VALUE_KINDS, ImportBatch, Person, PlanningPeriod, Team, UsageRecord
from app.services import coverage as coverage_svc

ZERO = Decimal("0.00")
UNATTRIBUTED = "unattributed"
TOKEN_FIELDS = ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_tokens")
MAX_RECORD_PAGE = 5000

NOTES = [
    "recorded_spend counts subscription fees, billable overage and direct API charges only",
    "included usage is covered by its subscription fee: shown as notional value, never added to spend",
    "unpriced usage is token volume without a known cost; it is not converted to dollars",
]


# In the Codex/OpenAI usage shape `cached_input_tokens` is a subset of `input_tokens` and
# `reasoning_tokens` (reasoning_output_tokens) is a subset of `output_tokens`. Only the two totals are
# added; the subsets stay visible per field in `tokens` but are never summed on top.
TOTAL_TOKEN_FIELDS = ("input_tokens", "output_tokens")


def _tokens(r: UsageRecord) -> int:
    return sum(getattr(r, f) or 0 for f in TOTAL_TOKEN_FIELDS)


def _aggregate(team: str, recs: list[UsageRecord]) -> dict:
    by_cat: dict[str, dict] = {}
    for cat in COST_CATEGORIES:
        rows = [r for r in recs if r.cost_category == cat]
        counts = cat not in NON_SPEND_CATEGORIES
        notional = sum((r.notional_value for r in rows if r.notional_value is not None), ZERO)
        by_cat[cat] = {
            "amount": sum((r.amount for r in rows if r.amount is not None), ZERO) if counts else None,
            "counts_toward_spend": counts,
            "record_count": len(rows),
            "notional_value": notional if cat == "included_usage" else None,
        }
    by_kind = {k: ZERO for k in VALUE_KINDS}
    spend = ZERO
    for r in recs:
        if r.counts_toward_spend and r.amount is not None:
            spend += r.amount
            by_kind[r.value_kind] += r.amount
    return {
        "team": team,
        "recorded_spend": spend,
        "by_cost_category": by_cat,
        "by_value_kind": by_kind,
        "included_usage_notional": by_cat["included_usage"]["notional_value"],
        "tokens": {f: sum(getattr(r, f) or 0 for r in recs) for f in TOKEN_FIELDS},
        "unpriced_tokens": sum(_tokens(r) for r in recs if r.cost_category == "unpriced_usage"),
        "record_count": len(recs),
        "last_record_at": max((r.occurred_at for r in recs), default=None),
    }


def spend_summary(session: Session, period: PlanningPeriod, *, clock: Clock) -> dict:
    now = clock.now()
    cov = coverage_svc.coverage_report(session, period, now)
    records = session.scalars(select(UsageRecord).where(UsageRecord.period_id == period.id)).all()
    by_team: dict[str | None, list[UsageRecord]] = defaultdict(list)
    for r in records:
        by_team[r.team_id].append(r)

    teams = []
    for tc in cov["teams"]:
        teams.append({**_aggregate(tc["team"], by_team.get(tc["team"], [])), "coverage": tc})
    unattributed = {
        **_aggregate(UNATTRIBUTED, by_team.get(None, [])),
        "source_accounts": cov["unattributed"]["source_accounts"],
    }
    # Records attributed to a team that is no longer active still count toward the company total.
    active = {t["team"] for t in teams}
    inactive_spend = sum(
        (r.amount for tid, recs in by_team.items() if tid is not None and tid not in active
         for r in recs if r.counts_toward_spend and r.amount is not None),
        ZERO,
    )
    attributed = sum((t["recorded_spend"] for t in teams), ZERO)
    notes = list(NOTES)
    if inactive_spend:
        notes.append("company_total includes spend attributed to inactive teams")
    return {
        "period": cov["period"],
        "unit": "USD",
        "as_of": now,
        "teams": teams,
        "unattributed": unattributed,
        "attributed_total": attributed,
        "company_total": attributed + unattributed["recorded_spend"] + inactive_spend,
        "coverage": cov["company"],
        "data_labels": cov["data_labels"],
        "notes": notes,
    }


def record_out(r: UsageRecord) -> dict:
    return {
        "id": r.id, "import_batch_id": r.import_batch_id, "source_kind": r.source_kind,
        "source_record_key": r.source_record_key, "source_account": r.source_account,
        "team": r.team_id or UNATTRIBUTED, "person": r.person_id, "period": r.period_id, "occurred_at": r.occurred_at,
        "provider": r.provider, "model": r.model, "stream_key": r.stream_key,
        **{f: getattr(r, f) for f in TOKEN_FIELDS},
        "counter_reset": r.counter_reset, "amount": r.amount, "unit": r.unit, "value_kind": r.value_kind,
        "cost_category": r.cost_category, "counts_toward_spend": r.counts_toward_spend,
        "notional_value": r.notional_value,
    }


def list_records(
    session: Session,
    period: PlanningPeriod,
    *,
    team: str | None = None,
    value_kind: str | None = None,
    cost_category: str | None = None,
    batch: str | None = None,
    person: str | None = None,
    offset: int = 0,
    limit: int = 500,
) -> dict:
    reasons = []
    if team is not None and team != UNATTRIBUTED and session.get(Team, team) is None:
        reasons.append({"code": "unknown_team", "message": f"unknown team {team!r} (use 'unattributed' for unmapped)"})
    if value_kind is not None and value_kind not in VALUE_KINDS:
        reasons.append({"code": "unknown_value_kind", "message": f"value_kind must be one of {VALUE_KINDS}"})
    if cost_category is not None and cost_category not in COST_CATEGORIES:
        reasons.append({"code": "unknown_cost_category", "message": f"cost_category must be one of {COST_CATEGORIES}"})
    if batch is not None and session.get(ImportBatch, batch) is None:
        reasons.append({"code": "unknown_batch", "message": f"import batch {batch!r} not found"})
    if person is not None and session.get(Person, person) is None:
        reasons.append({"code": "unknown_person", "message": f"unknown person {person!r}"})
    if reasons:
        raise DomainError("validation_failed", 422, "invalid record filter", {"reasons": reasons})

    q = select(UsageRecord).where(UsageRecord.period_id == period.id)
    if team == UNATTRIBUTED:
        q = q.where(UsageRecord.team_id.is_(None))
    elif team:
        q = q.where(UsageRecord.team_id == team)
    if value_kind:
        q = q.where(UsageRecord.value_kind == value_kind)
    if cost_category:
        q = q.where(UsageRecord.cost_category == cost_category)
    if batch:
        q = q.where(UsageRecord.import_batch_id == batch)
    if person:
        q = q.where(UsageRecord.person_id == person)
    total = session.scalar(select(func.count()).select_from(q.subquery())) or 0
    rows = session.scalars(
        q.order_by(UsageRecord.occurred_at, UsageRecord.source_record_key).offset(offset).limit(limit)
    ).all()
    return {
        "period": period.id,
        "filters": {"team": team, "value_kind": value_kind, "cost_category": cost_category, "batch": batch,
                    "person": person},
        "total": total, "offset": offset, "limit": limit,
        "items": [record_out(r) for r in rows],
    }
