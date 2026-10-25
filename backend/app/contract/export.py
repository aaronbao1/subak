"""Export the API contract: `contract/openapi.json` and `contract/fixtures/*.json`.

    cd backend && .venv/bin/python -m app.contract.export            # write
    cd backend && .venv/bin/python -m app.contract.export --check    # exit 1 if committed files differ

Every fixture is a REAL response captured through the FastAPI app against a fresh, seeded SQLite file
with a frozen clock (2026-10-24T12:00:00Z, advanced one minute per request) and sequential ids, so
the output is byte-for-byte deterministic. Each file is
`{"name", "scenario", "description", "schema", "request": {...}, "status", "response"}`.
Ids restart in every scenario (each scenario is its own database).
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from pydantic import BaseModel, TypeAdapter

from app.config import BACKEND_ROOT, Settings
from app.core.clock import FrozenClock, SequentialIdFactory
from app.main import create_app
from app.schemas.agent import AgentRunList, AgentRunOut
from app.schemas.budget import BudgetHistory, BudgetState
from app.schemas.charts import ChartKindList, ChartSpecOut
from app.schemas.common import ErrorBody
from app.schemas.decisions import DecisionEventOut, DecisionOut
from app.schemas.documents import DocumentDetail, DocumentIngestResult, DocumentList, DocumentVersions
from app.schemas.forecasts import ForecastResult, ForecastSnapshotOut
from app.schemas.imports import CoverageReport, ImportResult, TeamMappingOut, TeamMappingUpsertResult, TeamOut
from app.schemas.meta import MetaOut, Overview
from app.schemas.people import PersonOut
from app.schemas.proposals import ProposalOut
from app.schemas.signals import ContextSignalOut, SignalList
from app.schemas.spending import SpendRecordList, SpendSummary
from app.schemas.usage import DailyUsageResponse
from app.seed.northstar import seed

DEFAULT_OUT = BACKEND_ROOT / "contract"
FROZEN_AT = datetime(2026, 10, 24, 12, 0, 0, tzinfo=timezone.utc)

ANALYST = {"X-Actor-Id": "fin-analyst-ana", "X-Actor-Role": "finance_analyst"}
APPROVER = {"X-Actor-Id": "fin-approver-alice", "X-Actor-Role": "finance_approver"}
APPROVER_2 = {"X-Actor-Id": "fin-approver-bob", "X-Actor-Role": "finance_approver"}
DROID = {"X-Actor-Id": "droid-northstar", "X-Actor-Role": "droid_agent"}
IMPORTER = {"X-Actor-Id": "importer-1", "X-Actor-Role": "importer"}

OUTCOME_A_LINES = [
    {"from_team": "product", "to_team": "research", "amount": "25000.00"},
    {"from_team": "product", "to_team": "engineering", "amount": "5000.00"},
]
OUTCOME_B_LINES = [
    {"to_team": "research", "amount": "35000.00"},
    {"to_team": "engineering", "amount": "15000.00"},
]

# Fixture `schema` -> model used to validate it. Every name is an OpenAPI component name
# (`components.schemas.<name>`); `<name>[]` is a JSON array of that component; `NoContent` is an empty
# 204 body. `ErrorBody` is used for every error case.
SCHEMAS: dict[str, Any] = {
    "MetaOut": MetaOut, "TeamOut[]": list[TeamOut], "PersonOut[]": list[PersonOut], "TeamMappingOut[]": list[TeamMappingOut],
    "TeamMappingUpsertResult": TeamMappingUpsertResult,
    "BudgetState": BudgetState, "BudgetHistory": BudgetHistory, "SpendSummary": SpendSummary,
    "SpendRecordList": SpendRecordList, "CoverageReport": CoverageReport, "ImportResult": ImportResult,
    "DailyUsageResponse": DailyUsageResponse,
    "ForecastResult": ForecastResult, "ForecastSnapshotOut": ForecastSnapshotOut, "Overview": Overview,
    "DocumentList": DocumentList, "DocumentDetail": DocumentDetail, "DocumentVersions": DocumentVersions,
    "DocumentIngestResult": DocumentIngestResult,
    "ContextSignalOut": ContextSignalOut, "SignalList": SignalList, "ProposalOut": ProposalOut,
    "ProposalOut[]": list[ProposalOut], "DecisionOut": DecisionOut, "DecisionOut[]": list[DecisionOut],
    "DecisionEventOut[]": list[DecisionEventOut], "ErrorBody": ErrorBody,
    "AgentRunOut": AgentRunOut, "AgentRunList": AgentRunList, "NoContent": None,
    "ChartSpecOut": ChartSpecOut, "ChartKindList": ChartKindList,
}


def validate_fixture(fixture: dict) -> None:
    """Raise if a fixture's response does not match its declared schema."""
    schema = SCHEMAS[fixture["schema"]]
    if schema is None:
        if fixture["response"] is not None:
            raise ValueError(f"{fixture['name']}: NoContent fixture has a body")
        return
    if isinstance(schema, type) and issubclass(schema, BaseModel):
        schema.model_validate(fixture["response"])
    else:
        TypeAdapter(schema).validate_python(fixture["response"])


@dataclass
class Recorder:
    client: TestClient
    clock: FrozenClock
    scenario: str
    out: dict[str, dict] = field(default_factory=dict)

    def call(self, name: str | None, method: str, path: str, *, schema: str, description: str,
             headers: dict | None = None, json_body: Any = None, params: dict | None = None,
             files: dict | None = None, form: dict | None = None, expect: int | None = None) -> dict:
        self.clock.advance(minutes=1)
        kwargs: dict[str, Any] = {"headers": headers or {}}
        if json_body is not None:
            kwargs["json"] = json_body
        if params:
            kwargs["params"] = params
        if files:
            kwargs["files"] = files
            kwargs["data"] = form or {}
        resp = self.client.request(method, path, **kwargs)
        if expect is not None and resp.status_code != expect:
            raise RuntimeError(f"{self.scenario}/{name}: expected {expect}, got {resp.status_code}: {resp.text}")
        body = resp.json() if resp.content else None
        if name is not None:
            request: dict[str, Any] = {"method": method, "path": path}
            if params:
                request["query"] = params
            if headers:
                request["headers"] = headers
            if json_body is not None:
                request["body"] = json_body
            if files:
                request["multipart"] = {"form": form or {}, "file": next(iter(files.values()))[0]}
            fixture = {"name": name, "scenario": self.scenario, "description": description, "schema": schema,
                       "request": request, "status": resp.status_code, "response": body}
            validate_fixture(fixture)
            if name in self.out:
                raise RuntimeError(f"duplicate fixture name {name}")
            self.out[name] = fixture
        return body


Scenario = Callable[[Recorder], None]


def _run(scenario: str, fn: Scenario, out: dict[str, dict], *, forecast_provider: str = "placeholder",
         seed_kwargs: dict | None = None, droid_runner: str = "fake") -> None:
    with tempfile.TemporaryDirectory() as tmp:
        clock = FrozenClock(FROZEN_AT)
        ids = SequentialIdFactory()
        app = create_app(Settings(db_path=Path(tmp) / "contract.db", forecast_provider=forecast_provider,
                                  droid_runner=droid_runner), clock=clock, id_factory=ids)
        s = app.state.session_factory()
        try:
            seed(s, clock=clock, ids=ids, **(seed_kwargs or {}))
        finally:
            s.close()
        try:
            with TestClient(app) as client:
                fn(Recorder(client, clock, scenario, out))
        finally:
            app.state.engine.dispose()


def _doc_id(rec: Recorder, doc_key: str, version: int | None = None) -> str:
    versions = rec.call(None, "GET", f"/api/documents/by-key/{doc_key}/versions", schema="DocumentVersions",
                        description="", expect=200)["versions"]
    if version is None:
        return versions[-1]["id"]
    return next(v["id"] for v in versions if v["version"] == version)


def _transfer(rationale: str, evidence: list[dict] | None = None, base_version: int = 1) -> dict:
    return {"action_type": "transfer", "base_version": base_version, "rationale": rationale,
            "lines": OUTCOME_A_LINES, "evidence_refs": evidence or []}


def _addition(rationale: str, evidence: list[dict] | None = None, base_version: int = 1) -> dict:
    return {"action_type": "addition", "base_version": base_version, "envelope_increase": "50000.00",
            "rationale": rationale, "lines": OUTCOME_B_LINES, "evidence_refs": evidence or []}


# ---- scenarios ---------------------------------------------------------------------------------


def scenario_main(r: Recorder) -> None:
    """Seeded Northstar: reads, signals, outcome A applied, replay, stale outcome B, rebase."""
    r.call("meta", "GET", "/api/meta", schema="MetaOut", expect=200,
           description="modes and real-vs-simulated labels")
    r.call("teams", "GET", "/api/teams", schema="TeamOut[]", expect=200, description="three Northstar teams")
    r.call("people", "GET", "/api/people", schema="PersonOut[]", expect=200,
           description="fifteen fictional people (6 research / 4 product / 5 engineering), simulated")
    r.call("team_mappings", "GET", "/api/team-mappings", schema="TeamMappingOut[]", expect=200,
           description="explicit source account -> team mappings")
    r.call("budget_state_initial", "GET", "/api/budget", schema="BudgetState", expect=200,
           description="version 1: research 60k, product 80k, engineering 60k; envelope 200k")
    r.call("spend_summary", "GET", "/api/spend/summary", schema="SpendSummary", expect=200,
           description="recorded spend 45k/20k/30k = 95k; included usage notional only; coverage complete")
    r.call("coverage", "GET", "/api/coverage", schema="CoverageReport", expect=200,
           description="coverage per team and company for the seeded data")
    r.call("spend_records_research", "GET", "/api/spend/records", params={"team": "research", "limit": 8},
           schema="SpendRecordList", expect=200,
           description="research drill-down (first 8 of 260 daily records): per-person rows carry `person`; "
                       "team-level included_usage has person null and counts_toward_spend=false")
    r.call("spend_records_person", "GET", "/api/spend/records",
           params={"person": "research-omar-haddad", "cost_category": "direct_api", "limit": 20},
           schema="SpendRecordList", expect=200,
           description="one person's daily API spend Oct 1-20 (usage halves from Oct 19)")
    r.call("forecast_available", "GET", "/api/forecasts", schema="ForecastResult", expect=200,
           description="placeholder projections 85k/50k/65k, full_period_total, simulated (not a model)")
    snap = r.call("forecast_snapshot", "POST", "/api/forecasts/snapshots", headers=DROID,
                  schema="ForecastSnapshotOut", expect=201,
                  description="persisted forecast that proposals and decisions can cite")
    r.call("overview", "GET", "/api/overview", schema="Overview", expect=200,
           description="spend + budget + forecast combined, per-team comparison")
    r.call("documents", "GET", "/api/documents", schema="DocumentList", expect=200,
           description="13 seeded documents with supersedes links, is_current, integration and person_tags")
    r.call("documents_search_model_evaluation", "GET", "/api/documents",
           params={"q": "model-evaluation", "include_superseded": "true"}, schema="DocumentList", expect=200,
           description="keyword search with exact match offsets; superseded thread still listed, marked")
    plan_id = _doc_id(r, "research-eval-plan")
    thread_id = _doc_id(r, "research-timeline-thread")
    launch_v1 = _doc_id(r, "product-launch-plan", 1)
    launch_v2 = _doc_id(r, "product-launch-plan", 2)
    eng_id = _doc_id(r, "engineering-platform-note")
    mkt_id = _doc_id(r, "marketing-ideas-slack")
    r.call("document_detail_research_plan", "GET", f"/api/documents/{plan_id}", schema="DocumentDetail",
           expect=200, description="full content of the approved research plan")
    r.call("document_versions_product_launch", "GET", "/api/documents/by-key/product-launch-plan/versions",
           schema="DocumentVersions", expect=200, description="product launch plan v1 -> v2 chain")

    research = r.call("signal_created", "POST", "/api/signals", headers=ANALYST, schema="ContextSignalOut",
                      expect=201, description="verified signal: exact quote from the approved research plan",
                      json_body={
        "team": "research", "project": "model-evaluation", "change_type": "expansion", "status": "current",
        "summary": "Approved plan expands model-evaluation work in the current period.",
        "applies_from": "2026-10-01", "applies_to": "2026-12-31",
        "uncertainty": "token volume depends on how many model updates ship; plan is not measured usage",
        "citations": [{"document_id": plan_id,
                       "quote": "This plan expands model-evaluation work during the current planning period."}],
    })
    r.call(None, "POST", "/api/signals", headers=ANALYST, schema="ContextSignalOut", expect=201, description="",
           json_body={
        "team": "research", "project": "model-evaluation", "change_type": "timing_shift", "status": "superseded",
        "summary": "Older email thread pushed the evaluation expansion to next period; superseded by the approved plan.",
        "uncertainty": "informal correspondence; replaced by the approved plan of 2026-10-08",
        "citations": [{"document_id": thread_id,
                       "quote": "we will push the model-evaluation expansion to next period."}],
    })
    product = r.call(None, "POST", "/api/signals", headers=ANALYST, schema="ContextSignalOut", expect=201,
                     description="", json_body={
        "team": "product", "project": "workspace-launch", "change_type": "timing_shift", "status": "current",
        "summary": "Launch milestone moved to the following period; near-term launch work reduced.",
        "uncertainty": "pilot feedback could move the milestone again",
        "citations": [
            {"document_id": launch_v2,
             "quote": "The general-availability launch milestone moves to the following period"},
            {"document_id": launch_v1,
             "quote": "The general-availability launch milestone for the assistant workspace lands in the current period."},
        ],
    })
    eng = r.call(None, "POST", "/api/signals", headers=ANALYST, schema="ContextSignalOut", expect=201,
                 description="", json_body={
        "team": "engineering", "project": "platform", "change_type": "continuation", "status": "current",
        "summary": "Platform migration continues through the current period at the current pace.",
        "uncertainty": "pace tracks the migration backlog",
        "citations": [{"document_id": eng_id,
                       "quote": "Platform migration work continues through the current period at the current pace."}],
    })
    marketing = r.call(None, "POST", "/api/signals", headers=ANALYST, schema="ContextSignalOut", expect=201,
                       description="", json_body={
        "team": None, "project": "campaigns", "change_type": "other", "status": "informal",
        "summary": "Marketing brainstorm about generated demo videos; no budget or approval.",
        "uncertainty": "brainstorm only, explicitly not a plan",
        "citations": [{"document_id": mkt_id, "quote": "fun idea, no budget or approval for it yet though"}],
    })
    omar_doc = _doc_id(r, "research-model-switch-slack")
    announce_doc = _doc_id(r, "company-model-announcement-slack")
    r.call("signal_person_created", "POST", "/api/signals", headers=DROID, schema="ContextSignalOut", expect=201,
           description="person-scope signal: team derived from the person, signal_kind model_change", json_body={
        "scope": "person", "person_ids": ["research-omar-haddad"], "signal_kind": "model_change",
        "title": "Omar Haddad moving eval sweeps to a cheaper model tier", "project": "model-evaluation",
        "change_type": "reduction", "status": "current", "applies_from": "2026-10-19",
        "summary": "Omar Haddad moves his nightly eval sweeps to the smaller model tier from 2026-10-19.",
        "uncertainty": "no prices or token volumes for either tier",
        "citations": [{"document_id": omar_doc,
                       "quote": "from Monday 2026-10-19 I'm moving the nightly eval sweeps from the large model "
                                "to the smaller model tier."}],
    })
    r.call("signal_company_created", "POST", "/api/signals", headers=DROID, schema="ContextSignalOut", expect=201,
           description="company-scope signal: no team, no people; applies to every team", json_body={
        "scope": "company", "signal_kind": "model_change", "title": "Company-wide default model change from Nov 2",
        "change_type": "other", "status": "current", "applies_from": "2026-11-02",
        "summary": "Every team's default model moves to a new mid-tier model from 2026-11-02.",
        "uncertainty": "the net effect on each team's bill is not known",
        "citations": [{"document_id": announce_doc,
                       "quote": "the net effect on each team's bill is not known yet."}],
    })
    r.call("error_signal_scope", "POST", "/api/signals", headers=DROID, schema="ErrorBody", expect=422,
           description="scope rules: every person in a person signal must be on one team (person_team_mismatch)",
           json_body={
        "scope": "person", "person_ids": ["research-omar-haddad", "product-felix-weber"], "team": "research",
        "change_type": "other", "status": "current", "summary": "Two people on two teams.",
        "uncertainty": "invalid on purpose",
        "citations": [{"document_id": omar_doc, "quote": "just the cheaper tier for everything except the final "
                                                         "comparison runs."}],
    })
    r.call("signals", "GET", "/api/signals", schema="SignalList", expect=200,
           description="team / person / company signals (current, superseded, informal) with citation currency")
    r.call("signal_detail_product", "GET", f"/api/signals/{product['id']}", schema="ContextSignalOut", expect=200,
           description="product timing shift citing v2 (current) and v1 (superseded)")
    r.call("error_citation_not_found", "POST", "/api/signals", headers=DROID, schema="ErrorBody", expect=422,
           description="quote does not occur verbatim in the cited document", json_body={
        "team": "research", "change_type": "expansion", "status": "current",
        "summary": "Research budget doubles.", "uncertainty": "unverified",
        "citations": [{"document_id": plan_id, "quote": "research budget doubles this period"}],
    })
    r.call("error_signal_cites_superseded_only", "POST", "/api/signals", headers=DROID, schema="ErrorBody",
           expect=422, description="a current signal resting only on a superseded document is refused", json_body={
        "team": "research", "change_type": "timing_shift", "status": "current",
        "summary": "Evaluation expansion is next period.", "uncertainty": "from email",
        "citations": [{"document_id": thread_id,
                       "quote": "we will push the model-evaluation expansion to next period."}],
    })

    evidence = [
        {"kind": "signal", "id": research["id"]}, {"kind": "signal", "id": product["id"]},
        {"kind": "signal", "id": eng["id"]}, {"kind": "forecast_snapshot", "id": snap["id"]},
        {"kind": "document", "id": plan_id},
    ]
    a = r.call("proposal_transfer_pending", "POST", "/api/proposals", headers=DROID, schema="ProposalOut",
               expect=201, description="outcome A drafted by Droid: product->research 25k, product->engineering 5k",
               json_body=_transfer("Research expands model evaluation this period while the product launch moved "
                                   "to next period; move 30k of product's allocation.", evidence))
    b = r.call("proposal_addition_pending", "POST", "/api/proposals", headers=DROID, schema="ProposalOut",
               expect=201, description="outcome B drafted at the same base version: +50k envelope, research +35k, "
                                       "engineering +15k",
               json_body=_addition("Add 50k prioritizing research evaluation and engineering continuation.", evidence))
    r.call("error_validation_negative_allocation", "POST", "/api/proposals", headers=DROID, schema="ErrorBody",
           expect=422, description="transfer exceeding the source allocation",
           json_body={**_transfer("move more than product has"),
                      "lines": [{"from_team": "product", "to_team": "research", "amount": "90000.00"}]})
    r.call("error_validation_addition_mismatch", "POST", "/api/proposals", headers=DROID, schema="ErrorBody",
           expect=422, description="addition whose lines do not sum to the envelope increase",
           json_body={**_addition("lines short of the increase"),
                      "lines": [{"to_team": "research", "amount": "35000.00"}]})
    r.call("proposals_pending", "GET", "/api/proposals", params={"status": "pending_review"},
           schema="ProposalOut[]", expect=200, description="review queue")
    approve = {"outcome": "approve", "rationale": "Matches the approved research plan and the launch update.",
               "evidence_refs": [{"kind": "signal", "id": research["id"]}]}
    r.call("error_role_forbidden_droid_decides", "POST", f"/api/proposals/{a['id']}/decision",
           headers={**DROID, "Idempotency-Key": "droid-attempt-1"}, json_body=approve, schema="ErrorBody",
           expect=403, description="Droid can draft but never decide")
    applied = r.call("decision_applied_transfer", "POST", f"/api/proposals/{a['id']}/decision",
           headers={**APPROVER, "Idempotency-Key": "approve-transfer-1"}, json_body=approve, schema="DecisionOut",
           expect=201, description="approved and applied: 85k/50k/65k, total 200k, version 1 -> 2")
    r.call("decision_replayed", "POST", f"/api/proposals/{a['id']}/decision",
           headers={**APPROVER, "Idempotency-Key": "approve-transfer-1"}, json_body=approve, schema="DecisionOut",
           expect=200, description="same Idempotency-Key and body: stored decision, replayed=true, applied once")
    r.call("error_idempotency_key_reused", "POST", f"/api/proposals/{a['id']}/decision",
           headers={**APPROVER, "Idempotency-Key": "approve-transfer-1"},
           json_body={**approve, "rationale": "different rationale"}, schema="ErrorBody", expect=409,
           description="same key with a different request body")
    r.call("error_proposal_not_pending", "POST", f"/api/proposals/{a['id']}/decision",
           headers={**APPROVER, "Idempotency-Key": "approve-transfer-2"}, json_body=approve, schema="ErrorBody",
           expect=409, description="a second decision on an applied proposal")
    r.call("budget_state_after_transfer", "GET", "/api/budget", schema="BudgetState", expect=200,
           description="version 2 after outcome A")
    r.call("error_stale_proposal", "POST", f"/api/proposals/{b['id']}/decision",
           headers={**APPROVER, "Idempotency-Key": "approve-addition-1"},
           json_body={"outcome": "approve", "rationale": "add funds"}, schema="ErrorBody", expect=409,
           description="outcome B was drafted against version 1; budget is now version 2 -> not applied")
    r.call("proposal_stale", "GET", f"/api/proposals/{b['id']}", schema="ProposalOut", expect=200,
           description="the stale proposal with is_stale=true and its blocked attempt")
    r.call("proposal_rebased", "POST", f"/api/proposals/{b['id']}/rebase", headers=ANALYST, json_body={},
           schema="ProposalOut", expect=201, description="same intent re-drafted on version 2; needs a fresh review")
    r.call("decision_history", "GET", "/api/decisions", schema="DecisionOut[]", expect=200,
           description="who, when, why, evidence, before/after, version for each decision")
    r.call("decision_events", "GET", "/api/decision-events", schema="DecisionEventOut[]", expect=200,
           description="blocked attempts: Droid decide (role), stale apply")
    r.call("budget_history", "GET", "/api/budget/history", schema="BudgetHistory", expect=200,
           description="immutable snapshots v1 (seed) and v2 linked to the decision")
    r.call("decision_detail", "GET", f"/api/decisions/{applied['id']}", schema="DecisionOut", expect=200,
           description="one decision by id: who, when, why, evidence, before/after")
    r.call("signal_patched", "PATCH", f"/api/signals/{marketing['id']}", headers=ANALYST, schema="ContextSignalOut",
           expect=200, json_body={"uncertainty": "brainstorm only; finance reviewed it, still no plan or budget"},
           description="finance curation: uncertainty updated; content and citations stay immutable")
    r.call("signal_deleted", "DELETE", f"/api/signals/{marketing['id']}", headers=ANALYST, schema="NoContent",
           expect=204, description="an uncited signal removed (204, empty body); cited signals return 409")
    r.call("team_mapping_upserted", "PUT", "/api/team-mappings", headers=ANALYST, schema="TeamMappingUpsertResult",
           expect=200, json_body={"source_kind": "northstar_billing", "source_account": "ws-shared-sandbox",
                                  "team_id": "research", "effective_from": "2026-10-01"},
           description="explicit mapping for a previously unmapped account (future imports attribute to research)")
    doc = {"doc_key": "research-eval-staffing-note", "title": "Evaluation staffing note", "origin": "upload",
           "doc_type": "note", "plan_status": "n/a", "authored_at": "2026-10-20T09:00:00Z",
           "team_tags": ["research"], "project_tags": ["model-evaluation"], "is_simulated": True,
           "content": "Two more evaluators join the model-evaluation effort this period."}
    r.call("document_ingested", "POST", "/api/documents", headers=IMPORTER, json_body=doc,
           schema="DocumentIngestResult", expect=201, description="new corpus document stored as version 1")
    r.call("document_duplicate", "POST", "/api/documents", headers=IMPORTER, json_body=doc,
           schema="DocumentIngestResult", expect=200,
           description="identical content and metadata again: created=false, nothing changes")
    r.call("usage_daily", "GET", "/api/usage/daily", schema="DailyUsageResponse", expect=200,
           params={"scope_type": "team", "scope_id": "research", "start_date": "2026-10-19",
                   "end_date_exclusive": "2026-10-22"},
           description="bounded UTC observed daily ledger; exact simulated costs, separate included notional, "
                       "unknown token telemetry and missing days never become known zero")


def scenario_addition(r: Recorder) -> None:
    b = r.call(None, "POST", "/api/proposals", headers=DROID, schema="ProposalOut", expect=201, description="",
               json_body=_addition("Add 50k prioritizing research evaluation and engineering continuation."))
    r.call("decision_applied_addition", "POST", f"/api/proposals/{b['id']}/decision",
           headers={**APPROVER, "Idempotency-Key": "approve-addition-1"},
           json_body={"outcome": "approve", "rationale": "Leadership approved 50k of new funds for this period."},
           schema="DecisionOut", expect=201, description="approved addition: 95k/80k/75k, total 250k, version 1 -> 2")
    r.call("budget_state_after_addition", "GET", "/api/budget", schema="BudgetState", expect=200,
           description="version 2 after outcome B")


def scenario_agent(r: Recorder) -> None:
    """FakeDroidRunner: interpret the corpus, then draft outcome B; nothing is applied."""
    r.call("agent_run_interpret", "POST", "/api/agent/runs", headers=ANALYST,
           json_body={"task_type": "interpret_corpus"}, schema="AgentRunOut", expect=201,
           description="fake runner reads the corpus, flags the superseded research thread, records cited signals")
    r.call("agent_run_propose_addition", "POST", "/api/agent/runs", headers=ANALYST,
           json_body={"task_type": "propose_allocation",
                      "params": {"mode": "addition", "amount": "50000.00", "prioritize": "research"}},
           schema="AgentRunOut", expect=201,
           description="fake runner drafts outcome B (+50k: research +35k, engineering +15k) as pending_review")
    r.call("agent_run_propose_transfer", "POST", "/api/agent/runs", headers=ANALYST,
           json_body={"task_type": "propose_allocation", "params": {"mode": "transfer", "prioritize": "research"}},
           schema="AgentRunOut", expect=201,
           description="fake runner drafts outcome A (product -> research 25k, product -> engineering 5k)")
    answer = r.call("agent_run_answer_question", "POST", "/api/agent/runs", headers=ANALYST,
                    json_body={"task_type": "answer_question"}, schema="AgentRunOut", expect=201,
                    description="fake runner compares allocation, recorded spend and projections with period, "
                                "units, coverage and projection labels")
    r.call("agent_runs", "GET", "/api/agent/runs", schema="AgentRunList", expect=200,
           description="recent runs, newest first, each with its step log and events")
    r.call("agent_run_detail", "GET", f"/api/agent/runs/{answer['id']}", schema="AgentRunOut", expect=200,
           description="one run by id with its step log, events and findings")
    r.call("agent_run_answer_with_chart", "POST", "/api/agent/runs", headers=ANALYST,
           json_body={"task_type": "answer_question", "params": {"chart": {"kind": "spend_vs_allocation"}}},
           schema="AgentRunOut", expect=201,
           description="answer_question with params.chart: the read-only build_chart_spec tool runs and the "
                       "Vega-Lite spec is attached as output.charts[0]")


def scenario_agent_sdk_unavailable(r: Recorder) -> None:
    import os

    saved = os.environ.pop("FACTORY_API_KEY", None)  # the fixture documents the no-key case
    try:
        r.call("error_runner_unavailable", "POST", "/api/agent/runs", headers=ANALYST,
               json_body={"task_type": "interpret_corpus"}, schema="ErrorBody", expect=503,
               description="DROID_RUNNER=sdk without FACTORY_API_KEY: 503, no silent fallback to the fake runner")
    finally:
        if saved is not None:
            os.environ["FACTORY_API_KEY"] = saved


def scenario_rejection(r: Recorder) -> None:
    p = r.call(None, "POST", "/api/proposals", headers=APPROVER, schema="ProposalOut", expect=201, description="",
               json_body=_addition("Requesting new funds for evaluation."))
    r.call("error_self_approval", "POST", f"/api/proposals/{p['id']}/decision",
           headers={**APPROVER, "Idempotency-Key": "self-approve-1"},
           json_body={"outcome": "approve", "rationale": "approving my own request"}, schema="ErrorBody",
           expect=403, description="the requester cannot approve its own proposal")
    r.call("decision_rejected", "POST", f"/api/proposals/{p['id']}/decision",
           headers={**APPROVER_2, "Idempotency-Key": "reject-1"},
           json_body={"outcome": "reject", "rationale": "No new money this period; revisit after launch."},
           schema="DecisionOut", expect=201, description="rejected; budget stays version 1 at 60k/80k/60k")
    r.call("budget_state_after_rejection", "GET", "/api/budget", schema="BudgetState", expect=200,
           description="unchanged version 1 after a rejection")


def scenario_forecast_unavailable(r: Recorder) -> None:
    r.call("forecast_unavailable", "GET", "/api/forecasts", schema="ForecastResult", expect=200,
           description="availability unavailable, empty projections (never zero), reason given")
    r.call("overview_forecast_unavailable", "GET", "/api/overview", schema="Overview", expect=200,
           description="spend and budget still present; projected fields null")
    r.call("spend_summary_forecast_unavailable", "GET", "/api/spend/summary", schema="SpendSummary",
           expect=200, description="spend summary is unaffected by the forecast provider")
    r.call("chart_projection_unavailable", "GET", "/api/charts/projection_vs_allocation", schema="ChartSpecOut",
           expect=200, description="forecast unavailable: allocation rows only, no projection rows (never zero), "
                                   "title and notes say projections are unavailable")


def scenario_imports(r: Recorder) -> None:
    from app.seed.northstar import SPEND_FILE

    raw = SPEND_FILE.read_bytes()
    form = {"source_kind": "northstar_billing", "source_label": "Northstar billing export (simulated)"}
    r.call("import_result", "POST", "/api/imports", headers=IMPORTER, form=form,
           files={"file": (SPEND_FILE.name, raw, "text/csv")}, schema="ImportResult", expect=201,
           description="first import of the simulated billing export")
    r.call("import_duplicate", "POST", "/api/imports", headers=IMPORTER, form=form,
           files={"file": (SPEND_FILE.name, raw, "text/csv")}, schema="ImportResult", expect=200,
           description="same bytes again: status duplicate, nothing added")


INCOMPLETE_CSV = (
    "record_id,occurred_at,source_account,provider,model,cost_category,value_kind,amount,unit\n"
    "ns-extra-001,2026-10-18T00:00:00Z,ws-shared-sandbox,openai,gpt,direct_api,simulated,1200.00,USD\n"
)


def _codex_reset_session() -> str:
    def snap(ts: str, i: int, o: int) -> dict:
        usage = {"input_tokens": i, "cached_input_tokens": 0, "output_tokens": o, "reasoning_output_tokens": 0}
        return {"timestamp": ts, "type": "event_msg", "payload": {"type": "token_count", "info": {
            "total_token_usage": {**usage, "total_tokens": i + o}, "last_token_usage": usage}}}

    lines = [
        {"timestamp": "2026-10-19T09:00:00Z", "type": "session_meta", "payload": {"id": "sess-contract-1"}},
        {"timestamp": "2026-10-19T09:00:00Z", "type": "turn_context", "payload": {"model": "gpt-5-codex"}},
        snap("2026-10-19T09:05:00Z", 1000, 200),
        snap("2026-10-19T09:10:00Z", 1000, 200),  # repeated cumulative snapshot -> delta 0
        snap("2026-10-19T09:20:00Z", 2500, 500),
        snap("2026-10-19T09:30:00Z", 300, 50),  # counter decreased -> reset
    ]
    return "\n".join(json.dumps(x) for x in lines) + "\n"


def scenario_incomplete(r: Recorder) -> None:
    r.call("import_unmapped_account", "POST", "/api/imports", headers=IMPORTER,
           form={"source_kind": "northstar_billing"},
           files={"file": ("sandbox.csv", INCOMPLETE_CSV.encode(), "text/csv")}, schema="ImportResult",
           expect=201, description="record from an account with no team mapping -> unattributed + warning")
    r.call("import_codex_counter_reset", "POST", "/api/imports", headers=IMPORTER,
           form={"source_kind": "codex_sessions", "source_account": "codex-research-laptops"},
           files={"file": ("rollout.jsonl", _codex_reset_session().encode(), "application/jsonl")},
           schema="ImportResult", expect=201,
           description="real Codex format: repeated snapshot adds 0, a counter decrease is flagged as reset")
    r.call("spend_summary_incomplete", "GET", "/api/spend/summary", schema="SpendSummary", expect=200,
           description="unattributed bucket + counter reset -> coverage partial; company total includes unattributed")
    r.call("coverage_incomplete", "GET", "/api/coverage", schema="CoverageReport", expect=200,
           description="partial coverage with notes")
    r.call("chart_spend_vs_allocation_incomplete", "GET", "/api/charts/spend_vs_allocation", schema="ChartSpecOut",
           expect=200, description="partial coverage: unattributed spend is its own column (no allocation); "
                                   "plotted dollars are simulated; real sample token rows noted, not plotted")


def scenario_revision(r: Recorder) -> None:
    """A reviewer replaces Droid's draft with smaller lines; the original becomes `revised`."""
    original = r.call(None, "POST", "/api/proposals", headers=DROID, schema="ProposalOut", expect=201,
                      description="", json_body=_transfer("Move 30k from product to research and engineering."))
    revised = r.call("proposal_revised", "POST", f"/api/proposals/{original['id']}/revise", headers=ANALYST,
                     schema="ProposalOut", expect=201,
                     json_body={**_transfer("Reviewer keeps 10k of the move in product until the launch date is "
                                            "confirmed."),
                                "lines": [{"from_team": "product", "to_team": "research", "amount": "20000.00"}]},
                     description="replacement draft (pending_review) with revises_proposal_id -> the original")
    r.call("proposal_revised_original", "GET", f"/api/proposals/{original['id']}", schema="ProposalOut",
           expect=200, description="the original: status revised, replaced_by_proposal_id -> the replacement")
    r.call("error_decide_revised_original", "POST", f"/api/proposals/{original['id']}/decision",
           headers={**APPROVER, "Idempotency-Key": "approve-original-1"},
           json_body={"outcome": "approve", "rationale": "approving the old lines"}, schema="ErrorBody",
           expect=409, description="a revised proposal can no longer be decided (proposal_not_pending)")
    r.call("decision_applied_revised", "POST", f"/api/proposals/{revised['id']}/decision",
           headers={**APPROVER, "Idempotency-Key": "approve-revised-1"},
           json_body={"outcome": "approve", "rationale": "Revised transfer matches the confirmed plans."},
           schema="DecisionOut", expect=201, description="the replacement approved: research 80k, product 60k")


def scenario_forecast_partial(r: Recorder) -> None:
    """A fourth active team without a placeholder projection: availability partial."""
    from app.db.models import Team

    s = r.client.app.state.session_factory()
    try:
        s.add(Team(id="marketing", name="Marketing", active=True, created_at=FROZEN_AT))
        s.commit()
    finally:
        s.close()
    r.call("forecast_partial", "GET", "/api/forecasts", schema="ForecastResult", expect=200,
           description="availability partial: projections for three teams, missing_teams [marketing], reason")
    r.call("overview_forecast_partial", "GET", "/api/overview", schema="Overview", expect=200,
           description="partial forecast: marketing projected null; projected_total null (not a partial sum)")


def scenario_charts(r: Recorder) -> None:
    """Vega-Lite v5 chart specs built from backend data; budget history after outcome A is applied."""
    r.call("chart_kinds", "GET", "/api/charts", schema="ChartKindList", expect=200,
           description="chart kinds with their metrics and defaults")
    r.call("chart_spend_vs_allocation", "GET", "/api/charts/spend_vs_allocation", schema="ChartSpecOut",
           expect=200, description="grouped bars: allocation (planned) vs recorded spend (simulated) per team")
    r.call("chart_spend_vs_allocation_remaining", "GET", "/api/charts/spend_vs_allocation",
           params={"team": "research", "metric": "remaining"}, schema="ChartSpecOut", expect=200,
           description="one team, metric remaining: allocation minus recorded spend (15k for research)")
    r.call("chart_projection_vs_allocation", "GET", "/api/charts/projection_vs_allocation", schema="ChartSpecOut",
           expect=200, description="grouped bars: allocation vs placeholder projection (simulated, not a model); "
                                   "no forecast snapshot is persisted")
    r.call("chart_spend_by_cost_category", "GET", "/api/charts/spend_by_cost_category", schema="ChartSpecOut",
           expect=200, description="stacked bars by cost category; included usage is not plotted (notional in notes)")
    p = r.call(None, "POST", "/api/proposals", headers=DROID, schema="ProposalOut", expect=201, description="",
               json_body=_transfer("Shift product headroom to research evaluation and engineering continuation."))
    r.call(None, "POST", f"/api/proposals/{p['id']}/decision",
           headers={**APPROVER, "Idempotency-Key": "chart-approve-transfer-1"},
           json_body={"outcome": "approve", "rationale": "Matches the approved research plan and the launch update."},
           schema="DecisionOut", expect=201, description="")
    r.call("chart_budget_history", "GET", "/api/charts/budget_history", schema="ChartSpecOut", expect=200,
           description="lines per team across versions 1 -> 2, each point linked to the decision that saved it")
    r.call("error_unknown_chart_kind", "GET", "/api/charts/burn_rate", schema="ErrorBody", expect=404,
           description="unknown chart kind: 404 unknown_chart_kind with the supported kinds")
    r.call("error_chart_invalid_request", "GET", "/api/charts/budget_history",
           params={"metric": "spend"}, schema="ErrorBody", expect=422,
           description="metric not supported by the kind: 422 validation_failed, reason unknown_metric")


SCENARIOS: list[tuple[str, Scenario, dict]] = [
    ("main", scenario_main, {}),
    ("addition", scenario_addition, {}),
    ("rejection", scenario_rejection, {}),
    ("forecast_unavailable", scenario_forecast_unavailable, {"forecast_provider": "unavailable"}),
    ("forecast_partial", scenario_forecast_partial, {}),
    ("revision", scenario_revision, {}),
    ("imports", scenario_imports, {"seed_kwargs": {"include_spend": False}}),
    ("incomplete", scenario_incomplete, {}),
    ("agent", scenario_agent, {}),
    ("charts", scenario_charts, {}),
    ("agent_sdk_unavailable", scenario_agent_sdk_unavailable, {"droid_runner": "sdk"}),
]


def build_fixtures() -> dict[str, dict]:
    out: dict[str, dict] = {}
    for name, fn, kwargs in SCENARIOS:
        _run(name, fn, out, **kwargs)
    return out


def build_openapi() -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        app = create_app(Settings(db_path=Path(tmp) / "openapi.db"))
        try:
            return app.openapi()
        finally:
            app.state.engine.dispose()


def _dump(data: Any) -> str:
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def render(fixtures: dict[str, dict] | None = None, openapi: dict | None = None) -> dict[str, str]:
    """Relative path -> file content for everything the export writes."""
    fixtures = build_fixtures() if fixtures is None else fixtures
    files = {"openapi.json": _dump(build_openapi() if openapi is None else openapi)}
    index = []
    for name in sorted(fixtures):
        fx = fixtures[name]
        files[f"fixtures/{name}.json"] = _dump(fx)
        index.append({"name": name, "file": f"{name}.json", "scenario": fx["scenario"], "schema": fx["schema"],
                      "method": fx["request"]["method"], "path": fx["request"]["path"], "status": fx["status"],
                      "description": fx["description"]})
    files["fixtures/index.json"] = _dump({"generated_with": {"frozen_clock": FROZEN_AT.isoformat(),
                                                             "ids": "sequential per scenario"},
                                          "fixtures": index})
    return files


def write(out_dir: Path, files: dict[str, str]) -> None:
    fixtures_dir = out_dir / "fixtures"
    fixtures_dir.mkdir(parents=True, exist_ok=True)
    expected = {Path(p).name for p in files if p.startswith("fixtures/")}
    for stale in fixtures_dir.glob("*.json"):
        if stale.name not in expected:
            stale.unlink()
    for rel, content in files.items():
        (out_dir / rel).write_text(content, encoding="utf-8")


def diff(out_dir: Path, files: dict[str, str]) -> list[str]:
    problems = []
    for rel, content in files.items():
        path = out_dir / rel
        if not path.exists():
            problems.append(f"missing: {rel}")
        elif path.read_text(encoding="utf-8") != content:
            problems.append(f"changed: {rel}")
    expected = {Path(p).name for p in files if p.startswith("fixtures/")}
    for extra in sorted((out_dir / "fixtures").glob("*.json")):
        if extra.name not in expected:
            problems.append(f"unexpected: fixtures/{extra.name}")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--check", action="store_true", help="compare instead of writing; exit 1 on drift")
    args = parser.parse_args(argv)
    files = render()
    if args.check:
        problems = diff(args.out, files)
        for p in problems:
            print(p)
        print("contract up to date" if not problems else f"{len(problems)} contract file(s) out of date")
        return 1 if problems else 0
    write(args.out, files)
    print(f"wrote {len(files)} files to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
