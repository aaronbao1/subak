"""Current internal budget state and its version history (design.md §3.6, §4)."""

from __future__ import annotations

from datetime import date, datetime

from app.schemas.common import CoverageStatus, MoneyStr, OutModel


class PeriodRef(OutModel):
    id: str
    label: str
    starts_on: date
    ends_on: date


class AllocationOut(OutModel):
    team: str
    amount: MoneyStr
    recorded_spend: MoneyStr
    # amount - recorded_spend; negative means the team has already spent past its allocation.
    remaining: MoneyStr
    # Completeness of this team's recorded_spend (see /api/coverage). Anything but `complete` means
    # recorded_spend may be understated and remaining overstated.
    coverage_status: CoverageStatus


class BudgetSpendCoverage(OutModel):
    """How complete the recorded_spend / remaining figures are. They are attributed spend to date."""

    status: CoverageStatus
    unattributed_spend: MoneyStr  # counts toward the company total but toward no team's remaining
    unattributed_records: int
    notes: list[str]


class BudgetState(OutModel):
    period: PeriodRef
    unit: str
    envelope_total: MoneyStr
    allocated_total: MoneyStr
    state_version: int
    allocations: list[AllocationOut]
    updated_at: datetime
    last_decision_id: str | None
    spend_coverage: BudgetSpendCoverage
    # Internal planning records only: nothing here moves provider credits or enforces limits.
    note: str = "internal planning allocations; no provider credits are transferred or enforced"


class SnapshotDecisionRef(OutModel):
    id: str
    proposal_id: str
    action_type: str
    actor_id: str
    actor_role: str
    rationale: str
    decided_at: datetime


class BudgetSnapshotOut(OutModel):
    state_version: int
    total_amount: MoneyStr
    allocations: dict[str, MoneyStr]
    created_at: datetime
    decision: SnapshotDecisionRef | None  # None for the initial (seeded) state


class BudgetHistory(OutModel):
    period: PeriodRef
    unit: str
    current_version: int
    snapshots: list[BudgetSnapshotOut]
