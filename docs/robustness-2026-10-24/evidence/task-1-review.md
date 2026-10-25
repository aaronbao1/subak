# Task 1 independent review

Decision: **Needs fixes**.

Reviewed the exact owned snapshot in `task-1-review.diff` against `task-1-brief.md`, `constraints.md`, and the implementation report. Read the owned production modules and the three named research findings. Inspected only focused arithmetic/service/scenario call sites. No product, test, index, or branch edits; no broad repository crawl or full-suite rerun.

## Spec compliance and strengths

The implementation substantially satisfies the typed financial boundary work: direct construction and deserialization validate Boolean/string/collection types, usage is nonnegative incurred physical flow, physical results reject fixed monetary components, and supported monetary measures remain available. The optional scenario API preserves the low-level helper, records material assumption IDs, keeps immutable baseline and adjustment tuples, rejects duplicate adjustment/assumption IDs, and recomputes from the baseline. State-aware conflicts distinguish cancellation from compatible approved/observed assertions and preserve effective overlap. Retirement remains internal before access filtering, avoiding obsolete-claim resurrection.

The new regressions cover the central reported defects and explicit zero-versus-unknown fixed obligations. The implementation report gives separate red/green evidence and correctly does not claim an integrated full-suite pass. This review did not independently rerun those suite claims; it used focused executable probes for the doubts below.

## Findings

### P1 — Revoked superseded identities still leak through returned active events

**Location:** `src/forecasting/context.py:224` and `src/forecasting/context.py:237` (return at line 239).

The new filter removes inaccessible IDs from `ContextResolution.superseded`, but `events` still contains the original `ContextEvent` with its unfiltered `supersedes` tuple. A visible cancellation that supersedes a now-inaccessible event therefore exposes that event's identity, even though the top-level tuple is empty. This violates the explicit requirement to filter unauthorized superseded metadata; IDs can encode private project names.

Independent execution created an approved event `private-project`, a visible cancellation `public-cancellation` with `supersedes=('private-project',)`, then revoked finance access to the first source. Observed:

```text
filtered retired IDs: ()
returned active supersession IDs: ('private-project',)
```

Keep the complete retirement graph internally, but sanitize every externally returned supersession reference using the referenced event's current source permissions. Add a regression that checks `result.events[0].supersedes`, including the visible-cancellation/private-predecessor case, while retaining no-resurrection behavior.

### P2 — Silent Decimal underflow breaks exact scenario replay and identity stability

**Location:** `src/forecasting/context.py:362`, using `src/forecasting/contracts.py:45`–48 (the sum helper at line 39 has the same issue).

The shared helpers inherit the caller's exponent limits and only increase precision. `decimal(...)` rejects Infinity but accepts finite rounded or underflowed zero. `BoundWorkloadScenario.values` is recomputed on every access, while `scenario_id` hashes the immutable inputs rather than that arithmetic environment. Consequently, the same already-constructed scenario and content ID can yield a different quantity after an unrelated caller changes Decimal `Emin`.

Independent execution used a valid baseline quantity `Decimal('1e-20')` and assumption multiplier `Decimal('1e-40')`:

```text
default:    scenario_id=286e0bc18ebc7c6509d338cd37086b23cb7c52de16d010e7e67272e37a3210c3, value=1E-60
Emin=-20:  scenario_id=286e0bc18ebc7c6509d338cd37086b23cb7c52de16d010e7e67272e37a3210c3, value=0E-47
```

`exact_sum((Decimal('1e-60'),))` similarly returned `0E-47` under `Emin=-20`. These calls use Python's default disabled Underflow/Inexact traps; no deliberate suppression is required. Select exponent bounds sufficient for the operation or reject inexact/underflowed results, so immutable scenario lineage cannot silently identify differing numerical outputs. Add focused product/sum and bound-scenario regressions under a small exponent range. Exact subnormal results should remain supported if they are representable.

## Verification actually performed

Two read-only `PYTHONPATH=src python3` reproduction scripts completed with exit 0. They built genuine `ContextLedger`, `Target`, `WorkloadBaseline`, `WorkloadAdjustment`, and `BoundWorkloadScenario` instances and printed the unauthorized metadata and arithmetic discrepancy above. The first arithmetic probe (`1e-20 * 1e-20`) remained exactly representable at `Emin=-20`; the second used `1e-20 * 1e-40` to exercise actual underflow. No full-suite outcome is asserted here.
