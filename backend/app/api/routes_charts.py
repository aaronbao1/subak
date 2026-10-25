"""Read-only chart specs (Vega-Lite v5) built from backend data. No UI code lives in the backend."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_clock, get_forecast_provider
from app.core.clock import Clock
from app.db.session import get_session
from app.schemas.charts import ChartKindList, ChartSpecOut
from app.services import charts as svc

router = APIRouter(prefix="/api", tags=["charts"])


@router.get("/charts", response_model=ChartKindList)
def list_chart_kinds():
    """Chart kinds, their metrics and defaults."""
    return svc.chart_kinds()


@router.get("/charts/{kind}", response_model=ChartSpecOut)
def get_chart(
    kind: str,
    team: str | None = Query(default=None, min_length=1, max_length=100),
    metric: str | None = Query(default=None, min_length=1, max_length=50),
    period: str | None = Query(default=None),
    session: Session = Depends(get_session),
    clock: Clock = Depends(get_clock),
    provider=Depends(get_forecast_provider),
):
    """A Vega-Lite v5 spec with the data inline, labeled with value kinds and simulated data. Writes nothing
    (a projection chart does not persist a forecast snapshot)."""
    return svc.build_chart(session, kind, team=team, metric=metric, period_id=period, provider=provider,
                           clock=clock)
