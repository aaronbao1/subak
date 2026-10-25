"""Team mapping resolution: source account -> team, or unattributed (never guessed)."""

from __future__ import annotations

import bisect
from collections import defaultdict
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import Clock, IdFactory
from app.core.errors import DomainError
from app.db.models import Person, Team, TeamMapping, UsageRecord


class MappingResolver:
    """Resolves (source_account, occurred date) -> team_id using the mapping whose
    effective_from is the latest one on or before that date. No mapping -> None (unattributed)."""

    def __init__(self, session: Session, source_kind: str) -> None:
        rows = session.scalars(
            select(TeamMapping).where(TeamMapping.source_kind == source_kind).order_by(TeamMapping.effective_from)
        ).all()
        self._by_account: dict[str, list[tuple[date, str]]] = defaultdict(list)
        for m in rows:
            self._by_account[m.source_account].append((m.effective_from, m.team_id))

    def resolve(self, source_account: str | None, occurred_at: datetime) -> str | None:
        if not source_account:
            return None
        entries = self._by_account.get(source_account)
        if not entries:
            return None
        day = occurred_at.date()
        idx = bisect.bisect_right([d for d, _ in entries], day) - 1
        return entries[idx][1] if idx >= 0 else None


def list_teams(session: Session) -> list[Team]:
    return list(session.scalars(select(Team).order_by(Team.id)))


def list_mappings(session: Session) -> list[TeamMapping]:
    return list(
        session.scalars(
            select(TeamMapping).order_by(TeamMapping.source_kind, TeamMapping.source_account, TeamMapping.effective_from)
        )
    )


def reresolve_records(session: Session, source_kind: str, source_account: str) -> int:
    """Re-attribute every record of one source account after a mapping change. Returns how many changed.

    A record keeps its person only if that person is on the new team; otherwise it becomes team-level."""
    resolver = MappingResolver(session, source_kind)
    person_team: dict[str, str] = {}
    changed = 0
    records = session.scalars(
        select(UsageRecord).where(
            UsageRecord.source_kind == source_kind, UsageRecord.source_account == source_account
        )
    )
    for rec in records:
        team = resolver.resolve(rec.source_account, rec.occurred_at)
        if team != rec.team_id:
            rec.team_id = team
            if rec.person_id is not None:
                if rec.person_id not in person_team:
                    person = session.get(Person, rec.person_id)
                    person_team[rec.person_id] = person.team_id if person else ""
                if team is None or person_team[rec.person_id] != team:
                    rec.person_id = None
            changed += 1
    return changed


def upsert_mapping(
    session: Session,
    *,
    source_kind: str,
    source_account: str,
    team_id: str,
    effective_from: date,
    actor_id: str,
    clock: Clock,
    ids: IdFactory,
) -> tuple[TeamMapping, int]:
    team = session.get(Team, team_id)
    if team is None or not team.active:
        raise DomainError("unknown_team", 422, f"unknown or inactive team {team_id!r}", {"team_id": team_id})
    mapping = session.scalars(
        select(TeamMapping).where(
            TeamMapping.source_kind == source_kind,
            TeamMapping.source_account == source_account,
            TeamMapping.effective_from == effective_from,
        )
    ).one_or_none()
    if mapping is None:
        mapping = TeamMapping(
            id=ids.new_id("map_"),
            created_at=clock.now(),
            source_kind=source_kind,
            source_account=source_account,
            team_id=team_id,
            effective_from=effective_from,
            created_by=actor_id,
        )
        session.add(mapping)
    else:
        mapping.team_id = team_id
        mapping.created_by = actor_id
    session.flush()
    return mapping, reresolve_records(session, source_kind, source_account)
