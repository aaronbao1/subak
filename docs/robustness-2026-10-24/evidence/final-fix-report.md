# Consolidated final fix wave

Base: `53e06ce`. Four final-review findings addressed in one focused wave; no commits, dependency acquisition, pretrained execution, or financial/control feature work. Product changes are frozen for root integration and one scoped independent rereview.

## Changed files

- `src/forecasting/joint_service.py`: resolve validated source-axis identities before availability gates and group actuals into forecast entity identities; fixed Decimal risk projection and excess; structural population limit forwarding; typed numerical unavailability isolation.
- `src/forecasting/joint.py`: `DerivedNumericalUnavailable(ContractError)` distinguishes arithmetic failure of derived totals from invalid input contracts. Invalid probability weights above one reject as contract errors before summation.
- `src/forecasting/state.py`: preallocation path, horizon, cell, population, and emitted/continuation root-work budgets; explicitly typed derived mark/path overflow; indexed ongoing-root lookup avoids repeatedly scanning starts.
- `src/forecasting/contracts.py` (root-authorized supporting change): exact sum/product use fully specified contexts, with exactness still enforced by `Inexact` traps. No price rounding introduced.
- `tests/test_final_review_regressions.py`: 18 final-review regressions and boundary/contract checks.

Before versions are in [final-fix-before](final-fix-before/). Current product/test SHA-256 values and Python version are in [final-fix-files.json](final-fix-files.json). Original reviewer probes and their defect output were preserved unchanged.

## Findings and final behavior

### 1. Multi-axis actuals

The native aggregate route validates typed unique compatible axes, resolves raw axis IDs and unambiguous single-axis entity IDs, and maps recorded totals before any model/coverage gate. Initial entity rows use those same entity identities. Both mature actuals and a same-source delayed supplement are aggregated exactly once. The full-period two-meter fixture now has only `team:a`, recorded 300, future 20, company mean 320. With a two-day supplement, recorded is 310 and company mean 330. Unavailable coverage preserves the same single team and exact recorded totals with unavailable future. Malformed or ambiguous axes still reject.

The original source-series identity remains the history identity passed to `fit_joint_blocks`; no uncoupled path join or change to fitted-law behavior was introduced.

### 2. Decimal context independence

Threshold subtraction uses `copy_negate()`. Rational expectations use an explicit local `Context`: precision 50, `ROUND_HALF_EVEN`, `MIN_EMIN`/`MAX_EMAX`, capitals 1, clamp 0, empty flags and disabled inherited traps. The manifest names the rounding policy. Pricing totals remain exact Decimal; only statistical expectation projections use the declared 50 significant digits.

Native mean 20 / threshold 19.99 and monetary mean 23 / threshold 22.99 both retain expected excess 0.01 and the same artifact ID under precision 3, `ROUND_UP`, narrow exponent limits, clamp, and all ambient traps enabled. The two-thirds summary deterministically ends in 7 under both `ROUND_DOWN` and `ROUND_UP` caller contexts.

An integration regression also exposed `exact_sum((1e100, -1e100))` inheriting the caller's `Rounded` trap even though its numerical result is exact. The first fix pass had 13 passing / 1 failing test for this reason, recorded in [final-fix-first-green.txt](final-fix-first-green.txt). Root authorized the supporting contracts change. Exact sum/product now explicitly specify precision, rounding, exponent bounds, capitals, clamp, flags and traps (`Inexact`, `InvalidOperation`, `Overflow` enabled). A long-digit monetary multiplication retains every expected digit, and exact cancellation is independent of `ROUND_FLOOR` signed-zero behavior.

### 3. Structural bounds

Declared limits are 10,000 paths, 366 days, 2,000,000 path/axis/date cells, and 50,000 units of emitted/continuation root work. The effective generated population must respect `service.max_entities`; direct generator calls default to 1,000 people. `state_inputs` cannot override the serving population bound.

Before constructing the people/configuration cross-product, matrices, RNG or emitted roots, validation computes:

- cells = paths × population × distinct billed configurations × dates;
- possible new roots = the sum of maximum count support for every accessible effective exposure day whose occurrence can be positive (including returning-use branches and shocks);
- continuations = ongoing roots × forecast days, including roots for people whose access is now off;
- root work = paths × (possible new roots + continuations).

Proposal admission does not reduce the preflight bound: denied proposals also consume generation work. Laws above a limit reject with a clear bound/budget error; no support truncation or stochastic acceptance occurs. The estimate is conservative about returning-state reachability. An ongoing-root lookup dictionary ensures continuation work does not hide a root-by-root repeated scan of all starts.

Boundary regressions use tiny limits to prove acceptance at a limit and rejection above it, account for a one-day effective exposure plus three days of continuing work, cover multiple configurations, and establish that inaccessible high-count populations do not accrue impossible new-root work. Separate preallocation sentinels safely reject the review's billion-path request, large positive counts, excessive multi-configuration cells, and continuing-root workload before cross-product/RNG allocation.

The existing 1,000-path/two-person/three-day common-shock test still passes (18,000 possible roots). A 100-path/10-person/30-day/count-1 monthly law requires 30,000 root units and fits these budgets. The actual cap measurement used 100 paths × 10 people × 25 days × 2 roots, exactly 50,000 roots and 25,000 cells:

- elapsed with tracemalloc: 2.8264 seconds;
- retained traced allocation: 27,601,250 bytes;
- peak traced allocation: 88,385,239 bytes;
- process peak RSS on this macOS host: 178,929,664 bytes.

Runnable measurement: [final-fix-resource-measurement.py](final-fix-resource-measurement.py); result: [final-fix-resource-measurement.json](final-fix-resource-measurement.json). This is a bounded finite fixture at the chosen cap, not an OOM test or universal production memory certification. User-supplied evidence/support representation sizes and concurrent requests remain host concerns; full serving artifact serialization adds work beyond this generator measurement.

### 4. Derived numerical isolation

Finite history values whose joint total overflows produce typed `DerivedNumericalUnavailable`; serving preserves exact Decimal actuals and marks future/usage risk unavailable with an explicit derived-numerical reason. The reviewer fixture returns recorded `1.2e310` and unavailable future. Structural finite mark/path overflow follows the same boundary behavior. Malformed axes, cohort state, nonfinite supplied bundle values, and invalid probability weights still reject as caller contract errors. No blanket `ContractError` or `ValueError` catch was added; the serving catch of generic `OverflowError` was replaced with the specific numerical type.

## Executed validation

1. Initial requested regressions: `PYTHONPATH=src:tests python3 -m pytest -q tests/test_final_review_regressions.py` — **14 failures**, all four defects reproduced before product edits. [Red evidence](final-fix-red.txt). Initial attempt via `.venv/bin/python` could not run because that interpreter lacks pytest; system Python was used for all reported test results.
2. First implementation pass — **13 passed, 1 failed**, exposing the additional exact-sum `Rounded` integration issue above.
3. Final focused command: `PYTHONPATH=src:tests python3 -m pytest -q tests/test_final_review_regressions.py tests/test_joint_service.py tests/test_joint.py tests/test_state.py tests/test_contracts.py tests/test_pricing.py tests/test_commercial.py` — **144 passed in 0.88s**. [Focused output](final-fix-focused.txt).
4. One complete suite after all product/test changes: `PYTHONPATH=src:tests python3 -m pytest -q` — **519 passed in 8.88s**, no failures or skips reported. [Full output](final-fix-full-suite.txt). This includes scalar and joint APIs and the existing common-shock case.
5. Both integrated synthetic demos executed freshly through `run_joint_demo`: aggregate and state each returned usage mean 20, conditional contract mean 26, matching stored/retrieved artifact IDs, and `safe_transfer: false`. [Demo report](final-fix-demos.json); adjacent `final-fix-demo-aggregate/` and `final-fix-demo-state/` hold artifacts.
6. `PYTHONPATH=src python3 -m compileall -q src tests` and `git diff --check` — exit 0, no output.

## Self-review and limits

Reviewed the combined four-file diff and test assertions against all four findings. The actual/future identity mapping happens before unavailable branches; actuals conservation is checked for both normal and delayed evidence. Decimal exact arithmetic retains explicit exactness traps and the statistical rounding policy is manifest-visible. Structural bounds precede expensive cross-product allocation and cover count support and continuations as well as cells. Numerical exceptions remain distinguishable from malformed contracts; all preexisting and added tests pass.

No enterprise calibration or forecasting superiority claim is made. The genuine pretrained benchmark remains separately incomplete and blocked pending the user's cloud approval. This wave does not address that acquisition/runtime requirement, and does not alter the earlier public-trace evidence. No external messages, paid compute, deployment, push, merge, or commits were performed. Existing untracked documentation directories were left untouched. Root should refresh the previously stale verification prose and obtain the requested single scoped final rereview; this report is implementer evidence, not independent approval.
