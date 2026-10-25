"""People directory (read-only)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.errors import DomainError
from app.db.models import Team
from app.db.session import get_session
from app.schemas.people import PersonOut
from app.services import people as svc

router = APIRouter(prefix="/api", tags=["people"])


@router.get("/people", response_model=list[PersonOut])
def list_people(team: str | None = Query(default=None), session: Session = Depends(get_session)):
    if team is not None and session.get(Team, team) is None:
        raise DomainError("validation_failed", 422, "invalid people filter",
                          {"reasons": [{"code": "unknown_team", "message": f"unknown team {team!r}"}]})
    return [svc.person_out(p) for p in svc.list_people(session, team)]


@router.get("/people/{person_id}", response_model=PersonOut)
def get_person(person_id: str, session: Session = Depends(get_session)):
    return svc.person_out(svc.get_person(session, person_id))
