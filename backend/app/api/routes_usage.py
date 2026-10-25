"""Bounded observed usage; shared native and compatibility payloads."""

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_clock
from app.core.clock import Clock
from app.db.session import get_session
from app.schemas.usage import DailyUsageResponse, ScopeType
from app.services.usage import daily_usage

router = APIRouter(prefix="/usage", tags=["usage"])


@router.get("/daily", response_model=DailyUsageResponse)
def usage_daily(
    start_date: date,
    end_date_exclusive: date,
    scope_type: ScopeType = Query(default="company"),
    scope_id: str | None = Query(default=None),
    provider: str | None = Query(default=None),
    model: str | None = Query(default=None),
    session: Session = Depends(get_session),
    clock: Clock = Depends(get_clock),
):
    return daily_usage(session, scope_type=scope_type, scope_id=scope_id, start_date=start_date,
                       end_date_exclusive=end_date_exclusive, provider=provider, model=model, clock=clock)
