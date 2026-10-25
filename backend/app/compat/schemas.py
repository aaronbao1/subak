"""Pydantic mirrors of the frontend contract (`frontend/src/lib/contracts/index.ts` on origin/main).

These are the response models of the compat router. They are deliberately strict (`extra="forbid"`)
and camelCase, with TypeScript optional fields (`field?: T`) as `T | None = None`; the router serializes
with `exclude_none`, so an optional field the backend cannot honestly fill is omitted, never `null`.
`tests/test_compat_contract.py` parses the current checked-out TypeScript file and fails if a field,
its optionality, or a string-literal union drifts from these models.

Money fields are JSON numbers here (the frontend contract) and are produced only by
`app.compat.mappers.num`; nothing in this module flows back into a service.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict
from app.schemas.agent import ForecastQuestionContext

Unit = Literal["credits", "usd", "tokens"]
CostComponent = Literal["subscription", "included_usage", "extra_usage", "api"]
Provenance = Literal["reported_charge", "estimate", "usage_only"]
ContextKind = Literal["plan", "project_doc", "research_note", "correspondence"]
ClaimType = Literal["stated_plan", "observed_event", "interpretation"]
ProposalKind = Literal["redistribute", "add_budget"]
Integration = Literal["slack", "asana", "monday", "email", "document", "gmail", "notion", "google_docs", "linear", "pdf"]
SignalKind = Literal["project_deferred", "project_accelerated", "model_change", "tool_change", "out_of_office",
                     "onboarding", "steady", "pricing_change", "policy_change", "project_paused"]
EvidenceCategory = Literal["project", "staffing", "policy", "pricing", "model", "macro"]
Scope = Literal["person", "team", "company"]
Number = int | float


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Team(_Model):
    id: str
    name: str
    description: str | None = None
    lead: str | None = None
    color: str


class EffectMagnitude(_Model):
    pct: Number | None = None
    amount: Number | None = None
    basis: str | None = None


class ForecastAdjustment(_Model):
    contextId: str
    amount: Number
    note: str | None = None


class Person(_Model):
    id: str
    teamId: str
    name: str
    role: str | None = None
    email: str | None = None
    integrations: list[Integration] | None = None
    primaryTool: str | None = None


class Period(_Model):
    start: str
    end: str
    label: str | None = None


class SpendingRecord(_Model):
    id: str
    teamId: str
    personId: str | None = None
    date: str
    component: CostComponent
    provider: str
    model: str | None = None
    tokens: Number | None = None
    amount: Number
    unit: Unit
    provenance: Provenance
    source: str
    complete: bool


class Budget(_Model):
    teamId: str
    period: Period
    allocated: Number
    unit: Unit
    version: str | None = None


class ForecastDailyPoint(_Model):
    date: str
    projected: Number
    low: Number | None = None
    high: Number | None = None


class Forecast(_Model):
    id: str | None = None
    teamId: str
    personId: str | None = None
    period: Period
    status: Literal["available", "unavailable"]
    basis: Literal["full_period", "remaining"] | None = None
    kind: Literal["forecast", "scenario"] | None = None
    origin: Literal["placeholder", "forecasting_service"] | None = None
    projected: Number | None = None
    low: Number | None = None
    high: Number | None = None
    daily: list[ForecastDailyPoint] | None = None
    baseline: Number | None = None
    adjustments: list[ForecastAdjustment] | None = None
    unit: Unit
    assumptions: list[str]
    limitations: list[str]
    generatedAt: str
    unavailableReason: str | None = None


class SourceRef(_Model):
    documentId: str
    title: str
    excerpt: str | None = None
    locator: str | None = None
    date: str | None = None
    kind: ContextKind | None = None
    integration: Integration | None = None
    author: str | None = None


class ContextItem(_Model):
    id: str
    teamIds: list[str]
    title: str
    summary: str
    kind: ContextKind
    effectiveFrom: str | None = None
    effectiveTo: str | None = None
    expectedEffect: Literal["increase", "decrease", "neutral", "unknown"]
    confidence: Literal["high", "medium", "low"]
    sources: list[SourceRef]
    uncertainty: str | None = None
    claimType: ClaimType | None = None
    supersededBy: str | None = None
    supersedes: list[str] | None = None
    personIds: list[str] | None = None
    scope: Scope | None = None
    signal: SignalKind | None = None
    category: EvidenceCategory | None = None
    magnitude: EffectMagnitude | None = None
    attribution: str | None = None


class AllocationLine(_Model):
    teamId: str
    before: Number
    after: Number


class AllocationProposal(_Model):
    id: str
    kind: ProposalKind
    unit: Unit
    period: Period
    totalBefore: Number
    totalAfter: Number
    addedAmount: Number | None = None
    lines: list[AllocationLine]
    rationale: str
    citations: list[SourceRef]
    createdAt: str
    status: Literal["proposed", "pending", "applied", "rejected", "revised", "stale", "failed"]
    revisesProposalId: str | None = None
    basedOnBudgetVersion: str | None = None
    failureReason: str | None = None
    forecastsReviewed: list[Forecast] | None = None


class Decision(_Model):
    id: str
    proposalId: str
    action: Literal["applied", "rejected"]
    kind: ProposalKind
    appliedAt: str
    appliedBy: str
    note: str | None = None
    lines: list[AllocationLine]
    unit: Unit
    forecastsReviewed: list[Forecast] | None = None
    rationale: str | None = None


class ToolCallSummary(_Model):
    name: str
    summary: str


class AssistantMessage(_Model):
    id: str
    threadId: str
    role: Literal["user", "assistant"]
    content: str
    createdAt: str
    proposalId: str | None = None
    citations: list[SourceRef] | None = None
    toolCalls: list[ToolCallSummary] | None = None


class CompanyDocument(_Model):
    id: str
    title: str
    kind: ContextKind
    date: str
    teamIds: list[str] | None = None
    origin: str
    body: str
    supersededBy: str | None = None
    personIds: list[str] | None = None
    integration: Integration | None = None


class Company(_Model):
    id: str
    name: str
    isDemo: bool
    budgetUnit: Unit
    currentPeriod: Period


# ---- request bodies (frontend -> compat) ------------------------------------------------------


class MessageIn(BaseModel):
    content: str
    forecast_context: ForecastQuestionContext | None = None


class ApplyIn(BaseModel):
    note: str | None = None


class ErrorOut(BaseModel):
    """Compat error envelope: `error` is the plain-English message the UI shows verbatim; `code` is the
    backend's stable code for anyone who wants to branch on it."""

    error: str
    code: str


# Every interface in the TypeScript contract, by name (used by the drift test).
CONTRACT_MODELS: dict[str, type[_Model]] = {
    m.__name__: m
    for m in (Team, EffectMagnitude, ForecastAdjustment, Person, Period, SpendingRecord, Budget, ForecastDailyPoint, Forecast, SourceRef, ContextItem, AllocationLine,
              AllocationProposal, Decision, ToolCallSummary, AssistantMessage, CompanyDocument, Company)
}
CONTRACT_ALIASES = {
    "Unit": Unit, "CostComponent": CostComponent, "Provenance": Provenance, "ContextKind": ContextKind,
    "ClaimType": ClaimType, "ProposalKind": ProposalKind, "Integration": Integration, "SignalKind": SignalKind, "EvidenceCategory": EvidenceCategory,
}
