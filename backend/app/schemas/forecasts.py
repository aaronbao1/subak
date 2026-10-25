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
    """One person's share of a team placeholder. A proportional split, NOT a person-level model.

    `amount` is the full-period total (spend to date + remaining). `share` is the person's percent of
    the split weights (recorded spend to date), one decimal place, as text - not money.
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


class ForecastModelChoice(BaseModel):
    """One team's model from the latest model run (ForecastingPackageProvider)."""

    model_config = ConfigDict(extra="forbid")

    team: str
    model: str
    validated: bool          # chosen by backtest (False: too little history, used unvalidated)
    wape: str | None = None  # backtest WAPE as a ratio, 4 places (text, not money)
    scored_origins: int = 0
    history_days: int = 0


class ForecastSkip(BaseModel):
    model_config = ConfigDict(extra="forbid")

    team: str
    reason: str


class ForecastRefreshOut(BaseModel):
    """POST /api/forecasts/refresh. `refreshed` is false for providers without a model cache."""

    model_config = ConfigDict(extra="forbid")

    provider: str
    refreshed: bool
    reason: str | None = None
    period: str | None = None
    history_end: _dt.date | None = None   # first day not in the fitted history (the partial latest day)
    horizon_days: int | None = None
    backtest_origins: int | None = None
    computed_at: datetime | None = None
    elapsed_ms: int | None = None
    teams: list[ForecastModelChoice] = Field(default_factory=list)
    skipped: list[ForecastSkip] = Field(default_factory=list)
