# Overnight report: backend foundation

Branch `devin/backend-foundation`. Everything lives under `backend/` and `agent/`, plus a root
`README.md`, which did not exist on `main` and contains only a "Workstreams" pointer. Nothing in
`docs/` (Aaron's plans) was touched. The setup and API details are in [`../README.md`](../README.md),
and the full design is in [`design.md`](design.md).

## Summary

- FastAPI + SQLAlchemy 2 + SQLite backend for the Northstar AI-spend workspace. It covers spend
  ingestion, coverage, budgets, proposals, finance decisions, forecasts behind a provider interface,
  corpus search, cited signals, an overview, and Droid agent runs with an SSE activity stream.
- **302 tests pass.** All 12 planted-error checks match the answer key. The contract is up to date.
  A live server on port 8787 answered `/health` and `/api/budget` with 200.
- Droid runs on a deterministic `FakeDroidRunner` by default. The real SDK runner is built but sits
  behind the `DroidRunner` interface. It is never used unless `DROID_RUNNER=sdk` is set and a
  Factory key is in the environment.
- Teammates can mock against `backend/contract/`. It holds the OpenAPI spec and 70 real response
  fixtures.

## What was built (by module)

| Module | Contents |
|---|---|
| `app/core` | `money.py` (Decimal-only money; float binds raise; exactly 2 decimals), `clock.py` (injectable clock and sequential ids), `errors.py` (uniform `{"error": {code, message, details}}`), `actors.py` (demo role headers), `openapi.py` |
| `app/db` | SQLAlchemy models, a `MoneyType` that stores money as a canonical string, and session handling. Tables are created on startup and there are no migrations |
| `app/schemas` | Pydantic v2 request and response models for every route |
| `app/services/parsers` | Northstar billing CSV/JSON parser (simulated format) and Codex session JSONL parser (real format) |
| `app/services` | imports (byte-level and per-record dedupe, conversion of cumulative counters to deltas), coverage (complete/partial/missing, unattributed bucket), spending, budget (versioned state, immutable snapshots), proposals (validation, before/after arithmetic, rebase/revise), decisions (stale-version and idempotency checks, rule that a requester cannot approve their own draft, blocked-attempt log), forecasts, corpus (versioned documents, supersession), signals (quotes checked verbatim against the stored document), overview (each section degrades on its own), teams, agent_runs |
| `app/providers/forecast.py` | `ForecastProvider` interface, `PlaceholderForecastProvider` (the shared Northstar projections, labeled as not a model), and an `unavailable` mode |
| `app/agent` | `DroidRunner` interface, `BackendToolbox` (read + draft tools only, with per-run caps), `FakeDroidRunner`, runner loader, tool definitions |
| `agent/northstar_droid` | `SdkDroidRunner` (lazy SDK import), SDK MCP tools, prompts, generated `tool_manifest.json` |
| `app/api` | Routes for meta, spending, coverage, imports, budget, proposals, decisions, forecasts, documents, signals, teams, agent runs (+ SSE), and admin reset (off by default) |
| `app/seed` + `seed/` | Northstar seed that reproduces the shared table exactly, plus a planted-error pack with `answer_key.md` |
| `app/contract/export.py` | Regenerates `contract/openapi.json` and `contract/fixtures/` from the real app (`--check` mode) |
| `docs/` | `design.md`, `droid-sdk-notes.md`, `edge-cases.md` (each edge case from the plans and judge feedback, with how it is handled or why it is out of scope), this report |

## How to run

```bash
python3 -m venv backend/.venv                 # from the repo root, once
backend/.venv/bin/pip install -e "backend[dev]"
cd backend
.venv/bin/python -m app.seed                  # seed BACKEND_DB_PATH (default backend/data/app.db)
.venv/bin/python -m app.seed --check-planted  # verify the planted-error pack
.venv/bin/python -m app.main                  # http://127.0.0.1:8787  (BACKEND_PORT)
.venv/bin/pytest -q
```

## Test results (2026-10-24)

- `cd backend && .venv/bin/pytest -q`: **302 passed, 1 warning in 13.16s**. The warning is a
  Starlette deprecation notice about `httpx` in `TestClient` and is harmless.
- `python -m app.seed` on a fresh DB: seeded.
- `python -m app.seed --check-planted`: **12/12 planted checks match the answer key**. These cover the
  duplicate import, the cumulative-counter trap, the unmapped project, an approved plan versus an
  informal restatement, a stale approval being refused, and a rebased draft needing fresh review.
- `python -m app.contract.export --check`: contract up to date.
- Seed and end-to-end tests (`test_seed_e2e`, `test_meta_seed`, `test_planted`, `test_spending`):
  14 passed.
- Live smoke test on port 8787: `GET /health` returned `{"status":"ok"}` with 200. `GET /api/budget`
  returned 200 with envelope 200000.00, engineering 60000.00, product 80000.00, research 60000.00,
  and `state_version` 1. The server was then stopped.

## Real vs simulated vs stubbed

| Status | Component |
|---|---|
| **Real** | Authority rules: only `finance_approver` can decide, the requester cannot approve their own draft, and Droid gets 403. Also real: stale-version and idempotency checks, Decimal money handling, import dedupe and de-cumulation, coverage accounting, verbatim quote verification on signals, the Codex session parser (real file format), and the SSE event stream |
| **Simulated** | All Northstar spend, budgets and corpus documents (`value_kind=simulated`, `is_simulated=true`), the Northstar billing export format, and identity (demo `X-Actor-*` headers, not authentication) |
| **Stubbed / placeholder** | Forecasts: `PlaceholderForecastProvider` returns the shared Northstar projections and is not a model; `FORECAST_PROVIDER=unavailable` exercises the degraded path. Droid: `FakeDroidRunner` (deterministic, scripted) is used until `FACTORY_API_KEY` and the Factory SDK are wired in; then `DROID_RUNNER=sdk` switches to `SdkDroidRunner`. The SDK runner exists but has never run against the real service, and it fails loudly (`RunnerUnavailable`) instead of quietly falling back. Every run and event reports `runner_kind` / `source` / `simulated` |

## Open questions for the team

1. **Internal credit unit.** Budgets currently accept only `USD`. Every amount carries a `unit`
   field, so adding an internal credit unit later does not break the contract. We still need to
   decide whether credits exist and how they convert.
2. **Data source.** Spend comes from a simulated Northstar billing export plus real Codex session
   files. Which real billing sources do we want (provider invoices, usage APIs, finance exports),
   and who maps provider projects to teams? Unmapped projects currently land in an unattributed
   bucket.
3. **Forecast cadence.** How often should projections refresh (per import, daily, per planning
   cycle), and for what horizon? There is one period today, `2026-P1` (2026-10-01..2026-12-31). The
   forecasting workstream plugs in by implementing `ForecastProvider`.
4. Factory key handoff. Who provides `FACTORY_API_KEY`, and should real Droid runs be gated beyond
   the finance roles?

## For teammates

- **Frontend / forecasting / agent:** mock against [`../contract/`](../contract/README.md).
  `openapi.json` is the spec. `fixtures/*.json` are real captured responses, indexed in
  `fixtures/index.json`. They are generated with a frozen clock and sequential ids, so do not
  hand-edit them. Regenerate with `.venv/bin/python -m app.contract.export`.
- Money arrives as JSON strings (`"60000.00"`). Branch on `error.code`. Read `period` and `unit`
  from responses instead of hard-coding them. Use `simulated` / `runner_kind` to label demo data
  honestly.
- CORS allows any `localhost` / `127.0.0.1` port, so frontend dev servers work without changes.
- The forecasting workstream implements `ForecastProvider` in `app/providers/forecast.py` and needs
  no route changes.
