# Northstar backend

FastAPI + SQLite backend for the Northstar AI-spend planning workspace.

- **Start here:** [`docs/morning-runbook.md`](docs/morning-runbook.md). It covers running with the real
  Droid, the demo journey, evals, pointing the frontend at `/compat`, and the 60-second judge explanation.
  To run with the UI, see [Run the backend with the frontend](#run-the-backend-with-the-frontend).
- Droid integration (tools, bounds, live results): [`../agent/README.md`](../agent/README.md)
- Design: [`docs/design.md`](docs/design.md). Droid SDK notes: [`docs/droid-sdk-notes.md`](docs/droid-sdk-notes.md).
  Live Droid runs: [`docs/droid-live-log.md`](docs/droid-live-log.md). Evals: [`evals/README.md`](evals/README.md).
- Frontend mapping: [`docs/frontend-alignment.md`](docs/frontend-alignment.md). Edge cases:
  [`docs/edge-cases.md`](docs/edge-cases.md). Overnight report: [`docs/overnight-report.md`](docs/overnight-report.md).
Product plans live in the repo-level `docs/` folder and are authoritative.

The backend calls the numerical package directly and serves the dashboard and Droid forecast tools.
Start the connected forecast demo with the [integration runbook](../docs/implementation/forecast-integration-runbook.md).

## Setup

Use Python 3.12 for the integrated numerical runtime and its pinned model dependencies.
The backend alone supports Python 3.12+. From the repo root:

```bash
python3.12 -m venv backend/.venv
backend/.venv/bin/pip install -e '.[models,test]' -e './backend[dev]'
```

## Run

```bash
cd backend
.venv/bin/python -m app.seed          # seed the Northstar example into BACKEND_DB_PATH (no-op if seeded),
                                      # then interpret the corpus once with the stand-in (signals: droid_fake)
.venv/bin/python -m app.seed --no-signals     # seed without context signals
.venv/bin/python -m app.seed --live-signals   # interpret with the real Droid instead (needs the DROID_RUNNER=sdk
                                      # requirements; exits 2 before touching the DB if any is missing)
.venv/bin/python -m app.seed --check-planted   # verify the planted-error pack against seed/answer_key.md
.venv/bin/python -m app.main          # serves http://127.0.0.1:8787
.venv/bin/python -m app.demo          # walk the demo journey against the running server (3 Droid runs)
# or, with reload:
.venv/bin/uvicorn app.main:create_app --factory --port 8787 --reload
```

Health check: `curl http://127.0.0.1:8787/health` (also `/api/health`).

Canonical forecasting tables use versioned, idempotent SQLite migrations on startup.
Legacy finance tables are checked for missing columns; startup refuses an outdated native
schema with a `SchemaOutdated` message. Preserve and back up databases containing evidence,
forecast history, or decisions before a reviewed native-schema upgrade. The explicitly enabled
admin reset is a separate destructive operation for disposable demo databases, and recreates
both finance and canonical forecasting tables before reseeding and stand-in interpretation.

## Test

```bash
cd backend
.venv/bin/pytest -q
```

Every test uses its own temporary SQLite file, a frozen clock, and sequential ids.

Droid scenario evals (answer key, fake and live runners, live-run cap): see [`evals/README.md`](evals/README.md).
`.venv/bin/python -m evals.run --runner fake` scores every scenario in a few seconds.

## Configuration (environment variables)

| Variable | Default | Meaning |
|---|---|---|
| `BACKEND_DB_PATH` | `backend/data/app.db` | SQLite file (directory is created; `data/` is gitignored) |
| `BACKEND_PORT` | `8787` | Port used by `python -m app.main` |
| `BACKEND_CORS_ORIGIN_REGEX` | localhost / 127.0.0.1, any port | Allowed browser origins; credentials are never allowed |
| `FORECAST_PROVIDER` | `engine` | Numerical `engine`, explicit simulated `placeholder`, or `unavailable` |
| `FORECAST_DEMO` | off | `1` opts into deterministic synthetic usage/exposure/pricing fixtures |
| `FORECAST_WORKER` | on | `0` disables scheduled and background processing for controlled tests |
| `DROID_RUNNER` | `fake` | `fake` (deterministic, no credentials) or `sdk` (requires a Factory key in the environment; no silent fallback) |
| `DROID_EXECUTABLE`, `DROID_MODEL`, `DROID_TIMEOUT_S` | `droid` on PATH, user default, `120` | SDK runner only |
| `DROID_CHAT_MODEL`, `DROID_CHAT_REASONING_EFFORT` | `DROID_MODEL`, SDK default | SDK runner only: model and reasoning effort (`none`, `dynamic`, `off`, `minimal`, `low`, `medium`, `high`, `xhigh`, `max`) for chat tasks (`answer_question`, `propose_allocation`); corpus interpretation keeps `DROID_MODEL`. `low` is a good demo setting |
| `BACKEND_ALLOW_RESET` | off | `1` enables `POST /api/admin/reset` for demos (reseeds and reruns the stand-in interpretation) |
| `BACKEND_COMPANY_ID`, `BACKEND_COMPANY_NAME` | unset | Override the company shown by `/api/meta` and `/compat/api/company`. Otherwise the `company_profile` row (written by `python -m app.seed` or `datagen/load_backend.py`) is used, then the Northstar default |
| `BACKEND_COMPAT` | on | `0` unmounts the frontend compat layer under `/compat/api` (see below) |
| `NEXT_PUBLIC_API_URL` (frontend, in `frontend/.env.local`) | unset (mock data) | `http://localhost:8787/compat` points the UI at this backend |
| `NEXT_PUBLIC_LIVE_REFRESH_MS` (frontend) | unset (no polling) | Re-fetch interval for live data; the frontend enforces at least 2000 |

No credentials are stored in this repo or requested by the backend. The Factory SDK reads its own
key from the environment only when `DROID_RUNNER=sdk`.

## Conventions

- Legacy financial ledger money is `decimal.Decimal`, two decimal places, never float. On the wire it is a JSON string
  (`"60000.00"`); in SQLite it is stored as a canonical string. Binding a float raises `TypeError`.
- Canonical forecast views expose finite numeric estimates with declared units and basis; supported
  commercial calculations price full pools before summaries. Compatibility adapters round only at
  the legacy ledger boundary.
- Every error response is `{"error": {"code", "message", "details"}}`.
- All timestamps are timezone-aware UTC.

## Ingestion

```bash
# simulated Northstar billing export (CSV or JSON)
curl -F source_kind=northstar_billing -F file=@export.csv \
     -H 'X-Actor-Id: imp-1' -H 'X-Actor-Role: importer' http://127.0.0.1:8787/api/imports
# real Codex session telemetry; account is stated by the uploader, never inferred
curl -F source_kind=codex_sessions -F source_account=codex-research-laptops -F file=@rollout.jsonl \
     -H 'X-Actor-Id: imp-1' -H 'X-Actor-Role: importer' http://127.0.0.1:8787/api/imports
curl http://127.0.0.1:8787/api/coverage
curl 'http://127.0.0.1:8787/api/documents?q=model-evaluation&include_superseded=false'
```

Re-posting identical bytes returns `status: "duplicate"` and adds nothing; overlapping files are
deduplicated per record key; cumulative token counters are converted to deltas. See design §11.

## API

All routes are under `/api`; the full spec is [`contract/openapi.json`](contract/openapi.json) and
example responses are in [`contract/fixtures/`](contract/fixtures/) (see
[`contract/README.md`](contract/README.md) for mocking). Main read routes:

| Route | Returns |
|---|---|
| `GET /api/meta` | period, unit, runner/provider modes, real-vs-simulated labels |
| `GET /api/spend/summary`, `GET /api/spend/records` | team/company spend by cost category and value kind, coverage, drill-down (records carry `person`; filter `?person=`) |
| `GET /api/people`, `GET /api/people/{id}` | people directory (`?team=`); spend is attributed to a person only via a known email on the mapped team |
| `GET /api/coverage` | completeness per team, unattributed bucket, contributing batches |
| `GET /api/budget`, `GET /api/budget/history` | current allocations + version, immutable snapshots |
| `GET /api/forecasts`, `POST /api/forecasts/snapshots` | ForecastProvider result (200 even when unavailable), citable snapshot |
| `GET /api/forecast-views`, `POST /api/forecast-refreshes` | Immutable scoped views/current actuals; idempotent manual job |
| `GET /api/forecast-refreshes/{id}` | Durable job status and failure |
| `GET /api/forecast-runs/{id}/explanation`, `POST /api/forecast-runs/{id}/scenarios` | Stored source/calculation chain; isolated what-if job |
| `GET /api/forecast-scenarios/{id}`, `GET/POST /api/forecast-evidence` | Scenario receipt; included/queued/context-only evidence and ingestion |
| `GET /api/overview` | spend + budget + forecast; each section degrades independently |
| `GET /api/documents[?q=]`, `GET /api/documents/{id}`, `.../by-key/{key}/versions` | corpus search/read |
| `GET/POST /api/signals`, `GET/PATCH/DELETE /api/signals/{id}` | context signals with verified citations |
| `POST /api/proposals`, `.../{id}/decision`, `.../rebase`, `.../revise` | drafting and finance decisions |
| `GET /api/decisions`, `GET /api/decision-events` | decision history and blocked attempts |
| `POST /api/agent/runs`, `GET /api/agent/runs[/{id}]` | start a Droid task (finance roles), run output + step log + events |
| `GET /api/agent/runs/{id}/events` | SSE activity stream (tool called, evidence found, proposal drafted, ...) |
| `GET /api/agent/tools` | the exact tools Droid gets (read + draft only) |

Regenerate the contract after any schema or seed change:
`.venv/bin/python -m app.contract.export` (`--check` to verify; `tests/test_contract.py` enforces it).

## Run the backend with the frontend

The Next.js app in `../frontend/` uses its in-memory mock unless `NEXT_PUBLIC_API_URL` is set. With it
set, its `HttpDataClient` talks to this backend's compat layer with no frontend code changes.

```bash
# terminal 1: backend (from backend/)
rm -f data/app.db                         # only after pulling a schema change
.venv/bin/python -m app.seed              # 15 people, daily per-person spend, 13 documents,
                                          # then 12 context signals by the stand-in (droid_fake)
.venv/bin/python -m app.main              # http://127.0.0.1:8787

# terminal 2: frontend (from the repo root)
echo 'NEXT_PUBLIC_API_URL=http://localhost:8787/compat' > frontend/.env.local
cd frontend && npm install && npm run dev # http://localhost:3000
```

- Check: `curl -s http://127.0.0.1:8787/compat/api/company` and `.../compat/api/people`.
- The UI loads 10 GETs at once and renders nothing if any of them fails. On a seeded DB all return 200.
  On an unseeded DB only `/company` fails, with 503 "The database is not seeded yet; run
  `python -m app.seed`."
- Seed flags: default = stand-in signals so context cards show on first load; `--no-signals` = no
  signals (cards stay empty until a chat asks "what changed in the documents?"); `--live-signals` = the
  real Droid interprets the corpus (needs the `DROID_RUNNER=sdk` requirements; refuses before touching
  the DB if they are missing, never falls back to the stand-in). Signals are only interpreted on a fresh
  seed; delete the DB or use `POST /api/admin/reset` (`BACKEND_ALLOW_RESET=1`) to redo it.
- `DROID_RUNNER=fake` (default): chat replies are deterministic and instant, need no credentials, and
  end with a "Simulated: ..." line. `DROID_RUNNER=sdk`: chat runs the real Factory Droid with the key from
  your environment. A reply waits for the whole run (one synchronous POST; up to `DROID_TIMEOUT_S`).
  For a faster demo set `DROID_CHAT_REASONING_EFFORT=low` (and optionally `DROID_CHAT_MODEL`); proposals
  reuse the signals recorded at seed time instead of re-reading the corpus.
- Apply and Reject/Dismiss act as the demo approver `dashboard-approver` (shown as "Finance approver
  (demo)"); chat runs as `dashboard-analyst`, so self-approval is still blocked. Dismissing a stale
  proposal records a rejected decision and leaves budgets unchanged.

## Run on the Uber dataset

The simulated "Uber (simulated)" company from `../datagen/` (16 teams, 130 people, ~331k usage
records Q1-Q4 2026, 249 corpus documents; Q4 current, as-of 2026-10-24). Everything below uses the
fake runner unless you set `DROID_RUNNER=sdk` yourself.

```bash
# one command (from the repo root): generate if needed, load once into backend/data/uber.db, start the
# backend (default FORECAST_PROVIDER=engine) with the Uber company name, stream live usage
datagen/demo.sh                               # --interval 1 --speed 100 for a faster feed

# or by hand
python3 datagen/generate.py --quiet           # writes datagen/out/ (gitignored)
backend/.venv/bin/python datagen/load_backend.py --db backend/data/uber.db --reset   # ~45 s
cd backend && PYTHONPATH=../src:.:../agent BACKEND_DB_PATH=data/uber.db .venv/bin/python -m app.main
```

- **Company.** The loader writes a `company_profile` row, so `/compat/api/company` says "Uber
  (simulated)" without env vars. `BACKEND_COMPANY_ID` / `BACKEND_COMPANY_NAME` (set by `demo.sh`) win
  over the row; Northstar is the default when neither exists.
- **Forecasts** (default `FORECAST_PROVIDER=engine`). The numerical engine from the repo-root
  `src/forecasting` package (install and `PYTHONPATH` as in Setup) publishes immutable runs; read paths
  never recompute. No load step publishes: the worker queues the current week's job on its first poll
  after startup, or request one by hand and poll it:

  ```bash
  curl -X POST http://127.0.0.1:8787/api/forecast-refreshes -H 'Idempotency-Key: uber-1'
  curl http://127.0.0.1:8787/api/forecast-refreshes/<id>
  ```

  Repository usage carries no exposure or complete pricing pool, so team totals can stay qualified and
  `/compat/api/forecasts` can report a team as unavailable; that is the honest result, not a bug.
  Startup captures all current repository rows for the forecast store, which takes longer on ~331k rows.
  Details: [`../docs/implementation/forecast-integration-runbook.md`](../docs/implementation/forecast-integration-runbook.md).
- **Live interpretation of the corpus** (`python -m app.interpret`). Selects the period-relevant
  documents, runs one scoped `interpret_corpus` Droid run per batch, and stops before the credit cap:

  ```bash
  cd backend
  BACKEND_DB_PATH=data/uber.db .venv/bin/python -m app.interpret --since 2026-09-01 --include-announced \
      --batch 10 --credit-cap 600000 --dry-run    # print the selection and batch plan only
  BACKEND_DB_PATH=data/uber.db .venv/bin/python -m app.interpret --since 2026-09-01 --include-announced \
      --batch 10 --credit-cap 600000              # DROID_RUNNER=sdk for the real Droid
  ```

  Selection: current documents authored on or after `--since`, plus (with `--include-announced`) earlier
  documents whose effective window overlaps the current period: 64 documents in 8 batches on the default
  dataset. Message/task pairs stay in the same batch. The cap sums provider-reported `factory_credits`,
  including earlier interpret-cli runs in the same database (`--ignore-prior-spend` opts out). It stops
  before a batch that could exceed the cap and hands each batch the remaining cap as its credit budget,
  which the sdk runner enforces on the provider's streamed usage. So the cap holds to within one usage
  update, not exactly. An sdk batch that reports no or partial credits also stops the run. 8 batches can
  cost more than 600k: use a larger cap to cover them all in one go.
  Re-running skips documents already interpreted by the same runner kind (`--force` re-runs). sdk
  batches append to `data/live_runs.log`. With `DROID_RUNNER=sdk` and the SDK or key unavailable it exits
  2 and runs nothing; there is no fallback to the stand-in. The fake runner is scripted for Northstar and
  records **no** signals for Uber documents (the CLI header says so) so a fake run never looks like an
  interpretation. Exit codes: 0 done (also when stopped at the cap), 1 a batch failed, 2 runner unavailable
  or bad input. Notes and the selection rule: [`docs/uber-interpret-notes.md`](docs/uber-interpret-notes.md).
- **Live refresh in the UI.** In `frontend/.env.local` set `NEXT_PUBLIC_API_URL=http://localhost:8787/compat`
  and `NEXT_PUBLIC_LIVE_REFRESH_MS=1000`. The frontend currently clamps the interval to at least 2 s
  (`frontend/src/components/shell/app-shell.tsx`); the backend is built to answer every 1 s. Responses are
  gzipped, and `/compat/api/spending` and `/people` keep their rendered JSON keyed by a data
  stamp (write generation + latest usage row id) plus query parameters, so an unchanged poll is a cache hit
  ([`app/compat/cache.py`](app/compat/cache.py)).

Measured on the default dataset (331,731 records, in-process TestClient, fake runner, 2026-10-25; forecast
reads are served from the engine's stored publication and are not response-cached here):

| Request | First call | Warm (cached) |
|---|---|---|
| `GET /compat/api/spending` (~3 MB JSON before gzip) | 358 ms | 4 ms |
| `GET /compat/api/people` | 7 ms | 2 ms |

After a live import the next spending read rebuilds once (~0.4-0.8 s), then is cached again.

## Frontend compat layer

`app/compat/` serves the app's 16 paths (including `GET /api/people`) under `/compat/api/*` in the
exact TypeScript shapes of `frontend/src/lib/contracts/index.ts` (camelCase, money as numbers, person
and company context, per-person spend and forecasts with daily points, errors as
`{"error": "<plain English>"}`) by translating the services above; decisions still go through the real
decision service. Not part of `openapi.json`. Mapping, closed and remaining gaps:
[`docs/frontend-alignment.md`](docs/frontend-alignment.md). Build details:
[`docs/frontend-integration-design.md`](docs/frontend-integration-design.md).

## Droid agent runs

Droid interprets the corpus into cited signals and drafts proposals through a scoped toolbox; it cannot
apply anything. See [`../agent/README.md`](../agent/README.md) for the runtime design.

```bash
H='-H X-Actor-Id:fin-ana -H X-Actor-Role:finance_analyst -H Content-Type:application/json'
# run to completion (201) - default
curl $H -d '{"task_type":"interpret_corpus"}' http://127.0.0.1:8787/api/agent/runs
# start in the background (202) and follow live activity over SSE
curl $H -d '{"task_type":"propose_allocation","params":{"mode":"addition","amount":"50000.00","prioritize":"research"},"wait":false}' \
     http://127.0.0.1:8787/api/agent/runs
curl -N http://127.0.0.1:8787/api/agent/runs/<run id>/events
```

Task types: `interpret_corpus`, `propose_allocation` (`params.mode` `addition` | `transfer`, `amount`,
`prioritize`), `answer_question`. Stale-proposal recovery: after a decision returns 409 `stale_proposal`,
start `propose_allocation` with `params: {"stale_proposal_id": "<id>"}` (nothing else). Droid calls
`rebase_proposal`, explains what changed since the proposal's base version (per-team changes and the
decisions that moved the budget) and leaves a NEW `pending_review` draft (`rebased_from_proposal_id`)
that needs a fresh finance review; if the same lines no longer fit, it says why and drafts nothing. SSE frames are `id: <seq>`, `event: <type>`, `data: <json>`; event
types: `run_started`, `tool_call`, `tool_result`, `evidence_found`, `supersession_detected`,
`conflict_detected`, `signal_recorded`, `proposal_drafted`, `assistant_text`, `warning`, `error`,
`run_finished`. The stream replays stored events, follows a running run, and ends after
`run_finished`; reconnect with `Last-Event-ID` or `?after=<seq>`. In the browser use `EventSource`.
Every event carries `source` (`fake_runner` | `droid_sdk` | `backend`) and every run `runner_kind` and
`simulated`, so the UI can label simulated activity honestly.

## Seed, planted errors and edge cases

The default seed reproduces the shared Northstar table exactly. A separate planted-error pack in
[`seed/`](seed/README.md) contains a duplicate import, a cumulative-counter trap, an unmapped provider
project, a proposal on outdated budgets, and conflicting documents. Each one has an
[answer key](seed/answer_key.md) that `--check-planted` and `tests/test_planted.py` verify.
`--with-planted` loads the data traps into your DB for a demo. Every edge case from the plans and the
judge feedback, and how it is handled or why it is out of scope, is listed in
[`docs/edge-cases.md`](docs/edge-cases.md).

## Real vs simulated

| Component | Status |
|---|---|
| Northstar spend, budgets, corpus, people | simulated (`value_kind=simulated`, `is_simulated=true`); 15 fictional people with `@northstar.example` emails |
| Per-person projections | proportional split of the team placeholder by spend to date, not a person-level model |
| Codex session parser | real format; real samples import as `measured` tokens, `unpriced_usage` unless priced |
| Projections | `engine` (default): numerical engine publications from the `src/forecasting` package; `placeholder`: shared simulated projections, not a model; `unavailable` mode available |
| Uber dataset | simulated by `datagen/` ("Uber (simulated)"); not Uber data |
| Droid | `FakeDroidRunner` (deterministic) by default; `DROID_RUNNER=sdk` runs real Factory Droid (live-verified 2026-10-24); `runner_kind` always reported |
| Identity | demo headers, not authentication; authority rules themselves are enforced |
