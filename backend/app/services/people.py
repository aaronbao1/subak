"""People directory (frontend-integration-design §2.1).

A person is the only way spend is attributed below team level: an export's `user_email` is matched
against this directory, and only for a person on the team the mapping already resolved.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.errors import DomainError
from app.db.models import INTEGRATIONS, PERSON_ID_PATTERN, Person, Team

_ID_RE = re.compile(PERSON_ID_PATTERN)
MAX_EMAIL = 320


def normalize_email(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip().lower()
    return text or None


def list_people(session: Session, team: str | None = None, *, include_inactive: bool = False) -> list[Person]:
    q = select(Person)
    if team is not None:
        q = q.where(Person.team_id == team)
    if not include_inactive:
        q = q.where(Person.active.is_(True))
    return list(session.scalars(q.order_by(Person.team_id, Person.name, Person.id)))


def get_person(session: Session, person_id: str) -> Person:
    person = session.get(Person, person_id)
    if person is None:
        raise DomainError("not_found", 404, f"person {person_id!r} not found")
    return person


def people_by_email(session: Session) -> dict[str, Person]:
    """Active people keyed by lowercase email (the import-time directory)."""
    return {p.email: p for p in session.scalars(select(Person).where(Person.active.is_(True))) if p.email}


def person_out(p: Person) -> dict[str, Any]:
    return {
        "id": p.id, "team": p.team_id, "name": p.name, "role": p.role, "email": p.email,
        "primary_tool": p.primary_tool, "integrations": list(p.integrations or []),
        "is_simulated": p.is_simulated, "active": p.active,
    }


def _validate(session: Session, row: Mapping[str, Any], seen_ids: set[str], seen_emails: set[str]) -> list[dict]:
    reasons: list[dict] = []
    pid = row.get("id")
    if not isinstance(pid, str) or not _ID_RE.match(pid) or pid == "unattributed":
        reasons.append({"code": "invalid_person_id", "message": f"person id {pid!r} must be a lowercase slug"})
    elif pid in seen_ids or session.get(Person, pid) is not None:
        reasons.append({"code": "duplicate_person", "message": f"person {pid!r} already exists"})
    team = session.get(Team, row.get("team"))
    if team is None or not team.active:
        reasons.append({"code": "unknown_team", "message": f"unknown or inactive team {row.get('team')!r}"})
    if not str(row.get("name") or "").strip():
        reasons.append({"code": "name_required", "message": "name is required"})
    email = normalize_email(row.get("email"))
    if email is not None:
        if "@" not in email or len(email) > MAX_EMAIL:
            reasons.append({"code": "invalid_email", "message": f"invalid email {email!r}"})
        elif email in seen_emails or session.scalar(select(Person.id).where(Person.email == email)):
            reasons.append({"code": "duplicate_email", "message": f"email {email!r} is already used"})
    bad = [i for i in row.get("integrations") or [] if i not in INTEGRATIONS]
    if bad:
        reasons.append({"code": "unknown_integration", "message": f"integrations must be from {INTEGRATIONS}: {bad}"})
    return reasons


def create_people(session: Session, rows: Iterable[Mapping[str, Any]], *, clock: Clock) -> list[Person]:
    """Validate and add people (all-or-nothing). Rows: id, team, name, role?, email?, primary_tool?,
    integrations?, is_simulated?."""
    rows = list(rows)
    reasons: list[dict] = []
    seen_ids: set[str] = set()
    seen_emails: set[str] = set()
    for row in rows:
        reasons += _validate(session, row, seen_ids, seen_emails)
        seen_ids.add(row.get("id"))  # type: ignore[arg-type]
        if (email := normalize_email(row.get("email"))) is not None:
            seen_emails.add(email)
    if reasons:
        raise DomainError("validation_failed", 422, "invalid people", {"reasons": reasons})
    now = clock.now()
    people = [
        Person(
            id=row["id"], team_id=row["team"], name=str(row["name"]).strip(), role=row.get("role"),
            email=normalize_email(row.get("email")), primary_tool=row.get("primary_tool"),
            integrations=list(dict.fromkeys(row.get("integrations") or [])),
            is_simulated=bool(row.get("is_simulated", False)), active=True, created_at=now,
        )
        for row in rows
    ]
    session.add_all(people)
    session.flush()
    return people
