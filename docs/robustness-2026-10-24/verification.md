# Verification checkpoint

Root independently verified the combined code committed as `7c2f23f`, following the eight task reviews and the consolidated final fix wave. The [scoped final rereview](evidence/final-rereview.md) approved all four corrections and independently passed 42 targeted tests. The genuine pretrained comparison subsequently completed on the same reviewed code and frozen origins.

| Check actually executed | Result |
|---|---|
| `python3 -m pytest -q -p no:cacheprovider` | 519 passed in 9.03 seconds |
| `python3 -m compileall -q src/forecasting benchmarks/robustness` | Exit 0 |
| `git diff --check` and staged diff check | Exit 0 |
| State CLI demonstration | 20 native tokens, 26 conditional USD; stored/retrieved IDs match |
| Aggregate CLI demonstration | Same hand-computed totals and retrieval identity |
| Genuine BurstGPT input-token benchmark | 20 frozen origins at each of two horizons; all baseline/joint forecasts available |
| Genuine Chronos-Bolt Tiny cloud run | 40/40 successful forecasts; pinned weights/configuration verified; command exit 0 |
| Cloud cleanup | Session confirmed stopped; persistence disabled |

The [machine-readable verification record](verification.json) binds this checkpoint to source hashes and the actual demo outputs. [Task evidence](evidence/) records the specific regressions, independent reviews and resolved findings. Counts are mechanism checks, not evidence of enterprise accuracy or probability calibration.

The benchmark's primary input file and all 40 origins match the preregistration. An independent reviewer recomputed all 240 candidate opportunity rows, truth sums, baseline paths and aggregate metrics; all 40 joint predictions reproduced. Root then refreshed the run against the final task code. The initial local adapter attempt failed because `chronos` was unavailable; that result is retained as historical evidence. Following authorization, the pinned adapter ran successfully in the temporary cloud sandbox. The current [results](results.json) retain all 240 candidate opportunity rows, including 40 genuine foundation predictions. The [independent cloud benchmark review](evidence/cloud-benchmark-review.md) recomputed every record, overall/slice/matched metric and paired count; all 200 nonfoundation rows agree with the historical run apart from latency.

The cloud run loaded the pinned Apache-2.0 Chronos-Bolt Tiny checkpoint after validating its weight hash, size and complete configuration. It used Python 3.11.17, CPU float32 and two threads, with the pinned direct dependencies and a recorded full environment. Root verified the retrieved archive and each file hash, matched all 11 transferred source/data hashes to the reviewed local files, and confirmed the sandbox stopped after 248.359 seconds with persistence disabled. [Runtime evidence](evidence/cloud-chronos/runtime-evidence.json) and [execution details](evidence/cloud-chronos/execution-summary.json) preserve these checks. Actual invoice cost was not queried. Earlier local network/browser acquisition failures remain historical evidence.

The synthetic demonstrations do not validate adoption behavior, capability scores, causality, live provider billing, real employee attribution, calibrated breach probabilities, or safe budget transfers. The public hourly trace supports a limited native-load comparison. Its release coverage, model pretraining contamination and lack of enterprise identity/contract data remain explicit limitations.
