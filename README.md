# Subak

**Agent-powered FP&A to forecast and manage enterprise AI token spending across teams.**

Subak brings AI usage, company plans, forecasts, and budget decisions into one workspace for financial planning and analysis (FP&A) teams. Finance can see where spending is headed, investigate what is changing, and decide how to allocate funding across the company.

[Try the demo](https://subak-chi.vercel.app) · [Open the dashboard](https://subak-chi.vercel.app/overview)

## Why Subak?

The name comes from Bali's **subak** irrigation system. Farming communities cooperate to manage the water that sustains their rice fields through a shared network of canals, weirs, and water temples. This living cultural tradition connects the practical distribution of water with community governance and the Balinese philosophy of *Tri Hita Karana*, which links people, nature, and spiritual life. [Read about subak at UNESCO](https://whc.unesco.org/en/list/1194/).

Our project takes inspiration from that principle of coordinating a shared resource. Teams have different workloads and priorities, but draw on the same company AI budget. Helping one team meet a new need requires understanding what other teams need, what is available, and how the whole system is changing. Subak brings those needs into a common view, supports evidence-based allocation proposals, and keeps people responsible for the final decisions.

## What Subak does

1. **Unifies spending visibility.** Explore recorded usage and spending by company, team, person, and model, with source coverage and attribution available for inspection.
2. **Forecasts weekly needs.** Estimate team-level token usage and supported costs from observed history, workload measurements, model pricing, and dated company plans.
3. **Explains changes.** Use Factory Droid to investigate imported messages and documents, trace citations, and explain the saved forecasts behind a team's outlook.
4. **Previews scenarios.** Compare expected spending with and without supported changes in staffing, workload, timing, or model usage.
5. **Coordinates budgets.** Review team funding requests, redistribute existing allocations, or propose additional company funding. Transfers preserve the total budget; new funding changes it explicitly.
6. **Records accountable decisions.** Review a structured proposal, its evidence, before-and-after allocations, and remaining funding gaps. The backend validates the proposal, and a finance approver decides whether to apply it.

For example, Research may be preparing a larger evaluation while Product delays a launch. Finance can inspect both outlooks, read the supporting plans, and ask Droid to draft an allocation proposal. A request such as “We have $50,000 more—prioritize Research” adds funding; a request to redistribute existing funding keeps the company total unchanged.

## How it works

### 1. Import usage and company context

The FastAPI backend imports supported billing CSV/JSON exports and Codex session JSONL. It removes duplicate records, converts cumulative token counters into usage increments, and maps known people and teams. SQLite stores usage and spending records alongside company documents, budgets, forecasts, and decisions.

Token usage, reported charges, cost estimates, and internal allocations retain their own units and provenance. Token counts alone do not establish a complete bill. The integrated demo supplies the coverage, workload, and pricing inputs needed for forecasting with synthetic company data.

### 2. Estimate demand and apply supported context

The Python engine focuses on weekly team planning. For teams with sufficient data, it estimates weekday usage patterns from up to the latest **56 complete observed days** that pass coverage and maturity checks. Compatible staffing or workload measurements support estimates of usage per unit of work; otherwise, the engine retains an aggregate view.

Factory Droid reads imported company context to identify relevant changes. A rule-based interpreter converts supported, dated changes into numerical adjustments. A project delay, staffing change, vacation, or revised model-use plan can inform a forecast when the necessary evidence is present. Ambiguous statements remain context until they can support a calculation.

Supported prices are applied across complete billing pools before costs are allocated to teams. This accounts for shared allowances and pricing tiers. Missing inputs or unsupported costs remain explicitly unavailable.

### 3. Preserve forecasts and update the live outlook

A backend worker runs the forecast package and saves each publication with its inputs, citations, and calculations. The dashboard shows current recorded spending alongside the saved forecast. Refreshing builds a new publication using the latest eligible inputs and supported billing-pool pricing.

The forecast issued before the week began stays fixed for comparison with actual results. Later refreshes do not rewrite that historical expectation. Forecasts with and without supported context can also be compared with outcomes to evaluate which assumptions help.

### 4. Investigate, propose, and approve

The Factory Droid SDK exposes **16 scoped backend tools** for investigating documents and funding requests, explaining saved forecasts, previewing scenarios, and drafting budget proposals. The backend verifies quotations, recomputes proposal arithmetic, and checks whether budgets and evidence are still current.

A finance approver makes the allocation decision, which is saved with a decision receipt. Allocations are internal planning records; they do not purchase compute, transfer vendor credits, or change provider limits.

## Architecture

| Component | Technologies | Responsibility |
| --- | --- | --- |
| [Dashboard](frontend/) | Next.js, React, TypeScript, Tailwind CSS, shadcn/ui, Recharts, Zustand | Spending views, weekly comparisons, evidence inspection, and proposal review. |
| [Backend](backend/) | Python, FastAPI, Pydantic, SQLAlchemy, SQLite | Imports, storage, forecast jobs, financial validation, and decision history. |
| [Forecast engine](src/forecasting/) | Python | Usage estimates, context adjustments, scenarios, billing-pool pricing, and evaluation. |
| [Assistant](agent/) | Factory Droid SDK | Investigate company context and use scoped tools to explain results and draft proposals. |
| [Demo data](datagen/) | Python | Synthetic company usage, documents, and workload examples. |

## Try the demo

The [public demo](https://subak-chi.vercel.app) includes a simulated company with **16 teams and 130 people**. Open Droid Assistant and ask:

> Transfer $1,000 from Freight to Support.

Review the proposed allocations and supporting information, then apply the proposal. The company budget stays unchanged.

The public demo uses saved data and forecasts. Changes stay in your browser session and reset on reload. Live Factory calls, forecast recalculation, and persistent decisions require the full backend.

## Run locally

Use **Node.js 22.13 or newer** (the recommended development version) and npm for the dashboard demo. No API key or backend is needed for this mode.

```sh
git clone https://github.com/aaronbao1/subak.git
cd subak/frontend
npm ci
NEXT_PUBLIC_DEMO_SNAPSHOT=/demo npm run dev
```

Open [localhost:3000](http://localhost:3000). For an existing checkout, run the last two commands from its `frontend/` directory.

For the connected application, use **Python 3.12** and follow the [backend setup](backend/README.md) and [Droid integration guide](agent/README.md). Leave `NEXT_PUBLIC_DEMO_SNAPSHOT` unset and configure `NEXT_PUBLIC_API_URL` to connect the frontend to the backend. Live Droid execution requires the Factory SDK, the `droid` CLI, and credentials configured in the backend environment.

## Evaluation and next steps

Subak is a research prototype. Synthetic company data and public token-usage experiments support controlled evaluation, but real enterprise forecasting accuracy still needs validation. Authenticated company connectors and production access controls remain development priorities.

Near-term work focuses on running alongside a real company, comparing preserved forecasts with actual spending over successive weeks, and measuring whether the workflow makes budget reviews faster and easier. Longer term, Subak aims to support autonomous agent teams: people set priorities and spending limits, while agents coordinate funding within those permissions and escalate requests that exceed them.

## Documentation

- [Public demo behavior and setup](docs/implementation/interactive-demo.md)
- [Forecast integration architecture](docs/implementation/forecast-integration.md)
- [Backend setup and API](backend/README.md)
- [Factory Droid tools and integration](agent/README.md)
- [Forecasting research](docs/forecasting-research/README.md)
- [Benchmark results and limitations](docs/robustness-2026-10-24/benchmark.md)

Built at Cal Hacks 13.0.
