"""Injectable clock and id factory so tests and fixture export are deterministic."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Protocol


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Clock(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    def now(self) -> datetime:
        return utcnow()


class FrozenClock:
    def __init__(self, at: datetime) -> None:
        if at.tzinfo is None:
            raise ValueError("FrozenClock requires a timezone-aware datetime")
        self._at = at

    def now(self) -> datetime:
        return self._at

    def advance(self, **kwargs: float) -> None:
        self._at = self._at + timedelta(**kwargs)


class IdFactory(Protocol):
    def new_id(self, prefix: str = "") -> str: ...


class UuidIdFactory:
    def new_id(self, prefix: str = "") -> str:
        return f"{prefix}{uuid.uuid4()}"


class SequentialIdFactory:
    """Deterministic ids: `<prefix>000001`, `<prefix>000002`, ... (counter per prefix)."""

    def __init__(self) -> None:
        self._counters: dict[str, int] = {}

    def new_id(self, prefix: str = "") -> str:
        n = self._counters.get(prefix, 0) + 1
        self._counters[prefix] = n
        return f"{prefix}{n:06d}"
