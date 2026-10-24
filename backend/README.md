# Northstar backend

FastAPI + SQLite backend for the Northstar AI-spend planning workspace. Design:
[`docs/design.md`](docs/design.md). Droid SDK notes: [`docs/droid-sdk-notes.md`](docs/droid-sdk-notes.md).
Product plans live in the repo-level `docs/` folder and are authoritative.

This workstream only touches `backend/` and `agent/`. No UI code, no forecasting models.

## Setup

Python 3.12+ (developed on 3.13). From the repo root:

```bash
python3 -m venv backend/.venv
backend/.venv/bin/pip install -e "backend[dev]"
```

## Run

```bash
cd backend
.venv/bin/python -m app.seed          # seed the Northstar example into BACKEND_DB_PATH (no-op if seeded)
.venv/bin/python -m app.seed --check-planted   # verify the planted-error pack against seed/answer_key.md
.venv/bin/python -m app.main          # serves http://127.0.0.1:8787
# or, with reload:
.venv/bin/uvicorn app.main:create_app --factory --port 8787 --reload
```

Health check: `curl http://127.0.0.1:8787/health` (also `/api/health`).

There are no migrations: tables are created on startup. After pulling a schema change, delete
`backend/data/app.db` (or your `BACKEND_DB_PATH`) and re-run `python -m app.seed`.

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
| `FORECAST_PROVIDER` | `placeholder` | `placeholder` (shared Northstar projections, not a model) or `unavailable` |
| `DROID_RUNNER` | `fake` | `fake` (deterministic, no credentials) or `sdk` (requires a Factory key in the environment; no silent fallback) |
| `DROID_EXECUTABLE`, `DROID_MODEL`, `DROID_TIMEOUT_S` | `droid` on PATH, user default, `120` | SDK runner only |
| `BACKEND_ALLOW_RESET` | off | `1` enables `POST /api/admin/reset` for demos |
| `BACKEND_COMPAT` | on | `0` unmounts the frontend compat layer under `/compat/api` (see below) |

No credentials are stored in this repo or requested by the backend. The Factory SDK reads its own
key from the environment only when `DROID_RUNNER=sdk`.

## Conventions

- Money is `decimal.Decimal`, two decimal places, never float. On the wire it is a JSON string
  (`"60000.00"`); in SQLite it is stored as a canonical string. Binding a float raises `TypeError`.
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
| `GET /api/spend/summary`, `GET /api/spend/records` | team/company spend by cost category and value kind, coverage, drill-down |
| `GET /api/coverage` | completeness per team, unattributed bucket, contributing batches |
| `GET /api/budget`, `GET /api/budget/history` | current allocations + version, immutable snapshots |
| `GET /api/forecasts`, `POST /api/forecasts/snapshots` | ForecastProvider result (200 even when unavailable), citable snapshot |
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

## Frontend compat layer

The Next.js app's `HttpDataClient` works against this backend with no frontend changes:
`NEXT_PUBLIC_API_URL=http://localhost:8787/compat`. `app/compat/` serves its 15 paths under
`/compat/api/*` in the exact TypeScript shapes (camelCase, money as numbers, errors as
`{"error": "<plain English>"}`) by translating the services above; decisions still go through the real
decision service. Not part of `openapi.json`. Mapping, gaps and open questions:
[`docs/frontend-alignment.md`](docs/frontend-alignment.md).

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
| Northstar spend, budgets, corpus | simulated (`value_kind=simulated`, `is_simulated=true`) |
| Codex session parser | real format; real samples import as `measured` tokens, `unpriced_usage` unless priced |
| Projections | placeholder, not a model; `unavailable` mode available |
| Droid | `FakeDroidRunner` (deterministic) until a Factory key exists; `runner_kind` always reported |
| Identity | demo headers, not authentication; authority rules themselves are enforced |
