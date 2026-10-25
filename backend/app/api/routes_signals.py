"""Context signals: verified create, list/read with citation currency, finance curation, guarded delete."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.orm import Session

from app.api.deps import get_clock, get_ids
from app.core.actors import FINANCE_ROLES, Actor, require_role
from app.core.clock import Clock, IdFactory
from app.db.session import get_session
from app.schemas.signals import ContextSignalIn, ContextSignalOut, ContextSignalPatch, SignalList
from app.services import signals as svc

router = APIRouter(prefix="/api", tags=["signals"])


@router.get("/signals", response_model=SignalList)
def list_signals(
    team: str | None = Query(default=None, description="team id, or 'none' for company-wide signals"),
    status: str | None = Query(default=None),
    project: str | None = Query(default=None),
    scope: Literal["person", "team", "company"] | None = Query(default=None),
    person: str | None = Query(default=None, description="person id: signals that name this person"),
    include_company: bool = Query(default=False, description="with team: also list company-wide signals"),
    session: Session = Depends(get_session),
):
    items = [svc.signal_out(session, s) for s in svc.list_signals(
        session, team=team, status=status, project=project, scope=scope, person=person,
        include_company=include_company)]
    return {"count": len(items), "items": items}


@router.get("/signals/{signal_id}", response_model=ContextSignalOut)
def get_signal(signal_id: str, session: Session = Depends(get_session)):
    return svc.signal_out(session, svc.get_signal(session, signal_id))


@router.post("/signals", response_model=ContextSignalOut, status_code=201)
def create_signal(
    body: ContextSignalIn,
    request: Request,
    session: Session = Depends(get_session),
    actor: Actor = Depends(require_role("droid_agent", *FINANCE_ROLES)),
    clock: Clock = Depends(get_clock),
    ids: IdFactory = Depends(get_ids),
):
    sig, corrected = svc.create_signal(
        session, body, actor=actor, runner_kind=request.app.state.settings.droid_runner, clock=clock, ids=ids
    )
    session.commit()
    return svc.signal_out(session, sig, corrected)


@router.patch("/signals/{signal_id}", response_model=ContextSignalOut)
def patch_signal(
    signal_id: str,
    body: ContextSignalPatch,
    session: Session = Depends(get_session),
    actor: Actor = Depends(require_role(*FINANCE_ROLES)),
    clock: Clock = Depends(get_clock),
):
    sig = svc.patch_signal(session, signal_id, body, clock=clock)
    session.commit()
    return svc.signal_out(session, sig)


@router.delete("/signals/{signal_id}", status_code=204)
def delete_signal(
    signal_id: str,
    session: Session = Depends(get_session),
    actor: Actor = Depends(require_role(*FINANCE_ROLES)),
):
    svc.delete_signal(session, signal_id)
    session.commit()
    return Response(status_code=204)
