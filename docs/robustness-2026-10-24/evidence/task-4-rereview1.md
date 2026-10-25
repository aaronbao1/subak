# Task 4 fixround1 independent rereview

Spec verdict: approved for the scoped fixes. Quality verdict: approved. No new actionable issues found in `task-4-fix1.diff`; all three prior findings are resolved.

Reviewed production blob `74e7ed0bcd16af8e11b9923e150a288910546344` and test blob `487800aae1a77602aaaaf0026d2cada96f2858fd`, matching the fix diff. Read the fixround1 report and inspected the actual changed lines. No product edits, full-suite run, or delegation.

## Finding closure

- **Original P1, fitted-origin integrity — resolved.** `src/forecasting/state.py:204–220` adds explicit fitted/supplied source, aware fitting cutoff, evidence identity, and a reserved fitted-ID namespace. Actual fitting populates those fields; generation at `:387` rejects a later fitted cutoff. Constructor checks reject removing the cutoff, source-only relabeling, and stripping source/cutoff/evidence while retaining the actual fit identity. The full parameter record remains in procedure configuration (`:432`) and therefore its immutable identity. This preserves explicit supplied hypotheses without accidentally treating retained actual-fit artifacts as supplied laws. The contract remains a trusted caller's provenance contract, not authentication against deliberately reconstructing every field as a different artifact.
- **Original P2, future-spell prior-use — resolved.** `src/forecasting/state.py:453–454` applies known prior-use at effective entry before access/occurrence decisions, while preserving True state already established by historical or emitted roots. Both known-never entrants and known-ever returning entrants now follow the correct branches; the later-spell regression prevents a second first trial.
- **Original P2, UTC recency — resolved.** `src/forecasting/state.py:427` converts historical timestamps to UTC before extracting their dates, matching the declared target and fitter day semantics.

## Executed verification

`python3 -m pytest -q tests/test_state.py tests/test_joint_service.py`: **45 passed in 0.59s** (30 state cases, 15 direct service integration cases).

Additional independent read-only Python probes reproduced the original future-fit fixture and verified rejection at the earlier origin; verified all three metadata-stripping variants above reject; and verified an origin-valid fitted artifact runs and retains its source, cutoff and evidence ID in serialized procedure configuration. The future-entry and UTC regressions were executed in the targeted test run and checked against the actual implementation.

Summary: the reviewed regressions are fixed with narrow changes and meaningful coverage. Existing documented conditional modeling scope remains unchanged.
