"""Corpus document API models (design.md §4 'Readable company material')."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Literal

from pydantic import AwareDatetime, Field, field_validator, model_validator

from app.schemas.common import InModel, OutModel
from app.schemas.people import Integration

DocOrigin = Literal["upload", "email_export", "slack_export", "seed"]
DocType = Literal["plan", "update", "correspondence", "note"]
PlanStatus = Literal["approved", "draft", "informal", "cancelled", "n/a"]
_SLUG = re.compile(r"^[a-z0-9][a-z0-9._-]{0,199}$")


def _slugs(values: list[str], field: str) -> list[str]:
    out: list[str] = []
    for v in values:
        s = v.strip().lower()
        if not _SLUG.match(s):
            raise ValueError(f"{field} entries must be lowercase slugs, got {v!r}")
        if s not in out:
            out.append(s)
    return out


class DocumentIn(InModel):
    doc_key: str = Field(min_length=1, max_length=200)
    title: str = Field(min_length=1, max_length=500)
    origin: DocOrigin = "upload"
    doc_type: DocType
    plan_status: PlanStatus = "n/a"
    authored_at: AwareDatetime
    effective_from: date | None = None
    effective_to: date | None = None
    team_tags: list[str] = Field(default_factory=list)
    project_tags: list[str] = Field(default_factory=list)
    author: str | None = Field(default=None, max_length=200)
    # Where the document came from; omitted -> derived from `origin` when shown (frontend-integration §1.1).
    integration: Integration | None = None
    # People the document is about; every id must be an active person (422 unknown_person otherwise).
    person_tags: list[str] = Field(default_factory=list, max_length=50)
    content: str = Field(min_length=1, max_length=1_000_000)
    supersedes_document_id: str | None = None
    supersedes_doc_key: str | None = None
    supersedes_version: int | None = Field(default=None, ge=1)
    is_simulated: bool = False

    @field_validator("doc_key")
    @classmethod
    def _key(cls, v: str) -> str:
        if not _SLUG.match(v):
            raise ValueError("doc_key must be a lowercase slug (a-z, 0-9, . _ -)")
        return v

    @field_validator("title")
    @classmethod
    def _title(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("title must not be blank")
        return v.strip()

    @field_validator("content")
    @classmethod
    def _content(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("content must not be blank")
        return v

    @field_validator("team_tags")
    @classmethod
    def _teams(cls, v: list[str]) -> list[str]:
        return _slugs(v, "team_tags")

    @field_validator("project_tags")
    @classmethod
    def _projects(cls, v: list[str]) -> list[str]:
        return _slugs(v, "project_tags")

    @field_validator("person_tags")
    @classmethod
    def _people(cls, v: list[str]) -> list[str]:
        return _slugs(v, "person_tags")

    @model_validator(mode="after")
    def _checks(self) -> "DocumentIn":
        if self.effective_from and self.effective_to and self.effective_to < self.effective_from:
            raise ValueError("effective_to must not be before effective_from")
        if self.supersedes_document_id and self.supersedes_doc_key:
            raise ValueError("give supersedes_document_id or supersedes_doc_key, not both")
        if self.supersedes_version is not None and not self.supersedes_doc_key:
            raise ValueError("supersedes_version requires supersedes_doc_key")
        return self


class DocRef(OutModel):
    id: str
    doc_key: str
    version: int
    title: str


class SearchMatch(OutModel):
    term: str
    char_start: int
    char_end: int
    text: str
    snippet: str


class DocumentSummary(OutModel):
    id: str
    doc_key: str
    version: int
    title: str
    origin: DocOrigin
    doc_type: DocType
    plan_status: PlanStatus
    authored_at: datetime
    effective_from: date | None
    effective_to: date | None
    team_tags: list[str]
    project_tags: list[str]
    author: str | None
    integration: Integration | None
    person_tags: list[str]
    content_hash: str
    is_simulated: bool
    is_current: bool
    supersedes: DocRef | None
    superseded_by: DocRef | None


class DocumentDetail(DocumentSummary):
    content: str


class DocumentSearchItem(DocumentSummary):
    score: int
    matches: list[SearchMatch]


class DocumentList(OutModel):
    query: str | None
    filters: dict[str, Any]
    count: int
    items: list[DocumentSearchItem]


class DocumentIngestResult(OutModel):
    created: bool
    duplicate_of_version: int | None
    document: DocumentDetail


class DocumentVersions(OutModel):
    doc_key: str
    current_version: int
    versions: list[DocumentSummary]
