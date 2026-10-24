"""Normalized parser output shared by every source kind."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timezone
from decimal import Decimal
from typing import Any

TOKEN_FIELDS = ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_tokens")


@dataclass
class ParseIssue:
    code: str
    message: str
    row: int | None = None  # 1-based line/record number in the source

    def as_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "row": self.row}


@dataclass
class ParsedRecord:
    """One observation. Either `tokens` are per-record deltas, or `cumulative` holds a running
    counter for `stream_key` and the import pipeline derives deltas (design.md §3.5)."""

    row: int
    occurred_at: datetime
    cost_category: str
    value_kind: str | None  # None -> batch default
    source_record_key: str | None = None  # None for cumulative records: derived from the counter
    source_account: str | None = None
    provider: str | None = None
    model: str | None = None
    amount: Decimal | None = None
    unit: str = "USD"
    notional_value: Decimal | None = None
    tokens: dict[str, int | None] = field(default_factory=dict)
    stream_key: str | None = None
    cumulative: dict[str, int] | None = None

    def fingerprint(self) -> tuple:
        """Content identity used to detect a record key restated with different values."""
        return (
            self.occurred_at.isoformat(),
            self.cost_category,
            self.source_account,
            None if self.amount is None else str(self.amount),
            None if self.notional_value is None else str(self.notional_value),
            tuple(self.tokens.get(f) for f in TOKEN_FIELDS),
        )


@dataclass
class ParseResult:
    records: list[ParsedRecord] = field(default_factory=list)
    errors: list[ParseIssue] = field(default_factory=list)
    warnings: list[ParseIssue] = field(default_factory=list)
    stats: dict[str, int] = field(default_factory=dict)

    def bump(self, key: str, n: int = 1) -> None:
        self.stats[key] = self.stats.get(key, 0) + n


class FieldError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def parse_timestamp(value: Any) -> datetime:
    """ISO-8601 date (-> 00:00 UTC) or timezone-aware datetime. Naive datetimes are rejected:
    the source's timezone is never guessed."""
    if not isinstance(value, str) or not value.strip():
        raise FieldError("occurred_at_required", "occurred_at is required")
    text = value.strip()
    if len(text) == 10:
        try:
            return datetime.combine(date.fromisoformat(text), time(0, 0), tzinfo=timezone.utc)
        except ValueError as exc:
            raise FieldError("invalid_timestamp", f"not an ISO date: {text!r}") from exc
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise FieldError("invalid_timestamp", f"not an ISO-8601 timestamp: {text!r}") from exc
    if parsed.tzinfo is None:
        raise FieldError("timezone_required", f"timestamp has no timezone: {text!r}")
    return parsed.astimezone(timezone.utc)


def parse_token_count(value: Any, name: str) -> int | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if isinstance(value, bool) or isinstance(value, float):
        raise FieldError("invalid_token_count", f"{name} must be a non-negative integer")
    if isinstance(value, str):
        text = value.strip()
        if not text.isdigit():
            raise FieldError("invalid_token_count", f"{name} must be a non-negative integer, got {text!r}")
        return int(text)
    if isinstance(value, int):
        if value < 0:
            raise FieldError("invalid_token_count", f"{name} must be non-negative")
        return value
    raise FieldError("invalid_token_count", f"{name} must be a non-negative integer")
