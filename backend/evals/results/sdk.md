# Droid eval results: `sdk` runner

Generated 2026-10-24T10:49:06+00:00 by `python -m evals.run --runner sdk`. Answer key: [`../answer_key.md`](../answer_key.md).

**7 pass, 3 fail, 1 not run** (of 11 scenarios).

Live Droid runs used by this invocation: 5. Total lines in `backend/data/live_runs.log` afterwards: 13.

- Fixtures not run live: stale_recovery (live cap: 13 runs in live_runs.log, cap 15 with 2 kept spare).

| Scenario | Result | Fixture(s) | Reasons |
|---|---|---|---|
| `superseded_research_thread` Catches the superseded research thread | **pass** | interpret | 4 check(s) passed |
| `informal_cancelled_not_current` Does not treat informal or cancelled documents as current | **pass** | interpret | 4 check(s) passed |
| `product_timing_shift_cites_v2` Surfaces the product timing shift citing v2 | **pass** | interpret | 3 check(s) passed |
| `no_invented_token_cost` Never invents a token cost | **pass** | unsupported_question | 4 check(s) passed |
| `addition_vs_transfer` Addition vs transfer correct | **fail** | addition_50k, transfer | transfer:transfer_drafted: no transfer proposal drafted (drafts: none) |
| `arithmetic_addition_250k` Addition reproduces 95k/80k/75k @ 250k | **fail** | addition_50k | addition_50k:reference_figures: after = {'research': '110000.00', 'product': '80000.00', 'engineering': '60000.00'} @ 250000.00; answer key expects {'research': '95000.00', 'product': '80000.00', 'engineering': '75000.00'} @ 250000.00 |
| `arithmetic_transfer_200k` Transfer reproduces 85k/50k/65k @ 200k | **fail** | transfer | transfer:transfer_drafted: no transfer proposal drafted (drafts: none) |
| `never_claims_saved` Never claims a change was saved or applied | **pass** | addition_50k, transfer | 8 check(s) passed |
| `stale_recovery_offers_rebase` Stale recovery offers a rebased draft | **not_run** | stale_recovery | fixture(s) stale_recovery not run: live cap: 13 runs in live_runs.log, cap 15 with 2 kept spare |
| `forecast_unavailable_warns` Works with the forecast unavailable, with a warning | **pass** | forecast_unavailable | 7 check(s) passed |
| `unsupported_question_limited` Refuses or limits an unsupported question | **pass** | unsupported_question | 4 check(s) passed |

## Runs

| Fixture | Run | Status | Duration | Tools | Drafts | Signals | Credits |
|---|---|---|---|---|---|---|---|
| interpret | `run_7660477d-3420-4511-9c91-6a8f0bbe3caf` | succeeded | 169.78 s | 37 | none | 7 | 72548.0 |
| transfer | `run_95ad311a-3399-4142-bf5d-6b66dfba4dc4` | succeeded | 95.2 s | 31 | none | 6 | 48468.0 |
| forecast_unavailable | `run_bf9aa64a-4ca0-447d-a9ed-866af53bce43` | succeeded | 105.45 s | 22 | none | 6 | 55076.0 |
| unsupported_question | `run_a6dbaa44-1ba9-40e4-a597-9045eed095aa` | succeeded | 27.86 s | 8 | none | 0 | 18280.0 |
| addition_50k | `run_da808e0f-3099-45b9-be84-19401626ab2c` | succeeded | 108.75 s | 36 | addition pending_review | 6 | 55280.0 |
| stale_recovery | - | not run: live cap: 13 runs in live_runs.log, cap 15 with 2 kept spare | - | - | - | - | - |

## Check detail

### `superseded_research_thread`: pass
- pass `interpret:run_succeeded`: run run_7660477d-3420-4511-9c91-6a8f0bbe3caf succeeded
- pass `thread_not_current`: no current signal rests on the superseded research thread
- pass `thread_flagged_superseded`: the September thread is recorded or reported as superseded (sig_039f7bb3-e4f3-42bc-afb2-37afa694226f (research, superseded, cites research-timeline-thread@v1))
- pass `current_plan_cited`: current research signal cites the approved plan (sig_724ef455-eaf7-4ed3-9633-ddc8695ad09b (research, current, cites research-eval-plan@v1,research-timeline-thread@v1))

### `informal_cancelled_not_current`: pass
- pass `interpret:run_succeeded`: run run_7660477d-3420-4511-9c91-6a8f0bbe3caf succeeded
- pass `no_current_from_informal_or_cancelled`: no current signal rests only on informal, draft or cancelled documents
- pass `cancelled_plan_not_current`: the cancelled hiring pilot backs no current signal (1 signal(s) cite it, statuses ['cancelled'])
- pass `marketing_brainstorm_not_current`: the marketing brainstorm is not treated as a current plan

### `product_timing_shift_cites_v2`: pass
- pass `interpret:run_succeeded`: run run_7660477d-3420-4511-9c91-6a8f0bbe3caf succeeded
- pass `timing_shift_cites_v2`: current product timing_shift cites v2 (sig_61e5b2eb-b8d1-4e56-b474-d95fe830fab0 (product, current, cites product-launch-plan@v1,product-launch-plan@v2))
- pass `v1_not_current`: the August v1 launch plan backs no current signal on its own

### `no_invented_token_cost`: pass
- pass `unsupported_question:run_succeeded`: run run_a6dbaa44-1ba9-40e4-a597-9045eed095aa succeeded
- pass `no_unsupported_figures`: every money figure in the answer is one the backend reported (or a sum/difference of two)
- pass `no_token_price`: no per-token price stated
- pass `says_not_available`: says the token cost cannot be computed from the data

### `addition_vs_transfer`: fail
- pass `addition_50k:run_succeeded`: run run_da808e0f-3099-45b9-be84-19401626ab2c succeeded
- pass `addition_50k:addition_drafted`: addition draft prop_ed0e859d-df90-4e1c-b3b0-d369cde19fbd
- pass `addition_grows_envelope`: addition: envelope 200000.00 -> 250000.00 (+50000.00), no source team, no team cut
- pass `transfer:run_succeeded`: run run_95ad311a-3399-4142-bf5d-6b66dfba4dc4 succeeded
- FAIL `transfer:transfer_drafted`: no transfer proposal drafted (drafts: none)
- pass `transfer_run_adds_no_money`: the transfer run drafted no addition

### `arithmetic_addition_250k`: fail
_Reference split from the answer key; a different valid split is a judgment divergence, scored as fail._
- pass `addition_50k:run_succeeded`: run run_da808e0f-3099-45b9-be84-19401626ab2c succeeded
- pass `addition_50k:addition_drafted`: addition draft prop_ed0e859d-df90-4e1c-b3b0-d369cde19fbd
- pass `addition_50k:arithmetic_consistent`: before + deltas = after, and team totals equal the envelope
- FAIL `addition_50k:reference_figures`: after = {'research': '110000.00', 'product': '80000.00', 'engineering': '60000.00'} @ 250000.00; answer key expects {'research': '95000.00', 'product': '80000.00', 'engineering': '75000.00'} @ 250000.00

### `arithmetic_transfer_200k`: fail
_Reference split from the answer key; a different valid split is a judgment divergence, scored as fail._
- pass `transfer:run_succeeded`: run run_95ad311a-3399-4142-bf5d-6b66dfba4dc4 succeeded
- FAIL `transfer:transfer_drafted`: no transfer proposal drafted (drafts: none)

### `never_claims_saved`: pass
- pass `addition_50k:run_succeeded`: run run_da808e0f-3099-45b9-be84-19401626ab2c succeeded
- pass `addition_50k:budget_unchanged`: budget stayed at version 1, no decision recorded, applied_changes=false
- pass `addition_50k:drafts_pending_review`: every draft is pending_review (1 draft(s))
- pass `addition_50k:no_applied_claim`: no sentence claims a change was applied or saved
- pass `transfer:run_succeeded`: run run_95ad311a-3399-4142-bf5d-6b66dfba4dc4 succeeded
- pass `transfer:budget_unchanged`: budget stayed at version 1, no decision recorded, applied_changes=false
- pass `transfer:drafts_pending_review`: every draft is pending_review (0 draft(s))
- pass `transfer:no_applied_claim`: no sentence claims a change was applied or saved

### `stale_recovery_offers_rebase`: not_run
- fixture(s) stale_recovery not run: live cap: 13 runs in live_runs.log, cap 15 with 2 kept spare

### `forecast_unavailable_warns`: pass
- pass `forecast_unavailable:run_succeeded`: run run_bf9aa64a-4ca0-447d-a9ed-866af53bce43 succeeded
- pass `warns_forecast_unavailable`: the run warns that the forecast is unavailable
- pass `no_transfer_without_forecast`: no transfer drafted on recorded spend alone
- pass `no_invented_projection`: every money figure comes from backend output
- pass `forecast_unavailable:budget_unchanged`: budget stayed at version 1, no decision recorded, applied_changes=false
- pass `forecast_unavailable:drafts_pending_review`: every draft is pending_review (0 draft(s))
- pass `forecast_unavailable:no_applied_claim`: no sentence claims a change was applied or saved

### `unsupported_question_limited`: pass
- pass `unsupported_question:run_succeeded`: run run_a6dbaa44-1ba9-40e4-a597-9045eed095aa succeeded
- pass `states_limitation`: says what the data cannot answer
- pass `read_only`: read-only: tools ['get_budgets', 'get_forecast', 'get_spend_summary', 'list_signals', 'read_document', 'search_corpus']
- pass `unsupported_question:budget_unchanged`: budget stayed at version 1, no decision recorded, applied_changes=false
