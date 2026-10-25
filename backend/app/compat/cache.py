"""Per-app rendered read caches with transactional SQLite invalidation.

Revision triggers commit with the source write, including writes from a different process. Readers
never write: startup installs triggers, while polling only reads the small revision table. Pure usage
appends retain the incremental index; updates/deletes and source-label edits force a complete rebuild.

People responses keep their final JSON bytes keyed by the committed data stamp and request parameters;
spending uses the incremental index in spending_index.py. Forecasts are read from the engine's stored
publication on every request. ResponseCache builds are single-flight per key. Bodies use the same
Pydantic validation and exclude_none serialization as uncached routes, and live only on app.state.
"""
from __future__ import annotations

import gzip
import threading
from collections import OrderedDict
from collections.abc import Callable, Hashable
from typing import Any

from fastapi import Request, Response
from pydantic import TypeAdapter
from sqlalchemy import event, text
from sqlalchemy.orm import Session
from app.db.base import Base

GZIP_MIN = 1024  # same threshold as the app's GZipMiddleware
GZIP_LEVEL = 1  # favor speed for large bodies rebuilt while the live feed runs
_REVISION_TABLE = "_compat_cache_revisions"


@event.listens_for(Base.metadata, "after_create")
def _install_revision_tracking(target, connection, **kwargs) -> None:
    # Metadata.create_all is also used inside the existing atomic reset transaction.
    connection.exec_driver_sql(f"CREATE TABLE IF NOT EXISTS {_REVISION_TABLE} (name TEXT PRIMARY KEY, version INTEGER NOT NULL)")
    keys = ["schema", *[f"{table}:{kind}" for table in ("usage_records", "import_batches", "people", "teams")
                       for kind in ("ins", "mut")]]
    for key in keys:
        connection.exec_driver_sql(f"INSERT OR IGNORE INTO {_REVISION_TABLE}(name,version) VALUES (?,0)", (key,))
    connection.exec_driver_sql(f"UPDATE {_REVISION_TABLE} SET version=version+1 WHERE name='schema'")
    for table in ("usage_records", "import_batches", "people", "teams"):
        for action, kind in (("INSERT", "ins"), ("UPDATE", "mut"), ("DELETE", "mut")):
            columns = " OF source_label,filename,source_kind" if table == "import_batches" and action == "UPDATE" else ""
            trigger = f"_compat_{table}_{action.lower()}"
            connection.exec_driver_sql(f"""CREATE TRIGGER IF NOT EXISTS {trigger} AFTER {action}{columns} ON {table}
                BEGIN UPDATE {_REVISION_TABLE} SET version=version+1 WHERE name='{table}:{kind}'; END""")


    # SQLite REPLACE deletes a conflicting row without DELETE triggers when an external
    # connection has recursive_triggers disabled. Detect conflicts before that deletion.
    conflicts = {
        "usage_records": "id=NEW.id OR (source_kind=NEW.source_kind AND source_record_key=NEW.source_record_key) OR (NEW.rowid<>-1 AND rowid=NEW.rowid)",
        "import_batches": "id=NEW.id OR (status='imported' AND NEW.status='imported' AND source_kind=NEW.source_kind AND content_hash=NEW.content_hash)",
    }
    for table, conflict in conflicts.items():
        connection.exec_driver_sql(f"""CREATE TRIGGER IF NOT EXISTS _compat_{table}_replacement
            BEFORE INSERT ON {table} WHEN EXISTS (SELECT 1 FROM {table} WHERE {conflict})
            BEGIN UPDATE {_REVISION_TABLE} SET version=version+1 WHERE name='{table}:mut'; END""")


def _revisions(session: Session) -> dict[str, int]:
    return dict(session.execute(text(f"SELECT name,version FROM {_REVISION_TABLE}")).all())


def table_generation(session: Session, *tables: str, inserts: bool = False) -> tuple:
    """Committed mutation revisions for these tables, including external SQLite writes.

    Pure appends leave the mutation stamp unchanged so rowid-tracking readers can update incrementally.
    Set inserts=True when all changes matter. Startup/reset also advance the schema revision.
    """
    versions = _revisions(session)
    return (versions["schema"],) + tuple((versions.get(f"{t}:mut", 0),
            versions.get(f"{t}:ins", 0) if inserts else 0) for t in tables)


def data_stamp(session: Session) -> tuple:
    """Current directory revisions; callers add their other dependencies and request parameters."""
    return table_generation(session, "people", "teams", inserts=True)


class ResponseCache:
    """Small thread-safe LRU of rendered JSON bodies, with a per-key build lock (`building`) so that
    concurrent misses on one key run the build once and the others wait for its result."""

    def __init__(self, size: int = 32) -> None:
        self.size = size
        self._items: OrderedDict[Hashable, Any] = OrderedDict()
        self._lock = threading.Lock()
        self._building: dict[Hashable, threading.Lock] = {}
        self.hits = 0
        self.misses = 0
        self.builds = 0

    def building(self, key: Hashable) -> threading.Lock:
        """The lock to hold while building `key` (one per key; dropped again once the key is stored)."""
        with self._lock:
            lock = self._building.get(key)
            if lock is None:
                lock = self._building[key] = threading.Lock()
            return lock

    def _peek(self, key: Hashable) -> Any | None:
        with self._lock:
            return self._items.get(key)

    def get_or_build(self, key: Hashable, build: Callable[[], Any]) -> Any:
        """The stored value for `key`, or `build()` stored. Single-flight: one build per key at a time;
        concurrent callers wait for it and reuse its value instead of repeating the work."""
        value = self.get(key)
        if value is not None:
            return value
        with self.building(key):
            value = self._peek(key)  # another thread may have built it while we waited
            if value is None:
                self.builds += 1
                value = build()
                self.put(key, value)
            with self._lock:
                self._building.pop(key, None)
        return value

    def get(self, key: Hashable) -> Any | None:
        with self._lock:
            value = self._items.get(key)
            if value is None:
                self.misses += 1
                return None
            self._items.move_to_end(key)
            self.hits += 1
            return value

    def put(self, key: Hashable, value: Any) -> None:
        with self._lock:
            self._items[key] = value
            self._items.move_to_end(key)
            while len(self._items) > self.size:
                self._items.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._items.clear()


_adapters: dict[Any, TypeAdapter] = {}


def render(model: Any, rows: Any) -> bytes:
    """JSON exactly as FastAPI renders `response_model=model` with `response_model_exclude_none=True`."""
    adapter = _adapters.get(model)
    if adapter is None:
        adapter = _adapters[model] = TypeAdapter(model)
    return adapter.dump_json(adapter.validate_python(rows), exclude_none=True)


def cache_for(state: Any) -> ResponseCache:
    cache = getattr(state, "compat_cache", None)
    if cache is None:
        cache = state.compat_cache = ResponseCache()
    return cache


class Body:
    """A rendered JSON body plus its gzip form, compressed once on first gzip request (the GZip
    middleware passes a response that already carries Content-Encoding through untouched)."""

    __slots__ = ("raw", "_gz", "keep", "_gz_lock")

    def __init__(self, raw: bytes, keep: Any = None) -> None:
        self.raw, self._gz, self.keep = raw, None, keep  # keep: objects whose ids are in the cache key
        self._gz_lock = threading.Lock()  # concurrent first gzip requests compress once

    def response(self, request: Request) -> Response:
        if len(self.raw) >= GZIP_MIN and "gzip" in request.headers.get("accept-encoding", "").lower():
            if self._gz is None:
                with self._gz_lock:
                    if self._gz is None:
                        self._gz = gzip.compress(self.raw, compresslevel=GZIP_LEVEL)
            return Response(content=self._gz, media_type="application/json",
                            headers={"Content-Encoding": "gzip", "Vary": "Accept-Encoding"})
        return Response(content=self.raw, media_type="application/json")


def cached_json(request: Request, key: Hashable, model: Any, build: Callable[[], Any]) -> Response:
    """The cached body for `key`, or `build()` rendered through `model` and stored."""
    body = cache_for(request.app.state).get_or_build(key, lambda: Body(render(model, build())))
    return body.response(request)
