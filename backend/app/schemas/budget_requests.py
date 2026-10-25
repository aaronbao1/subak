"""Explicit team funding requests and read-only assessments, separate from approved budgets."""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import Field, field_validator

from app.schemas.common import InModel, MoneyStr, OutModel
from app.schemas.proposals import EvidenceRef, ProposalOut


class BudgetRequestCreate(InModel):
    client_request_id: str = Field(min_length=1, max_length=200)
    team_id: str
    title: str = Field(min_length=1, max_length=300)
    request_kind: Literal["team", "project", "initiative"] = "team"
    project_name: str | None = Field(default=None, max_length=300)
    narrative: str = Field(min_length=1, max_length=20000)
    requested_amount: MoneyStr | None = None
    unit: Literal["USD"] = "USD"
    period_start: date
    period_end_exclusive: date
    source_ref: str | None = Field(default=None, max_length=1000)
    evidence_refs: list[EvidenceRef] = Field(default_factory=list, max_length=98)

    @field_validator("client_request_id", "title", "narrative")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must contain non-whitespace text")
        return value.strip()

    @field_validator("requested_amount", mode="before")
    @classmethod
    def explicit_decimal(cls, value):
        if value is not None and not isinstance(value, str):
            raise ValueError("requested_amount must be an explicit decimal string")
        return value

    @field_validator("requested_amount")
    @classmethod
    def positive_amount(cls, value):
        if value is not None and value <= 0:
            raise ValueError("requested_amount must be positive additional allocation, or null for an update")
        return value


class RequestPeriod(OutModel):
    id: str
    start_date: date
    end_date_exclusive: date
    label: str


class RequestSource(OutModel):
    reference: str | None
    submitted_by: str
    submitted_at: datetime


class AvailableDonor(OutModel):
    team_id: str
    headroom: MoneyStr


class RequestAssessment(OutModel):
    assessed_at: datetime
    budget_version: int | None
    envelope_total: MoneyStr | None
    team_allocation: MoneyStr | None
    recorded_spend: MoneyStr
    forecast_amount: MoneyStr | None
    forecast_run_id: str | None
    forecast_status: Literal["available", "unavailable"]
    forecast_unit: Literal["USD"] = "USD"
    forecast_basis: Literal["full_period_total"] = "full_period_total"
    projected_headroom: MoneyStr | None
    requested_allocation: MoneyStr | None
    available_donors: list[AvailableDonor]
    qualification: str
    amount_included_in_forecast: Literal[False] = False


class BudgetRequestOut(BudgetRequestCreate):
    id: str
    period: RequestPeriod
    source: RequestSource
    status: Literal["submitted", "pending_review", "needs_revision", "partially_funded", "approved_applied", "rejected"]
    linked_proposal_ids: list[str]
    decision_ids: list[str]
    approved_amount: MoneyStr
    remaining_requested_amount: MoneyStr | None
    assessment: RequestAssessment


class BudgetRequestList(OutModel):
    items: list[BudgetRequestOut]


class BudgetRequestDraft(InModel):
    base_version: int = Field(ge=1)
    action_type: Literal["addition", "transfer"]
    source_team_id: str | None = None


class BudgetRequestDraftOut(OutModel):
    request: BudgetRequestOut
    proposal: ProposalOut
