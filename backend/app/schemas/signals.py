"""Relevant company context: interpreted signals with verified citations (design.md §3.10, §4)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from app.schemas.common import InModel, OutModel

ChangeType = Literal["expansion", "reduction", "continuation", "timing_shift", "other"]
SignalStatus = Literal["current", "superseded", "conflicting", "informal", "cancelled"]
Producer = Literal["droid_fake", "droid_sdk", "finance"]


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
