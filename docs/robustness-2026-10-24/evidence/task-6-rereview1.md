# Task 6 scoped round 1 rereview

Scope: appended round-1 report and `task-6-fix1.diff`; the previous P2 and the new shared weighted-quantile change only. Inspected the actual helper and its `ScenarioBundle.quantile` call site. No product/index edits, subagents, or full-suite runs.

## Previous finding

**Addressed.** `src/forecasting/evaluation.py:521` now validates a temporary `target_prediction` before assigning the Opportunity prediction. The selected-target overflow therefore leaves `prediction=None`; the handler records an unavailable outcome. The added real seasonal-naive regression retains the scheduled/unissued denominator and verifies another candidate still succeeds. This directly covers the reproduced failure condition from `task-6-review.md`.

## New shared quantile change

**No issue found in the scoped diff.** `src/forecasting/uncertainty.py:133` computes the left-inverse rank using exact `Fraction` arithmetic over decimal-rendered probability masses and the normalized total. It handles q=0/q=1 and zero weights without binary cumulative-prefix drift. The returned support object is unchanged, preserving exact Decimal values above float range.

The documented division of validation is satisfied by the concrete callers: legacy `empirical_quantile` still validates finite float support and normalized weights, while `ScenarioBundle` validates finite Decimal/numeric support and finite normalized probability weights before `quantile` delegates to the helper. The joint caller continues validating q. The helper does not introduce float narrowing of values or context-dependent Decimal arithmetic.

## Verification and verdict

Independently executed the four changed focused regressions:

`PYTHONPATH=src python3 -m pytest -q tests/test_robustness_risk_evaluation.py -k 'target_only or legacy_equal or weighted_quantile_normalizes'`

Result: **4 passed, 27 deselected in 0.02s**. The reported 77-test broader targeted result was read but not rerun. Root retains whole-branch verification ownership.

**Spec verdict for this fix round: pass. Quality verdict: approved; previous P2 resolved and no new blocking finding in the scoped fix diff.** This does not expand the earlier review into an enterprise calibration or performance claim.
