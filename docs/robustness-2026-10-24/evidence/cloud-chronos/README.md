# Executed Chronos-Bolt Tiny evidence

The authorized temporary 2-vCPU cloud environment executed the frozen native-input benchmark successfully, producing **40/40 genuine pretrained forecasts**, then stopped. Current procedure identity is `501d304bf55847edbca545499ff0ad0c03649634751cc07774b7006a87760877`. This directory archives execution evidence; no optional runtime or weights are added to the product package.

- `results-chronos.json`: authoritative successful run, identical bytes to the published `../../results.json`.
- `runtime-evidence.json`: Python/platform, all 11 transferred source hashes, actual direct dependency versions, loaded checkpoint/config/weight identity and timings.
- `requirements-executed.txt`: complete executed package freeze, including transitive dependencies.
- `install.log` and `benchmark.log`: raw installation and benchmark command output. The logged `torch_dtype` deprecation warnings did not fail execution.
- `execution-summary.json`: root's observed command exit0, 20.779-second install/benchmark duration, stopped nonpersistent 2-vCPU session and 248.359-second session lifetime. Actual invoice cost was not queried.
- `stop-metadata.json`: relevant stopped-session fields normalized from the raw tool receipt, retaining the receipt's source path/SHA256. Internal session/project identifiers and tool-envelope noise are omitted here; the raw receipt remains at its recorded source path.
- `transfer-manifest.json` and `cloud-evidence.tar.gz`: the authoritative returned file hashes and original compressed evidence bundle. The transfer transport's redundant base64 chunks are omitted.
- `prior-local-results.json`: preserved historical local `ModuleNotFoundError: No module named 'chronos'` run, with zero foundation coverage; superseded by the successful cloud results.
- `artifact-manifest.json`: SHA256 of every archived file except this manifest itself.

The actual [official pinned model](https://huggingface.co/amazon/chronos-bolt-tiny/blob/a0e552de83495b5c28c14c71c374f3e33280b340/model.safetensors) is Apache-2.0, revision `a0e552de83495b5c28c14c71c374f3e33280b340`. Runtime adapter validation checked 34,622,352 weight bytes against SHA256 `75068728d376d2bec670379eeef4bfb4d24c0cfe24d957451f8d19b447030a32` and required full pinned configuration semantics before loading. Weight bytes are publicly retrievable and are not bundled in this small evidence archive.

Before publication, local verification checked the returned archive and every transferred file hash, all current source hashes, exact preregistered data/origins, 240 candidate-opportunity records, 40 finite successful foundation paths and their summed totals. Foundation MAE/RMSE/bias/WAPE/worst error were recomputed independently from the raw rows. Baseline/joint paths exactly match the prior real-data run. The canonical procedure digest was recomputed; runtime observations remain outside its immutable model manifest.

There are 20 opportunities per horizon, at 37 unique native origin indices across the two horizons. Cross-horizon targets and histories overlap. This is single-stream, hourly input-load evidence with idealized coverage/receipt assumptions and unknown public-trace pretraining contamination. Chronos outputs clipped per-bin marginal medians, whose sum is a point aggregate rather than a cumulative median or mean. No enterprise, monthly spending, calibrated uncertainty or allocation-safety claim follows.
