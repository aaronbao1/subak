# AI Spend Planner — frontend

Finance workspace for an enterprise FP&A team: AI token spending, projections, company context, and an assistant that proposes internal budget allocations. Read `../docs/frontend-plan.md` first (the frontend plan of record), then `../docs/forecasting-plan.md` (how to present projections), then `../docs/ai-spend-master-plan.md`. This folder is the frontend workstream only.

## Stack
Next.js 16 (App Router, `src/`), React 19, TypeScript, Tailwind v4, shadcn/ui (`src/components/ui`), Recharts, Zustand, lucide-react. `npm run dev` → http://localhost:3000.

## Architecture (read before writing code)
- `src/lib/contracts/index.ts` — **shared types for the six handoffs. Frozen.** Add optional fields only; never rename or remove. Ask the integration owner for anything else.
- `src/lib/data/client.ts` — `DataClient` interface. UI never imports fixtures directly; it goes through `useAppStore` (`src/lib/store.ts`) or `getDataClient()`.
- `src/lib/data/mock-client.ts` — in-memory mock. Will be swapped for an HTTP client when the backend lands.
- `src/fixtures/index.ts` — the shared company example from the plan (Northstar Software, 3 teams, USD, $200k envelope). Totals are fixed by the plan; see the header comment. Includes `scriptedReply()` for the mock assistant. Exported as `northstar: Dataset`.
- `src/fixtures/generate.ts` — `generateCompany(n)` builds a deterministic synthetic company with 0..16 teams plus a generic assistant. The mock client picks it when the URL has `?teams=N` (remembered in localStorage; `?teams=default` resets). **UI code must never assume a team count or hard-code team ids.**
- `src/lib/store.ts` — app state. Applying a proposal here updates budgets everywhere.
- `src/lib/format.ts` — `formatAmount`, `pct`, `formatPct`. Use these; don't hand-format numbers.
- **People are the unit of attribution.** `Person` (contracts) belongs to one team. Spending records and forecasts carry an optional `personId`; the store splits `forecasts` (team-level, no personId) from `personForecasts`. Team numbers are always the sum of the team's people; `src/components/person/derive.ts` (`summarizePeople`) is the one place that rolls them up. Context items with `scope: "person"` name `personIds`, a typed `signal`, and `sources[].integration` (Slack, Asana, Monday) so the UI and the assistant can say *why* an individual's usage moves (manager pushed a project back, moving to a new model, out of office). `scope: "company"` is a macro change (e.g. a new model everyone migrates to). Person pages live at `/teams/[teamId]/people/[personId]`.

## Ownership (parallel agents — stay in your lane)
| Area | Owns |
|---|---|
| Fixtures | `src/fixtures/**`, `src/lib/data/mock-client.ts` |
| Dashboard | `src/app/page.tsx`, `src/components/dashboard/**` |
| Teams | `src/app/teams/**`, `src/components/team/**` |
| People | `src/components/person/**`, `src/app/(app)/teams/[teamId]/people/**` |
| Assistant + allocation | `src/components/assistant/**`, `src/components/allocation/**`, `src/app/(app)/decisions/**` |
| Landing | `src/app/(marketing)/**`, `src/components/landing/**` |
| Shell / shared | `src/components/shell/**`, `src/lib/**`, `src/components/ui/**` — integration owner only |

If you need a shared component, put it in your own folder first and flag it; don't edit another lane's files.

## Product rules the UI must respect
- **Add budget ≠ redistribute.** Always label which one a proposal is. Redistribute keeps the total constant.
- **Units are explicit.** Credits, USD, and tokens are never mixed in one number. Use the `unit` field.
- **Provenance is visible.** Reported charge vs estimate vs usage-only must be distinguishable where amounts appear.
- **Cost components stay distinguishable**: subscription, included usage, extra usage, API.
- **Missing data is shown, not hidden.** A forecast with `status: "unavailable"` renders its reason. `complete: false` days are marked.
- **Superseded context is distinguishable.** A `ContextItem` with `supersededBy` is visibly outdated and never cited as current. `claimType` separates a stated plan from an observed event from an assistant interpretation.
- **Proposal states are distinct.** proposed / pending / applied / rejected / revised / stale / failed each look different. Success shows only after the DataClient confirms. A double-click cannot apply twice (disable the button while pending).
- **A receipt follows every applied decision**: what changed, when, why, who. History lives at /decisions.
- **Forecast periods come from the Forecast object.** Never hard-code dates or name a quarter the data doesn't name.
- **Never double count.** `Forecast.basis === "full_period"` already includes incurred spend; do not add spent + projected. Only a `remaining` basis is added to spent.
- **Placeholder projections stay labeled.** `Forecast.origin === "placeholder"` renders a visible "placeholder projection" tag. `kind === "scenario"` is labeled as conditional on its assumptions, never as a forecast.
- **Receipts cite the projection reviewed.** A decision shows `forecastsReviewed` from the moment of review, not the current forecast.
- **Citations are reachable** from any context card or proposal, but the main dashboard is not a tool-execution console.
- **Demo label stays on.** `company.isDemo` shows a badge.
- **Individuals reconcile to the team.** Person projections sum to the team projection; person spend sums to team spend. A person has no allocation of their own (allocations stay at team level); show share of the team number instead.
- Calm design: restrained status colors, clear hierarchy, details on demand. No neon dashboards.

## Conventions
- Client components only where interactive; mark with `"use client"`.
- Team colors: `team.color` (CSS var). Charts use `--chart-1..5` tokens.
- Run `npm run lint` and `npx tsc --noEmit` before you say you're done.
- Commits: plain conventional messages. No AI attribution lines in commits or PRs, ever.
