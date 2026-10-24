# AI Spend Planner — frontend

Finance workspace for an enterprise FP&A team: AI token spending, projections, company context, and an assistant that proposes internal budget allocations. See `../MASTER_PLAN.md` for product scope. This folder is the frontend workstream only.

## Stack
Next.js 16 (App Router, `src/`), React 19, TypeScript, Tailwind v4, shadcn/ui (`src/components/ui`), Recharts, Zustand, lucide-react. `npm run dev` → http://localhost:3000.

## Architecture (read before writing code)
- `src/lib/contracts/index.ts` — **shared types for the six handoffs. Frozen.** Add optional fields only; never rename or remove. Ask the integration owner for anything else.
- `src/lib/data/client.ts` — `DataClient` interface. UI never imports fixtures directly; it goes through `useAppStore` (`src/lib/store.ts`) or `getDataClient()`.
- `src/lib/data/mock-client.ts` — in-memory mock. Will be swapped for an HTTP client when the backend lands.
- `src/fixtures/index.ts` — the shared company example (Meridian Software, 4 teams, October 2026, credits). Includes `scriptedReply()` for the mock assistant.
- `src/lib/store.ts` — app state. Applying a proposal here updates budgets everywhere.
- `src/lib/format.ts` — `formatAmount`, `pct`, `formatPct`. Use these; don't hand-format numbers.

## Ownership (parallel agents — stay in your lane)
| Area | Owns |
|---|---|
| Fixtures | `src/fixtures/**`, `src/lib/data/mock-client.ts` |
| Dashboard | `src/app/page.tsx`, `src/components/dashboard/**` |
| Teams | `src/app/teams/**`, `src/components/team/**` |
| Assistant + allocation | `src/components/assistant/**`, `src/components/allocation/**`, `src/app/decisions/**` |
| Shell / shared | `src/components/shell/**`, `src/lib/**`, `src/components/ui/**` — integration owner only |

If you need a shared component, put it in your own folder first and flag it; don't edit another lane's files.

## Product rules the UI must respect
- **Add budget ≠ redistribute.** Always label which one a proposal is. Redistribute keeps the total constant.
- **Units are explicit.** Credits, USD, and tokens are never mixed in one number. Use the `unit` field.
- **Provenance is visible.** Reported charge vs estimate vs usage-only must be distinguishable where amounts appear.
- **Cost components stay distinguishable**: subscription, included usage, extra usage, API.
- **Missing data is shown, not hidden.** A forecast with `status: "unavailable"` renders its reason. `complete: false` days are marked.
- **Forecast periods come from the Forecast object.** Never hard-code dates.
- **Citations are reachable** from any context card or proposal, but the main dashboard is not a tool-execution console.
- **Demo label stays on.** `company.isDemo` shows a badge.
- Calm design: restrained status colors, clear hierarchy, details on demand. No neon dashboards.

## Conventions
- Client components only where interactive; mark with `"use client"`.
- Team colors: `team.color` (CSS var). Charts use `--chart-1..5` tokens.
- Run `npm run lint` and `npx tsc --noEmit` before you say you're done.
- Commits: plain conventional messages. No AI attribution lines in commits or PRs, ever.
