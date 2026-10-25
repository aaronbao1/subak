"""Service metadata and the combined company overview."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from app.schemas.budget import BudgetState
from app.schemas.common import CoverageStatus, MoneyStr, OutModel
from app.schemas.forecasts import ForecastResult
from app.schemas.imports import PeriodOut
from app.schemas.spending import SpendSummary


class RealVsSimulated(OutModel):
    component: str
    status: Literal["real", "simulated", "placeholder", "fake", "demo"]
    detail: str


class CompanyMeta(OutModel):
    id: str
    name: str
    as_of: date | None
    is_simulated: bool
    # Where the name came from: env var > company_profile record > Northstar default.
    source: Literal["env", "db", "default"]
    detail: str


class MetaOut(OutModel):
    service: str
    version: str
    company: CompanyMeta
    period: PeriodOut | None
    unit: Literal["USD"]
    money_format: str
    runner_kind: Literal["fake", "sdk"]
    forecast_provider: str
    forecast_mode: Literal["placeholder", "unavailable", "forecasting_package"]
    identity_mode: Literal["demo_headers_unauthenticated"]
    roles: list[str]
    real_vs_simulated: list[RealVsSimulated]


class TeamOverview(OutModel):
    team: str
    allocation: MoneyStr | None
    recorded_spend: MoneyStr
    remaining: MoneyStr | None
    # None whenever the forecast has no projection for this team; never substituted with zero.
    projected: MoneyStr | None
    projected_minus_allocation: MoneyStr | None
    coverage_status: CoverageStatus


class CompanyOverview(OutModel):
    envelope_total: MoneyStr | None
    recorded_spend: MoneyStr
    unattributed_spend: MoneyStr
    projected_total: MoneyStr | None  # only when every team has a projection


class Overview(OutModel):
    period: PeriodOut
    unit: Literal["USD"]
    as_of: datetime
    company: CompanyOverview
    teams: list[TeamOverview]
    spend: SpendSummary
    budget: BudgetState | None
    budget_unavailable_reason: str | None
    forecast: ForecastResult
    notes: list[str]
