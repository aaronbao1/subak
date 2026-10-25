# Task 5 fix round 1 rereview

Verdict: **approved for the reviewed Task 5 scope**. All four findings from `task-5-review.md` are addressed. No additional actionable defect was found in the fix diff.

Reviewed `task-5-fix1.diff`, its reconstructed baseline provenance in `task-5-before-fix/RECONSTRUCTION.json`, the appended implementation report, and the current changed modules/tests. The reconstructed controls baseline matches the original review-diff blob identity `e434579`; its current diff agrees with the supplied fix scope. Review was limited to the previous findings and possible regressions introduced by their fixes. No product files, full suite or subagents were used.

## Finding disposition

1. **P1 premature liability release — fixed.** `controls.py:168` requires terminal execution end/cancellation acknowledgement before settlement. `:160` prohibits subsequent starts of terminal/settled attempts. Opening `Attempt` state rejects settled-but-nonterminal lifecycle flags at `:47`. Both pre-start and live execution settlement are rejected; pre-start cancellation plus settlement remains a valid terminal path.
2. **P1 reset-erased breach/assurance — fixed.** `ControlState` now derives and retains `peak_overshoot` and sticky `hard_assurance_lost` at `controls.py:71–73`. Every physical transition carries both into the next state at `:179`; budget transitions preserve them through `replace`. `ControlResult.overshoot` reports retained trajectory deficit while `final_deficit` separately reports the ending balance deficit. Reset, hard-mode reconfiguration, resumed empty chunks and adapter continuation cannot erase a prior breach or restore whole-trajectory hard assurance.
3. **P2 nonzero empty temporal components — fixed.** `commercial.py:178–181` rejects nonzero known/late prefix when `through == period_start` and nonzero future when `through == period_end`. The native bundle adapter reaches the same gates. Regression cases cover both prefix roles and the exact future-November scenario; explicit zero prefix still produces the correct 30-unit charge.
4. **P2 lost budget cursor/replay protection — fixed.** `controls.py:138` persists audit `event_ids/last_at` for budget events. Subsequent reducer calls and `ControlAdmission.apply` reject replay and time travel. Physical balances, policy and attempts remain invariant; the tests correctly distinguish physical invariance from audit-state identity.

## Independent verification

Executed:

```text
python3 -m pytest tests/test_controls.py tests/test_commercial.py -q -k 'settlement_cannot or opening_settled or prestart_cancel or reset_retains or chunked_adapter or budget_only_chunk or nonzero_prefix or nonzero_future or bundle_adapter_refuses or opening_deficit or chunked_budget'
15 passed, 20 deselected in 0.04s
```

These executed cases cover all four findings, parameterized pre-start/live settlement and known/late prefix variants, opening-state validity, adapter chunking, opening deficits, zero-prefix acceptance and chronological continuation. A narrow constructor/call-site search found no external `ControlResult(...)` constructor needing adjustment for the new required `final_deficit` field. The broader **52-pass** targeted result is implementer-reported evidence, not a suite rerun by this reviewer.

The original conditional-evidence, complete-pool, simulation-only and lack-of-empirical-calibration limitations remain. The fixes do not claim provider enforcement or verified billing accuracy. Root retains responsibility for integrated verification.
