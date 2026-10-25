"""ForecastProvider interface and the shared Northstar placeholder (design.md §6).

This is NOT a forecasting model. The forecasting teammate plugs a real provider in behind
`ForecastProvider`; until then `PlaceholderForecastProvider` returns the shared Northstar projections
(research 85k, product 50k, engineering 65k for 2026-P1), labeled `simulated`, or an honest
`unavailable` result.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal
from typing import Literal, Protocol, runtime_checkable

from app.schemas.forecasts import ForecastResult, TeamProjection

PLACEHOLDER_PERIOD = "2026-P1"
PLACEHOLDER_PROJECTIONS: dict[str, Decimal] = {
    "research": Decimal("85000.00"),
    "product": Decimal("50000.00"),
    "engineering": Decimal("65000.00"),
}
PLACEHOLDER_METHOD = "shared placeholder (not a forecast model)"
UNAVAILABLE_REASON = "forecast provider not connected"


@runtime_checkable
class ForecastProvider(Protocol):
    name: str

    def get_forecast(self, period_id: str, team_ids: Sequence[str]) -> ForecastResult: ...


class PlaceholderForecastProvider:
    """Shared Northstar placeholder projections. NOT a model."""

    name = "placeholder"

    def __init__(self, mode: Literal["available", "unavailable"] = "available") -> None:
        if mode not in ("available", "unavailable"):
            raise ValueError(f"unknown placeholder mode {mode!r}")
        self.mode = mode

    def get_forecast(self, period_id: str, team_ids: Sequence[str]) -> ForecastResult:
        if self.mode == "unavailable":
            return ForecastResult(
                provider=self.name, availability="unavailable", reason=UNAVAILABLE_REASON,
                target_period=period_id, projections=[], missing_teams=sorted(team_ids),
                method_label=PLACEHOLDER_METHOD,
            )
        if period_id != PLACEHOLDER_PERIOD:
            return ForecastResult(
                provider=self.name, availability="unavailable",
                reason=f"no placeholder projections exist for period {period_id!r}",
                target_period=period_id, projections=[], missing_teams=sorted(team_ids),
                method_label=PLACEHOLDER_METHOD,
            )
        projections = [
            TeamProjection(
                team=t, amount=PLACEHOLDER_PROJECTIONS[t],
                assumptions=["shared Northstar sample projection agreed across workstreams",
                             "full-period total for the planning period, not a remaining amount"],
                uncertainty="placeholder value; no model or historical fit behind it",
            )
            for t in sorted(team_ids) if t in PLACEHOLDER_PROJECTIONS
        ]
        missing = sorted(t for t in team_ids if t not in PLACEHOLDER_PROJECTIONS)
        if not projections:
            availability, reason = "unavailable", "no placeholder projections for the requested teams"
        elif missing:
            availability, reason = "partial", f"no placeholder projection for: {', '.join(missing)}"
        else:
            availability, reason = "available", None
        return ForecastResult(
            provider=self.name, availability=availability, reason=reason, target_period=period_id,
            basis="full_period_total", projections=projections, missing_teams=missing,
            value_kind="simulated", method_label=PLACEHOLDER_METHOD,
        )


def provider_from_settings(name: str, *, forecast_service=None, session_factory=None) -> ForecastProvider:
    """`FORECAST_PROVIDER=placeholder|unavailable` (validated in Settings)."""
    if name == "engine":
        from app.providers.engine import EngineForecastProvider
        return EngineForecastProvider(forecast_service, session_factory)
    if name == "unavailable":
        return PlaceholderForecastProvider(mode="unavailable")
    return PlaceholderForecastProvider(mode="available")
