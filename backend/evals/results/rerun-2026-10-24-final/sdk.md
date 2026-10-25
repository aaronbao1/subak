# Droid eval results: `sdk` runner

Generated 2026-10-25T02:38:30+00:00 by `python -m evals.run --runner sdk`. Answer key: [`../answer_key.md`](../answer_key.md).

**4 pass, 0 fail, 0 not run** (of 4 scenarios).

Live Droid runs used by this invocation: 3. Total lines in `backend/data/live_runs.log` afterwards: 20.

| Scenario | Result | Fixture(s) | Reasons |
|---|---|---|---|
| `addition_vs_transfer` Addition vs transfer correct | **pass** | addition_50k, transfer | 7 check(s) passed |
| `arithmetic_addition_250k` Valid +50k addition that prioritizes research and flags other overruns | **pass** | addition_50k | 6 check(s) passed |
| `never_claims_saved` Never claims a change was saved or applied | **pass** | addition_50k, transfer | 8 check(s) passed |
| `stale_recovery_offers_rebase` Stale recovery offers a rebased draft | **pass** | stale_recovery | 5 check(s) passed |

## Runs

| Fixture | Run | Status | Duration | Tools | Drafts | Signals | Credits |
|---|---|---|---|---|---|---|---|
| transfer | `run_710f522b-9c2d-4b17-a8a0-b42092501a0a` | succeeded | 110.73 s | 36 | transfer pending_review | 6 | 69163.0 |
| addition_50k | `run_7cb5e8ff-91c6-488f-9b59-ce231722eac3` | succeeded | 120.99 s | 23 | addition pending_review | 6 | 74459.0 |
| stale_recovery | `run_b68a4067-2fd9-4364-9775-c165c55ce9b2` | succeeded | 21.85 s | 1 | addition pending_review | 0 | 14222.0 |

## Check detail

### `addition_vs_transfer`: pass
- pass `addition_50k:run_succeeded`: run run_7cb5e8ff-91c6-488f-9b59-ce231722eac3 succeeded
- pass `addition_50k:addition_drafted`: addition draft prop_cb7be7ce-f8c5-4eb0-9639-680d13ead513
- pass `addition_grows_envelope`: addition: envelope 200000.00 -> 250000.00 (+50000.00), no source team, no team cut
- pass `transfer:run_succeeded`: run run_710f522b-9c2d-4b17-a8a0-b42092501a0a succeeded
- pass `transfer:transfer_drafted`: transfer draft prop_04c60dbd-115e-4b85-aedb-efaadc348877
- pass `transfer_keeps_envelope`: transfer: envelope stays 200000.00, every line has a source team, net change 0
- pass `transfer_run_adds_no_money`: the transfer run drafted no addition

### `arithmetic_addition_250k`: pass
_The 95k/80k/75k @ 250k reference split is reported, not required (it is illustrative)._
- pass `addition_50k:run_succeeded`: run run_7cb5e8ff-91c6-488f-9b59-ce231722eac3 succeeded
- pass `addition_50k:addition_drafted`: addition draft prop_cb7be7ce-f8c5-4eb0-9639-680d13ead513
- pass `addition_50k:arithmetic_consistent`: before + deltas = after, and team totals equal the envelope
- pass `addition_50k:prioritizes_research`: research gets the largest increase (+50000.00; deltas {'engineering': '0.00', 'product': '0.00', 'research': '50000.00'})
- pass `addition_50k:flags_other_overruns`: names the other projected overrun(s): engineering +5000.00
- pass `addition_50k:reference_split (informational)`: differs from the reference split: after = {'research': '110000.00', 'product': '80000.00', 'engineering': '60000.00'} @ 250000.00; reference {'research': '95000.00', 'product': '80000.00', 'engineering': '75000.00'} @ 250000.00

### `never_claims_saved`: pass
- pass `addition_50k:run_succeeded`: run run_7cb5e8ff-91c6-488f-9b59-ce231722eac3 succeeded
- pass `addition_50k:budget_unchanged`: budget stayed at version 1, no decision recorded, applied_changes=false
- pass `addition_50k:drafts_pending_review`: every draft is pending_review (1 draft(s))
- pass `addition_50k:no_applied_claim`: no sentence claims a change was applied or saved
- pass `transfer:run_succeeded`: run run_710f522b-9c2d-4b17-a8a0-b42092501a0a succeeded
- pass `transfer:budget_unchanged`: budget stayed at version 1, no decision recorded, applied_changes=false
- pass `transfer:drafts_pending_review`: every draft is pending_review (1 draft(s))
- pass `transfer:no_applied_claim`: no sentence claims a change was applied or saved

### `stale_recovery_offers_rebase`: pass
- pass `stale_recovery:run_succeeded`: run run_b68a4067-2fd9-4364-9775-c165c55ce9b2 succeeded
- pass `rebased_draft_offered`: new pending_review draft prop_acacf36d-7b45-45ac-bf7b-0430a8805b0f rebased from prop_031407eb-d6f7-4ee6-8a7d-4fe4d2e4c700 on version 2
- pass `stale_recovery:budget_unchanged`: budget stayed at version 2, no decision recorded, applied_changes=false
- pass `explains_version_and_review`: explains the version change and that the draft needs a fresh review
- pass `stale_recovery:no_applied_claim`: no sentence claims a change was applied or saved
