"""Projections and supported scenarios (design.md §4, §6). Every projection is labeled simulated."""

from __future__ import annotations

import datetime as _dt
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import MoneyStr, OutModel

Availability = Literal["available", "partial", "unavailable"]
Basis = Literal["full_period_total", "remaining"]


class DailyProjection(BaseModel):
    """Projected spend on one day after the data as-of (frontend-integration-design §4.2)."""

    model_config = ConfigDict(extra="forbid")

    date: _dt.date
    amount: MoneyStr


class TeamProjection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    team: str
    amount: MoneyStr
    unit: Literal["USD"] = "USD"
    assumptions: list[str] = Field(default_factory=list)
    uncertainty: str | None = None
    # Remaining projected spend per day (as-of + 1 .. period end). Built by summing the person and
    # team-level series, so per-day person sums never exceed it. None when not provided.
    daily: list[DailyProjection] | None = None


class PersonProjection(BaseModel):
    """A person's full-period projection, with method identified by its provider.

    The placeholder uses a proportional spend-to-date split; the engine supplies
    only compatible, immutable issued person quarters. `share` is the provider's
    declared percentage of the team total, as text rather than money.
    """

    model_config = ConfigDict(extra="forbid")

    person: str
    team: str
    amount: MoneyStr
    spent_to_date: MoneyStr
    share: str
    unit: Literal["USD"] = "USD"
    daily: list[DailyProjection] | None = None
    assumptions: list[str] = Field(default_factory=list)
    uncertainty: str | None = None


class ForecastResult(BaseModel):
    """What a ForecastProvider returns. `projections` is empty when unavailable - never zero-filled."""

    model_config = ConfigDict(extra="forbid")

    provider: str
    availability: Availability
    reason: str | None = None
    target_period: str
    basis: Basis = "full_period_total"
    projections: list[TeamProjection] = Field(default_factory=list)
    missing_teams: list[str] = Field(default_factory=list)
    value_kind: Literal["simulated", "estimated"] = "simulated"
    method_label: str
    generated_at: datetime | None = None
    forecast_run_id: str | None = None
    input_snapshot_id: str | None = None
    input_revision: str | None = None
    repository_revision: str | None = None
    tenant_id: str | None = None
    information_cutoff: datetime | None = None
    procedure_version: str | None = None
    # Optional per-person split of the team projections (sum + team-level remainder == team amount).
    person_projections: list[PersonProjection] = Field(default_factory=list)
    # Last day with counted usage in the period; daily points start the day after.
    as_of: _dt.date | None = None


class ForecastSnapshotOut(OutModel):
    id: str
    period: str
    provider: str
    availability: Availability
    fetched_at: datetime
    forecast: ForecastResult


class CompanyProjectionScope(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["company"] = "company"
    id: str | None


class CompanyProjectionOut(BaseModel):
    """SDK-only exact issued company receipt; it never changes the native snapshot."""

    model_config = ConfigDict(extra="forbid")
    availability: Literal["available", "unavailable"] = "unavailable"
    reason: str | None = None
    # Unlike native allocation amounts, an issued forecast can have sub-cent precision.
    amount: str | None = None
    scope: CompanyProjectionScope
    period_id: str
    period_start: _dt.date
    period_end_exclusive: _dt.date
    unit: Literal["USD"] = "USD"
    basis: Literal["planning"] = "planning"
    quantity: Literal["spend"] = "spend"
    timezone: Literal["UTC"] = "UTC"
    projection_basis: Literal["full_period_total"] = "full_period_total"
    run_id: str | None = None
    input_snapshot_id: str | None = None
    information_cutoff: datetime | None = None
    value_kind: Literal["simulated", "estimated"]
    qualification: str = "Issued company total includes shared spend; conditional on the recorded run's inputs."
