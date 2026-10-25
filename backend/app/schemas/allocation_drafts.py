"""Full-team allocation targets for drafting a native, independently reviewed proposal."""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import Field, StrictInt

from app.schemas.budget import BudgetSpendCoverage
from app.schemas.common import CoverageStatus, InModel, MoneyStr, OutModel
from app.schemas.proposals import RawAmount


class AllocationDraftCreate(InModel):
    base_version: StrictInt
    period_start: date
    period_end_exclusive: date
    unit: Literal["USD"]
    # Keep invalid money values intact for the native named validation reasons.
    allocations: dict[str, RawAmount] = Field(max_length=100)
    rationale: Annotated[str, Field(max_length=10_000)]
    request_ids: list[Annotated[str, Field(min_length=1, max_length=200)]] = Field(
        default_factory=list, max_length=100,
    )


class AllocationPeriod(OutModel):
    id: str
    start_date: date
    end_date_exclusive: date
    label: str


class AllocationStateRow(OutModel):
    team_id: str
    amount: MoneyStr
    recorded_spend: MoneyStr
    remaining: MoneyStr
    coverage_status: CoverageStatus


class AllocationState(OutModel):
    period: AllocationPeriod
    unit: str
    state_version: int
    envelope_total: MoneyStr
    allocated_total: MoneyStr
    unallocated_amount: MoneyStr
    allocations: list[AllocationStateRow]
    updated_at: datetime
    last_decision_id: str | None
    spend_coverage: BudgetSpendCoverage
    note: str = "internal planning allocations; no provider credits are transferred or enforced"
