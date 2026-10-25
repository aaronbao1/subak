# Droid eval results: `sdk` runner

Generated 2026-10-25T01:08:09+00:00 by `python -m evals.run --runner sdk`. Answer key: [`../answer_key.md`](../answer_key.md).

**1 pass, 1 fail, 0 not run** (of 2 scenarios).

Live Droid runs used by this invocation: 2. Total lines in `backend/data/live_runs.log` afterwards: 15.

| Scenario | Result | Fixture(s) | Reasons |
|---|---|---|---|
| `arithmetic_transfer_200k` Transfer reproduces 85k/50k/65k @ 200k | **fail** | transfer | transfer:transfer_drafted: no transfer proposal drafted (drafts: none) |
| `forecast_unavailable_warns` Works with the forecast unavailable, with a warning | **pass** | forecast_unavailable | 8 check(s) passed |

## Runs

| Fixture | Run | Status | Duration | Tools | Drafts | Signals | Credits |
|---|---|---|---|---|---|---|---|
| transfer | `run_82f2610e-cab7-4fdf-a1de-4f47adae4a79` | succeeded | 90.38 s | 21 | none | 5 | 59571.0 |
| forecast_unavailable | `run_df86e26f-842d-4625-8556-5afe19e43eb4` | succeeded | 105.91 s | 37 | addition pending_review | 6 | 63486.0 |

## Check detail

### `arithmetic_transfer_200k`: fail
_Reference split from the answer key; a different valid split is a judgment divergence, scored as fail._
- pass `transfer:run_succeeded`: run run_82f2610e-cab7-4fdf-a1de-4f47adae4a79 succeeded
- FAIL `transfer:transfer_drafted`: no transfer proposal drafted (drafts: none)

### `forecast_unavailable_warns`: pass
- pass `forecast_unavailable:run_succeeded`: run run_df86e26f-842d-4625-8556-5afe19e43eb4 succeeded
- pass `warns_forecast_unavailable`: the run warns that the forecast is unavailable
- pass `completed_or_declined`: drafted addition prop_acdd2250-70e3-4596-93d3-1912a63fe08a
- pass `no_transfer_without_forecast`: no transfer drafted on recorded spend alone
- pass `no_invented_projection`: every money figure comes from backend output
- pass `forecast_unavailable:budget_unchanged`: budget stayed at version 1, no decision recorded, applied_changes=false
- pass `forecast_unavailable:drafts_pending_review`: every draft is pending_review (1 draft(s))
- pass `forecast_unavailable:no_applied_claim`: no sentence claims a change was applied or saved
