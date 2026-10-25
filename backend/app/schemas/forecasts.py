"""Projections and supported scenarios (design.md §4, §6). Every projection is labeled simulated."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import MoneyStr, OutModel

Availability = Literal["available", "partial", "unavailable"]
Basis = Literal["full_period_total", "remaining"]


class TeamProjection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    team: str
    amount: MoneyStr
    unit: Literal["USD"] = "USD"
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


class ForecastSnapshotOut(OutModel):
    id: str
    period: str
    provider: str
    availability: Availability
    fetched_at: datetime
    forecast: ForecastResult
