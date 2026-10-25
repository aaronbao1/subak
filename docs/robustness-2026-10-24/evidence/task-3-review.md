# Task 3 independent review

## Spec verdict

**Changes required.** The owned snapshot substantially implements the requested common joint law and a real fitted historical generator. Two reproducible correctness gaps remain: empirical quantile boundaries and type-preserving configuration identity.

Reviewed the exact `task-3-review.diff`, brief, constraints, report, and published interface. Dependency inspection was limited to `contracts.py` serialization/exact summation/Target and `models.py` Series, eligibility, registry/defaults, and forecast behavior needed to verify the changed code. No full suite, product edits, or delegated review.

## Strengths

- Rolling historical forecasts use prefixes ending before held-out blocks and the same configured baseline used at the forecast origin. Common block sampling preserves entity and temporal dependence; fallback is explicitly identified as `joint_direct_blocks`.
- Missing/misaligned histories and future observations are rejected. Delayed history keeps the actual as-of, models the complete bridge horizon, and slices output only after the joint draw.
- Rectangular shape, compatible native units, finite cells and cumulative totals, nonnegative usage support, exact Decimal money aggregation, and sensitivity-versus-probability distinctions are enforced.
- Derived entity/company laws retain common path IDs and parent linkage. Generator path IDs include a law namespace, avoiding accidental coupling of independently configured laws.
- Public-trace evidence cannot be declared enterprise-qualified. Empirical qualification requires declared scope and evidence references; generator output remains explicitly assumption-conditional.

## Findings

### P2 — Floating cumulative weights select the wrong empirical quantile

**Location:** `src/forecasting/joint.py:219`–`223` (`quantile`).

Repeated `cumulative += weight` drifts below an exact CDF boundary. A valid bundle with totals 1 through 10 and ten weights of 0.1 returns **9** for `quantile(.8)` and **10** for `quantile(.9)`, rather than 8 and 9 under the implemented inverse-CDF convention. With 30 equal-weight paths, `quantile(.9)` returns **28** rather than 27. These are ordinary generated-law path counts and percentile requests, so tail reporting can jump an entire support point despite valid normalized inputs.

Focused executed reproduction constructed one-axis, one-date ScenarioBundles for `(n, q) = (10, .8), (10, .9), (30, .9)` and printed respectively `9.0`, `10.0`, `28.0`. Expected support points are `8.0`, `9.0`, `27.0`.

Use stable cumulative mass calculation and a documented treatment of floating-point CDF boundaries; add regressions at exact empirical mass boundaries, including unequal weights.

### P2 — Distinct typed procedure inputs share the same identity

**Location:** `src/forecasting/joint.py:23`–`37` (`_freeze`) and `src/forecasting/joint.py:75`–`77` (`ProcedureSpec.identity`). Specific dependency: `src/forecasting/contracts.py:81`–`97`.

ProcedureSpec explicitly accepts Decimal, date/datetime, and string configuration values, but `digest` serializes Decimal and date/datetime as untagged strings. Consequently `ProcedureSpec('typed_config', config={'threshold': Decimal('1.5')})` and the same procedure with `{'threshold': '1.5'}` have identical identities despite retaining different input types. Dates versus matching ISO strings have the same issue. Generic procedure inputs can interpret these types differently; the common identity contract therefore does not bind every material accepted input. Bundle IDs inherit the collision when other fields match.

Focused executed reproduction printed distinct retained types `Decimal str` and `same identity: True`.

Make identity encoding type-preserving for accepted configuration values, or restrict/canonicalize accepted inputs under an explicit schema so these values cannot denote different behaviors. Keep external financial serialization exact; this need not require changing its wire format.

## Qualification boundary and remaining limits

Evaluation references are declared metadata, not authenticated evaluations. The interface and report disclose that a promotion boundary must resolve them; no unsupported assertion was made that this module performs empirical evaluation. Aggregation currently preserves qualification metadata verbatim, so consumers must continue to interpret its output identifiers and evaluation scope rather than infer newly validated aggregate-tail calibration. No unproven qualification defect is counted above.

## Quality verdict

**Request changes for the two P2 findings.** The implementation is compact, generally readable, and has useful explicit support/provenance boundaries. Existing snapshot tests cover important behavior, but neither identified boundary case is covered. Verification for this review consists of source inspection and the named focused Python reproductions; the author's reported test runs were read, not independently rerun. Root owns integrated suite verification.
