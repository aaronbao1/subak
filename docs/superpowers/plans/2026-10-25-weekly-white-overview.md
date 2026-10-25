# Weekly spending overview and white theme implementation plan

> **For agentic workers:** Use superpowers:subagent-driven-development. Preserve existing dirty work; no commits or deployments requested.

**Goal:** Make the finance workspace immediately understandable through a white theme, weekly actual-versus-forecast comparison, visible over/under differences, and a direct allocation workflow.

**Architecture:** Reuse the native immutable forecast archive and observed-outcome receipts. A bounded weekly-history read model supplies honest comparison targets to a single dominant chart and week inspector. Existing allocation proposals/review/receipts remain the mutation boundary. No new forecasting algorithm is introduced.

**Tech stack:** Existing Next.js/React, Zustand, Recharts, FastAPI, SQLite and forecasting engine; no new packages.

**Spec and design:** User's October 25 follow-up plus `docs/ai-spend-master-plan.md` and `docs/forecasting-plan.md`. The master plan prioritizes company/team FP&A and reviewed allocation decisions. Our design is a white, outlined workspace: a full-width weekly chart, short same-week actual/forecast/difference summary, visible signed differences for each completed week, then a team allocation table. Clicking a week opens its explanation; Adjust allocations opens a structured draft workbench; Assistant remains available globally. Detailed provenance, source revisions and assumptions stay one level deeper. The existing Planning and Evidence routes retain scenario and source capabilities.

**Reference audit:** Ramp's official [reporting page](https://ramp.com/reporting) and [budgets overview](https://support.ramp.com/budgets-overview-and-setup/) and its linked product screenshot informed compact navigation, white space, a thin tab/filter boundary, one large comparison visual and an actionable table. Do not reproduce its chart content, logo, assets or lime palette. Keep a restrained blue accent.

## Global constraints

- White theme applies across all routes, dialogs, charts and tooltips. Remove duplicate assistant actions and decorative explanatory microcopy on the overview.
- Historical forecast must have been issued before the target week began. Current/recomputed predictions cannot be relabeled as past forecasts.
- Final over/under is actual minus forecast for one exact scope, period, unit, basis and dataset, using complete accepted outcome evidence. Current partial and unavailable values remain visibly distinct from zero.
- Do not manufacture source completeness, historic runs or uncertainty. The demo may generate synthetic vintages sequentially with frozen clocks and only then reveal synthetic outcomes.
- Financial edits create drafts; existing explicit Apply/Reject/Revise and saved receipts remain required. No provider transactions.

## Review focus

Late issuance and unpublished/shadow runs; partial first/current weeks; missing or withdrawn outcomes; corrected outcomes and exact vintage identity; white theme contrast and keyboard/mobile drilldowns.

## Tasks

- [ ] **Weekly read model (finance):** Add `GET /api/forecast-weekly-history`, native/compat mount, bounded exact weekly contract. Failing-first backend checks for the review-focus cases; implement archive and observed-record joins; retain real forecast identity and current outlook separately.
- [ ] **Client/model (actions):** Typed weekly contract, explicit HTTP adapter, bounded mock response with disclosed synthetic vintages, store loading/retry/stale isolation. Test null/zero/partial/variance and request races.
- [ ] **Weekly finance surface (interface):** Full-width actual/forecast chart, aligned signed over/under cells, same-week headline and Week review sheet. Accessible selectable weeks and exact data; test pure derived display semantics. Root wires Overview.
- [ ] **Allocation workflow (planning):** `AllocationWorkbench({open,onOpenChange,initialTeamId?})` and `TeamAllocationSummary({onAdjust?,compact?})`. Exact amount/source/destination/funding mode; draft creation uses existing store transport and explicit review. Test totals and draft-only behavior.
- [ ] **White theme and shell (usage/root):** Light tokens/root class and component contrast audit. Root simplifies shell copy/duplicate actions and overview hierarchy. Verify actual browser surfaces instead of redundant markup tests.
- [ ] **Integration and demo (integration/root/review):** New isolated synthetic history issued sequentially through real engine; endpoint and TypeScript integration checks. Independent financial review; Node/backend tests, lint/types/contracts/build, browser desktop/mobile + week review + draft/review flow. Open updated preview and record limitations.

## Acceptance

Overview answers what was spent, what was forecast, how far over/under, and what comes next without opening technical details. Completed weeks and future weeks are distinguishable. Team allocations and an obvious reviewed-action path remain visible. Sources, scenarios and usage are still reachable. No body or tooltip remains dark-themed. All numerical claims trace to authoritative records; no synthetic forecasting accuracy claim.

## Transcript-driven allocation extension

The user's subsequent instruction and two attached October23 transcripts make active budget coordination central. Preserve the weekly comparison work while adding:

- Authoritative company envelope and team distribution immediately above the weekly spending view.
- Full team-allocation editor using native proposal validation, unchanged-budget redistribution or explicit additional funding; review/apply stays separate.
- Durable team/project request inbox with explicit additional amount (unknown stays unknown), exact period, narrative/source and receipt-derived lifecycle.
- Automatic read-only assessment against current saved budget, matching forecast and possible donor headroom; request amounts do not silently alter numerical forecasts.
- Request-specific draft preparation and durable evidence linkage; a later rejection, partial approval, changed forecast or stale budget must not look fully funded.
- Current requests made available to assistant reasoning, including when the team already has an older context signal. Requests are considered, not automatically approved.
- Browser walkthrough: add a team update → inspect assessment → draft redistribution/addition → review → saved receipt and request status; manual full-team edit is also tested. Live Slack/email acquisition and outbound notifications remain outside this local implementation.

Detailed source cases and existing capability distinctions are recorded in `.coordination/weekly-white-20261025/findings/transcript-requirements.md`.
