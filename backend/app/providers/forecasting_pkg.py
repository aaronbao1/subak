"""ForecastingPackageProvider: real per-team forecasts from the root `forecasting` package.

`FORECAST_PROVIDER=forecasting_package` selects it (the placeholder stays the default, so Northstar is
unchanged). Design: backend/docs/forecasting-integration-notes.md §5.

Two halves, so a 1-second frontend refresh stays cheap:

- **Model run (background, cached).** Per active team, a daily series of counted spend without seat
  fees, on complete days only: every day strictly before the latest record's date (that day is still
  partial). A rolling-origin backtest on that history alone picks each team's model (lowest WAPE at the
  real remaining horizon), and the chosen model forecasts the remaining days of the period. The run is
  cached per (period, last complete day, history fingerprint) and recomputed in a single background
  worker when a new complete day appears, late rows land on a complete day, or an in-place change
  (a team re-attribution, a team (de)activation) alters the per-team history fingerprint; `refresh()`
  (and `POST /api/forecasts/refresh`) forces it on the same worker. Requests never wait for it.
- **Projection (per request).** `projected = recorded spend to date (incl. today's partial day, from the
  forecast service's Attribution) + cached model future for the days after today + seat fees on any
  remaining 1st of month`. Person projections split each day's team amount by share of spend to date
  (largest remainder in cents), so persons + team-level remainder sum exactly to the team.

Only the package's dependency-free models are candidates: its learned models need numpy/scikit-learn
pins that do not install on Python 3.13, and are too slow for a live backtest (notes §1). The models
are statistical continuations; announced context events are not applied. All of this is said in each
projection's `assumptions`. If `import forecasting` fails, every result is `unavailable` (fail closed).
"""

from __future__ import annotations

import concurrent.futures
import math
import threading
import time
from collections import defaultdict
from collections.abc import Hashable, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import select, text

from app.providers.forecast import BUCKET, Attribution, TeamAttribution, _share_text, largest_remainder
from app.schemas.forecasts import DailyProjection, ForecastResult, PersonProjection, TeamProjection

NAME = "forecasting_package"
METHOD_LABEL = "evidence-forecasting rolling-backtest selection"
NOT_INSTALLED = "forecasting package not installed: run `pip install -e ..` from backend/"
COMPUTING = "forecast computing: model selection is running in the background"
# Dependency-free candidates, in tie-break order (the package's registry order).
CANDIDATES = ("last_observation", "trailing_mean", "weekday_mean", "seasonal_naive",
              "exponential_smoothing", "local_linear_trend")
# Used, unvalidated, when a team has too little history for any backtest origin.
FALLBACK_ORDER = ("weekday_mean", "trailing_mean", "seasonal_naive", "exponential_smoothing",
                  "local_linear_trend", "last_observation")
BACKTEST_ORIGINS = 8
SEAT_CATEGORY = "subscription_fee"
DEPENDENCY_NOTE = ("candidates: the forecasting package's six dependency-free models; its learned models "
                   "need numpy/scikit-learn pins that are not installed on Python 3.13")
EVENTS_NOTE = "statistical continuation of history; announced context events are not applied"
PERSON_UNCERTAINTY = "team model estimate split by share of spend to date; not a person-level model"

_CENTS = "CAST(REPLACE(amount, '.', '') AS INTEGER)"  # MoneyType stores exactly two places: exact cents
_HISTORY_SQL = text(f"""
    SELECT team_id, substr(occurred_at, 1, 10) AS day, SUM({_CENTS}) AS cents
    FROM usage_records
    WHERE counts_toward_spend = 1 AND amount IS NOT NULL AND team_id IS NOT NULL
      AND cost_category != '{SEAT_CATEGORY}' AND occurred_at < :history_end
    GROUP BY team_id, day
""")
_SEAT_SQL = text(f"""
    SELECT team_id, substr(occurred_at, 1, 7) AS month, SUM({_CENTS}) AS cents
    FROM usage_records
    WHERE counts_toward_spend = 1 AND amount IS NOT NULL AND team_id IS NOT NULL
      AND cost_category = '{SEAT_CATEGORY}' AND occurred_at < :history_end
    GROUP BY team_id, month
""")
_PERIOD_AS_OF_SQL = text("""
    SELECT MAX(occurred_at) FROM usage_records
    WHERE period_id = :period AND counts_toward_spend = 1 AND amount IS NOT NULL
""")
_MAX_ROWID_SQL = text("SELECT MAX(rowid) FROM usage_records")
# Per-team fingerprint of everything a model run reads from complete days (history + seat fees). Run
# only after an in-place change to usage_records or a teams write (see _check_inputs), e.g. a team
# re-attribution, which moves rows between teams without adding a rowid.
_FINGERPRINT_SQL = text(f"""
    SELECT team_id, cost_category = '{SEAT_CATEGORY}' AS seat, COUNT(*), SUM({_CENTS})
    FROM usage_records
    WHERE counts_toward_spend = 1 AND amount IS NOT NULL AND team_id IS NOT NULL AND occurred_at < :history_end
    GROUP BY team_id, seat
""")
_LATE_ROWS_SQL = text("""
    SELECT 1 FROM usage_records
    WHERE rowid > :after AND rowid <= :upto AND counts_toward_spend = 1 AND occurred_at < :history_end
    LIMIT 1
""")


def _forecasting():
    """(models, evaluation) modules, or None when the package is not installed."""
    try:
        from forecasting import evaluation, models
    except ImportError:
        return None
    return models, evaluation


def _midnight(d: date) -> datetime:
    return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)


def _day(value: Any) -> date:
    return value.date() if isinstance(value, datetime) else date.fromisoformat(str(value)[:10])


def _pct(x: float | None) -> str:
    return "n/a" if x is None else f"{x:.1%}"


# ---- pure model-run pieces (unit-tested on synthetic series) -----------------------------------


def build_series(rows: dict[str, dict[date, int]], history_end: date) -> dict[str, tuple[list[date], list[float], int]]:
    """team -> (dates, dollar values, zero-filled interior days), from each team's first counted day
    through history_end - 1. Interior days without rows are zero (billing coverage is complete on those
    days); days before a team's first row are not invented."""
    out = {}
    for team, by_day in rows.items():
        days = [d for d in by_day if d < history_end]
        if not days:
            continue
        start, last = min(days), history_end - timedelta(days=1)
        dates = [start + timedelta(days=i) for i in range((last - start).days + 1)]
        filled = sum(1 for d in dates if d not in by_day)
        out[team] = (dates, [by_day.get(d, 0) / 100 for d in dates], filled)
    return out


def backtest_origins(history_end: date, horizon: int, earliest: date, n: int = BACKTEST_ORIGINS) -> list[date]:
    """Weekly first-forecast dates whose whole horizon lies in history (< history_end), newest first,
    each with at least one week of history before it."""
    out = []
    for k in range(n):
        o = history_end - timedelta(days=horizon + 7 * k)
        if o - earliest >= timedelta(days=7):
            out.append(o)
    return out


def select_models(backtest: dict, teams: Sequence[str], candidates: Sequence[str]) -> dict[str, dict]:
    """team -> {model, wape, mae, bias, scored} or {} when no candidate was scored. Most scored origins
    first (a candidate never beats another on fewer opportunities), then lowest WAPE, then candidate
    order."""
    out: dict[str, dict] = {}
    for team in teams:
        scored = []
        for i, name in enumerate(candidates):
            summ = (backtest.get("candidates", {}).get(name, {}).get("summary", {})
                    .get("companies", {}).get(team))
            if not summ or not summ.get("scored"):
                continue
            point = summ.get("point") or {}
            wape = point.get("wape")
            if wape is None or not math.isfinite(wape):
                continue
            scored.append((-summ["scored"], wape, i, name, point, summ["scored"]))
        if not scored:
            out[team] = {}
            continue
        _, wape, _, name, point, n = min(scored)
        out[team] = {"model": name, "wape": wape, "mae": point.get("mae"), "bias": point.get("bias"), "scored": n}
    return out


def to_cents(values: Sequence[float]) -> list[int]:
    """Float daily dollars -> whole cents, floored at 0 (spend has no negative days)."""
    return [max(0, int(round(v * 100))) for v in values]


def split_daily(team_daily: list[tuple[date, int]], ta: TeamAttribution) -> tuple[list[tuple[Hashable, int]], dict]:
    """Split each day's team cents over people (and the team-level bucket) by spend-to-date cents.
    Returns (weights, key -> [cents per day]). Exact: per day, the parts sum to the team amount."""
    members = sorted(ta.people)
    weights: list[tuple[Hashable, int]] = [(p, int(ta.people[p] * 100)) for p in members]
    if ta.team_level > 0:
        weights.append((BUCKET, int(ta.team_level * 100)))
    if sum(w for _, w in weights) == 0:
        weights = [(p, 1) for p in members] or [(BUCKET, 1)]
    parts: dict[Hashable, list[int]] = {k: [] for k, _ in weights}
    for _, cents in team_daily:
        split = largest_remainder(cents, weights) if cents else {k: 0 for k, _ in weights}
        for k, _ in weights:
            parts[k].append(split[k])
    return weights, parts


# ---- cache -------------------------------------------------------------------------------------


@dataclass
class TeamFit:
    model: str
    validated: bool
    wape: float | None
    mae: float | None
    bias: float | None
    scored: int
    history_start: date
    history_days: int
    zero_filled: int
    future: dict[date, int]           # model cents per day, history_end .. period end
    seat_cents: int                   # latest month's seat fees, carried to each remaining 1st
    seat_month: str | None


@dataclass
class ModelRun:
    period_id: str
    period_end: date
    history_end: date                 # first day NOT in history (the latest record's date)
    horizon: int
    origins: int
    computed_at: datetime
    elapsed_ms: int
    checked_rowid: int                # every row up to here was in (or irrelevant to) this run's history
    fingerprint: tuple = ()           # active teams + per-team (count, cents) of the history it read
    input_gen: tuple = ()             # compat.cache.table_generation(...) when `fingerprint` was last confirmed
    teams: dict[str, TeamFit] = field(default_factory=dict)
    skipped: dict[str, str] = field(default_factory=dict)
    stale: bool = False               # late rows landed on a complete day after this run


class ForecastingPackageProvider:
    name = NAME
    supports_attribution = True

    def __init__(self, session_factory=None, clock=None) -> None:
        self._session_factory = session_factory
        self._clock = clock
        self._lock = threading.Lock()
        self._runs: dict[str, ModelRun] = {}
        self._pending: set[tuple] = set()
        self._failed: set[tuple] = set()
        self._results: dict[tuple, ForecastResult] = {}
        # One worker runs every model run, background and refresh() alike, so runs land in the order they
        # were requested and an older run can never overwrite a newer one.
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="forecast-model")
        self.last_error: str | None = None

    # -- wiring --

    def bind(self, session_factory, clock=None, *, prefetch: bool = True) -> None:
        """Called by create_app: the provider reads history with its own sessions. `prefetch` starts the
        first model run in the background so the first page load usually finds it ready."""
        self._session_factory, self._clock = session_factory, clock or self._clock
        if prefetch and _forecasting() is not None:
            self._submit(None)

    def _now(self) -> datetime:
        return self._clock.now() if self._clock is not None else datetime.now(timezone.utc)

    # -- model run --

    def refresh(self, period_id: str | None = None) -> ModelRun | None:
        """Recompute now and wait for it. None if the package is missing or the database has no period
        yet. Runs on the provider's single model worker (after any background run already queued), so a
        background run that read older data cannot finish later and replace this one."""
        return self._executor.submit(self._refresh_now, period_id).result()

    def _refresh_now(self, period_id: str | None = None) -> ModelRun | None:
        """Compute and store a run, in the model worker thread only."""
        lib = _forecasting()
        if lib is None or self._session_factory is None:
            return None
        run = self._compute(period_id, lib)
        if run is not None:
            with self._lock:
                self._runs[run.period_id] = run
                self._failed.clear()
                self._results = {k: v for k, v in self._results.items() if k[0] != run.period_id}
        return run

    def _submit(self, period_id: str | None, key: tuple | None = None) -> None:
        key = key or ("startup", period_id)
        with self._lock:
            # One run at a time; a key whose run failed is not retried on every request (refresh() can).
            if self._pending or key in self._failed:
                return
            self._pending.add(key)

        def job():
            try:
                self._refresh_now(period_id)
                self.last_error = None
            except Exception as exc:  # noqa: BLE001 - a failed run leaves the old cache; reported below
                self.last_error = f"{type(exc).__name__}: {exc}"
                with self._lock:
                    self._failed.add(key)
            finally:
                with self._lock:
                    self._pending.discard(key)

        self._executor.submit(job)

    def wait_idle(self, timeout: float = 30.0) -> None:
        """Test helper: wait until queued background runs have finished."""
        self._executor.submit(lambda: None).result(timeout=timeout)

    def _compute(self, period_id: str | None, lib) -> ModelRun | None:
        from app.db.models import Team
        from app.services.coverage import resolve_period
        from app.core.errors import DomainError

        models, evaluation = lib
        t0 = time.perf_counter()
        input_gen = _input_generation()  # read before the data: a change in between is caught next check
        with self._session_factory() as session:
            try:
                period = resolve_period(session, period_id, self._now())
            except DomainError:
                return None
            upto = int(session.execute(_MAX_ROWID_SQL).scalar() or 0)
            last = session.execute(_PERIOD_AS_OF_SQL, {"period": period.id}).scalar()
            history_end = _day(last) if last is not None else period.starts_on
            teams = list(session.scalars(select(Team.id).where(Team.active.is_(True)).order_by(Team.id)))
            rows: dict[str, dict[date, int]] = defaultdict(dict)
            params = {"history_end": history_end.isoformat()}
            for team, day, cents in session.execute(_HISTORY_SQL, params):
                rows[team][date.fromisoformat(day)] = int(cents or 0)
            seats: dict[str, tuple[str, int]] = {}
            for team, month, cents in session.execute(_SEAT_SQL, params):
                if team not in seats or month > seats[team][0]:
                    seats[team] = (month, int(cents or 0))
            period_id, period_end = period.id, period.ends_on
            fingerprint = _fingerprint(session, history_end, teams)

        horizon = max(0, (period_end - history_end).days + 1)   # forecast dates history_end .. period_end
        series = build_series({t: rows[t] for t in teams if t in rows}, history_end)
        run = ModelRun(period_id=period_id, period_end=period_end, history_end=history_end, horizon=horizon,
                       origins=0, computed_at=self._now(), elapsed_ms=0, checked_rowid=upto,
                       fingerprint=fingerprint, input_gen=input_gen)
        for t in teams:
            if t not in series:
                run.skipped[t] = f"no counted spend history before {history_end.isoformat()}"
        if horizon == 0 or not series:
            run.elapsed_ms = int((time.perf_counter() - t0) * 1000)
            return run

        objs = {t: models.Series(t, tuple(d), tuple(v)) for t, (d, v, _) in series.items()}
        earliest = min(d[0] for d, _, _ in series.values())
        origins = backtest_origins(history_end, horizon, earliest)
        run.origins = len(origins)
        choice: dict[str, dict] = {t: {} for t in objs}
        if origins:
            bt = evaluation.evaluate_rolling(list(objs.values()), origins, horizon, list(CANDIDATES),
                                             score_as_of=_midnight(history_end))
            choice = select_models(bt, list(objs), CANDIDATES)
        future_dates = tuple(history_end + timedelta(days=i) for i in range(horizon))
        for t, s in objs.items():
            picked = choice.get(t) or {}
            order = ([picked["model"]] if picked else []) + [m for m in FALLBACK_ORDER if not picked or m != picked["model"]]
            for name in order:
                if not models.eligibility(s, name).eligible:
                    continue
                try:
                    pred = models.forecast(s, future_dates, name)
                except (models.ModelUnavailable, ValueError):
                    continue
                validated = bool(picked) and name == picked["model"]
                dates, values, filled = series[t]
                seat_month, seat_cents = seats.get(t, (None, 0))
                run.teams[t] = TeamFit(
                    model=name, validated=validated,
                    wape=picked.get("wape") if validated else None, mae=picked.get("mae") if validated else None,
                    bias=picked.get("bias") if validated else None, scored=picked.get("scored", 0) if validated else 0,
                    history_start=dates[0], history_days=len(dates), zero_filled=filled,
                    future=dict(zip(pred.dates, to_cents(pred.daily_values))),
                    seat_cents=seat_cents, seat_month=seat_month,
                )
                break
            else:
                run.skipped[t] = "no forecasting model is eligible for this team's history"
        run.elapsed_ms = int((time.perf_counter() - t0) * 1000)
        return run

    # -- freshness (cheap, per request) --

    def _check_inputs(self, run: ModelRun) -> None:
        """Marks the run stale when an in-place change altered what it was fitted on: a team mapping
        change re-attributes existing rows with an UPDATE (no new rowid, same history_end), and a team
        (de)activation changes the team set. Cheap: the fingerprint query runs only after such a write
        in this process (compat.cache.table_generation)."""
        if self._session_factory is None or run.stale:
            return
        gen = _input_generation()
        if gen == run.input_gen:
            return
        from app.db.models import Team

        with self._session_factory() as session:
            teams = list(session.scalars(select(Team.id).where(Team.active.is_(True)).order_by(Team.id)))
            current = _fingerprint(session, run.history_end, teams)
        if current != run.fingerprint:
            run.stale = True
        else:
            run.input_gen = gen

    def _check_late_rows(self, run: ModelRun) -> None:
        """Marks the run stale when rows for a complete day arrived after it (or the table shrank: a
        reset). Scans only rows newer than the last check, by rowid."""
        if self._session_factory is None or run.stale:
            return
        with self._session_factory() as session:
            upto = int(session.execute(_MAX_ROWID_SQL).scalar() or 0)
            if upto == run.checked_rowid:
                return
            if upto < run.checked_rowid:
                run.stale = True
                return
            late = session.execute(_LATE_ROWS_SQL, {"after": run.checked_rowid, "upto": upto,
                                                    "history_end": run.history_end.isoformat()}).first()
        if late is not None:
            run.stale = True
        else:
            run.checked_rowid = upto

    # -- request path --

    def get_forecast(self, period_id: str, team_ids: Sequence[str],
                     attribution: Attribution | None = None) -> ForecastResult:
        teams = sorted(team_ids)

        def unavailable(reason: str) -> ForecastResult:
            return ForecastResult(provider=self.name, availability="unavailable", reason=reason,
                                  target_period=period_id, projections=[], missing_teams=teams,
                                  method_label=METHOD_LABEL, value_kind="estimated",
                                  as_of=attribution.as_of if attribution is not None else None)

        if _forecasting() is None:
            return unavailable(NOT_INSTALLED)
        if attribution is None:
            return unavailable("forecasting package provider needs recorded spend to date (attribution)")
        today = attribution.as_of
        wanted_end = today if today is not None else attribution.period_start
        with self._lock:
            run = self._runs.get(period_id)
        if run is not None:
            self._check_inputs(run)
            self._check_late_rows(run)
        usable = run is not None and run.history_end <= wanted_end
        if run is None or run.history_end != wanted_end or run.stale:
            self._submit(period_id, key=(period_id, wanted_end, run.checked_rowid if run else None,
                                         run.input_gen if run else None))
        if not usable:
            return unavailable(self.last_error and f"{COMPUTING} (last run failed: {self.last_error})" or COMPUTING)

        key = (period_id, id(run), run.history_end, run.stale, tuple(teams), _attr_key(attribution))
        with self._lock:
            cached = self._results.get(key)
        if cached is not None:
            return cached
        result = self._build(run, period_id, teams, attribution)
        with self._lock:
            if len(self._results) > 64:
                self._results.clear()
            self._results[key] = result
        return result

    def _build(self, run: ModelRun, period_id: str, teams: list[str], attr: Attribution) -> ForecastResult:
        today = attr.as_of
        first = attr.period_start if today is None else max(attr.period_start, today + timedelta(days=1))
        days = [first + timedelta(days=i) for i in range((attr.period_end - first).days + 1)]
        refit_note = None
        if run.history_end < (today or attr.period_start) or run.stale:
            refit_note = (f"model fitted on history through {(run.history_end - timedelta(days=1)).isoformat()}; "
                          "a refit on the newer data is running in the background")
        projections, people, missing = [], [], []
        for team in teams:
            fit, ta = run.teams.get(team), attr.teams.get(team)
            if fit is None or ta is None:
                missing.append(team)
                continue
            team_daily = [(d, fit.future.get(d, 0) + (fit.seat_cents if d.day == 1 else 0)) for d in days]
            spent = sum(ta.people.values(), Decimal("0")) + ta.team_level
            future_cents = sum(c for _, c in team_daily)
            amount = spent + Decimal(future_cents).scaleb(-2)
            seat_days = [d for d in days if d.day == 1]
            assumptions = [
                (f"{fit.model} chosen by rolling backtest on history only ({fit.scored} weekly origins, "
                 f"{run.horizon}-day horizon, WAPE {_pct(fit.wape)})") if fit.validated else
                (f"{fit.model} used without a backtest: too little history for a {run.horizon}-day backtest origin"),
                (f"projected = recorded spend to date (including {today.isoformat()} so far) + model forecast for "
                 f"{days[0].isoformat()}..{days[-1].isoformat()}") if today and days else
                "projected = recorded spend to date; no days remain in the period",
                (f"history: counted spend without seat fees, {fit.history_start.isoformat()}.."
                 f"{(run.history_end - timedelta(days=1)).isoformat()} ({fit.history_days} complete days"
                 + (f", {fit.zero_filled} days without records counted as zero" if fit.zero_filled else "")
                 + f"); {run.history_end.isoformat()} is partial and not used for fitting"),
                DEPENDENCY_NOTE,
                EVENTS_NOTE,
            ]
            if seat_days and fit.seat_cents:
                assumptions.append(f"seat fees carried from {fit.seat_month} "
                                   f"(${Decimal(fit.seat_cents).scaleb(-2)}) on {', '.join(d.isoformat() for d in seat_days)}")
            if refit_note:
                assumptions.append(refit_note)
            # The package scores one prediction per origin: the sum over the whole backtest horizon. So
            # MAE is the error of a {horizon}-day total, not a daily error.
            uncertainty = (f"backtest WAPE {_pct(fit.wape)} at this horizon (MAE ${fit.mae:,.2f} on the "
                           f"{run.horizon}-day total); no prediction interval" if fit.validated and fit.mae is not None
                           else "not validated by a backtest; no prediction interval")
            uncertainty += "; the remaining hours of today are not forecast"
            daily = None
            if days:
                weights, parts = split_daily(team_daily, ta)
                daily = [DailyProjection(date=d, amount=Decimal(c).scaleb(-2)) for d, c in team_daily]
                total_w = sum(w for _, w in weights)
                proportional = spent > 0
                weight_of = dict(weights)
                for p in sorted(ta.people):
                    share = _share_text(weight_of[p], total_w)
                    basis = (f"share of the team projection in proportion to recorded spend to date ({share}% of team spend)"
                             if proportional else f"equal share of the team projection ({share}%); no recorded spend to date")
                    people.append(PersonProjection(
                        person=p, team=team, amount=ta.people[p] + Decimal(sum(parts[p])).scaleb(-2),
                        spent_to_date=ta.people[p], share=share,
                        daily=[DailyProjection(date=d, amount=Decimal(c).scaleb(-2)) for d, c in zip(days, parts[p])],
                        assumptions=[basis, "full-period total, includes spend to date",
                                     f"team model: {fit.model}"],
                        uncertainty=PERSON_UNCERTAINTY,
                    ))
            else:
                for p in sorted(ta.people):
                    people.append(PersonProjection(
                        person=p, team=team, amount=ta.people[p], spent_to_date=ta.people[p], share="0.0",
                        assumptions=["no days remain in the period: projection equals recorded spend"],
                        uncertainty=PERSON_UNCERTAINTY,
                    ))
            projections.append(TeamProjection(team=team, amount=amount, assumptions=assumptions,
                                              uncertainty=uncertainty, daily=daily))
        reasons = [f"{t}: {run.skipped.get(t, 'no model output for this team')}" for t in missing]
        availability = "unavailable" if not projections else "partial" if missing else "available"
        return ForecastResult(
            provider=self.name, availability=availability, reason="; ".join(reasons) or None,
            target_period=period_id, basis="full_period_total", projections=projections, missing_teams=missing,
            value_kind="estimated", method_label=METHOD_LABEL, person_projections=people, as_of=today,
            # When this projection was built (it is reused until recorded spend or the run changes), so
            # repeated reads of an unchanged projection are identical and the compat render cache hits.
            generated_at=self._now(),
        )

    # -- reporting --

    def status(self, period_id: str | None = None) -> dict:
        with self._lock:
            runs = dict(self._runs)
        run = runs.get(period_id) if period_id else (max(runs.values(), key=lambda r: r.computed_at) if runs else None)
        return run_summary(self.name, run, self.last_error)


def _input_generation() -> tuple:
    """In-process write counter for in-place usage changes and any teams write (compat/cache.py)."""
    from app.compat import cache

    return cache.table_generation("usage_records") + cache.table_generation("teams", inserts=True)


def _fingerprint(session, history_end: date, teams: Sequence[str]) -> tuple:
    rows = session.execute(_FINGERPRINT_SQL, {"history_end": history_end.isoformat()})
    return (tuple(teams), tuple(sorted((t, int(seat), int(n), int(c or 0)) for t, seat, n, c in rows)))


def _attr_key(attr: Attribution) -> tuple:
    return (attr.as_of, attr.period_start, attr.period_end,
            tuple((t, tuple(sorted(ta.people.items())), ta.team_level) for t, ta in sorted(attr.teams.items())))


def run_summary(provider: str, run: ModelRun | None, error: str | None = None) -> dict:
    if run is None:
        return {"provider": provider, "refreshed": False,
                "reason": error or "no model run yet (no period or no forecasting package)", "teams": []}
    return {
        "provider": provider, "refreshed": True, "reason": None, "period": run.period_id,
        "history_end": run.history_end, "horizon_days": run.horizon, "backtest_origins": run.origins,
        "computed_at": run.computed_at, "elapsed_ms": run.elapsed_ms,
        "teams": [{"team": t, "model": f.model, "validated": f.validated,
                   "wape": None if f.wape is None else f"{f.wape:.4f}", "scored_origins": f.scored,
                   "history_days": f.history_days} for t, f in sorted(run.teams.items())],
        "skipped": [{"team": t, "reason": r} for t, r in sorted(run.skipped.items())],
    }
