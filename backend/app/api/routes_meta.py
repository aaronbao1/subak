"""Service metadata: period, unit, runner/provider modes, and honest real-vs-simulated labels."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import get_clock, get_forecast_provider
from app.core.actors import ROLES
from app.core.clock import Clock
from app.core.errors import DomainError
from app.db.session import get_session
from app.schemas.meta import MetaOut
from app.services import company as company_svc
from app.services import coverage as coverage_svc

router = APIRouter(prefix="/api", tags=["meta"])

REAL_VS_SIMULATED = [
    {"component": "northstar_spend_budgets_corpus", "status": "simulated",
     "detail": "fictional Northstar Software example; value_kind=simulated, is_simulated=true"},
    {"component": "codex_session_parser", "status": "real",
     "detail": "real Codex session format; imported samples are measured tokens, unpriced unless priced"},
    {"component": "projections", "status": "placeholder",
     "detail": "shared placeholder numbers behind ForecastProvider, not a forecasting model"},
    {"component": "droid_runner", "status": "fake",
     "detail": "deterministic FakeDroidRunner unless DROID_RUNNER=sdk with a Factory key; runner_kind always reported"},
    {"component": "identity", "status": "demo",
     "detail": "X-Actor-Id / X-Actor-Role headers are not authentication; authority rules are enforced"},
]


@router.get("/meta", response_model=MetaOut)
def meta(
    request: Request,
    session: Session = Depends(get_session),
    clock: Clock = Depends(get_clock),
    provider=Depends(get_forecast_provider),
):
    settings = request.app.state.settings
    try:
        period = coverage_svc.resolve_period(session, None, clock.now())
    except DomainError:
        period = None  # empty database: meta must still answer
    company = company_svc.resolve(session)
    rows = [dict(r) for r in REAL_VS_SIMULATED]
    if company["id"] != company_svc.DEFAULT_ID and company["source"] != "default":
        # Another dataset is loaded (e.g. datagen's Uber data): label it by name, keep the component key.
        rows[0] = {**rows[0], "status": "simulated" if company["is_simulated"] else "real",
                   "detail": f"{company['name']} dataset loaded from datagen; "
                             f"is_simulated={str(company['is_simulated']).lower()}"}
    if settings.droid_runner == "sdk":
        rows[3] = {**rows[3], "status": "real",
                   "detail": "Factory Droid SDK runner selected; runs fail with 503 if no key is configured"}
    if settings.forecast_provider == "engine":
        rows[2] = {**rows[2], "status": "simulated" if settings.forecast_demo else "real",
                   "detail": "Numerical forecast engine with immutable weekly/manual publications; "
                             + ("synthetic Northstar inputs" if settings.forecast_demo else "repository inputs; missing source coverage stays unknown")}
    if settings.forecast_provider == "unavailable":
        rows[2] = {**rows[2], "detail": "forecast provider in unavailable mode; no projections are returned"}
    return {
        "service": "northstar-backend",
        "version": request.app.version,
        "company": company,
        "period": period,
        "unit": "USD",
        "money_format": "decimal string with exactly two places, e.g. \"60000.00\"; never a float",
        "runner_kind": settings.droid_runner,
        "forecast_provider": getattr(provider, "name", type(provider).__name__),
        "forecast_mode": settings.forecast_provider,
        "identity_mode": "demo_headers_unauthenticated",
        "roles": list(ROLES),
        "real_vs_simulated": rows,
    }
