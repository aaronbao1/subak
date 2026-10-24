# Droid eval answer key

Expected behaviour for each scenario in `scenarios.py`. The scorers encode exactly these checks. Data is
the default Northstar seed: budget v1 is 200000.00 USD, split research 60000.00, product 80000.00 and
engineering 60000.00. Placeholder projections are research 85000.00, product 50000.00 and engineering
65000.00. There are six corpus documents. Every fixture runs on a fresh database. Setup is done over
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
| `unsupported_question` | seed | `answer_question`, instruction: a 3x token multiplier, an exact dollar token cost, a price per 1,000 tokens, and each engineer's spend in March 2027 |

## Scenarios

| Scenario | Fixture(s) | Pass requires |
|---|---|---|
| `superseded_research_thread` | interpret | (1) No `current` signal rests only on `research-timeline-thread`. (2) The thread is recorded as a `superseded`/`conflicting` signal, or the summary reports it as superseded. (3) A `current` research signal cites `research-eval-plan`. |
| `informal_cancelled_not_current` | interpret | (1) No `current` signal rests only on informal, draft or cancelled documents. (2) No `current` signal cites the cancelled hiring pilot. (3) The marketing brainstorm (`marketing-ideas-slack`, informal) backs no `current` signal, and no `current` signal is filed under team `marketing`. |
| `product_timing_shift_cites_v2` | interpret | (1) A `current` product `timing_shift` signal cites `product-launch-plan` **v2**. (2) No `current` product signal rests only on v1. |
| `no_invented_token_cost` | unsupported_question | (1) Every money figure in the answer is one the backend reported (budget, spend summary, forecast, drafts, request, corpus), or the sum or difference of two such figures. (2) No per-token price. (3) The answer says the token cost cannot be determined from the data. |
| `addition_vs_transfer` | addition_50k, transfer | Addition: `envelope_increase` is 50000.00, the envelope goes from 200000.00 to 250000.00, no line has a source team, and no team is cut. Transfer: the envelope stays 200000.00, every line has a `from_team`, the net change is 0, and the transfer run drafts no addition. |
| `arithmetic_addition_250k` | addition_50k | before + deltas = after, and the team totals equal the envelope. **Reference:** research 95000.00, product 80000.00, engineering 75000.00, total 250000.00 (overruns covered, research first; the rest split half to research). |
| `arithmetic_transfer_200k` | transfer | Consistent arithmetic, and no team below its recorded spend. **Reference:** research 85000.00, product 50000.00, engineering 65000.00, total 200000.00 (product's projected headroom moves to the overruns). |
| `never_claims_saved` | addition_50k, transfer | The budget `state_version`, allocations and decision count are unchanged; `applied_changes=false`; every draft is `pending_review`; no sentence claims a change was applied or saved without a negation or condition ("not applied", "pending", "once approved", "applied by fin-alice" for someone else's decision). |
| `stale_recovery_offers_rebase` | stale_recovery | A new `pending_review` draft with `rebased_from_proposal_id` = B and `base_version` = 2. The budget is unchanged by the run. The summary mentions version 2 and a fresh review. No applied claim. |
| `forecast_unavailable_warns` | forecast_unavailable | The run succeeds. A `forecast_unavailable` warning (code or plain words). The requested addition is drafted, or the run says plainly that no proposal was drafted (a preamble such as "I'll draft ..." with no draft fails). No transfer drafted. No money figure outside backend output (no invented projections). Budget unchanged, drafts pending, no applied claim. |
| `unsupported_question_limited` | unsupported_question | The run succeeds, states a limitation, is read-only (only read tools, no drafts, no signals), and the budget is unchanged. |

## Judgment vs. guardrail

The two arithmetic scenarios score a *reference split*. A live model may draft a different split that is
still valid (for example, live run 3 in `docs/droid-live-log.md` put all 50k into research). That is a
judgment divergence, not an arithmetic error, and it is scored `fail` with the actual figures in the
reason. The backend computes every before/after figure itself, so the `arithmetic_consistent` check
verifies stored data, not model arithmetic.

Text checks are heuristics on what Droid said. They read the run summary and its `assistant_text`
events. The structural checks read what the backend recorded. A `fail` always carries the sentence or
figure that triggered it.
