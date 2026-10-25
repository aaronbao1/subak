# Verification checkpoint

Root independently verified the combined code committed as `7c2f23f`, following the eight task reviews and the consolidated final fix wave. The [scoped final rereview](evidence/final-rereview.md) approved all four corrections and independently passed 42 targeted tests. The genuine pretrained comparison remains incomplete.

| Check actually executed | Result |
|---|---|
| `python3 -m pytest -q -p no:cacheprovider` | 519 passed in 9.03 seconds |
| `python3 -m compileall -q src/forecasting benchmarks/robustness` | Exit 0 |
| `git diff --check` and staged diff check | Exit 0 |
| State CLI demonstration | 20 native tokens, 26 conditional USD; stored/retrieved IDs match |
| Aggregate CLI demonstration | Same hand-computed totals and retrieval identity |
| Genuine BurstGPT input-token benchmark | 20 frozen origins at each of two horizons; all baseline/joint forecasts available |
| Prepared Chronos adapter load attempt | Failed: `ModuleNotFoundError: No module named 'chronos'`; zero pretrained forecasts |

The [machine-readable verification record](verification.json) binds this checkpoint to source hashes and the actual demo outputs. [Task evidence](evidence/) records the specific regressions, independent reviews and resolved findings. Counts are mechanism checks, not evidence of enterprise accuracy or probability calibration.

The benchmark's primary input file and all 40 origins match the preregistration. An independent reviewer recomputed all 240 candidate opportunity rows, truth sums, baseline paths and aggregate metrics; all 40 joint predictions reproduced. Root then refreshed the run against the final task code and attempted the pinned adapter. [Results](results.json) retain the concrete loader failure and every unavailable opportunity.

No pretrained weights were loaded, no model inference was performed, and no cloud resource was created. Shell DNS and two browser routes failed during acquisition; supported GitHub binary routes also failed. The public CSV was acquired through the supported GitHub connector and aggregated without passing its 50 MB content through the model. A temporary cloud run is prepared but requires the pending approval for a billable resource.

The synthetic demonstrations do not validate adoption behavior, capability scores, causality, live provider billing, real employee attribution, calibrated breach probabilities, or safe budget transfers. The public hourly trace supports a limited native-load comparison. Its release coverage, model pretraining contamination and lack of enterprise identity/contract data remain explicit limitations.
