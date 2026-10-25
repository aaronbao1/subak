# Frontend alignment: Next.js app vs backend API

Status: compat layer implemented and caught up with the people-aware frontend contract (`e90b7f1`),
2026-10-24 (`backend/app/compat/`, served under `/compat/api`). §1-§4 are the original mapping design
(the field tables include the people-aware additions); §5 lists what is served and how it differs from
that design; §5.1 lists what the integration pass closed; §6 lists what the frontend owner still has to
decide. Build details for the integration pass: [`frontend-integration-design.md`](frontend-integration-design.md).

Sources compared:
- Frontend (on this branch, based on `main` `e90b7f1`; read only, never edited): `docs/frontend-integration.md`,
  `frontend/src/lib/contracts/index.ts` (the frontend's source of truth), `frontend/src/lib/data/{client,http-client,mock-client,index}.ts`,
  `frontend/src/lib/store.ts`, `frontend/src/components/person/derive.ts`,
  `frontend/src/components/assistant/assistant-drawer.tsx`, `frontend/src/components/allocation/{proposal-review,decision-log,proposal-card}.tsx`,
  `frontend/src/fixtures/{index,generate}.ts`.
- Backend (this branch): `backend/contract/openapi.json`, `backend/app/api/routes_*.py`, `backend/app/schemas/*.py`,
  `backend/app/services/*`, `docs/design.md` §4-§15.

The frontend calls 16 endpoints on `${NEXT_PUBLIC_API_URL}` (15 originally, plus `GET /api/people`). The
store loads 10 GETs with `Promise.all`, so a single non-200 means nothing renders. It sends **no**
`X-Actor-*` headers and no
`Idempotency-Key`. It expects plain camelCase JSON, money as JSON numbers, and errors as
`{"error": "<plain English>"}`. None of the original paths existed on the backend in that shape: the
names differ (`/api/budget` vs `/api/budgets`), the shapes differ (snake_case, money as strings, one
`ForecastResult` vs `Forecast[]`), and the error envelope differs (`error` is an object, not a string).
The frontend would show `[object Object]` as the error text. A translation layer is required.

## 1. Endpoint mapping

| # | Method | Frontend path | Query / body | Frontend type | Backend source (route -> service) | Fit |
|---|---|---|---|---|---|---|
| 1 | GET | `/api/company` | - | `Company` | `GET /api/meta` (`routes_meta`) + `GET /api/spend/summary` `data_labels` | derived |
| 2 | GET | `/api/teams` | - | `Team[]` | `GET /api/teams` (`routes_teams`, `TeamOut`) + people (for `lead`) | partial (color assigned, lead derived, no description) |
| 2a | GET | `/api/people` | - | `Person[]` | `services/people.list_people` (`GET /api/people`) | 1:1 reshape (new) |
| 3 | GET | `/api/spending` | `teamId?`, `from?`, `to?` (ISO dates, inclusive) | `SpendingRecord[]` | `services/spending.list_records` + `services/coverage` | aggregated per person and day |
| 4 | GET | `/api/budgets` | - | `Budget[]` | `GET /api/budget` (`BudgetState`) | reshape |
| 5 | GET | `/api/forecasts` | - | `Forecast[]` (team + person items, `daily`) | `GET /api/forecasts` (`ForecastResult` incl. `person_projections`, `services/forecasts`) | reshape, no low/high |
| 6 | GET | `/api/context` | `teamId?` | `ContextItem[]` | `GET /api/signals` (`services/signals.list_signals`, `include_company`) + cited documents | derived; seeded by `python -m app.seed` |
| 7 | GET | `/api/documents` | - | `CompanyDocument[]` (with `body`) | `services/corpus` list + `get_document` per item | reshape (list needs content) |
| 8 | GET | `/api/documents/:id` | - | `CompanyDocument` | `GET /api/documents/{id}` (`DocumentDetail`) | reshape |
| 9 | GET | `/api/proposals` | - (newest first) | `AllocationProposal[]` | `services/proposals.list_proposals` + `proposal_out` (oldest first today) | reshape + resolve citations |
| 10 | GET | `/api/proposals/:id` | - | `AllocationProposal` | `GET /api/proposals/{id}` | reshape |
| 11 | GET | `/api/decisions` | - (newest first) | `Decision[]` | `services/decisions.list_decisions` + `decision_out` (oldest first today) | reshape |
| 12 | GET | `/api/threads/:threadId` | UI uses `main` | `AssistantMessage[]` | **none** (no thread store) | new state needed |
| 13 | POST | `/api/threads/:threadId/messages` | `{content}` | `AssistantMessage[]` (user echo + reply) | `services/agent_runs.start_run` (`POST /api/agent/runs`, `wait=true`) | free text -> typed task, new |
| 14 | POST | `/api/proposals/:id/apply` | `{note?}` | `Decision` | `services/decisions.decide(outcome="approve")` (`POST /api/proposals/{id}/decision`) | identity + idempotency adapted |
| 15 | POST | `/api/proposals/:id/reject` | `{}` | `AllocationProposal` | `services/decisions.decide(outcome="reject")`, then `proposal_out` | identity adapted; also the UI's Dismiss on `stale` |

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
| `lead` | derived: name of the first active person on the team whose `role` ends in " lead" | omitted when no such person |
| `description` | none | omitted (optional) |

### #2a `Person` (`GET /people`, active people only, ordered by team then name)
| Frontend | Backend (`m.Person`) | Notes |
|---|---|---|
| `id`, `teamId`, `name` | `id`, `team_id`, `name` | e.g. `research-ava-chen` |
| `role`, `email`, `primaryTool` | `role`, `email`, `primary_tool` | omitted when null; emails are `first.last@northstar.example` |
| `integrations` | `integrations` (`slack`/`asana`/`monday`) | omitted when empty |

The seed has 15 fictional people, all `is_simulated=true`: research 6, product 4, engineering 5, each
with a role, a primary tool (Claude Code, Codex, Cursor, Anthropic API) and integrations. Spend is
attributed to a person only through a known email on the record's mapped team; the team never comes
from an email.

Pseudo-team: when the period has unattributed records, compat appends `{id:"unattributed", name:"Unattributed", color:"var(--muted-foreground)"}` so that money the company spent is not silently dropped from every chart (see gap G3).

### #3 `SpendingRecord`
The seed is a deterministic daily per-person series (`app/seed/daily_spend.py`, 616 rows, 2026-10-01
to the as-of date 2026-10-20) that sums exactly to 45,000 / 20,000 / 30,000. The frontend wants one row
per team x person x day x component x provider. Compat groups `usage_records` for the current period by
`(team or "unattributed", person or none, occurred_at UTC date, cost_category, provider)` and sums `amount`.

| Frontend | Backend | Notes |
|---|---|---|
| `id` | synthesized `"{team}:{person}:{date}:{component}:{provider}"`, or `"{team}:{date}:{component}:{provider}"` for a team-level row | stable, not a DB id |
| `teamId` | `team_id` or `"unattributed"` | |
| `personId` | `person_id` | omitted on team-level rows (included usage is team-level); person rows sum exactly to the team's counted spend |
| `date` | `occurred_at` UTC date | `from`/`to` filter applied here (the backend has no date filter) |
| `component` | `cost_category`: `subscription_fee`->`subscription`, `included_usage`->`included_usage`, `billable_overage`->`extra_usage`, `direct_api`->`api` | `unpriced_usage` has no equivalent: rows omitted (G2) |
| `provider` | `provider` or `"unknown"` | |
| `amount` | sum of `amount` where `counts_toward_spend`; **`0` for `included_usage`** | the frontend sums every component into "spent" (`derive.ts::summarizeTeams`); emitting `notional_value` would double count (G1) |
| `unit` | `"usd"` | |
| `provenance` | `value_kind`: `reported`->`reported_charge`, `estimated`->`estimate`, `simulated`->`reported_charge`, `measured`->`usage_only`; **included usage rows are always `usage_only`** (no charge of their own) | a group mixing kinds takes the weakest (`estimate` > `usage_only` > `reported_charge`); `simulated` has no frontend value (G7) |
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
One backend `ForecastResult` becomes one `Forecast` per active team, followed by one per active person
(`personId` set). Person items are the placeholder provider's proportional split of the team amount
(by spend to date, whole dollars), so person `projected` values sum exactly to the team's; the UI
separates the two by `personId`. A priced team-level remainder, if any, is named in the team's
`assumptions`. A team without a projection makes its people `unavailable` too.
| Frontend | Backend | Notes |
|---|---|---|
| `id` | synthesized `"fc-{team}-{target_period}"`, person items `"fc-{team}-{target_period}-{person}"` | not a snapshot id; reading a forecast never writes |
| `teamId` | `projections[].team` | teams in `missing_teams` or absent -> `status:"unavailable"` |
| `personId` | `person_projections[].person` | person items only |
| `daily` | `projections[].daily` / `person_projections[].daily`: `{date, projected}` | 72 points, 2026-10-21..2026-12-31 (the day after as-of), weekday-weighted; spend to date + `sum(daily)` == `projected` on the JSON numbers. No `low`/`high` |
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
| `limitations` | `[method_label, uncertainty]` + `reason`; person items add "person split is proportional to spend to date; not a person-level model" | |
| `generatedAt` | `generated_at`, else the response time | |

`forecastsReviewed` on proposals and decisions holds team-level forecasts only (the review UI finds them
by `teamId`).

### #6 `ContextItem` (from context signals)
| Frontend | Backend (`ContextSignalOut`) | Notes |
|---|---|---|
| `id` | `id` | |
| `teamIds` | `[team]`; company scope -> every active team; `[]` when a team-scope signal has no team (marketing brainstorm) | `teamId` filter: that team's signals **plus every company-scope signal** |
| `scope` | `scope` (`team` / `person` / `company`) | company scope has `team NULL` in the DB (CHECK constraint) |
| `personIds` | `person_ids` | person scope only, else `[]`; each id is a real person on the signal's team (validated when recorded) |
| `signal` | `signal_kind` (`project_deferred`, `project_accelerated`, `model_change`, `tool_change`, `out_of_office`, `onboarding`, `steady`) | omitted when the signal has none |
| `title` | `title` (recorded by Droid) | falls back to the first sentence of `summary`, max 90 chars |
| `summary` | `summary` | |
| `kind` | `doc_type` of the first cited document: `plan`->`plan`, `update`->`project_doc`, `note`->`project_doc`, `correspondence`->`correspondence` | `research_note` never produced |
| `effectiveFrom/To` | `applies_from/to` | |
| `expectedEffect` | `change_type`: `expansion`->`increase`, `reduction`->`decrease`, `continuation`->`neutral`, `other`->`unknown`; `timing_shift` -> `decrease` with `signal: project_deferred`, `increase` with `project_accelerated`, else `unknown` | |
| `confidence` | none | derived from status + cited `plan_status`: current & approved -> `high`, current otherwise -> `medium`, informal/conflicting/superseded/cancelled -> `low`; labeled derived (G5) |
| `sources[]` | `citations[]`: `documentId`=`document_id`, `title`, `excerpt`=`quote`, `locator`=`"chars {char_start}-{char_end}"`, `date`=doc `authored_at` date, `kind` as above, `integration` and `author` from the cited document | quotes are verified verbatim by the backend |
| `uncertainty` | `uncertainty` (+ `"needs review"` when `needs_review`) | |
| `claimType` | `observed_event` for `signal: onboarding`; `stated_plan` when status is current/superseded/cancelled and the doc is a plan or update; `interpretation` otherwise | |
| `supersededBy` | `superseded_by_signal_id` | |
| `supersedes` | `supersedes_signal_ids` | |

### #7/#8 `CompanyDocument`
| Frontend | Backend (`DocumentDetail`) | Notes |
|---|---|---|
| `id`, `title` | `id`, `title` | each version is its own id (`product-launch-plan` v1 and v2) |
| `kind` | `doc_type` as in #6 | |
| `date` | `authored_at` date | |
| `teamIds` | `team_tags` | |
| `origin` | from `integration` first ("Slack export", "Asana export", "monday.com export", "Email export"), else `upload`->"Uploaded document", `email_export`->"Email export", `slack_export`->"Slack export", `seed`->"Seeded demo document"; `" (simulated)"` when `is_simulated` | |
| `personIds` | `person_tags` (front matter, resolved to real people at load) | `[]` for team and company documents |
| `integration` | `integration` front matter, else from origin (`email_export`->`email`, `slack_export`->`slack`), else `document` | |
| `body` | `content` | the list endpoint needs it, so compat reads detail per document (13 docs; fine) |
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
| `appliedBy` | `actor.id`, labeled: `dashboard-approver` -> "Finance approver (demo)" | a header-supplied `X-Actor-Id` is shown as given (G9) |
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

**G4. Granularity and completeness.** *Granularity closed:* the seed is now a deterministic daily
per-person series (616 rows, Oct 1-20) with the same team totals, and forecasts carry `daily` points
from Oct 21. Compat still never invents points: every spend row is a stored record. *Still open:*
completeness is tracked per team for the period, so `complete:false` gets applied to every row of a
partial team, not to specific days.

**G5. Context fields we do not store.** *Mostly closed.* `context_signals` now stores `title`, `scope`,
`person_ids` and `signal_kind`, and Droid's `record_signal` tool takes them (invalid scope/person
combinations are refused as tool errors). A timing shift's direction comes from `signal_kind`
(`project_deferred` -> `decrease`, `project_accelerated` -> `increase`; any other timing shift stays
`unknown`). `confidence` is still derived (rules in §2 #6), and `title` falls back to the derived first
sentence for older signals. **Signals are seeded
(resolved):** `python -m app.seed` now runs the stand-in interpretation once on a fresh seed (an audited
`interpret_corpus` run; signals labeled `droid_fake`), `--live-signals` uses the real Droid instead
(no fallback) and `--no-signals` skips it. A GET still never triggers a run, because that writes data
and spends credits under the SDK runner.

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
  also becomes 409 `"This proposal was already applied; it cannot be applied or rejected again."`.
- Stale handling lines up: the backend returns 409 `stale_proposal` and marks the proposal stale,
  which is the frontend rule.
- Dismiss: the UI's Dismiss on a `stale` proposal calls `/reject`. The backend's reject now accepts
  `pending_review` **and** `stale` (approve is still `pending_review`-only, with role, self-approval and
  stale checks unchanged). It records a `rejected` Decision with "Dismissed from the dashboard: the
  budget changed after this proposal was drafted", and leaves allocations, the budget version and
  snapshots untouched. A dismissed proposal can no longer be rebased. `failed` is never produced, so
  Dismiss on `failed` is unreachable.

**G11. Error envelope.** The backend sends `{"error":{"code","message","details"}}`. The frontend wants
`{"error":"<plain English>"}`. Compat sends `{"error": message, "code": code}`, where `message` comes
from a per-code plain-English table (for example, `stale_proposal` -> "The budget changed after this
proposal was drafted, so it was not applied. Ask the assistant for a refreshed proposal, or dismiss this
one.").

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

### 4.4 Tests (implemented: `backend/tests/test_compat.py`, `backend/tests/test_compat_contract.py`, FakeDroidRunner only)
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

## 5. What is served (implemented)

Run the backend (`python -m app.seed && python -m app.main`) and start the frontend with
`NEXT_PUBLIC_API_URL=http://localhost:8787/compat` in `frontend/.env.local`. All 16 paths in §1 answer
under `/compat/api/*` with the exact TypeScript shapes. CORS already allows any `localhost` /
`127.0.0.1` port. On a freshly seeded DB all 10 store GETs return 200. On an unseeded DB the list routes
return `200 []` and only `/company` refuses, with 503 "The database is not seeded yet; run
`python -m app.seed`." (a `Company` cannot be built without a period).

| Piece | File | Notes |
|---|---|---|
| Routes | `app/compat/router.py` | `CompatRoute` renders errors as `{"error": "<plain English>", "code"}`; an unknown `/compat/api/*` path is a plain 404. Mounted only when `BACKEND_COMPAT` is on (default `1`), with `include_in_schema=False`, so `contract/openapi.json` is unchanged (`export --check` passes) |
| Mappers | `app/compat/mappers.py` | Pure functions. `num()` is the only place money becomes a JSON number |
| Contract models | `app/compat/schemas.py` | Pydantic mirrors of all 14 interfaces and 6 string unions, `extra="forbid"`, used as `response_model` with `exclude_none`. Optional fields the backend cannot fill are omitted, never `null` |
| Drift check | `tests/test_compat_contract.py` + `tests/vendored/frontend_contracts.ts` | Parses a verbatim copy of `frontend/src/lib/contracts/index.ts` (`main` e90b7f1, the people-aware contract) and fails on any missing or extra field, optionality change, or literal-union change. `COMPAT_UPSTREAM_CHECK=1` also checks live `origin/main`. It is opt-in so a frontend push cannot turn the backend suite red |
| Chat | `app/compat/intent.py`, `app/compat/threads.py` | New table `assistant_messages`, created on startup and wiped by `/api/admin/reset` |
| Errors | `app/compat/errors.py` | Per-code plain-English table; the UI shows POST errors verbatim. Stale: "The budget changed after this proposal was drafted, so it was not applied. Ask the assistant for a refreshed proposal, or dismiss this one." Second apply: "This proposal was already applied; it cannot be applied or rejected again." Also `already_rejected`, `self_approval_forbidden`, `role_forbidden`, `proposal_not_found`, `not_seeded`, one sentence each |

Changes from the design above, all made to avoid showing a number or claim the backend does not have:
- **Included usage** rows are `amount: 0`, `provenance: "usage_only"`, and their `source` names the notional value
  ("included in the subscription fee, notional value $3,000.00 is not counted as spend"). Before, these rows
  were labeled `reported_charge`, which claimed a $0 bill.
- **Unattributed** pseudo-team also has a `description` saying the spend has no team mapping yet. Its
  rows are always `complete: false`.
- **Forecast `limitations`** adds "simulated projection for the demo company" when the provider's
  `value_kind` is `simulated`. `generatedAt` is the response time when the provider gives none, or the
  snapshot's `fetched_at` inside `forecastsReviewed`.
- **Citation `locator`** reads `chars a-b (superseded version)` when the cited document version has been replaced.
- **Chat intents** (§4.3) also cover *refresh / rebase* plus a stale proposal. That runs
  `propose_allocation {stale_proposal_id}`, Droid rebases the proposal, and the new proposal has
  `revisesProposalId` set to the stale one, so the stale error's advice works from the drawer. The
  parser asks a question, and starts no run, when an addition has no amount, or when no team is
  named and no projection exists to choose one. Message `citations` are the proposal's evidence
  signals, or the run's recorded signals when there is no proposal. Fake-runner replies end with a
  "Simulated: ..." line.
- **Errors** add two compat-only codes, `already_applied` and `already_rejected`. A settled proposal is
  checked before `decide` is called. A replayed idempotency key also becomes 409 `already_applied`.
- **Identity**: `dashboard-analyst` (`finance_analyst`) sends chat and `dashboard-approver`
  (`finance_approver`) applies and rejects. Both are constants in `router.py`. `X-Actor-Id` and
  `X-Actor-Role` together override them, and sending only one of the two is a 401. Tests show that
  `dashboard-analyst` acting as an approver gets 403 `self_approval_forbidden` on both `/api` and
  `/compat`, and that `finance_analyst` and `droid_agent` get `role_forbidden`.
- **Not done:** the separate compat fixture snapshots under `contract/compat/` (§4.1). The vendored-TS
  drift test plus `response_model` validation cover the contract instead.

Verified by tests: seed numbers (spent 45k/20k/30k, allocated 60k/80k/60k, projected 85k/50k/65k);
chat "add 50k prioritizing research" -> `add_budget` 95k/80k/75k, total 250k; apply -> `Decision`,
budgets at version "2"; a second apply returns 409 with a string error; a stale transfer returns 409
with the stale text and its status becomes `stale`, and "refresh" produces a new proposal on
version 2; reject -> `rejected` plus a rejected `Decision` with budgets unchanged; read routes write
nothing (no forecast snapshots, no runs); runner unavailable -> an assistant reply instead of a 5xx;
`FORECAST_PROVIDER=unavailable` -> every forecast `unavailable` with a reason; `BACKEND_COMPAT=0`
unmounts the router; CORS preflight from `localhost:3000` works.

### 5.1 People-aware contract (integration pass, closed)

Every field the `e90b7f1` contract added is served. Tests: `tests/test_compat.py`,
`tests/test_compat_integration.py`, `tests/test_compat_contract.py`, `tests/test_people_spend.py`,
`tests/test_forecast_split.py`, `tests/test_person_signals.py`, `tests/test_seed_interpret.py`,
`tests/test_chat_speed.py`, `tests/test_stale.py`.

| Contract addition | Served by | Status |
|---|---|---|
| `GET /api/people`, `Person{id, teamId, name, role?, email?, integrations?, primaryTool?}` | new `people` table, `services/people`, compat `/people` | closed |
| `Team.lead` | derived from the role suffix " lead" | closed (derived) |
| `SpendingRecord.personId` | `usage_records.person_id`, daily per-person seed | closed; person rows sum to the team's counted spend |
| `Forecast.personId`, `Forecast.daily[]` | placeholder provider's proportional person split + weekday-weighted daily points | closed; person items sum to the team, `spent + sum(daily) == projected` |
| `ContextItem.scope`, `personIds`, `signal` | `context_signals.scope/person_ids/signal_kind`, Droid `record_signal` | closed; company items appear in every `teamId` filter |
| `SourceRef.integration`, `author` | cited document's `integration` / `author` | closed |
| `CompanyDocument.personIds`, `integration` | `corpus_documents.person_tags/integration` (front matter), 13 docs | closed |
| Dismiss on `stale` -> `/reject` | reject accepts `stale`, records a rejected Decision, budgets untouched | closed |
| Readable POST errors | `compat/errors.MESSAGES` | closed |
| Context cards on first load | `python -m app.seed` interprets the corpus once (12 signals by `droid_fake`, or the real Droid with `--live-signals`) | closed |
| Chat stays one synchronous POST | unchanged; `DROID_CHAT_MODEL` / `DROID_CHAT_REASONING_EFFORT` and reuse of current signals make it faster under the SDK runner | closed (latency still open, item 8 below) |
| Empty DB | list routes `200 []`, `/company` 503 `not_seeded` | closed |

The corpus now has 13 documents: the six team plans and notes, six person-tagged items (Asana, Slack,
monday.com) about Leila Novak (harness deferred), Omar Haddad (model switch), Theo Brandt (out of
office), Sofia Reyes (cutover accelerated), Hana Sato (onboarding) and Felix Weber (tool switch), and one
company-wide Slack model announcement. The stand-in interpretation records one person signal per person
document and one company signal; `evals` scenario `person_signals_cited` checks the same for live Droid.

## 6. Still open for the frontend owner

1. **Included usage (G1).** The dashboard's "Included usage" bar reads $0, while the frontend fixture
   counts included usage as cost. Decide whether the UI shows notional value separately (we have it,
   but only as text in `source` today), or whether a `notional` field gets added to `SpendingRecord`.
2. **Token telemetry (G2).** Unpriced Codex token rows are not sent, because the UI adds `amount` without
   checking `unit`. If the UI is changed to filter on `unit`, compat can send them with `unit: "tokens"`.
3. **Unattributed pseudo-team (G3).** It shows up in `/teams` only when such spend exists, and it has no
   budget and no forecast. Confirm the team grid handles a team without either.
4. **Completeness per team (G4).** The daily series is in place, but completeness is per team, so a
   partial team marks all of its days partial.
5. **Context fields (G5).** `confidence` is derived (rules in §2 #6). A timing shift with no
   `project_deferred` / `project_accelerated` kind comes through as `expectedEffect: "unknown"`.
6. **No low/high range (G6).** Forecasts and `daily` points have no range, so the UI's band stays
   empty. The person split is proportional to spend to date, not a person-level model; each person item
   says so in `limitations`.
7. **Identity (G9).** One browser acts as both analyst and approver, so separation of duties in the
   dashboard is nominal. Real per-user identity needs the UI to send `X-Actor-*` (or real auth).
8. **Chat latency (G12).** Under `DROID_RUNNER=sdk` a reply can take up to `DROID_TIMEOUT_S` (120 s).
   The drawer shows nothing until then. Streaming (`/api/agent/runs/{id}/events`) is available, but
   the frontend contract has no streaming path. Mitigations on the backend side:
   `DROID_CHAT_MODEL` / `DROID_CHAT_REASONING_EFFORT` (chat tasks only) and proposals that reuse the
   current signals recorded at seed time. An optional activity feed the frontend could adopt is
   described in [`frontend-streaming-note.md`](frontend-streaming-note.md) (no frontend file changed).
9. **`failed` / `pending` proposal statuses** are never sent. The backend validates when the proposal
   is drafted and applies synchronously, so Dismiss on `failed` is unreachable. If a later change emits
   `failed`, it must map to a backend status that reject accepts.
10. **Port (G14).** Use `http://localhost:8787/compat`, not `:8000` (the comment in
    `frontend/src/lib/data/index.ts`).
11. **Dismissed stale proposals** become `rejected` and cannot be rebased afterwards. Ask for a
    refreshed proposal before dismissing if the change is still wanted.
