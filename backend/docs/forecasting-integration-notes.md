# Forecasting package integration notes (probe, 2026-10-25)

This probe checks how the backend can call the root `src/forecasting` package (`evidence-forecasting`)
for the Uber (simulated) dataset. It covers the install results, the exact library calls, timings for
16 teams, the mismatches the adapter must handle, and a recommended adapter design for
`app/providers/forecasting_pkg.py` (plan §2). Holdout files were not read.

Inputs: `datagen/out/forecasting/uber-observations.json`, and a scratch DB loaded with
`datagen/load_backend.py --db /tmp/uber-probe.db --reset` (331,732 usage records, 0 unmapped, 87 s).
The team-day variable sums from `usage_records` match the export exactly (0 mismatches over 4,752 team-days).

## 1. Install results (backend/.venv, Python 3.13.12, macOS arm64)

| Step | Result |
|---|---|
| `pip install -e /Users/devinfitzpatrick/code/cal-hacks-13` (core, `dependencies = []`) | **OK.** `import forecasting` works. |
| `pip install -e "/Users/devinfitzpatrick/code/cal-hacks-13[models]"` | **FAILS** after 83 s. The pins `numpy==1.26.4` and `scipy==1.13.1` ship no cp313 wheels. pip builds scipy from source, and that build fails (`metadata-generation-failed`). |
| `pip install --only-binary=:all: "numpy>=2.1,<3" "scipy>=1.14.1,<2" scikit-learn==1.6.1 joblib==1.5.3 threadpoolctl==3.6.0` | Installs (numpy 2.5.4, scipy 1.18.1). **But it does not help:** `models.eligibility()` checks for the exact pins `numpy==1.26.4` and `scikit-learn==1.6.1`, so every learned model reports `dependency requires numpy==1.26.4 (installed 2.5.4)`. These packages were uninstalled again after the probe. |

The learned models do run on numpy 2.5.4 if the version gate is bypassed (probe-only monkeypatch, never
for serving): `calendar_regression` takes about 2.4 s and `pooled_ridge` about 2.6 s for **one** team at
69 days, mostly sklearn import plus 69 per-horizon fits. `tabular_mean` (GBR) takes 95.5 s for one team,
and `tabular_direct_cumulative` 0.84 s. Even with matching pins, they would be too slow for a 16-team
rolling backtest on a demo laptop.

**Conclusion:** use the core install only. The six dependency-free models are eligible on Python 3.13:
`last_observation`, `trailing_mean`, `weekday_mean`, `seasonal_naive`, `exponential_smoothing`,
`local_linear_trend`. This is the fallback the plan already allows ("the backtest uses the
dependency-free models and says so"). The provider should put this sentence in `assumptions`.

**`backend/pyproject.toml`: no extra added.** The root package is a local path. PEP 508 extras cannot
name a relative path portably, and the `[models]` pins do not install on 3.13 anyway. The install step
is:

```sh
cd backend && .venv/bin/pip install -e ..        # evidence-forecasting core, no third-party deps
```

`datagen/demo.sh` and the backend README should run or document this step. The provider must fail
closed (`availability="unavailable"`, reason `"forecasting package not installed: pip install -e .."`)
when `import forecasting` fails.

## 2. Exact API

### Run one model for one team series

```python
from datetime import date, timedelta
from forecasting.models import Series, forecast, eligibility, MODEL_REGISTRY, ModelUnavailable

s = Series(entity_id="rider-app",
           dates=(date(2026,1,1), ..., date(2026,10,23)),   # consecutive, date-only; no gaps allowed
           values=(40.9, ...))                               # float, finite; missing != 0
future = tuple(date(2026,10,24) + timedelta(days=i) for i in range(69))  # must start the day after s.dates[-1]
p = forecast(s, future, "weekday_mean")     # config=None uses _DEFAULTS; panel ignored by local models
p.cumulative_value      # float, == fsum(p.daily_values)
p.daily_values          # tuple[float] aligned to p.dates (None only for tabular_direct_cumulative)
p.statistic             # "mean" (or "point" if nonnegative clipping changed it)
p.coherence             # "daily_sum"
p.limitations, dict(p.metadata)   # metadata: required_history, horizon_strategy, origin, config, ...
```

- Supported names come from `[n for n, s in MODEL_REGISTRY.items() if s.supported]`. Gate each one with
  `eligibility(series, n).eligible`, which reports both history minimums and dependency pins.
- Minimum history: `last_observation` 1, `exponential_smoothing` 2, `local_linear_trend` 3,
  `trailing_mean` 7, `seasonal_naive` 7, `weekday_mean` 28 days (window).
- `forecast` raises `ModelUnavailable` (a `ValueError`) for ineligible input, a bad horizon or
  non-consecutive future dates. `Series(...)` raises `ValueError` on gaps or non-finite values.
- Optional `config={"nonnegative": True}` clips negative daily means to 0 and relabels the output as a
  point forecast. Spend history has no refunds, so the default is fine.

### Rolling-origin backtest (reuse `forecasting.evaluation.evaluate_rolling`)

```python
from datetime import datetime, timezone
from forecasting.evaluation import evaluate_rolling

H = (period_end_exclusive - origin).days                       # e.g. 69 for Oct 24 .. Dec 31
origins = [origin - timedelta(days=H) - timedelta(days=7*k) for k in range(8)]   # weekly, fully in history
res = evaluate_rolling(series_list, origins, H, candidates,
                       score_as_of=datetime.combine(origin, datetime.min.time(), timezone.utc))
wape = res["candidates"][name]["summary"]["companies"][team_id]["point"]["wape"]   # per-team error
# also available per team: mae, rmse, bias; overall: summary["point"], team_macro_mae, spend_weighted_mae
```

- Each origin is the **first forecast date**, and its inputs end the previous day. Without
  `observation_labels`, the history is "idealized next-midnight availability" (`res["history_mode"]`).
  That is correct for billing rows that are complete the next day, and the provider should state it.
- `companies` defaults to `entity_id`, so `summary["companies"][team]` is the per-team summary. Pass
  `companies={team: "uber-sim"}` only for a company rollup.
- Failures (ineligible, too little history) come back as rows with `output_status="unavailable"` and do
  not raise, so a candidate can be scored on fewer opportunities. Check
  `summary["companies"][team]["scored"]` before comparing WAPE.

## 3. Timings (16 teams, Uber, as-of Oct 24, 69-day horizon)

| Step | Time |
|---|---|
| `import forecasting.models, forecasting.evaluation` | 144 ms |
| `forecast()`: 16 teams x 6 local models x 69 days | 8.7 ms |
| `evaluate_rolling`: 8 origins x 6 models x 16 teams, H=69 (also H=28, H=14) | 0.25 to 0.65 s |
| Final forecasts for 16 chosen models | 2.3 ms |
| History SQL (team x day, counted, variable, before as-of) on scratch DB | 0.97 to 2.8 s cold |
| Q4 spend to date per team, no new index | 126 ms cold / 42 ms warm |
| Q4 spend to date per team+person, no new index | 132 ms cold / 50 ms warm |
| Same two queries with a covering index `(period_id, counts_toward_spend, team_id, person_id, occurred_at, amount)` | 6 to 9 ms (index build 1.8 s) |
| `select max(rowid) from usage_records` (change token) | under 1 ms |
| `select count(*)` / `max(created_at)` | 188 / 334 ms (do not use as a fingerprint) |

Model selection plus forecasts take about 1 s in total, and history SQL dominates. That is fine for a
background recompute, and too slow for a request path. Spend to date per request needs the covering
index (or an incremental running sum keyed by `max(rowid)`) to stay well under 200 ms.

Backtest winners at H=69 (WAPE): weekday_mean on 10 teams; seasonal_naive on ai-labs (0.081),
driver-app, eats-delivery, security and support-automation (0.202, the worst); trailing_mean on
payments-risk. WAPE ranges from 0.077 to 0.202. At H=28 or H=14 the winners shift toward
trailing_mean and exponential_smoothing for some teams. Selection is horizon-dependent, so it must use
the real remaining horizon.

## 4. Mismatches the adapter must handle

1. **Half-open periods.** The package uses `[period_start, period_end)` (`contracts.interval`:
   "nonempty half-open date interval required"; `service._days` excludes the end date). Backend
   `planning_periods.ends_on` is **inclusive** (Q4 = 2026-10-01..2026-12-31). The adapter must use
   `ends_on + 1 day` as the exclusive end. Note: `datagen/out/forecasting/uber-config.json` passes
   `period_end: "2026-12-31"` to the package, which drops Dec 31. Flag this to the datagen owner. The
   backend adapter does not use that config.
2. **as-of is midnight; the last day is partial.** The package's `as_of` is a UTC midnight timestamp,
   and its origin date is the first day *not* in history. The dataset's as-of is Oct 24, a partial
   Saturday, and `uber-config.json` uses `2026-10-24T00:00Z`, so history ends on Oct 23. Backend
   `Attribution.as_of` is "max occurred_at date", which is Oct 24 here. Rule for the adapter:
   **history = counted days strictly before the latest record's date**, so the partial day is never
   treated as complete; **future = the latest record's date through period end**. Live feed rows
   (`datagen/live.py`) use wall-clock UTC `now`. Once the clock moves past midnight, the dataset's
   partial Oct 24 (plus any live rows on it) enters history as a "complete" day. Accept this and
   record it in assumptions. Alternatively, treat `company_profile.as_of` as the earliest possible
   cutoff.
3. **Projection = recorded + future, with no double count of today.** `projected = recorded spend to
   date in the period (incl. today's partial) + model future for the days after today`. That gives
   69 future days from Oct 24 at data load. Once live rows exist on a later date, the future starts the
   day after that date. Today's remaining hours are not forecast (state this as a limitation), or the
   adapter can forecast today and subtract today's recorded amount, floored at 0. Keep it simple: the
   future starts tomorrow.
4. **Categories and seat fees.** `uber-observations.json` holds only `category="variable"` (= backend
   `direct_api` + `billable_overage`). Backend `counts_toward_spend` also includes `subscription_fee`
   (850 rows, all on the 1st of each month at 00:00). `included_usage` is excluded by a constraint.
   Seat fees must **not** be in the daily model series, because a monthly lump on day 1 breaks
   weekday_mean and seasonal_naive. Treat them as a fixed obligation: for each 1st-of-month left in the
   period (Nov 1, Dec 1), add the team's latest month's seat total, and label it "seat fees carried
   from Oct". Spend to date includes seat fees already billed (Oct 1).
5. **Gaps and coverage.** `Series` rejects gaps ("gaps are not zeros"). The Uber history has none: every
   team has every day from 2026-01-01, even holidays at reduced levels. A team that starts mid-year
   still needs a decision. Start its series at its first counted day, and zero-fill only interior days,
   because billing coverage is complete for those days. Say so in the assumptions. Teams with fewer than
   28 days lose weekday_mean through `eligibility`, which is fine. A team with no history gets
   `missing_teams`, not 0.
6. **Horizon caps.** `ModelSpec.max_horizon` is 366 for local models, so 69 days is fine. Learned
   models cap at 90 (irrelevant here). `ForecastService` has a separate `max_horizon=366` workload
   bound.
7. **Money precision.** The models take and return floats. Convert the future total and daily values
   with `Decimal(str(round(v, 2)))`, then fix the rounding remainder so `sum(daily) == future`
   (`largest_remainder` already exists in `app/providers/forecast.py`). Keep spend to date on the
   backend's Decimal path, not on `cast(amount as real)`.
8. **The models are blind to events.** All the eligible models continue the recent level and weekday
   shape. They do **not** see the announced Q4 events (Fable 5.1 step on Nov 16, Freight hold on Nov 2,
   Thanksgiving and year-end closures, Build Week). Assumptions must say "statistical continuation of
   history; announced context events are not applied". Context signals stay a separate layer.
9. **`ForecastService` is not a good fit for the request path.** It needs a `Snapshot` (source
   manifest, coverage, `known_at`) and runs a single `request.model`. Calling `models.forecast` and
   `evaluation.evaluate_rolling` directly is simpler and keeps the package's validation (Series gates,
   eligibility, Prediction coherence checks).

## 5. Recommended adapter design (`app/providers/forecasting_pkg.py`)

```
ForecastingPackageProvider(name="forecasting_package", supports_attribution=True)
  get_forecast(period_id, team_ids, attribution) -> ForecastResult       # request path, cheap
  refresh(force=False)                                                   # background or POST /api/forecasts/refresh
```

- **Cache entry** (per period): `{fingerprint, history_end, origin, per_team: {model, wape, scored,
  mae, bias, future_daily: [(date, Decimal)], seat_future: Decimal}, computed_at}`. Keep it in memory
  behind a lock, optionally mirrored to a `forecast_snapshots` row.
- **Fingerprint** = `(period_id, history_end, max(rowid) of counted rows with date < history_end)`.
  Cheaper: `(period_id, latest record date)`. The model only changes when a new complete day appears,
  because rows arriving for today do not change history.
- **refresh()**
  1. Load team x day counted non-seat sums before `history_end` (one SQL, about 1 s).
  2. Build `Series`.
  3. Run `evaluate_rolling` with 8 weekly origins at `H = days(origin .. ends_on]` over the six
     eligible models.
  4. For each team, pick the lowest WAPE among candidates with `scored == max scored`; break ties by
     registry order.
  5. Call `forecast(...)` for `future_dates` = tomorrow .. ends_on.
  6. Store the result.

  Run it in a `ThreadPoolExecutor(max_workers=1)` and never block a request on it. Before the first
  run completes, return `availability="unavailable"` with reason `"forecast computing"`, not zeros.
- **get_forecast()** (per request, under 20 ms with the covering index)
  1. Take spend to date per team and person from `attribution`. The forecast service already computes
     it; cache it by `max(rowid)`.
  2. Set `team.amount = to_date + future_total + seat_future`.
  3. Set `team.daily = future_daily`, plus seat lumps on the 1st.
  4. Split person projections with the existing proportional-split code, so they sum exactly.
  5. Set `assumptions = [f"model {m} chosen by rolling backtest (8 weekly origins, {H}-day horizon,
     WAPE {w:.1%})", "dependency-free models only (Python 3.13; numpy/scikit-learn pins unavailable)",
     "statistical continuation; announced context events not applied", "seat fees carried from
     latest month"]`.
  6. Set `value_kind="estimated"` and `method_label="evidence-forecasting rolling-backtest selection"`.
  7. If the cached origin is older than the latest record date, kick off a non-blocking refresh.
- **Index**: add `(period_id, counts_toward_spend, team_id, person_id, occurred_at, amount)` on
  `usage_records` (1.8 s once at load). It is the difference between 50 ms and 7 ms per spend-to-date
  query.
- **Config**: add `"forecasting_package"` to `FORECAST_PROVIDERS` in `app/config.py`. The placeholder
  stays the default, so Northstar is unchanged. `datagen/demo.sh` exports
  `FORECAST_PROVIDER=forecasting_package`.
- **Tests**: use a synthetic 60-day, 2-team DB, never the holdout. Check the half-open end (Dec 31
  included), that the partial last day is excluded from history, that seat fees are excluded from the
  series, that persons sum exactly to the team, that the cache is reused while `max(rowid)` changes
  only today, that refresh fires when a new day appears, and that the provider fails closed on
  `ImportError`.
