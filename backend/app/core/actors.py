"""Demo identity from headers. NOT authentication: authority rules are enforced, identity is simulated."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from fastapi import Header

from app.core.errors import DomainError

ROLES = ("finance_approver", "finance_analyst", "droid_agent", "importer")
FINANCE_ROLES = ("finance_approver", "finance_analyst")


@dataclass(frozen=True)
class Actor:
    id: str
    role: str


def get_actor(
    x_actor_id: str | None = Header(default=None),
    x_actor_role: str | None = Header(default=None),
) -> Actor:
    actor_id = (x_actor_id or "").strip()
    role = (x_actor_role or "").strip()
    if not actor_id or not role:
        raise DomainError(
            "actor_required",
            401,
            "X-Actor-Id and X-Actor-Role headers are required (demo identity, not authentication)",
        )
    if role not in ROLES:
        raise DomainError("unknown_role", 403, f"unknown role {role!r}", {"allowed_roles": list(ROLES)})
    return Actor(id=actor_id, role=role)


def require_role(*roles: str) -> Callable[..., Actor]:
    """Dependency factory: the caller's role must be one of `roles`, else 403 `role_forbidden`."""

    def _dep(
        x_actor_id: str | None = Header(default=None),
        x_actor_role: str | None = Header(default=None),
    ) -> Actor:
        actor = get_actor(x_actor_id, x_actor_role)
        if actor.role not in roles:
            raise DomainError(
                "role_forbidden",
                403,
                f"role {actor.role!r} may not perform this action",
                {"role": actor.role, "allowed_roles": list(roles)},
            )
        return actor

    return _dep
