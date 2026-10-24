"""Spend import pipeline (design.md §3.4-3.5).

Guarantees:
- Identical bytes for a source kind import once; a re-post records a `duplicate` batch, inserts nothing.
- Overlapping files with different hashes cannot double count: (source_kind, source_record_key) is
  unique; a key restated with different values is skipped and reported, never overwritten.
- Cumulative counters become deltas per stream (`to_deltas`); repeated snapshots are stored once with
  their first delta, a decrease is a counter reset (flagged, coverage becomes partial).
- Team comes only from explicit mappings; unmapped accounts are stored with team_id NULL.
- A batch with any invalid row fails as a whole (nothing inserted) and is kept for audit.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Callable

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.clock import Clock, IdFactory
from app.core.errors import DomainError
from app.db.models import VALUE_KINDS, ImportBatch, PlanningPeriod, UsageRecord
from app.services.parsers import codex_sessions, northstar_csv
from app.services.parsers.base import TOKEN_FIELDS, ParsedRecord, ParseIssue, ParseResult
from app.services.teams import MappingResolver

MAX_IMPORT_BYTES = 10 * 1024 * 1024
MAX_ISSUE_ROWS = 20


@dataclass(frozen=True)
class SourceKind:
    name: str
    parse: Callable[[str, str | None], ParseResult]
    default_value_kind: str
    takes_source_account: bool  # telemetry files do not name an account; the uploader states it


SOURCE_KINDS: dict[str, SourceKind] = {
    northstar_csv.SOURCE_KIND: SourceKind(northstar_csv.SOURCE_KIND, northstar_csv.parse, "simulated", False),
    codex_sessions.SOURCE_KIND: SourceKind(codex_sessions.SOURCE_KIND, codex_sessions.parse, "measured", True),
}


# ---- cumulative counters ---------------------------------------------------------------------


def counter_hash(counter: dict[str, int]) -> str:
    canonical = json.dumps({k: counter.get(k, 0) for k in TOKEN_FIELDS}, sort_keys=True)
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


def cumulative_record_key(stream_key: str, counter: dict[str, int]) -> str:
    return f"{stream_key}#{counter_hash(counter)}"


@dataclass
class StreamState:
    last_at: datetime | None = None
    last_counter: dict[str, int] | None = None
    known_keys: set[str] = field(default_factory=set)


@dataclass
class DeltaStats:
    repeated_snapshots: int = 0
    counter_resets: int = 0
    out_of_order: int = 0
    out_of_order_rows: list[int] = field(default_factory=list)
    reset_rows: list[int] = field(default_factory=list)


def to_deltas(
    records: list[ParsedRecord], prior: dict[str, StreamState] | None = None
) -> tuple[list[tuple[ParsedRecord, bool]], DeltaStats]:
    """Turn cumulative observations into delta records. Returns [(record, counter_reset)].

    Per stream, observations are ordered by time (ties by counter size). The delta is current minus
    previous cumulative value (previous = last stored snapshot for the stream, if any). A snapshot whose
    counter was already seen (in this file or the DB) is skipped: it is the same usage reported again.
    If any counter decreases the stream was reset: delta = current value, flagged. A snapshot older
    than the last stored one cannot be placed without rewriting stored deltas, so it is skipped and
    reported as out of order.
    """
    prior = prior or {}
    stats = DeltaStats()
    by_stream: dict[str, list[ParsedRecord]] = defaultdict(list)
    for rec in records:
        assert rec.stream_key and rec.cumulative is not None
        by_stream[rec.stream_key].append(rec)

    out: list[tuple[ParsedRecord, bool]] = []
    for stream, recs in by_stream.items():
        state = prior.get(stream) or StreamState()
        seen = set(state.known_keys)
        prev = dict(state.last_counter) if state.last_counter else {k: 0 for k in TOKEN_FIELDS}
        recs.sort(key=lambda r: (r.occurred_at, sum(r.cumulative.values())))  # type: ignore[union-attr]
        for rec in recs:
            counter = rec.cumulative  # type: ignore[assignment]
            key = cumulative_record_key(stream, counter)
            if key in seen:
                stats.repeated_snapshots += 1
                continue
            if state.last_at is not None and rec.occurred_at < state.last_at:
                stats.out_of_order += 1
                stats.out_of_order_rows.append(rec.row)
                continue
            seen.add(key)
            reset = any(counter.get(k, 0) < prev.get(k, 0) for k in TOKEN_FIELDS)
            if reset:
                stats.counter_resets += 1
                stats.reset_rows.append(rec.row)
                deltas = {k: counter.get(k, 0) for k in TOKEN_FIELDS}
            else:
                deltas = {k: counter.get(k, 0) - prev.get(k, 0) for k in TOKEN_FIELDS}
            rec.source_record_key = key
            rec.tokens = deltas
            prev = dict(counter)
            out.append((rec, reset))
    return out, stats


def _prior_stream_states(session: Session, source_kind: str, streams: set[str]) -> dict[str, StreamState]:
    states: dict[str, StreamState] = {}
    for stream in streams:
        rows = session.scalars(
            select(UsageRecord)
            .where(UsageRecord.source_kind == source_kind, UsageRecord.stream_key == stream)
            .order_by(UsageRecord.occurred_at)
        ).all()
        if not rows:
            continue
        last = rows[-1]
        states[stream] = StreamState(
            last_at=last.occurred_at,
            last_counter=dict(last.cumulative_snapshot or {}),
            known_keys={r.source_record_key for r in rows},
        )
    return states


# ---- issues ----------------------------------------------------------------------------------


def _group_issues(issues: list[ParseIssue]) -> list[dict[str, Any]]:
    """Aggregate per code so a 100k-row file cannot produce a 100k-entry payload."""
    grouped: dict[str, dict[str, Any]] = {}
    for issue in issues:
        g = grouped.setdefault(issue.code, {"code": issue.code, "message": issue.message, "count": 0, "rows": []})
        g["count"] += 1
        if issue.row is not None and len(g["rows"]) < MAX_ISSUE_ROWS:
            g["rows"].append(issue.row)
    return list(grouped.values())


# ---- pipeline --------------------------------------------------------------------------------


@dataclass
class ImportOutcome:
    batch: ImportBatch
    created: bool  # False when the result is a duplicate of an earlier batch


def _period_lookup(session: Session) -> Callable[[datetime], str | None]:
    periods = session.scalars(select(PlanningPeriod)).all()

    def lookup(at: datetime) -> str | None:
        day = at.date()
        for p in periods:
            if p.starts_on <= day <= p.ends_on:
                return p.id
        return None

    return lookup


def _new_batch(
    *, ids: IdFactory, clock: Clock, kind: str, label: str | None, filename: str | None,
    content_hash: str, status: str, actor_id: str, value_kind_default: str,
) -> ImportBatch:
    return ImportBatch(
        id=ids.new_id("imp_"),
        created_at=clock.now(),
        source_kind=kind,
        source_label=label,
        filename=filename,
        content_hash=content_hash,
        status=status,
        imported_by=actor_id,
        value_kind_default=value_kind_default,
        record_count=0,
        skipped_duplicate_records=0,
        unmapped_record_count=0,
    )


def find_imported_batch(session: Session, source_kind: str, content_hash: str) -> ImportBatch | None:
    return session.scalars(
        select(ImportBatch).where(
            ImportBatch.source_kind == source_kind,
            ImportBatch.content_hash == content_hash,
            ImportBatch.status == "imported",
        )
    ).one_or_none()


def _decode(raw: bytes) -> str:
    text = raw.decode("utf-8-sig")
    return text.replace("\r\n", "\n").replace("\r", "\n")


def run_import(
    session: Session,
    *,
    source_kind: str,
    raw: bytes,
    filename: str | None,
    actor_id: str,
    clock: Clock,
    ids: IdFactory,
    source_label: str | None = None,
    source_account: str | None = None,
    value_kind_default: str | None = None,
) -> ImportOutcome:
    kind = SOURCE_KINDS.get(source_kind)
    if kind is None:
        raise DomainError(
            "unknown_source_kind", 422, f"unknown source_kind {source_kind!r}",
            {"allowed": sorted(SOURCE_KINDS)},
        )
    if len(raw) > MAX_IMPORT_BYTES:
        raise DomainError("file_too_large", 413, f"import files are limited to {MAX_IMPORT_BYTES} bytes")
    vk_default = value_kind_default or kind.default_value_kind
    if vk_default not in VALUE_KINDS:
        raise DomainError("unknown_value_kind", 422, f"value_kind_default must be one of {VALUE_KINDS}")
    account = (source_account or "").strip() or None
    if account and not kind.takes_source_account:
        raise DomainError(
            "source_account_not_allowed", 422,
            f"{source_kind} files name their own accounts; source_account cannot be overridden",
        )

    content_hash = hashlib.sha256(raw).hexdigest()
    batch_args = dict(
        ids=ids, clock=clock, kind=source_kind, label=source_label, filename=filename,
        content_hash=content_hash, actor_id=actor_id, value_kind_default=vk_default,
    )

    original = find_imported_batch(session, source_kind, content_hash)
    if original is not None:
        dup = _new_batch(status="duplicate", **batch_args)
        dup.duplicate_of_batch_id = original.id
        dup.error_details = {
            "errors": [],
            "warnings": [{
                "code": "duplicate_file",
                "message": f"identical content was already imported as batch {original.id}; nothing added",
                "count": 1, "rows": [],
            }],
            "stats": {},
        }
        session.add(dup)
        session.flush()
        return ImportOutcome(dup, created=False)

    def fail(issues: list[ParseIssue], stats: dict[str, int] | None = None) -> ImportOutcome:
        batch = _new_batch(status="failed", **batch_args)
        batch.error_details = {"errors": _group_issues(issues), "warnings": [], "stats": stats or {}}
        session.add(batch)
        session.flush()
        return ImportOutcome(batch, created=True)

    if not raw.strip():
        return fail([ParseIssue("empty_file", "file is empty")])
    try:
        text = _decode(raw)
    except UnicodeDecodeError:
        return fail([ParseIssue("invalid_encoding", "file must be UTF-8 text")])

    parsed = kind.parse(text, filename)
    if parsed.errors:
        return fail(parsed.errors, parsed.stats)

    warnings: list[ParseIssue] = list(parsed.warnings)
    stats: dict[str, int] = dict(parsed.stats)

    # 1. cumulative -> deltas, against what is already stored for each stream
    cumulative = [r for r in parsed.records if r.cumulative is not None]
    plain = [r for r in parsed.records if r.cumulative is None]
    resets: set[int] = set()
    if cumulative:
        prior = _prior_stream_states(session, source_kind, {r.stream_key for r in cumulative})  # type: ignore[misc]
        delta_records, dstats = to_deltas(cumulative, prior)
        stats["repeated_snapshots_skipped"] = dstats.repeated_snapshots
        stats["counter_resets"] = dstats.counter_resets
        stats["out_of_order_skipped"] = dstats.out_of_order
        for row in dstats.reset_rows:
            warnings.append(ParseIssue(
                "counter_reset", "cumulative counter decreased; treated as a reset (coverage partial)", row
            ))
        for row in dstats.out_of_order_rows:
            warnings.append(ParseIssue(
                "out_of_order_snapshot",
                "snapshot is older than the last stored snapshot for its stream; skipped", row,
            ))
        resets = {id(r) for r, was_reset in delta_records if was_reset}
        candidates = [r for r, _ in delta_records] + plain
    else:
        candidates = plain

    # 2. period, team, record-key dedupe
    period_of = _period_lookup(session)
    resolver = MappingResolver(session, source_kind)
    keys = [r.source_record_key for r in candidates]
    existing: dict[str, UsageRecord] = {}
    for chunk_start in range(0, len(keys), 500):
        chunk = keys[chunk_start:chunk_start + 500]
        for rec in session.scalars(
            select(UsageRecord).where(UsageRecord.source_kind == source_kind, UsageRecord.source_record_key.in_(chunk))
        ):
            existing[rec.source_record_key] = rec

    batch = _new_batch(status="imported", **batch_args)
    session.add(batch)
    session.flush()

    inserted = skipped_dup = conflicts = unmapped = out_of_period = 0
    unmapped_accounts: dict[str, int] = defaultdict(int)
    spend_added = Decimal("0.00")
    for rec in sorted(candidates, key=lambda r: r.row):
        acct = account if kind.takes_source_account else rec.source_account
        prev = existing.get(rec.source_record_key)  # type: ignore[arg-type]
        if prev is not None:
            if rec.cumulative is None and _stored_fingerprint(prev) != rec.fingerprint():
                conflicts += 1
                warnings.append(ParseIssue(
                    "record_key_conflict",
                    "record already imported with different values; existing record kept, new one skipped",
                    rec.row,
                ))
            else:
                skipped_dup += 1
            continue
        period_id = period_of(rec.occurred_at)
        if period_id is None:
            out_of_period += 1
            warnings.append(ParseIssue("outside_known_periods", "record date is outside every planning period; skipped", rec.row))
            continue
        team_id = resolver.resolve(acct, rec.occurred_at)
        if team_id is None:
            unmapped += 1
            unmapped_accounts[acct or "<none>"] += 1
        category = rec.cost_category
        counts = UsageRecord.derive_counts_toward_spend(category)
        if counts and rec.amount is not None:
            spend_added += rec.amount
        session.add(UsageRecord(
            id=ids.new_id("rec_"),
            created_at=clock.now(),
            import_batch_id=batch.id,
            source_kind=source_kind,
            source_record_key=rec.source_record_key,
            source_account=acct,
            team_id=team_id,
            period_id=period_id,
            occurred_at=rec.occurred_at,
            provider=rec.provider,
            model=rec.model,
            stream_key=rec.stream_key,
            cumulative_snapshot=rec.cumulative,
            counter_reset=id(rec) in resets,
            amount=rec.amount,
            unit=rec.unit,
            value_kind=rec.value_kind or vk_default,
            cost_category=category,
            counts_toward_spend=counts,
            notional_value=rec.notional_value,
            **{f: rec.tokens.get(f) for f in TOKEN_FIELDS},
        ))
        inserted += 1

    for acct, n in sorted(unmapped_accounts.items()):
        warnings.append(ParseIssue(
            "unmapped_source_account",
            f"source account {acct!r} has no team mapping; {n} record(s) reported as unattributed",
        ))
    stats.update({
        "conflicting_records": conflicts,
        "out_of_period_skipped": out_of_period,
    })
    batch.record_count = inserted
    batch.skipped_duplicate_records = skipped_dup
    batch.unmapped_record_count = unmapped
    batch.error_details = {
        "errors": [],
        "warnings": _group_issues(warnings),
        "stats": stats,
        "unmapped_accounts": dict(sorted(unmapped_accounts.items())),
        "spend_added": format(spend_added, "f"),
    }
    session.flush()
    return ImportOutcome(batch, created=True)


def _stored_fingerprint(rec: UsageRecord) -> tuple:
    return (
        rec.occurred_at.isoformat(),
        rec.cost_category,
        rec.source_account,
        None if rec.amount is None else str(rec.amount),
        None if rec.notional_value is None else str(rec.notional_value),
        tuple(getattr(rec, f) for f in TOKEN_FIELDS),
    )


def import_and_commit(session: Session, **kwargs: Any) -> ImportOutcome:
    """Run in its own transaction. A concurrent identical import that wins the unique index race is
    turned into a `duplicate` result instead of a 500."""
    try:
        outcome = run_import(session, **kwargs)
        session.commit()
        return outcome
    except IntegrityError:
        session.rollback()
        outcome = run_import(session, **kwargs)
        session.commit()
        return outcome


def list_batches(session: Session) -> list[ImportBatch]:
    return list(session.scalars(select(ImportBatch).order_by(ImportBatch.created_at, ImportBatch.id)))


def get_batch(session: Session, batch_id: str) -> ImportBatch:
    batch = session.get(ImportBatch, batch_id)
    if batch is None:
        raise DomainError("not_found", 404, f"import batch {batch_id!r} not found")
    return batch


def batch_record_count(session: Session, batch_id: str) -> int:
    return session.scalar(select(func.count()).where(UsageRecord.import_batch_id == batch_id)) or 0
