"""Calls the configured ForecastProvider and never lets it break spend or budget views (design.md §6).

- Exceptions, timeouts and malformed provider output become an `unavailable` result whose `reason`
  says what happened. Projections are never zero-filled.
- Results are sanity-checked: wrong period, non-USD units, negative or duplicate projections and
  unknown teams make the result unavailable (or partial when only some teams are affected).
- `snapshot` persists a result so proposals/decisions can cite exactly what they relied on.
"""

from __future__ import annotations

import concurrent.futures
from collections.abc import Sequence
from decimal import Decimal

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import Clock, IdFactory
from app.core.errors import DomainError
from app.db.models import ForecastSnapshot, PlanningPeriod, Team
from app.providers.forecast import ForecastProvider
from app.schemas.forecasts import ForecastResult

DEFAULT_TIMEOUT_SECONDS = 5.0
_executor = concurrent.futures.ThreadPoolExecutor(max_workers=4, thread_name_prefix="forecast")


def _provider_name(provider: object) -> str:
    return str(getattr(provider, "name", type(provider).__name__))


def unavailable(provider: object, period_id: str, team_ids: Sequence[str], reason: str, now=None) -> ForecastResult:
    return ForecastResult(
        provider=_provider_name(provider), availability="unavailable", reason=reason, target_period=period_id,
        projections=[], missing_teams=sorted(team_ids), method_label="unavailable", generated_at=now,
    )


def _sanitize(result: ForecastResult, provider: object, period_id: str, team_ids: Sequence[str], now) -> ForecastResult:
    if result.target_period != period_id:
        return unavailable(provider, period_id, team_ids,
                           f"provider answered for period {result.target_period!r}, not {period_id!r}", now)
    known = set(team_ids)
    kept, problems, seen = [], [], set()
    for p in result.projections:
        if p.team not in known:
            problems.append(f"unknown team {p.team!r} ignored")
        elif p.team in seen:
            problems.append(f"duplicate projection for {p.team!r} ignored")
        elif p.amount < Decimal("0"):
            problems.append(f"negative projection for {p.team!r} ignored")
        else:
            seen.add(p.team)
            kept.append(p)
    missing = sorted(known - seen)
    if result.availability == "unavailable" or not kept:
        reason = result.reason or "provider returned no usable projections"
        if problems:
            reason = f"{reason}; {'; '.join(problems)}"
        return unavailable(provider, period_id, team_ids, reason, now)
    availability = "available" if not missing and result.availability == "available" else "partial"
    reasons = [r for r in [result.reason, *problems] if r]
    if missing and not result.reason:
        reasons.insert(0, f"no projection for: {', '.join(missing)}")
    return result.model_copy(update={
        "availability": availability,
        "reason": "; ".join(reasons) or None,
        "projections": sorted(kept, key=lambda p: p.team),
        "missing_teams": missing,
        "generated_at": result.generated_at or now,
    })


def get_forecast(
    provider: ForecastProvider,
    period_id: str,
    team_ids: Sequence[str],
    *,
    clock: Clock,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> ForecastResult:
    """Never raises: any provider failure is reported as `availability: unavailable`."""
    now = clock.now()
    teams = sorted(team_ids)
    try:
        future = _executor.submit(provider.get_forecast, period_id, teams)
        raw = future.result(timeout=timeout)
    except concurrent.futures.TimeoutError:
        return unavailable(provider, period_id, teams, f"forecast provider timed out after {timeout:g}s", now)
    except Exception as exc:  # noqa: BLE001 - the point is to contain provider failures
        return unavailable(provider, period_id, teams, f"forecast provider error: {type(exc).__name__}: {exc}", now)
    try:
        result = raw if isinstance(raw, ForecastResult) else ForecastResult.model_validate(raw)
    except (ValidationError, TypeError, ValueError) as exc:
        return unavailable(provider, period_id, teams, f"forecast provider returned malformed output: {exc}", now)
    return _sanitize(result, provider, period_id, teams, now)


def active_team_ids(session: Session) -> list[str]:
    return list(session.scalars(select(Team.id).where(Team.active.is_(True)).order_by(Team.id)))


def forecast_for_period(session: Session, provider: ForecastProvider, period: PlanningPeriod, *, clock: Clock) -> ForecastResult:
    return get_forecast(provider, period.id, active_team_ids(session), clock=clock)


def snapshot(session: Session, result: ForecastResult, *, clock: Clock, ids: IdFactory) -> ForecastSnapshot:
    snap = ForecastSnapshot(
        id=ids.new_id("fcs_"), period_id=result.target_period, provider=result.provider,
        availability=result.availability, payload=result.model_dump(mode="json"),
        fetched_at=clock.now(), created_at=clock.now(),
    )
    session.add(snap)
    session.flush()
    return snap


def snapshot_out(snap: ForecastSnapshot) -> dict:
    return {
        "id": snap.id, "period": snap.period_id, "provider": snap.provider, "availability": snap.availability,
        "fetched_at": snap.fetched_at, "forecast": ForecastResult.model_validate(snap.payload),
    }


def get_snapshot(session: Session, snapshot_id: str) -> ForecastSnapshot:
    snap = session.get(ForecastSnapshot, snapshot_id)
    if snap is None:
        raise DomainError("not_found", 404, f"forecast snapshot {snapshot_id!r} not found")
    return snap
