"""Finance decisions and decision history (design.md §3.8, §4)."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field, field_validator

from app.schemas.budget import BudgetState
from app.schemas.common import InModel, OutModel
from app.schemas.proposals import BudgetFigures, EvidenceOut, EvidenceRef, LineOut


class DecisionCreate(InModel):
    outcome: Literal["approve", "reject"]
    rationale: Annotated[str, Field(max_length=10_000)]
    evidence_refs: list[EvidenceRef] = Field(default_factory=list, max_length=100)

    @field_validator("rationale")
    @classmethod
    def _rationale_required(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("rationale_required: a decision must say why")
        return v.strip()


class ActorOut(OutModel):
    id: str
    role: str


class DecisionOut(OutModel):
    id: str
    proposal_id: str
    action_type: Literal["addition", "transfer"]
    outcome: Literal["approved_applied", "rejected"]
    actor: ActorOut
    requester: ActorOut
    rationale: str
    evidence_refs: list[EvidenceOut]
    proposal_evidence_refs: list[EvidenceOut]
    decided_at: datetime
    from_version: int
    to_version: int | None
    before: BudgetFigures
    after: BudgetFigures | None  # None on rejection: nothing changed
    lines: list[LineOut]
    replayed: bool = False
    budget_state: BudgetState  # current saved state when this response was produced


class DecisionEventOut(OutModel):
    id: str
    proposal_id: str
    event: Literal["stale_rejected", "self_approval_blocked", "role_blocked"]
    actor_id: str
    details: dict
    at: datetime
