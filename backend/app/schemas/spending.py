"""Spending history and current snapshot (design.md §4). Included usage is never added to spend."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from app.schemas.common import CostCategory, DataLabels, MoneyStr, OutModel, ValueKind
from app.schemas.imports import CompanyCoverage, PeriodOut, TeamCoverage, UnattributedSource


class CategoryBreakdown(OutModel):
    # None for included_usage / unpriced_usage: those categories carry no charge.
    amount: MoneyStr | None
    counts_toward_spend: bool
    record_count: int
    # List value of included usage (display only, never summed into spend).
    notional_value: MoneyStr | None


class TokenTotals(OutModel):
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int
    reasoning_tokens: int


class TeamSpend(OutModel):
    team: str
    recorded_spend: MoneyStr
    by_cost_category: dict[str, CategoryBreakdown]
    by_value_kind: dict[str, MoneyStr]
    included_usage_notional: MoneyStr
    tokens: TokenTotals
    # Tokens on records with no known monetary value (unpriced usage). Not a dollar amount.
    unpriced_tokens: int
    record_count: int
    last_record_at: datetime | None


class TeamSpendWithCoverage(TeamSpend):
    coverage: TeamCoverage


class UnattributedSpend(TeamSpend):
    team: Literal["unattributed"] = "unattributed"
    source_accounts: list[UnattributedSource]


class SpendSummary(OutModel):
    period: PeriodOut
    unit: Literal["USD"]
    as_of: datetime
    teams: list[TeamSpendWithCoverage]
    unattributed: UnattributedSpend
    attributed_total: MoneyStr
    # Includes unattributed spend: the company spent it even if no team mapping exists yet.
    company_total: MoneyStr
    coverage: CompanyCoverage
    data_labels: DataLabels
    notes: list[str]


class SpendRecordOut(OutModel):
    id: str
    import_batch_id: str
    source_kind: str
    source_record_key: str
    source_account: str | None
    team: str  # team id or "unattributed"
    # Person id when the record's user_email matched an active person on that team; None = team-level.
    person: str | None = None
    period: str
    occurred_at: datetime
    provider: str | None
    model: str | None
    stream_key: str | None
    input_tokens: int | None
    cached_input_tokens: int | None
    output_tokens: int | None
    reasoning_tokens: int | None
    counter_reset: bool
    amount: MoneyStr | None
    unit: str
    value_kind: ValueKind
    cost_category: CostCategory
    counts_toward_spend: bool
    notional_value: MoneyStr | None


class SpendRecordList(OutModel):
    period: str
    filters: dict[str, str | None]
    total: int
    offset: int
    limit: int
    items: list[SpendRecordOut]
