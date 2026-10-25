# Task 6 report: finite risk and serving-equivalent replay

Implemented in `src/forecasting/uncertainty.py`, `src/forecasting/evaluation.py`, and `tests/test_robustness_risk_evaluation.py`. No commits; no other worker's implementation files edited.

## Root causes and resulting behavior

- Finite calibration inputs could overflow in `actual-prediction` or `point+q`, yielding an available interval with infinite bounds. `cumulative_interval` checks both stages and returns `status='numerical_failure'`, `lower=None`, `upper=None`, and empty capabilities. Existing insufficient-rank and mature/revision/overlap rules remain.
- Expected excess subtracted opposite-sign extremes without checking the result, and multiplied zero probability by infinity to produce NaN. `NumericalFailure(ValueError)` now identifies unsupported derived arithmetic; checked sums validate path totals and positive-weight risk terms. Nonexceeding paths are compared before subtraction, so an extreme refund below an extreme positive threshold correctly has zero excess. Invalid positive excess arithmetic is rejected, not saturated.
- `JointPaths.expected_shortfall(alpha, entities=None)` reports the average of the worst `1-alpha` probability mass for confidence alpha in `[0,1)`. It consumes only the required fraction of the threshold atom. This differs from expected overspend above a chosen budget. Negative target values remain signed; zero mass is ignored; normalization precedes multiplication to keep a constant `1e308` law finite even near alpha one. Risk is conditional on the supplied law and makes no empirical calibration claim.
- `LockedSelection.record` now accepts one preaggregated D loss for each registered candidate identity. Duplicate candidate records are rejected before mutation. Fold/seed aggregation belongs before recording; distinct configurations require separate registered names. Existing freeze/final temporal guards remain.
- `summarize_opportunities` preserves `point` as an explicitly documented alias of `all_issued_point`, adds `on_time_point`, and reports issued/unissued/on-time-issued/mature counts alongside the original full scheduled population. Cohort/company reports receive the same metrics and denominators. Late and stale predictions stay in all-issued conditional accuracy, while on-time accuracy excludes them.
- `evaluate_rolling` accepts `history_ends={origin: exclusive_mature_watermark}` and `max_history_lag_days=0`. The lag policy matches scalar serving's integer 0..30 range. Default watermark remains origin, so stale history cannot quietly qualify. Delayed inputs must reach the declared watermark with mature labels. Forecasts span watermark through target end; only target dates are scored. Direct cumulative output cannot slice a bridge and is unavailable. Input/model manifests record watermark, lag, target dates and bridge dates. Daily target reduction uses the same exact Decimal-rendering sum as scalar serving, then converts the scored scalar to float.

## Executed red/green evidence

1. Before implementation:
   `PYTHONPATH=src python3 -m pytest -q tests/test_robustness_risk_evaluation.py`
   -> **18 failed, 1 passed in 0.09s**.
   Failures: expected excess did not reject overflow; zero-weight extreme returned NaN; both conformal cases returned available infinite bounds; expected shortfall API absent (all alpha/atom/constant cases); duplicate selection accepted; explicit watermark API absent; named delivery metrics absent. The existing no-bridge stale-history check passed.
2. Initial implementation:
   `PYTHONPATH=src python3 -m pytest -q tests/test_robustness_risk_evaluation.py tests/test_uncertainty.py tests/test_evaluation.py`
   -> **65 passed in 4.99s**.
3. Additional finite negative-excess boundary and actual serving comparisons:
   new suite -> **1 failed, 23 passed in 1.22s**. Failure `test_expected_excess_below_threshold_does_not_subtract_opposite_extremes` identified unnecessary subtraction of a nonexceeding negative extreme. Compare-before-subtraction fixed it.
4. Serving parity expanded to fractional daily amounts:
   `PYTHONPATH=src python3 -m pytest -q tests/test_robustness_risk_evaluation.py -k 'matches_scalar'`
   -> **1 failed, 5 passed, 21 deselected in 0.09s**. `test_delayed_replay_matches_scalar_serving_exact_future_target[10-last_observation]` proved evaluation returned `0.8999999999999999` while serving returned `0.9`. Exact Decimal reduction fixed the discrepancy.
5. Final Task 6 targeted verification:
   `PYTHONPATH=src python3 -m pytest -q tests/test_robustness_risk_evaluation.py tests/test_uncertainty.py tests/test_evaluation.py`
   -> **73 passed in 4.29s**.
   New file contains 27 parametrized test cases, including actual `ForecastService.run` parity for last observation, trailing mean and seasonal naive; integer and fractional histories; a hand-calculated bridge target of 14; direct cumulative bridge exclusion; immature watermark exclusion; full cohort denominators; signed/fractional-atom shortfall and invalid alpha cases.
6. Full project command during concurrent workers' red/green cycles:
   `PYTHONPATH=src python3 -m pytest -q`
   -> **8 failed, 401 passed in 9.19s**.
   Exact failures outside Task 6 ownership:
   - `tests/test_joint.py::test_independently_generated_laws_do_not_reuse_global_path_ids`
   - `tests/test_joint_service.py::test_joint_public_service_exists`
   - `tests/test_joint_service.py::test_joint_shared_paths_conserve_and_replay_under_current_acl`
   - `tests/test_joint_service.py::test_joint_exact_future_support_and_lag_does_not_invent_gap_actuals`
   - `tests/test_joint_service.py::test_joint_unavailable_model_preserves_actual_usage`
   - `tests/test_joint_service.py::test_bound_provenance_cannot_be_upgraded_in_either_service`
   - `tests/test_joint_service.py::test_joint_wsgi_route_uses_trusted_options_and_retrieves_result`
   - `tests/test_robustness_evidence.py::test_unbound_redelivery_of_known_synthetic_bytes_cannot_change_namespace`
   Root notified; these were unfinished concurrent implementations, not suppressed. Joint owner subsequently reported the path-ID regression fixed and 25 joint tests green; Task 6 has not independently rerun that later joint change.

An intermediate broader targeted command included `tests/test_service_models.py` and produced **1 failed, 79 passed in 4.21s**, with `test_explicit_delayed_history_bridges_gap_without_inventing_incurred_or_future` failing snapshot digest construction during concurrent evidence-class edits. This failure was reported immediately and was absent in the later full-project run.

## Self-review and limits

- Tests derive atom results by hand: mass .9 at 0 and .1 at 100 gives ES(0)=10, ES(.8)=50, ES(.9)=100, ES(.95)=100, while excess over 50 is 5. They distinguish the functional from strict conditional tail averaging.
- Exact future-date parity is tested against real scalar serving, including its Decimal aggregation. The delayed seasonal target is independently asserted as 6+7+1=14, so agreement alone is not the oracle.
- Mature observation availability is queried at each forecast origin, independent of the later scoring vintage. No current series truth fills missing versioned labels. Default zero lag and D/C/F/final-lock tests continue to pass.
- Existing interval-to-event-probability prohibition remains; no probability is inferred from bounds.
- Finite numerical laws are not enterprise tail calibration. No donor-policy safety, empirical uncertainty qualification, unseen-company generalization, or future forecast accuracy is established here.
- Watermarks are explicit caller declarations, checked against available mature labels. This does not infer missing late charges, add new observation coverage, or implement fallback/whole-procedure benchmark promotion. Failed or pending outcomes remain visible in scheduled denominators.
- `NumericalFailure` rejects arithmetic outside finite float support rather than claiming a finite risk by saturation. Exact recorded financial Decimal amounts remain owned by their original data/service paths.

## Round 1 independent review fix

Read `task-6-review.md`; preserved all three owned files before fixes under `task-6-before-fix/src/forecasting/` and `task-6-before-fix/tests/`.

The review correctly identified that a selected target can overflow even if the bridge-inclusive prediction remains finite. The conversion result was assigned to `prediction` before checking finiteness, so the availability handler left infinity for the later `Opportunity` constructor. The implementation now converts into a temporary `target_prediction`, validates it, and assigns to `prediction` only after that succeeds. The regression uses the actual signed seasonal-naive bridge `(-1e308, 1e308, 1e308)`; its target-only sum overflows, but the row remains unavailable with `prediction=None`, scheduled=1, unissued=1, and no scored prediction. A second candidate remains available with prediction zero.

Root also relayed a joint-law review defect that existed in the legacy quantile: equal-weight binary prefix addition selected 9 instead of 8 for 10 values at q=.8, and 28 instead of 27 for 30 values at q=.9. After coordinating with the joint owner, `weighted_quantile(values, weights, q)` now provides a shared exact rank calculation using `Fraction(str(weight))`, `Fraction(str(q))`, and threshold `q*sum(masses)`. It accepts nonnegative positive-total masses, normalizes the rank by their exact total, ignores zero mass and returns the original comparable value without narrowing Decimal support to float. Callers validate finite value support; legacy `empirical_quantile` retains its existing validation and delegates to this helper. The joint owner imports the helper in its separately owned file.

Executed round-1 red evidence:

- `PYTHONPATH=src python3 -m pytest -q tests/test_robustness_risk_evaluation.py -k 'target_only or legacy_equal'` -> **3 failed, 27 deselected in 0.08s**. Exact output preserved in `task-6-round1-red.log`. Failures reproduced the replay abort and both quantile rank shifts.
- `PYTHONPATH=src python3 -m pytest -q tests/test_robustness_risk_evaluation.py -k 'weighted_quantile_normalizes'` -> **1 failed, 30 deselected in 0.05s**, missing shared API. Test independently checks normalized masses, preservation by identity of Decimal('1e400') and Decimal('2e400'), q=1 and zero-weight q=0 handling.

Round-1 green:

- `PYTHONPATH=src python3 -m pytest -q tests/test_robustness_risk_evaluation.py tests/test_uncertainty.py tests/test_evaluation.py` -> **77 passed in 4.15s**.
- Root owns integrated full-suite verification; no additional full-suite run was performed during concurrent edits.

Self-review: temporary validation ensures a known failure path does not leak a partial prediction. The regression asserts retained denominators, absent infinity, explicit failure reason and survival of an independent candidate. Exact rational rank comparisons avoid epsilon tolerances that would incorrectly merge genuinely distinct nearby quantile levels. The shared helper deliberately does not narrow validated Decimal support to float. Earlier empirical-calibration and donor-policy limitations remain unchanged.
