"""Shared API types: MoneyStr, enums, coverage."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, PlainSerializer

from app.core.money import MoneyError, money_str, parse_money


def _money_in(value: Any) -> Decimal:
    try:
        return parse_money(value)
    except MoneyError as exc:
        raise ValueError(f"{exc.code}: {exc}") from exc


MoneyStr = Annotated[
    Decimal,
    BeforeValidator(_money_in),
    PlainSerializer(money_str, return_type=str, when_used="always"),
]

Unit = Literal["USD"]
ValueKind = Literal["measured", "estimated", "reported", "simulated"]
CostCategory = Literal["subscription_fee", "included_usage", "billable_overage", "direct_api", "unpriced_usage"]
CoverageStatus = Literal["complete", "partial", "missing"]


class OutModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class InModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Coverage(OutModel):
    status: CoverageStatus
    record_count: int
    unmapped_records: int
    counter_resets: int
    last_record_at: datetime | None
    notes: list[str]


class DataLabels(OutModel):
    simulated: bool
    real_sample: bool


class ErrorDetail(OutModel):
    code: str
    message: str
    details: dict[str, Any]


class ErrorBody(OutModel):
    """Every 4xx/5xx response: {"error": {"code", "message", "details"}}. Branch on `code`."""

    error: ErrorDetail
