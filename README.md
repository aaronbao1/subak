# Evidence-bound forecasting

A runnable Python reference implementation of the forecasting architecture in [the research dossier](docs/forecasting-research/README.md). It preserves financial meaning, historical availability, source permissions, model eligibility and immutable reviewed outputs. Backend owns source acquisition and financial transactions; Factory owns evidence extraction/explanation; this package owns numerical forecasts and their evaluation.

The core and synthetic integration tests run locally. No enterprise dataset, authenticated provider account, live Factory runtime or prospective outcomes were supplied. The included model ranking is a synthetic mechanism demonstration, not a production champion or enterprise accuracy claim.

## Run

Python 3.9 or newer. The core has no third-party runtime dependency. NumPy/scikit-learn enable the actual regression and tabular challengers.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[models,test]'
.venv/bin/python -m pytest -q
.venv/bin/forecasting demo --output-dir artifacts/northstar-first-run
.venv/bin/forecasting evaluate --seed 7 --output artifacts/evaluation.json
```

The demo requires a fresh output directory, writes normalized source/config files, archives raw bytes, saves immutable forecasts/scenarios, and executes the two independent Northstar allocation alternatives through the reference backend. Its computed forecasts differ from the original illustrative placeholders. Every number is synthetic. Both backend reviews are explicitly simulated finance actors.

If dependencies are already installed, the verified offline source invocation is:

```sh
PYTHONPATH=src python3 -m pytest -q
PYTHONPATH=src python3 -m forecasting forecast examples/northstar-config.json --store artifacts/results.sqlite
PYTHONPATH=src python3 -m forecasting models
PYTHONPATH=src python3 -m forecasting show RESULT_ARTIFACT_ID --store artifacts/results.sqlite --tenant northstar --source billing
```

`show` assesses current age and source access without altering the reviewed result. Unavailable forecasts retain measured spending; an unsupported probability is never displayed as zero.

For actual authorized files, acquisition and historical availability are separate:

```sh
PYTHONPATH=src python3 -m forecasting ingest your-config.json --store artifacts/production-reference.sqlite
# Later, use a nonfuture reporting-midnight as_of in the same config/store.
PYTHONPATH=src python3 -m forecasting forecast your-config.json --store artifacts/production-reference.sqlite
```

Use `evidence_class: "authorized_local_file"` for these files. Original receipts and coverage revisions persist in the adjacent `production-reference-sources.sqlite`; synthetic examples use a separate namespace and cannot be relabeled as historical real acquisition. Fresh imports never enter an earlier origin. Reimporting identical active bytes preserves their first receipt; a replacement reverting to earlier content records its new activation time.

Delayed sources can opt into an explicit `history_end` (exclusive end of the contiguous mature training prefix) and `max_history_lag_days` (default 0, maximum 30). The service forecasts across this bridge and returns only genuine future dates. A separate same-source snapshot retains known partial incurred amounts in the gap; missing late charges stay unknown. Direct cumulative slicing and new entities without training support are unavailable. Missing dates inside the training prefix are still rejected. See the [full delayed-source contract](docs/implementation/api.md#durable-acquisition-and-delayed-daily-data).


## What runs

- Strict versioned Decimal financial contracts; authorized normalized JSON/CSV and native Anthropic Console Cost Report file imports; atomic replacement, delta, revision and counter semantics; exact arithmetic, raw archives and replay manifests.
- Coverage and maturity gates, as-of source/processing timestamps, bitemporal attribution, explicit shared/unattributed amounts and company conservation.
- Ten real numerical candidates: last observation, trailing/weekday means, seasonal naive, exponential smoothing, damped local linear trend, calendar ridge regression, pooled ridge, tabular daily mean, and direct cumulative tabular regression. Eligibility and dependency failures are explicit.
- Full-period/remainder forecasts, coherent entity sums, disclosed point versus mean semantics, full-contract linear/graduated/volume pricing and explicit conditional workload scenarios.
- Availability-aware rolling origins, locked development/calibration/final selection, proper scores, all-opportunity denominators, cohort and donor diagnostics, cumulative split-conformal intervals and explicit weighted joint-path arithmetic. Serving does not automatically promote these uncertainty capabilities.
- SQLite immutable artifacts; authenticated WSGI adapter; source-backed context; independent backend finance review, current-authority/stale-evidence checks, exactly-once receipts and frontend reference adapters.

Optional neural/foundation/LLM/session methods, arbitrary distributions, automated safe-transfer recommendations, latent unmet demand, causal savings, native account acquisition and live Factory execution remain explicitly unsupported or evidence-blocked. The [capability and requirement ledger](docs/implementation/requirements-and-capabilities.md) and [all 206 edge records](docs/implementation/edge-ledger.json) preserve exact scope and residual limits.

## Integrate

See [API and schema contracts](docs/implementation/api.md), [consumer wiring](docs/implementation/consumer-contracts.md), [verification evidence](docs/implementation/verification.md), [dependency/license inventory](docs/implementation/dependencies.md) and [implementation plan](docs/implementation/plan.md).

`ForecastApplication` is a thin WSGI boundary. Your backend supplies authentication and a trusted snapshot resolver; HTTP request bodies cannot choose files or grant permissions. A local bearer-authenticated example is included:

```sh
# Set FORECASTING_DEMO_TOKEN privately in your environment first.
PYTHONPATH=src python3 examples/serve.py --config examples/northstar-config.json --store artifacts/service.sqlite --port 8080
```

Routes: `GET /v1/models`, `POST /v1/forecast`, `GET /v1/results/{artifact_id}`. The example binds to loopback and fixes source/tenant scope at startup. It is not production authentication or a deployment.
