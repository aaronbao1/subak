"""ForecastProvider interface and the shared Northstar placeholder (design.md §6).

This is NOT a forecasting model. The forecasting teammate plugs a real provider in behind
`ForecastProvider`; until then `PlaceholderForecastProvider` returns the shared Northstar projections
(research 85k, product 50k, engineering 65k for 2026-P1), labeled `simulated`, or an honest
`unavailable` result.

With an `Attribution` (spend to date per team and person) the placeholder also splits each team
placeholder across the team's people in proportion to their recorded spend to date, and spreads the
remaining amount over the days after the data as-of (frontend-integration-design §4). That split is
arithmetic on the shared placeholder, not a person-level forecast, and is labeled as such.
"""

from __future__ import annotations

import math
from collections.abc import Hashable, Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from fractions import Fraction
from typing import Literal, Protocol, runtime_checkable

from app.schemas.forecasts import DailyProjection, ForecastResult, PersonProjection, TeamProjection

PLACEHOLDER_PERIOD = "2026-P1"
PLACEHOLDER_PROJECTIONS: dict[str, Decimal] = {
    "research": Decimal("85000.00"),
    "product": Decimal("50000.00"),
    "engineering": Decimal("65000.00"),
}
PLACEHOLDER_METHOD = "shared placeholder (not a forecast model)"
UNAVAILABLE_REASON = "forecast provider not connected"
PERSON_SPLIT_UNCERTAINTY = "person split is proportional to spend to date; not a person-level model"
BELOW_SPEND_LIMITATION = "placeholder is below recorded spend"
WEEKDAY_WEIGHT, WEEKEND_WEIGHT = 3, 1
CENT = Decimal("0.01")


@dataclass(frozen=True)
class TeamAttribution:
    team: str
    people: dict[str, Decimal]      # active member id -> counted spend to date (0 if none)
    team_level: Decimal = Decimal("0")  # counted spend with no (member) person


@dataclass(frozen=True)
class Attribution:
    as_of: date | None              # max occurred_at date of counted records in the period
    period_start: date
    period_end: date
    teams: dict[str, TeamAttribution] = field(default_factory=dict)


class _Bucket:
    """The team-level key in a split. Sorts after every person id; never emitted as a person."""

    def __repr__(self) -> str:
        return "BUCKET"


BUCKET = _Bucket()


def largest_remainder(total: int, weights: Sequence[tuple[Hashable, int]]) -> dict[Hashable, int]:
    """Split `total` whole units over `weights` (in tie-break order) so the parts sum exactly to total.

    q_i = total * w_i / W; a_i = floor(q_i); the leftover units go to the largest fractional parts,
    ties -> earlier position in `weights`. Pure and deterministic.
    """
    if total < 0:
        raise ValueError("total must be >= 0")
    if any(w < 0 for _, w in weights):
        raise ValueError("weights must be >= 0")
    big_w = sum(w for _, w in weights)
    if big_w == 0:
        raise ValueError("weights must not all be zero")
    quotas = [(k, Fraction(total * w, big_w)) for k, w in weights]
    parts = {k: math.floor(q) for k, q in quotas}
    left = total - sum(parts.values())
    order = sorted(range(len(quotas)), key=lambda i: (-(quotas[i][1] - parts[quotas[i][0]]), i))
    for i in order[:left]:
        parts[quotas[i][0]] += 1
    return parts


def remaining_days(attr: Attribution) -> list[date]:
    """as_of + 1 .. period_end (or the whole period when as_of is None); [] once the period is over."""
    start = attr.period_start if attr.as_of is None else max(attr.period_start, attr.as_of + timedelta(days=1))
    return [start + timedelta(days=i) for i in range((attr.period_end - start).days + 1)]


def _day_weight(d: date) -> int:
    return WEEKDAY_WEIGHT if d.weekday() < 5 else WEEKEND_WEIGHT


def _spread(amount: Decimal, days: list[date]) -> list[Decimal]:
    """Whole dollars by largest remainder over weekday-weighted days; leftover cents on the first day."""
    whole = int(amount // 1)
    parts = largest_remainder(whole, [(d, _day_weight(d)) for d in days])
    out = [Decimal(parts[d]) for d in days]
    out[0] += amount - whole
    return out


def _cents(value: Decimal) -> int:
    return int((value / CENT).to_integral_value())


def _share_text(weight: int, total: int) -> str:
    pct = (Decimal(weight) * 100 / Decimal(total)).quantize(Decimal("0.1"), rounding="ROUND_HALF_EVEN")
    return format(pct, "f")


def split_team(team: str, placeholder: Decimal, ta: TeamAttribution, days: list[date]):
    """Returns (team_daily | None, [PersonProjection], below_spend: bool) for one team (design §4.2).

    Invariants (exact Decimal): sum(P_p) + P_0 == placeholder; spent_p + sum(daily_p) == P_p;
    S + sum(team_daily) == placeholder; team_daily[d] == sum_p daily_p[d] + daily_0[d].
    """
    members = sorted(ta.people)
    spent = sum(ta.people.values(), Decimal("0")) + ta.team_level
    remaining = placeholder - spent
    if remaining < 0:
        return None, [], True
    weights: list[tuple[Hashable, int]] = [(p, _cents(ta.people[p])) for p in members]
    if ta.team_level > 0:
        weights.append((BUCKET, _cents(ta.team_level)))
    proportional = sum(w for _, w in weights) > 0
    if not proportional:
        weights = [(p, 1) for p in members] or [(BUCKET, 1)]
    whole = int(remaining // 1)
    rem = {k: Decimal(v) for k, v in largest_remainder(whole, weights).items()}
    # leftover cents go to the key with the largest weight (ties -> id ascending, bucket last)
    top = min(range(len(weights)), key=lambda i: (-weights[i][1], i))
    rem[weights[top][0]] += remaining - whole
    total_w = sum(w for _, w in weights)

    daily: dict[Hashable, list[Decimal]] = {k: _spread(rem[k], days) for k, _ in weights} if days else {}
    team_daily = None
    if days:
        team_daily = [DailyProjection(date=d, amount=sum((daily[k][i] for k, _ in weights), Decimal("0")))
                      for i, d in enumerate(days)]
    weight_of = dict(weights)
    people = []
    for p in members:
        share = _share_text(weight_of[p], total_w)
        basis = (f"share of the team placeholder in proportion to recorded spend to date ({share}% of team spend)"
                 if proportional else f"equal share of the team placeholder ({share}%); no recorded spend to date")
        people.append(PersonProjection(
            person=p, team=team, amount=ta.people[p] + rem[p], spent_to_date=ta.people[p], share=share,
            daily=[DailyProjection(date=d, amount=a) for d, a in zip(days, daily[p])] if days else None,
            assumptions=[basis, "full-period total, includes spend to date"],
            uncertainty=f"placeholder value; {PERSON_SPLIT_UNCERTAINTY}",
        ))
    return team_daily, people, False


@runtime_checkable
class ForecastProvider(Protocol):
    name: str

    def get_forecast(self, period_id: str, team_ids: Sequence[str]) -> ForecastResult: ...


class PlaceholderForecastProvider:
    """Shared Northstar placeholder projections. NOT a model.

    `supports_attribution = True`: the forecast service then passes `attribution=` so the placeholder
    can add the per-person split and daily points. Providers without the flag keep the 2-argument call.
    """

    name = "placeholder"
    supports_attribution = True

    def __init__(self, mode: Literal["available", "unavailable"] = "available") -> None:
        if mode not in ("available", "unavailable"):
            raise ValueError(f"unknown placeholder mode {mode!r}")
        self.mode = mode

    def get_forecast(self, period_id: str, team_ids: Sequence[str],
                     attribution: Attribution | None = None) -> ForecastResult:
        if self.mode == "unavailable":
            return ForecastResult(
                provider=self.name, availability="unavailable", reason=UNAVAILABLE_REASON,
                target_period=period_id, projections=[], missing_teams=sorted(team_ids),
                method_label=PLACEHOLDER_METHOD,
            )
        if period_id != PLACEHOLDER_PERIOD:
            return ForecastResult(
                provider=self.name, availability="unavailable",
                reason=f"no placeholder projections exist for period {period_id!r}",
                target_period=period_id, projections=[], missing_teams=sorted(team_ids),
                method_label=PLACEHOLDER_METHOD,
            )
        projections = [
            TeamProjection(
                team=t, amount=PLACEHOLDER_PROJECTIONS[t],
                assumptions=["shared Northstar sample projection agreed across workstreams",
                             "full-period total for the planning period, not a remaining amount"],
                uncertainty="placeholder value; no model or historical fit behind it",
            )
            for t in sorted(team_ids) if t in PLACEHOLDER_PROJECTIONS
        ]
        person_projections: list[PersonProjection] = []
        if attribution is not None:
            days = remaining_days(attribution)
            for i, tp in enumerate(projections):
                ta = attribution.teams.get(tp.team)
                if ta is None:
                    continue
                team_daily, people, below = split_team(tp.team, tp.amount, ta, days)
                update: dict = {"daily": team_daily}
                if below:
                    update["uncertainty"] = f"{tp.uncertainty}; {BELOW_SPEND_LIMITATION}"
                projections[i] = tp.model_copy(update=update)
                person_projections.extend(people)
        missing = sorted(t for t in team_ids if t not in PLACEHOLDER_PROJECTIONS)
        if not projections:
            availability, reason = "unavailable", "no placeholder projections for the requested teams"
        elif missing:
            availability, reason = "partial", f"no placeholder projection for: {', '.join(missing)}"
        else:
            availability, reason = "available", None
        return ForecastResult(
            provider=self.name, availability=availability, reason=reason, target_period=period_id,
            basis="full_period_total", projections=projections, missing_teams=missing,
            value_kind="simulated", method_label=PLACEHOLDER_METHOD,
            person_projections=person_projections,
            as_of=attribution.as_of if attribution is not None else None,
        )


def provider_from_settings(name: str) -> ForecastProvider:
    """`FORECAST_PROVIDER=placeholder|unavailable` (validated in Settings)."""
    if name == "unavailable":
        return PlaceholderForecastProvider(mode="unavailable")
    return PlaceholderForecastProvider(mode="available")
