# Unified token-spend forecasting robustness

The implementation now has one evidence-bound pipeline with two alternative generators. Aggregate-only inputs use a fitted common-block forecast; qualified person/execution inputs use a finite recurrent hurdle state model. Both produce the same joint path contract, which supports exact shared-pool pricing and coherent summaries. The original scalar API remains available.

This work reread both complete original transcripts and the master plan. Twenty research contributors produced **243 edge cases**, consolidated into eight common mechanisms rather than separate features for each scenario. [The registry](edge-cases.md) preserves source references, conditional assumptions, exclusions and narrowly scoped implementation evidence. The [research notes](research/) contain the detailed investigations.

```mermaid
flowchart LR
  E[As-of evidence and coverage] --> S[Typed snapshot and provenance]
  S --> A[Common historical block generator]
  S --> R[Exposure and execution state kernel]
  A --> J[Aligned joint path bundle]
  R --> J
  J --> U[Native usage views]
  J --> P[Complete billing pools and exact pricing]
  P --> C[Allocated monetary paths]
  U --> Q[Independently qualified summaries]
  C --> Q
  Q --> X[Immutable artifacts with dependency withdrawal]
```

## Common defenses

| Boundary | Implemented defense | Examples it addresses |
|---|---|---|
| Evidence to history | Known-but-unprocessed evidence gates readiness independently of selected amounts; coverage, acquisition provenance and global attribution policy bind snapshot identity | False zeroes, late revisions, moved service dates, synthetic relabeling, changed team allocations |
| History to behavior | Exposure spells and qualified execution leaves distinguish missingness, new roots, ongoing roots, first trial and recurrent use | Access loss with work still running, rehire, future entrants, retries and fallback losers, wrapper double counting |
| Behavior to paths | Bounded occurrence/count/mark laws or honest rolling residual blocks preserve common draw identity and temporal dependence | Shared project bursts, dependence between people, impossible cross-model path joins, future-fit leakage, unknown capability |
| Proposals to delivered work | A chronological conditional reducer retains reservations, execution state, settlement, audit cursor and breach history | Concurrent quota races, early cancellation, late billing, reset-erased overshoot, repeated admission |
| Usage to money | Versioned dimensioned tariffs price complete shared pools per path before allocation, with exact Decimal conservation | Allowances, tiers, resets, mismatched units, empty temporal components, prefix charges mistaken for remainder spending |
| Paths to decisions | Target-specific means, quantiles, exceedance and atom-safe tail means remain assumption-conditional; missing views degrade independently | Infinite derived risk, sum-of-quantile errors, sensitivity grids presented as probabilities, unsupported all-in headroom |
| Context to scenarios | Typed baseline/adjustment identity prevents repeated application; cancellation and supersession obey current access | Double workload uplift, contradictory cancellations, revoked predecessor IDs |
| Artifacts to consumers | Derived artifacts inherit material dependencies and source permissions; withdrawal is checked transitively | Revoked snapshots or parent bundles remaining readable through derived outputs |

These are implemented mechanisms and tests, not claims that every compound case is empirically solved. The [scope and qualification document](scope-and-qualification.md) distinguishes supported calculations, conditional inputs and unimplemented extensions. Provider enforcement, learned causal price/adoption response, verified live contract adapters, and certified budget transfers are outside the demonstrated result.

The structural generator checks population, path, cell and root-work budgets before allocation. Its local limits are 10,000 paths, 366 days, 2,000,000 cells and 50,000 possible emitted/continuation root records. An executed fixture at the root cap used about 88 MB of peak traced allocations; this does not certify total server memory under concurrency. Larger scenarios must reduce their sampling/population workload or use an appropriately qualified aggregate forecast. The law is never silently truncated to fit the budget.

## Run the integrated examples

From this worktree, with the project's Python test dependencies:

```sh
python3 -m pytest -q -p no:cacheprovider
PYTHONPATH=src python3 -m forecasting joint-demo --output-dir artifacts/example-state --process state
PYTHONPATH=src python3 -m forecasting joint-demo --output-dir artifacts/example-aggregate --process aggregate
```

Use a fresh output directory for each demo. Each example traverses acquisition, a coverage-qualified snapshot, one generator, two shared billing-period resets, exact allocation, risk summaries, storage and authorized retrieval. The hand-computed fixture is 20 future tokens and 26 USD under explicitly synthetic tariffs; it demonstrates mechanics only.

## Real benchmark and current limit

The [benchmark report](benchmark.md) and [per-origin results](results.json) use genuine public BurstGPT request input tokens: 1,462 complete hourly bins from a release containing 1,429,737 requests. Input tokens are the primary target because eventual response lengths lack completion/availability timestamps. Empty released bins have an explicit idealized coverage assumption. There are no inferred employees, teams, invoices or enterprise calendar claims.

The initial run used 20 frozen held-out origins for each of the one-hour and four-hour targets. The joint procedure slightly improved on last observation at one hour and performed worse at four hours. Trailing mean won at one hour; last observation won at four hours. These results support neither universal improvement nor enterprise calibration.

**The genuine pretrained comparison is still pending.** A pinned Chronos-Bolt Tiny adapter, exact weight hash/configuration checks and installation manifest are prepared, but no pretrained weights have been loaded or inference executed in the current environment. Local networking and browser failures are recorded. A bounded temporary cloud run requires the pending user approval. The existing results retain foundation unavailability explicitly rather than substitute a model.

Reproduce the local baseline/joint run:

```sh
PYTHONPATH=src python3 benchmarks/robustness/run.py \
  --series benchmarks/robustness/data/burstgpt_hourly_input_tokens.csv \
  --provenance benchmarks/robustness/data/burstgpt_input_provenance.json \
  --bin-seconds 3600 --target-meter input_tokens --context 64 \
  --max-origins 20 --seasonal-period 24 \
  --output artifacts/benchmark-input.json
```

The optional pretrained run adds `--foundation-adapter benchmarks/robustness/chronos_bolt_adapter.py` in an environment with the pinned optional dependencies and access to the verified weights. The adapter reports sums of marginal median forecasts as point aggregates, not cumulative medians or means. No benchmark interval or probability calibration is inferred from those outputs.
