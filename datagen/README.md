# Synthetic company dataset: "Uber (simulated)"

A full year of fabricated AI token spend for a large ride-hailing / delivery company, built so every
component of this repository (backend, frontend, forecasting, Droid) can be exercised against realistic,
evidence-rich data. **Everything is fictional**: the people, the messages, the model line-up, the list
prices and the company itself (labelled "Uber (simulated)" as a familiar stand-in; nothing is derived from
any real account). The generator is stdlib-only Python 3.9+ and deterministic for a given seed.

```sh
python3 datagen/generate.py          # writes datagen/out/ (~10 s)
python3 datagen/check.py             # integrity checks: the planted patterns must be visible in the data
```

`datagen/out/` is gitignored; regenerate it whenever you need it. Read `datagen/out/SUMMARY.md` for the
headline numbers and `datagen/out/ANSWER_KEY.md` for every planted storyline with its window, multiplier
and the effect measured in the generated data.

## What is in the data

| Dimension | Content |
|---|---|
| Time | 2026-01-01 to 2026-10-24 (the as-of date, a Saturday, partial). Four quarterly planning periods; Q4 is current. |
| Organisation | 16 teams (Rider App, Driver App, Marketplace & Pricing, Maps & Routing, Eats Delivery, Freight, Safety & Trust, Payments & Risk, Data Platform, AI Labs, Infrastructure & SRE, Customer Support Automation, Security, Finance & Legal Ops, People & Recruiting, Marketing & Comms), 130 named people with roles, levels, emails, time zones, a primary tool and the connectors they appear in. 10 join and 5 leave during the year. |
| Usage | One row per person × day × model × cost category: input / cached-input / output / reasoning tokens, request count, charged cost and list value. Cost categories: `direct_api`, `billable_overage` (Cursor / Copilot), `included_usage` (ChatGPT / Gemini Enterprise seats), plus monthly `subscription_fee` seat rows. |
| Providers and models | Anthropic (Claude Opus/Sonnet/Haiku 4.5 → 5.5, Fable 5.1), OpenAI (GPT-5.2 → 5.5, mini), Google (Gemini 3 → 3.5 Pro/Flash). Fictional list prices per model with two mid-year price changes; model mix ramps over three weeks after each adoption. |
| Calendar | Weekday rhythm (Fridays lower), weekends at a per-person fraction of a weekday, US holidays and company closures at a quarter or less, seasonal dips (July 4th week, late August, year-end shutdown). |
| Trend | Adoption grows through the year, faster for AI Labs and Support Automation; company-wide bumps around each model adoption and hackathon. |
| Storylines | ~150 events with ~250 pieces of evidence across **Slack, Microsoft Teams, Gmail, Outlook, Asana and monday.com**: project holds and restarts, deadlines pulled forward or pushed back, out-of-office windows, people taking on extra work (with Saturday messages), onboarding, departures, model migrations, model releases and adoptions, price cuts, a provider-access policy change, a tool consolidation, hackathons, incidents, hiring freeze, quarter-close weeks and holiday notices. |
| Future | 22 events start after the as-of date but are announced before it (Fable 5.1 pilot on Oct 31 and company-wide step on Nov 16, a Freight hold from Nov 2, Build Week Nov 9-13, Thanksgiving and year-end closures, Q4 deliveries, planned leave). The generator also writes the synthetic *truth* for Oct 25 - Dec 31 (`usage_daily_holdout`, `forecasting/uber-holdout-truth.json`) so forecasts can be scored. Never feed the holdout to a model. |
| Budgets | Quarterly internal allocations per team. By construction AI Labs and Support Automation run over in Q4 while Freight and Payments & Risk have headroom. |

## Outputs (`datagen/out/`)

- `uber_ai_spend.sqlite` — the whole dataset: `company`, `periods`, `teams`, `people`, `providers`, `models`,
  `model_prices`, `model_events`, `calendar`, `projects`, `events`, `messages`, `tasks`, `usage_daily`,
  `usage_daily_holdout`, `seat_subscriptions(_holdout)`, `budgets`; views `team_daily`, `person_daily`,
  `company_daily`, `model_monthly`.
- `backend/` — `billing/*.csv` in the backend's `northstar_billing` import format (half-month files, each
  under the 10 MB import limit), `corpus/*.md` documents with the front matter `app.services.corpus`
  parses, and `reference.json` (periods, teams, account → team mappings, budgets per quarter).
- `frontend/` — contract shapes from `frontend/src/lib/contracts/index.ts`: `company.json` (company,
  teams, people, budgets), `spending-records.json.gz` (per-person `SpendingRecord`s, ~130 MB unpacked),
  `spending-team-daily.json` (team × day × component × provider × model), `documents.json`
  (`CompanyDocument`), `context.json` (`ContextItem` per event, with `signal`, `scope`, `category`,
  `magnitude` and source refs; the extra optional `eventKind` carries the finer-grained kind).
- `forecasting/` — `uber-observations.json` (team-day variable spend, source `billing`, in the `src/forecasting`
  export format), `uber-seat-observations.json` (monthly seat fees, source `seats`), `uber-config.json` (a Q4
  forecast request over `billing`), `uber-holdout-truth.json`.
- `csv/` — flat tables (`usage_daily.csv.gz`, `team_daily.csv`, `people.csv`, `events.csv`, `messages.csv`,
  `tasks.csv`, `model_events.csv`, `calendar.csv`, `budgets.csv`, `seat_subscriptions.csv`, `teams.csv`).

## Loading into the backend

Requires the backend's Python 3.12 environment (`backend/.venv`, see `backend/README.md`). From the repo root:

```sh
backend/.venv/bin/python datagen/load_backend.py            # -> backend/data/uber.db (use --reset to reload)
cd backend && BACKEND_DB_PATH=data/uber.db .venv/bin/python -m app.main
```

The loader creates the four periods, teams, mappings and budget envelopes, ingests every corpus document and
runs every billing CSV through `imports.run_import`, so dedupe, period lookup and team attribution are the
backend's own. The frontend can then point at it with `NEXT_PUBLIC_API_URL=http://localhost:8787/compat`.
Verified on 2026-10-24: 331,966 usage records imported, 0 unmapped, 252 documents, coverage `complete`.

## Forecasting

```sh
.venv/bin/forecasting forecast datagen/out/forecasting/uber-config.json --store artifacts/uber-results.sqlite
```

Verified on 2026-10-24: the request runs end to end and returns a per-team daily projection for Q4. Score it against
`uber-holdout-truth.json` (variable rows) to evaluate a model.

## Changing the data

`datagen/uberdata/config.py` holds teams, roles, models, prices, holidays and the model timeline;
`events.py` holds the storylines and message templates; `usage.py` the daily mechanics. Run
`generate.py --seed N` for a different draw of people and sampled person-level events with the same scripted
company and team storylines.
