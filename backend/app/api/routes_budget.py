"""Current internal budget state and its version history."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_clock
from app.core.clock import Clock
from app.db.session import get_session
from app.schemas.budget import BudgetHistory, BudgetState
from app.services import budget as svc

router = APIRouter(prefix="/api", tags=["budget"])


@router.get("/budget", response_model=BudgetState)
def get_budget(
    period: str | None = Query(default=None),
    session: Session = Depends(get_session),
    clock: Clock = Depends(get_clock),
):
    p, env = svc.resolve_envelope(session, period, clock)
    return svc.budget_state(session, p, env)


@router.get("/budget/history", response_model=BudgetHistory)
def get_budget_history(
    period: str | None = Query(default=None),
    session: Session = Depends(get_session),
    clock: Clock = Depends(get_clock),
):
    p, env = svc.resolve_envelope(session, period, clock)
    return svc.history(session, p, env)
