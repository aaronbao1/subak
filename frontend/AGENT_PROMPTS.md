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

## Agent D — Assistant, allocation review, decisions (port 3004)

You are building the assistant drawer, the allocation review flow, and the decision history for an AI-spend planning tool used by an enterprise FP&A team. Read `CLAUDE.md` in this folder, then `../docs/frontend-plan.md` sections "Active assistant" and "Review, action and receipt" and "Acceptance checks". Your lane is ONLY `src/components/assistant/**`, `src/components/allocation/**`, and `src/app/decisions/**`. Do not edit anything else. All data and actions go through `useAppStore()` in `src/lib/store.ts`: `threads.main`, `sendMessage`, `proposals`, `applyProposal`, `rejectProposal`, `assistantDraft`, `clearAssistantDraft`. Never import fixtures. Markdown via `react-markdown` (installed). shadcn from `src/components/ui`.

The mock replies to "redistribute…" and "we have another 50,000, prioritize research" with a proposal; try those first.

Deliver:
1. `src/components/assistant/assistant-drawer.tsx` (keep the existing Sheet + store wiring): message list with markdown, user/assistant styling, timestamps, auto-scroll, a composer with Enter to send, a sending state, and 3 quick prompts. If `assistantDraft` is set, prefill the composer and call `clearAssistantDraft()`.
2. On each assistant message: an expandable compact "Work record" listing `toolCalls` (name humanized, summary) so Factory SDK activity is visible without being a console; a "Sources" row of citation chips showing title and date, with the excerpt on hover or expand.
3. When a message has `proposalId`, render an inline proposal card: a clear kind label ("Adds $50,000 to envelope" vs "Redistributes existing envelope, total unchanged"), envelope before → after, and per-team before/after/delta. A "Review" button opens the full review.
4. `src/components/allocation/proposal-review.tsx` as a Dialog: kind, envelope before/after, added amount if any, per-team table (allocation before, after, delta, and spent/projection for context taken from the proposal's `forecastsReviewed`, not the live store, so the review shows what the assistant actually looked at), rationale, citations. Actions: **Apply** (sets a local pending state, disables the button, calls `applyProposal`; on success shows a receipt with what changed, when, who; on error shows the error text and leaves allocations unchanged), **Reject** (calls `rejectProposal`, confirms it is recorded), **Revise** (closes and prefills the composer with "Revise this proposal: "). A proposal whose `status` is not `proposed` shows its state (applied / rejected / revised / stale / failed with `failureReason`) and disables Apply. A double-click can never apply twice.
5. `/decisions` page: history from `decisions` newest first, each a receipt: action (applied/rejected), kind, timestamp, who, per-team before/after, note, the `rationale`, and an expandable "Projections reviewed at the time" section from `forecastsReviewed` (with their placeholder tag if any). Also list proposals that are stale or failed with a one-line explanation.
6. Success is shown only after the store call resolves. Pending, failed, and stale are visually distinct from applied.

Calm, restrained. Phone width works. When done: `npx tsc --noEmit`, `npm run lint`, smoke test with `PORT=3004 npm run dev`: send the 50k message, review, apply, confirm the receipt and that the Overview numbers changed (Overview may still be a placeholder; the store budgets are what matter). Reply with a short summary and anything in `NEEDS.md` (create under "Agent D").
