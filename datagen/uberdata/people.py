"""Teams and people. Deterministic given the seed."""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from . import config as C


def slug(s: str) -> str:
    out = "".join(ch.lower() if ch.isalnum() else "-" for ch in s)
    while "--" in out:
        out = out.replace("--", "-")
    return out.strip("-")


@dataclass
class Team:
    id: str
    name: str
    description: str
    cost_center: str
    provider_mix: dict
    intensity: float
    weekend: float
    tool: str
    growth: float
    color: str
    lead_id: Optional[str] = None
    projects: list = field(default_factory=list)


@dataclass
class Person:
    id: str
    team_id: str
    name: str
    role: str
    email: str
    level: str
    tool: str
    base_tokens_k: float        # tokens (thousands) on a normal weekday
    input_share: float
    cache_rate: float
    weekend_factor: float
    provider_tilt: dict          # multiplicative tilt on team provider mix
    start_date: date             # first day employed (may be before YEAR_START)
    end_date: Optional[date]     # last day employed, None if still employed
    integrations: list
    is_lead: bool = False
    timezone: str = "America/Los_Angeles"

    @property
    def first(self) -> str:
        return self.name.split(" ")[0]


def build_teams() -> list:
    teams = []
    for t in C.TEAMS:
        teams.append(Team(id=t["id"], name=t["name"], description=t["description"], cost_center=t["cost_center"],
                          provider_mix=dict(t["provider_mix"]), intensity=t["intensity"], weekend=t["weekend"],
                          tool=t["tool"], growth=t["growth"], color=t["color"], projects=list(C.PROJECTS[t["id"]])))
    return teams


def _pick_role(rnd: random.Random, team: Team):
    roles = C.BUSINESS_ROLES if team.id in C.BUSINESS_TEAMS else C.ENGINEERING_ROLES
    weights = [r[4] for r in roles]
    return rnd.choices(roles, weights=weights, k=1)[0]


def build_people(teams: list, rnd: random.Random) -> list:
    used = set()
    people = []
    tz_pool = ["America/Los_Angeles"] * 6 + ["America/New_York"] * 2 + ["Europe/Amsterdam", "Asia/Bangalore"]
    for team in teams:
        cfg = next(t for t in C.TEAMS if t["id"] == team.id)
        team_firsts = set()
        for i in range(cfg["headcount"]):
            while True:  # unique full names company-wide and unique first names within a team
                first, last = rnd.choice(C.FIRST_NAMES), rnd.choice(C.LAST_NAMES)
                name = f"{first} {last}"
                if name not in used and first not in team_firsts:
                    used.add(name)
                    team_firsts.add(first)
                    break
            is_lead = i == 0
            if is_lead:
                role = ("Engineering Manager", 320, 0.76, 0.35, 1.0) if team.id not in C.BUSINESS_TEAMS else ("Operations Manager", 200, 0.72, 0.30, 1.0)
            else:
                role = _pick_role(rnd, team)
            title, tokens_k, in_share, cache, _w = role
            level = "Lead" if is_lead else rnd.choice(["L3", "L4", "L4", "L5", "L5", "L6"])
            level_mult = {"Lead": 1.0, "L3": 0.8, "L4": 1.0, "L5": 1.15, "L6": 1.3}[level]
            personal = rnd.lognormvariate(0, 0.28)
            base = tokens_k * C.TOKEN_SCALE * level_mult * personal * team.intensity
            # Most people joined before the year; a few join (onboarding) or leave (departure) during it.
            start = C.YEAR_START - __import__("datetime").timedelta(days=rnd.randint(60, 1500))
            end = None
            tool = team.tool
            if rnd.random() < 0.25:
                tool = rnd.choice(["Cursor", "Claude Code", "GitHub Copilot"]) if team.id not in C.BUSINESS_TEAMS else tool
            tilt = {p: rnd.uniform(0.75, 1.3) for p in C.PROVIDERS}
            integrations = ["slack"]
            integrations.append(rnd.choice(["asana", "monday"]))
            integrations.append(rnd.choice(["gmail", "outlook"]))
            if rnd.random() < 0.4:
                integrations.append("teams")
            pid = f"{team.id}-{slug(name)}"
            people.append(Person(
                id=pid, team_id=team.id, name=name, role=title,
                email=f"{slug(name).replace('-', '.')}@{C.EMAIL_DOMAIN}", level=level, tool=tool,
                base_tokens_k=base, input_share=in_share, cache_rate=cache,
                weekend_factor=team.weekend * rnd.uniform(0.6, 1.5),
                provider_tilt=tilt, start_date=start, end_date=end, integrations=integrations,
                is_lead=is_lead, timezone=rnd.choice(tz_pool),
            ))
            if is_lead:
                team.lead_id = pid
    return people
