# Scope and output qualification

This implementation supports enterprise finance planning of company and team AI spending. The governing workflow combines spending evidence, numerical forecasts, cited company context, a concrete internal allocation proposal, finance review and a saved backend receipt. The latest request also requires a real foundation forecasting benchmark. The [master plan](../ai-spend-master-plan.md) supplies the product boundary; the [eight-task implementation plan](../superpowers/plans/2026-10-24-unified-robustness.md) supplies the current work. This document distinguishes the intended contract from verified execution; it does not declare those eight tasks complete.

## Useful outputs with different evidence needs

| Output | What it means | Required evidence or assumptions | Qualification |
|---|---|---|---|
| Recorded usage or charges | What a covered source reports for a declared target and period | As-of receipts, correct counter/revision semantics, explicit units, maturity and source coverage | Measured usage is not a verified monetary bill. Unknown or pending records are not zero. |
| Aggregate forecast | Future covered usage or charges under a named procedure | Complete aligned eligible history; exact future dates, reporting basis and history watermark | A forecast may remain useful when roster, capability or monetary evidence is absent. |
| Fitted joint paths | One coherent finite law across declared series and dates | Shared historical sampling or fitted residual procedure, seed, support and all material transformations | Historical continuation is an assumption; mathematical availability does not establish empirical calibration. |
| Structural scenario paths | Outcomes conditional on supplied exposure, execution, capability and policy inputs | Origin-known state or explicit finite parameter tables; delivered/proposal process mode; immutable scenario identity | Supplied assumptions are a valid scenario mechanism. They are not learned causal effects or representative enterprise behavior. |
| Contract-priced estimate | Exact commercial transformation of covered usage paths | Matching tariff/meter/configuration units; complete contract-period pool and prefix; effective known-at schedule; allocation rule | A calculated estimate is not a provider-reported charge or cash payment. Missing pricing need not disable native usage. |
| Quantiles, exceedance and tail summaries | Arithmetic under the declared joint law for the exact target | Compatible paths and normalized weights; finite arithmetic; stated thresholds and alpha convention | Sensitivity branches without probabilities do not become a probability law. Held-out calibration is a separate empirical claim. |
| Budget comparison | Internal allocation minus compatible projected full-period spending | Same tenant, entity population, coverage, unit, target period, financial basis and provenance | A point gap is not safely removable funds. Unknown obligations remain unknown. |
| Internal allocation decision | Finance's recorded before/after budget choice | Concrete proposal, exact conservation, explicit additions versus transfers, current authority and material evidence, backend-confirmed receipt | Forecast support does not authorize application. Forecast abstention does not prevent a manual reviewed decision. |

Unavailable outputs degrade independently. A missing tariff can make cost unavailable while usage remains available; missing all-in obligations can prevent a safe-headroom claim while preserving a variable forecast; missing roster data can disable structural fitting while preserving an aggregate forecast. Existing measured actuals remain readable. Values and limitations must stay bound to the result artifact rather than be supplied later through an untracked label.

## Decisions and effects

Changing an internal allocation does not change external demand, purchase vendor credits, raise a provider cap or terminate an agent. An explicit conditional workload-policy scenario can change modeled demand; it is a different object from the budget transaction. Human-initiated coding-agent usage remains part of team spending even though managing autonomous swarms is parked.

Northstar's redistribution and funding-addition examples are independent alternatives from the original state, not an optimal allocation policy. Finance may choose another distribution. Protected reserves are explicit policy inputs. No universal prohibition on reducing a budget below recorded expense is inferred: a manual finance choice may expose an underfunded team, but it must not erase the incurred expense or claim safety. A complete structured proposal-impact summary remains unimplemented: the current defense is inspectable before/after allocations, protected reserves, manual finance review and the absence of a safe-transfer claim. Any later automated recommendation should explain retained allocation, observed charges, applicable protections and unresolved obligations.

A selected donor needs decision-specific validation. Pooled forecast accuracy or interval coverage does not establish that teams selected for withdrawals can meet retained budgets. Descriptive retained-budget exposure can be computed against mature outcomes without claiming causal savings. A validated transfer policy would additionally need an origin-frozen selection/withdrawal rule, candidate and selected denominators, matched obligations and business risk constraints. Chosen-policy evaluation and automated donor recommendations remain conditional and unimplemented in this work. The architecture does not learn allocations. Current defenses are manual finance review and explicit rejection of safe-transfer or optimal-allocation claims; neither point comparisons nor joint arithmetic supplies safety certification.

## Scope exclusions and conditional mechanisms

Unknown future model releases and industry shifts are not predicted as facts. Observed releases, known price/configuration changes, local adoption and supported migration scenarios remain forecasting concerns; the exclusion must not become a blanket rejection of post-change forecasting. A short historical series may support a modest fitted continuation model while leaving release frequency and enterprise adoption probabilities unvalidated.

Passive admission, reservation, reset, cancellation and settlement simulation is an in-scope conditional planning mechanism. Actual provider dispatch, account-limit mutation, key rotation and kill switches are excluded. These mixed cases still require an implemented boundary that prevents internal decisions from implying external action.

General-ledger posting, statutory accrual journals, vendor payments, separate employee/team products, recursive swarm budget delegation and outbound manager notifications remain parked. Distinguishing incurred, billed and cash targets and preserving late evidence remain in scope. Current read restrictions do not establish complete deletion from archives, fitted parameters or backups; production retention erasure needs backend ownership and policy.

A real public token trace supplies real measured request/token activity at its declared granularity. It does not supply employee rosters, real company teams, budgets, contracts, verified invoice dollars or business outcomes. An actual pretrained model run on that trace can support a limited temporal forecasting comparison. Synthetic company fixtures verify arithmetic, handoffs and selected failure behavior. Neither establishes representative enterprise accuracy, optimal allocations or realized savings.

## Verification status

The final integrated reference code is committed as `7c2f23f`. Root's fresh full-project run passed **519 tests in 9.03 seconds**, with successful compile and diff checks. The [final verification record](verification.md) and [source-bound machine record](verification.json) preserve the commands and results. The [independent final rereview](evidence/final-rereview.md) approved code readiness within the documented reference scope after **42 focused tests passed in 0.75 seconds**. That review covers the corrected attribution, Decimal arithmetic, structural resource bounds and actual-preserving numerical-failure handling. It does not establish enterprise calibration; the subsequent actual pretrained comparison has separate execution evidence below.

The following earlier checks remain historical scoped evidence, rather than a substitute for the final integrated run. Before the eight-task implementation, the scope audit ran:

```sh
PYTHONPATH=src python3 -m pytest -q tests/test_consumers.py tests/test_integration.py tests/test_evaluation.py
```

Result: **78 passed in 9.04 seconds**. These tests exercised the existing scalar/reference consumer contracts: independent alternatives, current authority, material-evidence staleness, protected allocations, exactly-once receipts, actuals under unavailable forecasts and the lack of automatic safe-headroom semantics. That earlier run did not verify the subsequently added joint/state/commercial mechanisms or a live Factory runtime.

The structural and path mechanisms now exist. An independent focused run of `tests/test_state.py tests/test_commercial.py tests/test_controls.py tests/test_joint.py` passed **100 tests in 0.45 seconds**. This supports the asserted fixture contracts, including finite conditional laws; it does not establish real enterprise calibration. The fitted recurrent adapter learns occurrence, positive root counts and observed start-day native token marks from qualified exposure/execution history. It does not learn root duration, termination or latent intentions. Ongoing roots need explicit continuation marks; mixed-configuration root fitting needs a separate adapter. Unknown access/capability and supplied finite parameters remain qualified assumptions.

The independent integration audit initially reproduced five serving regressions. After the serving repair, the same mechanism/serving checks plus artifact-store tests passed **126 tests in 0.80 seconds**:

```sh
PYTHONPATH=src python3 -m pytest -q tests/test_joint_service.py tests/test_state.py tests/test_commercial.py tests/test_controls.py tests/test_joint.py tests/test_store.py
```

The repaired assertions distinguish a requested remainder cost of 40 from a complete-contract cost of 240; suppress an incompatible requested monetary view while retaining valid native usage and a separately labeled contract view; propagate parent/snapshot withdrawal through artifact dependencies; and retain sensitivity scenario identity while withholding probability summaries. This is concrete local contract evidence, not whole-case or enterprise validation.

Both final state and aggregate CLI demonstrations passed: each produced **20 native tokens and 26 conditional USD**, with matching stored/retrieved artifact IDs. The [final verification record](verification.json) retains the actual outputs; the [earlier Task 7 report](evidence/task-7-report.md) explains the hand computation under two supplied reset-period tariffs. Those demonstration amounts are assumptions and calculations, not observed invoice charges. Their conditional risk arithmetic does not validate real-world event probabilities or safe budget transfers.

The benchmark input is now pinned in [its data manifest](../../benchmarks/robustness/data/burstgpt_input_provenance.json): 1,462 native hourly input-token bins from the actual six-column BurstGPT release. Thirty-six empty interior bins are zero only under the explicit recorded-release coverage assumption; they do not establish outage-free capture. Source receipt/maturity history and potential foundation pretraining contamination remain unknown. The public input data has no real people, company-team ownership, cache accounting, historical tariffs or invoice charges. Excluding those inferred claims does not exclude forecasting native workload or calculating an explicitly conditional contract estimate.

The acquisition registry audit preserved all nine BD01–BD09 source records exactly, including the conditional BD03/BD09 assumptions and the retained native/provenance guards in excluded-claim cases BD06/BD07. Data transformation execution is reported by its acquisition worker; the local raw source is not retained, so independent canonical-artifact checks do not amount to independently rerunning the complete raw transformation.

The [actual real-trace benchmark](benchmark.md) ran the baseline and joint procedures on 20 frozen origins at each of the native one-hour and four-hour horizons; all 40 opportunities were available for each numerical procedure. The joint method slightly improved on last observation at one hour and performed substantially worse at four hours. This is a limited workload result, not evidence of forecasting superiority.

**The requested basic genuine pretrained comparison has now executed.** After the earlier local attempt failed with `ModuleNotFoundError: No module named 'chronos'`, an approved temporary cloud run loaded official `amazon/chronos-bolt-tiny` weights at revision `a0e552de83495b5c28c14c71c374f3e33280b340`, verified their pinned SHA256, and produced **40/40 successful forecasts**: 20 at each horizon on the same frozen input hash and origin lists. The frozen source hash and both origin lists were independently matched against the preregistration. [Raw cloud results](results.json) and [runtime evidence](evidence/cloud-chronos/runtime-evidence.json) preserve the checkpoint, hashes, exact package versions, CPU execution with two threads, `float32`, seed 0 and procedure identity. The original missing-dependency failure is historical evidence of the earlier local run, not the current pretrained availability status.

| Native horizon | Chronos MAE, input tokens | Best baseline MAE, input tokens | Baseline |
|---|---:|---:|---|
| One hour | 292,074.44 | 345,308.56 | Trailing mean of 16 hours |
| Four hours | 964,212.12 | 824,088.75 | Last observation |

This demonstrates that the genuine pretrained model runs as a basic native-token forecaster on the real trace. It improved on the strongest baseline at one hour and lost to last observation at four hours, so there is no consistent dominance claim. The adapter uses per-bin marginal medians, clipped nonnegative; their sum is a point aggregate, not a cumulative median or mean. There is no fitted probability calibration, safe-transfer certification, causal finding or enterprise-generalization claim. Public-trace pretraining contamination and the source coverage assumptions remain unresolved. The temporary VM was stopped and root verified that state; [the stop receipt](evidence/cloud-chronos/stop-metadata.json) records it.

Production authentication, enterprise connectors, private tariffs, live Factory SDK integration and deployment are not established by local reference tests. Their absence narrows production claims; it does not convert conditional mechanisms or real workload measurements into validated enterprise decisions.
