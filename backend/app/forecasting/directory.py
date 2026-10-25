"""Read-only directory projection for the explicitly configured forecast demo."""

from __future__ import annotations

from app.db.models import Person


def snapshot_people(snapshot: dict) -> list[Person]:
    """Use known effective membership; unresolved membership stays unattributed.

    These transient rows are never added to a session. The native seed directory
    and ledger retain their original identities, and absent contact details are
    not inferred from fixture names.
    """
    at = snapshot["information_cutoff"][:10]
    known_teams = {team["id"] for team in snapshot.get("teams", [])}
    result = []
    for row in snapshot.get("people", []):
        teams = {
            membership["team_id"] for membership in snapshot.get("memberships", [])
            if membership["person_id"] == row["id"]
            and membership["effective_from"] <= at
            and (not membership.get("effective_to") or at < membership["effective_to"])
        }
        team = next(iter(teams)) if len(teams) == 1 else "unattributed"
        result.append(Person(
            id=row["id"], team_id=team if team in known_teams else "unattributed", name=row["name"],
            role=row.get("role"), email=row.get("email"),
            primary_tool=row.get("primary_tool", row.get("primaryTool")),
            integrations=list(row.get("integrations") or []),
            is_simulated=bool(snapshot.get("is_synthetic")), active=row.get("active", True),
        ))
    return result
