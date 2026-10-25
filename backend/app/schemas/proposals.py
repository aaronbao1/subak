"""Proposed allocation changes: addition to the envelope vs transfer between teams (design.md §3.7, §4).

Amount fields accept raw str/int/float/Decimal on input on purpose: the proposal service parses them
itself so every problem comes back as a named reason code (`float_not_allowed`, `too_many_decimals`,
...) in one `validation_failed` response instead of an opaque schema error.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal, Union

from pydantic import Field, StrictFloat, StrictInt, StrictStr

from app.schemas.common import InModel, MoneyStr, OutModel

RawAmount = Union[StrictStr, StrictInt, StrictFloat, Decimal]

EvidenceKind = Literal["signal", "document", "forecast_snapshot", "spend_summary"]


class EvidenceRef(InModel):
    kind: EvidenceKind
    id: Annotated[str, Field(min_length=1, max_length=200)]
    version: int | None = None
    note: Annotated[str, Field(max_length=1000)] | None = None


class AdditionLineIn(InModel):
    to_team: str
    amount: RawAmount


class TransferLineIn(InModel):
    from_team: str
    to_team: str
    amount: RawAmount


class _ProposalBase(InModel):
    base_version: int
    rationale: Annotated[str, Field(max_length=10_000)]
    evidence_refs: list[EvidenceRef] = Field(default_factory=list, max_length=100)
    period: str | None = None  # defaults to the current planning period
    unit: str | None = None  # defaults to the envelope unit; anything else is `currency_mismatch`
    agent_run_id: str | None = None


class AdditionCreate(_ProposalBase):
    action_type: Literal["addition"]
    envelope_increase: RawAmount
    lines: list[AdditionLineIn] = Field(max_length=100)


class TransferCreate(_ProposalBase):
    action_type: Literal["transfer"]
    # Present only so a transfer that tries to grow the envelope gets a named reason code
    # (`transfer_with_envelope_change`); a transfer can never change the envelope.
    envelope_increase: RawAmount | None = None
    lines: list[TransferLineIn] = Field(max_length=100)


ProposalCreate = Annotated[Union[AdditionCreate, TransferCreate], Field(discriminator="action_type")]


class RebaseIn(InModel):
    rationale: Annotated[str, Field(max_length=10_000)] | None = None  # defaults to the original's


# ---- responses -------------------------------------------------------------------------------


class BudgetFigures(OutModel):
    total: MoneyStr
    allocations: dict[str, MoneyStr]


class LineOut(OutModel):
    from_team: str | None  # None for additions: new money has no source team
    to_team: str
    amount: MoneyStr


class Requester(OutModel):
    id: str
    role: str


class WarningOut(OutModel):
    code: str
    message: str
    team: str | None = None


class EvidenceOut(OutModel):
    kind: str
    id: str
    version: int | None = None
    note: str | None = None


class BlockedAttemptOut(OutModel):
    id: str
    event: str
    actor_id: str
    details: dict
    at: datetime


class ProposalOut(OutModel):
    id: str
    period: str
    unit: str
    action_type: Literal["addition", "transfer"]
    status: Literal["pending_review", "applied", "rejected", "stale", "revised"]
    base_version: int
    current_version: int
    # True when the proposal is still pending but the budget moved on since it was drafted:
    # it can no longer be applied and must be rebased and reviewed again.
    is_stale: bool
    envelope_increase: MoneyStr
    lines: list[LineOut]
    before: BudgetFigures
    after: BudgetFigures
    deltas: dict[str, MoneyStr]
    rationale: str
    evidence_refs: list[EvidenceOut]
    warnings: list[WarningOut]
    requester: Requester
    origin: Literal["droid_run", "finance_manual"]
    agent_run_id: str | None
    revises_proposal_id: str | None
    rebased_from_proposal_id: str | None
    replaced_by_proposal_id: str | None
    decision_id: str | None
    blocked_attempts: list[BlockedAttemptOut]
    created_at: datetime
    updated_at: datetime
