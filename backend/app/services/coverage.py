"""Coverage / completeness per team and period. Missing data stays visibly incomplete.

Rules:
- A team with no records in the period is `missing` (never reported as a complete zero).
- A team with records is `partial` if any of its counter streams reset, or if unattributed records
  exist in the period (they could belong to any team, so no team total can be called complete).
- Company status is `missing` with no records, `partial` if any team is not complete, else `complete`.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import DomainError
from app.db.models import ImportBatch, PlanningPeriod, Team, UsageRecord


def resolve_period(session: Session, period_id: str | None, now: datetime) -> PlanningPeriod:
    if period_id:
        period = session.get(PlanningPeriod, period_id)
        if period is None:
            raise DomainError("unknown_period", 404, f"unknown period {period_id!r}")
        return period
    periods = session.scalars(select(PlanningPeriod).order_by(PlanningPeriod.starts_on)).all()
    if not periods:
        raise DomainError("no_periods", 404, "no planning periods are configured")
    for p in periods:
        if p.starts_on <= now.date() <= p.ends_on:
            return p
    return periods[-1]


def coverage_report(session: Session, period: PlanningPeriod, now: datetime) -> dict:
    teams = session.scalars(select(Team).where(Team.active.is_(True)).order_by(Team.id)).all()
    records = session.scalars(select(UsageRecord).where(UsageRecord.period_id == period.id)).all()

    by_team: dict[str | None, list[UsageRecord]] = defaultdict(list)
    for r in records:
        by_team[r.team_id].append(r)
    unattributed = by_team.get(None, [])
    company_resets = sum(1 for r in records if r.counter_reset)

    def summarize(recs: list[UsageRecord]) -> dict:
        return {
            "record_count": len(recs),
            "counter_resets": sum(1 for r in recs if r.counter_reset),
            "last_record_at": max((r.occurred_at for r in recs), default=None),
            "source_kinds": sorted({r.source_kind for r in recs}),
            "value_kinds": sorted({r.value_kind for r in recs}),
        }

    team_rows = []
    for t in teams:
        recs = by_team.get(t.id, [])
        s = summarize(recs)
        notes: list[str] = []
        if not recs:
            status = "missing"
            notes.append("no usage or billing records for this team in the period")
        else:
            status = "complete"
            if s["counter_resets"]:
                status = "partial"
                notes.append(f"{s['counter_resets']} cumulative counter reset(s); usage may be understated")
            if unattributed:
                status = "partial"
                notes.append(
                    f"{len(unattributed)} unattributed record(s) in the period may belong to this team"
                )
        team_rows.append({
            "team": t.id,
            "status": status,
            "unmapped_records": 0,
            "notes": notes,
            **s,
        })

    company_notes: list[str] = []
    accounts: dict[str, int] = defaultdict(int)
    unattributed_spend = Decimal("0.00")
    for r in unattributed:
        accounts[f"{r.source_kind}:{r.source_account or '<none>'}"] += 1
        if r.counts_toward_spend and r.amount is not None:
            unattributed_spend += r.amount
    if unattributed:
        company_notes.append(
            f"{len(unattributed)} record(s) from unmapped source accounts are unattributed; add team mappings"
        )
    if company_resets:
        company_notes.append(f"{company_resets} cumulative counter reset(s) detected")
    missing = [row["team"] for row in team_rows if row["status"] == "missing"]
    if missing and records:
        company_notes.append(f"no records for: {', '.join(missing)}")
    if now.date() < period.ends_on:
        company_notes.append(f"period in progress (ends {period.ends_on.isoformat()}); totals are to date")

    if not records:
        company_status = "missing"
        company_notes.insert(0, "no usage or billing records for the period")
    elif unattributed or any(row["status"] != "complete" for row in team_rows):
        company_status = "partial"
    else:
        company_status = "complete"

    batch_ids = sorted({r.import_batch_id for r in records})
    batches = (
        session.scalars(select(ImportBatch).where(ImportBatch.id.in_(batch_ids)).order_by(ImportBatch.created_at)).all()
        if batch_ids else []
    )
    value_kinds = {r.value_kind for r in records}
    return {
        "period": {"id": period.id, "label": period.label, "starts_on": period.starts_on, "ends_on": period.ends_on},
        "company": {
            "status": company_status,
            "unmapped_records": len(unattributed),
            "notes": company_notes,
            **summarize(records),
        },
        "teams": team_rows,
        "unattributed": {
            "record_count": len(unattributed),
            "recorded_spend": unattributed_spend,
            "unit": "USD",
            "source_accounts": [{"source": k, "record_count": v} for k, v in sorted(accounts.items())],
        },
        "sources": [
            {"batch_id": b.id, "source_kind": b.source_kind, "source_label": b.source_label,
             "filename": b.filename, "imported_at": b.created_at}
            for b in batches
        ],
        "data_labels": {"simulated": "simulated" in value_kinds, "real_sample": "measured" in value_kinds},
    }
