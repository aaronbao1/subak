"""Weekly recorded spend and immutable pre-week serving predictions."""
from datetime import date, datetime
from typing import Literal
from pydantic import Field
from app.schemas.common import OutModel
from app.schemas.usage import UsageScope


class WeeklyActual(OutModel):
    amount: str | None
    status: Literal['mature', 'partial', 'missing', 'pending', 'disputed', 'future']
    source: Literal['observed_outcome', 'repository_ledger', 'none']
    dataset_id: str | None
    revision: str | None
    corrected: bool
    source_refs: list[str]


class WeeklyPriorForecast(OutModel):
    amount: str
    run_id: str
    target_id: str
    issued_at: datetime
    information_cutoff: datetime | None
    start: date
    end_exclusive: date
    dataset_id: str


class WeeklyOutlook(OutModel):
    amount: str
    run_id: str
    issued_at: datetime
    information_cutoff: datetime | None
    start: date
    end_exclusive: date
    partial: bool
    dataset_id: str


class WeeklyVariance(OutModel):
    amount: str | None
    status: Literal['available', 'unavailable']
    reason: str | None


class WeeklyHistoryRow(OutModel):
    start: date
    end_exclusive: date
    state: Literal['closed', 'current', 'future']
    actual: WeeklyActual
    prior_forecast: WeeklyPriorForecast | None
    outlook: WeeklyOutlook | None
    variance: WeeklyVariance


class WeeklyHistoryResponse(OutModel):
    scope: UsageScope
    start_date: date
    end_date_exclusive: date
    timezone: Literal['UTC']
    unit: Literal['USD']
    basis: Literal['planning']
    quantity: Literal['spend']
    dataset_id: str
    as_of: datetime
    synthetic: bool
    actuals_revision: str
    selection_policy: Literal['latest_published_before_week_start']
    weeks: list[WeeklyHistoryRow] = Field(max_length=26)
    notes: list[str]
