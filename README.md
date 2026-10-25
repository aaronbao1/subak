# AI Spend Planner

A finance workspace for understanding AI spending, comparing expected team needs, and planning internal budgets. Built for Cal Hacks 13.0.

The goal is to bring spending records, forecasts, and company plans into one place so finance teams can investigate changes and make informed allocation decisions.

**Preliminary status:** The overview and team screens run with mock data, and the Python forecasting package runs independently. The product backend (`backend/`) runs with the live Factory Droid assistant (`agent/`) and serves the frontend's API under `/compat`. The assistant drawer and decisions page are placeholders. Connecting the UI to the backend and the forecasting service to the backend remains integration work.

## The intended workflow

1. Review company and team spending alongside internal allocations.
2. Compare projected needs and inspect the assumptions, source coverage, and uncertainty behind them.
3. Consult company plans and correspondence to understand changes in workload.
4. Review a proposed redistribution or additional funding allocation, then record finance's decision.

The shared demo company is **Northstar Software**, with research, product, and engineering teams. Its example asks how to support research when it is projected to exceed its allocation while product has headroom. Demo spending, budgets, documents, and UI projections are synthetic.

Allocations are internal planning records. They do not transfer vendor credits, purchase compute, or change provider limits. Usage, reported charges, cost estimates, and internal budgets retain their own units and provenance.

## What is in the repository

| Component | Role | Current state |
| --- | --- | --- |
| [Frontend](frontend/) | Finance dashboard, team comparisons, spending charts, and evidence inspection | Next.js / React / TypeScript UI with an in-memory mock client and an HTTP client. Overview and team views are implemented; assistant and decisions views are placeholders. |
| [Forecasting](src/forecasting/) | Numerical forecasts, scenarios, pricing, and evaluation | Runnable Python reference implementation with a CLI, local service example, SQLite artifacts, and tests. Includes baseline models, optional regression models, and joint workload/pricing paths. |
| [Product backend](backend/README.md) | Spend and document ingestion, budgets, proposals, finance decisions, and the frontend API | FastAPI + SQLite service with versioned budgets, stale-proposal and self-approval checks, idempotent imports, quote-verified context signals, and a `/compat` layer serving the frontend's `/api/*` contract. 561 tests. The forecast is a placeholder provider until the forecasting service is connected. |
| [Backend reference components](docs/implementation/consumer-contracts.md) | Source handling, financial validation, and saved results (forecasting package) | Reference ingestion, storage, and budget-decision controls inside the forecasting package. |
| [Factory / Droid](agent/README.md) | Interpret company context, cite evidence, and help finance prepare proposals | Live Droid SDK runtime inside the backend: read and draft tools only, a static script gate (red-teamed), and a retry turn on refusals. The latest live run of each of 11 eval scenarios passes ([evals](backend/evals/README.md)). Not yet wired to the UI's assistant drawer. |
| [Research and benchmarks](docs/robustness-2026-10-24/README.md) | Document assumptions, test mechanisms, and evaluate forecasting approaches | Research dossier, regression tests, synthetic examples, and a limited real-trace benchmark with recorded execution evidence. |

## Run locally

Run each component separately. Commands below assume a checkout of the current `main` branch.

### Frontend demo

Requires **Node.js 20.9+** and npm. From the repository root:

```sh
cd frontend
npm install
npm run dev
```

Open [localhost:3000](http://localhost:3000). The default demo uses in-memory data and needs no backend or API key. Mock mutations reset on reload. Use `?teams=default` for Northstar or `?teams=N` for a generated company with 0–16 teams.

From `frontend/`, run `npm run lint` for linting and `npm run build` for a production build.

### Product backend and Droid assistant

Requires **Python 3.12+**. See [`backend/README.md`](backend/README.md) for the full guide and [`backend/docs/morning-runbook.md`](backend/docs/morning-runbook.md) for the demo journey. In short, from `backend/`: create `backend/.venv`, install with `pip install -e ".[dev]"`, seed with `python -m app.seed`, and serve with `python -m app.main` on port 8787. Droid uses a deterministic fake runner by default; set `DROID_RUNNER=sdk` with `FACTORY_API_KEY` and the `droid` CLI to use the live runtime.

To point the frontend at it, set `NEXT_PUBLIC_API_URL=http://localhost:8787/compat` in `frontend/.env.local`. Open gaps between the frontend contract and the backend are listed in [`backend/docs/frontend-alignment.md`](backend/docs/frontend-alignment.md).

### Forecasting reference demo

Requires **Python 3.9+**. From the repository root, in a separate terminal:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[models,test]'
.venv/bin/python -m pytest -q
.venv/bin/forecasting demo --output-dir artifacts/northstar-first-run
```

The demo imports synthetic source data, saves forecasts and scenarios, and exercises two independent allocation alternatives through the reference backend. Use a fresh output directory for each run. Finance approvals in this demo are simulated.

The core package has no third-party runtime dependencies; the install above adds the optional numerical models and test dependencies. The Chronos benchmark uses a separate Python 3.11 environment and its own [dependency file](benchmarks/robustness/requirements-chronos.txt).

Additional CLI examples:

```sh
.venv/bin/forecasting models
.venv/bin/forecasting evaluate --seed 7 --output artifacts/evaluation.json
.venv/bin/forecasting forecast examples/northstar-config.json --store artifacts/results.sqlite
```

## Connecting the components

The intended flow is: backend acquires spending and company documents; Factory interprets context; forecasting produces numerical results; the frontend presents evidence and proposals; finance approves changes that the backend validates and saves.

The frontend's payload definitions live in [its TypeScript contracts](frontend/src/lib/contracts/index.ts). The [frontend integration guide](docs/frontend-integration.md) lists the required `/api/*` endpoints. Set `NEXT_PUBLIC_API_URL` in `frontend/.env.local` to select the HTTP client once a compatible backend is available.

The forecasting package exposes a separate `/v1/*` interface through [the local WSGI example](examples/serve.py). It is not a drop-in implementation of the frontend API. See the [forecasting API guide](docs/implementation/api.md) for authentication, trusted data inputs, and request/response contracts, and the [consumer guide](docs/implementation/consumer-contracts.md) for reference handoffs.

The remaining product integration work is to connect those contracts, implement the live assistant and decision UI, and verify that an approved allocation persists and appears consistently across the dashboard and assistant.

## Evidence and current limits

The forecasting tests check financial arithmetic, data boundaries, permissions, historical availability, and reference workflows. Synthetic demos establish executable behavior; they do not establish enterprise forecasting accuracy.

A separate benchmark ran pinned **Chronos-Bolt Tiny** weights on a public BurstGPT input-token trace and completed 40 of 40 scheduled forecasts. Results were mixed across one-hour and four-hour horizons. The [benchmark report](docs/robustness-2026-10-24/benchmark.md) and [verification record](docs/robustness-2026-10-24/verification.md) document the results and limitations. This benchmark is separate from the frontend's placeholder projections.

Live enterprise billing connections, production authentication, and deployed end-to-end operation are not established. The live Factory runtime runs inside the backend and is evaluated in [`backend/evals/`](backend/evals/README.md); it is not yet connected to the UI.

## Further reading

- [Product scope and shared demo story](docs/ai-spend-master-plan.md)
- [Frontend integration contract](docs/frontend-integration.md)
- [Backend and ingestion plan](docs/backend-plan.md)
- [Factory assistant plan](docs/factory-agent-plan.md)
- [Forecasting capabilities and limits](docs/implementation/requirements-and-capabilities.md)
- [Forecasting research dossier](docs/forecasting-research/README.md)
- [Joint forecasting and benchmark work](docs/robustness-2026-10-24/README.md)
