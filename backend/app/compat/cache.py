"""Rendered-response cache for the compat reads the dashboard polls every second.

The frontend refreshes `/spending`, `/people` and `/forecasts` every 1 s, while the data under them
changes only when something is written (the live feed imports every few seconds). Rebuilding the
~3 MB spending list costs ~0.8 s on the ~331k-row Uber dataset, so each of these routes keeps its
final JSON bytes keyed by a *data stamp* plus the request's own parameters.

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


def _bump() -> None:
    global _generation
    with _gen_lock:
        _generation = next(_counter)


def generation() -> int:
    return _generation


@event.listens_for(Engine, "after_cursor_execute")
def _after_execute(conn, cursor, statement, parameters, context, executemany) -> None:  # noqa: ARG001
    if statement.lstrip()[:7].upper().startswith(_WRITE_PREFIXES):
        _bump()


@event.listens_for(Session, "after_flush")
def _after_flush(session, flush_context) -> None:  # noqa: ARG001
    session.info["compat_cache_wrote"] = True


@event.listens_for(Session, "after_commit")
def _after_commit(session) -> None:
    if session.info.pop("compat_cache_wrote", False):
        _bump()


@event.listens_for(Session, "after_rollback")
def _after_rollback(session) -> None:
    session.info.pop("compat_cache_wrote", None)


def data_stamp(session: Session) -> tuple:
    """Changes whenever anything the compat reads depend on may have changed (see module doc)."""
    gen = generation()  # read before the query: a write landing in between only causes a miss later
    return gen, session.execute(_MAX_USAGE_ROWID).scalar()


class ResponseCache:
    """Small thread-safe LRU of rendered JSON bodies."""

    def __init__(self, size: int = 32) -> None:
        self.size = size
        self._items: OrderedDict[Hashable, Any] = OrderedDict()
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0

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

    __slots__ = ("raw", "_gz", "keep")

    def __init__(self, raw: bytes, keep: Any = None) -> None:
        self.raw, self._gz, self.keep = raw, None, keep  # keep: objects whose ids are in the cache key

    def response(self, request: Request) -> Response:
        if len(self.raw) >= GZIP_MIN and "gzip" in request.headers.get("accept-encoding", "").lower():
            if self._gz is None:
                self._gz = gzip.compress(self.raw, compresslevel=6)
            return Response(content=self._gz, media_type="application/json",
                            headers={"Content-Encoding": "gzip", "Vary": "Accept-Encoding"})
        return Response(content=self.raw, media_type="application/json")


def cached_json(request: Request, key: Hashable, model: Any, build: Callable[[], Any]) -> Response:
    """The cached body for `key`, or `build()` rendered through `model` and stored."""
    cache = cache_for(request.app.state)
    body = cache.get(key)
    if body is None:
        body = Body(render(model, build()))
        cache.put(key, body)
    return body.response(request)
