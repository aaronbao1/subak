# Frontend alignment: Next.js app vs backend API

Status: analysis and compat-layer design, 2026-10-24. Nothing here is implemented yet.

Sources compared:
- Frontend (on `origin/main`, read via `git show`): `docs/frontend-integration.md`,
  `frontend/src/lib/contracts/index.ts` (the frontend's source of truth), `frontend/src/lib/data/{client,http-client,mock-client,index}.ts`,
  `frontend/src/fixtures/index.ts`, `frontend/src/components/dashboard/{derive,status}.ts`.
- Backend (this branch): `backend/contract/openapi.json`, `backend/app/api/routes_*.py`, `backend/app/schemas/*.py`,
  `backend/app/services/*`, `docs/design.md` §4-§15.

The frontend calls 15 endpoints on `${NEXT_PUBLIC_API_URL}`. It sends **no** `X-Actor-*` headers and no
`Idempotency-Key`. It expects plain camelCase JSON, money as JSON numbers, and errors as
`{"error": "<plain English>"}`. None of the 15 paths exists on the backend in that shape: the
names differ (`/api/budget` vs `/api/budgets`), the shapes differ (snake_case, money as strings, one
`ForecastResult` vs `Forecast[]`), and the error envelope differs (`error` is an object, not a string).
The frontend would show `[object Object]` as the error text. A translation layer is required.

## 1. Endpoint mapping

| # | Method | Frontend path | Query / body | Frontend type | Backend source (route -> service) | Fit |
|---|---|---|---|---|---|---|
| 1 | GET | `/api/company` | - | `Company` | `GET /api/meta` (`routes_meta`) + `GET /api/spend/summary` `data_labels` | derived |
| 2 | GET | `/api/teams` | - | `Team[]` | `GET /api/teams` (`routes_teams`, `TeamOut`) | partial (no color/lead/description) |
| 3 | GET | `/api/spending` | `teamId?`, `from?`, `to?` (ISO dates, inclusive) | `SpendingRecord[]` | `services/spending.list_records` + `services/coverage` | aggregated + lossy |
| 4 | GET | `/api/budgets` | - | `Budget[]` | `GET /api/budget` (`BudgetState`) | reshape |
| 5 | GET | `/api/forecasts` | - | `Forecast[]` | `GET /api/forecasts` (`ForecastResult`, `services/forecasts.get_forecast`) | reshape, no low/high |
| 6 | GET | `/api/context` | `teamId?` | `ContextItem[]` | `GET /api/signals` (`services/signals.list_signals`) + cited documents | derived, empty until Droid runs |
| 7 | GET | `/api/documents` | - | `CompanyDocument[]` (with `body`) | `services/corpus` list + `get_document` per item | reshape (list needs content) |
| 8 | GET | `/api/documents/:id` | - | `CompanyDocument` | `GET /api/documents/{id}` (`DocumentDetail`) | reshape |
| 9 | GET | `/api/proposals` | - (newest first) | `AllocationProposal[]` | `services/proposals.list_proposals` + `proposal_out` (oldest first today) | reshape + resolve citations |
| 10 | GET | `/api/proposals/:id` | - | `AllocationProposal` | `GET /api/proposals/{id}` | reshape |
| 11 | GET | `/api/decisions` | - (newest first) | `Decision[]` | `services/decisions.list_decisions` + `decision_out` (oldest first today) | reshape |
| 12 | GET | `/api/threads/:threadId` | UI uses `main` | `AssistantMessage[]` | **none** (no thread store) | new state needed |
| 13 | POST | `/api/threads/:threadId/messages` | `{content}` | `AssistantMessage[]` (user echo + reply) | `services/agent_runs.start_run` (`POST /api/agent/runs`, `wait=true`) | free text -> typed task, new |
| 14 | POST | `/api/proposals/:id/apply` | `{note?}` | `Decision` | `services/decisions.decide(outcome="approve")` (`POST /api/proposals/{id}/decision`) | identity + idempotency adapted |
| 15 | POST | `/api/proposals/:id/reject` | `{}` | `AllocationProposal` | `services/decisions.decide(outcome="reject")`, then `proposal_out` | identity adapted |

Backend features the frontend does not use (yet): coverage report, imports, budget history, overview,
document versions/search, signal curation, rebase/revise, decision events, agent run SSE stream,
forecast snapshots, `/api/meta` real-vs-simulated labels.

## 2. Field-by-field mapping

Conventions used by every mapper below:
- **Money**: backend `Decimal` -> JSON number at the compat boundary only. Whole values go out as
  integers (`60000`), otherwise as a float rounded to 2 dp. No number from the frontend ever enters the
  backend as money (the frontend sends none except inside chat text, see #13).
- **Unit**: `"USD"` -> `"usd"`. The backend accepts only USD today; `credits`/`tokens` are never emitted
  as money.
- **Period**: `{id, label, starts_on, ends_on}` -> `{start, end, label}` (ISO dates, inclusive on both
  sides in both systems).
- **Versions**: `state_version: int` -> `version: String(n)`; `base_version` -> `basedOnBudgetVersion: String(n)`.
- **Ids**: backend ids are passed through unchanged (`doc_000003`, `prop_000001`, `sig_000001`,
  `research`). They are opaque strings to the frontend. Synthesized ids are marked below.

### #1 `Company`
| Frontend | Backend | Notes |
|---|---|---|
| `id` | constant `"northstar"` | not stored; config constant |
| `name` | constant `"Northstar Software"` | not stored (seed docstring + `/meta` detail only) |
| `isDemo` | `spend_summary.data_labels.simulated` OR any `real_vs_simulated[].status != "real"` | true for the seed |
| `budgetUnit` | `meta.unit` lowercased | `"usd"` |
| `currentPeriod` | `meta.period` | `{start:"2026-10-01", end:"2026-12-31", label:"Northstar planning period"}` |

### #2 `Team`
| Frontend | Backend | Notes |
|---|---|---|
| `id`, `name` | `TeamOut.id`, `.name` | inactive teams filtered out |
| `color` | none | compat assigns `var(--chart-N)` by sorted index (the frontend's own tokens) |
| `description`, `lead` | none | omitted (optional) |

Pseudo-team: when the period has unattributed records, compat appends `{id:"unattributed", name:"Unattributed", color:"var(--muted-foreground)"}` so that money the company spent is not silently dropped from every chart (see gap G3).

### #3 `SpendingRecord`
The backend stores one row per source record (8 seed rows on 4 dates). The frontend wants one row per
team x day x component x provider. Compat groups `usage_records` for the current period by
`(team or "unattributed", occurred_at UTC date, cost_category, provider)` and sums `amount`.

| Frontend | Backend | Notes |
|---|---|---|
| `id` | synthesized `"{team}:{date}:{component}:{provider}"` | stable, not a DB id |
| `teamId` | `team_id` or `"unattributed"` | |
| `date` | `occurred_at` UTC date | `from`/`to` filter applied here (the backend has no date filter) |
| `component` | `cost_category`: `subscription_fee`->`subscription`, `included_usage`->`included_usage`, `billable_overage`->`extra_usage`, `direct_api`->`api` | `unpriced_usage` has no equivalent: rows omitted (G2) |
| `provider` | `provider` or `"unknown"` | |
| `amount` | sum of `amount` where `counts_toward_spend`; **`0` for `included_usage`** | the frontend sums every component into "spent" (`derive.ts::summarizeTeams`); emitting `notional_value` would double count (G1) |
| `unit` | `"usd"` | |
| `provenance` | `value_kind`: `reported`->`reported_charge`, `estimated`->`estimate`, `simulated`->`reported_charge`, `measured`->`usage_only` | a group mixing kinds takes the weakest (`estimate` over `reported_charge`); `simulated` has no frontend value (G7) |
| `source` | `import_batch.source_label`/`filename` + `"(simulated)"` when `value_kind=simulated`; included usage adds `"notional value $X not counted"` | human readable |
| `complete` | team coverage `status == "complete"` and no `counter_reset` in the group | backend coverage is per team, not per day (G4) |

### #4 `Budget`
| Frontend | Backend (`BudgetState`) |
|---|---|
| `teamId` | `allocations[].team` |
| `period` | `period` (mapped) |
| `allocated` | `allocations[].amount` (number) |
| `unit` | `unit` lowercased |
| `version` | `String(state_version)` |

Dropped: `envelope_total`, `recorded_spend`, `remaining`, `coverage_status`, `spend_coverage`, `last_decision_id`.

### #5 `Forecast`
One backend `ForecastResult` becomes one `Forecast` per active team.
| Frontend | Backend | Notes |
|---|---|---|
| `id` | synthesized `"fc-{team}-{target_period}"` | not a snapshot id; reading a forecast never writes |
| `teamId` | `projections[].team` | teams in `missing_teams` or absent -> `status:"unavailable"` |
| `period` | period row for `target_period` | |
| `status` | projection present -> `available`; else `unavailable` | `availability:"partial"` becomes per-team available/unavailable |
| `unavailableReason` | `reason` or `"no projection for this team"` | |
| `basis` | `full_period_total`->`full_period`, `remaining`->`remaining` | |
| `kind` | `"forecast"` | backend has no scenario flag |
| `origin` | provider `placeholder` -> `"placeholder"`, else `"forecasting_service"` | |
| `projected` | `projections[].amount` (number) | |
| `low`, `high` | none | omitted; the UI handles undefined (G6) |
| `unit` | `"usd"` | |
| `assumptions` | `projections[].assumptions` | |
| `limitations` | `[method_label, uncertainty]` + `reason` | |
| `generatedAt` | `generated_at`, else the response time | |

### #6 `ContextItem` (from context signals)
| Frontend | Backend (`ContextSignalOut`) | Notes |
|---|---|---|
| `id` | `id` | |
| `teamIds` | `[team]`, or `[]` when `team` is null (marketing brainstorm) | `teamId` filter: `team == teamId` |
| `title` | none | derived: first sentence of `summary`, max 90 chars (G5) |
| `summary` | `summary` | |
| `kind` | `doc_type` of the first cited document: `plan`->`plan`, `update`->`project_doc`, `note`->`project_doc`, `correspondence`->`correspondence` | `research_note` never produced |
| `effectiveFrom/To` | `applies_from/to` | |
| `expectedEffect` | `change_type`: `expansion`->`increase`, `reduction`->`decrease`, `continuation`->`neutral`, `timing_shift`/`other`->`unknown` | the product launch shift is "decrease" in the frontend fixture; the backend does not encode direction for a timing shift (G5) |
| `confidence` | none | derived from status + cited `plan_status`: current & approved -> `high`, current otherwise -> `medium`, informal/conflicting/superseded/cancelled -> `low`; labeled derived (G5) |
| `sources[]` | `citations[]`: `documentId`=`document_id`, `title`, `excerpt`=`quote`, `locator`=`"chars {char_start}-{char_end}"`, `date`=doc `authored_at` date, `kind` as above | quotes are verified verbatim by the backend |
| `uncertainty` | `uncertainty` (+ `"needs review"` when `needs_review`) | |
| `claimType` | `stated_plan` when status is current/superseded/cancelled and the doc is a plan or update; `interpretation` otherwise | `observed_event` never produced |
| `supersededBy` | `superseded_by_signal_id` | |
| `supersedes` | `supersedes_signal_ids` | |

### #7/#8 `CompanyDocument`
| Frontend | Backend (`DocumentDetail`) | Notes |
|---|---|---|
| `id`, `title` | `id`, `title` | each version is its own id (`product-launch-plan` v1 and v2) |
| `kind` | `doc_type` as in #6 | |
| `date` | `authored_at` date | |
| `teamIds` | `team_tags` | |
| `origin` | `upload`->"Uploaded document", `email_export`->"Email export", `slack_export`->"Slack export", `seed`->"Seeded demo document"; `" (simulated)"` when `is_simulated` | |
| `body` | `content` | the list endpoint needs it, so compat reads detail per document (6 docs; fine) |
| `supersededBy` | `superseded_by.id` | |

### #9/#10 `AllocationProposal`
| Frontend | Backend (`ProposalOut`) | Notes |
|---|---|---|
| `id` | `id` | |
| `kind` | `transfer`->`redistribute`, `addition`->`add_budget` | |
| `unit`, `period` | `unit`, period row for `period` | |
| `totalBefore`/`totalAfter` | `before.total`/`after.total` | |
| `addedAmount` | `envelope_increase` (additions only) | |
| `lines[]` | one per team in `before.allocations`: `{teamId, before, after}` | backend `lines` are movements (`from_team`/`to_team`/`amount`); compat uses the backend-computed before/after, so `sum(after) == totalAfter` holds |
| `rationale` | `rationale` | |
| `citations[]` | `evidence_refs`: signal -> its citations (as #6 `sources`); document -> `{documentId, title}`; forecast_snapshot/spend_summary -> not citations | |
| `createdAt` | `created_at` | |
| `status` | `pending_review` & !`is_stale` -> `proposed`; `pending_review` & `is_stale` -> `stale`; `applied`, `rejected`, `stale`, `revised` 1:1 | `pending` and `failed` are never produced (the backend validates at draft time) |
| `revisesProposalId` | `revises_proposal_id` (or `rebased_from_proposal_id`) | |
| `basedOnBudgetVersion` | `String(base_version)` | |
| `failureReason` | none | omitted |
| `forecastsReviewed` | `evidence_refs` of kind `forecast_snapshot` -> `GET /forecasts/snapshots/{id}` -> #5 mapping | the snapshot is what Droid actually cited |

Order: compat reverses to newest first.

### #11/#14 `Decision`
| Frontend | Backend (`DecisionOut`) | Notes |
|---|---|---|
| `id`, `proposalId` | `id`, `proposal_id` | |
| `action` | `approved_applied`->`applied`, `rejected`->`rejected` | |
| `kind` | `action_type` mapped | |
| `appliedAt` | `decided_at` | also set on rejections (frontend naming) |
| `appliedBy` | `actor.id` | the compat approver identity (G9) |
| `note` | `rationale` (finance's reason) | |
| `rationale` | proposal `rationale` | the frontend's `rationale` is the proposal's explanation |
| `lines[]` | from `before`/`after` (rejection: proposal `before`/`after`) | |
| `unit` | proposal `unit` | |
| `forecastsReviewed` | from `proposal_evidence_refs` forecast snapshots | |

### #12/#13 `AssistantMessage`
| Frontend | Backend | Notes |
|---|---|---|
| `id`, `threadId`, `role`, `createdAt` | new compat thread table | |
| `content` | user: the text sent. Assistant: run `summary` plus `assistant_text` event texts, prefixed with the interpreted intent (see §4.3) | markdown |
| `proposalId` | first of `AgentRunOut.proposals[].id` | proposal already retrievable via #9 |
| `citations` | citations of the signals in the run's `signal_ids` / the proposal's evidence | |
| `toolCalls[]` | `steps[]`: `{name: tool, summary: result_summary}` | one line each, real steps only |

## 3. Gaps and semantics conflicts

**G1. Included usage.** The frontend adds `included_usage` amounts into "spent". The backend never
does (`counts_toward_spend=false`; `notional_value` is display-only). Compat sends `amount: 0` and puts
the notional value in `source`. The "Included usage" bar will read $0, which is correct as cost but
looks like missing data. The frontend fixture models included usage as real cost, so its numbers
disagree with ours. This needs a decision from the frontend owner.

**G2. Unpriced usage and tokens.** Codex telemetry records have tokens and no dollar amount. The
frontend sums `amount` across rows without checking `unit`, so token rows would be added to dollars.
Compat omits them. The team's coverage then says partial, which surfaces as `complete:false`.

**G3. Unattributed spend.** The backend keeps unmapped spend in an `unattributed` bucket that counts
toward the company total. The frontend only aggregates rows whose `teamId` is a known team. Compat adds
an "Unattributed" pseudo-team whenever such spend exists. Without it the company total would be
understated with no warning.

**G4. Granularity and completeness.** The seed has 8 lump records on 4 dates, not a daily series, so
the daily chart will be sparse. Compat must not invent daily points. Completeness is tracked per team
for the period, so `complete:false` gets applied to every row of a partial team, not to specific days.

**G5. Context fields we do not store.** The backend has no `title`, no `confidence`, and no effect
direction for a `timing_shift`. Compat derives the first two and documents the rules. A timing shift
is sent as `unknown`, not `decrease`. Adding nullable `title` and `expected_effect` columns to
`context_signals` and the Droid `record_signal` tool would be the honest fix. **Signals are not seeded.**
`/api/context` stays empty until an `interpret_corpus` run happens. The fix is a
`python -m app.seed --with-signals` option that runs the fake runner once. A GET must not trigger a
run, because that writes data and spends credits under the SDK runner.

**G6. Forecast range.** There is no low/high and no scenario kind. The placeholder provider is labeled
`origin:"placeholder"`. Each team gets its own `Forecast` even though the backend produces one result.

**G7. Provenance vocabulary.** `simulated` has no frontend equivalent. Compat maps it to
`reported_charge` and labels it "(simulated)" in `source`. `Company.isDemo=true` is the main honesty
signal. `measured` maps to `usage_only`.

**G8. Money as numbers.** The backend sends decimal strings by design. Compat converts to numbers on
output only. Cent-level float error is possible in frontend sums, but all seed values are whole
dollars. No frontend number is ever parsed into backend money.

**G9. Identity and separation of duties.** The frontend sends no actor. The backend requires
`X-Actor-*` and forbids a requester from approving its own draft, including drafts from runs they
started. Compat uses two configured demo actors: `dashboard-analyst` (`finance_analyst`) starts chat
runs and `dashboard-approver` (`finance_approver`) applies and rejects. Because one person in the browser
acts as both, separation of duties is only nominal in the dashboard demo. If the request carries
`X-Actor-*` headers, compat uses them instead.

**G10. Apply semantics.**
- The backend requires a non-empty rationale. When `note` is missing, compat sends
  "Approved from the dashboard (no note given)". Reject sends "Rejected from the dashboard".
- The backend requires an `Idempotency-Key`. Compat uses `compat-{approve|reject}-{proposal_id}`.
  A retried click therefore replays and never double-applies.
- The frontend expects a second apply to fail. Compat checks `status` first. A replayed response
  also becomes 409 `"This proposal was already applied."`.
- Stale handling lines up: the backend returns 409 `stale_proposal` and marks the proposal stale,
  which is the frontend rule.

**G11. Error envelope.** The backend sends `{"error":{"code","message","details"}}`. The frontend wants
`{"error":"<plain English>"}`. Compat sends `{"error": message, "code": code}`, where `message` comes
from a per-code plain-English table (for example, `stale_proposal` -> "Budgets changed since this
proposal was prepared. Ask for a refreshed proposal.").

**G12. Assistant/chat endpoint.** This is the largest gap. The backend has typed agent runs
(`interpret_corpus`, `propose_allocation` with `mode/amount/prioritize`, `answer_question`). It has no
conversation and no persistence of free text. Compat needs (a) a thread store and (b) a rule that turns
free text into a typed task. The parse can be wrong, so every reply starts with what was understood
(for example, "Read as: add $50,000.00 to the envelope, prioritize Research"). Runs are synchronous
(`wait=true`). Under the SDK runner they can take up to `DROID_TIMEOUT_S` (120 s). The frontend fetch
has no timeout, so this works but will be slow. Droid still only drafts; nothing in compat can apply
from chat.

**G13. Ordering and ids.** The backend lists proposals and decisions oldest first, and compat reverses
them. Backend ids are not the frontend fixture's ids (`doc-q4-research-plan` vs `doc_000003`). That is
fine because the frontend never hard-codes ids.

**G14. Port.** The frontend comment suggests `http://localhost:8000`. The backend runs on 8787. CORS
already allows `localhost:3000`.

## 4. Compat layer design

### 4.1 Mounting
- Package `backend/app/compat/`: `router.py` (routes), `mappers.py` (pure functions, backend dicts ->
  frontend dicts), `threads.py` (thread store), `intent.py` (free text -> `AgentRunCreate`),
  `errors.py` (code -> plain English), `schemas.py` (Pydantic mirrors of the TS contract, camelCase,
  `extra="forbid"`, used as `response_model` so drift fails tests).
- `router = APIRouter(prefix="/compat/api", tags=["compat"])`, included in `create_app` after the
  existing routers. Frontend: `NEXT_PUBLIC_API_URL=http://localhost:8787/compat`. The frontend path
  `/api/company` then resolves to `/compat/api/company`. No frontend change is needed, and nothing
  collides with `/api/*`.
- Env `BACKEND_COMPAT` (default `1`). When it is `0`, the router is not mounted.
- Excluded from `contract/openapi.json` (`include_in_schema=False`), so the main contract and its
  check stay unchanged. Compat gets its own snapshot fixtures under `backend/contract/compat/`.

### 4.2 Rules
- Read routes call services directly (same session, clock, ids) and never write. In particular,
  `/forecasts` does not create snapshots and `/context` does not start runs.
- Errors: each compat route is wrapped so that `DomainError` and request-validation errors from compat
  paths are rendered by `errors.py`. The global handler is not changed.
- Money conversion happens only in `mappers.py::num(Decimal) -> int | float`. No float ever reaches a
  service.
- Writes: chat goes through `agent_runs.start_run` (analyst actor). Apply and reject go through
  `decisions.decide` (approver actor, deterministic idempotency key), with the pre-checks from G10.

### 4.3 Chat (`POST /compat/api/threads/{id}/messages`)
1. Store the user message.
2. `intent.parse(content)` returns one of:
   - `propose_allocation{mode:addition, amount, prioritize}` when the text mentions adding,
     additional, or more budget/funding plus an amount. The amount is parsed as a decimal string
     (`50k` -> `"50000.00"`). If there is no amount, compat asks rather than defaulting.
   - `propose_allocation{mode:transfer, prioritize}` for redistribute, rebalance, move, or reallocate.
   - `interpret_corpus` for "what changed" or "read the documents".
   - `answer_question` (instruction = the text) otherwise.
   The team named in the text becomes `prioritize`, defaulting to the most over-projected team.
3. Run with `wait=true`. Build the assistant message from the run (§2 #12/#13). On 503
   `runner_unavailable` or a failed run, reply with an assistant message that says so plainly instead
   of a 5xx, so the drawer still renders.
4. Store the assistant message with `run_id` and `proposal_id`. Return `[user, assistant]`.

Thread store: a new table `assistant_messages` (`id`, `thread_id`, `role`, `content`, `agent_run_id`,
`proposal_id`, `citations` JSON, `tool_calls` JSON, `created_at`), created on startup like the other
tables and wiped by `/api/admin/reset`. `GET /compat/api/threads/{id}` returns it oldest first, or `[]`.

### 4.4 Tests (planned, `backend/tests/test_compat.py`, FakeDroidRunner only)
- Every compat route validates against `compat/schemas.py`.
- Seed totals through compat: spent 45000/20000/30000, allocated 60000/80000/60000, projected
  85000/50000/65000.
- Included usage contributes 0 to spend. Unattributed spend appears under the pseudo-team.
- Chat "add 50k prioritizing research" -> proposal `add_budget` 95/80/75, total 250000.
  Apply -> `Decision.action=applied`. A second apply -> 409 with a string `error`. Budgets version "2".
- Stale: apply a transfer after the addition -> 409 with the plain-English stale message, and the
  proposal status becomes `stale`.
- Reject -> `rejected` with a `Decision{action:"rejected"}` and allocations unchanged.
- The compat chat actor cannot approve through `/api/proposals/{id}/decision` (self-approval still enforced).
- `/api/*` contract unchanged (`app.contract.export --check`).
