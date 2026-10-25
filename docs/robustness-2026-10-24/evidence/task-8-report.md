# Task 8 benchmark harness evidence

Scope: `benchmarks/robustness/run.py`, `tests/test_benchmark_robustness.py`, `docs/robustness-2026-10-24/{benchmark.md,results.json}`. Data acquisition and genuine pretrained runtime are separate workers; edge registry is separate ownership. No commits made.

## Protocol implemented

Native complete contiguous token bins; never fill unknown gaps. Common final chronological 20% origins; horizons 1/4 native bins; nonoverlapping targets within horizon; fixed context64, last observation, trailing mean16, zero diagnostic, new joint block mean (200 paths, seed0), genuine pretrained adapter if available. Seasonal baseline is explicitly unavailable without an externally supported repeated period. Optional deterministic evenly spaced origin cap is selected by indices before model inference and disclosed in output. No development selection, calibration or empirical uncertainty claim.

Every candidate receives the identical prefix. Per-opportunity failures, availability, token MAE/RMSE/bias/WAPE (undefined for zero denominator), worst error, latency, fixed prefix-threshold load/burst/zero slices and matched paired descriptive loss differences remain in JSON. Cold model load is separate. Full procedure digest binds source/provenance/harness/joint/model hashes, adapter metadata, fixed origins, seed, projection, mean context, joint paths, fit/fallback/calibration/pricing policies. Artificial consecutive dates inside the production daily joint API are bin indices only and never trace dates or enterprise days.

## Executed red/green evidence

- `PYTHONPATH=src python3 -m pytest -q tests/test_benchmark_robustness.py` before harness implementation: **5 failed**, expected missing harness assertion.
- Same command after implementation: **5 passed**.
- Added paired-opportunity regression: **1 failed, 5 passed**, expected missing `paired_comparisons`; implemented independent candidate-versus-last matching: **6 passed**.
- Added content identity regression: **1 failed, 6 passed**, expected missing `procedure_identity`; implemented canonical complete manifest hashing: **7 passed**.
- Production joint wrapper executed on a 64-bin increasing mechanism fixture with horizon4 -> `(65.0, 66.0, 67.0, 68.0)`. This is a software smoke check, not real model performance evidence.

## Actual benchmark acquisition/run

Pending genuine trace artifact from `r_benchmark_data`; runtime worker reports no pretrained checkpoint yet, blocked shell DNS/no cache and is attempting supported native browser download. No mock checkpoint or synthetic trace will be reported as a real benchmark. Final actual commands, output and limitations will be appended after acquisition attempt.

Full-suite check during concurrent integration: `PYTHONPATH=src python3 -m pytest -q` -> **1 failed, 417 passed in 8.31s**. Failure: `tests/test_integration.py::test_real_delayed_daily_acquisition_replays_nonfuture_origin_and_retains_partial_charges`, at fresh `forecast_from_config`, where `joint_service.bound_evidence` rejects `authorized_local_file` requested versus snapshot `unspecified`. Root notified; outside benchmark ownership. No omission of this non-benchmark failure.

## Additional regression cycles and actual real-data run

- Input mutation during adapter load: **1 failed,7 passed** before checks, then **8 passed** after binding input SHA before adapter/inference and rejecting post-run mutation.
- Fixed mean16 shorter context: **1 failed,8 passed** before validation, then **9 passed** after requiring16context bins.
- Target-meter relabeling against provenance: **1 failed,9 passed** before validation, then **10 passed** after rejecting contradictions and source-hash mismatches.
- New full-suite run during concurrent implementation: **11 failed,447 passed in8.38s**. Failing names: `test_equal_weight_quantiles_select_exact_cdf_boundary`(3cases), `test_unequal_weight_quantiles_distinguish_boundary_from_next_atom`, `test_boundary_quantile_preserves_exact_decimal_money`, `test_configuration_identity_preserves_types_inside_nested_containers`(3cases), `test_target_only_bridge_overflow_retains_unavailable_opportunity_and_other_candidates`, `test_legacy_equal_weight_quantile_uses_normalized_atom_boundary`(2cases). Root notified; respective production/test owners were editing these paths. Benchmark regressions remained green.

Primary trace changed to **input tokens**, with root agreement before any result inspection. Source timestamps are request submission and final response lengths have no completion timestamp; total-token targets would backfill ultimate output lengths across origins. Input lengths are known at request submission. Source acquisition/coverage completeness is still an explicitly idealized assumption, not historical online verification. Pinned README's daily/weekly periodicity supports predeclared native lag24hours; no fabricated calendar dates.

`benchmarks/robustness/preregistered-input.json` freezes source hash, target meter,64context, lag24, horizons1/4 and20evenly spaced final origins per horizon before first numerical evaluation. Executed actual primary command:

```sh
PYTHONPATH=src python3 benchmarks/robustness/run.py --series benchmarks/robustness/data/burstgpt_hourly_input_tokens.csv --bin-seconds 3600 --target-meter input_tokens --provenance benchmarks/robustness/data/burstgpt_input_provenance.json --context 64 --max-origins 20 --seasonal-period 24 --output docs/robustness-2026-10-24/results.json
```

Actual source:1,429,737request records,1,462complete interior native-hour bins,872,916,802input tokens;36empty hours conditional on released-stream observation. All five numerical baseline/joint procedures succeed20/20at each horizon. Mean16has1hMAE345,308.56tokens versus joint349,854.73andlast358,746.00;4hlast824,088.75versus joint1,352,666.98andmean16 1,342,390.00. Seasonal1h463,495.50/4h1,100,305.00. Adverse4hjoint result retained; no champion promotion. Per-origin records and all candidate failures retained. Independently rechecked input hash and all exact origin indices against the predeclared manifest;120candidate-opportunity rows per horizon. Joint paired loss difference versus last is−8,891.27tokens1h and+528,578.23tokens4h, with8wins/12losses each; descriptive only.

Foundation genuine checkpoint still unavailable:0/20success at each horizon, explicit unavailability rather than a mock model result. Runtime researcher continues supported acquisition. Required pretrained comparison remains incomplete until actual genuine checkpoint/runtime execution. Full trace provenance, upstream CC-BY-4.0 license and reproducible preparer now live at `benchmarks/robustness/data/` under data worker ownership. Initial permanent-path run failed only because the concurrent copy had not completed; rerun after copy succeeded. No total-token secondary numerical benchmark executed.

## Review fix round 1: adapter failure atomicity and genuine-manifest boundary

Read `task-8-review.md` in full. Reviewer P2 reproduced: assigning the prediction callable before metadata normalization allowed a reported load failure to retain available foundation forecasts. Saved pre-fix source/test snapshots as `task-8-fixround1-before-{run,tests}.py` before edits.

The candidate callable now remains local until all load, callable, metadata, dependency/weight identity, adapter hash and finite JSON normalization checks succeed. Any exception explicitly clears the admitted callable. JSON roundtrip also detaches nested manifest inputs from adapter-owned mutable data. Required JSON metadata fields are documented: nonempty checkpoint, pinned revision, point_statistic, projection and device; nonempty dependencies name/version mapping; lowercase SHA256 weight identity string or filename/hash mapping. This validates a manifest, not the authenticity of underlying model bytes; independent acquisition/loading evidence remains required.

Executed regressions with temporary unit-test adapters only (never real benchmark model evidence):

- Metadata `None`, non-JSON object, NaN: **3 failed,10 passed** against pre-fix code; **13 passed** after atomic validation/admission. Each case retains exact frozen origins `[80,99]` at horizon1 and `[80,96]` at horizon4;2opportunities,0success,2failures and undefined accuracy each.
- Missing each of seven required checkpoint/runtime manifest fields: **7 failed,13 passed** before field validation; **20 passed** after validation.
- Latest targeted command: `PYTHONPATH=src python3 -m pytest -q tests/test_benchmark_robustness.py` -> **20 passed in0.21s**. Red/green logs preserved in task records.

Per root instruction, **did not regenerate the actual benchmark** during this fix round. Existing stored results have numerically unchanged baseline/joint predictions but stale harness/joint implementation hashes due concurrent reviewed fixes. They remain prior-run evidence; final `results.json` must be regenerated only after core implementation freezes and genuine adapter is available (or root explicitly chooses final truthful unavailable status). No model-runtime or numerical checkpoint result is fabricated.

Post-fix full-suite command `PYTHONPATH=src python3 -m pytest -q` -> **7 failed,490 passed in10.33s** during concurrent integration edits. All failures were `NameError: _monetary_summaries is not defined` in `joint_service.py`: `test_joint_commercial_exact_shared_pool_and_independent_unavailability`, `test_cli_compound_demo_acquires_evidence_prices_resets_and_retrieves[state]`, `[aggregate]`, `test_views_are_independently_qualified_and_commercial_inputs_replayable`, `test_monetary_remainder_excludes_historical_prefix_and_uses_requested_event`, and `test_monetary_mismatched_start_or_untimed_fixed_keeps_distinct_contract_view[full_period-fixed0]` / `[remainder-fixed1]`. Root notified; no benchmark failures. Code/tests/docs frozen for rereview in `task-8-fixround1-freeze.json`; no final actual benchmark run attempted.

## Adapter review timing fix

Read `task-8-adapter-review.md` in full. Runtime owner corrected complete pinned config semantics separately; this change addresses remaining P2: acquisition/model-load durations were report observations accidentally bound into procedure identity. Saved pre-fix run/test snapshots as `task-8-timing-before-{run,tests}.py`.

Added an explicit foundation metadata classification boundary. Immutable procedure fields include checkpoint/revision/weights, dependencies, adapter/config hashes, statistic/projection, device/dtype/threads, seed, source/license/weight size, declared calibration/contamination and explicit configuration/preprocessing/output/fit/inference policies. Acquisition/model-load/cold-load durations, runtime observations and load failure are report observations. New fields must be classified; they cannot silently disappear from the identity. Arbitrary future runtime measurements can enter the `runtime_observations` mapping. Adapter source hash is now retained even when loading fails. Full report metadata preserves observed timings.

Executed regression evidence:

- Stable-model metadata with only timing/cache-observation differences: **1 failed,20 passed** before metadata classification, expected missing boundary. After implementation: **21 passed**. Checkpoint/dependency/projection/config/dtype/threads/adapter changes all change identity; timing-only changes do not. Unknown model fields fail classification.
- Actual CLI unit regression with identical source/provenance/adapter bytes and changed observed acquisition/load durations: frozen pre-fix harness produces unequal IDs and fails the identity equality assertion; current harness produces identical IDs, retains changed durations in report metadata, excludes them from foundation procedure manifest, and changes ID on changed checkpoint. This is software verification with an explicitly unit-test adapter, not a foundation performance result. An initial frozen-source replay needed `__file__` adjusted to the actual repo script path for relative artifact lookup; corrected replay's expected assertion failure is preserved in `task-8-timing-cli-red.log`.
- Latest targeted command `PYTHONPATH=src python3 -m pytest -q tests/test_benchmark_robustness.py` -> **22 passed in0.25s**.

No actual real-trace benchmark rerun during this fix, per root instruction. Prior results remain numerically valid but stale implementation-hash evidence until final frozen genuine-model execution. Runtime owner informed of accepted stable and observation field classifications; current Chronos adapter fields fit this schema without changing its runtime measurements.

Post-timing-fix full-suite command `PYTHONPATH=src python3 -m pytest -q` -> **501 passed in8.99s**. Frozen run/test/docs hashes saved in `task-8-timing-freeze.json`; root notified. No further owned source edits planned before rereview or genuine-model execution handoff.

## Final local evidence refresh from independently executed root artifact

Root independently executed the frozen public-input benchmark with `--foundation-adapter benchmarks/robustness/chronos_bolt_adapter.py` and saved `artifacts/root-benchmark-current.json`. Per root instruction, copied that artifact byte-for-byte into `docs/robustness-2026-10-24/results.json`; did not rerun model or benchmark inference in this refresh. This supersedes the earlier stale implementation-hash status.

Actual attempted local foundation load failed with **`ModuleNotFoundError: No module named 'chronos'`**, cold-load attempt0.901787708seconds. The optional local Chronos runtime is absent. No genuine pretrained weights loaded, no foundation inference performed; both horizons retain exactly20opportunities,0successes,20failures,0availability and undefined accuracy. Prepared adapter code identity is retained despite its failed load. Cloud runtime acquisition remains pending user approval; required genuine pretrained comparison is still incomplete.

Current procedure identity: **`d3c17a4d74724d6107ef045a33c449bc6aa77aa4ee819f04084c2256811d9bab`**.

Executed artifact verification (standard-library Python, no optional model imports/inference):

- Source SHA256 matches both the actual canonical CSV and predeclared `501f1f40c880ee38bc97b73ad5f15f9bd1d42866357edb55e9e5f396d13858de`.
- All exact horizon1/4origin indices match `preregistered-input.json`;120candidate-opportunity records per horizon,240total retained.
- All baseline/joint prediction paths and native truth totals exactly match prior genuine-trace measurements; accuracy conclusions unchanged.
- Harness, joint, numerical model, provenance and adapter hashes all match current frozen files.
- Independently canonicalized/hash-recomputed the entire procedure manifest; exact current identity reproduced.
- Published results bytes equal root artifact bytes; benchmark documentation now reproduces the actual adapter-attempt command and states the missing dependency, pending cloud approval and incomplete pretrained requirement.

Root separately reported final501tests passed, compilation/diff checks clean and both CLI demos verified. My independently executed full-suite evidence remains501passed in8.99s from the timing-fix verification above. No code edits occurred during this final documentation/results refresh.

## Final checkpoint refresh: 7c2f23f

This final refresh supersedes the previous `root-benchmark-current.json`/`d3c17a4d...` published checkpoint. Root independently reran the exact benchmark command after final implementation checkpoint **7c2f23f** and reported **519 tests passed in9.03s**. Copied `artifacts/root-benchmark-7c2f23f.json` byte-for-byte into published `results.json`. No code edits or model/benchmark rerun by this worker.

Current published procedure identity: **`9818f3e4b71e1169c016f2e62949c423abec7ea5561797dcd629a13faa53c80b`**.

Executed independent artifact checks: source SHA and every exact horizon1/4origin match preregistration;120rows/horizon retained; every stored prediction scalar/path and truth total equals prior actual-trace results; every candidate's opportunity count, success/failure count, availability, MAE, RMSE, bias, WAPE and worst absolute loss are exactly unchanged. Current source/provenance/harness/joint/model/adapter hashes all match manifest fields; canonical manifest hashing reproduces the current published identity; published bytes equal newest root artifact bytes. The benchmark page contains only the newest procedure identity.

Actual foundation outcome remains **`ModuleNotFoundError: No module named 'chronos'`**, cold-load attempt **0.725933708seconds**;20/20unavailable opportunities per horizon and no weights/inference. Cloud approval remains pending. Updated benchmark page to current identity and measured attempt duration. Final results/documentation hashes frozen in `task-8-final-7c2f23f-freeze.json` for scoped rereview/registry integration.
