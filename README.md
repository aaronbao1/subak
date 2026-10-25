# Subak

**Understand AI spending. Forecast demand. Allocate budgets with evidence.**

Subak helps financial planning and analysis (FP&A) teams see where AI spending is headed and decide which teams need more funding. It brings usage, company plans, funding requests, and allocation decisions into one workspace.

[Try the demo](https://subak-chi.vercel.app) · [Open the dashboard](https://subak-chi.vercel.app/overview)

## What you can do

- **See the whole company.** Explore spending by team and person, subscription costs, API charges by model, and daily activity.
- **Compare forecast with reality.** View weekly actuals, projected spending, and over/under differences against preserved forecasts.
- **Understand what changed.** Inspect the project plans, team updates, and source documents behind upcoming needs.
- **Coordinate budgets.** Assess team requests, redistribute existing funding, or propose an increase to the company budget.
- **Work with Droid.** Investigate spending and review allocation proposals through an assistant. Finance approves changes and keeps a decision record.

## Try a budget decision

The demo includes a fictional company with **16 teams and 130 people**. Open Droid Assistant and ask:

> Transfer $1,000 from Freight to Support.

Review the before-and-after allocations, inspect the evidence, and apply the proposal. The company budget stays unchanged.

The public demo uses saved data and forecasts. Changes stay in your browser session and reset on reload; live Factory calls and forecast recalculation require the full backend.

## How it works

The full application has four main components:

| Component | Role |
| --- | --- |
| **Next.js, React, TypeScript** | Finance dashboard, weekly comparisons, evidence, and proposal review. |
| **FastAPI and SQLite** | Import and deduplicate records; store company context, budgets, forecasts, and decisions. |
| **Python forecast engine** | Estimate usage from observed history, apply supported changes in workload and timing, and calculate costs. |
| **Factory Droid SDK** | Give the assistant scoped tools to investigate sources, explain forecasts, and draft proposals. |

Each issued forecast preserves its inputs, citations, and calculations. The dashboard and Droid reference the same saved results. The backend checks proposal arithmetic and evidence freshness before finance approves an internal allocation change.

## Run the demo locally

Requires Node.js 22.13 or newer.

```sh
cd frontend
npm ci
NEXT_PUBLIC_DEMO_SNAPSHOT=/demo npm run dev
```

Open [localhost:3000](http://localhost:3000). No API key or backend is needed for this mode.

## Documentation

- [Demo setup](docs/implementation/interactive-demo.md)
- [Architecture and forecasting](docs/implementation/forecast-integration.md)
- [Backend setup](backend/README.md) · [Droid integration](agent/README.md)
- [Forecasting research](docs/forecasting-research/README.md)

Built at Cal Hacks 13.0.
