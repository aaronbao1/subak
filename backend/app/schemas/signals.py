"""Relevant company context: interpreted signals with verified citations (design.md §3.10, §4)."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from app.schemas.common import InModel, OutModel

ChangeType = Literal["expansion", "reduction", "continuation", "timing_shift", "other"]
SignalStatus = Literal["current", "superseded", "conflicting", "informal", "cancelled"]
Producer = Literal["droid_fake", "droid_sdk", "finance"]
# person: one or more named people on one team; team: a team plan; company: every team (team null).
SignalScope = Literal["person", "team", "company"]
# Why usage is expected to move (the frontend `SignalKind`):
# project_deferred (work pushed back), project_accelerated (work moved earlier), model_change (moving to a
# different model), tool_change (moving between tools or billing paths), out_of_office (away for dates),
# onboarding (a new person or seat), steady (continues at the current pace).
SignalKind = Literal["project_deferred", "project_accelerated", "model_change", "tool_change", "out_of_office",
                     "onboarding", "steady"]
MAX_SIGNAL_PEOPLE = 10
_PERSON_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")


class CitationIn(InModel):
    document_id: Annotated[str, Field(min_length=1, max_length=200)]
    # Exact text from the cited document version. Offsets are optional; if missing or wrong, the
    # backend locates the exact quote itself. A quote that does not occur verbatim is rejected.
    quote: Annotated[str, Field(min_length=3, max_length=5000)]
    char_start: Annotated[int, Field(ge=0)] | None = None
    char_end: Annotated[int, Field(ge=1)] | None = None

    @field_validator("quote")
    @classmethod
    def _quote(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("quote must not be blank")
        return v

    @model_validator(mode="after")
    def _span(self) -> "CitationIn":
        if (self.char_start is None) != (self.char_end is None):
            raise ValueError("give both char_start and char_end, or neither")
        if self.char_start is not None and self.char_end <= self.char_start:  # type: ignore[operator]
            raise ValueError("char_end must be greater than char_start")
        return self


class ContextSignalIn(InModel):
    team: str | None = None
    # Scope rules (checked by the signal service, 422 validation_failed with reasons[].code):
    # person -> person_ids required, all active people on one team (team derived when omitted);
    # team -> no person_ids; company -> team null and no person_ids.
    scope: SignalScope = "team"
    person_ids: list[str] = Field(default_factory=list)
    signal_kind: SignalKind | None = None
    title: Annotated[str, Field(min_length=1, max_length=120)] | None = None
    project: Annotated[str, Field(max_length=200)] | None = None
    summary: Annotated[str, Field(min_length=1, max_length=5000)]
    change_type: ChangeType
    applies_from: date | None = None
    applies_to: date | None = None
    status: SignalStatus
    # Required: a planned expansion is context, not a guaranteed event.
    uncertainty: Annotated[str, Field(min_length=1, max_length=5000)]
    citations: list[CitationIn] = Field(min_length=1, max_length=50)
    agent_run_id: str | None = None
    supersedes_signal_id: str | None = None

    @field_validator("summary", "uncertainty")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("must not be blank")
        return v.strip()

    @field_validator("title")
    @classmethod
    def _title(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if not v.strip():
            raise ValueError("title must not be blank")
        return v.strip()

    @field_validator("person_ids")
    @classmethod
    def _person_ids(cls, v: list[str]) -> list[str]:
        out: list[str] = []
        for raw in v:
            pid = str(raw).strip().lower()
            if not _PERSON_ID.match(pid):
                raise ValueError(f"person_ids entries must be person id slugs, got {raw!r}")
            if pid not in out:
                out.append(pid)
        if len(out) > MAX_SIGNAL_PEOPLE:
            raise ValueError(f"at most {MAX_SIGNAL_PEOPLE} person_ids")
        return out

    @model_validator(mode="after")
    def _dates(self) -> "ContextSignalIn":
        if self.applies_from and self.applies_to and self.applies_to < self.applies_from:
            raise ValueError("applies_to must not be before applies_from")
        return self


class ContextSignalPatch(InModel):
    """Finance curation. Content and citations are immutable; record a new signal instead."""

    status: SignalStatus | None = None
    uncertainty: Annotated[str, Field(min_length=1, max_length=5000)] | None = None
    superseded_by_signal_id: str | None = None


class CitationOut(OutModel):
    id: str
    document_id: str
    doc_key: str
    version: int
    title: str
    quote: str
    char_start: int
    char_end: int
    # `superseded` when the cited document version has since been replaced by a newer one.
    citation_currency: Literal["current", "superseded"]
    superseded_by_document_id: str | None
    offsets_corrected: bool = False


class ContextSignalOut(OutModel):
    id: str
    team: str | None
    scope: SignalScope
    person_ids: list[str]
    signal_kind: SignalKind | None
    title: str | None
    project: str | None
    summary: str
    change_type: ChangeType
    applies_from: date | None
    applies_to: date | None
    status: SignalStatus
    uncertainty: str
    produced_by: Producer
    agent_run_id: str | None
    superseded_by_signal_id: str | None
    supersedes_signal_ids: list[str]
    citations: list[CitationOut]
    # True when a `current` signal now rests only on superseded documents: re-check it.
    needs_review: bool
    created_at: datetime


class SignalList(OutModel):
    count: int
    items: list[ContextSignalOut]
