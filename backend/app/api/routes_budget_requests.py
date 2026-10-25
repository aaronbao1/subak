"""Budget request intake and assessment-backed native allocation drafts."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.intake_actors import default_dashboard_actor
from app.api.deps import get_clock, get_forecast_provider, get_ids
from app.core.actors import FINANCE_ROLES, Actor, require_role
from app.core.clock import Clock, IdFactory
from app.db.session import get_session
from app.schemas.budget_requests import (BudgetRequestCreate, BudgetRequestDraft, BudgetRequestDraftOut,
                                        BudgetRequestList, BudgetRequestOut)
from app.services import budget_requests as svc
from app.services import proposals as proposal_svc

def build_router(prefix: str, actor_dependency):
    router = APIRouter(prefix=prefix, tags=["budget requests"])


    @router.get("", response_model=BudgetRequestList)
    def list_budget_requests(session: Session = Depends(get_session), provider=Depends(get_forecast_provider),
                             clock: Clock = Depends(get_clock)):
        return {"items": svc.list_requests(session, provider=provider, clock=clock)}


    @router.post("", response_model=BudgetRequestOut, status_code=201)
    def create_budget_request(body: BudgetRequestCreate, session: Session = Depends(get_session),
                              actor: Actor = Depends(actor_dependency),
                              provider=Depends(get_forecast_provider), clock: Clock = Depends(get_clock),
                              ids: IdFactory = Depends(get_ids)):
        row, replayed = svc.create_request(session, body, actor=actor, clock=clock, ids=ids)
        out = BudgetRequestOut.model_validate(svc.request_out(session, row, provider=provider, clock=clock))
        return JSONResponse(status_code=200 if replayed else 201, content=out.model_dump(mode="json"))


    @router.get("/{request_id}", response_model=BudgetRequestOut)
    def get_budget_request(request_id: str, session: Session = Depends(get_session),
                           provider=Depends(get_forecast_provider), clock: Clock = Depends(get_clock)):
        return svc.request_out(session, svc.get_request(session, request_id), provider=provider, clock=clock)


    @router.post("/{request_id}/draft", response_model=BudgetRequestDraftOut, status_code=201)
    def create_budget_request_draft(request_id: str, body: BudgetRequestDraft,
                                    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
                                    session: Session = Depends(get_session),
                                    actor: Actor = Depends(actor_dependency),
                                    provider=Depends(get_forecast_provider), clock: Clock = Depends(get_clock),
                                    ids: IdFactory = Depends(get_ids)):
        row = svc.get_request(session, request_id)
        proposal, replayed = svc.create_draft(session, row, body, actor=actor, provider=provider,
                                              idempotency_key=idempotency_key, clock=clock, ids=ids)
        out = BudgetRequestDraftOut.model_validate({
            "request": svc.request_out(session, row, provider=provider, clock=clock),
            "proposal": proposal_svc.proposal_out(session, proposal),
        })
        return JSONResponse(status_code=200 if replayed else 201, content=out.model_dump(mode="json"))
    return router


router = build_router("/api/budget-requests", require_role(*FINANCE_ROLES))
compat_router = build_router("/compat/api/budget-requests", default_dashboard_actor)
