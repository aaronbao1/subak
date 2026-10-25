"""Bounded daily observations. Null telemetry is distinct from an observed zero."""

from datetime import date, datetime
from typing import Literal

from app.schemas.common import MoneyStr, OutModel, ValueKind

ScopeType = Literal["company", "team", "person", "shared"]
DailyCoverage = Literal["complete", "partial", "missing", "unknown", "future"]


class UsageScope(OutModel):
    type: ScopeType
    id: str | None = None


class UsageTokens(OutModel):
    input_tokens: int | None
    output_tokens: int | None
    cached_input_tokens: int | None
    reasoning_tokens: int | None
    total_tokens: int | None


class TokenObservedRecordCounts(OutModel):
    input_tokens: int
    output_tokens: int
    cached_input_tokens: int
    reasoning_tokens: int
    total_tokens: int


class UsageAggregate(OutModel):
    recorded_spend: MoneyStr | None
    costs_by_value_kind: dict[ValueKind, MoneyStr | None]
    included_usage_notional: MoneyStr | None
    tokens: UsageTokens
    token_observed_record_counts: TokenObservedRecordCounts
    record_count: int


class UsageBreakdown(UsageAggregate):
    provider: str | None
    model: str | None


class DailyUsageBucket(UsageAggregate):
    date: date
    coverage: DailyCoverage
    revision: str
    breakdowns: list[UsageBreakdown]
    # Native import-batch IDs, usable in the existing /api/spend/records batch filter.
    source_refs: list[str]


class UsageSourceCoverage(OutModel):
    source_kind: str
    source_account: str | None
    record_count: int
    coverage: DailyCoverage
    last_record_at: datetime


class UsageFilters(OutModel):
    provider: str | None
    model: str | None


class DailyUsageResponse(OutModel):
    scope: UsageScope
    start_date: date
    end_date_exclusive: date
    timezone: Literal["UTC"] = "UTC"
    unit: Literal["USD"] = "USD"
    dataset_id: Literal["repository-ledger"] = "repository-ledger"
    # Content revision of the requested slice; it changes when its native records change.
    dataset_revision: str
    synthetic: bool
    as_of: datetime
    filters: UsageFilters
    available_start_date: date | None
    available_end_date_exclusive: date | None
    buckets: list[DailyUsageBucket]
    source_coverage: list[UsageSourceCoverage]
    notes: list[str]
