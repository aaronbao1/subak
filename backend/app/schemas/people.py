"""People (team members) API models."""

from __future__ import annotations

from typing import Literal

from app.schemas.common import OutModel

Integration = Literal["slack", "asana", "monday", "email", "document"]


class PersonOut(OutModel):
    id: str
    team: str
    name: str
    role: str | None
    email: str | None
    primary_tool: str | None
    integrations: list[Integration]
    is_simulated: bool
    active: bool
