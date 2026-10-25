"""Compat dashboard identity for intake; explicit headers retain native validation."""
from fastapi import Header
from app.core.actors import Actor, get_actor


def default_dashboard_actor(x_actor_id: str | None = Header(default=None),
                            x_actor_role: str | None = Header(default=None)) -> Actor:
    if x_actor_id is None and x_actor_role is None:
        return Actor(id="dashboard-analyst", role="finance_analyst")
    return get_actor(x_actor_id, x_actor_role)
