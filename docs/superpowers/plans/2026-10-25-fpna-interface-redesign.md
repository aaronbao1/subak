# FP&A interface redesign implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking. This is a proposed plan; implementation has not been authorized.

**Goal:** Give nontechnical FP&A users a streamlined, high-level first layer for AI spending, forecast risk and reviewed actions, with explanations and deeper evidence available on demand.

**Architecture:** Preserve the native ledger, immutable forecast engine, scoped Droid tools and approval boundary. Introduce common financial view models, a truthful observed-usage API, task-oriented components, and structured conversational drafts. The browser presents authoritative values and previews; it does not invent forecasts, uncertainty or financial facts.

**Tech stack:** Existing Next.js 16.4.3, React 19.3.0, TypeScript, Zustand, Recharts, Tailwind, FastAPI, SQLite and Python forecasting package. Use existing UI primitives and tests. Select a calendar primitive after checking keyboard support; do not add a large visualization framework merely for a heatmap.

**Spec:** [AI Spend Planner UI audit and redesign proposal](../../ui-audit-2026-10-25.md). The recommended design is provisional. Read its scope, findings, semantics and acceptance criteria before execution.

## Global constraints

- High-level first, depth on demand is an explicit user requirement. Routine monitoring must work from the summary alone; deeper analysis remains easy to reach.
- Use three disclosure layers: summary → business explanation → evidence/calculations. Preserve company/team, period, metric and issued-result context across drill-downs and back navigation.
- Keep the default Overview to essential amounts, one primary chart, three to five grouped issues and one obvious primary next action. Additional calendars, breakdowns and advanced controls belong in focused views or disclosures, not an expanding stack of landing-page panels.
- Use plain finance language and short summaries. Keep material limitations concise beside affected values; reveal technical diagnostics and full sources on request.
- Preserve unrelated work; inspect current Git status and current instructions before implementation. This plan was prepared against `d4bd856`; recheck if sources have moved.
- Do not fabricate actual tokens, daily completeness, causal effects, forecast bounds or calibrated confidence.
- Every comparison uses matching scope, period, currency, financial basis and dataset. An unmatched budget is unavailable for comparison, not zero.
- Reported charges, estimates and informational included usage remain distinct. Included usage and unpriced tokens do not add to dollar spending.
- Preserve every native provenance kind, including measured and simulated, through exhaustive mapping. Never drop simulated costs from a demo total or relabel them as reported charges.
- Input plus output forms total tokens under the existing native contract. Cached input and reasoning remain subsets, not extra totals.
- Current actual corrections do not rewrite an issued forecast. Scenarios never replace the publication or change budgets automatically.
- Financial approval stays with the human approver; Droid has no approval tool. Saved receipts and idempotency determine action state.
- Demo data and scripted assistant are visibly labeled once at the application level and where necessary in exported/standalone artifacts.
- Raw run/proposal/driver IDs and JSON belong in calculation details, not normal task instructions.
- Existing `/api/*` and `/compat/*` consumers must remain compatible unless an explicit migration is included.
- No live Factory calls, production data migration, deployment or external connector acquisition is implied by this plan.

## Review focus

1. Period/cutoff boundaries: Sunday, partial first week, UTC midnight, quarter transition, observations received after issuance.
2. Missingness: complete zero, absent telemetry, partial sources, unpriced tokens, incomplete long outlook, and available shorter targets.
3. Identity and aggregation: shared/unassigned costs, inactive membership, duplicate model names across providers, cross-team/project effects and corrections.
4. Action outcomes: mutation committed but refresh failed, unknown network outcome, concurrent budget revision, stale evidence and interrupted conversation.
5. Natural language: negation, questions containing action words, exact small/negative amounts, explicit source/destination, relative dates and selected-proposal follow-ups.

Each condition is assigned to tests below. Styling-only changes require browser checks rather than tests that merely mirror markup.

## Proposed shared interfaces

These names are proposed new interfaces, not claims about existing exports. Reuse compatible current types where practical and adapt at boundaries.

| Interface | Owner and shape | Contract |
|---|---|---|
| `ScopeRef` | `frontend/src/lib/contracts/finance-view.ts`; `{type: company|team|person|shared, id?: string}` | Stable identifiers; shared residual type/partition retained separately when needed |
| `ComparisonTarget` | Same file; scope, start date, exclusive end date, UTC timezone, unit, financial basis, dataset id, optional issued run id | Exact compatibility required before budget variance; canonical backend metadata is the source |
| `ScopeSummary` | Same file; target, observed amounts and revision, issued forecast, matching allocation, nullable variance, quality states | No fallback sum that conceals missing/shared values; precise currency representation follows existing money utilities |
| `DailyUsageBucket` | `frontend/src/lib/contracts/usage.ts`; date, scoped costs by every native value kind, separate included-notional amount, nullable token categories, coverage state/revision and drill-down refs | Known zero differs from null; measured/simulated provenance retained; cached/reasoning subsets documented; no future actuals |
| `DailyUsageResponse` | Same file; target/date window, buckets, source coverage, dataset revision, synthetic flag | Bounded query across planning periods; dimensions and aggregate denominators explicit |
| `DriverInsight` | `frontend/src/lib/contracts/finance-view.ts`; driver/run/scope/target, title, effective dates, available effect, inclusion state, source refs | Effect is paired model sensitivity; no additive total or fabricated effect for context-only evidence |
| `ConversationContext` | Extend existing assistant contracts; scope/period, pinned run, selected proposal/version, current draft and pending slot | Selected identity survives round trips; explanation context does not silently override later action intent |
| `ActionDraft` | Extend existing assistant contracts; id/version, question/scenario/allocation kind, original/proposed values, target, validation and revision lineage | A scenario and a budget change have separate apply semantics; literal user constraints retained |

Use explicit field adapters between Python snake_case payloads and TypeScript naming. Monetary calculations stay server-side or use existing exact-money helpers; chart-only numeric conversion must not become the financial source of truth.

## Task 1 Correct financial targets and mock accounting

**Files:** create `frontend/src/lib/contracts/finance-view.ts` and `frontend/src/lib/finance-summary.ts`; modify `frontend/src/fixtures/generate.ts`, `frontend/src/fixtures/index.ts`, `frontend/src/lib/data/mock-forecast.ts`, `frontend/src/lib/data/mock-client.ts`, `frontend/src/components/dashboard/derive.ts`, `frontend/src/components/dashboard/forecast-derive.ts`, `frontend/src/lib/store.ts`, and summary consumers in Overview, TeamList, TeamHeader and PersonDetail. Add `frontend/src/lib/finance-summary.test.mjs`; extend existing forecast/mock tests. Inspect `backend/app/compat/mappers.py` for parity, without undoing its correct included-usage rule.

**Consumes:** native financial semantics and canonical `ForecastView` metadata. **Produces:** `selectScopeSummary(input): ScopeSummary`, `canCompareTargets(a, b): boolean`, and coherent fixed-clock mock data.

- [ ] Add failing invariants: included usage contributes zero billable dollars; eligible charge components reconcile for every supported provenance kind; unpriced usage adds zero dollars; no quarter-to-week variance; unknown target/budget does not become zero.
- [ ] Add clock fixtures covering Oct 25 Sunday, Oct 26 Monday, UTC cutoff and quarter boundary. Assert no reversed leave dates, future greeting or post-cutoff history inside an issued snapshot.
- [ ] Implement the shared selectors and explicit target adapters. Use the authoritative company view with shared partitions. Join all fixture data by identity; derive welcome/status/proposal reviewed values from the same target.
- [ ] Run targeted Node tests, then the existing forecast derivation and store tests. Expected: all new invariants pass and original conservation/unavailable cases remain green.
- [ ] Browser check the original $206K weekly-budget reproducer. Either display a matching weekly outlook or explicitly withhold the mismatch; all labels and proposal review identify the same period. Commit only after reviewing scoped changes.

## Task 2 Make actions and loading recover truthfully

**Files:** modify `frontend/src/lib/store.ts`, `frontend/src/components/allocation/proposal-review.tsx`, `frontend/src/components/assistant/assistant-drawer.tsx`, `frontend/src/lib/data/client.ts`, `frontend/src/lib/data/http-client.ts`, and `frontend/src/components/shell/app-shell.tsx`. Add `frontend/src/lib/action-receipts.test.mjs`; extend `store.test.mjs` and thread tests.

**Consumes:** existing backend action receipts/idempotency. **Produces:** explicit initial-load state and action status with separate mutation and synchronization outcomes.

- [ ] Write a failing test where apply succeeds, totals refresh fails, and retry refresh succeeds. Assert UI state remains confirmed applied, never unchanged. Add unknown-outcome and repeated-refresh-failure cases.
- [ ] Separate receipt processing from refreshing summaries. Add a stable operation id, receipt lookup/reconciliation path, retryable view refresh, and readable messages for confirmed/unknown outcomes.
- [ ] Add initial loading/error/stale states and targeted retry. Do not block spending on optional assistant/history failure. Preserve the most recent valid view.
- [ ] Add send tests: pending user message visible immediately; failure does not overwrite a newer composer draft; unknown-outcome retry remains disabled until backend reconciliation from Task 3 is available. Show progress only for actual work.
- [ ] Run tests and browser fault injection against an isolated backend/mock transport. Verify close/retry behavior and that existing double-apply/stale protections remain intact; commit this slice.

## Task 3 Repair intent and preserve conversational context

**Files:** modify `backend/app/compat/intent.py`, `backend/app/compat/router.py`, `backend/app/compat/threads.py`, assistant schemas, `agent/northstar_droid/sdk_runner.py`, frontend assistant contracts/client/store/drawer, both mock generators, and `frontend/src/components/allocation/proposal-review.tsx`. Extend `backend/tests/test_chat_revise_and_grounding.py`; add shared semantic fixtures and frontend intent tests.

**Consumes:** selected scope/target and stable action/proposal identities. **Produces:** `ConversationContext`/`ActionDraft` transport and context-preserving clarification/revision behavior.

- [ ] Pin request examples: no-new-funding redistribution has zero envelope change; $50 stays $50; negative amounts are rejected; “Why did you add…” remains a question; explicit Product→Research transfer retains source/destination; “Do not add funding” never requests an amount to add.
- [ ] Add follow-up cases with one and multiple proposals: “50k,” “Make it 40k instead,” and date changes fill a pending slot or revise the explicitly selected draft. No raw `prop_…` entry is required.
- [ ] Replace ambiguous keyword-only routing with validated action interpretation. Starter controls carry intent; free text still passes constraints and clarification. Persist only appropriate conversation/task context and preserve the pinned forecast for factual answers.
- [ ] Add backend message request deduplication and reconciliation keyed by authenticated tenant/thread plus stable client message identity. Identical retries return the same message/run/proposal; conflicting reuse is rejected. Test timeout after acceptance, concurrent retries and reconnect before enabling the Task 2 retry control.
- [ ] Pass selected proposal id/version through Revise. Supersede or link prior drafts according to native revision semantics. Make explanation context a visible removable chip and deliberate action-mode transition.
- [ ] Run pure parser, frontend semantic and backend revision/tool-boundary tests. Verify with deterministic runner first; record live SDK validation separately when credentials and authorization are available. Commit the slice.

## Task 4 Refactor the financial screen hierarchy and chart styling

**Files:** refactor `frontend/src/components/forecast/forecast-panel.tsx`; create `forecast/forecast-summary.tsx`, `forecast/spend-forecast-chart.tsx`, `forecast/calculation-details.tsx` and shared chart tooltip/tick formatting; modify Overview, `team/team-detail.tsx`, `person/person-detail.tsx`, `dashboard/hero.tsx`, and `evidence/evidence-page.tsx`.

**Consumes:** `ScopeSummary`, canonical issued view, current actuals, matching budget and supported horizon. **Produces:** reusable scope summary/chart plus a secondary audit-detail surface.

- [ ] Capture regression expectations for actual/forecast dates, supported horizons, immutable issued line, unavailable components and scenario/error separation. Retain the pointwise interpretation of historical intervals; do not imply whole-path coverage. Use existing numerical outputs; do not synthesize a new model in the browser.
- [ ] Implement the three disclosure layers. Lead Overview with essential amounts, one chart and three to five grouped issues. Selecting an issue opens a concise business explanation; sources/calculations require a further explicit action. Remove duplicate full ForecastPanel from Evidence; place team/person actuals near the top. Keep concise demo/freshness/material-incompleteness badges.
- [ ] Apply the audit copy table. Move IDs, exact cutoffs, raw JSON, full daily tables and detailed reconciliation into calculation details; preserve accessible source paths.
- [ ] Implement themed tooltip/ticks, compact currency axes and human dates. Remove fake calculation delay. Make chart controls affect the clearly labeled view and offer exact data inspection.
- [ ] Check desktop 1440 × 1000, laptop 1024 × 768 and phone 390 × 844, plus keyboard/touch. Default-state gate: one primary chart, one primary action, three to five grouped priorities, advanced controls collapsed, and concise material-data qualifications without repeated diagnostic prose. Primary finance answers fit the first desktop viewport without opening details; no white tooltip or clipped essential action; drill-down and close preserve scope/period/metric. Run lint/type check and scoped tests; commit.

## Task 5 Expose truthful daily observed usage

**Files:** create `backend/app/api/routes_usage.py`, `backend/app/schemas/usage.py`, `backend/app/services/usage.py`, `frontend/src/lib/contracts/usage.ts`; modify backend route registration/compat mounts, spending query utilities and frontend clients. Add `backend/tests/test_usage_daily.py` and `frontend/src/lib/data/usage-transport.test.mjs`; regenerate contract artifacts when the route stabilizes.

**Consumes:** native records, exact token category semantics, memberships, revisions and coverage receipts. **Produces:** proposed `GET /api/usage/daily`, also accessible under `/compat`, returning `DailyUsageResponse`.

Proposed query: `scope_type`, optional `scope_id`, `start_date`, `end_date_exclusive`, and supported provider/model filters. Keep UTC buckets and cap a single request to 366 days; larger history can be requested by windows. Empty data and source absence must be distinguishable. If current records cannot establish completeness, report unknown/partial rather than invent a manifest.

- [ ] Add native-record→response tests retaining model/provider, zero-dollar and unpriced token rows, nullable telemetry, exact costs and deduplication/revisions. Cover reported, estimated, measured and simulated value kinds exhaustively; unknown kinds must fail validation rather than disappear.
- [ ] Add category tests proving total=input+output and that cache/reasoning are not counted twice. Preserve included-notional value separately from billable cost.
- [ ] Implement cross-period daily aggregation, scope/shared reconciliation, source coverage and drill-down references. Do not load an entire 331K-record company into the browser merely to draw a calendar.
- [ ] Wire the client and mock to the same response shape with explicit synthetic provenance. Verify API model displays no longer lose dimensions or hide nonzero tokens when cost is zero.
- [ ] Run Python usage/spending tests, TypeScript transport tests and contract determinism check. Inspect a known source slice manually against the aggregate; commit.

## Task 6 Add actual usage calendar and focused breakdowns

**Files:** create `frontend/src/components/usage/token-activity-calendar.tsx`, `usage/day-detail.tsx`, `usage/usage-trend.tsx`, `frontend/src/lib/usage-derive.ts` and meaningful derivation tests; add compact Usage activity entry points to Overview/team/person views; adapt `dashboard/model-breakdown.tsx` and `team-breakdown-panel.tsx`.

**Consumes:** `DailyUsageResponse`, scope/date selection and metric. **Produces:** shared selected-day/range state and recorded usage exploration.

- [ ] Test known-zero, missing, partial, future, corrected days and complete sums across company/team/person/shared partitions. Test stable thresholds and provider/model identity collisions.
- [ ] Implement a focused Usage activity view with Spend/Tokens control, readable legend, date presets and range picker. Preserve an existing date selection; otherwise default to 13 weeks. Keep advanced filters secondary. Use fewer weeks when the data window requires it; no invented history. Do not add another permanently expanded calendar panel to Overview.
- [ ] Connect selection to exact day/range summary and model/provider/tool breakdown. Keep forecast cells outside the actual calendar. Separate reported and estimated dollars.
- [ ] Implement roving keyboard focus, touch selection and table/date-control equivalents. Add meaningful accessible labels and non-color missing/partial encodings.
- [ ] Verify actual sums and drill-down records agree, UTC boundary behavior is explicit, and the existing forecast never changes when browsing history. Browser-test responsive layout and keyboard tasks; commit.

## Task 7 Rank relevant contributors and forecast changes

**Files:** create `frontend/src/components/forecast/driver-overview.tsx`, `forecast/driver-detail.tsx`, `dashboard/cost-contributors.tsx` and `frontend/src/lib/driver-insights.ts`; modify forecast contracts/adapter, mock scope mapping, Evidence and team summaries. If needed, extend backend forecast scope metadata rather than guessing project/configuration applicability in the UI. Add `driver-insights.test.mjs` and backend evidence-scope tests.

**Consumes:** actual scoped totals, canonical `driver_effects`, included/queued/context-only states and source references. **Produces:** top-five actual contributor lists and `rankForecastInsights(input): DriverInsight[]` for one run/scope/horizon.

- [ ] Test ranking by available absolute financial effect, sign, scope/run match, target availability, zero-versus-missing and duplicate driver identity. Test Research excludes unrelated Product evidence but retains genuine cross-team effects.
- [ ] Implement “Where the money went” and “What changes the outlook” as focused tabs or disclosures reached from the compact issue summary. Initially show up to five grouped items with business labels; expose calculation/source detail on selection. Include Other/shared remainder only for genuine additive cost partitions.
- [ ] Add group/event titles and concise source summaries. Never rank context-only or queued facts as realized numerical effects. Unknown scope remains unknown.
- [ ] Use exact same-run effects in the drawer; replace driver-id-only fallbacks. Category-level joint scenario effects require a joint calculation, not summed individual deltas.
- [ ] Test company→team→source navigation and scoped top-five results using canonical fixtures with actual supplied effects. Confirm no probability/causal/savings claim is added; commit.

## Task 8 Add editable scenario and budget cards

**Files:** create `frontend/src/components/assistant/action-draft-card.tsx`, `assistant/scenario-preview.tsx`, `assistant/date-field.tsx`, `forecast/planning-calendar.tsx`, and typed draft adapters; modify forecast scenario client/store and allocation review. Extend backend scenario/draft validation and context schemas only where existing APIs lack the required edit. Add scenario/context/revision tests.

**Consumes:** `ActionDraft`, `ConversationContext`, selected baseline and validated driver types. **Produces:** editable proposal/scenario previews with exact identity and revision lineage.

- [ ] Define supported edits per driver type. Test start/end dates, invalid/ambiguous dates, timezone resolution, exact amounts, source-team constraints and period matching.
- [ ] Implement named scope/entity selectors, natural-language date plus calendar field, exact amount inputs, and a concise before/after card. Initially show only fields needed for the current action, with optional details expandable and one clear next step. User-authored assumptions remain hypothetical unless an explicit evidence workflow exists.
- [ ] Add an Upcoming changes calendar/list from effective driver dates with company/team filtering, opened through a relevant issue/team/planning action. Keep the calendar, editor and comparison chart behind contextual actions rather than appending them to Overview. Event selection opens sources or the scenario card. Separate source-backed plans from draft what-ifs; no drag/edit action silently changes evidence or the published baseline.
- [ ] Translate draft patches into a complete driver set for scenario submission. Test unrelated drivers are preserved and parent run cannot drift during an asynchronous preview.
- [ ] Show baseline-versus-scenario chart and relevant deltas/ranges. Keep Preview, Update forecast and Apply budget change distinct. Use explicit revision linkage; any future reversal creates a new audited proposal.
- [ ] Test explain→edit date→preview→revise→review budget→receipt in deterministic connected mode. Ensure no tool or UI shortcut bypasses finance approval; commit.

## Task 9 Refine navigation, decisions and resilient progress

**Files:** modify `shell/app-shell.tsx`, `team/team-list.tsx`, `allocation/decision-log.tsx`, assistant drawer/message rendering and client run/event transport; add minimal scoped components for filters and progress.

**Consumes:** shared summaries, conversation context and existing persisted agent events. **Produces:** navigable task history and understandable asynchronous actions.

- [ ] Add Teams search/sort and Decisions status/team/period filters; preserve selected state in the URL where appropriate.
- [ ] Collapse citations to a short relevant subset with See sources; place low-level tool events in Details. Show progress from real run receipts/SSE or polling, with reconnect handling.
- [ ] Add primary page headings, skip navigation, clear mobile navigation overflow and correct focus restoration to composer after Revise.
- [ ] Test waiting/reload/reconnect, stale proposals, changed publication, no teams/people, inaccessible sources and partial data. Add cancellation only if the backend actually supports it.
- [ ] Run keyboard/mobile walkthroughs and scoped regression tests; commit.

## Task 10 Verify a coherent demo and nontechnical workflow

**Files:** extend existing `frontend/tests/forecast-backend.integration.mjs`, component SSR and native acceptance fixtures as needed; update `docs/implementation/forecast-browser-journey.md` and add a dated validation record.

**Consumes:** completed slices above. **Produces:** reproducible demo data/mode, browser evidence and release decision.

- [ ] Use a coherent engine-backed synthetic fixture with aligned budgets/periods, relevant drivers, actual histories and honest supplied ranges. Keep scripted vs live assistant explicit. Never manufacture calibration to fill an empty band.
- [ ] Run numerical/backend tests relevant to changed contracts and calculations, frontend tests, `npm run lint`, `npx tsc --noEmit`, pinned production build, and the real TypeScript client→FastAPI integration journey. Record actual commands/results and any blocks.
- [ ] Browser-test both mock and connected deterministic modes: company/team/person totals, daily tokens, missing day, top drivers, source drill-down, scenario revision, stale approval, save-success/refresh-failure and receipt recovery.
- [ ] Test with several nontechnical finance users. Proposed targets: spend/budget answer ≤30 seconds from summary alone; relevant driver/token-spike investigation ≤60 seconds; dated scenario preview/revision ≤2 minutes. Check summary→explanation→source→return preserves context and users can discover depth without confronting technical detail upfront. Record completion, errors and requests for help; these are evaluation targets, not existing performance claims.
- [ ] Review the combined diff and evidence. Run live Droid tests only as a separately authorized/configured step; label that capability unverified until executed. Do not claim production identity/connectors or forecasting accuracy from synthetic tests.

## Parallel execution and handoff

Task 1 establishes shared semantics. Task 2 and Task 3 can be owned separately after interface agreement. Task 4 and Task 5 may proceed in parallel with single ownership of store/contracts; Task 6 depends on Task 5, and Task 7 depends on stable target/scope semantics. Task 8 depends on Task 3 and canonical scenario behavior. Task 9 integrates the interaction patterns. Task 10 checks the combined result.

Recheck interface ownership before edits. Prefer existing worktree state and preserve unrelated user work. Review each independently testable slice, then the full integrated experience. Do not use agreement between reviewers as a substitute for executed financial invariants or browser evidence.

No implementation step has been performed as part of this audit. Product choices that remain open are the preferred default planning period, whether users primarily compare currency or usage, and whether the next demo should use Northstar or the larger generated company. The plan assumes dollars as the finance default, matching available budget periods, and Northstar as the initial validation fixture; these are recommendations, not recorded user decisions.
