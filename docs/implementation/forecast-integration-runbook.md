# Forecast integration runbook

Use the repository-root [setup commands](../../README.md#run-the-integrated-demo) to install the numerical package and backend into the same Python 3.12 environment. The default backend provider is `engine`; `FORECAST_DEMO=1` opts into synthetic data. Default repository mode uses existing records and leaves unsupported coverage/exposure unknown.

## Execute the acceptance journey

```sh
PYTHONPATH=src:backend:agent .venv/bin/python -m app.forecasting.demo \
  --output-dir artifacts/northstar-integration
```

The output directory must be fresh. The command uses real FastAPI routes, SQLite persistence, and the numerical worker in process. It writes an independently observed 84-day Northstar history, seven connector-shaped events, initial and refreshed forecasts, source/calculation explanations, a Droid response, an isolated scenario, mature truth, error receipts, learning scores, and `report.json`. IDs are newly generated on each run; fixture inputs and numerical behavior are deterministic.

The checks cover coherent shared partitions; seven days/four weeks; automatic extraction; context-only release/ambiguity; unchanged publication while evidence queues; changed immutable publication; matching Droid citations; scenario isolation; mature scoring and next fit; persisted error receipts; synthetic promotion rejection; and actuals separate from issued forecasts.

Append `--serve` to run the same database on port 8787 after the journey. The served demo clock is frozen at November 2, 2026; `--port` chooses another port. Refreshes and pending jobs run through the worker. Restart with the normal app command only when intentionally switching to the system clock and its availability semantics. Browser checks are documented [separately](forecast-browser-journey.md).

## Run against repository records

```sh
PYTHONPATH=src:backend:agent .venv/bin/python -m app.seed
PYTHONPATH=src:backend:agent FORECAST_PROVIDER=engine .venv/bin/python -m app.main
```

`BACKEND_DB_PATH` selects the SQLite file. `FORECAST_WORKER=0` disables automatic scheduling and processing for controlled tests. `FORECAST_PROVIDER=placeholder` retains the explicit older simulated provider; `unavailable` retains unavailable behavior. The engine never silently falls back to synthetic observations.

The old seed contains reported monetary records, not a complete daily usage/exposure ledger. Its charges appear as recorded amounts, while unsupported future totals remain incomplete. Supply versioned normalized usage, required-source completion records, identity/exposure records, and supported pricing for a complete usage-derived forecast.

```sh
curl -X POST http://localhost:8787/api/forecast-refreshes \
  -H 'Idempotency-Key: finance-manual-001'
curl http://localhost:8787/api/forecast-refreshes/JOB_ID
curl http://localhost:8787/api/forecast-views
curl 'http://localhost:8787/api/forecast-runs/RUN_ID/explanation?scope_type=team&scope_id=research'
```

Replay the same idempotency key to retrieve the same job. Retryable jobs resume after their delay or an expired lease; inspect attempts and error before creating a distinct manual request. Do not edit stored snapshots or publication rows. Save the database and its WAL consistently before operational changes.

## Ingest supported evidence and inspect a scenario

`connector-events.json` from the demo contains Slack, Asana, Monday, and model-release envelopes. Post each complete object to `/api/forecast-evidence` with JSON content type. The result may include a completed interpretation or a durable pending receipt. Queued eligible drivers affect the next publication only. Context-only entries expose their reasons.

For an omission scenario, take the **same run's company view** `included_drivers`, remove the selected driver, and send the remaining complete set as `{"drivers":[...]}` to `/api/forecast-runs/RUN_ID/scenarios`. Sending only a team's subset would remove unrelated drivers. Pending responses contain a job and scenario ID; poll the job, then retrieve the scenario. The dashboard handles these states and preserves the issued curve on failure.

Use `DROID_RUNNER=sdk` with the established Factory setup in [agent/README](../../agent/README.md) for a live SDK request. The integrated acceptance journey uses the deterministic runner and stored calculation tools; it does not prove live SDK availability.

## Learning and recovery

Mature outcomes enter as versioned `truth_revisions` for exact issued target IDs, units, basis, and periods. Each refresh records new error or withdrawal receipts and refits observed rates. See the [truth schema and scoring policy](../learning/README.md). Production integrations must derive truth from actual observations, never forecast values.

Canonical tables migrate idempotently on startup; legacy finance tables retain their existing creation mechanism. Worker claims are leased, and publication is fenced by cutoff and sequence. An expired worker cannot complete a replacement claim. Reset is a destructive demo operation, disabled by default; it is not a production migration strategy.

Run the full verification commands in the README after code changes. Regenerate OpenAPI and fixtures with `PYTHONPATH=src:backend:agent .venv/bin/python -m app.contract.export` when contracts change. Keep historical evaluation and synthetic/genuine evidence distinct.
