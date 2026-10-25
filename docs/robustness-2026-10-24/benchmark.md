# Genuine pretrained native-token benchmark

Chronos-Bolt Tiny ran successfully on a genuine public input-token trace: **40/40 forecasts**, with 20 predeclared opportunities at each of the 1-hour and 4-hour horizons. Its 1-hour MAE was 15.4% lower than the strongest simple comparator, trailing mean16. At 4 hours its MAE was 17.0% higher than last observation. This establishes runtime feasibility and a narrow, mixed forecasting result; it does not establish enterprise spending accuracy or a generally superior model.

## Data and target

The target is **input tokens at request submission** from [BurstGPT](https://github.com/HPMLL/BurstGPT/tree/d895a53bb7b8ec137d0d2fe203b335835a78c10a), CC-BY-4.0, attributed to Yuxin Wang et al., *BurstGPT: A Real-World Workload Dataset to Optimize LLM Serving Systems*. The pinned 50,853,373-byte source contains 1,429,737 request records. Complete interior hourly bins cover elapsed seconds `[3600,5266800)`: **1,462 bins and 872,916,802 input tokens**. The [source card and preparation script](../../benchmarks/robustness/data/README.md) retain source revision, byte hashes, license, acquisition method, QA counts and transformations.

Source timestamps represent submission. Final response lengths have no completion timestamps; an input-only primary target avoids treating future completed output lengths as known history. The older immutable CSV supplies no real teams, users, invoices or receipt/maturity histories. First/last partial hours are excluded. Its 36 empty interior hours are recorded as zero under the explicit idealized assumption that the released request stream was continuously observed; provider completeness and zero actual demand are not established. Historical online acquisition availability remains unverified.

## Frozen comparison

Before inference, [preregistered-input.json](../../benchmarks/robustness/preregistered-input.json) froze the data hash, latest 64-hour context, seasonal lag24, horizons 1/4 hours, seed0 and 20 evenly spaced final origins per horizon. Origins lie in the final chronological 20% and targets do not overlap within a horizon. Across horizons there are 40 forecast opportunities at 37 unique native origin indices; overlapping targets and histories prevent treating these as independent company samples. Earlier evaluated targets can enter later observed histories during sequential replay. No future target enters its own prefix. There was no development-based tuning, calibration or final-outcome model selection.

Every candidate receives the identical prefix and opportunities. Comparators are last observation, trailing mean16, seasonal naive24, zero diagnostic and the production joint residual-block generator with 200 paths, seed0 and mean16 baseline. The upstream README documents daily/weekly periodicity, supporting the predeclared 24-hour native lag. The joint point is the weighted mean of complete sampled paths. Its daily API receives arbitrary consecutive **bin-index dates**, which never imply calendar-day or monthly validation.

Chronos-Bolt Tiny uses official checkpoint `amazon/chronos-bolt-tiny`, immutable revision `a0e552de83495b5c28c14c71c374f3e33280b340`, Apache-2.0. The adapter verified all 34,622,352 weight bytes against SHA256 `75068728d376d2bec670379eeef4bfb4d24c0cfe24d957451f8d19b447030a32` and validated the complete pinned configuration before local-only loading. It selects native per-bin q0.5 and clips negative values to zero. **Its horizon total sums marginal medians: a point aggregate, not a cumulative median or a conditional mean.** No marginal quantiles are summed into an interval. The joint mean and foundation median-derived point therefore have distinct statistical meanings.

## Actual results

All six candidates succeeded on 20/20 opportunities at each horizon, with zero inference failures. [results.json](results.json) retains every origin, forecast path, native truth total, signed error, failure denominator, latency, slice and paired comparison.

| Procedure | 1-hour MAE, input tokens | 1-hour WAPE | 4-hour MAE, input tokens | 4-hour WAPE |
|---|---:|---:|---:|---:|
| Chronos-Bolt Tiny | 292,074 | 80.7% | 964,212 | 61.0% |
| Last observation | 358,746 | 99.1% | 824,089 | 52.1% |
| Trailing mean16 | 345,309 | 95.4% | 1,342,390 | 84.9% |
| Seasonal naive24 | 463,496 | 128.0% | 1,100,305 | 69.6% |
| Joint block mean | 349,855 | 96.6% | 1,352,667 | 85.5% |
| Zero diagnostic | 362,093 | 100.0% | 1,581,243 | 100.0% |

Chronos has lower absolute loss than last observation at 13/20 one-hour opportunities and 9/20 four-hour opportunities. Its signed mean errors are −71,471 and −445,238 input tokens respectively. Large errors remain despite the one-hour improvement. The new joint procedure slightly improves on last observation at 1 hour and performs substantially worse at 4 hours. These descriptive comparisons support no significance, calibration or automatic model promotion claim.

MAE, RMSE, signed bias, WAPE, worst-window loss and all-opportunity availability are retained in JSON; zero truth denominators remain undefined. Fixed descriptive slices are zero target, target total above `horizon*(prefix_mean+2*prefix_std)`, and any target bin above `prefix_mean+3*prefix_std`. Their thresholds use only each prefix. They are not selected operational thresholds.

## Executed runtime and provenance

The successful temporary Linux environment used Python3.11.17, CPU float32 with two threads, `chronos-forecasting==2.2.2` and `torch==2.5.1+cpu`. The full executed dependency freeze, installation/benchmark logs, source hashes and execution/stop evidence are in [evidence/cloud-chronos](evidence/cloud-chronos/README.md). Foundation inference medians were **10.73ms at 1 hour and 10.62ms at 4 hours**. The **12.33-second cold load includes imports and acquisition**; separately observed acquisition and model loading took 0.810s and 0.066s. The install-and-benchmark command completed with exit0 in 20.779s. The authorized nonpersistent 2-vCPU environment was stopped after 248.359s total lifetime; actual invoice cost was not queried.

Current procedure identity: `501d304bf55847edbca545499ff0ad0c03649634751cc07774b7006a87760877`.

The immutable manifest binds source/provenance/harness/joint/model/adapter hashes, checkpoint, actual dependencies, configuration hash, native statistic, device/dtype/threads, projection, seed, every origin and fitting/fallback policies. Acquisition/load durations remain observations outside procedure identity. New adapter fields require classification so semantic parameters cannot silently escape identity binding. The earlier local missing-`chronos` result is preserved as [prior-local-results.json](evidence/cloud-chronos/prior-local-results.json); it is historical failure evidence superseded by this executed cloud run.

The runtime requirement is now satisfied for one genuine pretrained model. This remains one hindsight serving-input stream with idealized coverage/receipt assumptions, 1/4-hour horizons and unknown public-trace pretraining contamination. It cannot validate monthly team spend, actual dollars, enterprise transfer, calibrated breach probabilities, allocation safety or workflow savings. Broader models, datasets and prospective enterprise evaluation remain unexecuted.

## Reproduce

Use an isolated Python3.11 environment with the [optional direct requirements](../../benchmarks/robustness/requirements-chronos.txt); the exact executed dependency freeze is archived separately. The product core remains standard-library only. The adapter downloads only official public revision-pinned artifacts, verifies weights/config, and never supplies a synthetic fallback.

```sh
PYTHONPATH=src .venv-chronos/bin/python benchmarks/robustness/run.py \
  --series benchmarks/robustness/data/burstgpt_hourly_input_tokens.csv \
  --bin-seconds 3600 --target-meter input_tokens \
  --provenance benchmarks/robustness/data/burstgpt_input_provenance.json \
  --context 64 --max-origins 20 --seasonal-period 24 \
  --foundation-adapter benchmarks/robustness/chronos_bolt_adapter.py \
  --output artifacts/chronos-repeat.json
```

Canonical CSV columns are `bin_start_seconds,total_tokens`; the generic value column is explicitly bound to `target_meter=input_tokens` by provenance. Noncontiguous bins, changed source hashes and target-meter relabeling are rejected. The adapter returns a callable and JSON-compatible metadata with checkpoint/revision/weight identity, dependencies, point statistic, projection and device. It is admitted only after validation; load failures clear the callable and retain every unavailable opportunity and reason. Repeated timing observations may differ without changing the procedure identity.
