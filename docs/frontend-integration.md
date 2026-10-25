# Frontend integration contract

The frontend (`frontend/`) runs fully on an in-memory mock today. To connect a real backend, set `NEXT_PUBLIC_API_URL` in `frontend/.env.local` and serve the endpoints below. Every payload is exactly one of the TypeScript types in `frontend/src/lib/contracts/index.ts`. That file is the source of truth; this page is the map.

## Run it

```
cd frontend && npm install && npm run dev      # http://localhost:3000, mock data
```

Demo switches (mock only): `?teams=N` for a generated company with N teams (0..16), `?teams=default` for the plan's Northstar example. The header dropdown does the same.

## Endpoints the frontend calls

| Method | Path | Returns | Notes |
|---|---|---|---|
| GET | `/api/company` | `Company` | `isDemo`, `budgetUnit`, `currentPeriod` |
| GET | `/api/teams` | `Team[]` | `color` is any CSS color; frontend falls back if missing |
| GET | `/api/people` | `Person[]` | everyone whose usage rolls up into a team (`teamId`, `role`, `integrations` such as slack/asana/monday, `primaryTool`) |
| GET | `/api/spending?teamId=&from=&to=` | `SpendingRecord[]` | one row per person × day × cost component × provider, with `personId` set when attribution is known (team-level rows omit it); team totals are the sum; `complete:false` marks partial days |
| GET | `/api/budgets` | `Budget[]` | include `version` so stale proposals can be detected |
| GET | `/api/forecasts` | `Forecast[]` | team-level AND person-level projections in one list; person-level ones carry `personId` and must sum to the team projection. `basis:"full_period"` means the number already includes spend to date. `status:"unavailable"` + `unavailableReason` is a valid answer |
| GET | `/api/context?teamId=` | `ContextItem[]` | Droid's cited summaries; `supersededBy` for outdated items. Person-level signals set `scope:"person"`, `personIds`, a typed `signal` (project_deferred, model_change, out_of_office, …) and `sources[].integration` (slack/asana/monday). Macro changes such as a new model set `scope:"company"` with every `teamId` |
| GET | `/api/documents` | `CompanyDocument[]` | readable source material (markdown body) |
| GET | `/api/documents/:id` | `CompanyDocument` | |
| GET | `/api/proposals` | `AllocationProposal[]` | newest first |
| GET | `/api/proposals/:id` | `AllocationProposal` | |
| GET | `/api/decisions` | `Decision[]` | newest first; includes rejections (`action`) |
| GET | `/api/threads/:threadId` | `AssistantMessage[]` | the UI uses thread id `main` |
| POST | `/api/threads/:threadId/messages` `{content}` | `AssistantMessage[]` | returns the new messages (user echo + assistant reply). If the assistant made a proposal, set `proposalId` on the reply and make it retrievable via `/api/proposals` |
| POST | `/api/proposals/:id/apply` `{note?}` | `Decision` | backend validates arithmetic and staleness, mutates budgets, bumps `Budget.version`, records the decision. On refusal respond 4xx with `{error: "<plain English>"}`; the UI shows it verbatim and leaves allocations unchanged |
| POST | `/api/proposals/:id/reject` | `AllocationProposal` | status → `rejected`; also record a `Decision` with `action:"rejected"` |

## Rules the backend must keep (the UI relies on them)

- **Add vs redistribute.** `AllocationProposal.kind` is `add_budget` (envelope grows by `addedAmount`) or `redistribute` (sum of `after` equals sum of `before`). `lines[].after` must sum to `totalAfter`.
- **Apply once.** A second apply of the same proposal must fail with an error, not double-apply.
- **Stale detection.** If `proposal.basedOnBudgetVersion !== current Budget.version`, apply fails and the proposal's status becomes `stale`.
- **Forecasts reviewed.** Copy `forecastsReviewed` from the proposal to the `Decision` so the receipt cites what finance actually saw.
- **Units are explicit.** Every money-like number carries `unit`. Never mix USD, tokens, and credits in one field.
- **Provenance.** Every `SpendingRecord` says `reported_charge`, `estimate`, or `usage_only`.
- **Missing data is data.** Send `complete:false` days and `status:"unavailable"` forecasts instead of zeros.

## Factory / Droid session

The assistant endpoint is where Droid lives. The UI renders `content` as markdown, lists `toolCalls` as a compact "work record", shows `citations` as chips, and renders an inline proposal card when `proposalId` is set. Keep `toolCalls[].summary` to one human sentence each.

## Forecasting session

Produce `Forecast[]` with the period you actually forecast (`period.start/end/label`), `basis`, `assumptions`, `limitations`, `generatedAt`, and `origin:"forecasting_service"`. Fixture projections are `origin:"placeholder"` and the UI labels them as such until yours replace them.
