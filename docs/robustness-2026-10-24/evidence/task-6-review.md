# Task 6 independent spec and quality review

Reviewed the exact owned working-tree snapshot packaged in `task-6-review.diff` versus `22b353e`, its brief, shared constraints, implementation report, risk/validation findings, and relevant model/serving call sites. Product files and index were not changed. No subagents or full-suite reruns were used.

## Spec verdict

**Changes requested: one reproducible numerical-failure gap remains.** The requested finite risk rejection, atom-safe weighted expected shortfall, explicit mature-watermark bridge, exact target slicing, duplicate candidate rejection, and named delivery accuracy populations are otherwise implemented coherently. Temporal D/C/F and final-lock code is preserved.

## Strengths

- `uncertainty.py` checks residuals, interval endpoints, path reductions and weighted excess arithmetic. Nonexceeding and zero-weight paths avoid unnecessary overflowing subtraction. Explicit numerical failures do not advertise available intervals or infer event probability.
- Expected shortfall consumes exactly the required upper-tail probability mass, including a fractional threshold atom; its confidence convention and signed-value semantics are explicit. Normalizing mass before multiplying avoids the constant-large-law overflow defect.
- Evaluation reconstructs mature as-of history through an explicit bounded watermark, predicts the bridge, and scores exact future dates. Direct cumulative output cannot silently include bridge costs. Target reduction matches serving's decimal-rendering arithmetic.
- Named all-issued/on-time metrics retain full scheduled, issued, maturity, cohort and company counts. Duplicate unresolved candidate records are rejected before mutation. The new tests include independent hand calculations and actual scalar-service comparisons, rather than only agreement between two new helpers.

## Findings

### P2 — Overflowing selected target aborts replay instead of recording an unavailable opportunity

**Location:** `src/forecasting/evaluation.py:521` (assignment/check), `:531` (failure handler), `:537` (Opportunity construction).

`prediction=float(exact_sum(...))` can assign infinity when the selected future target exceeds float support, even though the bridge-plus-target model output is finite and valid. The subsequent `ModelUnavailable` handler changes the output status but leaves `prediction=inf`. `Opportunity` is constructed outside the handler and rejects it with `ValueError: finite metric values required`, aborting the complete replay and losing scheduled unavailable outcomes.

Focused reproducer executed with the real `seasonal_naive` model:

```python
from datetime import date, datetime, timedelta, timezone
from forecasting.evaluation import evaluate_rolling
from forecasting.models import Series
start = date(2025, 1, 1)
s = Series('t', tuple(start + timedelta(days=i) for i in range(7)),
           (-1e308, 1e308, 1e308, 0., 0., 0., 0.))
origin = start + timedelta(days=8)
evaluate_rolling((s,), (origin,), 2, ('seasonal_naive',),
                 datetime(2025, 2, 1, tzinfo=timezone.utc), labels=(),
                 history_ends={origin: start + timedelta(days=7)},
                 max_history_lag_days=1)
```

Observed result: **`ValueError: finite metric values required`**. The full predicted path is `(-1e308, 1e308, 1e308)` with finite cumulative value `1e308`; the exact selected target is `2e308`. This is a supported signed history and a valid explicit one-day bridge. The expected evaluator outcome is an unavailable/failed row with `prediction=None`, a numerical reason, and the opportunity retained in the scheduled denominator. Validate a temporary local before assigning `prediction`, or clear it in failure handlers, and add this target-only-overflow regression. The same regression should include another scheduled origin/candidate to verify that other opportunities remain reportable.

## Verification and quality verdict

**Quality verdict: changes requested for the P2 above; no other blocking finding in the owned snapshot.** The report's 73-test result was inspected as reported evidence, not independently rerun. Independent execution was limited to the named overflow doubt above, which reproduced the defect. Root owns whole-branch validation after the fix. No enterprise accuracy, calibration, or foundation-model performance conclusion is implied by this code review.
