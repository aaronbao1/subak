# Frontend review — Oct 24, 2026

Sources: a Chrome walkthrough of localhost:3002 at 1440px (landing, overview, teams, team detail, assistant → review → apply, decisions), plus four independent read-only reviews (correctness, demo practicality, accessibility/perf/responsive, interaction ideas). Every bug below was verified against the code path or by executing the fixture generator.

Demo is judged Sunday Oct 25. Items in section 1 can sink the live demo. Fix those first.

---

## 1. Demo-breaking bugs (fix before Sunday)

| # | What breaks | Where | Fix |
|---|---|---|---|
| 1 | The headline sentence **"we got 50,000 more, how should we split it" returns the fallback reply** on the default 8-team dataset. The add regex needs `add`, `$`, or `k`. | `src/fixtures/generate.ts` ~355 | Run `parseAmount` first; any amount ≥ 1,000 without a redistribute verb = add_budget. Add `more|another|split|extra|allocate` to the regex. Mirror in `src/fixtures/index.ts` ~287. |
| 2 | **"Redistribute … without adding funding" produces an ADD BUDGET proposal** in every dataset. `\badd` matches "adding"; add is tested before redistribute. This is the second quick-prompt chip. Violates add ≠ redistribute. | `generate.ts` ~355, `index.ts` ~287 | Test `/redistribut|rebalanc|\bmove\b|shift|reallocat|without (adding|new)/` before the add branch. Also "move 10k from product to research" currently becomes +$10k new money. |
| 3 | **Hard refresh wipes applied decisions** and reverts allocations. Mock state is in-memory. Seen live: after Apply, loading /decisions by URL shows "No decisions yet". Sidebar navigation keeps it. | `src/lib/data/mock-client.ts` | Persist budgets/proposals/decisions/threads/budgetVersion to sessionStorage keyed by dataset; hydrate on construction. Until then: never press refresh in the demo. |
| 4 | **Spent to date drifts between loads** ($196,060 → 196,070 → 196,090 on three loads; Teams page disagreed with Overview by $10). The partial day is derived from the real clock. | `generate.ts` (asOf / partial-day factor) | Pin `asOf` via `NEXT_PUBLIC_DEMO_ASOF` (mid-week, e.g. Wednesday) so numbers are stable and Thu–Sun stay projected. |
| 5 | **On Sunday the projection disappears.** `asOf === period.end` means no "projected" rows, so dashed lines, shaded region, the Projected legend and the footnote all vanish. If judging slips to Monday the period resets to Oct 26 with one partial day and every team "On track". | `spend-by-team-chart.tsx` ~103, `team-spend-chart.tsx` ~70/205, `generate.ts` period | Same fix as 4 (pin asOf). Also treat any row with a non-null projected value as having a projection. |
| 6 | **Projected ($191,324) is lower than Spent ($196,090)** on the hero because Security has no forecast and is excluded from projected but not from spent. The bar hides it with `max()`. | `overview/page.tsx` ~24, `team-list.tsx` ~35 | Compare spent and allocation over the same team set as projected, and say so on all three figures; or show projected as "≥ spent". |
| 7 | **"Revise" on the default dataset creates a second unrelated proposal** (no revise branch in `makeGenericReply`); the old one stays proposed. | `generate.ts` ~337–443 | Port the Northstar revise branch (`revisesProposalId`, mark old `revised`). |
| 8 | **Wrong team answered**: "Why is Sales Engineering tracking under…" answers about Engineering (substring match). | `generate.ts` ~422 | Match longest team name first or on word boundary. |
| 9 | Team detail's only assistant button prefills "Tell me about {team}'s spending" → fallback in both datasets. | `team-header.tsx` ~680 | Prefill "Why is {team} tracking over/under its allocation?" and add a generic per-team branch to Northstar replies. |
| 10 | Esc inside the review dialog **closes the review AND the drawer** (sibling dialogs both think they're topmost). | `assistant-drawer.tsx` ~72/153 | Render ProposalReview/SourceSheet inside `SheetContent`, or ignore the Sheet's close while a review is open. |
| 11 | `?teams=16` is sticky in localStorage; `?teams=northstar` is not, and it only applies on an app route. Landing's "Open dashboard" always gives 8 teams. A reload on `/teams/research` under Northstar silently swaps to the 8-team company with the same ids. | `mock-client.ts` ~19 | Persist northstar symmetrically; show the active dataset + reset link in the shell. |
| 12 | Stale/failed proposals can never be dismissed from "Needs attention". | `proposal-review.tsx` ~45, `decision-log.tsx` ~34 | Allow Reject/Dismiss for stale and failed. |

## 2. Credibility problems (an FP&A manager would stop trusting it)

1. **"Spent to date" counts included usage as spend.** ~20–23% of the total is "Included usage", which the UI itself says is not billed. Exclude `included_usage` from spent totals (one `billableSpent()` helper) and show it as a separate line. Fixtures must then rebalance targets onto billable components.
2. **The overview can't answer "who is over?"** Hero says "Projected 93% of allocation" with no red because the company total is fine while the split is wrong. Add one line under the hero: "4 teams likely over: Research, Data Science, Customer Support, Engineering", and/or a compact variance table under the chart.
3. **Weekly budgeting with no period control.** FP&A allocates monthly/quarterly; "$200k/week AI envelope reallocated on Saturday" reads as a toy. Label it "Planning period", pin asOf, add a period selector later.
4. **"Envelope" still appears 50+ times** outside the hero: proposal card ("Adds $25,000 to the envelope", "Company envelope"), review dialog, decision log ("ENVELOPE" column), assistant copy and quick prompts, fixtures. Also "Projection (7 of 8 teams)" and lowercase "week of oct 19" on /teams.
5. **Timestamps disagree.** Chat bubbles are local time; proposals and receipts are forced UTC ("7:12 PM UTC" next to a 12:12 PM message). Drop `timeZone: "UTC"` from `fmtDateTime`.
6. **"Placeholder" appears 6+ times on one screen.** To finance it means "made up". Say "sample projection" once in the hero with a tooltip; drop the chart-footer sentence.
7. **Landing copy contradicts the product.** "Real-time token spend" (data is daily USD exports), "before the quarter is over" (period is a week), "Three teams, one period" (default is 8). Say "Daily AI spend, projections and allocations by team", "before the period is over", drop the count.
8. **No approver identity, no export, no alerts.** Receipts say `finance@demo`. Cheap wins: a named approver on the receipt, "Download CSV" on /teams and /decisions built from in-memory rows.
9. Hard-coded "Research" and "$25,000" in the quick prompts; derive from `teams` and `formatAmount(25_000, unit)`.
10. Northstar scripted replies ignore the typed amount ("add $20,000" → the fixed $50k proposal) and quote stale numbers after an apply. Build strings from `state.budgets`.
11. The incoming token-unit direction has no guard anywhere: every total sums `amount` regardless of `unit` and labels it with the budget unit. Sum only matching units and surface "mixed units" otherwise.

## 3. Make it look nicer (from the Chrome pass)

**Overview**
1. **One big number.** Spent, Projected and Allocation are all ~28px. Make Spent to date ~56–64px, the other two secondary. That is the "nice big number" the brief asked for.
2. **Fill the empty right column.** "Select a team to see its breakdown" occupies a quarter of the width until a click. Default it to a company summary: top 3 over-allocation teams with variance, or the cost-component bars.
3. **The Friday → Saturday cliff.** All 8 lines drop from ~$9K to ~$3K because of weekend + partial day + small placeholder projections. It reads as a bug. Shade weekends, label "weekend", or project from weekday run-rate.
4. **Clicking a line between dots doesn't select.** Only dots work. Add an invisible wide stroke (12–16px) per line for hit testing, or use `activeDot` + `onClick` on the chart with nearest-series lookup. Legend chips are the safe demo target meanwhile.
5. **Cost components collapsed** into a thin strip, leaving a third of the page empty at 900px tall. Expand by default or move into the right column.
6. Page header note "Internal allocations in USD — planning records, not provider limits or purchases." is the first line on every page. Demote to the sidebar footer or a tooltip.
7. 16-team colors: adjacent hues 22.5° apart at identical lightness are indistinguishable on a projector. Alternate lightness on odd indices or group beyond 8 as "Other".
8. Two different status-chip styles (Overview "Watch" amber-on-amber vs Teams neutral-with-dot). One `StatusChip` using the `--warning`/`--success` tokens that already exist and are unused.

**Teams and team detail**
9. Teams table is ~830px centered in a 1300px main. Let it breathe to ~1100px and add a Variance column (projection − allocation) with a small inline bar.
10. Team detail stacked bars: 7 bars in 800px with tiny projected bars. Wider bars (barSize 28–36) and a dashed "allocation / 7" daily reference line.
11. Context cards are single column with a large empty right side; two columns at lg.
12. Make the stacked-bar day selection keyboard reachable (row of day buttons).

**Assistant**
13. **The drawer backdrop blurs the entire dashboard**, so you cannot watch numbers change while a proposal is previewed. Make it non-modal or push the layout; the apply moment should be visible on the hero.
14. Textarea is disabled while sending, so focus drops and the next question needs a click; chips unmount and shift the composer 60px. Keep it enabled, gate on `canSend`, reserve chip height, refocus after reply.
15. Typing in the composer re-renders the whole app (store has no selectors; composer text lives in the store). Keep draft text local; use `useShallow` selectors.

**Landing**
16. **Light landing → dark dashboard** flip when you click "Open dashboard". Pick one (dark landing matches the product) or add a theme toggle and respect it both sides.
17. **Hero right half is empty** at 1440px. Put a live mini-hero there (see idea A6) or a real screenshot.
18. Three identical grey placeholder frames read as "unfinished". Until videos exist, draw animated ghost bars (A14) or use real screenshots.
19. Scrollbar/color-scheme are set dark on `<html>`; on the white landing the scrollbar thumb is 14% white on white (visible on Windows/Linux). Scope to the app wrapper.

**Everywhere**
20. Alpha-faded muted text (`/60`, `/70`) drops below 4.5:1 contrast on cards. Use full `text-muted-foreground` for informative text.
21. No `prefers-reduced-motion` rule anywhere. Add one in `globals.css` before adding any of the motion below.
22. Skeleton shapes don't match content below md (table rows vs cards), and the mock resolves in ~120ms so skeletons flash once. Delay skeleton 150ms or hold 300ms.
23. Mobile legend at 16 teams is clipped to 64px with a hidden scrollbar; drop `max-h-16` below sm or show "+N more".
24. Horizontal two-finger swipe over the chart can trigger browser Back to the landing page mid-demo. Add `overscroll-x-none` on main; use the arrow buttons in the demo.

## 4. The sexy stuff (interactive, "new AI era")

Install once: `npm i motion @number-flow/react` (both work with React 19 / Next 16; import from `"motion/react"`). Use `useReducedMotion()` in every item. Effort: S ≤2h, M 2–5h, L 5h+.

**Do these 6 first (~19h, two people in a day)**
1. **Cursor-reactive dot field** behind the landing hero: faint grid of dots; dots within ~140px of the cursor brighten and nudge away, spring back. Canvas + rAF, DPR-aware, ~1,500 dots cap, static under reduced motion. (M)
2. **Tilt + lift tiles with spotlight**: media tiles tilt ≤6° toward the cursor, click pops them (scale 1.03, deeper shadow) and holds while the video plays; a radial glow follows the cursor across the frame. `motion` springs + one CSS `radial-gradient` on `--mx/--my`. (S–M)
3. **Hero number odometer + allocation bar fill** on /overview: Spent rolls in on load and ticks when a proposal is applied; the bar grows spent → projected → overrun with a 150ms delay on the overrun. `@number-flow/react` + CSS width transition. (S)
4. **Line draw-in + breakdown panel slide**: lines reveal left→right on first paint only (Recharts `isAnimationActive` gated by a ref); panel enters from the right with a 60ms stagger of its sections; switching teams crossfades. (S)
5. **Streaming replies + thinking shimmer**: mock replies stream in 15–25ms word chunks with a pulsing caret; "Working…" becomes gradient-shimmer text that phases through "Reading spend records → Drafting proposal", driven by real `toolCalls`. (M)
6. **Proposal diff that moves money**: before→after bars per team; for redistribute an amount pill travels from the giving team to the receiving team while the total stays pinned with a lock ("Total unchanged"); for add-budget a new segment grows in. `motion` `layout` + `animate()`. (M–L; the `layout` re-sort subset is 1.5h)

**Landing showpieces**
- Magnetic CTA buttons (drift ≤8px toward cursor). S
- Headline that assembles: words rise, unblur, stagger 40ms; underline draws under "before the period is over". S
- Live "one number" hero demo in the empty right column: Spent/Projected/Allocation count up, dashed projection extends past the marker on scroll into view. M
- Scroll-driven number reveals in the closing CTA. S
- Sticky scroll storytelling: one pinned media frame crossfades overview → breakdown → reallocate as text scrolls. L
- Animated token-stream: small squares in team colors flow along three bezier streams into one allocation bar; speed ∝ spend. M
- Gradient mesh backdrop: two blurred blobs at 6–10% opacity on a 30–40s drift. S
- Provider marquee (monochrome text wordmarks, pause on hover, edge mask). S
- Border beam on the closing CTA card (conic gradient travelling the 1px border). S
- Scroll progress hairline + active section label in the top bar. S
- Placeholder draw-in: ghost bars grow and the hairline chart draws when a slot enters view. S

**Dashboard micro-interactions (stay calm)**
- Hover crosshair + value pills pinned at the right edge aligned to each line. M
- Selected-line halo (SVG blur filter on the selected line only; others fade to 0.2 in 250ms). S
- Shared-element transition: team name + color dot morph from panel/card into the team page header (React ViewTransition, experimental flag). M
- Tile lift on click: 2px lift + brighter ring on press, selected stays lifted. S
- Receipt animation: badge morphs proposed → pending → applied with a check that draws in; rows re-sort with layout animation; receipt slides up; hero numbers tick. Only after the client confirms. M
- Skeleton shimmer sweep, staggered hero → chart → components. S
- Cost-component bars grow on expand. S
- Ambient team tint: selected team color at 10% on the chart ring and 30% on the panel's top border. S
- Sidebar indicator glides between nav items (`layoutId`). S

**Assistant / AI-feel**
- Tool-call timeline that ticks in 300ms apart with checks drawing in, collapses after. S–M
- Proposal card materializes: grows from 0 height with a 1px ring flash fading over 1.2s. S
- Citation hover-preview: title, quoted span, mini sparkline; superseded shows its "outdated" tag inside the preview. M
- Ask-from-anywhere handoff: the prefilled question flies as a pill into the composer as the drawer opens. M
- Drawer edge pulse: 1px gradient pulse on the Sheet's left border while sending. S

**Demo-day flourishes**
- `Shift+T` cycles 3 / 8 / 16 teams live with line draw-in: "it scales". S
- Typing `unicorn` recolors the brand mark cells to team colors for 400ms. S
- Cmd-K palette: team jump, open decisions, "Ask: redistribute". M (only if it fully works)
- Present mode (`P`): collapses sidebar, scales hero 1.25×, soft cursor halo for the projector. S–M
- Receipt tear-off on /decisions: new receipts slide in with a dotted edge; hover "Copy receipt". S
- Judge tour `?tour=1`: numbered dots with one-line "why this matters" hovers. M

**Avoid (looks cheap or hurts finance credibility)**
1. Confetti, emoji, or sound on Apply. The receipt is the celebration.
2. Neon purple/cyan "AI gradients" inside the dashboard. Stay on `--ring` blue ≤15% alpha and the chart tokens.
3. Animating numbers that aren't real (fake live tickers, "tokens saved" counters, invented tool names).
4. Scroll hijacking (Lenis/Locomotive), horizontal scroll-jacked sections, parallax on text.
5. Three.js / Spline hero scenes (1MB+, WebGL jank on demo wifi). Also skip typewriter headings, custom cursors, glass blur on every card.

## 5. Demo script (Northstar, 3 minutes)

Start on `http://localhost:3002/overview?teams=northstar` (the param only works on an app route). Do not hard-reload after this until bug 3 is fixed. Click **legend chips**, not lines.

1. (Optional, 10s) Landing: "Northstar budgets AI spend by team. FP&A gets one view and an assistant that proposes reallocations with receipts." Open dashboard. Skip if media slots are still empty.
2. Hero: "Spent $95k of a $200k allocation, projected $200k. Company looks fine. The problem is the split."
3. Click the **Research** legend chip. Panel: "Allocation $60k, spent $45k, projection $85k, likely over. API is the driver, all reported charges."
4. View team → Research page: approved Q4 plan, high confidence. Scroll to the greyed card: "An older Slack thread had a smaller timeline. Superseded, never cited." Open one source.
5. Teams: "Research over, Product under because the v4 launch moved, Engineering on track."
6. Assistant. Type exactly `Why is Research tracking over its allocation?`. Expand the steps: "That's the agent reading the plan and the spending export."
7. Type `What if Research grows another 20%?` → it declines to invent a number. "It knows what it cannot do."
8. Type `We got 50,000 more, how should we split it?` → ADD BUDGET, $200,000 → $250,000, Research +35k, Engineering +15k, Product +0.
9. (Optional) `Revise: make it 40k for Research instead` → new card, old one marked Revised.
10. Review → read Before/After/Change/Spent/Projection reviewed → expand Evidence → note "Q4 eval expansion approved by VP Research" → Apply → green "Applied and saved" → Done → close drawer.
11. Hero: Total allocation $250,000. Click Decisions: receipt, deltas, note, projection reviewed at the time.
12. Close: "Nothing here touched a vendor account. It's an internal budget record with the evidence attached, and finance made the call."

Phrases that FAIL today on Northstar: "We have another $25,000 to allocate this week." (third chip), "Tell me about …", any "why" about Engineering, the "Redistribute … without adding funding" chip (wrong kind). On the default 8-team dataset additionally: "50,000" without add/$/k, "compare", "what if", and "Revise".

## 6. What is already strong (don't touch)

- full_period vs remaining handled once and correctly in three places; no double counting.
- Fixture arithmetic exact for n = 0, 1, 3, 8, 16 and Northstar; lines sum to totals; redistribute keeps the total.
- Proposal lifecycle: seven distinct states, apply disabled while pending, success only after the client confirms, stale-version check, receipts snapshot `forecastsReviewed`.
- Superseded context genuinely distinguishable (strikethrough, "Replaced by", sorted last, excluded from citations).
- Scenario refusal and unavailable-forecast handling give a credible "knows when to stop" beat.
- Calm, consistent encoding: solid = recorded, dashed/hollow = projected across every chart; empty states on every route; hydration-safe data loading; the team-detail page is the most polished screen.
