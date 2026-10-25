# Task 4 fixround1 — three reviewed issues addressed

Reviewed full `task-4-review.md`. Before changes, copied exact production and test files to `task-4-before-fix/state.py` and `task-4-before-fix/test_state.py`. Only Task4 owned production/tests changed; no full-suite execution and no commits.

## P1 fitted parameters after forecast origin

Added immutable HurdleParameters provenance fields `parameter_source`, `fit_as_of`, and `fit_evidence_id`. Actual fitter populates source `fitted`, aware fitting cutoff and replay evidence digest; fit IDs use reserved `fitted:` namespace. Constructor rejects missing actual-fit cutoff/evidence and rejects supplied relabelling of retained actual-fit metadata/identity. Generator rejects actual fitted cutoff after generation as-of. All fields flow through existing primitive parameter serialization into bundle procedure identity. Explicit newly supplied hypotheses remain supported.

Regression `test_parameters_fitted_after_forecast_origin_cannot_leak_future_marks` reproduces reviewer fixture: Jan 5 root with 123456 tokens, fitted Jan 7, generation Jan 4. Before fix, expected rejection did not occur; after fix it rejects with fitted-after-origin error. `test_actual_fit_cutoff_cannot_be_removed_or_relabelled_as_supplied` covers missing cutoff, source-only relabel and simultaneous source/cutoff/evidence stripping while retaining actual-fit identity; genuine supplied hypothesis and origin-valid fit remain runnable. Initial targeted command: **2 failed / 24 deselected**. Stronger retained-identity stripping check separately reproduced **1 failed / 25 deselected** before fix. Final P1 targeted: **2 passed / 24 deselected**.

## P2 effective future-entry prior use

At each spell's effective entry, reconcile known prior-use evidence before that day's access/occurrence decision. True ever-used state from any previous evidence/emitted roots is preserved; future known-never initializes unknown to False and future known-ever activates returning-user branch. Evidence is still filtered by origin availability.

Parametrized `test_future_exposure_prior_use_applies_at_effective_entry` reproduces Jan 5 entrants at Jan 4 origin. Known-never p_any=1 produces 10 tokens and exactly Jan 5 first trial; known-ever p_any=0/p_returning=1 produces 10 tokens without first trial or first-observed adoption. `test_future_known_never_spell_does_not_reset_already_emitted_first_trial` preserves existing first trial across later spell entry. Initial targeted command: **2 failed /1 passed / 26 deselected**; after fix **3 passed / 26 deselected**.

## P2 UTC historical recency

Normalize historical qualifying-root timestamps with `astimezone(timezone.utc).date()` before initializing last_use. `test_historical_recency_uses_utc_service_date_for_offset_events` reproduces completed Jan 2 23:30 UTC−08 root and no new starts, expects Jan 3 UTC recency. Initial targeted command **1 failed / 29 deselected**; final combined run passes.

## Verification and frozen handoff

`python3 -m pytest -q tests/test_state.py tests/test_joint_service.py`: **45 passed in 0.60s**. Exact output in `task-4-fixround1-tests.txt`. This covers 30 state cases and 15 direct service integration cases. `python3 -m compileall -q src/forecasting/state.py` and `git diff --check` pass. No full suite ran as requested. Existing scope/limitations remain those of task-4-report.md; no new model mechanisms introduced. Implementation/tests are frozen for root/reviewer inspection after this report.
