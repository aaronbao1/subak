"""All persistence entities (design.md §3). Money columns use MoneyType; never float."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator

from app.core.clock import utcnow
from app.core.money import MoneyType
from app.db.base import Base

# ---- enumerations (stored as strings, enforced by CHECK constraints) --------------------------

VALUE_KINDS = ("measured", "estimated", "reported", "simulated")
COST_CATEGORIES = (
    "subscription_fee",
    "included_usage",
    "billable_overage",
    "direct_api",
    "unpriced_usage",
)
NON_SPEND_CATEGORIES = frozenset({"included_usage", "unpriced_usage"})
IMPORT_STATUSES = ("imported", "duplicate", "failed")
ACTION_TYPES = ("addition", "transfer")
PROPOSAL_STATUSES = ("pending_review", "applied", "rejected", "stale", "revised")
PROPOSAL_ORIGINS = ("droid_run", "finance_manual")
DECISION_OUTCOMES = ("approved_applied", "rejected")
DECISION_EVENTS = ("stale_rejected", "self_approval_blocked", "role_blocked")
DOC_ORIGINS = ("upload", "email_export", "slack_export", "seed")
DOC_TYPES = ("plan", "update", "correspondence", "note")
PLAN_STATUSES = ("approved", "draft", "informal", "cancelled", "n/a")
CHANGE_TYPES = ("expansion", "reduction", "continuation", "timing_shift", "other")
SIGNAL_STATUSES = ("current", "superseded", "conflicting", "informal", "cancelled")
SIGNAL_PRODUCERS = ("droid_fake", "droid_sdk", "finance")
FORECAST_AVAILABILITY = ("available", "partial", "unavailable")
AGENT_TASK_TYPES = ("interpret_corpus", "propose_allocation", "answer_question")
RUNNER_KINDS = ("fake", "sdk")
AGENT_RUN_STATUSES = ("running", "succeeded", "failed", "unavailable")
# Where a person works / where a document came from (frontend `Integration`).
INTEGRATIONS = ("slack", "asana", "monday", "email", "document")
PERSON_ID_PATTERN = r"^[a-z0-9][a-z0-9._-]{0,63}$"
# Who a context signal is about (frontend `ContextItem.scope`) and why usage moves (frontend `SignalKind`).
SIGNAL_SCOPES = ("person", "team", "company")
SIGNAL_KINDS = ("project_deferred", "project_accelerated", "model_change", "tool_change", "out_of_office",
                "onboarding", "steady")


def _in(column: str, values: tuple[str, ...]) -> str:
    quoted = ", ".join(f"'{v}'" for v in values)
    return f"{column} IN ({quoted})"


def new_uuid() -> str:
    return str(uuid.uuid4())


class UTCDateTime(TypeDecorator):
    """Stores naive UTC in SQLite; always returns timezone-aware UTC. Rejects naive input."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Any) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("naive datetimes are not allowed; use timezone-aware UTC")
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect: Any) -> datetime | None:
        if value is None:
            return None
        return value.replace(tzinfo=timezone.utc)


class _IdMixin:
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_uuid)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)


# ---- 3.1 / 3.2 / 3.3 -------------------------------------------------------------------------


class PlanningPeriod(Base):
    __tablename__ = "planning_periods"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)  # e.g. "2026-P1"
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    starts_on: Mapped[date] = mapped_column(Date, nullable=False)
    ends_on: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)

    __table_args__ = (CheckConstraint("ends_on >= starts_on", name="period_order"),)


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # slug
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)

    # "unattributed" is a summary bucket, never a row.
    __table_args__ = (CheckConstraint("id <> 'unattributed'", name="no_unattributed_row"),)


class Person(Base):
    """A fictional (or imported) individual on a team. Spend is attributed to a person only through a
    known directory entry (email), never from an export alone (frontend-integration-design §2.2)."""

    __tablename__ = "people"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # slug, e.g. research-ava-chen
    team_id: Mapped[str] = mapped_column(ForeignKey("teams.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[str | None] = mapped_column(String(200))
    email: Mapped[str | None] = mapped_column(String(320), unique=True)  # stored lowercase
    primary_tool: Mapped[str | None] = mapped_column(String(100))
    integrations: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)

    __table_args__ = (
        CheckConstraint("id <> 'unattributed'", name="no_unattributed_person"),
        CheckConstraint("email IS NULL OR email = lower(email)", name="email_lowercase"),
        Index("ix_people_team", "team_id"),
    )


class TeamMapping(_IdMixin, Base):
    __tablename__ = "team_mappings"

    source_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    source_account: Mapped[str] = mapped_column(String(200), nullable=False)
    team_id: Mapped[str] = mapped_column(ForeignKey("teams.id"), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)

    __table_args__ = (UniqueConstraint("source_kind", "source_account", "effective_from"),)


# ---- 3.4 / 3.5 imports and usage -------------------------------------------------------------


class ImportBatch(_IdMixin, Base):
    __tablename__ = "import_batches"

    source_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    source_label: Mapped[str | None] = mapped_column(String(200))
    filename: Mapped[str | None] = mapped_column(String(500))
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    duplicate_of_batch_id: Mapped[str | None] = mapped_column(ForeignKey("import_batches.id"))
    record_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    skipped_duplicate_records: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    unmapped_record_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_details: Mapped[dict | list | None] = mapped_column(JSON)
    imported_by: Mapped[str] = mapped_column(String(200), nullable=False)
    value_kind_default: Mapped[str] = mapped_column(String(16), nullable=False)

    records: Mapped[list["UsageRecord"]] = relationship(back_populates="batch")

    __table_args__ = (
        CheckConstraint(_in("status", IMPORT_STATUSES), name="status"),
        CheckConstraint(_in("value_kind_default", VALUE_KINDS), name="value_kind_default"),
        # Identical bytes can be imported only once per source kind.
        Index(
            "uq_import_batches_imported_hash",
            "source_kind",
            "content_hash",
            unique=True,
            sqlite_where=text("status = 'imported'"),
        ),
    )


class UsageRecord(_IdMixin, Base):
    __tablename__ = "usage_records"

    import_batch_id: Mapped[str] = mapped_column(ForeignKey("import_batches.id"), nullable=False)
    source_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    source_record_key: Mapped[str] = mapped_column(String(500), nullable=False)
    source_account: Mapped[str | None] = mapped_column(String(200))
    team_id: Mapped[str | None] = mapped_column(ForeignKey("teams.id"))
    # Set only when the export's user_email matches an active person on the mapped team.
    person_id: Mapped[str | None] = mapped_column(ForeignKey("people.id"))
    period_id: Mapped[str] = mapped_column(ForeignKey("planning_periods.id"), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    provider: Mapped[str | None] = mapped_column(String(100))
    model: Mapped[str | None] = mapped_column(String(200))
    stream_key: Mapped[str | None] = mapped_column(String(200))
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    cached_input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    reasoning_tokens: Mapped[int | None] = mapped_column(Integer)
    cumulative_snapshot: Mapped[dict | None] = mapped_column(JSON)
    counter_reset: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    amount: Mapped[Decimal | None] = mapped_column(MoneyType)
    unit: Mapped[str] = mapped_column(String(16), default="USD", nullable=False)
    value_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    cost_category: Mapped[str] = mapped_column(String(32), nullable=False)
    counts_toward_spend: Mapped[bool] = mapped_column(Boolean, nullable=False)
    notional_value: Mapped[Decimal | None] = mapped_column(MoneyType)

    batch: Mapped[ImportBatch] = relationship(back_populates="records")

    __table_args__ = (
        UniqueConstraint("source_kind", "source_record_key"),
        CheckConstraint(_in("value_kind", VALUE_KINDS), name="value_kind"),
        CheckConstraint(_in("cost_category", COST_CATEGORIES), name="cost_category"),
        # counts_toward_spend is derived from cost_category; the DB refuses a mismatch.
        CheckConstraint(
            "(cost_category IN ('included_usage', 'unpriced_usage') AND counts_toward_spend = 0)"
            " OR (cost_category NOT IN ('included_usage', 'unpriced_usage') AND counts_toward_spend = 1)",
            name="counts_toward_spend_derived",
        ),
        CheckConstraint(
            "(input_tokens IS NULL OR input_tokens >= 0)"
            " AND (cached_input_tokens IS NULL OR cached_input_tokens >= 0)"
            " AND (output_tokens IS NULL OR output_tokens >= 0)"
            " AND (reasoning_tokens IS NULL OR reasoning_tokens >= 0)",
            name="non_negative_token_deltas",
        ),
        Index("ix_usage_records_team_period", "team_id", "period_id"),
        Index("ix_usage_records_team_person_period", "team_id", "person_id", "period_id"),
        Index("ix_usage_records_stream", "source_kind", "stream_key", "occurred_at"),
    )

    @staticmethod
    def derive_counts_toward_spend(cost_category: str) -> bool:
        return cost_category not in NON_SPEND_CATEGORIES


class CounterBaseline(_IdMixin, Base):
    """A cumulative-counter observation that falls outside every planning period.

    It books no usage (there is no period to book it to), but its counter value is the starting point
    for the next in-period snapshot of the same stream. Without it, a later import would compute that
    snapshot's delta from zero and count all pre-period usage inside the period.
    """

    __tablename__ = "counter_baselines"

    import_batch_id: Mapped[str] = mapped_column(ForeignKey("import_batches.id"), nullable=False)
    source_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    source_record_key: Mapped[str] = mapped_column(String(500), nullable=False)
    stream_key: Mapped[str] = mapped_column(String(200), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    cumulative_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    counter_reset: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    __table_args__ = (
        UniqueConstraint("source_kind", "source_record_key"),
        Index("ix_counter_baselines_stream", "source_kind", "stream_key", "occurred_at"),
    )


# ---- 3.6 budgets -----------------------------------------------------------------------------


class BudgetEnvelope(_IdMixin, Base):
    __tablename__ = "budget_envelopes"

    period_id: Mapped[str] = mapped_column(ForeignKey("planning_periods.id"), unique=True, nullable=False)
    unit: Mapped[str] = mapped_column(String(16), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(MoneyType, nullable=False)
    state_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)

    allocations: Mapped[list["BudgetAllocation"]] = relationship(
        back_populates="envelope", order_by="BudgetAllocation.team_id"
    )

    __table_args__ = (CheckConstraint("state_version >= 1", name="state_version_positive"),)


class BudgetAllocation(_IdMixin, Base):
    __tablename__ = "budget_allocations"

    envelope_id: Mapped[str] = mapped_column(ForeignKey("budget_envelopes.id"), nullable=False)
    team_id: Mapped[str] = mapped_column(ForeignKey("teams.id"), nullable=False)
    amount: Mapped[Decimal] = mapped_column(MoneyType, nullable=False)

    envelope: Mapped[BudgetEnvelope] = relationship(back_populates="allocations")

    __table_args__ = (UniqueConstraint("envelope_id", "team_id"),)


class BudgetSnapshot(_IdMixin, Base):
    """Immutable record of every saved budget state (seed v1 has decision_id NULL)."""

    __tablename__ = "budget_snapshots"

    envelope_id: Mapped[str] = mapped_column(ForeignKey("budget_envelopes.id"), nullable=False)
    state_version: Mapped[int] = mapped_column(Integer, nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(MoneyType, nullable=False)
    allocations: Mapped[dict] = mapped_column(JSON, nullable=False)  # {team_id: "amount"}
    decision_id: Mapped[str | None] = mapped_column(ForeignKey("decisions.id"))

    __table_args__ = (UniqueConstraint("envelope_id", "state_version"),)


# ---- 3.7 / 3.8 proposals and decisions ------------------------------------------------------


class Proposal(_IdMixin, Base):
    __tablename__ = "proposals"

    period_id: Mapped[str] = mapped_column(ForeignKey("planning_periods.id"), nullable=False)
    unit: Mapped[str] = mapped_column(String(16), nullable=False)
    action_type: Mapped[str] = mapped_column(String(16), nullable=False)
    base_version: Mapped[int] = mapped_column(Integer, nullable=False)
    envelope_increase: Mapped[Decimal] = mapped_column(MoneyType, nullable=False)
    lines: Mapped[list] = mapped_column(JSON, nullable=False)
    before: Mapped[dict] = mapped_column(JSON, nullable=False)
    after: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="pending_review", nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_refs: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    created_by_actor: Mapped[str] = mapped_column(String(200), nullable=False)
    created_by_role: Mapped[str] = mapped_column(String(32), nullable=False)
    origin: Mapped[str] = mapped_column(String(32), nullable=False)
    agent_run_id: Mapped[str | None] = mapped_column(ForeignKey("agent_runs.id"))
    revises_proposal_id: Mapped[str | None] = mapped_column(ForeignKey("proposals.id"))
    rebased_from_proposal_id: Mapped[str | None] = mapped_column(ForeignKey("proposals.id"))
    warnings: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)

    __table_args__ = (
        CheckConstraint(_in("action_type", ACTION_TYPES), name="action_type"),
        CheckConstraint(_in("status", PROPOSAL_STATUSES), name="status"),
        CheckConstraint(_in("origin", PROPOSAL_ORIGINS), name="origin"),
        CheckConstraint("base_version >= 1", name="base_version_positive"),
        Index("ix_proposals_status", "status"),
    )


class Decision(_IdMixin, Base):
    __tablename__ = "decisions"

    proposal_id: Mapped[str] = mapped_column(ForeignKey("proposals.id"), unique=True, nullable=False)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(200), nullable=False)
    actor_role: Mapped[str] = mapped_column(String(32), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_refs: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    from_version: Mapped[int] = mapped_column(Integer, nullable=False)
    to_version: Mapped[int | None] = mapped_column(Integer)
    before: Mapped[dict] = mapped_column(JSON, nullable=False)
    after: Mapped[dict | None] = mapped_column(JSON)
    decided_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)

    __table_args__ = (
        CheckConstraint(_in("outcome", DECISION_OUTCOMES), name="outcome"),
        CheckConstraint("length(trim(rationale)) > 0", name="rationale_required"),
        CheckConstraint(
            "(outcome = 'rejected' AND to_version IS NULL)"
            " OR (outcome = 'approved_applied' AND to_version IS NOT NULL AND to_version = from_version + 1)",
            name="version_transition",
        ),
    )


class DecisionEvent(_IdMixin, Base):
    """Blocked attempts (stale, self-approval, role) - not decisions, but visible in history."""

    __tablename__ = "decision_events"

    proposal_id: Mapped[str] = mapped_column(ForeignKey("proposals.id"), nullable=False)
    event: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(200), nullable=False)
    details: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)

    __table_args__ = (CheckConstraint(_in("event", DECISION_EVENTS), name="event"),)


# ---- 3.9 / 3.10 corpus and signals ----------------------------------------------------------


class CorpusDocument(_IdMixin, Base):
    __tablename__ = "corpus_documents"

    doc_key: Mapped[str] = mapped_column(String(200), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    origin: Mapped[str] = mapped_column(String(32), nullable=False)
    doc_type: Mapped[str] = mapped_column(String(32), nullable=False)
    plan_status: Mapped[str] = mapped_column(String(16), nullable=False)
    authored_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    effective_from: Mapped[date | None] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date)
    team_tags: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    project_tags: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    author: Mapped[str | None] = mapped_column(String(200))
    # Where the document came from (slack/asana/monday/email/document); NULL falls back to `origin`.
    integration: Mapped[str | None] = mapped_column(String(16))
    # People the document is about (ids in `people`), checked at ingest.
    person_tags: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    supersedes_document_id: Mapped[str | None] = mapped_column(ForeignKey("corpus_documents.id"))
    superseded_by_document_id: Mapped[str | None] = mapped_column(ForeignKey("corpus_documents.id"))
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    __table_args__ = (
        UniqueConstraint("doc_key", "version"),
        CheckConstraint("version >= 1", name="version_positive"),
        CheckConstraint(_in("origin", DOC_ORIGINS), name="origin"),
        CheckConstraint(_in("doc_type", DOC_TYPES), name="doc_type"),
        CheckConstraint(_in("plan_status", PLAN_STATUSES), name="plan_status"),
        CheckConstraint("integration IS NULL OR " + _in("integration", INTEGRATIONS), name="integration"),
        CheckConstraint("supersedes_document_id IS NULL OR supersedes_document_id <> id", name="no_self_supersede"),
    )


class ContextSignal(_IdMixin, Base):
    __tablename__ = "context_signals"

    team_id: Mapped[str | None] = mapped_column(ForeignKey("teams.id"))
    # person: one or more named people on one team; team: a team plan; company: every team (team NULL).
    scope: Mapped[str] = mapped_column(String(16), default="team", server_default="team", nullable=False)
    person_ids: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    signal_kind: Mapped[str | None] = mapped_column(String(32))
    title: Mapped[str | None] = mapped_column(String(120))
    project: Mapped[str | None] = mapped_column(String(200))
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    change_type: Mapped[str] = mapped_column(String(32), nullable=False)
    applies_from: Mapped[date | None] = mapped_column(Date)
    applies_to: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    uncertainty: Mapped[str] = mapped_column(Text, nullable=False)
    produced_by: Mapped[str] = mapped_column(String(16), nullable=False)
    agent_run_id: Mapped[str | None] = mapped_column(ForeignKey("agent_runs.id"))
    superseded_by_signal_id: Mapped[str | None] = mapped_column(ForeignKey("context_signals.id"))

    citations: Mapped[list["SignalCitation"]] = relationship(
        back_populates="signal", order_by="SignalCitation.char_start"
    )

    __table_args__ = (
        CheckConstraint(_in("change_type", CHANGE_TYPES), name="change_type"),
        CheckConstraint(_in("status", SIGNAL_STATUSES), name="status"),
        CheckConstraint(_in("produced_by", SIGNAL_PRODUCERS), name="produced_by"),
        CheckConstraint("length(trim(uncertainty)) > 0", name="uncertainty_required"),
        CheckConstraint(_in("scope", SIGNAL_SCOPES), name="scope"),
        CheckConstraint("scope <> 'company' OR team_id IS NULL", name="company_scope_has_no_team"),
        CheckConstraint("signal_kind IS NULL OR " + _in("signal_kind", SIGNAL_KINDS), name="signal_kind"),
    )


class SignalCitation(_IdMixin, Base):
    __tablename__ = "signal_citations"

    signal_id: Mapped[str] = mapped_column(ForeignKey("context_signals.id"), nullable=False)
    document_id: Mapped[str] = mapped_column(ForeignKey("corpus_documents.id"), nullable=False)
    quote: Mapped[str] = mapped_column(Text, nullable=False)
    char_start: Mapped[int] = mapped_column(Integer, nullable=False)
    char_end: Mapped[int] = mapped_column(Integer, nullable=False)

    signal: Mapped[ContextSignal] = relationship(back_populates="citations")

    __table_args__ = (
        CheckConstraint("char_start >= 0 AND char_end > char_start", name="span_valid"),
    )


# ---- 3.11 / 3.12 forecasts and agent runs ---------------------------------------------------


class ForecastSnapshot(_IdMixin, Base):
    __tablename__ = "forecast_snapshots"

    period_id: Mapped[str] = mapped_column(ForeignKey("planning_periods.id"), nullable=False)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    availability: Mapped[str] = mapped_column(String(16), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)

    __table_args__ = (CheckConstraint(_in("availability", FORECAST_AVAILABILITY), name="availability"),)


class AgentRun(_IdMixin, Base):
    __tablename__ = "agent_runs"

    task_type: Mapped[str] = mapped_column(String(32), nullable=False)
    input: Mapped[dict] = mapped_column(JSON, nullable=False)
    runner_kind: Mapped[str] = mapped_column(String(8), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    output: Mapped[dict | None] = mapped_column(JSON)
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime)

    steps: Mapped[list["AgentRunStep"]] = relationship(back_populates="run", order_by="AgentRunStep.seq")

    __table_args__ = (
        CheckConstraint(_in("task_type", AGENT_TASK_TYPES), name="task_type"),
        CheckConstraint(_in("runner_kind", RUNNER_KINDS), name="runner_kind"),
        CheckConstraint(_in("status", AGENT_RUN_STATUSES), name="status"),
    )


class AgentRunStep(_IdMixin, Base):
    __tablename__ = "agent_run_steps"

    run_id: Mapped[str] = mapped_column(ForeignKey("agent_runs.id"), nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    tool: Mapped[str] = mapped_column(String(100), nullable=False)
    args: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    result_summary: Mapped[str | None] = mapped_column(Text)
    at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)

    run: Mapped[AgentRun] = relationship(back_populates="steps")

    __table_args__ = (UniqueConstraint("run_id", "seq"),)


AGENT_EVENT_SOURCES = ("fake_runner", "droid_sdk", "backend")


class AgentRunEvent(_IdMixin, Base):
    """Visible activity stream of a run (tool called, evidence found, proposal drafted, ...).

    Stored, not just pushed, so the SSE endpoint can replay a finished run and a reconnecting client
    resumes from `seq` without losing events."""

    __tablename__ = "agent_run_events"

    run_id: Mapped[str] = mapped_column(ForeignKey("agent_runs.id"), nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    type: Mapped[str] = mapped_column(String(40), nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    data: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)

    __table_args__ = (
        UniqueConstraint("run_id", "seq"),
        CheckConstraint(_in("source", AGENT_EVENT_SOURCES), name="source"),
    )


# ---- frontend compat: assistant threads (app/compat) -----------------------------------------

ASSISTANT_ROLES = ("user", "assistant")


class AssistantMessage(_IdMixin, Base):
    """One chat message in a dashboard assistant thread. Compat-layer state only: the run it triggered
    (`agent_run_id`) is the audit record; nothing here can change a budget."""

    __tablename__ = "assistant_messages"

    thread_id: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    agent_run_id: Mapped[str | None] = mapped_column(ForeignKey("agent_runs.id"))
    proposal_id: Mapped[str | None] = mapped_column(String(64))
    citations: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    tool_calls: Mapped[list] = mapped_column(JSON, default=list, nullable=False)

    __table_args__ = (
        UniqueConstraint("thread_id", "seq"),
        CheckConstraint(_in("role", ASSISTANT_ROLES), name="role"),
    )
