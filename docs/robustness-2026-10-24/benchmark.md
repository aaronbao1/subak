# Native-token benchmark

The reproducible harness is `benchmarks/robustness/run.py`. It measures token-load forecasts in the trace's native time bins. It does not measure enterprise monthly spending, invoice amounts, team allocations or calibrated breach probabilities.

## Frozen protocol

Use genuine public trace bytes and accompany the normalized CSV with source, license, pinned revision, SHA256, retrieval method, native timestamp range, token field definitions, filters and coverage provenance. The CSV columns are `bin_start_seconds,total_tokens`. Bin starts must be consecutive and equally spaced. Missing internal coverage is rejected, not filled with zeros. Acquisition must justify complete bins and any observed zero bins. Partial edge bins must be discarded upstream.

Fixed zero-shot procedures use the same latest64-bin prefix at each origin: last observation, mean of latest16 bins, zero diagnostic, and the production joint residual-block generator (200 paths, seed0, mean16 baseline). The joint point is the weighted mean of complete sampled paths. A genuine pretrained adapter must supply its native point statistic, checkpoint and dependency provenance, projection and device metadata. Seasonal naive uses a predeclared24-hour native lag: the pinned dataset README documents daily/weekly periodicity. This is a workload comparator, not a weekly/monthly enterprise claim.

The final20% chronological segment is untouched by fitting decisions and model selection. Horizons are1 and4 native bins; targets do not overlap within each horizon. There is no D/C tuning, fitted uncertainty calibration or empirical probability claim. The optional `--max-origins` cap chooses indices evenly across this final segment before inference and discloses them exactly. Earlier final targets may enter later origin histories, as in ordinary sequential forecasting; no future target enters its own prefix. Cross-horizon targets can overlap, so their sample counts cannot be added as independent evidence.

Every candidate has identical opportunities and prefix. Failures remain in the all-opportunity denominator. JSON reports conditional cumulative MAE, RMSE, signed bias, WAPE (undefined for zero truth denominator), worst absolute loss, cold model-load time, inference latency, failures, exact origins and descriptive paired losses versus last observation. Slice rules are fixed: zero target; target total above `horizon*(prefix_mean+2*prefix_std)`; any target bin above `prefix_mean+3*prefix_std`. These are outcome-defined descriptive slices with train-only thresholds. They are not selected policy thresholds.

The joint module's date-only API receives artificial consecutive index dates. These are a mathematical encoding of equal-width bins only. Actual horizon durations stay in seconds; no minute/server trace is relabeled as a daily or monthly enterprise test.

The result identity binds data/provenance/harness/joint/model hashes, declared adapter model behavior (checkpoint, dependencies, configuration, native statistic, device/dtype/threads, seed and projection), every origin, context, fallback and fitting policy. Observed acquisition, model-load and cold-load durations remain report observations and never enter procedure identity. Additional runtime observations belong in `runtime_observations`; new adapter metadata requires explicit classification so semantic parameters cannot silently escape identity binding. Model failures are retained and never replaced by a synthetic foundation result.

## Reproduce

```sh
PYTHONPATH=src python3 benchmarks/robustness/run.py \
  --series benchmarks/robustness/data/burstgpt_hourly_input_tokens.csv \
  --bin-seconds 3600 \
  --target-meter input_tokens \
  --provenance benchmarks/robustness/data/burstgpt_input_provenance.json \
  --context 64 --max-origins 20 --seasonal-period 24 \
  --foundation-adapter benchmarks/robustness/chronos_bolt_adapter.py \
  --output docs/robustness-2026-10-24/results.json
```

The checked-in command attempts the prepared pinned Chronos-Bolt Tiny adapter. Install its isolated optional runtime from `benchmarks/robustness/requirements-chronos.txt` before expecting inference. Optional dependencies belong in an isolated benchmark environment, not the standard-library product core. The adapter exports `load() -> (predict, metadata)` and `predict(prefix,horizon)` returns exactly `horizon` finite nonnegative token values. Metadata must be a JSON-compatible mapping containing nonempty `checkpoint`, pinned `revision`, `point_statistic`, `projection` and `device` strings; `dependencies` is a nonempty package/version string mapping; `weights_sha256` is either a lowercase64hex SHA256 or a nonempty filename/SHA256 mapping. Additional source/license/checkpoint provenance fields are retained. These fields are necessary manifest checks; source acquisition and actual weight loading still require independent evidence. Callable and metadata are admitted together only after validation. A failed import, load, metadata validation or hash collection clears the candidate and retains every unavailable opportunity with the failure reason and load time. Without an adapter every foundation opportunity is explicitly unavailable.

## Actual genuine trace run

The primary target is **input tokens at request submission** from [BurstGPT](https://github.com/HPMLL/BurstGPT/tree/d895a53bb7b8ec137d0d2fe203b335835a78c10a), CC-BY-4.0, attributed to Yuxin Wang et al., *BurstGPT: A Real-World Workload Dataset to Optimize LLM Serving Systems*. The immutable50,853,373-byte source has1,429,737 request records. Complete interior hourly bins span elapsed seconds[3600,5266800):1,462 bins and872,916,802 input tokens. The source's final response lengths are attributed to submission time with no completion timestamps; using input-only targets avoids treating future completed output lengths as known past history. No invoice or billing target exists.

Coverage remains conditional:36 empty interior hours are recorded as zero under the idealized assumption that the released stream is continuously observed. The source supplies no completeness, receipt or maturity history, so this does not establish historical online acquisition validity. First/last partial hours are excluded. The older immutable CSV has no real users/teams or completion/session fields.

Before inference, `benchmarks/robustness/preregistered-input.json` froze the input hash,64-hour context, seasonal lag24, horizons1/4 hours and20 evenly spaced origins per horizon in the final20%. Exact origins, per-origin predictions, failures and source/procedure hashes are in [results.json](results.json). Targets are nonoverlapping within each horizon, with cross-horizon dependence; no significance claim is made.

| Procedure |1-hour MAE, input tokens|1-hour WAPE|4-hour MAE, input tokens|4-hour WAPE|
|---|---:|---:|---:|---:|
|Last observation|358,746|99.1%|824,089|52.1%|
|Trailing mean16|345,309|95.4%|1,342,390|84.9%|
|Seasonal naive24|463,496|128.0%|1,100,305|69.6%|
|Joint block mean|349,855|96.6%|1,352,667|85.5%|
|Zero diagnostic|362,093|100.0%|1,581,243|100.0%|
|Genuine pretrained foundation|unavailable|undefined|unavailable|undefined|

Every numerical baseline/joint procedure succeeded on20/20 opportunities at each horizon. The new joint procedure slightly improves on last observation at1hour and performs substantially worse at4hours; it does not establish forecasting superiority. Joint median inference took approximately2milliseconds per opportunity on this machine, with import overhead included in its first call. Baseline latencies are in JSON. High errors and the narrow single-stream sample prevent enterprise transfer claims.

The final local run attempted `chronos_bolt_adapter.py` and failed during runtime loading with **`ModuleNotFoundError: No module named 'chronos'`**, after0.726seconds of cold-load attempt time. No pretrained weights were loaded and no foundation inference ran. All20foundation opportunities at each horizon remain unavailable with undefined accuracy. The current result binds the frozen source and adapter/implementation hashes under procedure identity `9818f3e4b71e1169c016f2e62949c423abec7ea5561797dcd629a13faa53c80b`.

Cloud runtime acquisition is pending user approval. The user-required genuine pretrained comparison remains incomplete; these are actual real-trace baseline/joint measurements plus an executed local dependency failure. No synthetic foundation result is substituted.
