# Backend and agent design

Status: implementation design, 2026-10-24. Owner: backend + Factory agent workstream (Devin).
Authoritative product spec: `docs/ai-spend-master-plan.md` (§2-4, §6, §8, §9), `docs/backend-plan.md`,
`docs/factory-agent-plan.md`, `docs/forecasting-plan.md`. This file never restates those plans; it
turns them into modules, tables, schemas, endpoints, fixtures, and tests. Every later backend/agent
step follows this file. If this design and the plans disagree, the plans win and this file is fixed.

## 0. Boundaries (parallel work, no conflicts)

- This workstream only writes under `backend/` and `agent/`. No UI code. No forecasting models.
- Frontend consumes `backend/contract/fixtures/*.json` and the REST API below. Fixture shapes are the
  contract; changing one is an integration change that must be announced to the frontend owner.
- Forecasting plugs in behind `ForecastProvider` (§6). Backend ships only a placeholder provider.
- Factory Droid has no API key yet. Everything runs on `FakeDroidRunner` by default; the real SDK
  runner is loaded only when explicitly configured and credentials exist in the environment.
- Nothing here transfers vendor credits, buys compute, or enforces provider limits. Every allocation
  is an internal planning record.

## 1. Settled implementation choices

| Choice | Decision | Rationale |
|---|---|---|
| Stack | Python 3.13, FastAPI, Pydantic v2, SQLAlchemy 2 (sync), SQLite, pytest | Small, testable, one process |
| DB path | env `BACKEND_DB_PATH`, default `backend/data/app.db` (gitignored by `backend/.gitignore`) | Tests use a tmp file per test |
| Port | env `BACKEND_PORT`, default `8787` | |
| CORS | allow `http://localhost:*` and `http://127.0.0.1:*` (regex), no credentials | Frontend dev servers |
| Money | `decimal.Decimal`, quantized to `0.01`, `ROUND_HALF_EVEN` never applied silently: input with more than 2 decimals is rejected | No float anywhere |
| Money on the wire | JSON **string** (`"60000.00"`) | JS clients cannot corrupt it |
| Money in SQLite | `MoneyType` TypeDecorator storing canonical string; float bind raises `TypeError` | SQLite has no decimal |
| Unit | `USD` for the Northstar example; `unit` field on every amount-bearing response; only `USD` accepted for budgets in v1 | Internal-credit unit stays open per plan |
| Period | One planning period `2026-P1` (label "Northstar planning period", 2026-10-01..2026-12-31). Consumers read period from responses, never hard-code it | Plan leaves horizon open |
| Identity | Demo headers `X-Actor-Id`, `X-Actor-Role`; **not authentication**, labeled as such in `/meta` | Bounded-authority checks are real; identity is simulated |
| Roles | `finance_approver`, `finance_analyst`, `droid_agent`, `importer` | |
| Clock / ids | Injected `Clock` and `IdFactory` (`app/core/clock.py`), frozen in tests and fixture export | Deterministic fixtures |
| Error envelope | `{"error": {"code": str, "message": str, "details": {...}}}` for every 4xx/5xx | Frontend can branch on `code` |

## 2. Package layout

```
backend/
  pyproject.toml            # package "northstar-backend"; [dev] extra: pytest, httpx
  .gitignore                # .venv/, data/, __pycache__/, *.db
  README.md                 # run/test instructions, real-vs-simulated table, Droid usage
  docs/design.md            # this file
  data/                     # runtime SQLite (gitignored)
  app/
    main.py                 # create_app(settings) -> FastAPI; CORS; error handlers; routers
    config.py               # Settings (pydantic-settings-free: dataclass from os.environ)
    core/
      money.py              # Money helpers: parse_money(str|Decimal), quantize, MoneyType
      clock.py              # Clock, FrozenClock, IdFactory (uuid4 / sequential in tests)
      errors.py             # DomainError(code, status, message, details) + handler
      actors.py             # Actor dataclass, get_actor dependency, require_role()
    db/
      base.py               # DeclarativeBase, engine/session factory from BACKEND_DB_PATH
      models.py             # all ORM entities (§3)
      session.py            # get_session dependency, transaction helpers
    schemas/                # Pydantic v2 API models (§4), one module per handoff
      common.py             # MoneyStr, Unit, ValueKind, CostCategory, Coverage, ErrorBody
      spending.py  budget.py  documents.py  signals.py  forecasts.py
      proposals.py  decisions.py  imports.py  agent.py  meta.py
    services/
      teams.py              # mapping resolution source_account -> team (or unattributed)
      imports.py            # import pipeline: hash, parse, dedupe, cumulative->delta
      parsers/
        northstar_csv.py    # simulated Northstar billing export (CSV)
        codex_sessions.py   # cumulative token telemetry (JSONL) - real-sample format
      spending.py           # summaries, totals, coverage; included usage never added
      budget.py             # current state, version history, snapshots
      proposals.py          # build/validate addition|transfer, compute before/after
      decisions.py          # approve/reject/apply with optimistic lock + idempotency
      corpus.py             # documents, versions, supersedes chain, search
      signals.py            # signal ingest, citation verification, currency of citations
      forecasts.py          # calls ForecastProvider, never raises into callers
      agent_runs.py         # creates AgentRun, builds scoped toolbox, invokes DroidRunner
    providers/
      forecast.py           # ForecastProvider protocol, PlaceholderForecastProvider
    agent/
      runner.py             # DroidRunner protocol, AgentTask, AgentToolbox, RunnerUnavailable
      toolbox.py            # BackendToolbox: scoped read tools + draft tools (no decide)
      fake_runner.py        # FakeDroidRunner (deterministic)
      loader.py             # select runner from env DROID_RUNNER=fake|sdk
    api/
      routes_meta.py  routes_teams.py  routes_imports.py  routes_spending.py
      routes_budget.py  routes_forecasts.py  routes_documents.py  routes_signals.py
      routes_proposals.py  routes_decisions.py  routes_agent.py  routes_admin.py
    seed/
      northstar.py          # seed(session): teams, mappings, envelope v1, spend, corpus
      corpus/*.md           # the six Northstar documents (§3.8), front-matter metadata
      spend/northstar_export.csv
    contract/
      export.py             # python -m app.contract.export -> writes contract/fixtures
  contract/fixtures/*.json  # §7
  tests/                    # §8
agent/
  README.md                 # where/how Droid is used at runtime; scoped tools; fake vs sdk
  northstar_droid/
    __init__.py
    sdk_runner.py           # SdkDroidRunner(DroidRunner): Factory Droid SDK; lazy import
    tool_manifest.json      # tool names, descriptions, JSON schemas (read + draft only)
    prompts/
      interpret_corpus.md   # cite exact quotes; mark superseded/conflicting/informal
      propose_allocation.md # draft only; addition vs transfer; never claim saved
```

`agent/` is importable via `pytest` `pythonpath = [".", "../agent"]` and by `app/agent/loader.py`
(which adds `../agent` to `sys.path` only when `DROID_RUNNER=sdk`). The SDK runner depends on the
protocol in `app/agent/runner.py`; the backend never imports the Factory SDK at module import time.

## 3. Persistence entities (SQLAlchemy 2)

All tables have `id` (string uuid unless noted) and `created_at` (UTC). Money columns use `MoneyType`.

### 3.1 `planning_periods`
`id` (`"2026-P1"`), `label`, `starts_on`, `ends_on`.

### 3.2 `teams`
`id` slug (`research|product|engineering`), `name`, `active`. Pseudo-team `unattributed` is **not**
a row; it is a summary bucket for records with `team_id IS NULL`.

### 3.3 `team_mappings`
`source_kind` (`northstar_billing|codex_sessions|...`), `source_account` (provider workspace /
project / key label), `team_id` FK, `effective_from`, `created_by`. Unique
(`source_kind`,`source_account`,`effective_from`). Provider accounts never imply ownership: an
unmapped account yields `team_id = NULL` and shows as `unattributed` with a coverage warning.

### 3.4 `import_batches`
`source_kind`, `source_label`, `filename`, `content_hash` (sha256 of raw bytes), `status`
(`imported|duplicate|failed`), `duplicate_of_batch_id` nullable, `record_count`,
`skipped_duplicate_records`, `unmapped_record_count`, `error_details` JSON, `imported_by`,
`value_kind_default`. Unique (`source_kind`,`content_hash`) over rows with `status='imported'`
(partial unique index). Re-posting identical bytes returns the existing batch with
`status: "duplicate"` and inserts nothing.

### 3.5 `usage_records`
| column | notes |
|---|---|
| `import_batch_id` FK | provenance |
| `source_kind`, `source_record_key` | natural key from source; **unique together** - overlapping files with different hashes still cannot double count |
| `source_account` | raw provider grouping |
| `team_id` FK nullable | resolved via mapping at import; re-resolved on mapping change |
| `period_id` FK, `occurred_at` | |
| `provider`, `model`, `stream_key` | `stream_key` identifies a cumulative counter stream (e.g. session id) |
| `input_tokens`, `cached_input_tokens`, `output_tokens`, `reasoning_tokens` | **deltas** (ints, nullable) |
| `cumulative_snapshot` JSON nullable | raw counter as reported, kept for audit |
| `counter_reset` bool | delta computed after a counter decrease |
| `amount` Money nullable, `unit` | `NULL` amount = usage without known cost |
| `value_kind` | `measured|estimated|reported|simulated` |
| `cost_category` | `subscription_fee|included_usage|billable_overage|direct_api|unpriced_usage` |
| `counts_toward_spend` bool | computed: `False` for `included_usage` and `unpriced_usage`; never user-settable |
| `notional_value` Money nullable | e.g. list value of included usage; displayed, never summed into spend |

Cumulative rule (`services/imports.py::to_deltas`): records within a `stream_key` are sorted by
`occurred_at`; delta = current - previous cumulative; identical repeated snapshots give delta 0 and
are stored once (dedupe on `source_record_key = stream_key + counter hash`); a decrease is treated as
a reset (delta = current value, `counter_reset = True`, coverage warning).

### 3.6 `budget_envelopes`, `budget_allocations`, `budget_snapshots`
- `budget_envelopes`: `period_id` (unique), `unit`, `total_amount`, `state_version` int (starts 1,
  +1 on every applied decision, never decremented), `updated_at`.
- `budget_allocations`: `envelope_id`, `team_id`, `amount`; unique (`envelope_id`,`team_id`).
  Invariant checked after every write: `sum(allocations) == total_amount`.
- `budget_snapshots`: `envelope_id`, `state_version` (unique together), `total_amount`,
  `allocations` JSON (`{team_id: "amount"}`), `decision_id` nullable (NULL for seed v1). Immutable;
  this is the explainable history of every saved state.

### 3.7 `proposals`
| column | notes |
|---|---|
| `period_id`, `unit` | must match envelope |
| `action_type` | `addition|transfer` (never mixed; a mixed intent is two proposals) |
| `base_version` | envelope `state_version` the proposal was computed against |
| `envelope_increase` Money | `> 0` for addition, exactly `0.00` for transfer |
| `lines` JSON | addition: `[{to_team, amount}]`; transfer: `[{from_team, to_team, amount}]` |
| `before` / `after` JSON | `{total, allocations{team: amount}}` computed by backend, not trusted from client |
| `status` | `pending_review|applied|rejected|stale|revised` |
| `rationale` text, `evidence_refs` JSON | `[{kind: signal|document|forecast_snapshot|spend_summary, id, version?}]` |
| `created_by_actor`, `created_by_role` | requester |
| `origin` | `droid_run|finance_manual` + `agent_run_id` nullable |
| `revises_proposal_id`, `rebased_from_proposal_id` nullable | lineage |
| `warnings` JSON | non-blocking: allocation below recorded spend, forecast unavailable, cites superseded doc |

### 3.8 `decisions`
`proposal_id` FK, `outcome` (`approved_applied|rejected`), `actor_id`, `actor_role`, `rationale`
(required, non-empty), `evidence_refs` JSON, `idempotency_key` (unique), `request_fingerprint`
(sha256 of proposal id + outcome + rationale), `from_version`, `to_version` (null on reject),
`before`/`after` JSON, `decided_at`. One decision per proposal (unique `proposal_id`).

Stale attempts are not decisions; they are written to `decision_events` (`proposal_id`, `event`
= `stale_rejected|self_approval_blocked|role_blocked`, `actor_id`, `details`, `at`) so history
shows the catch.

### 3.9 `corpus_documents`
`doc_key` (stable logical id, e.g. `research-eval-plan`), `version` int, unique (`doc_key`,
`version`), `title`, `origin` (`upload|email_export|slack_export|seed`), `doc_type`
(`plan|update|correspondence|note`), `plan_status` (`approved|draft|informal|cancelled|n/a`),
`authored_at`, `effective_from`/`effective_to` nullable, `team_tags` JSON, `project_tags` JSON,
`author`, `content` text, `content_hash`, `supersedes_document_id` nullable FK,
`superseded_by_document_id` nullable (denormalized), `is_simulated` bool.
Re-uploading identical content for a `doc_key` is a no-op; changed content creates `version+1`.

Northstar seed corpus (all `is_simulated = true`):
1. `research-eval-plan` v1 - approved plan, 2026-10-08, expands model-evaluation work this period;
   explicitly supersedes doc 2.
2. `research-timeline-thread` v1 - email thread, 2026-09-03, older timeline (eval push next period);
   `superseded_by` doc 1.
3. `product-launch-plan` v1 - plan, 2026-08-20, launch milestone in current period.
4. `product-launch-plan` v2 - update, 2026-10-14, moves milestone to the following period;
   supersedes v1.
5. `engineering-platform-note` v1 - note, 2026-10-12, work continues through current period.
6. `marketing-ideas-slack` v1 - informal Slack suggestion (`plan_status = informal`), no approval.

### 3.10 `context_signals` and `signal_citations`
- `context_signals`: `team_id` nullable, `project`, `summary`, `change_type`
  (`expansion|reduction|continuation|timing_shift|other`), `applies_from`/`applies_to`,
  `status` (`current|superseded|conflicting|informal|cancelled`), `uncertainty` text (required),
  `produced_by` (`droid_fake|droid_sdk|finance`), `agent_run_id` nullable, `superseded_by_signal_id`.
- `signal_citations`: `signal_id`, `document_id` (a specific version), `quote` text,
  `char_start`, `char_end`. On ingest the backend verifies `content[char_start:char_end] == quote`
  (fallback: exact substring search sets offsets); otherwise 422 `citation_not_found`.
  Response computes `citation_currency` = `current|superseded` from the cited document.
  A signal with `status=current` whose citations are **all** superseded is rejected
  (422 `signal_cites_superseded_only`).

### 3.11 `forecast_snapshots`
Persisted copy of a provider result used as evidence: `provider`, `availability`, `payload` JSON,
`fetched_at`. Proposals and decisions cite snapshots, so a later forecast change cannot rewrite why a
decision was made.

### 3.12 `agent_runs` and `agent_run_steps`
`agent_runs`: `task_type` (`interpret_corpus|propose_allocation|answer_question`), `input` JSON,
`runner_kind` (`fake|sdk`), `status` (`running|succeeded|failed|unavailable`), `output` JSON,
`error`, `started_at`, `finished_at`. `agent_run_steps`: `run_id`, `seq`, `tool`, `args` JSON,
`result_summary`, `at` - the visible work record; only tools actually invoked are recorded.

## 4. API schemas (Pydantic v2) mirrored to the shared-handoff table

All models `model_config = ConfigDict(extra="forbid")` on input. `MoneyStr` = annotated `Decimal`
that rejects floats, >2 decimals, NaN/Inf, and serializes as string.

| Handoff (master plan §3) | Response schema | Key fields |
|---|---|---|
| Spending history and current snapshot | `SpendSummary`, `TeamSpend`, `SpendRecordOut` | `period`, `unit`, per team `recorded_spend`, `by_cost_category`, `by_value_kind`, `included_usage_notional` (display only), `unpriced_tokens`; `unattributed`; `company_total`; `coverage{status: complete|partial|missing, unmapped_records, counter_resets, spend_record_count, last_record_at, notes[]}`; `data_labels{simulated: bool, real_sample: bool}` |
| Readable company material | `DocumentSummary`, `DocumentDetail` | `id`, `doc_key`, `version`, `title`, `origin`, `doc_type`, `plan_status`, `authored_at`, `effective_*`, `team_tags`, `project_tags`, `supersedes`, `superseded_by`, `is_simulated`, `content` (detail only) |
| Relevant company context | `ContextSignalIn`, `ContextSignalOut`, `CitationOut` | `team`, `project`, `summary`, `change_type`, `applies_from/to`, `status`, `uncertainty`, `citations[{document_id, doc_key, version, quote, char_start, char_end, citation_currency}]`, `produced_by` |
| Projections and supported scenarios | `ForecastResult`, `TeamProjection` | `provider`, `availability: available|partial|unavailable`, `reason`, `target_period`, `basis: full_period_total|remaining`, `projections[{team, amount, unit, assumptions[], uncertainty?}]`, `value_kind: "simulated"`, `method_label` |
| Current internal budgets | `BudgetState` | `period`, `unit`, `envelope_total`, `state_version`, `allocations[{team, amount, recorded_spend, remaining, coverage_status}]`, `updated_at`, `last_decision_id`, `spend_coverage{status, unattributed_spend, unattributed_records, notes[]}` (recorded/remaining are attributed spend to date) |
| Proposed allocation change | `ProposalCreate` (discriminated union on `action_type`), `ProposalOut` | `AdditionCreate{envelope_increase, lines[{to_team, amount}]}`, `TransferCreate{lines[{from_team,to_team,amount}]}`, plus `base_version`, `rationale`, `evidence_refs`; out adds `before`, `after`, `deltas{team: signed}`, `status`, `warnings`, `requester` |
| Finance decision and saved result | `DecisionCreate`, `DecisionOut`, `DecisionHistoryItem` | in: `outcome: approve|reject`, `rationale`, `evidence_refs`; out: `id`, `proposal_id`, `outcome`, `actor{id, role}`, `decided_at`, `from_version`, `to_version`, `before`, `after`, `replayed: bool`, `budget_state` (post-decision) |

Supporting: `ImportResult`, `MetaOut` (`period`, `unit`, `runner_kind`, `forecast_provider`,
`identity_mode: "demo_headers_unauthenticated"`, `real_vs_simulated[]`), `AgentRunCreate`,
`AgentRunOut`, `ErrorBody`.

## 5. REST endpoints (prefix `/api`)

| Method | Path | Role | Purpose |
|---|---|---|---|
| GET | `/health` | any | liveness |
| GET | `/meta` | any | period, unit, runner/provider modes, real-vs-simulated labels |
| GET | `/teams` | any | teams |
| GET | `/team-mappings` | any | mapping table |
| PUT | `/team-mappings` | finance_* | upsert mapping; re-resolves `team_id` on affected records |
| POST | `/imports` | importer, finance_* | multipart file + `source_kind`; idempotent by content hash and record key |
| GET | `/imports`, `/imports/{id}` | any | batch provenance |
| GET | `/coverage?period=` | any | completeness per team + company, unattributed bucket, contributing batches |
| GET | `/spend/summary?period=` | any | team + company totals, coverage; never blocked by forecast |
| GET | `/spend/records?team=&value_kind=&cost_category=&batch=` | any | record drill-down |
| GET | `/budget?period=` | any | current `BudgetState` |
| GET | `/budget/history?period=` | any | all `budget_snapshots` with linked decisions |
| GET | `/forecasts?period=` | any | `ForecastResult` (200 even when unavailable) |
| GET | `/overview?period=` | any | spend summary + budget + forecast in one call; forecast section may be unavailable |
| GET | `/documents?team=&project=&q=&include_superseded=true` | any | corpus list / keyword search |
| GET | `/documents/{id}` | any | full content + version links |
| GET | `/documents/by-key/{doc_key}/versions` | any | version chain |
| POST | `/documents` | finance_*, importer | upload/new version |
| GET | `/signals?team=&status=` | any | context signals with citation currency |
| GET | `/signals/{id}` | any | signal + resolved citations |
| POST | `/signals` | droid_agent, finance_* | verified ingest |
| POST | `/proposals` | droid_agent, finance_* | create; backend computes before/after; 422 on invalid |
| GET | `/proposals?status=`, `/proposals/{id}` | any | review; GET re-checks staleness and reports `is_stale` |
| POST | `/proposals/{id}/decision` | finance_approver only | header `Idempotency-Key` required; approve applies atomically, reject leaves state |
| POST | `/proposals/{id}/rebase` | droid_agent, finance_* | for `stale`: new `pending_review` proposal on current version, same intent |
| POST | `/proposals/{id}/revise` | finance_* | new proposal with changed lines; original -> `revised` |
| GET | `/decisions`, `/decisions/{id}` | any | decision history: who, when, why, evidence, before/after, version |
| POST | `/agent/runs` | finance_* | start a Droid task (fake by default); 503 `runner_unavailable` if sdk lacks credentials |
| GET | `/agent/runs/{id}` | any | output + step log |
| POST | `/admin/reset` | any, only if `BACKEND_ALLOW_RESET=1` | drop + reseed for demos |

Decision algorithm (`services/decisions.py::decide`), in one transaction:
1. Lookup `idempotency_key`. If found: same fingerprint -> return stored decision with
   `replayed: true` (200); different fingerprint -> 409 `idempotency_key_reused`.
2. Role must be `finance_approver` else 403 `role_forbidden` (Droid can never decide).
3. Outcome `approve` and the actor is a requester -> 403 `self_approval_forbidden`. Requesters are the
   authors of every proposal in the revise/rebase lineage plus the `initiated_by` of any Droid run that
   drafted or reused one of them.
   (A requester may still reject its own proposal; that changes no allocation.)
4. Proposal status must be `pending_review` else 409 `proposal_not_pending`.
5. Reject: write decision, status `rejected`, budget untouched.
6. Approve: `UPDATE budget_envelopes SET state_version = base+1 ... WHERE id=? AND state_version = base_version`;
   0 rows -> mark proposal `stale` only if it is still `pending_review` (a concurrent approver that already
   applied it yields 409 `proposal_not_pending`), write `decision_events(stale_rejected)`, 409 `stale_proposal`.
   The proposal's own status change is a compare-and-set (`... WHERE status='pending_review'`), so a revise
   that lands mid-decision makes the decision fail with 409 `proposal_not_pending`
   with `details{base_version, current_version, current_allocations}`. Otherwise re-validate lines
   against current allocations (no negative results), write allocations, snapshot, decision,
   status `applied`, assert envelope invariant, commit.

Validation (`services/proposals.py`), each a distinct `validation_failed.details.reasons[]` code:
`unknown_team`, `non_positive_amount`, `too_many_decimals`, `float_not_allowed`, `currency_mismatch`,
`period_mismatch`, `same_team_transfer`, `transfer_with_envelope_change`,
`addition_lines_do_not_sum_to_increase`, `negative_allocation_result`, `base_version_in_future`,
`empty_lines`. Transfers are zero-sum by construction (each line debits `from_team`, credits
`to_team`); the after-total must equal before-total. Additions: after-total = before + increase.

## 6. Interfaces

```python
# app/providers/forecast.py
class ForecastProvider(Protocol):
    name: str
    def get_forecast(self, period_id: str, team_ids: Sequence[str]) -> ForecastResult: ...

class PlaceholderForecastProvider:
    """Shared Northstar placeholder projections. NOT a model."""
    def __init__(self, mode: Literal["available", "unavailable"] = "available"): ...
    # available: research 85000.00, product 50000.00, engineering 65000.00, basis full_period_total,
    #   value_kind simulated, method_label "shared placeholder (not a forecast model)"
    # unavailable: availability "unavailable", reason "forecast provider not connected", projections []
```
Selected by env `FORECAST_PROVIDER=placeholder|unavailable` (default `placeholder`).
`services/forecasts.py` wraps every call: exceptions or timeouts -> `unavailable` result with the
error as `reason`; it never raises into spend/budget endpoints and never substitutes zero.

```python
# app/agent/runner.py
class AgentTask(BaseModel):
    type: Literal["interpret_corpus", "propose_allocation", "answer_question"]
    instruction: str
    params: dict  # e.g. {"mode": "addition", "amount": "50000.00", "prioritize": "research"}

class AgentToolbox(Protocol):          # the ONLY capabilities a runner gets
    def list_documents(self, **filters) -> list[DocumentSummary]: ...
    def get_document(self, document_id: str) -> DocumentDetail: ...
    def search_documents(self, q: str) -> list[DocumentSummary]: ...
    def get_spend_summary(self) -> SpendSummary: ...
    def get_budget_state(self) -> BudgetState: ...
    def get_forecast(self) -> ForecastResult: ...
    def save_signal(self, signal: ContextSignalIn) -> ContextSignalOut: ...   # draft-level write
    def draft_proposal(self, p: ProposalCreate) -> ProposalOut: ...           # pending_review only
    # no decide/apply tool exists

class DroidRunner(Protocol):
    kind: Literal["fake", "sdk"]
    def run(self, task: AgentTask, tools: AgentToolbox) -> AgentRunOutput: ...

class RunnerUnavailable(Exception): ...
```
`BackendToolbox` records every call as an `agent_run_steps` row and acts as `droid_agent`.
`FakeDroidRunner` is deterministic: `interpret_corpus` calls `list_documents`/`get_document` and saves
four signals (research expansion `current`; old research timeline `superseded`; product timing_shift
`current` citing v2 and noting v1; engineering continuation `current`) plus the marketing item as
`informal`, all with exact quotes. `propose_allocation` reads budget/spend/forecast/signals and drafts
outcome A (transfer) or B (addition, prioritize research). When the forecast is unavailable it still
drafts and adds the warning `forecast_unavailable`. It never reports a change as saved.
`loader.py`: `DROID_RUNNER=fake` (default) -> Fake; `sdk` -> `agent/northstar_droid/sdk_runner.py`,
which reads the key from the environment only and raises `RunnerUnavailable` if absent. No silent
fallback from sdk to fake: the API returns 503 `runner_unavailable` so the demo never misrepresents
which runner ran. `runner_kind` is on every run and in `/meta`.

## 7. Contract fixtures (`backend/contract/fixtures/*.json`)

Generated by `python -m app.contract.export` with `FrozenClock(2026-10-24T12:00:00Z)` and sequential
ids against a fresh seeded DB; each file is `{"request": {...}, "status": int, "response": {...}}`.

| File | Case |
|---|---|
| `meta.json` | modes + real-vs-simulated labels |
| `teams.json` | three teams |
| `budget_state_initial.json` | v1: 60k/80k/60k, envelope 200k |
| `spend_summary.json` | 45k/20k/30k = 95k, by category/value kind, coverage complete |
| `spend_summary_incomplete.json` | unmapped account + counter reset -> `partial`, `unattributed` bucket |
| `spend_records_research.json` | drill-down incl. included_usage with `counts_toward_spend:false` |
| `import_result.json` | first import |
| `import_duplicate.json` | same bytes again -> `duplicate`, 0 new records |
| `forecast_available.json` | placeholder 85k/50k/65k, `full_period_total`, simulated |
| `forecast_unavailable.json` | `availability: unavailable`, empty projections, reason |
| `overview.json` | combined, forecast available |
| `overview_forecast_unavailable.json` | spend + budget present, forecast unavailable |
| `documents.json` | six docs with supersedes links |
| `document_detail_research_plan.json` | full content |
| `document_versions_product_launch.json` | v1 -> v2 chain |
| `signals.json` | current / superseded / informal signals with citation currency |
| `agent_run_interpret.json` | fake run output + step log |
| `agent_run_propose_addition.json` | fake run drafting outcome B |
| `proposal_transfer_pending.json` | outcome A, base_version 1, before/after |
| `proposal_addition_pending.json` | outcome B, envelope_increase 50k |
| `decision_applied_transfer.json` | approved; 85k/50k/65k, total 200k, v1 -> v2 |
| `decision_applied_addition.json` | approved; 95k/80k/75k, total 250k, v1 -> v2 |
| `decision_replayed.json` | same Idempotency-Key -> `replayed: true`, version unchanged |
| `decision_rejected.json` | rejected; budget still v1 60k/80k/60k |
| `budget_state_after_transfer.json`, `budget_state_after_addition.json` | v2 states |
| `decision_history.json` | history after one applied decision |
| `error_stale_proposal.json` | 409 `stale_proposal` with base/current version |
| `proposal_rebased.json` | rebase of the stale proposal onto current version |
| `error_self_approval.json` | 403 `self_approval_forbidden` |
| `error_role_forbidden_droid_decides.json` | 403 `role_forbidden` |
| `error_validation_negative_allocation.json` | 422, transfer exceeding source allocation |
| `error_validation_addition_mismatch.json` | 422, lines do not sum to increase |
| `error_idempotency_key_reused.json` | 409 |
| `error_citation_not_found.json` | 422 |
| `error_runner_unavailable.json` | 503 when `DROID_RUNNER=sdk` without key |

## 8. Test plan

Every test uses a fresh tmp SQLite DB, FrozenClock, FakeDroidRunner, and `TestClient`.
Files under `backend/tests/`.

### 8.1 Acceptance checks from `docs/backend-plan.md` -> named tests

| # | Acceptance check (verbatim intent) | Test(s) |
|---|---|---|
| 1 | Importing the same source twice must not double spending | `test_imports.py::test_reimport_same_file_is_duplicate_and_totals_unchanged`, `test_imports.py::test_overlapping_file_with_new_hash_dedupes_by_record_key` |
| 2 | Repeated cumulative telemetry must not masquerade as new usage | `test_cumulative.py::test_repeated_cumulative_snapshot_yields_zero_delta`, `test_cumulative.py::test_monotonic_counters_sum_to_final_value`, `test_cumulative.py::test_counter_decrease_flagged_as_reset_and_partial_coverage` |
| 3a | Known sample totals match displayed company/team totals | `test_spending.py::test_northstar_seed_totals_45_20_30_95`, `test_spending.py::test_overview_totals_match_budget_and_spend_endpoints` |
| 3b | Missing data remains visibly incomplete | `test_spending.py::test_unmapped_account_goes_to_unattributed_with_partial_coverage`, `test_spending.py::test_team_without_records_reports_missing_not_zero_complete` |
| 4a | A cited context signal leads back to its source | `test_signals.py::test_signal_citation_resolves_to_document_version_and_exact_quote`, `test_signals.py::test_citation_quote_not_in_document_rejected` |
| 4b | Distinguishes a changed plan from its earlier version | `test_corpus.py::test_new_version_links_supersedes_and_keeps_old_version`, `test_signals.py::test_citation_currency_marks_superseded_document`, `test_signals.py::test_current_signal_citing_only_superseded_docs_rejected` |
| 5 | A rejected proposal must leave allocations unchanged | `test_decisions.py::test_reject_leaves_allocations_and_version_unchanged` |
| 6a | Approved addition preserves arithmetic | `test_decisions.py::test_apply_addition_outcome_b_95_80_75_total_250` |
| 6b | Approved redistribution preserves arithmetic | `test_decisions.py::test_apply_transfer_outcome_a_85_50_65_total_200` |
| 6c | Applies once | `test_decisions.py::test_same_idempotency_key_replays_without_second_apply`, `test_decisions.py::test_second_decision_on_applied_proposal_is_409_not_pending`, `test_decisions.py::test_reused_key_with_different_payload_is_409` |
| 6d | Persists | `test_persistence.py::test_applied_decision_survives_app_restart_same_db_file` |
| 6e | Remains explainable afterward | `test_decisions.py::test_decision_history_has_actor_role_time_rationale_evidence_before_after`, `test_budget.py::test_history_snapshots_link_to_decisions` |
| 7 | A proposal based on outdated budgets must be reviewed against current state before application | `test_stale.py::test_apply_against_changed_version_is_409_stale_and_budget_unchanged`, `test_stale.py::test_stale_attempt_recorded_in_decision_events`, `test_stale.py::test_rebase_creates_new_pending_proposal_requiring_fresh_review`, `test_stale.py::test_get_proposal_reports_is_stale` |
| 8 | Unavailable forecasts must not prevent access to measured spending | `test_forecasts.py::test_unavailable_mode_returns_200_unavailable_not_zero`, `test_forecasts.py::test_spend_and_overview_work_when_provider_unavailable`, `test_forecasts.py::test_provider_exception_becomes_unavailable` |

### 8.2 Additional spec checks (master plan §2-4, §6, §9)

| Spec point | Test |
|---|---|
| Addition vs transfer stay distinguishable | `test_proposals.py::test_action_type_persisted_and_transfer_has_zero_envelope_increase`, `test_proposals.py::test_transfer_with_envelope_change_rejected` |
| Requester cannot approve own request | `test_authority.py::test_self_approval_forbidden` |
| Droid may only read and draft | `test_authority.py::test_droid_role_cannot_decide`, `test_agent.py::test_toolbox_has_no_decide_capability` |
| Arithmetic validation | `test_proposals.py::test_transfer_exceeding_source_allocation_rejected`, `::test_addition_lines_must_sum_to_increase`, `::test_unknown_team_rejected`, `::test_float_and_three_decimal_amounts_rejected` |
| Money is Decimal | `test_money.py::test_money_type_rejects_float_bind`, `::test_money_serializes_as_string` |
| Included usage never extra expense | `test_spending.py::test_included_usage_excluded_from_spend_but_shown_as_notional` |
| Cost categories / value kinds kept apart | `test_spending.py::test_breakdown_by_cost_category_and_value_kind` |
| Provider account does not imply team | `test_teams.py::test_mapping_change_reattributes_records` |
| Superseded research thread caught | `test_agent.py::test_fake_interpret_marks_old_research_thread_superseded` |
| Agent work record is real | `test_agent.py::test_run_steps_match_toolbox_calls` |
| Agent never claims saved | `test_agent.py::test_propose_run_leaves_pending_proposal_and_budget_unchanged` |
| SDK runner honest failure | `test_agent.py::test_sdk_mode_without_key_returns_503_runner_unavailable` |
| Agent works without forecast | `test_agent.py::test_propose_with_forecast_unavailable_adds_warning` |
| Contract fixtures | `test_contract.py::test_every_fixture_validates_against_schema`, `test_contract.py::test_export_is_deterministic_and_matches_committed_fixtures` |
| CORS / port config | `test_app.py::test_cors_allows_localhost_origin`, `test_app.py::test_settings_read_env` |

## 9. Implementation order

1. Skeleton: pyproject, config, money, db, errors, `/health`, `/meta`, CI-able pytest.
2. Seed + teams/mappings + budget state + spend summary (checks 3, 8 partially).
3. Imports with hash/record-key dedupe and cumulative deltas (checks 1, 2).
4. Corpus + signals with citation verification (check 4).
5. Proposals, decisions, stale/idempotency/authority (checks 5, 6, 7).
6. ForecastProvider + overview (check 8).
7. DroidRunner, FakeDroidRunner, toolbox, agent runs; SDK runner stub in `agent/`.
8. Contract export + fixtures + README real-vs-simulated table.

## 10. Real vs simulated (README must carry this)

| Component | Status |
|---|---|
| Northstar spend, budgets, corpus | simulated (`value_kind=simulated`, `is_simulated=true`) |
| Codex session parser | real format; any real sample imported is `measured` tokens, `unpriced_usage` unless priced |
| Projections | placeholder, not a model; `unavailable` mode available |
| Droid | `FakeDroidRunner` deterministic until a Factory key exists; `runner_kind` always reported |
| Identity | demo headers, not authentication; authority rules themselves are enforced |

## 11. Ingestion implementation notes (as built)

Spend (`services/imports.py`, `services/parsers/`, `services/teams.py`, `services/coverage.py`):
- Source kinds: `northstar_billing` (CSV or JSON `{"records": [...]}`, simulated) and `codex_sessions`
  (real Codex JSONL; only session id, model, timestamps and `total_token_usage` are read). Codex files
  do not name an account, so the uploader passes `source_account`; without it records are unattributed.
- A batch with any invalid row fails as a whole (422 `import_failed`, nothing inserted, batch kept with
  grouped errors). Failed batches do not block a corrected retry. Row codes: `amount_required`,
  `included_usage_with_charge`, `unpriced_usage_with_amount`, `negative_amount`, `too_many_decimals`,
  `float_not_allowed`, `unknown_cost_category`, `unknown_value_kind`, `unsupported_unit`,
  `timezone_required`, `invalid_timestamp`, `conflicting_duplicate_record_id`, `missing_columns`, ...
- Non-fatal warnings (grouped by code with row samples): `team_column_ignored` (a `team` column is never
  trusted), `unmapped_source_account`, `duplicate_row_in_file`, `record_key_conflict` (key restated with
  different values: existing record kept), `outside_known_periods`, `counter_reset`,
  `out_of_order_snapshot`, `truncated_last_line`, `token_count_without_session`.
- Cumulative streams: `source_record_key = stream_key#sha256(counters)[:16]`; the baseline for a new
  file is the last stored snapshot of the stream, so a re-exported growing session adds only new usage.
  A snapshot older than the last stored one is skipped (rewriting stored deltas would alter provenance).
  Limitation: snapshots outside every planning period are dropped, so a later file's baseline cannot use
  them; within one file they still serve as the baseline.
- Concurrent identical uploads: the loser of the partial-unique-index race is retried and returns
  `duplicate`.
- Coverage: a team with no records is `missing`; resets or any unattributed records in the period make
  teams `partial` (unattributed spend could belong to any team); company is `complete` only if all teams
  are. Exposed at `GET /api/coverage` for the spending summary to embed.

Corpus (`services/corpus.py`): content identical to any existing version of a `doc_key` is a no-op
(an old export can never become current again); a new version dated before the current one is 422
`version_predates_current`; explicit cross-key supersedes must target an older document of another key
that is not already superseded (`supersedes_newer_document`, `already_superseded`, `supersedes_same_key`).
Search: all terms must match (title, content, tags, doc_key), "quoted phrases" supported, results carry
`is_current` and exact `char_start/char_end` offsets into stored content for citations.
`parse_markdown_document` reads `---` front matter (`supersedes: key@version`) for the seed corpus.

## 12. Budgets, proposals and decisions (as built)

Code: `services/budget.py`, `services/proposals.py`, `services/decisions.py`, routes `routes_budget.py`,
`routes_proposals.py`, `routes_decisions.py`. Differences from and additions to §3.6-§3.8 / §5:
- `services/budget.py::create_envelope` creates the v1 state + snapshot (for the seed module); there is no
  HTTP endpoint for it. `BudgetState` also carries `allocated_total` and per-team `remaining`
  (allocation minus recorded spend; included/unpriced usage never counts).
- Drafting with `base_version` older than the current version is refused up front with 409
  `stale_base_version` (details: current version and figures), so a draft always starts from a state
  that can be applied. `base_version` newer than current is the 422 reason `base_version_in_future`.
- Extra 422 reason codes: `invalid_amount` (NaN/empty/non-numeric), `duplicate_line`,
  `addition_line_has_source`, `rationale_required`, `unknown_evidence` (cited document/signal/forecast
  snapshot must exist; a document `version` must match), `unknown_agent_run`. Non-blocking warnings:
  `allocation_below_recorded_spend`, `cites_superseded_document`, `cites_non_current_signal`,
  `forecast_unavailable`, `no_evidence_cited`, `team_both_debited_and_credited`.
- Decision check order: role (recorded as `role_blocked`) runs before the idempotency lookup, so a
  non-approver can never obtain a decision through the decision route. The request fingerprint also
  includes the deciding actor id.
- Separation of duties covers lineage: nobody who drafted the proposal or any proposal it was revised or
  rebased from may approve it. The rebasing/revising actor is the requester of the new draft.
- Rebase accepts a `stale` proposal or a `pending_review` one whose base is outdated (the original is then
  marked `stale`). If the intent no longer fits the current state, rebase returns the usual 422 reasons
  and creates nothing. Revise (finance only) accepts `pending_review` or `stale`; original -> `revised`.
- `GET /api/decision-events?proposal_id=` lists blocked attempts; `ProposalOut.blocked_attempts`,
  `replaced_by_proposal_id` and `decision_id` make each proposal's history readable on its own.
- A replayed decision returns 200 with `replayed: true`; `budget_state` in any decision response is the
  current saved state when the response was produced (`after` holds the post-decision values).

## 13. API, forecasts, signals, seed and contract (as built)

Code: `api/routes_{meta,spending,forecasts,signals,admin}.py`, `services/{spending,forecasts,overview,signals}.py`,
`providers/forecast.py`, `seed/`, `contract/export.py`. Differences from and additions to §4-§7:
- Spend: `SpendSummary.teams[]` embed their `coverage`; `attributed_total` (teams) and `company_total`
  (teams + unattributed + any inactive-team spend) are both given. `by_cost_category[cat].amount` is `null`
  for included/unpriced usage; `included_usage_notional` and `unpriced_tokens` are display-only.
  `/spend/records` validates filters (422 `unknown_team|unknown_value_kind|unknown_cost_category|unknown_batch`;
  `team=unattributed` selects unmapped records) and paginates (`offset`, `limit` <= 5000, `total`).
- Forecasts: `GET /forecasts` never writes. `POST /forecasts/snapshots` (droid_agent, finance_*) persists the
  current result as citable evidence; `GET /forecasts/snapshots/{id}`. `services/forecasts.get_forecast` runs the
  provider with a 5 s timeout and converts exceptions, timeouts, malformed output (incl. float money) and a
  wrong `target_period` into `unavailable`; unknown/duplicate/negative team projections are dropped and the
  result becomes `partial` with `missing_teams`. `create_app(forecast_provider=...)` injects a provider.
- Overview: `teams[]` gives `allocation`, `recorded_spend`, `remaining`, `projected`, `projected_minus_allocation`
  (null when unknown, never 0); `company.projected_total` only when every team is projected; a missing budget
  envelope yields `budget: null` + `budget_unavailable_reason` instead of an error.
- Signals: at least one citation is required; offsets are optional and corrected to the first exact occurrence
  (`offsets_corrected: true`); unknown document -> 422 `unknown_document`. `produced_by` is derived from the
  caller (finance roles -> `finance`; droid -> its agent run's runner kind, else the configured runner) and
  cannot be sent. `supersedes_signal_id` on create marks the older signal `superseded`. `PATCH` (finance only)
  changes `status`, `uncertainty`, `superseded_by_signal_id`; content/citations are immutable. `DELETE`
  (finance only) is refused with 409 `signal_in_use` once a proposal cites it or it is part of a supersede chain.
  `needs_review` flags a `current` signal whose cited documents have all since been superseded.
- Seed: `python -m app.seed` seeds an empty DB (idempotent). Spend goes through the normal import pipeline from
  `seed/spend/northstar_export.csv` (subscriptions + direct API + overage + included usage); the six corpus
  documents are ingested in authored order from `seed/corpus/*.md`. `POST /admin/reset` drops, recreates and
  reseeds only when `BACKEND_ALLOW_RESET=1` (else 403 `reset_disabled`).
- Contract: fixture files carry `name`, `scenario`, `description`, `schema` in addition to
  `request/status/response`; `fixtures/index.json` lists them. Six scenarios (main, addition, rejection,
  forecast_unavailable, imports, incomplete) each run against their own seeded DB, so ids restart per scenario.
  Agent-run fixtures are deferred to the Droid module. `ErrorBody` lives in `schemas/common.py`.

## 14. Droid agent (as built)

Code: `app/agent/{runner,tools,toolbox,fake_runner,loader}.py`, `app/services/agent_runs.py`,
`app/api/routes_agent.py`, `app/schemas/agent.py`, `agent/northstar_droid/{sdk_runner,sdk_tools}.py`.
Differences from and additions to §3.12 / §5 / §6:
- Tool names (shared by both runners): `search_corpus`, `read_document`, `get_spend_summary`, `get_budgets`,
  `get_forecast` (persists a citable snapshot), `list_signals`, `record_signal`, `draft_proposal`. One
  `draft_proposal` takes either action type. `tool_manifest.json` is generated from `app/agent/tools.py`.
- New table `agent_run_events` (`run_id`, `seq`, `type`, `source`, `data`, `at`) backs the SSE stream
  `GET /api/agent/runs/{id}/events` (replay + follow, `Last-Event-ID` / `?after=` resume). Event types are
  listed in `app/agent/runner.py::EVENT_TYPES`.
- `POST /api/agent/runs` (finance roles): `{task_type, instruction, params, wait}`; `wait=true` (default) 201
  after completion, `wait=false` 202 and a background thread (at most 2 concurrent, else 429 `runner_busy`).
  Params are validated up front (422 `unknown_team|non_positive_amount|invalid_params|unexpected_params`).
- The run row is written before the runner starts; 503 `runner_unavailable` still leaves an `unavailable`
  run. `output.proposal_ids/signal_ids` come from the toolbox, not the runner. `AgentRunOut.proposals`
  shows each draft's live status; `applied_changes` is always false.
- Droid's actor id is `droid:<run id>` (role `droid_agent`). The finance user who starts a run is recorded in
  `input.initiated_by` and counts as a requester of every draft that run produced (or reused), across the
  revise/rebase lineage, so they cannot approve it (403 `self_approval_forbidden`, `details.via_agent_run`).
- `create_app(droid_runner=...)` injects a runner (tests); otherwise the runner is resolved per run.

## 15. Seed planted-error pack and edge cases (as built)

Code: `app/seed/planted.py`, `app/seed/__main__.py` (`--with-planted`, `--check-planted`). Data: `backend/seed/planted/`;
expected outcomes: `backend/seed/answer_key.md`; edge-case catalogue: `docs/edge-cases.md`.
- The default seed and contract fixtures are unchanged (six documents, 95k spend). The pack is opt-in, so the
  frontend contract does not move.
- `load_planted` uses the normal import and corpus services (idempotent). `run_planted_checks` replays checks
  P0-P6 through the HTTP API on a temporary DB and compares them with the answer key. It never touches
  `BACKEND_DB_PATH`.
- The two planted documents are outside the fake runner's playbook. It reports `document_not_interpreted`
  for them instead of inventing signals.
- Tests: `tests/test_planted.py` (answer key, labels, CLI idempotency, edge-case doc references) and
  `tests/test_seed_e2e.py` (seed CLI twice -> totals unchanged; fake Droid outcome B -> approve -> 95k/80k/75k,
  envelope 250k, persisted).
