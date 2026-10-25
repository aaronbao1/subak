"""Direct allocation planning produces native proposals and durable retry receipts."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import APIRouter, Depends, Header, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps import get_clock, get_ids
from app.api.intake_actors import default_dashboard_actor
from app.core.actors import FINANCE_ROLES, Actor, require_role
from app.core.clock import Clock, IdFactory
from app.db.session import get_session
from app.schemas.allocation_drafts import AllocationDraftCreate, AllocationState
from app.schemas.proposals import ProposalOut
from app.services import allocation_drafts as svc
from app.services import proposals as proposal_svc


def _build_router(prefix: str, actor_dependency: Callable[..., Actor]) -> APIRouter:
    routes = APIRouter(prefix=prefix, tags=["allocation planning"])

    @routes.get("/allocation-state", response_model=AllocationState)
    def get_allocation_state(
        period: str | None = Query(default=None),
        session: Session = Depends(get_session),
        clock: Clock = Depends(get_clock),
    ):
        return svc.allocation_state(session, period_id=period, clock=clock)

    @routes.post("/allocation-drafts", response_model=ProposalOut, status_code=201)
    def create_allocation_draft(
        body: AllocationDraftCreate,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        session: Session = Depends(get_session),
        actor: Actor = Depends(actor_dependency),
        clock: Clock = Depends(get_clock),
        ids: IdFactory = Depends(get_ids),
    ):
        proposal, replayed = svc.create_draft(session, body, actor=actor, idempotency_key=idempotency_key,
                                              clock=clock, ids=ids)
        out = ProposalOut.model_validate(proposal_svc.proposal_out(session, proposal))
        if replayed:
            return JSONResponse(status_code=200, content=out.model_dump(mode="json"))
        return out

    @routes.get("/allocation-drafts/{idempotency_key}", response_model=ProposalOut)
    def recover_allocation_draft(
        idempotency_key: str,
        session: Session = Depends(get_session),
        actor: Actor = Depends(actor_dependency),
    ):
        return proposal_svc.proposal_out(session, svc.get_submission(session, idempotency_key, actor=actor))

    return routes


router = _build_router("/api", require_role(*FINANCE_ROLES))
compat_router = _build_router("/compat/api", default_dashboard_actor)
