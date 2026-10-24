"""Chart specs: Vega-Lite v5 JSON built only from backend data (spend, budget, forecast, history).

The backend never renders a chart. It returns a self-contained Vega-Lite spec with the data inline, so a
client (or Droid, through the read-only `build_chart_spec` tool) can show exactly the numbers the API
holds. Money stays a decimal string in `spec.data.values[].amount`; the spec converts it for plotting
with a `toNumber` calculate transform, so no float is produced by the backend.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from app.schemas.common import DataLabels, InModel, OutModel
from app.schemas.forecasts import Availability

ChartKind = Literal["spend_vs_allocation", "projection_vs_allocation", "spend_by_cost_category", "budget_history"]

CHART_KINDS: tuple[str, ...] = ("spend_vs_allocation", "projection_vs_allocation", "spend_by_cost_category",
                                "budget_history")


class ChartRequest(InModel):
    """What a caller (HTTP query or the Droid tool) asks for. `metric` defaults per kind."""

    kind: ChartKind
    team: str | None = Field(default=None, min_length=1, max_length=100)
    metric: str | None = Field(default=None, min_length=1, max_length=50)


class ChartKindOut(OutModel):
    kind: ChartKind
    description: str
    metrics: list[str]
    default_metric: str
    # Values accepted by `team` besides active team ids (e.g. "unattributed" for cost categories).
    extra_teams: list[str]


class ChartKindList(OutModel):
    vega_lite_schema: str
    kinds: list[ChartKindOut]


class ChartSpecOut(OutModel):
    kind: ChartKind
    metric: str
    team: str | None
    period: str
    unit: str
    title: str
    # Value kinds of the plotted data (measured | estimated | reported | simulated, plus `planned` for
    # internal allocations). The same labels appear in the spec's title, subtitle and description.
    value_kinds: list[str]
    data_labels: DataLabels
    # Spend coverage for the plotted scope (complete | partial | missing).
    coverage_status: str
    # Forecast availability for projection charts; `null` for charts that use no forecast.
    forecast_availability: Availability | None
    row_count: int
    notes: list[str]
    # Backend endpoints whose data the spec contains (read-only).
    sources: list[str]
    # Vega-Lite v5 spec, data inline. Render it as-is (e.g. vega-embed); do not recompute the numbers.
    spec: dict[str, Any]
