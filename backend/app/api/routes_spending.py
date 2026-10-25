"""Spending summary and record drill-down. Never depends on the forecast provider."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_clock
from app.core.clock import Clock
from app.db.session import get_session
from app.schemas.spending import SpendRecordList, SpendSummary
from app.services import coverage as coverage_svc
from app.services import spending as svc

router = APIRouter(prefix="/api", tags=["spending"])


@router.get("/spend/summary", response_model=SpendSummary)
def spend_summary(
    period: str | None = Query(default=None),
    session: Session = Depends(get_session),
    clock: Clock = Depends(get_clock),
):
    p = coverage_svc.resolve_period(session, period, clock.now())
    return svc.spend_summary(session, p, clock=clock)


@router.get("/spend/records", response_model=SpendRecordList)
def spend_records(
    period: str | None = Query(default=None),
    team: str | None = Query(default=None, description="team id, or 'unattributed' for unmapped records"),
    value_kind: str | None = Query(default=None),
    cost_category: str | None = Query(default=None),
    batch: str | None = Query(default=None),
    person: str | None = Query(default=None, description="person id; team-level records have none"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=500, ge=1, le=svc.MAX_RECORD_PAGE),
    session: Session = Depends(get_session),
    clock: Clock = Depends(get_clock),
):
    p = coverage_svc.resolve_period(session, period, clock.now())
    return svc.list_records(session, p, team=team, value_kind=value_kind, cost_category=cost_category,
                            batch=batch, person=person, offset=offset, limit=limit)
