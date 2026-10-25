# Frontend sub-agent prompts

Open a terminal per remaining agent (A and D). In each: `cd ~/Code/calhacks13.0unicorns62/frontend && claude`, then paste ONE prompt below.
All four work in the same checkout on disjoint folders. Nobody commits; the integration owner commits.
Each agent runs its own dev server on its own port so they don't collide.

---

## Agent A — Fixtures & mock data (port 3001)

You are the fixtures owner for the frontend of an AI-spend planning tool for an enterprise finance team. Read `CLAUDE.md` in this folder, then `../docs/frontend-plan.md`. Your lane is ONLY `src/fixtures/**` and `src/lib/data/mock-client.ts`. Do not edit anything else. Do not change any type in `src/lib/contracts/index.ts`; if you need a new field, write the request in `NEEDS.md` (create it if missing) under a heading "Agent A" and work around it.

The shared company example is Northstar Software. The totals in the header comment of `src/fixtures/index.ts` are fixed by the plan and must not change: allocations 60k/80k/60k, spent 45k/20k/30k, projections 85k/50k/65k, and the two canonical proposals (redistribute 85/50/65 at a 200k envelope; add 50k → 95/80/75 at 250k). A quick check that prints spending totals per team must still give exactly 45000 / 20000 / 30000.

Deliver:
1. Richer `documents`: 3 to 6 paragraphs of readable markdown each, realistic for an approved plan, a roadmap update, a Slack thread, and an engineering note. Add one more correspondence doc per team (an email or Slack excerpt) and link them from `context[].sources` where sensible. Keep the superseded Sep 18 thread clearly superseded.
2. More `scriptedReply` cases, each with `toolCalls` that read like real work and `citations` where a claim is made: "compare research and product", "why is product under", "what if research grows another 20%" (return a clear limitation: scenarios not supported yet, no numbers invented), a revise case like "make it 40k for research instead" that returns a NEW `add_budget` proposal with `revisesProposalId` set to the most recent proposed proposal and marks the old one `revised`, and a fallback that lists what it can do. Keep arithmetic exact: lines must sum to totalAfter.
3. A scenario switch in `MockDataClient`: read `?scenario=` from `window.location.search` on construction (guard for SSR). `scenario=missing-forecast` makes the Engineering forecast `status: "unavailable"` with a plain-English `unavailableReason`. `scenario=partial-data` marks Oct 19 to 22 as `complete: false` for all teams and adds a note to the welcome message. Default behavior unchanged.
4. Latency realism: `sendMessage` resolves in ~1.2 to 2s so the UI's pending states are visible.

When done: `npx tsc --noEmit` and `npm run lint` must pass. Run `PORT=3001 npm run dev` only to smoke test. Reply with a short summary of what you added and anything in `NEEDS.md`.

---

## Agents B and C — DONE

The Overview dashboard (`src/components/dashboard/**`) and team pages (`src/components/team/**`) are built. Do not re-run these prompts. Remaining work for those lanes goes through the integration owner.

---

## Agent D — DONE

The assistant drawer (`src/components/assistant/**`), allocation review (`src/components/allocation/**`) and `/decisions` are built and smoke-tested: ask → proposal card → review dialog → apply/reject/revise → receipt → history. Composer text lives in the store as `composer` / `setComposer`; `askAssistant(text)` prefills it and opens the drawer. The mock also answers "compare…", "why is product under", "what if…" (clear limitation) and "revise this proposal: make it 40k for research instead" (new proposal with `revisesProposalId`; the old one becomes `revised`).

Remaining work for all lanes goes through the integration owner.

---

## Agent E — Landing page, overview cleanup, allocation wording (port 3003)

You are redesigning the entry experience of the frontend of an AI-spend planning tool for an enterprise finance team. Read `CLAUDE.md` in this folder first, then `../docs/frontend-plan.md`. Do not commit; the integration owner commits.

Your lane: `src/app/**` (route files and layouts only), a new `src/components/landing/**`, `src/components/shell/**`, and `src/components/dashboard/hero.tsx`. Read anything else but do not edit it. In particular do NOT touch `src/fixtures/**`, `src/lib/data/**`, `src/components/assistant/**` or `src/components/allocation/**`; other agents are working there right now. If `npx tsc --noEmit` reports errors only inside `src/fixtures/`, those are not yours; ignore them and report them.

This is user feedback from a walkthrough with a teammate. Fix all four points.

### 1. Landing page at `/`, dashboard moves to `/overview`
Jumping straight into the numbers is overwhelming. Build a Ramp-style marketing landing page (clean, mostly white, generous whitespace, one bold tight-tracked sans headline, calm single accent color from the existing theme tokens, no neon, no gradients-everywhere). Use Next route groups so the landing has no sidebar:
- `src/app/(marketing)/layout.tsx` + `src/app/(marketing)/page.tsx` — landing. Minimal top bar: product name on the left, one "Open dashboard" button on the right linking to `/overview`.
- `src/app/(app)/layout.tsx` — wraps children in the existing `AppShell` inside `<Suspense>` (the root layout currently does this; move it here). Move the current `src/app/page.tsx` to `src/app/(app)/overview/page.tsx`, and move `src/app/teams/**` and `src/app/decisions/**` under `(app)/`. Root `layout.tsx` keeps fonts, globals.css and metadata only.
- Update `nav` in `src/components/shell/app-shell.tsx`: Overview → `/overview` (fix `isActive`), Teams, Decisions. Add a small link back to the landing page in the sidebar footer. Update `src/components/shell/team-count-switcher.tsx` so switching teams reloads `/overview?teams=N`, not `/?teams=N`.
- Metadata: title "Subak", description = the tagline below.

Landing content (product name is **Subak**; tune the copy but keep the meaning):
- Headline: "See every team's AI spend before the quarter is over."
- Subhead: "Real-time token spend, projections, and allocations for finance teams. Every manager gets a number to run to; FP&A gets one view of the company and an assistant that proposes reallocations with receipts."
- Buttons: primary "Open dashboard" → `/overview`; secondary "See how it works" → anchor to the first feature block.
- Then exactly three alternating text + media feature sections (text left/media right, then swapped, then back), each with a short heading, 2 to 3 sentences, and a 16:9 media frame:
  1. "One number for the company" — spent to date, projected, and total allocation, with a bar that shows the overrun when projection passes allocation.
  2. "Click a team, see the breakdown" — click any line on the spend chart for that team's cost components, provenance, and last seven days.
  3. "Reallocate with receipts" — ask the assistant, review a proposal, apply it, and every decision lands in a log with the projection that was reviewed.
- The media frame is a `MediaSlot` component in `src/components/landing/media-slot.tsx`: props `src?: string`, `poster?: string`, `alt: string`. If `src` is given render `<video autoPlay muted loop playsInline>` ; otherwise render a quiet placeholder (muted surface, 1px ring, the alt text small in the corner). The owner will record product videos later and drop them in `public/media/*.mp4`; wire the three slots to `/media/overview.mp4`, `/media/team-breakdown.mp4`, `/media/reallocate.mp4` so a file appearing there is all that's needed. Do not fetch or check for the file; the browser handles a missing src with the poster/placeholder visible, so render the placeholder behind the video and let a missing video fail silently.
- Footer line: "Demo data. Planning records, not provider limits or purchases." Keep the `company.isDemo` badge rule in the app; the landing page does not load the store.
- Must look right at 390px wide and at 1440px. No horizontal scroll.

### 2. Rename "Envelope" to allocation wording
Nobody outside the team knows what an envelope is. In `src/components/dashboard/hero.tsx` and `src/components/shell/app-shell.tsx` (the header note), replace user-facing "Envelope"/"envelope" with **"Total allocation"** for the figure and "allocation" in the sentences ("42% of allocation recorded", "Projected $8,000 over allocation"). The idea: every team has an allocation number its manager runs to, and the company has a total allocation. Keep code identifiers, props and contract fields unchanged (`envelope`, `Budget.allocated`), only the strings change. Grep `src/components` for any other visible "envelope" and fix those strings too, but only in files in your lane; list the others in your report.

### 3. Fix the confusing "7 of 8 teams" hint
The projected figure shows "7 of 8 teams" when one team has no forecast, and the reader could not tell what it meant. Replace the hint with an explicit sentence under the figure, e.g. "Excludes 1 team with no projection yet: Engineering" (pluralize correctly; list up to three names then "+N more"). The hero needs the names: add an optional `unavailableTeams?: string[]` prop to `Hero` and pass it from the overview page (derive it from `summaries` where `projected` is undefined). Keep the product rule: missing data is shown, never hidden.

### 4. Move the team cards off the overview
Remove the `TeamGrid` section (and its skeleton) from the overview page so the overview is: hero, spend chart with the click-to-breakdown panel, cost components. Do not delete `team-grid.tsx`. Then check `/teams`: the list must show, per team, allocation / spent / projected with the allocation clearly labelled "Allocation", and a top row with the company total allocation. If `src/components/team/team-list.tsx` already does this, leave it; if it only lacks the labels or total, make the smallest change there and flag it in your report because that file belongs to another lane.

### Finish
Run `npx tsc --noEmit` and `npm run lint`. Smoke test with `PORT=3003 npm run dev`: `/` (landing), `/overview`, `/overview?teams=8` (hint sentence appears if the generated data has a missing projection; if not, say so), `/overview?teams=default`, `/teams`, `/decisions`, plus the landing at 390px wide. Reply with: files added/moved/changed, any strings containing "envelope" you could not change, anything you touched outside your lane, and the tsc/lint result.

---

## Oct 24 review follow-ups

Read `REVIEW.md` first. Three prompts below; each is one terminal. Agent A's terminal gets the addendum, not a fresh prompt.

### Addendum for the Agent A terminal (fixtures lane) — paste into the running session

Read `REVIEW.md` section 1, items 1, 2, 4, 5, 7, 8, and section 2 items 1, 4, 10, 11. These are all in your lane (`src/fixtures/**`, `src/lib/data/mock-client.ts`). In priority order:
1. Intent routing in BOTH `makeGenericReply` (generate.ts) and `scriptedReply` (index.ts): test redistribute verbs (`redistribut|rebalanc|\bmove\b|shift|reallocat|without (adding|new)`) BEFORE the add branch; `\badd` must not match "adding". Then run `parseAmount` and treat any amount ≥ 1,000 with no redistribute verb as add_budget, honoring the typed amount. "we got 50,000 more, how should we split it", "we have another $25,000 to allocate this week", "add $20,000 to research", "move 10k from product to research" must each produce the right kind and amount. Match team names longest-first on word boundaries.
2. Port the revise branch into `makeGenericReply` (`revisesProposalId`, old one `revised`). Add a generic per-team "why is X over/under" and a "tell me about X" branch to Northstar so every team answers.
3. Pin time: `asOf = process.env.NEXT_PUBLIC_DEMO_ASOF ?? today`, defaulting the demo to a mid-week date so Thu–Sun stay projected and Spent to date stops drifting between loads. Period label "Planning period · Oct 19–25", not "Week of".
4. Persist mock state (budgets, proposals, decisions, threads, budgetVersion) to sessionStorage keyed by dataset id; hydrate on construction. Persist `?teams=northstar` the same way `?teams=N` is persisted.
5. Replace every user-facing "envelope" in fixture strings with "allocation" / "total allocation".
6. Give the default dataset one superseded correspondence item and one `observed_event` on the top-pace team.
7. Included usage: stop distributing the dollar target onto `included_usage`; keep its records with the `tokens` unit (or amount 0) so billable spend is exact. Tell the integration owner the new per-team billable totals.
Verify with a scratch script that prints kind/amount for the sentences above on n=3, 8, 16 and Northstar. `npx tsc --noEmit` and `npm run lint` clean.

### Agent F — Demo-critical UI fixes (port 3005)

You are fixing demo-blocking UI issues in the frontend of an AI-spend planning tool. Read `CLAUDE.md`, then `REVIEW.md`. Do not commit. Your lane: `src/components/dashboard/**`, `src/components/team/**`, `src/components/allocation/**`, `src/components/assistant/**`, `src/app/(app)/**`, `src/lib/store.ts`. Do NOT touch `src/fixtures/**` or `src/lib/data/**` (another agent is in there now). Do these, in order:
1. Hero hierarchy (`dashboard/hero.tsx`): Spent to date becomes the one big number (text-5xl/6xl, tabular), Projected and Total allocation secondary. Add one line under the bar: "N teams likely over: A, B, C" from summaries + status (hide when zero). When some teams have no projection, compare spent/allocation over the same team set as projected and say "7 of 8 teams" on all three, so Projected is never shown below Spent without explanation.
2. Chart hit area (`dashboard/spend-by-team-chart.tsx`): clicking anywhere on a line selects the team. Add an invisible wide stroke per series (strokeWidth 14, opacity 0, same onClick) or nearest-series lookup on chart click. Treat any row with a non-null projected value as having a projection so dashed lines never vanish on the last day. Add `overscroll-x-none` to the chart container and main.
3. Breakdown panel default (`dashboard/team-breakdown-panel.tsx`): when nothing is selected, show a company summary (top 3 teams by projected − allocation with a small variance bar and status chip, click → select) instead of "Select a team".
4. Cost components (`dashboard/cost-components.tsx`): open by default; summary is a real `<button>` with aria-expanded.
5. Weekend/partial clarity: shade weekend columns lightly and label them in the footnote so the Fri→Sat drop reads as weekend, not a bug.
6. Rename every user-facing "envelope" in your lane to "allocation"/"total allocation" (`allocation/proposal-bits.tsx`, `proposal-card.tsx`, `proposal-review.tsx`, `decision-log.tsx`, `assistant/assistant-drawer.tsx` quick prompts). Fix "Projection (7 of 8 teams)" and the lowercase "week of oct 19" in `team/team-list.tsx`. Replace "placeholder" tags with "sample projection" (keep the tooltip text), and drop the duplicate chart-footer sentence.
7. Timestamps: `team/labels.tsx fmtDateTime` → local time with short zone; UTC only for date-only strings.
8. Assistant drawer: render `ProposalReview` and `SourceSheet` inside `SheetContent` so Esc closes only the top dialog (verify in browser). Keep the textarea enabled while sending (gate on canSend), refocus after reply, reserve the chip row height. Quick prompts derive team name from `teams` and amount from `formatAmount(25_000, unit)`. Composer draft becomes local state; use `useShallow` selectors so typing doesn't re-render the chart.
9. Stale/failed proposals get a Dismiss (records a rejection) in `proposal-review.tsx` / `decision-log.tsx`.
10. One `StatusChip` in `team/labels.tsx` using `text-warning`/`text-success`/`text-destructive`; use it in both dashboard and teams. Replace `/60` `/70` alpha on informative text with full `text-muted-foreground`.
11. Add `@media (prefers-reduced-motion: reduce)` to `src/app/globals.css` (flag it; shell lane) zeroing animation/transition durations.
Finish: `npx tsc --noEmit`, `npm run lint`, smoke on `PORT=3005 npm run dev` at `/overview`, `/overview?teams=16`, `/overview?teams=northstar`, run the demo script in REVIEW.md section 5 end to end. Report what you changed, anything outside your lane, and anything from the list you could not do.

### Agent G — Landing + motion (port 3006)

You are adding the showpiece layer to the frontend of an AI-spend planning tool. Read `CLAUDE.md`, then `REVIEW.md` sections 3 (Landing) and 4. Do not commit. Your lane: `src/app/(marketing)/**`, `src/components/landing/**`, and ONLY the motion wrappers you add inside `src/components/dashboard/hero.tsx`, `src/components/dashboard/team-breakdown-panel.tsx`, `src/components/dashboard/spend-by-team-chart.tsx` (coordinate: Agent F is editing those files for logic; keep your diffs to animation props and wrappers, pull their changes often, and never change numbers or labels). Nothing in fixtures, data, allocation, assistant.
Install `npm i motion @number-flow/react`. Respect `useReducedMotion()` everywhere. House style: calm on the dashboard, showy on the landing; accent is `--ring` at ≤15% alpha; no neon, no confetti, no scroll hijacking, no Three.js.
Build in this order and stop when time runs out:
1. Theme continuity: make the landing dark to match the dashboard (reuse the app tokens), or if you keep it light, add a theme toggle that both sides respect. Fix the scrollbar/color-scheme scoping noted in REVIEW.md item 19. Landing copy: "Daily AI spend, projections and allocations by team", "before the period is over", drop "Three teams" from the closing CTA.
2. Cursor-reactive dot field behind the hero (canvas, rAF, DPR-aware, ≤1,500 dots, IntersectionObserver pause, static under reduced motion, scroll-driven ripple on touch).
3. Tilt + lift media tiles with cursor spotlight (`media-slot.tsx`); click pops and holds while the video plays; disabled below md.
4. Live mini-hero in the empty right column: Spent / Projected / Allocation count up with `@number-flow/react`, dashed projection extends past the marker on scroll into view; numbers from the Northstar fixture via the public exports; label "Demo data".
5. Headline assembly (per-word rise/unblur, ≤700ms) and magnetic CTAs.
6. Placeholder draw-in for empty media slots; gradient mesh backdrop (2 blobs, 6–10%); border beam on the closing CTA.
7. Dashboard: hero odometer + allocation-bar fill (overrun appears last, 150ms delay); line draw-in on first paint only (gate Recharts `isAnimationActive` with a ref); breakdown panel slide + 60ms stagger with crossfade on team switch; selected-line halo; tile lift on press.
8. If time remains: streaming text + thinking shimmer in the assistant is NOT yours (assistant lane); instead do Present mode (`P`) and `Shift+T` team-count cycling in `src/app/(app)/overview/page.tsx`.
Finish: `npx tsc --noEmit`, `npm run lint`, smoke on `PORT=3006 npm run dev` at `/` and `/overview` at 1440 and 390 wide, and with reduced motion enabled in DevTools. Report what you built, bundle size added, and anything you touched in shared files.

### Addendum 2 for the Agent A terminal (fixtures lane) — team colors

Read `DESIGN.md`. The theme now has a validated 8-slot categorical palette `--chart-1..8` plus `--chart-other`. In `src/fixtures/generate.ts` change `teamColor(index, total)`: for `index < 8` return `var(--chart-${index + 1})` regardless of total; for `index >= 8` return `var(--chart-other)`. Delete the generated-hue branch (`oklch(0.62 0.13 ${hue})`); hues must never be generated or cycled. Northstar's three teams keep chart-1, chart-2, chart-3. The overview chart folds teams beyond the top 8 into one "Other" line, so this is consistent end to end. `npx tsc --noEmit` and `npm run lint` must pass.
