"""Calls the configured ForecastProvider and never lets it break spend or budget views (design.md §6).

- Exceptions, timeouts and malformed provider output become an `unavailable` result whose `reason`
  says what happened. Projections are never zero-filled.
- Results are sanity-checked: wrong period, non-USD units, negative or duplicate projections and
  unknown teams make the result unavailable (or partial when only some teams are affected).
- Person projections (an optional split of the team projections) are kept for a team only when they
  reconcile exactly with the kept team projection; otherwise they are dropped with a reason, never
  "fixed" (frontend-integration-design §4.1).
- `snapshot` persists a result so proposals/decisions can cite exactly what they relied on.
"""

from __future__ import annotations

import concurrent.futures
import functools
from collections import defaultdict
from collections.abc import Sequence
from decimal import Decimal

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import Clock, IdFactory
from app.core.errors import DomainError
from app.db.models import ForecastSnapshot, Person, PlanningPeriod, Team, UsageRecord
from app.providers.forecast import Attribution, ForecastProvider, TeamAttribution
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


def _person_split_problem(tp, people: list, attr: Attribution | None) -> str | None:
    """Why this team's person split does not reconcile with its kept team projection, or None."""
    ta = attr.teams.get(tp.team) if attr is not None else None
    ids = [pp.person for pp in people]
    if len(set(ids)) != len(ids):
        return "duplicate person"
    if ta is not None and any(i not in ta.people for i in ids):
        return "person not a member of the team"
    if any(pp.amount < 0 or pp.spent_to_date < 0 or pp.unit != tp.unit for pp in people):
        return "negative or non-USD person amount"
    if ta is not None and any(pp.spent_to_date != ta.people[pp.person] for pp in people):
        return "spend to date differs from the recorded spend"
    p0 = tp.amount - sum((pp.amount for pp in people), Decimal("0"))
    team_level = ta.team_level if ta is not None else Decimal("0")
    if p0 < team_level or (team_level == 0 and p0 != 0):
        return "person amounts do not add up to the team amount"
    team_daily = {d.date: d.amount for d in tp.daily or []}
    if len(team_daily) != len(tp.daily or []):
        return "duplicate daily dates"
    per_day: dict = defaultdict(Decimal)
    for pp in people:
        if pp.daily is None:
            if tp.daily is not None:
                return "missing person daily points"
            continue
        if [d.date for d in pp.daily] != [d.date for d in tp.daily or []]:
            return "person daily dates differ from the team"
        if pp.spent_to_date + sum((d.amount for d in pp.daily), Decimal("0")) != pp.amount:
            return "person daily points do not add up"
        for d in pp.daily:
            per_day[d.date] += d.amount
    if any(v > team_daily[d] or v < 0 for d, v in per_day.items()) or any(v < 0 for v in team_daily.values()):
        return "person daily points exceed the team"
    if tp.daily is not None and ta is not None:
        spent = sum(ta.people.values(), Decimal("0")) + ta.team_level
        if spent + sum(team_daily.values(), Decimal("0")) != tp.amount:
            return "team daily points do not add up"
    return None


def _sanitize_people(result: ForecastResult, kept: list, attr: Attribution | None) -> tuple[list, list[str]]:
    by_team: dict[str, list] = defaultdict(list)
    for pp in result.person_projections:
        by_team[pp.team].append(pp)
    kept_by_team = {tp.team: tp for tp in kept}
    out, problems = [], []
    for team in sorted(by_team):
        tp = kept_by_team.get(team)
        if tp is None:
            continue
        why = _person_split_problem(tp, by_team[team], attr)
        if why:
            problems.append(f"person split did not reconcile for {team} ({why})")
        else:
            out.extend(sorted(by_team[team], key=lambda pp: pp.person))
    return out, problems


def _sanitize(result: ForecastResult, provider: object, period_id: str, team_ids: Sequence[str], now,
              attribution: Attribution | None = None) -> ForecastResult:
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
        # An incomplete issued quarter still has an immutable evidence receipt.
        # Preserve its lineage while withholding unsupported monetary projections.
        return result.model_copy(update={"availability": "unavailable", "reason": reason,
                                         "projections": [], "person_projections": [], "as_of": None,
                                         "missing_teams": sorted(team_ids),
                                         "generated_at": result.generated_at or now})
    availability = "available" if not missing and result.availability == "available" else "partial"
    people, people_problems = _sanitize_people(result, kept, attribution)
    reasons = [r for r in [result.reason, *problems, *people_problems] if r]
    if missing and not result.reason:
        reasons.insert(0, f"no projection for: {', '.join(missing)}")
    return result.model_copy(update={
        "availability": availability,
        "reason": "; ".join(reasons) or None,
        "projections": sorted(kept, key=lambda p: p.team),
        "missing_teams": missing,
        "generated_at": result.generated_at or now,
        "person_projections": people,
    })


def get_forecast(
    provider: ForecastProvider,
    period_id: str,
    team_ids: Sequence[str],
    *,
    clock: Clock,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    attribution: Attribution | None = None,
) -> ForecastResult:
    """Never raises: any provider failure is reported as `availability: unavailable`.

    `attribution` reaches the provider only if it sets `supports_attribution = True`.
    """
    now = clock.now()
    teams = sorted(team_ids)
    call = provider.get_forecast
    if attribution is not None and getattr(provider, "supports_attribution", False):
        call = functools.partial(provider.get_forecast, attribution=attribution)
    else:
        attribution = None
    try:
        future = _executor.submit(call, period_id, teams)
        raw = future.result(timeout=timeout)
    except concurrent.futures.TimeoutError:
        return unavailable(provider, period_id, teams, f"forecast provider timed out after {timeout:g}s", now)
    except Exception as exc:  # noqa: BLE001 - the point is to contain provider failures
        return unavailable(provider, period_id, teams, f"forecast provider error: {type(exc).__name__}: {exc}", now)
    try:
        result = raw if isinstance(raw, ForecastResult) else ForecastResult.model_validate(raw)
    except (ValidationError, TypeError, ValueError) as exc:
        return unavailable(provider, period_id, teams, f"forecast provider returned malformed output: {exc}", now)
    return _sanitize(result, provider, period_id, teams, now, attribution)


def active_team_ids(session: Session) -> list[str]:
    return list(session.scalars(select(Team.id).where(Team.active.is_(True)).order_by(Team.id)))


def attribution_for_period(session: Session, period: PlanningPeriod, team_ids: Sequence[str]) -> Attribution:
    """Counted spend to date per active team and active member; anything else on the team is team-level."""
    members: dict[str, dict[str, Decimal]] = {t: {} for t in team_ids}
    for pid, team in session.execute(
        select(Person.id, Person.team_id).where(Person.active.is_(True), Person.team_id.in_(list(team_ids)))
    ):
        members[team][pid] = Decimal("0")
    team_level = {t: Decimal("0") for t in team_ids}
    as_of = None
    rows = session.execute(
        select(UsageRecord.team_id, UsageRecord.person_id, UsageRecord.amount, UsageRecord.occurred_at)
        .where(UsageRecord.period_id == period.id, UsageRecord.counts_toward_spend.is_(True),
               UsageRecord.amount.is_not(None))
    )
    for team, person, amount, occurred in rows:
        day = occurred.date()
        as_of = day if as_of is None or day > as_of else as_of
        if team is None or team not in members:  # unmapped spend only moves as_of
            continue
        if person is not None and person in members[team]:
            members[team][person] += amount
        else:
            team_level[team] += amount
    return Attribution(
        as_of=as_of, period_start=period.starts_on, period_end=period.ends_on,
        teams={t: TeamAttribution(team=t, people=members[t], team_level=team_level[t]) for t in team_ids},
    )


def forecast_for_period(session: Session, provider: ForecastProvider, period: PlanningPeriod, *, clock: Clock) -> ForecastResult:
    teams = active_team_ids(session)
    attribution = (attribution_for_period(session, period, teams)
                   if getattr(provider, "supports_attribution", False) else None)
    return get_forecast(provider, period.id, teams, clock=clock, attribution=attribution)


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
