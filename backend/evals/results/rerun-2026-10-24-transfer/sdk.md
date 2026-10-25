# Droid eval results: `sdk` runner

Generated 2026-10-25T01:33:11+00:00 by `python -m evals.run --runner sdk`. Answer key: [`../answer_key.md`](../answer_key.md).

**0 pass, 1 fail, 0 not run** (of 1 scenarios).

Live Droid runs used by this invocation: 1. Total lines in `backend/data/live_runs.log` afterwards: 16.

| Scenario | Result | Fixture(s) | Reasons |
|---|---|---|---|
| `arithmetic_transfer_200k` Transfer reproduces 85k/50k/65k @ 200k | **fail** | transfer | transfer:transfer_drafted: no transfer proposal drafted (drafts: none) |

## Runs

| Fixture | Run | Status | Duration | Tools | Drafts | Signals | Credits |
|---|---|---|---|---|---|---|---|
| transfer | `run_5beb39ef-05e7-4d42-8ec6-58c9a4285718` | succeeded | 146.86 s | 23 | none | 6 | 40625.0 |

## Check detail

### `arithmetic_transfer_200k`: fail
_Reference split from the answer key; a different valid split is a judgment divergence, scored as fail._
- pass `transfer:run_succeeded`: run run_5beb39ef-05e7-4d42-8ec6-58c9a4285718 succeeded
- FAIL `transfer:transfer_drafted`: no transfer proposal drafted (drafts: none)
