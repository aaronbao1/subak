"""Daily token usage per person, model and cost category, driven by the calendar, trend and events."""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

from . import config as C
from .events import Event
from .people import Person, Team


@dataclass
class CalendarDay:
    day: date
    weekday: int
    is_weekend: bool
    holiday: Optional[str]
    holiday_factor: float
    seasonal_factor: float
    period_id: Optional[str]
    partial: bool


@dataclass
class UsageRow:
    day: date
    person_id: str
    team_id: str
    provider: str
    model_id: str
    model_name: str
    tool: str
    cost_category: str          # direct_api | billable_overage | included_usage
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int
    reasoning_tokens: int
    requests: int
    cost_usd: float             # charged amount (0 for included usage)
    notional_usd: float         # list value (equals cost for charged rows)


@dataclass
class SeatRow:
    month: date                 # first of month
    person_id: str
    team_id: str
    tool: str
    provider: str
    amount_usd: float


def period_for(d: date) -> Optional[str]:
    for p in C.PERIODS:
        if p["start"] <= d <= p["end"]:
            return p["id"]
    return None


def build_calendar(start: date, end: date) -> dict:
    out = {}
    d = start
    while d <= end:
        wd = d.weekday()
        hol = C.HOLIDAYS.get(d) or C.RECHARGE_DAYS.get(d)
        season = 1.0
        for s, e, f in C.SEASONAL:
            if s <= d <= e:
                season = f
        out[d] = CalendarDay(day=d, weekday=wd, is_weekend=wd >= 5, holiday=hol[0] if hol else None,
                             holiday_factor=hol[1] if hol else 1.0, seasonal_factor=season, period_id=period_for(d),
                             partial=(d == C.AS_OF and not C.COMPLETE_AS_OF_DAY))
        d += timedelta(days=1)
    return out


def trend(d: date, team: Team) -> float:
    """Adoption growth through the year: reaches team.growth x the January level by year end."""
    t = max(0.0, (d - C.YEAR_START).days / 365.0)
    k = 2.2
    smooth = (1 - math.exp(-k * t)) / (1 - math.exp(-k))
    return 1.0 + (team.growth - 1.0) * smooth


def employment(d: date, p: Person) -> float:
    if d < p.start_date:
        return 0.0
    if p.end_date and d > p.end_date:
        return 0.0
    if p.start_date >= C.YEAR_START:
        days = (d - p.start_date).days
        if days < 28:
            return 0.15 + 0.85 * (days / 28.0)
    return 1.0


def applies(ev: Event, p: Person) -> bool:
    if ev.person_ids:
        return p.id in ev.person_ids
    if ev.scope == "company":
        return True
    return p.team_id in ev.team_ids


def model_mix(provider: str, d: date) -> dict:
    timeline = C.MODEL_MIX_TIMELINE[provider]
    cur_idx = 0
    for i, (eff, _mix) in enumerate(timeline):
        if eff <= d:
            cur_idx = i
    eff, cur = timeline[cur_idx]
    if cur_idx == 0:
        return dict(cur)
    prev = timeline[cur_idx - 1][1]
    a = min(1.0, max(0.0, ((d - eff).days + 1) / C.RAMP_DAYS))
    keys = set(cur) | set(prev)
    return {k: prev.get(k, 0.0) * (1 - a) + cur.get(k, 0.0) * a for k in keys}


def prices(model_id: str, d: date):
    _prov, _name, pin, pc, pout, _rel, _reason = C.MODELS[model_id]
    for mid, eff, i, c, o in C.PRICE_CHANGES:
        if mid == model_id and eff <= d:
            pin, pc, pout = i, c, o
    return pin, pc, pout


def provider_weights(p: Person, team: Team, d: date, active_events: list) -> dict:
    w = {prov: team.provider_mix.get(prov, 0.0) * p.provider_tilt[prov] for prov in C.PROVIDERS}
    for eff, shift, _note in C.PROVIDER_POLICY_SHIFTS:
        if d >= eff:
            a = min(1.0, ((d - eff).days + 1) / C.RAMP_DAYS)
            for prov, delta in shift.items():
                w[prov] = max(0.0, w[prov] + delta * a)
    for ev in active_events:
        if ev.provider_shift:
            for prov, delta in ev.provider_shift.items():
                w[prov] = max(0.0, w[prov] + delta)
    # A person works mostly in one or two providers: drop small weights.
    ranked = sorted(w.items(), key=lambda kv: -kv[1])
    keep = {}
    for i, (prov, val) in enumerate(ranked):
        thresh = 0.0 if i == 0 else 0.13
        if val >= thresh:
            keep[prov] = val
    s = sum(keep.values()) or 1.0
    return {k: v / s for k, v in keep.items()}


def split_person_tokens(p: Person, team: Team, d: date, total: float, rnd: random.Random, active: list) -> list:
    """Split one person's token total for day d across providers, models and cost categories."""
    rows: list = []
    weights = provider_weights(p, team, d, active)
    overrides = {}
    for ev in active:
        if ev.model_override:
            overrides.update(ev.model_override)
    tool = p.tool
    if tool == "GitHub Copilot" and d >= date(2026, 10, 1):
        tool = "Cursor"
    tool_cfg = C.TOOLS[tool]
    for prov, pw in weights.items():
        mix = overrides.get(prov) or model_mix(prov, d)
        mix = {m: s for m, s in mix.items() if s >= 0.08}  # keep the main models only, renormalise
        ms = sum(mix.values()) or 1.0
        for model_id, share in mix.items():
            share /= ms
            tok = total * pw * share * rnd.uniform(0.85, 1.15)
            if tok < 200:
                continue
            _prov, name, _pi, _pc, _po, _rel, reasoning = C.MODELS[model_id]
            pin, pc, pout = prices(model_id, d)
            inp = int(tok * p.input_share)
            cached = int(inp * p.cache_rate)
            out = int(tok - inp)
            reason = int(out * 0.35) if reasoning else 0
            cost = (inp - cached) / 1e6 * pin + cached / 1e6 * pc + out / 1e6 * pout
            requests = max(1, int(tok / rnd.uniform(4500, 9000)))
            included = tool_cfg.get("included") and tool_cfg["provider"] == prov
            overage_share = tool_cfg.get("overage_share", 0.0) if prov in ("anthropic", "openai") else 0.0
            parts = []
            if included:
                parts.append(("included_usage", tool_cfg["provider"], 1.0))
            elif overage_share > 0:
                parts.append(("billable_overage", tool_cfg["provider"], overage_share))
                parts.append(("direct_api", prov, 1.0 - overage_share))
            else:
                parts.append(("direct_api", prov, 1.0))
            for cat, prov_label, frac in parts:
                c = round(cost * frac, 2)
                rows.append(UsageRow(
                    day=d, person_id=p.id, team_id=p.team_id, provider=prov_label, model_id=model_id, model_name=name,
                    tool=tool, cost_category=cat, input_tokens=int(inp * frac), cached_input_tokens=int(cached * frac),
                    output_tokens=int(out * frac), reasoning_tokens=int(reason * frac), requests=max(1, int(requests * frac)),
                    cost_usd=0.0 if cat == "included_usage" else c, notional_usd=c,
                ))
    return rows


def generate_usage(teams: list, people: list, events: list, calendar: dict, rnd: random.Random,
                   start: date, end: date, holdout: bool = False) -> tuple:
    """Returns (usage_rows, seat_rows). `holdout` marks the synthetic ground-truth future."""
    team_by_id = {t.id: t for t in teams}
    rows: list = []
    seats: list = []
    person_events = {p.id: [ev for ev in events if applies(ev, p)] for p in people}
    d = start
    while d <= end:
        cal = calendar[d]
        bump = 1.0
        for s, e, f in C.COMPANY_BUMPS:
            if s <= d <= e:
                bump = f
        for p in people:
            team = team_by_id[p.team_id]
            emp = employment(d, p)
            # seats on the first of the month for everyone employed that day
            if d.day == 1 and emp > 0:
                tool = p.tool
                if tool == "GitHub Copilot" and d >= date(2026, 10, 1):
                    tool = "Cursor"
                seat_usd = C.TOOLS[tool]["seat_usd"]
                if seat_usd > 0:
                    seats.append(SeatRow(month=d, person_id=p.id, team_id=p.team_id, tool=tool,
                                         provider=C.TOOLS[tool]["provider"], amount_usd=seat_usd))
            if emp <= 0:
                continue
            active = [ev for ev in person_events[p.id] if ev.active(d)]
            if cal.is_weekend:
                f = p.weekend_factor
                for ev in active:
                    if ev.weekend_multiplier is not None:
                        f = max(f, ev.weekend_multiplier)
            else:
                f = C.WEEKDAY_FACTOR[cal.weekday]
            f *= cal.holiday_factor * cal.seasonal_factor
            mult = bump
            for ev in active:
                mult *= ev.multiplier
            if mult <= 0 or f <= 0:
                continue
            noise = rnd.lognormvariate(0.0, 0.22)
            total = p.base_tokens_k * 1000.0 * trend(d, team) * emp * f * mult * noise
            if cal.partial:
                total *= 0.55
            if total < 500:
                continue
            rows.extend(split_person_tokens(p, team, d, total, rnd, active))
        d += timedelta(days=1)
    return rows, seats


def budgets(teams: list, usage_rows: list, seat_rows: list, rnd: random.Random) -> list:
    """Quarterly internal allocations per team. Some teams are deliberately over or under."""
    spend = {}
    for r in usage_rows:
        pid = period_for(r.day)
        if pid and r.cost_usd:
            spend[(r.team_id, pid)] = spend.get((r.team_id, pid), 0.0) + r.cost_usd
    for s in seat_rows:
        pid = period_for(s.month)
        if pid:
            spend[(s.team_id, pid)] = spend.get((s.team_id, pid), 0.0) + s.amount_usd
    # Story: AI Labs and Support Automation are over in Q4; Freight and Payments have headroom.
    tilt = {"ai-labs": 0.78, "support-automation": 0.82, "freight": 1.45, "payments-risk": 1.35, "marketplace-pricing": 0.95}
    out = []
    for t in teams:
        for p in C.PERIODS:
            actual = spend.get((t.id, p["id"]), 0.0)
            if p["id"] == "2026-Q4":
                q3 = spend.get((t.id, "2026-Q3"), 0.0)
                base = q3 * 1.05 * tilt.get(t.id, 1.0)
            else:
                base = actual * rnd.uniform(0.92, 1.18)
            alloc = max(1000.0, round(base / 500.0) * 500.0)
            out.append({"team_id": t.id, "period_id": p["id"], "allocated_usd": alloc, "actual_usd_to_date": round(actual, 2)})
    return out
