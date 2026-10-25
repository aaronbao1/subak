# AI Spend Planner

A finance workspace for understanding AI spending, forecasting team needs, and planning internal budgets. Built for Cal Hacks 13.0 with FastAPI, SQLite, Next.js, Recharts, and the Factory Droid SDK.

The numerical engine is connected to the backend, dashboard, and Droid tools. It publishes immutable forecasts every Monday at 00:00 UTC and on manual refresh. New evidence queues between publications. Company, team, person, and shared views expose seven daily points, four calendar weeks, a cumulative spending fan, and a separate conditional quarter-end outlook.

The executable **Northstar Software** fixture demonstrates ingestion, automatic supported driver extraction, publication, cited explanations, isolated scenarios, and learning from mature observed outcomes. Its history, connector events, prices, and outcomes are synthetic. Live authenticated company connectors remain subsequent work.

## Run the integrated demo

Use Python 3.12 and Node.js 20.9 or newer. From the repository root:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -e '.[models,test]' -e './backend[dev]'
PYTHONPATH=src:backend:agent .venv/bin/python -m app.forecasting.demo \
  --output-dir artifacts/northstar-integration --serve
```

Use a fresh output directory. The command executes the acceptance journey, saves its evidence and SQLite database, then serves that database at `http://127.0.0.1:8787` with a frozen demo clock. Omit `--serve` for an entirely in-process API demonstration that needs no listening socket or API key. The default Droid runner is deterministic; the SDK wrapper exposes the same stored forecast tools.

In another terminal:

```sh
cd frontend
npm ci
NEXT_PUBLIC_API_URL=http://localhost:8787/compat npm run dev
```

Open [localhost:3000](http://localhost:3000). With no `NEXT_PUBLIC_API_URL`, the frontend uses its separately labeled in-memory mock client. See the [runbook](docs/implementation/forecast-integration-runbook.md) and [browser journey](docs/implementation/forecast-browser-journey.md) for the exact publication, evidence, and scenario flows.

## How forecasts work

Supported project schedules, membership changes, explicit workloads, model adoption, and prices become scoped, effective-dated numerical drivers with source citations. Model releases alone stay context. Ambiguous identities, incompatible units, conflicts, and unsupported magnitudes remain visible without an invented adjustment.

Rates use observed usage and exposure over 56 complete days. Every scenario is aggregated from the same daily paths and priced at the complete billing-pool level before monetary summaries. Explicit shared amounts remain shared. Unknown source days, late charges, or unsupported pricing produce incomplete totals rather than zeros.

The shaded **scenario range** describes evaluated low/base/high configurations. **Historical-error intervals** are separate, optional outputs from matching mature issued errors. They are unavailable without enough evidence. Quarter-end continuation is conditional; it is never labeled as a calibrated full-quarter forecast.

Each refresh refits observed parameters and archives the final priced serving, shadow, and seasonal-naive predictions. Corrections append truth and error revisions. Automatic model replacement requires genuine reconstructible company data, a frozen procedure, 20 calibration weeks, and 12 prospective comparison weeks under the [learning policy](docs/learning/README.md). Synthetic fixtures cannot authorize promotion.

## Repository components

| Component | Role |
| --- | --- |
| [Frontend](frontend/) | Company/team/person forecast panels, cumulative fan, weekly details, evidence drawer, exact-run Ask Droid, manual refresh, and isolated scenario previews |
| [Numerical package](src/forecasting/) | Daily planning paths, structured rates, pricing, uncertainty, immutable scoring, replay, and model governance |
| [Backend](backend/README.md) | Repository inputs, versioned evidence, SQLite jobs/migrations, publication, spending, budgets, proposals, and stale-dependency checks |
| [Droid](agent/README.md) | Shared tools and SDK wrappers for explanations, comparisons, scenarios, and refresh requests |
| [Architecture](docs/implementation/forecast-integration.md) | Data contracts, publication timing, evidence chain, and API boundaries |
| [Verification and limits](docs/implementation/forecast-integration-limits.md) | Executed checks and remaining integration/empirical limits |
| [Architecture audit](docs/implementation/forecast-architecture-audit.md) | Producer/consumer checks, fixes, actual frontend/API journey and rendering evidence |

Allocations are internal planning records. They do not transfer vendor credits, purchase compute, or change provider limits. Financial approval still uses the existing authority, budget-version, and dependency checks. New material evidence can stale a proposal immediately while its referenced forecast remains immutable.

## Verify and reproduce

```sh
PYTHONPATH=src:backend:agent .venv/bin/python -m pytest tests backend/tests -q
PYTHONPATH=src:backend:agent .venv/bin/python -m app.contract.export --check
PYTHONPATH=src:backend .venv/bin/python -m forecasting.replay_report \
  --output artifacts/northstar-replay.json
node --test frontend/src/components/dashboard/*test.mjs frontend/src/components/person/*test.mjs frontend/src/lib/data/*test.mjs frontend/src/lib/store.test.mjs
FORECAST_TEST_PYTHON=.venv/bin/python node --test frontend/tests/forecast-backend.integration.mjs
cd frontend
npm run lint
npx tsc --noEmit
npm run build
```

The Node test harnesses require Node 22.13 or newer for TypeScript type stripping. The cross-language integration test runs the actual frontend HTTP client and Zustand store against FastAPI, SQLite, the forecast worker and Droid tools through an in-process HTTP transport. It needs the backend Python dependencies but no listening socket or API key; it does not replace browser testing.

The [replay report](docs/learning/replay-summary.json) compares extracted context, no context, independently encoded oracle inputs, and two direct weekly challengers, retaining failed opportunities in each denominator. It establishes synthetic mechanism behavior; enterprise accuracy and calibration require subsequent company data.

The earlier standalone forecasting CLI and WSGI example remain available; the integrated backend calls the package directly and needs no separate forecasting network service. Earlier research remains in the [forecasting dossier](docs/forecasting-research/README.md) and [robustness benchmark](docs/robustness-2026-10-24/README.md).
