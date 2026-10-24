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
.venv/bin/python -m app.main          # serves http://127.0.0.1:8787
# or, with reload:
.venv/bin/uvicorn app.main:create_app --factory --port 8787 --reload
```

Health check: `curl http://127.0.0.1:8787/health` (also `/api/health`).

## Test

```bash
cd backend
.venv/bin/pytest -q
```

Every test uses its own temporary SQLite file, a frozen clock, and sequential ids.

## Configuration (environment variables)

| Variable | Default | Meaning |
|---|---|---|
| `BACKEND_DB_PATH` | `backend/data/app.db` | SQLite file (directory is created; `data/` is gitignored) |
| `BACKEND_PORT` | `8787` | Port used by `python -m app.main` |
| `BACKEND_CORS_ORIGIN_REGEX` | localhost / 127.0.0.1, any port | Allowed browser origins; credentials are never allowed |
| `FORECAST_PROVIDER` | `placeholder` | `placeholder` (shared Northstar projections, not a model) or `unavailable` |
| `DROID_RUNNER` | `fake` | `fake` (deterministic, no credentials) or `sdk` (requires a Factory key in the environment; no silent fallback) |
| `BACKEND_ALLOW_RESET` | off | `1` enables `POST /api/admin/reset` for demos |

No credentials are stored in this repo or requested by the backend. The Factory SDK reads its own
key from the environment only when `DROID_RUNNER=sdk`.

## Conventions

- Money is `decimal.Decimal`, two decimal places, never float. On the wire it is a JSON string
  (`"60000.00"`); in SQLite it is stored as a canonical string. Binding a float raises `TypeError`.
- Every error response is `{"error": {"code", "message", "details"}}`.
- All timestamps are timezone-aware UTC.

## Real vs simulated

| Component | Status |
|---|---|
| Northstar spend, budgets, corpus | simulated (`value_kind=simulated`, `is_simulated=true`) |
| Codex session parser | real format; real samples import as `measured` tokens, `unpriced_usage` unless priced |
| Projections | placeholder, not a model; `unavailable` mode available |
| Droid | `FakeDroidRunner` (deterministic) until a Factory key exists; `runner_kind` always reported |
| Identity | demo headers, not authentication; authority rules themselves are enforced |
