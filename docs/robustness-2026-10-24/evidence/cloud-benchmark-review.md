# Independent review of the executed Chronos benchmark

**Approved as actual genuine pretrained token-load benchmark evidence.** No blocking issue found in the captured cloud run. Chronos-Bolt Tiny supplied40 successful forecasts:20 at each predeclared horizon. This approval concerns the captured fixed experiment and its recorded arithmetic, not enterprise spending accuracy or empirical uncertainty calibration.

Reviewed artifacts are in [`artifacts/cloud-chronos-20261024/`](../../../artifacts/cloud-chronos-20261024/): `results-chronos.json`, `runtime-evidence.json`, `requirements-executed.txt`, transfer/archive manifest, install/benchmark logs and stop result. Historical comparison used [`artifacts/root-benchmark-7c2f23f.json`](../../../artifacts/root-benchmark-7c2f23f.json), avoiding the concurrently updated published results file. No source changes, model rerun, mocks or full test suite were used for this review.

## Artifact and genuine runtime checks

Programmatically recomputed SHA256 for all11 source/data/configuration paths in `runtime-evidence.json`; every value matches the current repository. This includes adapter, harness, joint/model implementation, contracts/uncertainty, requirements, preregistration, input CSV and provenance. Report inputs and procedure manifest agree with those hashes. Canonical manifest hashing reproduces procedure identity `501d304bf55847edbca545499ff0ad0c03649634751cc07774b7006a87760877`. Acquisition/model-load/cold-load durations remain outside the procedure identity and available in observed metadata.

Independently decoded each of the22 transferred base64 chunks, concatenated their decoded bytes and verified the21,252-byte archive SHA256 `618103ad71aab4826f76950b962564252e45fe8c2abe2c7929d8f023f055df97`. All five extracted file hashes match both the transfer manifest and archive members. Results SHA256 is `681ad015c23e9910f02a942248a34e830c2f8ef9771d215bd475f41c2cf86e2d`. The stop result records both sandbox and session as `stopped`.

The runtime identifies Python3.11.17 on Linux x86_64, CPU float32 with two torch threads, seed0, `chronos-forecasting==2.2.2` and `torch==2.5.1+cpu`. All nine adapter dependency versions agree with the captured full package freeze and direct requirements; the CPU build suffix is the documented torch distribution. Install logs support actual installation. The full freeze retains transitive package versions for reproduction.

Checkpoint metadata matches the independently reviewed [official pinned Chronos-Bolt Tiny weight identity](https://huggingface.co/amazon/chronos-bolt-tiny/blob/a0e552de83495b5c28c14c71c374f3e33280b340/model.safetensors): revision `a0e552de83495b5c28c14c71c374f3e33280b340`, SHA256 `75068728d376d2bec670379eeef4bfb4d24c0cfe24d957451f8d19b447030a32`, declared34,622,352 bytes. The exact transferred adapter source requires that size/hash for downloaded and cached weights, checks full official configuration semantics before loading, loads locally through the genuine Chronos pipeline and contains no synthetic prediction fallback. Runtime metadata records actual config SHA256 `278f0086733031635fb1c861cb01c1bad6477420c7fcb19381a2993e335785e0` and adapter SHA256 `293f971a981ac9c7b81058be6b06207df4ca34df3e69b213d0ba68d04f6f6be7`; both metadata captures agree. Weight/config bytes were not transferred to this reviewer for a second local byte hash; verification relies on captured successful execution of the hash-bound adapter and its mandatory acquisition checks. Prior config/API review is recorded in the Task8 adapter review.

## Independent row and metric audit

Read the1,462-bin input CSV and all240 result rows programmatically. Its872,916,802 input tokens, hourly bin duration, target meter and source hash agree with provenance/preregistration. Both horizon origin arrays match the preregistration and historical run exactly. Every origin is in the final20% segment, has64 preceding context bins, and permits a complete target. Each procedure has20 unique opportunities per horizon; targets do not overlap within a horizon. The hash-bound harness passes only `values[origin-64:origin]` to every candidate, and the adapter passes that prefix directly to the pretrained pipeline. No future target enters its own context. Later origins legitimately incorporate preceding observations.

Independently recalculated, for every row: truth total, horizon/target end, path length, finite/nonnegative predictions, path sum, signed error and all zero/high-load/burst slice flags using prefix-only thresholds. Recomputed every candidate's MAE, RMSE, bias, WAPE, worst loss, availability/failure counts, latency sum/median and failure reasons, both overall and in all reported slices and matched-success summaries. Recomputed all paired mean loss differences and win/tie/loss counts versus last observation. All agree, using relative tolerance1e-12 and absolute tolerance1e-9 for floating arithmetic.

All200 nonfoundation candidate rows match historical records exactly after excluding latency. Foundation has20/20 availability at both horizons, so all20 origins also enter each horizon's all-candidate matched summary. No failed opportunity was dropped or replaced.

| Foundation statistic |1 hour|4 hours|
|---|---:|---:|
|MAE, input tokens|292,074.44375|964,212.115625|
|RMSE, input tokens|542,546.085636|1,570,597.981287|
|Signed bias, input tokens|−71,471.342188|−445,237.68125|
|WAPE|80.66285%|60.97813%|
|Mean absolute-loss difference versus last|−66,671.55625|+140,123.365625|
|Paired wins/ties/losses versus last|13/0/7|9/0/11|
|Median inference latency|10.72945ms|10.61833ms|

Observed cold adapter load was12.33131seconds, including imports/acquisition; separately measured acquisition was0.81039seconds and model construction/load0.06599seconds. These describe this machine/run rather than a service latency guarantee.

## Interpretation and limits

The adapter selects q0.5 from each bin's native-scale marginal output, clips negative predictions to zero and sums those point forecasts. Its four-hour point is **a sum of marginal medians**, not a claimed median or mean of cumulative usage. The [official v2.2.2 API implementation](https://raw.githubusercontent.com/amazon-science/chronos-forecasting/v2.2.2/src/chronos/chronos_bolt.py) supports the adapter's `(batch,quantile,horizon)` interpretation. Joint results use a sampled-path mean, so native point statistics remain explicitly distinct.

Chronos improves on last observation in this1-hour sample and performs worse at4hours. Large errors persist; no general superiority follows. The40 foundation forecasts are not40 independent samples: cross-horizon targets can overlap and the stream is dependent. There is no fitted uncertainty calibration, confidence interval, significance test, breach-probability validation or model selection evidence here. Pretraining contamination remains unknown for this public trace.

The trace describes input workload at request submission, under explicitly idealized release-coverage and preceding-bin availability assumptions. It lacks verified historical receipt/maturity coverage, real team ownership, invoices and tariff evidence. Those boundaries, one-stream sampling and the1/4-hour horizons prevent enterprise weekly/monthly spending, online acquisition or calibrated tail-risk generalization. Earlier unavailable-foundation runs remain historical failed local attempts; this captured cloud run now supplies the previously missing genuine pretrained execution without changing their history.
