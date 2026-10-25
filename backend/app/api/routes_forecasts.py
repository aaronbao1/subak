"""Forecasts through the ForecastProvider (200 even when unavailable), snapshots, and the overview."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_clock, get_forecast_provider, get_ids
from app.core.actors import FINANCE_ROLES, Actor, require_role
from app.core.clock import Clock, IdFactory
from app.db.session import get_session
from app.schemas.forecasts import ForecastRefreshOut, ForecastResult, ForecastSnapshotOut
from app.schemas.meta import Overview
from app.services import coverage as coverage_svc
from app.services import forecasts as svc
from app.services import overview as overview_svc

router = APIRouter(prefix="/api", tags=["forecasts"])


@router.get("/forecasts", response_model=ForecastResult)
def get_forecast(
    period: str | None = Query(default=None),
    session: Session = Depends(get_session),
    clock: Clock = Depends(get_clock),
    provider=Depends(get_forecast_provider),
):
    p = coverage_svc.resolve_period(session, period, clock.now())
    return svc.forecast_for_period(session, provider, p, clock=clock)


@router.post("/forecasts/refresh", response_model=ForecastRefreshOut)
def refresh_forecast(
    period: str | None = Query(default=None),
    session: Session = Depends(get_session),
    clock: Clock = Depends(get_clock),
    provider=Depends(get_forecast_provider),
):
    """Recompute the provider's cached model run now (model selection + future), then report it.

    Changes no records: it only replaces derived, in-memory forecast state. Providers without a model
    cache (the placeholder) answer `refreshed: false`."""
    p = coverage_svc.resolve_period(session, period, clock.now())
    name = getattr(provider, "name", type(provider).__name__)
    if not callable(getattr(provider, "refresh", None)):
        return {"provider": name, "refreshed": False, "reason": "this provider has no model cache to refresh",
                "period": p.id}
    from app.providers.forecasting_pkg import run_summary

    return run_summary(name, provider.refresh(p.id), getattr(provider, "last_error", None))


@router.post("/forecasts/snapshots", response_model=ForecastSnapshotOut, status_code=201)
def create_snapshot(
    period: str | None = Query(default=None),
    session: Session = Depends(get_session),
    clock: Clock = Depends(get_clock),
    ids: IdFactory = Depends(get_ids),
    provider=Depends(get_forecast_provider),
    actor: Actor = Depends(require_role("droid_agent", *FINANCE_ROLES)),
):
    """Persist the current forecast so a proposal or decision can cite exactly what it relied on."""
    p = coverage_svc.resolve_period(session, period, clock.now())
    snap = svc.snapshot(session, svc.forecast_for_period(session, provider, p, clock=clock), clock=clock, ids=ids)
    session.commit()
    return svc.snapshot_out(snap)


@router.get("/forecasts/snapshots/{snapshot_id}", response_model=ForecastSnapshotOut)
def get_snapshot(snapshot_id: str, session: Session = Depends(get_session)):
    return svc.snapshot_out(svc.get_snapshot(session, snapshot_id))


@router.get("/overview", response_model=Overview)
def get_overview(
    period: str | None = Query(default=None),
    session: Session = Depends(get_session),
    clock: Clock = Depends(get_clock),
    provider=Depends(get_forecast_provider),
):
    p = coverage_svc.resolve_period(session, period, clock.now())
    return overview_svc.overview(session, p, provider, clock=clock)
