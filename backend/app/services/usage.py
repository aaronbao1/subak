"""Daily aggregation over native records, across planning-period boundaries.

The import ledger has unique (source_kind, source_record_key) identities. Observations
alone never establish a complete day; the selected source adapter may supply verified
completion receipts covering the same native revision and exact scoped dollars.
Historical team/person attribution is the attribution stored on each record; current
membership or active flags must not move or erase old costs.
"""

from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
import hashlib
import json

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.errors import DomainError
from app.db.models import VALUE_KINDS, Person, Team, UsageRecord
from app.schemas.usage import ScopeType
from app.services.spending import TOKEN_FIELDS
from app.services.source_completion import source_completion

MAX_WINDOW_DAYS = 366
ZERO = Decimal("0.00")
NOTES = [
    "Amounts are sums of recorded USD charge components, not an assertion that every charge was received.",
    "The repository ledger has no daily source-completion receipts: observed days are partial; missing days are unknown usage, not zero.",
    "Input plus output forms total tokens. Cached input and reasoning are subsets, never additional tokens.",
    "Token fields sum supplied observations only; record counts identify partial telemetry. Total tokens is null when a row supplies only input or only output.",
    "Included usage is informational notional value, excluded from recorded spend. Unpriced usage contributes no dollars.",
    "Shared without an ID is company usage without a team. Shared with a team ID is that team's usage without a person.",
    "Historical scopes use stored record attribution, including inactive people and teams. Dataset revision identifies this requested slice.",
]


def _validation(message: str) -> None:
    raise DomainError("validation_failed", 422, message, {})


def _scope_conditions(session: Session, scope_type: ScopeType, scope_id: str | None) -> list:
    if scope_type == "company":
        if scope_id is not None:
            _validation("company scope does not accept scope_id")
        return []
    if scope_type == "person":
        directory = session.info.get("people_directory")
        known_demo_person = scope_id and directory is not None and any(p.id == scope_id for p in directory())
        if not scope_id or (session.get(Person, scope_id) is None and not known_demo_person):
            _validation("person scope requires a known repository person")
        return [UsageRecord.person_id == scope_id]
    if scope_type == "shared" and scope_id is None:
        return [UsageRecord.team_id.is_(None)]
    if scope_type not in ("team", "shared"):
        _validation("unknown usage scope")
    if not scope_id or session.get(Team, scope_id) is None:
        _validation("team scope requires a known repository team")
    conditions = [UsageRecord.team_id == scope_id]
    if scope_type == "shared":
        conditions.append(UsageRecord.person_id.is_(None))
    return conditions


def _revision(records: list[UsageRecord]) -> str:
    # Hash values as well as IDs: a native correction must invalidate a stale calendar.
    fields = ("id", "import_batch_id", "source_kind", "source_record_key", "source_account", "team_id",
              "person_id", "period_id", "occurred_at", "created_at", "provider", "model", "stream_key",
              "amount", "unit", "value_kind", "cost_category", "counts_toward_spend", "notional_value",
              "counter_reset", *TOKEN_FIELDS)
    digest = hashlib.sha256()
    for row in sorted(records, key=lambda r: r.id):
        digest.update(json.dumps([getattr(row, field) for field in fields], default=str,
                                 separators=(",", ":")).encode())
        digest.update(b"\n")
    return digest.hexdigest()


def _aggregate(records: list[UsageRecord]) -> dict:
    by_kind: dict[str, list[UsageRecord]] = defaultdict(list)
    for row in records:
        if row.value_kind not in VALUE_KINDS:
            _validation(f"unknown native value kind: {row.value_kind}")
        if row.unit != "USD":
            _validation("daily usage cannot aggregate non-USD records")
        by_kind[row.value_kind].append(row)
    def charges(rows):
        return sum((row.amount for row in rows if row.counts_toward_spend and row.amount is not None), ZERO)
    values = {field: [getattr(row, field) for row in records if getattr(row, field) is not None]
              for field in TOKEN_FIELDS}
    tokens = {field: sum(items) if items else None for field, items in values.items()}
    with_totals = [r for r in records if r.input_tokens is not None or r.output_tokens is not None]
    paired = [r for r in with_totals if r.input_tokens is not None and r.output_tokens is not None]
    tokens["total_tokens"] = (sum(r.input_tokens + r.output_tokens for r in paired)
                              if paired and len(paired) == len(with_totals) else None)
    included = [r for r in records if r.cost_category == "included_usage"]
    return {
        "recorded_spend": charges(records) if records else None,
        "costs_by_value_kind": {kind: charges(by_kind[kind]) if by_kind[kind] else None for kind in VALUE_KINDS},
        "included_usage_notional": (sum((r.notional_value for r in included), ZERO)
                                    if included and all(r.notional_value is not None for r in included) else None),
        "tokens": tokens,
        "token_observed_record_counts": {**{f: len(items) for f, items in values.items()}, "total_tokens": len(paired)},
        "record_count": len(records),
    }


def daily_usage(session: Session, *, scope_type: ScopeType, scope_id: str | None, start_date: date,
                end_date_exclusive: date, provider: str | None, model: str | None, clock: Clock) -> dict:
    days = (end_date_exclusive - start_date).days
    if not 1 <= days <= MAX_WINDOW_DAYS:
        _validation("daily usage window must contain 1 to 366 days with an exclusive end date")
    now = clock.now().astimezone(timezone.utc)
    conditions = _scope_conditions(session, scope_type, scope_id)
    completion = source_completion(session, now) if provider is None and model is None else None
    notes = list(NOTES)
    if completion is not None:
        notes[1] = "Complete spending days have matching source receipts. Other observed days are partial; missing days remain unknown, not zero. Token fields still reflect only supplied telemetry."
    if scope_type == "person" and session.get(Person, scope_id) is None:
        notes.append("This forecast-demo person has no repository ledger identity: unavailable attribution, not zero spend.")
    conditions.extend([UsageRecord.occurred_at <= now, UsageRecord.created_at <= now])
    if provider is not None:
        conditions.append(UsageRecord.provider == provider)
    if model is not None:
        conditions.append(UsageRecord.model == model)
    first, last = session.execute(select(func.min(UsageRecord.occurred_at), func.max(UsageRecord.occurred_at))
                                 .where(*conditions)).one()
    records = list(session.scalars(select(UsageRecord).where(*conditions,
        UsageRecord.occurred_at >= datetime.combine(start_date, time.min, timezone.utc),
        UsageRecord.occurred_at < datetime.combine(end_date_exclusive, time.min, timezone.utc))
        .order_by(UsageRecord.occurred_at, UsageRecord.id)))
    if completion is not None and not completion.is_current(session):
        completion = None
        notes[1] = NOTES[1]
    by_day: dict[date, list[UsageRecord]] = defaultdict(list)
    sources: dict[tuple[str, str | None], list[UsageRecord]] = defaultdict(list)
    for record in records:
        by_day[record.occurred_at.date()].append(record)
        sources[(record.source_kind, record.source_account)].append(record)
    buckets = []
    for offset in range(days):
        day = start_date + timedelta(days=offset)
        rows = by_day[day]
        dimensions: dict[tuple[str | None, str | None], list[UsageRecord]] = defaultdict(list)
        for row in rows:
            dimensions[(row.provider, row.model)].append(row)
        breakdowns = [{"provider": key[0], "model": key[1], **_aggregate(group)}
                      for key, group in sorted(dimensions.items(), key=lambda item: (item[0][0] or "", item[0][1] or ""))]
        aggregate = _aggregate(rows)
        attested = completion.amount(scope_type, scope_id, day) if completion is not None else None
        complete = (attested is not None and completion.accepts_records(rows)
                    and attested == (aggregate['recorded_spend'] if rows else ZERO))
        if complete and not rows:
            aggregate['recorded_spend'] = ZERO
        revision = _revision(rows)
        if complete:
            revision = hashlib.sha256((revision + completion.revision).encode()).hexdigest()
        buckets.append({"date": day, **aggregate, "coverage": "future" if day > now.date() else
                        "complete" if complete else "partial" if rows else "missing", "revision": revision, "breakdowns": breakdowns,
                        "source_refs": sorted({r.import_batch_id for r in rows} or
                                              (completion.batch_ids if complete else set()))})
    return {
        "scope": {"type": scope_type, "id": scope_id}, "start_date": start_date,
        "end_date_exclusive": end_date_exclusive, "timezone": "UTC", "unit": "USD",
        "dataset_id": "repository-ledger", "dataset_revision": hashlib.sha256(json.dumps(
            [(row['date'].isoformat(), row['revision'], row['coverage']) for row in buckets]).encode()).hexdigest(),
        "synthetic": any(r.value_kind == "simulated" for r in records) or any(
            row['coverage'] == 'complete' and row['record_count'] == 0 for row in buckets), "as_of": now,
        "filters": {"provider": provider, "model": model},
        "available_start_date": first.date() if first else None,
        "available_end_date_exclusive": last.date() + timedelta(days=1) if last else None,
        "buckets": buckets,
        "source_coverage": [{"source_kind": key[0], "source_account": key[1], "record_count": len(rows),
                             "coverage": "partial", "last_record_at": max(r.occurred_at for r in rows)}
                            for key, rows in sorted(sources.items(), key=lambda item: (item[0][0], item[0][1] or ""))],
        "notes": notes,
    }
