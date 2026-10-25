# AI Spend Planner

A finance workspace for understanding AI spending, comparing expected team needs, and planning internal budgets. Built for Cal Hacks 13.0.

The goal is to bring spending records, forecasts, and company plans into one place so finance teams can investigate changes and make informed allocation decisions.

**Preliminary status:** The overview and team screens run with mock data, and the Python forecasting package runs independently. The assistant drawer and decisions page are placeholders. Connecting the UI, persistent product backend, forecasting service, and live Factory assistant remains integration work.

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
| [Backend reference components](docs/implementation/consumer-contracts.md) | Source handling, financial validation, and saved results | Reference ingestion, storage, and budget-decision controls are implemented in Python. A complete product backend exposing the frontend's API still needs integration. |
| [Factory / Droid workstream](docs/factory-agent-plan.md) | Interpret company context, cite evidence, and help finance prepare proposals | Planned runtime integration. Reference context contracts exist; live Droid execution is not connected to the UI. |
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

Live enterprise billing connections, production authentication, deployed end-to-end operation, and live Factory runtime integration are not established by the current reference implementation.

## Further reading

- [Product scope and shared demo story](docs/ai-spend-master-plan.md)
- [Frontend integration contract](docs/frontend-integration.md)
- [Backend and ingestion plan](docs/backend-plan.md)
- [Factory assistant plan](docs/factory-agent-plan.md)
- [Forecasting capabilities and limits](docs/implementation/requirements-and-capabilities.md)
- [Forecasting research dossier](docs/forecasting-research/README.md)
- [Joint forecasting and benchmark work](docs/robustness-2026-10-24/README.md)
