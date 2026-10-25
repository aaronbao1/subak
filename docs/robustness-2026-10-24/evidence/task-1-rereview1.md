# Task 1 scoped re-review — fix round 1

Decision: **Approved** for this task snapshot and fix round. No new important findings in the fix diff.

Scope: read the appended round-1 report and `task-1-fix1.diff`; checked only the changes addressing the prior P1/P2 and their focused regressions. No product edits, full-suite run, broad task re-review, or subagents.

## Prior findings

- **P1 nested supersession ACL leak — addressed.** `src/forecasting/context.py` now derives the currently visible eligible event IDs and projects every returned event with a filtered `supersedes` tuple. The full internal supersession graph is computed before projection, preserving retirement and no-resurrection behavior. The strengthened regression verifies that a visible cancellation exposes neither the inaccessible predecessor in top-level retired metadata nor in its nested event links, and that revoking the cancellation still does not resurrect the predecessor.
- **P2 ambient Decimal exponents alter values under a stable scenario ID — addressed.** Both shared exact helpers now set private exponent bounds to `MIN_EMIN`/`MAX_EMAX`, disable clamping, and enable the Inexact trap after choosing sufficient precision. The original `1e-20 × 1e-40` reproduction remains `1e-60` under a caller context with small exponent bounds. Scenario ID and values remain stable. The changes preserve the caller context and reject a nonzero product beyond the implementation's representable exponent range instead of silently accepting zero.

## Verification performed

Command:

```text
PYTHONPATH=src python3 -m pytest tests/test_robustness_contract_context.py -q -k 'revoked_superseded_metadata or exact_arithmetic_ignores_ambient_exponent_limits or exact_arithmetic_never_silently_underflows or bound_scenario_keeps_values_and_identity'
```

Result: **6 passed, 37 deselected**, exit 0.

An independent read-only Python probe additionally set ambient `prec=2`, `Emin=-20`, `Emax=20`, and `clamp=1`; verified exact product and sum outputs of `1e-60`; checked that all four caller settings remained unchanged; and verified `exact_product(Decimal('1e'+str(MIN_EMIN)), Decimal('1e'+str(MIN_EMIN)))` raises `Inexact` rather than accepting an underflowed zero. Probe exit 0.

The report's 88-test focused-suite result was read but not independently rerun; integrated/full-suite verification remains root-owned.
