"""Teams and explicit team mappings."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_clock, get_ids
from app.core.actors import FINANCE_ROLES, Actor, require_role
from app.core.clock import Clock, IdFactory
from app.db.session import get_session
from app.schemas.imports import TeamMappingIn, TeamMappingOut, TeamMappingUpsertResult, TeamOut
from app.services import teams as svc

router = APIRouter(prefix="/api", tags=["teams"])


@router.get("/teams", response_model=list[TeamOut])
def list_teams(session: Session = Depends(get_session)):
    return svc.list_teams(session)


@router.get("/team-mappings", response_model=list[TeamMappingOut])
def list_mappings(session: Session = Depends(get_session)):
    return svc.list_mappings(session)


@router.put("/team-mappings", response_model=TeamMappingUpsertResult)
def upsert_mapping(
    body: TeamMappingIn,
    session: Session = Depends(get_session),
    actor: Actor = Depends(require_role(*FINANCE_ROLES)),
    clock: Clock = Depends(get_clock),
    ids: IdFactory = Depends(get_ids),
):
    mapping, changed = svc.upsert_mapping(
        session,
        source_kind=body.source_kind,
        source_account=body.source_account,
        team_id=body.team_id,
        effective_from=body.effective_from,
        actor_id=actor.id,
        clock=clock,
        ids=ids,
    )
    session.commit()
    return {"mapping": mapping, "reattributed_records": changed}
