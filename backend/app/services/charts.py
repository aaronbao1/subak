"""Vega-Lite v5 chart specs built ONLY from backend data (read-only).

Kinds:
- `spend_vs_allocation`: recorded spend to date next to each team's internal allocation
  (metric `recorded_spend`, default) or allocation minus recorded spend (`remaining`).
- `projection_vs_allocation`: the ForecastProvider's full-period projection next to allocation
  (`projected`, default) or projection minus allocation (`gap`). An unavailable forecast plots no
  projection rows at all (never zeros) and says so in the title, subtitle and notes.
- `spend_by_cost_category`: recorded spend per team stacked by cost category (`recorded_spend`,
  default; included usage and unpriced usage never count as spend and are not plotted, their notional
  value / token volume is reported in `notes`) or usage record counts for every category
  (`record_count`). The `unattributed` bucket is a column of its own.
- `budget_history`: saved allocations per team across budget versions (`allocation`, default) or the
  envelope total per version (`envelope_total`), each point linked to the decision that saved it.

Every spec carries the data inline (`data.values`), with money as decimal strings in `amount` and a
`toNumber` calculate transform producing the plotted `value`; the value kinds (`measured`,
`estimated`, `reported`, `simulated`, `planned` for internal allocations) and the simulated / real
sample labels are in the title, subtitle, description and `usermeta`. Nothing here writes: no
forecast snapshot is persisted and no run is started.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.errors import DomainError
from app.core.money import money_str
from app.db.models import COST_CATEGORIES, NON_SPEND_CATEGORIES
from app.schemas.charts import CHART_KINDS
from app.services import budget as budget_svc
from app.services import coverage as coverage_svc
from app.services import forecasts as forecast_svc
from app.services import spending as spending_svc

VEGA_LITE_SCHEMA = "https://vega.github.io/schema/vega-lite/v5.json"
UNATTRIBUTED = spending_svc.UNATTRIBUTED
PLANNED = "planned"  # value kind label for internal allocations (a plan, not spend)

KIND_INFO: dict[str, dict[str, Any]] = {
    "spend_vs_allocation": {
        "description": "Recorded spend to date next to each team's internal allocation (or allocation minus "
                       "recorded spend with metric `remaining`).",
        "metrics": ["recorded_spend", "remaining"], "extra_teams": [],
    },
    "projection_vs_allocation": {
        "description": "Full-period projection from the ForecastProvider next to each team's allocation (or "
                       "projection minus allocation with metric `gap`). No projection rows when unavailable.",
        "metrics": ["projected", "gap"], "extra_teams": [],
    },
    "spend_by_cost_category": {
        "description": "Recorded spend per team stacked by cost category; included and unpriced usage are never "
                       "spend (metric `record_count` counts usage records in every category).",
        "metrics": ["recorded_spend", "record_count"], "extra_teams": [UNATTRIBUTED],
    },
    "budget_history": {
        "description": "Saved allocations per team across budget versions, each linked to its decision (or the "
                       "envelope total per version with metric `envelope_total`).",
        "metrics": ["allocation", "envelope_total"], "extra_teams": [],
    },
}
assert tuple(KIND_INFO) == CHART_KINDS


def chart_kinds() -> dict:
    return {
        "vega_lite_schema": VEGA_LITE_SCHEMA,
        "kinds": [{"kind": k, "description": v["description"], "metrics": list(v["metrics"]),
                   "default_metric": v["metrics"][0], "extra_teams": list(v["extra_teams"])}
                  for k, v in KIND_INFO.items()],
    }


def _invalid(reasons: list[dict]) -> DomainError:
    return DomainError("validation_failed", 422,
                       "chart request is invalid: " + ", ".join(sorted({r["code"] for r in reasons})),
                       {"reasons": reasons})


def build_chart(session: Session, kind: str, *, team: str | None = None, metric: str | None = None,
                period_id: str | None = None, provider: Any, clock: Clock) -> dict:
    """Return a `ChartSpecOut` dict. Raises 404 `unknown_chart_kind` or 422 `validation_failed`."""
    info = KIND_INFO.get(kind)
    if info is None:
        raise DomainError("unknown_chart_kind", 404, f"unknown chart kind {kind!r}", {"kinds": list(CHART_KINDS)})
    metric = metric or info["metrics"][0]
    reasons = []
    if metric not in info["metrics"]:
        reasons.append({"code": "unknown_metric", "field": "metric",
                        "message": f"{kind} supports metric {', '.join(info['metrics'])}; got {metric!r}"})
    active = forecast_svc.active_team_ids(session)
    if team is not None and team not in active and team not in info["extra_teams"]:
        reasons.append({"code": "unknown_team", "field": "team",
                        "message": f"unknown or inactive team {team!r}"})
    if team is not None and kind == "budget_history" and metric == "envelope_total":
        reasons.append({"code": "team_not_applicable", "field": "team",
                        "message": "the envelope total is company-wide; omit team"})
    if reasons:
        raise _invalid(reasons)
    period = coverage_svc.resolve_period(session, period_id, clock.now())
    spend = spending_svc.spend_summary(session, period, clock=clock)
    ctx = _Context(kind=kind, metric=metric, team=team, period_id=period.id, spend=spend)
    if kind == "spend_vs_allocation":
        _spend_vs_allocation(ctx, session, period, clock)
    elif kind == "projection_vs_allocation":
        _projection_vs_allocation(ctx, session, period, clock, provider)
    elif kind == "spend_by_cost_category":
        _spend_by_category(ctx)
    else:
        _budget_history(ctx, session, period, clock)
    return ctx.out()


# ---- shared labelling ----------------------------------------------------------------------------


def _team_kinds(team_spend: dict) -> list[str]:
    kinds = [k for k, v in team_spend["by_value_kind"].items() if v]
    if not kinds:
        kinds = list(team_spend.get("coverage", {}).get("value_kinds") or [])
    return sorted(kinds)


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _join(kinds: list[str]) -> str:
    return "+".join(kinds) if kinds else "none"


class _Context:
    def __init__(self, *, kind: str, metric: str, team: str | None, period_id: str, spend: dict) -> None:
        self.kind, self.metric, self.team, self.period_id, self.spend = kind, metric, team, period_id, spend
        self.unit = spend["unit"]
        self.rows: list[dict] = []
        self.notes: list[str] = []
        self.value_kinds: set[str] = set()
        self.sources: list[str] = []
        self.base_title = ""
        self.forecast_availability: str | None = None
        self.forecast_label: str | None = None
        self.mark: dict = {}
        self.encoding: dict = {}
        self.y_field = "value"
        teams = {t["team"]: t for t in spend["teams"]}
        if team is None or team == UNATTRIBUTED:
            self.coverage_status = spend["coverage"]["status"]
        else:
            self.coverage_status = teams[team]["coverage"]["status"] if team in teams else "missing"
        self.team_spend = teams

    def include(self, team: str) -> bool:
        return self.team is None or self.team == team

    def spend_kinds(self, team: str) -> list[str]:
        if team == UNATTRIBUTED:
            return _team_kinds(self.spend["unattributed"])
        return _team_kinds(self.team_spend[team]) if team in self.team_spend else []

    def sim_label(self) -> str:
        """Label for what is PLOTTED: the value kinds of the data rows; a planned-only chart (allocations)
        takes the period's dataset labels, since allocations carry no value kind of their own."""
        plotted = self.value_kinds - {PLANNED}
        if plotted:
            sim, real = "simulated" in plotted, bool(plotted - {"simulated"})
        else:
            labels = self.spend["data_labels"]
            sim, real = labels["simulated"], labels["real_sample"]
        if sim and real:
            return "simulated + real data"
        if sim:
            return "simulated data (fictional Northstar example)"
        if real:
            return "real data (" + ", ".join(sorted(plotted)) + ")" if plotted else "real sample data"
        return "no data labels"

    def out(self) -> dict:
        kinds = sorted(self.value_kinds)
        if (self.spend["data_labels"]["real_sample"] and self.value_kinds - {PLANNED}
                and not self.value_kinds & {"measured", "reported", "estimated"}):
            self.notes.append("real sample usage in this period carries no dollar amount (token telemetry), so it "
                              "is not in the plotted spend.")
        scope = f"team {self.team}" if self.team else "all teams"
        title = f"{self.base_title} | {self.period_id} | {self.unit} | {self.sim_label()}"
        subtitle = [f"value kinds: {', '.join(kinds) or 'none'} ({PLANNED} = internal allocation, not spend)",
                    f"spend coverage: {self.coverage_status}; {scope}"]
        if self.forecast_availability is not None:
            subtitle.append(f"forecast: {self.forecast_availability}"
                            + (f" ({self.forecast_label})" if self.forecast_label else ""))
        description = (f"{self.base_title} for planning period {self.period_id} in {self.unit}, {scope}. "
                       f"Value kinds: {', '.join(kinds) or 'none'}; {self.sim_label()}. "
                       f"Spend coverage {self.coverage_status}. Built by the Northstar backend from "
                       f"{', '.join(self.sources)}; data inline, nothing estimated by the chart.")
        if self.notes:
            description += " " + " ".join(self.notes)
        transform = [{"calculate": "toNumber(datum.amount)", "as": "value"}] if self.y_field == "value" else []
        spec = {
            "$schema": VEGA_LITE_SCHEMA,
            "title": {"text": title, "subtitle": subtitle},
            "description": description,
            "width": "container",
            "height": 300,
            "data": {"name": "northstar", "values": self.rows},
            **({"transform": transform} if transform else {}),
            "mark": self.mark,
            "encoding": self.encoding,
            "usermeta": {"northstar": {
                "kind": self.kind, "metric": self.metric, "team": self.team, "period": self.period_id,
                "unit": self.unit, "value_kinds": kinds, "data_labels": dict(self.spend["data_labels"]),
                "coverage_status": self.coverage_status, "forecast_availability": self.forecast_availability,
                "sources": list(self.sources), "money_field": "amount (decimal string)",
            }},
        }
        return {
            "kind": self.kind, "metric": self.metric, "team": self.team, "period": self.period_id,
            "unit": self.unit, "title": title, "value_kinds": kinds,
            "data_labels": dict(self.spend["data_labels"]), "coverage_status": self.coverage_status,
            "forecast_availability": self.forecast_availability, "row_count": len(self.rows),
            "notes": list(self.notes), "sources": list(self.sources), "spec": spec,
        }


def _money_axis(unit: str, title: str | None = None) -> dict:
    return {"field": "value", "type": "quantitative", "title": title or unit, "axis": {"format": ",.2f"}}


_TOOLTIP_MONEY = [{"field": "team", "type": "nominal", "title": "Team"},
                  {"field": "series", "type": "nominal", "title": "Series"},
                  {"field": "amount", "type": "nominal", "title": "Amount"},
                  {"field": "value_kind", "type": "nominal", "title": "Value kind"}]


def _grouped_bars(ctx: _Context, series: list[str], y_title: str) -> None:
    ctx.mark = {"type": "bar", "tooltip": True}
    ctx.encoding = {
        "x": {"field": "team", "type": "nominal", "title": "Team", "sort": None},
        "xOffset": {"field": "series", "type": "nominal", "sort": series},
        "y": _money_axis(ctx.unit, y_title),
        "color": {"field": "series", "type": "nominal", "title": "Series", "scale": {"domain": series}},
        "tooltip": _TOOLTIP_MONEY + [{"field": "coverage_status", "type": "nominal", "title": "Spend coverage"}],
    }


def _signed_bars(ctx: _Context, y_title: str) -> None:
    ctx.mark = {"type": "bar", "tooltip": True}
    ctx.encoding = {
        "x": {"field": "team", "type": "nominal", "title": "Team", "sort": None},
        "y": _money_axis(ctx.unit, y_title),
        "color": {"condition": {"test": "datum.value < 0", "value": "#c0392b"}, "value": "#4c78a8"},
        "tooltip": _TOOLTIP_MONEY + [{"field": "coverage_status", "type": "nominal", "title": "Spend coverage"}],
    }


# ---- kinds -----------------------------------------------------------------------------------------


def _spend_vs_allocation(ctx: _Context, session: Session, period, clock: Clock) -> None:
    _, env = budget_svc.resolve_envelope(session, period.id, clock)
    state = budget_svc.budget_state(session, period, env)
    ctx.sources = [f"/api/budget?period={period.id}", f"/api/spend/summary?period={period.id}"]
    ctx.notes.append(f"budget state_version {state['state_version']}; recorded spend is attributed spend to date "
                     f"(as of {_iso(ctx.spend['as_of'])}).")
    for a in state["allocations"]:
        t = a["team"]
        if not ctx.include(t):
            continue
        kinds = ctx.spend_kinds(t)
        common = {"team": t, "coverage_status": a["coverage_status"], "state_version": state["state_version"]}
        if ctx.metric == "recorded_spend":
            ctx.rows.append({**common, "series": "allocation", "amount": money_str(a["amount"]),
                             "value_kind": PLANNED, "simulated": None})
            ctx.rows.append({**common, "series": "recorded_spend", "amount": money_str(a["recorded_spend"]),
                             "value_kind": _join(kinds), "simulated": "simulated" in kinds})
        else:
            ctx.rows.append({**common, "series": "remaining", "amount": money_str(a["remaining"]),
                             "value_kind": f"{PLANNED}-{_join(kinds)}", "simulated": "simulated" in kinds})
        ctx.value_kinds.update([PLANNED, *kinds])
    un = ctx.spend["unattributed"]
    if un["record_count"] and ctx.team is None:
        kinds = ctx.spend_kinds(UNATTRIBUTED)
        msg = (f"{money_str(un['recorded_spend'])} {ctx.unit} of unattributed spend "
               f"({un['record_count']} record(s)) belongs to no team")
        if ctx.metric == "recorded_spend":
            ctx.rows.append({"team": UNATTRIBUTED, "series": "recorded_spend",
                             "amount": money_str(un["recorded_spend"]), "value_kind": _join(kinds),
                             "simulated": "simulated" in kinds, "coverage_status": ctx.spend["coverage"]["status"],
                             "state_version": state["state_version"]})
            ctx.value_kinds.update(kinds)
            ctx.notes.append(msg + "; plotted as its own column with no allocation.")
        else:
            ctx.notes.append(msg + "; it is in no team's remaining figure.")
    if ctx.metric == "recorded_spend":
        ctx.base_title = "Recorded spend vs allocation by team"
        _grouped_bars(ctx, ["allocation", "recorded_spend"], ctx.unit)
    else:
        ctx.base_title = "Allocation remaining after recorded spend by team"
        ctx.notes.append("negative remaining means recorded spend already exceeds the allocation.")
        _signed_bars(ctx, f"remaining ({ctx.unit})")


def _projection_vs_allocation(ctx: _Context, session: Session, period, clock: Clock, provider: Any) -> None:
    _, env = budget_svc.resolve_envelope(session, period.id, clock)
    state = budget_svc.budget_state(session, period, env)
    forecast = forecast_svc.forecast_for_period(session, provider, period, clock=clock)  # not snapshotted
    ctx.sources = [f"/api/budget?period={period.id}", f"/api/forecasts?period={period.id}"]
    ctx.forecast_availability = forecast.availability
    projections = {p.team: p for p in forecast.projections}
    if forecast.availability != "unavailable":
        ctx.forecast_label = forecast.value_kind
        ctx.notes.append(f"projections are {forecast.value_kind} ({forecast.method_label}), basis "
                         f"{forecast.basis}, provider {forecast.provider}; not measured spend.")
    else:
        ctx.notes.append(f"projections unavailable ({forecast.reason or 'no reason given'}); no projection is "
                         "plotted (never zero).")
    if forecast.availability == "partial" and forecast.missing_teams:
        ctx.notes.append(f"no projection for {', '.join(forecast.missing_teams)}; those teams show allocation only.")
    ctx.notes.append(f"budget state_version {state['state_version']}.")
    for a in state["allocations"]:
        t = a["team"]
        if not ctx.include(t):
            continue
        p = projections.get(t)
        common = {"team": t, "coverage_status": a["coverage_status"], "state_version": state["state_version"]}
        if ctx.metric == "projected":
            ctx.rows.append({**common, "series": "allocation", "amount": money_str(a["amount"]),
                             "value_kind": PLANNED, "simulated": None})
            ctx.value_kinds.add(PLANNED)
            if p is not None:
                ctx.rows.append({**common, "series": "projected", "amount": money_str(p.amount),
                                 "value_kind": forecast.value_kind, "simulated": forecast.value_kind == "simulated",
                                 "basis": forecast.basis, "method_label": forecast.method_label})
                ctx.value_kinds.add(forecast.value_kind)
        elif p is not None:
            ctx.rows.append({**common, "series": "projected_minus_allocation",
                             "amount": money_str(p.amount - a["amount"]),
                             "value_kind": f"{forecast.value_kind}-{PLANNED}",
                             "simulated": forecast.value_kind == "simulated", "basis": forecast.basis,
                             "method_label": forecast.method_label})
            ctx.value_kinds.update([PLANNED, forecast.value_kind])
    if ctx.metric == "projected":
        ctx.base_title = "Projection vs allocation by team"
        if forecast.availability == "unavailable":
            ctx.base_title += " (projections unavailable)"
        _grouped_bars(ctx, ["allocation", "projected"], ctx.unit)
    else:
        ctx.base_title = "Projected overrun (+) or headroom (-) vs allocation by team"
        if forecast.availability == "unavailable":
            ctx.base_title += " (projections unavailable)"
        _signed_bars(ctx, f"projected minus allocation ({ctx.unit})")


def _spend_by_category(ctx: _Context) -> None:
    ctx.sources = [f"/api/spend/summary?period={ctx.period_id}"]
    buckets = list(ctx.spend["teams"])
    un = ctx.spend["unattributed"]
    if un["record_count"] or ctx.team == UNATTRIBUTED:
        buckets.append(un)
    notional = Decimal("0.00")
    unpriced = 0
    for b in buckets:
        t = b["team"]
        if not ctx.include(t):
            continue
        kinds = ctx.spend_kinds(t)
        notional += b["included_usage_notional"]
        unpriced += b["unpriced_tokens"]
        for cat in COST_CATEGORIES:
            c = b["by_cost_category"][cat]
            if not c["record_count"]:
                continue
            if ctx.metric == "recorded_spend":
                if cat in NON_SPEND_CATEGORIES:
                    continue
                ctx.rows.append({"team": t, "cost_category": cat, "amount": money_str(c["amount"]),
                                 "record_count": c["record_count"], "counts_toward_spend": True,
                                 "value_kind": _join(kinds), "simulated": "simulated" in kinds})
            else:
                ctx.rows.append({"team": t, "cost_category": cat, "count": c["record_count"],
                                 "counts_toward_spend": c["counts_toward_spend"],
                                 "value_kind": _join(kinds), "simulated": "simulated" in kinds})
            ctx.value_kinds.update(kinds)
    tooltip = [{"field": "team", "type": "nominal", "title": "Team"},
               {"field": "cost_category", "type": "nominal", "title": "Cost category"},
               {"field": "value_kind", "type": "nominal", "title": "Value kind"},
               {"field": "counts_toward_spend", "type": "nominal", "title": "Counts toward spend"}]
    ctx.mark = {"type": "bar", "tooltip": True}
    color = {"field": "cost_category", "type": "nominal", "title": "Cost category",
             "scale": {"domain": [c for c in COST_CATEGORIES
                                  if ctx.metric == "record_count" or c not in NON_SPEND_CATEGORIES]}}
    if ctx.metric == "recorded_spend":
        ctx.base_title = "Recorded spend by cost category"
        ctx.notes.append("included usage and unpriced usage are never spend and are not plotted.")
        if notional:
            ctx.notes.append(f"included usage notional value {money_str(notional)} {ctx.unit} is display-only.")
        if unpriced:
            ctx.notes.append(f"{unpriced} unpriced token(s) have no known cost and are not converted to dollars.")
        ctx.encoding = {"x": {"field": "team", "type": "nominal", "title": "Team", "sort": None},
                        "y": {**_money_axis(ctx.unit), "stack": "zero"}, "color": color,
                        "tooltip": tooltip[:2] + [{"field": "amount", "type": "nominal", "title": "Amount"},
                                                  {"field": "record_count", "type": "quantitative",
                                                   "title": "Records"}] + tooltip[2:]}
    else:
        ctx.y_field = "count"
        ctx.base_title = "Usage records by cost category"
        ctx.notes.append("record counts, not dollars; included and unpriced usage records are counted but are "
                         "never spend.")
        ctx.encoding = {"x": {"field": "team", "type": "nominal", "title": "Team", "sort": None},
                        "y": {"field": "count", "type": "quantitative", "title": "records", "stack": "zero"},
                        "color": color,
                        "tooltip": tooltip[:2] + [{"field": "count", "type": "quantitative", "title": "Records"}]
                        + tooltip[2:]}


def _budget_history(ctx: _Context, session: Session, period, clock: Clock) -> None:
    _, env = budget_svc.resolve_envelope(session, period.id, clock)
    hist = budget_svc.history(session, period, env)
    ctx.sources = [f"/api/budget/history?period={period.id}"]
    ctx.value_kinds.add(PLANNED)
    ctx.notes.append(f"{len(hist['snapshots'])} saved version(s); current version {hist['current_version']}. "
                     "Each point is an immutable snapshot; version 1 is the seeded starting budget.")
    for snap in hist["snapshots"]:
        d = snap["decision"]
        common = {"state_version": snap["state_version"], "value_kind": PLANNED, "simulated": None,
                  "decision_id": d["id"] if d else None, "action_type": d["action_type"] if d else None,
                  "decided_by": d["actor_id"] if d else None,
                  "saved_at": _iso(snap["created_at"])}
        if ctx.metric == "envelope_total":
            ctx.rows.append({**common, "series": "envelope_total", "team": None,
                             "amount": money_str(snap["total_amount"])})
            continue
        for t, amount in sorted(snap["allocations"].items()):
            if ctx.include(t):
                ctx.rows.append({**common, "series": "allocation", "team": t, "amount": money_str(amount)})
    tooltip = [{"field": "state_version", "type": "ordinal", "title": "Version"},
               {"field": "team", "type": "nominal", "title": "Team"},
               {"field": "amount", "type": "nominal", "title": "Amount"},
               {"field": "action_type", "type": "nominal", "title": "Decision type"},
               {"field": "decision_id", "type": "nominal", "title": "Decision"},
               {"field": "saved_at", "type": "nominal", "title": "Saved at"}]
    ctx.mark = {"type": "line", "point": True, "tooltip": True}
    ctx.encoding = {"x": {"field": "state_version", "type": "ordinal", "title": "Budget version"},
                    "y": _money_axis(ctx.unit)}
    if ctx.metric == "envelope_total":
        ctx.base_title = "Envelope total across budget versions"
        ctx.encoding["tooltip"] = [x for x in tooltip if x["field"] != "team"]
    else:
        ctx.base_title = "Allocation by team across budget versions"
        ctx.encoding["color"] = {"field": "team", "type": "nominal", "title": "Team"}
        ctx.encoding["tooltip"] = tooltip
