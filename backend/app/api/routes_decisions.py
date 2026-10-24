"""Decision history: who decided, when, why, on what evidence, and what changed."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.schemas.decisions import DecisionEventOut, DecisionOut
from app.services import decisions as svc

router = APIRouter(prefix="/api", tags=["decisions"])


@router.get("/decisions", response_model=list[DecisionOut])
def list_decisions(proposal_id: str | None = Query(default=None), session: Session = Depends(get_session)):
    return [svc.decision_out(session, d) for d in svc.list_decisions(session, proposal_id)]


@router.get("/decisions/{decision_id}", response_model=DecisionOut)
def get_decision(decision_id: str, session: Session = Depends(get_session)):
    return svc.decision_out(session, svc.get_decision(session, decision_id))


@router.get("/decision-events", response_model=list[DecisionEventOut])
def list_decision_events(proposal_id: str | None = Query(default=None), session: Session = Depends(get_session)):
    """Blocked attempts (stale, self-approval, wrong role). They are not decisions and changed nothing."""
    return svc.list_events(session, proposal_id)
