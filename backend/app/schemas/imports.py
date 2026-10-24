"""Import batch, team mapping and coverage API models."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import Field

from app.schemas.common import CoverageStatus, DataLabels, InModel, MoneyStr, OutModel


class ImportIssue(OutModel):
    code: str
    message: str
    count: int
    rows: list[int]


class ImportResult(OutModel):
    id: str
    source_kind: str
    source_label: str | None
    filename: str | None
    content_hash: str
    status: Literal["imported", "duplicate", "failed"]
    duplicate_of_batch_id: str | None
    record_count: int
    skipped_duplicate_records: int
    unmapped_record_count: int
    unmapped_accounts: dict[str, int]
    spend_added: MoneyStr
    unit: Literal["USD"] = "USD"
    value_kind_default: str
    imported_by: str
    created_at: datetime
    stats: dict[str, int]
    errors: list[ImportIssue]
    warnings: list[ImportIssue]

    @classmethod
    def from_batch(cls, batch: Any) -> "ImportResult":
        details = batch.error_details or {}
        return cls(
            id=batch.id,
            source_kind=batch.source_kind,
            source_label=batch.source_label,
            filename=batch.filename,
            content_hash=batch.content_hash,
            status=batch.status,
            duplicate_of_batch_id=batch.duplicate_of_batch_id,
            record_count=batch.record_count,
            skipped_duplicate_records=batch.skipped_duplicate_records,
            unmapped_record_count=batch.unmapped_record_count,
            unmapped_accounts=details.get("unmapped_accounts", {}),
            spend_added=details.get("spend_added", "0.00"),
            value_kind_default=batch.value_kind_default,
            imported_by=batch.imported_by,
            created_at=batch.created_at,
            stats=details.get("stats", {}),
            errors=details.get("errors", []),
            warnings=details.get("warnings", []),
        )


class TeamOut(OutModel):
    id: str
    name: str
    active: bool


class TeamMappingIn(InModel):
    source_kind: str = Field(min_length=1, max_length=64)
    source_account: str = Field(min_length=1, max_length=200)
    team_id: str = Field(min_length=1, max_length=64)
    effective_from: date


class TeamMappingOut(OutModel):
    id: str
    source_kind: str
    source_account: str
    team_id: str
    effective_from: date
    created_by: str


class TeamMappingUpsertResult(OutModel):
    mapping: TeamMappingOut
    reattributed_records: int


class PeriodOut(OutModel):
    id: str
    label: str
    starts_on: date
    ends_on: date


class TeamCoverage(OutModel):
    team: str
    status: CoverageStatus
    record_count: int
    unmapped_records: int
    counter_resets: int
    spend_record_count: int  # records that carry dollars (counts_toward_spend); 0 means no billing data
    last_record_at: datetime | None
    source_kinds: list[str]
    value_kinds: list[str]
    notes: list[str]


class CompanyCoverage(OutModel):
    status: CoverageStatus
    record_count: int
    unmapped_records: int
    counter_resets: int
    spend_record_count: int  # records that carry dollars (counts_toward_spend); 0 means no billing data
    last_record_at: datetime | None
    source_kinds: list[str]
    value_kinds: list[str]
    notes: list[str]


class UnattributedSource(OutModel):
    source: str
    record_count: int


class UnattributedCoverage(OutModel):
    record_count: int
    recorded_spend: MoneyStr
    unit: Literal["USD"]
    source_accounts: list[UnattributedSource]


class CoverageSource(OutModel):
    batch_id: str
    source_kind: str
    source_label: str | None
    filename: str | None
    imported_at: datetime


class CoverageReport(OutModel):
    period: PeriodOut
    company: CompanyCoverage
    teams: list[TeamCoverage]
    unattributed: UnattributedCoverage
    sources: list[CoverageSource]
    data_labels: DataLabels
