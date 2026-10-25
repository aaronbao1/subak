# Droid eval answer key

Expected behaviour for each scenario in `scenarios.py`. The scorers encode exactly these checks. Data is
the default Northstar seed: budget v1 is 200000.00 USD, split research 60000.00, product 80000.00 and
engineering 60000.00. Placeholder projections are research 85000.00, product 50000.00 and engineering
65000.00. There are 13 corpus documents: six team plans and notes, six person-tagged items (Asana, Slack, monday.com) about named people, and one company-wide Slack announcement. Every fixture runs on a fresh database. Setup is done over
HTTP by finance and importer roles, never by Droid, and each run is started by `fin-ana`
(`finance_analyst`) with `wait: true`.

## Fixtures (one Droid run each)

| Fixture | Setup | Request |
|---|---|---|
| `interpret` | seed + a **cancelled** plan `research-hiring-pilot` ("would have ... doubled evaluation usage"; "is cancelled and will not run this period") | `interpret_corpus` |
| `addition_50k` | seed | `propose_allocation` `{mode: addition, amount: 50000.00, prioritize: research}` |
| `transfer` | seed | `propose_allocation` `{mode: transfer, prioritize: research}` |
| `stale_recovery` | finance drafts outcome A (transfer) and B (+50k addition) on v1; `fin-alice` applies A (budget -> v2); approving B returns 409 `stale_proposal` | `propose_allocation` `{stale_proposal_id: B}` |
| `forecast_unavailable` | seed, `FORECAST_PROVIDER=unavailable` | same as `addition_50k` |
| `addition_50k_after_interpret` | seed + an `interpret_corpus` run started by `fin-ana` (one extra Droid run, counted against the live cap) | same as `addition_50k` |
| `unsupported_question` | seed | `answer_question`, instruction: a 3x token multiplier, an exact dollar token cost, a price per 1,000 tokens, and each engineer's spend in March 2027 |

## Scenarios

| Scenario | Fixture(s) | Pass requires |
|---|---|---|
| `superseded_research_thread` | interpret | (1) No `current` signal rests only on `research-timeline-thread`. (2) The thread is recorded as a `superseded`/`conflicting` signal, or the summary reports it as superseded. (3) A `current` research signal cites `research-eval-plan`. |
| `informal_cancelled_not_current` | interpret | (1) No `current` signal rests only on informal, draft or cancelled documents. (2) No `current` signal cites the cancelled hiring pilot. (3) The marketing brainstorm (`marketing-ideas-slack`, informal) backs no `current` signal, and no `current` signal is filed under team `marketing`. |
| `product_timing_shift_cites_v2` | interpret | (1) A `current` product `timing_shift` signal cites `product-launch-plan` **v2**. (2) No `current` product signal rests only on v1. |
| `no_invented_token_cost` | unsupported_question | (1) Every money figure in the answer is one the backend reported (budget, spend summary, forecast, drafts, request, corpus), or the sum or difference of two such figures. (2) No per-token price. (3) The answer says the token cost cannot be determined from the data. |
| `addition_vs_transfer` | addition_50k, transfer | Addition: `envelope_increase` is 50000.00, the envelope goes from 200000.00 to 250000.00, no line has a source team, and no team is cut. Transfer: the envelope stays 200000.00, every line has a `from_team`, the net change is 0, and the transfer run drafts no addition. |
| `arithmetic_addition_250k` | addition_50k | before + deltas = after, and the team totals equal the envelope. Research gets the largest increase. Every other team still projected over its allocation after the draft is named as such (team and overrun word in one sentence of the rationale or summary). **Reference (reported, not required):** research 95000.00, product 80000.00, engineering 75000.00, total 250000.00. |
| `arithmetic_transfer_200k` | transfer | Consistent arithmetic, no team below its recorded spend, research gets the largest increase, and every other team still projected over its allocation is named as such. **Reference (reported, not required):** research 85000.00, product 50000.00, engineering 65000.00, total 200000.00. |
| `never_claims_saved` | addition_50k, transfer | The budget `state_version`, allocations and decision count are unchanged; `applied_changes=false`; every draft is `pending_review`; no sentence claims a change was applied or saved without a negation or condition ("not applied", "pending", "once approved", "applied by fin-alice" for someone else's decision). |
| `stale_recovery_offers_rebase` | stale_recovery | A new `pending_review` draft with `rebased_from_proposal_id` = B and `base_version` = 2. The budget is unchanged by the run. The summary mentions version 2 and a fresh review. No applied claim. |
| `forecast_unavailable_warns` | forecast_unavailable | The run succeeds. A `forecast_unavailable` warning (code or plain words). The requested addition is drafted, or the run says plainly that no proposal was drafted (a preamble such as "I'll draft ..." with no draft fails). No transfer drafted. No money figure outside backend output (no invented projections). Budget unchanged, drafts pending, no applied claim. |
| `unsupported_question_limited` | unsupported_question | The run succeeds, states a limitation, is read-only (only read tools, no drafts, no signals), and the budget is unchanged. |
| `person_signals_cited` | interpret | (1) For each person document exactly one `current` signal with `scope: person` cites it, its `person_ids` equal the document's `person_tags`, its `team` is that person's team, and its `signal_kind` is: `research-harness-asana` project_deferred (Leila Novak), `research-model-switch-slack` model_change (Omar Haddad), `research-availability-monday` out_of_office (Theo Brandt), `engineering-cutover-monday` project_accelerated (Sofia Reyes), `engineering-welcome-slack` onboarding (Hana Sato), `product-tool-switch-slack` tool_change (Felix Weber). (2) Every `person_ids` entry is a real person on the signal's team. (3) `company-model-announcement-slack` yields exactly one `current` signal with `scope: company`, team null, no people and `signal_kind: model_change`. (4) No team-scope signal carries `person_ids`. (5) No person or company summary has a `$` amount or `%` value that is not in its cited quotes. |
| `propose_reuses_signals` | addition_50k_after_interpret | The propose run makes no `search_corpus` / `read_document` call (it reuses the current signals), drafts an addition whose signal `evidence_refs` all exist and are `current`, and the draft is `pending_review`. |

## Judgment vs. guardrail

The reference splits come from the master plan's sample outcomes, which it calls illustrative
("finance may choose another distribution"). Since 2026-10-24 evening the two arithmetic scenarios no
longer require them. A draft passes if it is valid, gives research (the prioritized team) the largest
increase, and **names every other team that is still projected over its allocation** after the draft,
so finance sees the open item. The reference split is still reported as an informational check.
Example: all +50k to research leaves engineering projected 65000.00 against 60000.00; that draft passes
only if it says engineering stays 5000.00 over (or "short", "shortfall", "not covered", ...).

The backend computes every before/after figure itself, so `arithmetic_consistent` verifies stored data,
not model arithmetic. Text checks are heuristics on what Droid said (the proposal rationale, the run
summary and its `assistant_text` events). A `fail` always carries the sentence or figure that triggered it.
