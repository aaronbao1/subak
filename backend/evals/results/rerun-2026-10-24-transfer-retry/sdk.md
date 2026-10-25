# Droid eval results: `sdk` runner

Generated 2026-10-25T01:47:02+00:00 by `python -m evals.run --runner sdk`. Answer key: [`../answer_key.md`](../answer_key.md).

**0 pass, 1 fail, 0 not run** (of 1 scenarios).

Live Droid runs used by this invocation: 1. Total lines in `backend/data/live_runs.log` afterwards: 17.

| Scenario | Result | Fixture(s) | Reasons |
|---|---|---|---|
| `arithmetic_transfer_200k` Transfer reproduces 85k/50k/65k @ 200k | **fail** | transfer | transfer:reference_figures: after = {'research': '85000.00', 'product': '55000.00', 'engineering': '60000.00'} @ 200000.00; answer key expects {'research': '85000.00', 'product': '50000.00', 'engineering': '65000.00'} @ 200000.00 |

## Runs

| Fixture | Run | Status | Duration | Tools | Drafts | Signals | Credits |
|---|---|---|---|---|---|---|---|
| transfer | `run_4b85774e-0c3a-44c0-98b9-8201a61520cc` | succeeded | 126.36 s | 30 | transfer pending_review | 6 | 72633.0 |

## Check detail

### `arithmetic_transfer_200k`: fail
_Reference split from the answer key; a different valid split is a judgment divergence, scored as fail._
- pass `transfer:run_succeeded`: run run_4b85774e-0c3a-44c0-98b9-8201a61520cc succeeded
- pass `transfer:transfer_drafted`: transfer draft prop_ce6db8ad-3a5e-4e3c-a404-7830de510b61
- pass `transfer:arithmetic_consistent`: before + deltas = after, and team totals equal the envelope
- FAIL `transfer:reference_figures`: after = {'research': '85000.00', 'product': '55000.00', 'engineering': '60000.00'} @ 200000.00; answer key expects {'research': '85000.00', 'product': '50000.00', 'engineering': '65000.00'} @ 200000.00
- pass `no_team_below_recorded_spend`: no team is cut below its recorded spend
