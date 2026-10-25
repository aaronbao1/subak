# Final integrated architecture/code review

Reviewed `22b353eb378a9e6c89680989a26ba11c1dad3f61..53e06ce` on 2026-10-24. Product code and the index were not changed. **Verdict: changes requested before code readiness approval**, for the four concrete findings below. The architecture is coherent and does not need replacement or expansion into a general ledger or enforcement product.

The genuine pretrained benchmark is **separately incomplete**. Resolving these code findings would not complete that user requirement. The executed public-trace baseline/joint comparison and recorded Chronos dependency failure are useful evidence, but are not pretrained inference.

## Review coverage and evidence

- Read the full code-focused review diff in bounded portions, including every changed implementation, test and manifest; the three separately audited CSV bodies were omitted as declared. Read the implementation plan, README, scope/qualification document, verification JSON and benchmark report, with selected progress/review artifacts to distinguish already resolved issues.
- Root reports 501 passing tests, successful compileall/diff checks, two integrated synthetic demos, and the real public input-token benchmark. I inspected that evidence but did not rerun the full suite or independently execute the unavailable foundation model.
- Independently executed bounded probes of multi-axis serving, native and monetary risk under ambient Decimal precision, structural entity/resource bounds, and derived-overflow isolation. The reproducible script is [final-review-reproductions.py](final-review-reproductions.py); exact output is [final-review-reproductions.json](final-review-reproductions.json).
- Executed command: `PYTHONPATH=src:tests python3 .superpowers/sdd/2026-10-24-unified-robustness/final-review-reproductions.py > .superpowers/sdd/2026-10-24-unified-robustness/final-review-reproductions.json` (exit 0). This is a probe report reproducing defects, **not** a claim that desired-behavior regression tests passed. Its oversized workload probe stops at a mocked RNG constructor before allocating paths.

## Findings

### 1. P1 — Aggregate multi-axis actuals into the same entity identity as forecasts

**Location:** `src/forecasting/joint_service.py:294` and `:304`; the source-to-axis resolution is at `:255`.

The route explicitly accepts historical series keyed by `SeriesAxis.axis_id`, which is necessary when an entity has multiple meter/configuration axes. It maps those histories correctly into the fitted bundle, but leaves `recorded_by` and the initial `entities` mapping keyed by their raw axis hashes. Forecasts are then inserted under `axis.entity_id` with a recorded lookup that returns zero.

The independent full-period reproduction uses two axes for `team:a` (input and output), with 120 and 180 recorded tokens. The response publishes two hash-named entities with those actuals and no future, plus `team:a` with **recorded 0 / future 20**. Company mean 320 remains correct, hiding the broken team-level continuity. This is an ordinary supported multi-meter case, not an untrusted snapshot forgery.

**Required correction:** preserve the validated source-series-to-entity mapping and use it to aggregate actuals (including a delayed supplement) into the same entity IDs as future summaries. Do not lose or duplicate actuals when the forecast is unavailable. Verify a multi-meter full-period response has one team with recorded 300/future 20 and still conserves the company total.

### 2. P2 — Risk arithmetic depends on the caller's Decimal context

**Location:** `src/forecasting/joint_service.py:82` and `:38`.

Unary `-threshold` applies ambient Decimal precision before `exact_sum` sees the value. With the public serving fixture, usage mean 20 and threshold 19.99 have expected excess 0.01 under the default context but **0 under precision 3**, even while exceedance remains 1. The monetary view independently reproduces the same defect with mean 23 and threshold 22.99. These outputs are marked available. A direct 100.05/100.04 example returns 0.05 instead of 0.01 at precision 3.

The rational projection helper also sets only precision, inheriting rounding, exponent limits and traps. Identical two-thirds expectations therefore end in different last digits under `ROUND_DOWN` and `ROUND_UP`, despite the declared procedure being unchanged. Narrow inherited exponent limits or `Inexact` traps can additionally fail the projection.

**Required correction:** use context-free negation (`copy_negate`) and a fully specified local projection context/rounding policy. Preserve exact pricing totals; keep the declared 50-digit projection for nonterminating expectations. Verify end-to-end native/monetary excess and repeated summary output under changed ambient precision, rounding, exponent limits and traps.

### 3. P1 — Structural generation bypasses configured population and workload bounds

**Location:** `src/forecasting/state.py:374`, `:417`, `:439`; `src/forecasting/joint_service.py:194` and `:232`.

The aggregate generator bounds path count and path-axis-date cells. The structural generator accepts any positive integer path count, builds a people-by-all-mark-configurations axis cross-product, then retains every emitted root for every path/day/person. Positive count support up to 10,000 does not bound the combined work. Serving checks only the snapshot's entity count, not the supplied structural population.

An executed service probe with `max_entities=2` accepted three supplied people and returned all three forecasts. A safe sentinel probe reached RNG creation after all validation with one billion paths, three days and 10,000 roots per active day; it deliberately stopped before allocation. Resource exhaustion is inferred from the unbounded loops/storage, not claimed as an observed OOM. Even ordinary combinations of hundreds of paths, hundreds of employees and monthly horizons can retain millions of root records.

**Required correction:** check the effective structural population against the service bound and validate a declared resource budget before constructing cross-products, matrices or root records. Bound path count, axis/date cells and possible emitted/continuation root work; counting only cells misses the positive-count loop. Return a clear bounded-input error rather than truncate the law. Add small tests at/beyond limits, including a multi-configuration and large-count case that rejects before generation.

Practical compatibility expectation: retain the existing 1,000-path/two-person/three-day common-shock test (at most 18,000 emitted roots), both demos, and useful modest monthly scenarios. The aggregate route's 10,000-path and 2,000,000-cell caps are existing reference limits, but structural root records need a separate explicit budget. Compute that work from effective exposure days, count support and ongoing roots before simulation. A particular memory-safe record cap requires a bounded measurement; this review does not invent one from an unrun stress test.

### 4. P2 — A derived numerical failure aborts serving instead of preserving recorded actuals

**Location:** `src/forecasting/joint_service.py:273`; `src/forecasting/joint.py:65` and `:216`.

The route catches `ModelUnavailable` and `OverflowError`, but the joint contract translates nonfinite derived totals into `ContractError`. A snapshot with two individually finite constant `1e308` axes can fit a one-day last-observation law; their joint total overflows float. `run_joint` raises `ContractError('nonfinite derived total')` and returns no forecast response, even though its Decimal recorded actuals are valid and already available. This is an extreme arithmetic regression, not a claim about typical token volume.

The low-level bundle should reject a nonfinite law, as it currently does. The integration gap is loss of the independently valid actuals response when that typed numerical rejection crosses serving.

**Required correction:** distinguish derived numerical unavailability from malformed caller contracts and degrade only affected forecast/risk outputs at the serving boundary. Avoid broadly swallowing all contract errors. Verify finite-input overflow returns recorded actuals and a qualified unavailable forecast while genuinely invalid axes/state/configuration inputs still reject.

## Strengths and resolved boundaries

- One explicit path contract binds axes, exact dates, origin, procedure, scenario, provenance and assumptions. Same-path aggregation and normalized atom-aware quantiles avoid independent marginal joins. The fitted aggregate procedure actually forecasts historical prefixes and samples common held-out residual blocks.
- Acquisition-pending evidence stays separate from usable numerical values; moved-date revisions invalidate both affected dates, replacement generations do not revive old amounts, and allocation policy identity is separate from row revisions. Provenance is conservatively closed over receipt dependencies.
- Commercial valuation keeps native usage independent of tariff availability, requires explicit complete pool/period coverage, applies shared allowances once, preserves Decimal allocations, and separates requested remainder increments from complete-contract estimates. The prior mismatch/fixed-charge findings have concrete regressions.
- Execution replay distinguishes roots, attempts and physical meter leaves. Retries/fallbacks survive; wrappers reconcile without duplication. Explicit continuation, prior-use and access assumptions prevent quiet zero/capability invention. Control simulations retain unsettled liability and historical breach status across cancellation/reset/reconfiguration.
- Artifact dependencies inherit source unions and check transitive withdrawal, including intermediate structural/scenario parents. Probability views are withheld for sensitivity scenarios. The benchmark keeps failed foundation opportunities, frozen origins and actual adverse baseline/joint results visible.

## Behaviors not certified by this review

- **Foundation forecasting performance:** no weights/inference execution exists in the supplied evidence. Prepared adapter/config hashes do not establish runtime success; cloud approval remains pending. No empirical enterprise calibration or forecasting superiority is approved.
- **Raw-source acquisition and CSV reconstruction:** relied on the separately audited pinned canonical artifacts and acquisition records; did not reacquire the 50 MB raw trace or rerun its full transformation. Empty-bin completeness and historical online availability remain stated assumptions.
- **Host trust and caller hypotheses:** source acquisition classification, trusted snapshot construction, source permissions, supplied exposure/mark laws, admission callback identity, contract completeness and extra material dependencies are host-owned contracts. I did not treat a caller reconstructing a differently labeled object as a cryptographic identity/authentication breach. Production connectors/authentication and malicious-host resistance are not established here.
- **New financial/control products:** general-ledger posting, provider enforcement, verified live tariffs, donor-policy safety, fitted causal response and enterprise business outcomes remain outside the demonstrated implementation. Their absence is not a request to invent these products.
- **Runtime-scale performance:** no destructive stress test or memory benchmark was run. Finding 3 is backed by executed acceptance probes and concrete loop/storage structure; final limits should be validated with bounded fixtures.

The scope document still contains older statements that final integrated verification is pending, while `verification.json` records the root's completed checks. Refresh that prose in the final evidence pass, retaining the separate foundation-incomplete qualification.

After the four corrections, rerun their focused regressions and the integration owner's proportionate combined checks. Code approval can then be assessed independently of the remaining real pretrained benchmark requirement.
