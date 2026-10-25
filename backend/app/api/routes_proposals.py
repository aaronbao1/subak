"""Proposal drafting, review, rebase/revise, and the finance decision endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Header, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps import get_clock, get_ids
from app.core.actors import FINANCE_ROLES, Actor, get_actor, require_role
from app.core.clock import Clock, IdFactory
from app.db.session import get_session
from app.schemas.decisions import DecisionCreate, DecisionOut
from app.schemas.proposals import ProposalCreate, ProposalOut, RebaseIn
from app.services import decisions as decision_svc
from app.services import proposals as svc

router = APIRouter(prefix="/api", tags=["proposals"])


@router.post("/proposals", response_model=ProposalOut, status_code=201)
def create_proposal(
    body: ProposalCreate = Body(...),
    session: Session = Depends(get_session),
    actor: Actor = Depends(require_role(*svc.DRAFTING_ROLES)),
    clock: Clock = Depends(get_clock),
    ids: IdFactory = Depends(get_ids),
):
    p = svc.create_proposal(session, body, actor=actor, clock=clock, ids=ids)
    session.commit()
    return svc.proposal_out(session, p)


@router.get("/proposals", response_model=list[ProposalOut])
def list_proposals(status: str | None = Query(default=None), session: Session = Depends(get_session)):
    return [svc.proposal_out(session, p) for p in svc.list_proposals(session, status)]


@router.get("/proposals/{proposal_id}", response_model=ProposalOut)
def get_proposal(proposal_id: str, session: Session = Depends(get_session)):
    return svc.proposal_out(session, svc.get_proposal(session, proposal_id))


@router.post("/proposals/{proposal_id}/rebase", response_model=ProposalOut, status_code=201)
def rebase_proposal(
    proposal_id: str,
    body: RebaseIn | None = Body(default=None),
    session: Session = Depends(get_session),
    actor: Actor = Depends(require_role(*svc.DRAFTING_ROLES)),
    clock: Clock = Depends(get_clock),
    ids: IdFactory = Depends(get_ids),
):
    p = svc.rebase(session, proposal_id, body or RebaseIn(), actor=actor, clock=clock, ids=ids)
    session.commit()
    return svc.proposal_out(session, p)


@router.post("/proposals/{proposal_id}/revise", response_model=ProposalOut, status_code=201)
def revise_proposal(
    proposal_id: str,
    body: ProposalCreate = Body(...),
    session: Session = Depends(get_session),
    actor: Actor = Depends(require_role(*FINANCE_ROLES)),
    clock: Clock = Depends(get_clock),
    ids: IdFactory = Depends(get_ids),
):
    p = svc.revise(session, proposal_id, body, actor=actor, clock=clock, ids=ids)
    session.commit()
    return svc.proposal_out(session, p)


@router.post("/proposals/{proposal_id}/decision", response_model=DecisionOut, status_code=201)
def decide_proposal(
    proposal_id: str,
    body: DecisionCreate,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    session: Session = Depends(get_session),
    actor: Actor = Depends(get_actor),  # role is checked (and blocked attempts recorded) in the service
    clock: Clock = Depends(get_clock),
    ids: IdFactory = Depends(get_ids),
):
    decision, replayed = decision_svc.decide(
        session, proposal_id, body, actor=actor, idempotency_key=idempotency_key, clock=clock, ids=ids
    )
    out = DecisionOut.model_validate(decision_svc.decision_out(session, decision, replayed=replayed))
    if replayed:
        return JSONResponse(status_code=200, content=out.model_dump(mode="json"))
    return out
