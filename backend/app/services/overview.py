"""Company overview: spend + budget + forecast in one response. Each section degrades on its own:
a missing budget or an unavailable forecast never hides measured spending."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.errors import DomainError
from app.db.models import PlanningPeriod
from app.providers.forecast import ForecastProvider
from app.services import budget as budget_svc
from app.services import forecasts as forecast_svc
from app.services import spending as spending_svc

ZERO = Decimal("0.00")


def overview(session: Session, period: PlanningPeriod, provider: ForecastProvider, *, clock: Clock) -> dict:
    spend = spending_svc.spend_summary(session, period, clock=clock)
    budget = None
    budget_reason = None
    env = budget_svc.get_envelope(session, period.id)
    if env is None:
        budget_reason = f"no budget envelope exists for period {period.id}"
    else:
        try:
            budget = budget_svc.budget_state(session, period, env)
        except DomainError as exc:  # pragma: no cover - defensive; budget_state does not raise today
            budget_reason = exc.message
    forecast = forecast_svc.forecast_for_period(session, provider, period, clock=clock)

    allocs = {a["team"]: a["amount"] for a in budget["allocations"]} if budget else {}
    projected = {p.team: p.amount for p in forecast.projections} if forecast.availability != "unavailable" else {}
    teams = []
    for t in spend["teams"]:
        team = t["team"]
        alloc = allocs.get(team)
        proj = projected.get(team)
        teams.append({
            "team": team,
            "allocation": alloc,
            "recorded_spend": t["recorded_spend"],
            "remaining": None if alloc is None else alloc - t["recorded_spend"],
            "projected": proj,
            "projected_minus_allocation": None if proj is None or alloc is None else proj - alloc,
            "coverage_status": t["coverage"]["status"],
        })

    notes = []
    if forecast.availability == "unavailable":
        notes.append(f"forecast unavailable ({forecast.reason}); spend and budget are shown without projections")
    elif forecast.availability == "partial":
        notes.append(f"forecast partial ({forecast.reason})")
    if forecast.projections:
        notes.append(f"projections are {forecast.value_kind} ({forecast.method_label}), basis {forecast.basis}")
    if budget_reason:
        notes.append(budget_reason)
    if spend["coverage"]["status"] != "complete":
        notes.append(f"spend coverage is {spend['coverage']['status']}; see coverage notes")

    all_projected = forecast.availability == "available" and all(t["projected"] is not None for t in teams)
    return {
        "period": spend["period"],
        "unit": "USD",
        "as_of": spend["as_of"],
        "company": {
            "envelope_total": budget["envelope_total"] if budget else None,
            "recorded_spend": spend["company_total"],
            "unattributed_spend": spend["unattributed"]["recorded_spend"],
            "projected_total": sum((t["projected"] for t in teams), ZERO) if all_projected and teams else None,
        },
        "teams": teams,
        "spend": spend,
        "budget": budget,
        "budget_unavailable_reason": budget_reason,
        "forecast": forecast,
        "notes": notes,
    }
