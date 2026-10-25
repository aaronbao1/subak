# Task 7 integrated serving report

Implemented `ForecastService.run_joint` plus real `POST /v1/joint-forecast` and existing `GET /v1/results/{artifact_id}` retrieval. Core entry point also available as `forecasting.joint_service.run_joint(service, request, snapshot, ...)`. Existing scalar run/retrieve API remains.

## Evidence and behavior

- Aggregate mode calls the selected shared-block generator once for the complete native axis panel. Structural mode calls the recurrent state generator once; delayed requested target starts advance state from actual origin before a lineage-bound exact date slice. Aggregate history lag uses the generator's explicit mature-watermark bridge and actual reporting origin.
- Coherent daily entity means conserve company totals. Requested-target quantiles, strict exceedance probability, expected excess, and weighted fractional-atom expected shortfall each carry independent qualification. Supplied laws remain assumption-conditional; empirical calibration is unavailable. Full-period native risk includes recorded actuals only when coverage is complete. Incomplete incurred gaps retain known actuals/future means and explicitly partial known-plus-future views, while complete-target probability summaries are unavailable.
- Trusted `commercial_options` accepts a mapping or a callable taking the generated bundle, allowing exact path-bound prefix manifests without any independent law zipping. `price_bundle` consumes its catalog/prefixes exactly once. Unsupported commercial coverage leaves usage intact. Exact commercial path/period/allocation output and resolved material inputs are immutable artifacts.
- Immutable snapshots, optional gap snapshots, shared bundles, parent bundles, state output plus as-of execution replay, commercial inputs/results, and final results inherit target source permissions. Replay IDs bind request, snapshot, procedure, scenario, output, dates, risk settings, provenance and exact material pricing input IDs. Current ACL removal and artifact revocation prevent retrieval.
- Caller provenance cannot upgrade or relabel source-bound provenance. Root explicitly extended file ownership to one line in `integration.py`: serving policy now uses `snapshot.evidence_class`, while config evidence remains the acquisition namespace. This preserves the existing fresh-store unavailable behavior without accepting a fabricated authorization class.
- Workload adjustments multiply only future native paths, bind explicit adjustment/assumption IDs, reject duplicate application, preserve baseline parent bundle artifacts, retain observed actuals and label workload estimand. No safe-transfer recommendation or real provider enforcement is claimed.

## Executed verification

Initial RED: `PYTHONPATH=src python3 -m pytest tests/test_joint_service.py -q` — 6 expected failures for absent service method/route (`task-7-red.log`). Compound pricing RED caught missing monetary threshold integration; requested state-target slice and missing CLI RED recorded in `task-7-demo-red.log`. Additional observed RED checks caught missing independent qualification metadata, unsupported invalid-law swallowing, and incomplete full-period native total handling before fixes.

Final focused: `PYTHONPATH=src python3 -m pytest tests/test_joint_service.py -q` — **15 passed**.

Whole project: `PYTHONPATH=src python3 -m pytest -q` — **460 passed in 12.05s**, no failures (`task-7-suite.log`). This includes existing delayed/scalar integration regressions and other workers' current changes at execution time.

`python3 -m compileall -q src/forecasting/joint_service.py src/forecasting/service.py src/forecasting/cli.py` — exit 0.

## Compound demonstrations actually run

```sh
PYTHONPATH=src python3 -m forecasting joint-demo --output-dir artifacts/robustness-task7-final-state --process state
PYTHONPATH=src python3 -m forecasting joint-demo --output-dir artifacts/robustness-task7-final-aggregate --process aggregate
```

Use a fresh directory for another execution. Both commands acquire/retain normalized synthetic receipt bytes through SourceStore, build a coverage-qualified snapshot, select one generator, transform shared native paths through two complete synthetic tariff reset periods, calculate risk, store all artifacts and retrieve the result under current source ACL.

Hand computation: two entities produce 2+3 tokens/day for 4 days = **20 tokens**. Each two-day reset period contains 10 tokens, one shared allowance of 5, rate 2 and fixed 3: `(10-5)*2+3=13`. Two periods total **26 USD conditional estimate**. All paths are constant in this fixture, so `P(cost>25)=1` and ES at confidence .95 is 26.

Outputs:
- `artifacts/robustness-task7-final-state/joint-demo.json`; result `7edd5c86893124e630b311d0f8a75c1ac44e78880fa62ba3a194427820cb4fb2`.
- `artifacts/robustness-task7-final-aggregate/joint-demo.json`; result `a96d00a343add82e0b080fe2ce59480712b4debd779fc5047737e4dd72f1f9c9`.

Both retrieved IDs exactly match their stored result IDs; each emits synthetic_fixture, safe_transfer=false, native mean20, conditional-contract mean26, monetary exceedance1, expected shortfall26.

## Limits

The demonstration is synthetic. It provides no public-trace or enterprise empirical accuracy claim; that is Task8's separate benchmark. Statistical rational expectations use exact rational normalized weights with an explicit 50 significant decimal digit projection; commercial path prices and allocations remain exact Decimal. No automatic monetary billing/cash bridge, enterprise calibration promotion, safe-transfer recommendation, paid call or external operation is added. No commit created.

# Independent review fix round 1

Review: `task-7-review.md` identified three high integration defects after the initial whole-suite run. All owned source/test files and newly authorized `store.py` were preserved in `task-7-before-fix/` before editing. Root authorized focused generic dependency handling in `store.py`; no further full suite was run in this round, per root instruction.

Observed RED: `PYTHONPATH=src python3 -m pytest tests/test_joint_service.py -q` produced **6 failed / 15 passed** (`task-7-fixround1-red.log`). This independently reproduced monetary remainder240 instead of40, unsupported partial fixed/full-start mismatch, parent withdrawal remaining readable, missing generic dependency API, and sensitivity sharing the baseline artifact identity.

Corrections:

- New `_monetary_summaries`: requested remainder values use each exact commercial `future_increment`, plus fixed charges only for complete contract periods wholly inside the requested interval. A mid-contract nonzero fixed charge has no supplied temporal attribution, so the requested monetary view is unavailable. Full-period requests must exactly match each pool's complete commercial coverage. The complete-contract estimate remains under `monetary.complete_contract`, with explicit pool intervals, its own output qualification, and no requested-target threshold or event probability. Regression: native20/prefix100/rate2 gives requested monetary40 and P(>100)=0, while the separately labeled complete contract is240.
- `ArtifactStore.put(..., required_artifacts=())` binds material dependencies and conservatively inherits their source union. `ArtifactStore.get` iteratively validates every dependency's tenant/content/current source ACL/revocation state. Empty-dependency documents retain their prior schema and identity. Joint snapshot/supplement/state/parent/bundle/commercial-input/commercial-result/final artifacts now form an explicit dependency graph; `required_artifacts` trusted service options allow the backend to link additional material context evidence. Scalar results newly created by `ForecastService._run` also depend on their recorded snapshot/supplement artifacts. Revoking a snapshot, workload parent, or transitive external context artifact now blocks the derived result with ordinary source permissions unchanged; unrelated independent artifacts stay readable.
- Structural output now binds the requested ScenarioSpec, preserving the original generated bundle as an immutable parent when the declaration changes. Sensitivity grids strip probability weights and never publish mean/quantile/exceedance/tail probabilities. Workload adjustment preserves scenario kind and any declared non-baseline estimand (e.g. stress); baseline workload adjustment retains its explicit workload estimand. The requested scenario changes artifact identity and is recorded in the manifest.

Final targeted command:

```sh
PYTHONPATH=src python3 -m pytest tests/test_joint_service.py tests/test_service.py tests/test_service_models.py tests/test_store.py -q
```

Result: **43 passed in 1.76s**, no failures (`task-7-fixround1-targeted.log`). Joint service now has22 passing parameterized cases, including both compound CLI process routes. `compileall` over joint_service/service/store also exited0. Independent scope reviewer additionally reported126/126 passing across joint_service/state/commercial/controls/joint/store. The old460-test full-suite result above predates these review corrections; it is not presented as verification of this round.

Changed symbols: `joint_service._monetary_summaries`, `joint_service.run_joint` dependency graph/scenario handling, `ForecastService._run` snapshot dependencies; `ArtifactStore.put/get/_read`; seven added parameterized regression cases in `tests/test_joint_service.py`. No commit, external operation, numerical-module change, or new empirical claim.

Remaining explicit limits: partial-contract nonzero fixed timing is unavailable without a temporal attribution contract; full-period monetary target intervals must match complete supplied commercial periods. Finite sensitivity samples have no probability interpretation. Dependency withdrawal applies to newly linked artifacts; preexisting stored documents without dependency declarations keep their legacy schema and are not retroactively rewritten.

# Independent review fix round 2

Read the full `task-7-rereview1.md` before freezing. It confirms the round1 money/scenario findings resolved and identifies one remaining chain edge omission: generated baseline → declared sensitivity → exact date slice → adjusted bundle. Intermediate stored bundles lacked their preceding material parent dependency even though final result closure was protected.

Preserved current owned files in `task-7-before-fix2/` before editing. Added `test_chained_structural_artifacts_inherit_each_direct_parent_withdrawal`, then observed RED: direct read of a derived intermediate artifact remained allowed after withdrawing the original generated parent (`task-7-fixround2-red.log`).

Narrow correction in `run_joint`: immediately append each newly stored parent artifact to `material_dependencies` before declaring, slicing or adjusting the next bundle. Each later intermediate write and final bundle thus binds its actual material parent plus the existing ancestor closure. Removed the old final-only parent-list merge. No store/API or unrelated behavior change.

Final targeted command: `PYTHONPATH=src python3 -m pytest tests/test_joint_service.py tests/test_store.py -q` — **28 passed in 0.41s** (`task-7-fixround2-targeted.log`). The chain regression confirms original-parent withdrawal blocks direct get of both intermediate declared/sliced artifacts, final adjusted bundle, final result artifact, and `ForecastService.retrieve`; independent preceding state evidence remains readable. No full suite run, per root instruction. Source frozen for re-review; no commit.
