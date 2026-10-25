# Droid eval results: `sdk` runner

Generated 2026-10-25T05:46:50+00:00 by `python -m evals.run --runner sdk`. Answer key: [`../answer_key.md`](../answer_key.md).

**1 pass, 0 fail, 0 not run** (of 1 scenarios).

Live Droid runs used by this invocation: 1. Total lines in `backend/data/live_runs.log` afterwards: 21.

| Scenario | Result | Fixture(s) | Reasons |
|---|---|---|---|
| `arithmetic_addition_250k` Valid +50k addition that prioritizes research and flags other overruns | **pass** | addition_50k | 6 check(s) passed |

## Runs

| Fixture | Run | Status | Duration | Tools | Drafts | Signals | Credits |
|---|---|---|---|---|---|---|---|
| addition_50k | `run_a01faf3f-4018-4d80-9e20-f8709de7913e` | succeeded | 42.37 s | 77 | addition pending_review | 12 | 51762.0 |

## Check detail

### `arithmetic_addition_250k`: pass
_The 95k/80k/75k @ 250k reference split is reported, not required (it is illustrative)._
- pass `addition_50k:run_succeeded`: run run_a01faf3f-4018-4d80-9e20-f8709de7913e succeeded
- pass `addition_50k:addition_drafted`: addition draft prop_4a108be4-2afa-412e-875b-dbecb0def7af
- pass `addition_50k:arithmetic_consistent`: before + deltas = after, and team totals equal the envelope
- pass `addition_50k:prioritizes_research`: research gets the largest increase (+50000.00; deltas {'engineering': '0.00', 'product': '0.00', 'research': '50000.00'})
- pass `addition_50k:flags_other_overruns`: names the other projected overrun(s): engineering +5000.00
- pass `addition_50k:reference_split (informational)`: differs from the reference split: after = {'research': '110000.00', 'product': '80000.00', 'engineering': '60000.00'} @ 250000.00; reference {'research': '95000.00', 'product': '80000.00', 'engineering': '75000.00'} @ 250000.00
