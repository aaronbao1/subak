"""Incremental `/compat/api/spending` for the live demo.

Rebuilding the whole list (re-reading and re-grouping every usage record of the period) costs ~0.7-1 s
on the Uber dataset, and the live feed (datagen/live.py) appends records every few seconds, so a plain
"rebuild on any change" cache missed on almost every dashboard refresh. This index keeps the period's
records grouped exactly as `mappers.spending` groups them (one output row per team x person x day x
component x provider) plus each row's rendered JSON, and on each request:

- **nothing changed** (same period, same `table_generation("usage_records")`, same MAX(rowid)): serves
  the stored body (one cheap MAX(rowid) query);
- **pure append** (MAX(rowid) grew, no UPDATE/DELETE on usage_records, no DDL): reads only the new rows
  (rowid > the last one seen), re-maps and re-renders only the rows they touch, re-joins the bytes;
- **anything else** (an in-place change such as a team re-attribution, a reset, a smaller MAX(rowid)
  from another process, another period): full rebuild, as before.

Each output row is produced by `mappers.spending` over that row's own records (in the same
(occurred_at, source_record_key) order the full query uses), so the joined body is byte-for-byte what
the full build renders (tests compare them). One lock serializes syncs: concurrent requests after an
import wait for one update instead of each repeating it. Read-only; lives on `app.state`.
"""

from __future__ import annotations

import threading
from collections.abc import Hashable
from typing import Any

from sqlalchemy import func, literal_column, select, text
from sqlalchemy.orm import Session

from app.compat import cache, mappers
from app.compat import schemas as S
from app.db.models import ImportBatch, UsageRecord
from app.services import spending as spending_svc

ROWID = literal_column("usage_records.rowid")
# Only the columns mappers.spending reads, as plain rows (building ORM objects cost ~0.5 s per rebuild).
SPEND_COLUMNS = (
    func.coalesce(UsageRecord.team_id, spending_svc.UNATTRIBUTED).label("team"),
    UsageRecord.person_id.label("person"), UsageRecord.occurred_at, UsageRecord.cost_category,
    UsageRecord.provider, UsageRecord.amount, UsageRecord.counts_toward_spend, UsageRecord.value_kind,
    UsageRecord.import_batch_id, UsageRecord.source_kind, UsageRecord.notional_value, UsageRecord.counter_reset,
    UsageRecord.unit, UsageRecord.source_record_key,
)
_MAX_ROWID = text("SELECT MAX(rowid) FROM usage_records")
# Only in-place usage changes force a rebuild. Import batches are updated after their records are
# inserted (status, counts), but the label fields a row shows (source_label, filename, source_kind) are
# set when the batch is created and never changed, and are read when its first records appear.
_TABLES = ("usage_records",)


def _order(r: dict) -> tuple:
    return (r["occurred_at"], r["source_record_key"] or "")


def spend_rows(session: Session, period_id: str, *, after: int | None = None, upto: int | None = None) -> list[dict]:
    """The period's usage records as plain dicts, in spending.list_records order (mappers.spending takes
    each row's unit from its first record). `after`/`upto` bound the rowid (incremental reads)."""
    q = select(*SPEND_COLUMNS).where(UsageRecord.period_id == period_id)
    if after is not None:
        q = q.where(ROWID > after)
    if upto is not None:
        q = q.where(ROWID <= upto)
    rows = session.execute(q.order_by(UsageRecord.occurred_at, UsageRecord.source_record_key))
    return [dict(r) for r in rows.mappings()]


class SpendingIndex:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._stamp: tuple | None = None          # (period_id, table generation, upto)
        self._groups: dict[tuple, list[dict]] = {}
        self._rendered: dict[tuple, bytes] = {}
        self._keys: list[tuple] | None = None     # sorted row keys (None: re-sort on next render)
        self._labels: dict[str, str] = {}
        self._bodies: dict[Hashable, cache.Body] = {}
        self.full_builds = 0
        self.incremental_updates = 0

    def response(self, request: Any, session: Session, period_id: str, team_id: str | None,
                 date_from: str | None, date_to: str | None):
        return self.body(session, period_id, team_id, date_from, date_to).response(request)

    def body(self, session: Session, period_id: str, team_id: str | None = None,
             date_from: str | None = None, date_to: str | None = None) -> cache.Body:
        with self._lock:
            self._sync(session, period_id)
            key = (team_id or None, date_from, date_to)
            body = self._bodies.get(key)
            if body is None:
                if len(self._bodies) > 16:
                    self._bodies.clear()
                body = self._bodies[key] = cache.Body(self._join(*key))
            return body

    # -- sync --

    def _sync(self, session: Session, period_id: str) -> None:
        gen = cache.table_generation(*_TABLES)  # read before the data: a write in between only causes a later rebuild
        upto = int(session.execute(_MAX_ROWID).scalar() or 0)
        stamp = self._stamp
        if stamp is not None and stamp == (period_id, gen, upto):
            return
        if stamp is None or stamp[0] != period_id or stamp[1] != gen or upto < stamp[2]:
            self._rebuild(session, period_id, upto)
        else:
            self._append(session, period_id, stamp[2], upto)
        self._stamp = (period_id, gen, upto)
        self._bodies.clear()

    def _rebuild(self, session: Session, period_id: str, upto: int) -> None:
        self.full_builds += 1
        records = spend_rows(session, period_id, upto=upto)
        self._groups, self._rendered, self._labels = {}, {}, {}
        self._add_labels(session, {r["import_batch_id"] for r in records})
        for r in records:
            key = mappers.spending_group(r)
            if key is not None:
                self._groups.setdefault(key, []).append(r)
        for key in self._groups:
            self._render(key)
        self._keys = None

    def _append(self, session: Session, period_id: str, after: int, upto: int) -> None:
        self.incremental_updates += 1
        records = spend_rows(session, period_id, after=after, upto=upto)
        self._add_labels(session, {r["import_batch_id"] for r in records} - self._labels.keys())
        touched = set()
        for r in records:
            key = mappers.spending_group(r)
            if key is None:
                continue
            if key not in self._groups:
                self._groups[key] = []
                self._keys = None
            self._groups[key].append(r)
            touched.add(key)
        for key in touched:
            self._groups[key].sort(key=_order)
            self._render(key)

    def _add_labels(self, session: Session, batch_ids: set) -> None:
        batch_ids = {b for b in batch_ids if b is not None}
        if batch_ids:
            for b in session.scalars(select(ImportBatch).where(ImportBatch.id.in_(batch_ids))):
                self._labels[b.id] = b.source_label or b.filename or b.source_kind

    def _render(self, key: tuple) -> None:
        rows = mappers.spending(self._groups[key], batch_labels=self._labels)
        self._rendered[key] = cache.render(S.SpendingRecord, rows[0])

    # -- output --

    def _join(self, team_id: str | None, date_from: str | None, date_to: str | None) -> bytes:
        if self._keys is None:
            self._keys = sorted(self._rendered)
        parts = [self._rendered[k] for k in self._keys
                 if (not team_id or k[0] == team_id) and (not date_from or k[2] >= date_from)
                 and (not date_to or k[2] <= date_to)]
        return b"[" + b",".join(parts) + b"]"


def index_for(state: Any) -> SpendingIndex:
    index = getattr(state, "compat_spending_index", None)
    if index is None:
        with _create_lock:
            index = getattr(state, "compat_spending_index", None)
            if index is None:
                index = state.compat_spending_index = SpendingIndex()
    return index


_create_lock = threading.Lock()
