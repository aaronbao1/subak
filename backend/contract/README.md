# Backend contract (mock against this)

This folder is the shared handoff between the backend and the frontend / forecasting / agent
workstreams. Everything here is **generated** from the real FastAPI app; do not hand-edit it.

| File | What it is |
|---|---|
| `openapi.json` | OpenAPI 3 spec for every `/api` route (request and response schemas) |
| `fixtures/*.json` | Real responses captured against a freshly seeded Northstar database |
| `fixtures/index.json` | Machine-readable list: name, scenario, schema, method, path, status, description |

All data is the fictional **Northstar Software** example and is **simulated**. Projections come from
a placeholder provider, not a forecasting model.

## Fixture format

```json
{
  "name": "budget_state_initial",
  "scenario": "main",
  "description": "version 1: research 60k, product 80k, engineering 60k; envelope 200k",
  "schema": "BudgetState",
  "request": {"method": "GET", "path": "/api/budget", "headers": {...}, "body": {...}, "query": {...}},
  "status": 200,
  "response": { ...exact JSON the API returned... }
}
```

`request.multipart` replaces `body` for file uploads. Fixtures were captured with a frozen clock
(`2026-10-24T12:00:00Z`, advanced one minute per request) and sequential ids (`prop_000001`,
`doc_000003`, ...). Ids restart in each scenario because each scenario is its own database, so do
not join ids across scenarios.

| Scenario | Story |
|---|---|
| `main` | Seeded reads; signals; outcome A (transfer) approved and replayed; outcome B goes stale; rebase |
| `addition` | Outcome B (+50k addition) approved: 95k/80k/75k, envelope 250k |
| `rejection` | Self-approval blocked, then a second approver rejects: budget unchanged |
| `forecast_unavailable` | Provider in `unavailable` mode: spend/budget still served, projections null |
| `imports` | First import of the billing export, then the identical file again (`duplicate`) |
| `incomplete` | Unmapped account + Codex counter reset: coverage `partial`, `unattributed` bucket |

## Conventions the fixtures rely on

- **Money is a string** with exactly two decimals (`"60000.00"`). Never parse it into a JS float for
  arithmetic; display it or use a decimal library. Requests must send strings too: floats and more
  than two decimals are rejected.
- **Errors** are always `{"error": {"code", "message", "details"}}`. Branch on `code`
  (`stale_proposal`, `self_approval_forbidden`, `role_forbidden`, `validation_failed`,
  `idempotency_key_reused`, `citation_not_found`, ...). `validation_failed` carries
  `details.reasons[] = {code, message, line?, field?}`.
- **Identity** is the demo headers `X-Actor-Id` and `X-Actor-Role` (`finance_approver`,
  `finance_analyst`, `droid_agent`, `importer`). This is not authentication; the authority rules
  are still enforced (Droid can draft but never decide; a requester cannot approve its own request).
- **Decisions** need an `Idempotency-Key` header. Re-sending the same key and body returns the stored
  decision with `replayed: true` (200) and applies nothing twice.
- **Addition vs transfer**: `action_type` is `addition` (envelope grows) or `transfer`
  (`envelope_increase` is `"0.00"`). They are never mixed.
- **Stale proposals**: every proposal carries `base_version`; `is_stale` turns true when the budget
  moved on. Applying one returns 409 `stale_proposal`; `POST /api/proposals/{id}/rebase` re-drafts it.
- **Forecasts** always return 200. Check `availability` (`available | partial | unavailable`);
  when unavailable, `projections` is empty and overview `projected*` fields are `null`, never `0`.
- **Included usage** is never spend: `by_cost_category.included_usage.amount` is `null` and its list
  value is in `included_usage_notional`. `unpriced_tokens` is a token count, not dollars.
- **Coverage** (`complete | partial | missing`) and `data_labels` tell you how far to trust totals.
- **Citations** in signals point at a specific document version with exact offsets;
  `citation_currency: "superseded"` means a newer version exists.

## Mocking against it

Frontend (any stack): serve `fixture.response` with `fixture.status` for the matching
`request.method` + `request.path`. A minimal approach:

```js
import index from "../backend/contract/fixtures/index.json";
// pick the fixture for a screen state, e.g. "overview" or "overview_forecast_unavailable"
const fx = await import(`../backend/contract/fixtures/${name}.json`);
return new Response(JSON.stringify(fx.response), { status: fx.status });
```

Types: generate them from `openapi.json` (for example `npx openapi-typescript
backend/contract/openapi.json -o src/api-types.ts`), or read `schema` in each fixture.

Forecasting: your provider must return the `ForecastResult` shape in `forecast_available.json`
(`provider`, `availability`, `reason`, `target_period`, `basis`, `projections[{team, amount, unit,
assumptions, uncertainty}]`, `value_kind`, `method_label`). Amounts are decimal strings. Implement
`app.providers.forecast.ForecastProvider` (`get_forecast(period_id, team_ids) -> ForecastResult`);
the backend contains timeouts and errors and turns them into `unavailable`.

Live backend instead of mocks:

```bash
cd backend
.venv/bin/python -m app.seed      # seed backend/data/app.db with Northstar (once)
.venv/bin/python -m app.main      # http://127.0.0.1:8787, CORS open to localhost origins
```

## Regenerating

```bash
cd backend
.venv/bin/python -m app.contract.export          # rewrite openapi.json + fixtures
.venv/bin/python -m app.contract.export --check  # exit 1 if the committed contract is out of date
```

`tests/test_contract.py` fails when the committed files drift from what the code produces. A changed
fixture shape is an integration change: tell the frontend owner before merging it.

Agent runs: `agent_run_interpret`, `agent_run_propose_addition`, `agent_run_propose_transfer` and
`agent_runs` are real FakeDroidRunner runs (scenario `agent`); `error_runner_unavailable` is the 503
for `DROID_RUNNER=sdk` without a key. Each run embeds its `steps` and `events`; the same events are
streamed live by `GET /api/agent/runs/{id}/events` (SSE, see `backend/README.md`).
