"""Rendered-response cache for the compat reads the dashboard polls every second.

The frontend refreshes `/spending`, `/people` and `/forecasts` every 1 s, while the data under them
changes only when something is written (the live feed imports every few seconds). `/people` keeps its
final JSON bytes keyed by a *data stamp* plus the request's own parameters; `/spending`, whose full
rebuild costs ~0.7-1 s on the Uber dataset and would miss after every live import, uses the incremental
index in `spending_index.py`, which relies on `table_generation` below. `/forecasts` is not cached here:
it is read from the forecast engine's stored publication on every request. Builds are single-flight per
key (`ResponseCache.get_or_build`).

Data stamp = (process write generation, MAX(rowid) of usage_records):

- The **write generation** is a process-wide counter bumped on every INSERT/UPDATE/DELETE/DDL a
  SQLAlchemy engine executes (catches core statements, raw `text()` writes, and the demo reset) and
  again after any session that flushed changes commits. The after-commit bump closes the race where a
  concurrent read sees pre-commit state after the execute-time bump: whatever it cached is keyed by a
  generation that is already gone once the commit lands.
- **MAX(rowid)** of usage_records catches rows appended by another process (e.g. a loader run against
  the same file), which no in-process event sees. In-place updates from another process are not seen;
  the backend is the only writer while it runs (datagen/demo.sh loads before starting it).

Entries are rendered exactly as the route's response_model would render them (validated by the same
Pydantic model, `exclude_none`), so a cached body is byte-for-byte what an uncached call returns.
Nothing here writes, and nothing is cached across apps (the cache lives on `app.state`).
"""

from __future__ import annotations

import gzip
import itertools
import re
import threading
from collections import OrderedDict
from collections.abc import Callable, Hashable
from typing import Any

from fastapi import Request, Response
from pydantic import TypeAdapter
from sqlalchemy import event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

_WRITE_PREFIXES = ("INSERT", "UPDATE", "DELETE", "REPLACE", "CREATE", "DROP", "ALTER")
_counter = itertools.count(1)
_generation = 0
_gen_lock = threading.Lock()
_MAX_USAGE_ROWID = text("SELECT MAX(rowid) FROM usage_records")
GZIP_MIN = 1024  # same threshold as the app's GZipMiddleware
GZIP_LEVEL = 1   # the big bodies are rebuilt every few seconds while the live feed runs: favour speed
# Per-table write counters (see table_generation): "<table>:mut" counts UPDATE/DELETE/REPLACE, "<table>:ins"
# counts INSERT, "*ddl" counts CREATE/DROP/ALTER (which may change any table).
_TABLE_WRITE = re.compile(r"^\s*(UPDATE(?:\s+OR\s+\w+)?|DELETE\s+FROM|INSERT(?:\s+OR\s+\w+)?\s+INTO|REPLACE\s+INTO)"
                          r"\s+[\"`\[]?(\w+)", re.IGNORECASE)
_table_gens: dict[str, int] = {}
_pending = threading.local()  # table keys this thread wrote since its last session commit


def _bump(keys: tuple[str, ...] = ()) -> None:
    global _generation
    with _gen_lock:
        _generation = next(_counter)
        for k in keys:
            _table_gens[k] = _generation


def generation() -> int:
    return _generation


def table_generation(*tables: str, inserts: bool = False) -> tuple:
    """Changes whenever one of `tables` is updated or deleted from (and, with `inserts`, inserted into)
    in this process, or any DDL runs. Bumped at execute time and again after the writing session commits
    (same race reasoning as the write generation). Appends to usage_records do NOT move
    `table_generation("usage_records")`: readers that track appends by rowid use this to tell a pure
    append (incremental) from an in-place change such as a team re-attribution (rebuild)."""
    with _gen_lock:
        return (_table_gens.get("*ddl", 0),) + tuple(
            (_table_gens.get(f"{t}:mut", 0), _table_gens.get(f"{t}:ins", 0) if inserts else 0) for t in tables)


def _statement_keys(statement: str) -> tuple[str, ...]:
    head = statement.lstrip()[:7].upper()
    if head.startswith(("CREATE", "DROP", "ALTER")):
        return ("*ddl",)
    match = _TABLE_WRITE.match(statement)
    if match is None:
        return ()
    verb, table = match.group(1).upper(), match.group(2).lower()
    return (f"{table}:ins",) if verb.startswith("INSERT") else (f"{table}:mut",)


@event.listens_for(Engine, "after_cursor_execute")
def _after_execute(conn, cursor, statement, parameters, context, executemany) -> None:  # noqa: ARG001
    if statement.lstrip()[:7].upper().startswith(_WRITE_PREFIXES):
        keys = _statement_keys(statement)
        _bump(keys)
        if keys:
            pending = getattr(_pending, "keys", None)
            if pending is None:
                pending = _pending.keys = set()
            pending.update(keys)


@event.listens_for(Session, "after_flush")
def _after_flush(session, flush_context) -> None:  # noqa: ARG001
    session.info["compat_cache_wrote"] = True


@event.listens_for(Session, "after_commit")
def _after_commit(session) -> None:
    keys = tuple(getattr(_pending, "keys", None) or ())
    _pending.keys = set()
    if session.info.pop("compat_cache_wrote", False) or keys:
        _bump(keys)


@event.listens_for(Session, "after_rollback")
def _after_rollback(session) -> None:
    session.info.pop("compat_cache_wrote", None)
    _pending.keys = set()


def data_stamp(session: Session) -> tuple:
    """Changes whenever anything the compat reads depend on may have changed (see module doc)."""
    gen = generation()  # read before the query: a write landing in between only causes a miss later
    return gen, session.execute(_MAX_USAGE_ROWID).scalar()


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

    __slots__ = ("raw", "_gz", "_gz_lock")

    def __init__(self, raw: bytes) -> None:
        self.raw, self._gz = raw, None
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
