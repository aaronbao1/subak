"""Storylines: the company, team and person events that move token usage, and the evidence
(messages, tasks, announcements) that a finance team would find for each of them.

Every event carries the *effect* (usage multiplier, weekend override, model/provider shift and the
window it applies to) and one or more artifacts: Slack / Teams messages, Gmail / Outlook emails,
Asana tasks and monday.com board items. The artifacts are dated on or before AS_OF; some effects
start after AS_OF so forecasts can be tested against stated plans.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from typing import Optional

from . import config as C
from .people import Person, Team

UTC = timezone.utc

# SignalKind values shared with the frontend contract, plus a few finer-grained ones.
KINDS = {
    "out_of_office": ("decrease", "staffing"),
    "extra_load": ("increase", "project"),
    "project_accelerated": ("increase", "project"),
    "project_deferred": ("decrease", "project"),
    "project_paused": ("decrease", "project"),
    "project_resumed": ("increase", "project"),
    "model_change": ("increase", "model"),
    "model_release": ("increase", "model"),
    "pricing_change": ("decrease", "pricing"),
    "policy_change": ("unknown", "policy"),
    "tool_change": ("unknown", "policy"),
    "onboarding": ("increase", "staffing"),
    "departure": ("decrease", "staffing"),
    "incident": ("increase", "macro"),
    "hackathon": ("increase", "macro"),
    "holiday_notice": ("decrease", "macro"),
    "hiring_freeze": ("decrease", "policy"),
    "quarter_close": ("increase", "project"),
    "steady": ("neutral", "project"),
}


@dataclass
class Event:
    id: str
    kind: str
    scope: str                      # person | team | company
    team_ids: list
    person_ids: list
    starts_on: date
    ends_on: Optional[date]
    multiplier: float
    announced_on: date
    title: str
    summary: str
    project: Optional[str] = None
    weekend_multiplier: Optional[float] = None    # replaces the weekend factor inside the window
    model_override: Optional[dict] = None         # {provider: {model: share}} forced for affected people
    provider_shift: Optional[dict] = None         # {provider: +/- share}
    confidence: str = "high"
    uncertainty: str = ""
    claim_type: str = "stated_plan"
    magnitude_pct: Optional[int] = None

    @property
    def expected_effect(self) -> str:
        return KINDS[self.kind][0]

    @property
    def category(self) -> str:
        return KINDS[self.kind][1]

    @property
    def future(self) -> bool:
        return self.starts_on > C.AS_OF

    def active(self, d: date) -> bool:
        return self.starts_on <= d and (self.ends_on is None or d <= self.ends_on)


@dataclass
class Message:
    id: str
    event_id: str
    channel: str                    # slack | teams | gmail | outlook
    sent_at: datetime
    from_person_id: Optional[str]
    from_name: str
    to: list                        # names / channel
    where: str                      # "#channel", "DM", or email subject
    body: str
    team_ids: list
    person_ids: list

    @property
    def weekday(self) -> str:
        return self.sent_at.strftime("%A")


@dataclass
class Task:
    id: str
    event_id: str
    tool: str                       # asana | monday
    board: str
    title: str
    assignee_id: Optional[str]
    assignee_name: str
    created_at: datetime
    due_on: Optional[date]
    prev_due_on: Optional[date]
    status: str
    prev_status: Optional[str]
    status_changed_at: datetime
    body: str
    team_ids: list
    person_ids: list


@dataclass
class ModelEvent:
    id: str
    provider: str
    model_ids: list
    kind: str                       # release | adoption | price_change | policy
    announced_on: date
    effective_on: date
    details: dict


@dataclass
class Storyline:
    events: list = field(default_factory=list)
    messages: list = field(default_factory=list)
    tasks: list = field(default_factory=list)
    model_events: list = field(default_factory=list)

    def _n(self, prefix: str, lst: list) -> str:
        return f"{prefix}_{len(lst) + 1:04d}"

    def event(self, **kw) -> Event:
        ev = Event(id=self._n("evt", self.events), **kw)
        self.events.append(ev)
        return ev

    def message(self, ev: Event, channel: str, sent_at: datetime, sender: Optional[Person], to, where: str, body: str,
                from_name: Optional[str] = None, team_ids=None, person_ids=None) -> Message:
        m = Message(id=self._n("msg", self.messages), event_id=ev.id, channel=channel, sent_at=sent_at,
                    from_person_id=sender.id if sender else None, from_name=from_name or (sender.name if sender else "System"),
                    to=list(to), where=where, body=body,
                    team_ids=list(team_ids if team_ids is not None else ev.team_ids),
                    person_ids=list(person_ids if person_ids is not None else ev.person_ids))
        self.messages.append(m)
        return m

    def task(self, ev: Event, tool: str, board: str, title: str, assignee: Optional[Person], created_at: datetime,
             due_on: Optional[date], status: str, body: str, prev_due_on: Optional[date] = None,
             prev_status: Optional[str] = None, status_changed_at: Optional[datetime] = None,
             assignee_name: Optional[str] = None) -> Task:
        t = Task(id=self._n("task", self.tasks), event_id=ev.id, tool=tool, board=board, title=title,
                 assignee_id=assignee.id if assignee else None,
                 assignee_name=assignee_name or (assignee.name if assignee else "Unassigned"),
                 created_at=created_at, due_on=due_on, prev_due_on=prev_due_on, status=status,
                 prev_status=prev_status, status_changed_at=status_changed_at or created_at, body=body,
                 team_ids=list(ev.team_ids), person_ids=list(ev.person_ids))
        self.tasks.append(t)
        return t

    def model_event(self, **kw) -> ModelEvent:
        me = ModelEvent(id=self._n("mdl", self.model_events), **kw)
        self.model_events.append(me)
        return me


# ---------------------------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------------------------

def at(d: date, hh: int = 17, mm: int = 0) -> datetime:
    """A UTC timestamp for a US-Pacific working-hours message on day d (09:00 PT = 17:00 UTC)."""
    return datetime.combine(d, time(hh, mm), tzinfo=UTC)


def fmt(d: date) -> str:
    return d.strftime("%b %-d")


def nearest_weekday(d: date, wd: int) -> date:
    """Next date on/after d with weekday wd (0=Mon ... 5=Sat)."""
    return d + timedelta(days=(wd - d.weekday()) % 7)


def business_days_from(d: date, n: int) -> date:
    cur = d
    while n > 0:
        cur += timedelta(days=1)
        if cur.weekday() < 5:
            n -= 1
    return cur


def workday(d: date) -> date:
    """Pull a weekend date back to the Friday before it."""
    return d - timedelta(days=max(0, d.weekday() - 4))


def mail_channel(p: Person) -> str:
    return "outlook" if "outlook" in p.integrations else "gmail"


def chat_channel(p: Person) -> str:
    return "teams" if "teams" in p.integrations and hash(p.id) % 3 == 0 else "slack"


def task_tool(p: Person) -> str:
    return "monday" if "monday" in p.integrations else "asana"


def email_header(sender: str, to: list, subject: str, d: datetime) -> str:
    return (f"**From:** {sender}\n**To:** {', '.join(to)}\n**Date:** {d.strftime('%a %b %-d, %Y %H:%M UTC')}\n"
            f"**Subject:** {subject}\n\n---\n\n")


# ---------------------------------------------------------------------------------------------
# company-level storylines
# ---------------------------------------------------------------------------------------------

def company_storylines(S: Storyline, teams: list, people: list, by_team: dict, rnd: random.Random) -> None:
    all_team_ids = [t.id for t in teams]
    ai_lead = by_team["ai-labs"][0]
    infra_lead = by_team["infra-sre"][0]
    maps_lead = by_team["maps-routing"][0]
    sec_lead = by_team["security"][0]
    fin_lead = by_team["finance-legal"][0]
    people_lead = by_team["people-recruiting"][0]
    eng_leads = [by_team[t.id][0] for t in teams]

    # --- Gemini 3.5 release and adoption --------------------------------------------------------
    S.model_event(provider="google", model_ids=["gemini-3.5-pro", "gemini-3.5-flash"], kind="release",
                  announced_on=date(2026, 2, 10), effective_on=date(2026, 2, 10),
                  details={"note": "Gemini 3.5 Pro and Flash generally available", "list_price_usd_per_mtok": {"gemini-3.5-pro": [2.5, 15.0], "gemini-3.5-flash": [0.6, 3.5]}})
    ev = S.event(kind="model_release", scope="company", team_ids=all_team_ids, person_ids=[], project=None,
                 starts_on=date(2026, 2, 24), ends_on=date(2026, 3, 9), multiplier=1.0, announced_on=date(2026, 2, 12),
                 title="Gemini 3.5 approved for the company workspace; Maps and Data Platform migrate first",
                 summary="Google released Gemini 3.5 Pro and Flash on Feb 10. The AI Labs lead approved it for the company Vertex "
                         "workspace from Feb 24; Maps & Routing and Data Platform re-run their evaluation sets on the new models, "
                         "which raises Google token volume for about two weeks before the mix settles.",
                 confidence="high", magnitude_pct=10, uncertainty="How long the comparison runs last is the teams' estimate.")
    S.model_event(provider="google", model_ids=["gemini-3.5-pro", "gemini-3.5-flash"], kind="adoption",
                  announced_on=date(2026, 2, 12), effective_on=date(2026, 2, 24), details={"event_id": ev.id, "ramp_days": C.RAMP_DAYS})
    S.message(ev, "slack", at(date(2026, 2, 12), 18, 5), ai_lead, ["#announcements"], "#announcements",
              f"**{ai_lead.name}** · {fmt(date(2026, 2, 12))} 10:05 — Gemini 3.5 Pro and Flash are approved for the company Vertex workspace "
              f"starting **Tue Feb 24**. Maps & Routing and Data Platform go first and will re-run their eval sets on 3.5 before switching defaults. "
              f"Expect Google token volume to run above normal for ~2 weeks while comparisons run; list pricing is $2.50 / $15 per MTok for Pro and $0.60 / $3.50 for Flash.\n\n"
              f"**{maps_lead.name}** 10:21 — ETA v7 retrain will move to 3.5 Pro the same week, we are already queued.")

    # --- Claude 5.5 family release, company adoption April 1 --------------------------------------
    S.model_event(provider="anthropic", model_ids=["claude-opus-5.5", "claude-sonnet-5.5", "claude-haiku-5.5"], kind="release",
                  announced_on=date(2026, 3, 17), effective_on=date(2026, 3, 17),
                  details={"note": "Claude Opus 5.5, Sonnet 5.5 and Haiku 5.5 released; same list prices as the 4.5 generation"})
    ev = S.event(kind="model_release", scope="company", team_ids=all_team_ids, person_ids=[], project=None,
                 starts_on=date(2026, 4, 1), ends_on=date(2026, 4, 17), multiplier=1.0, announced_on=date(2026, 3, 20),
                 title="Claude 5.5 family becomes the default Anthropic line-up on Apr 1",
                 summary="Anthropic released the Claude 5.5 family on Mar 17 at unchanged list prices. AI Labs set Apr 1 as the "
                         "cut-over date for the company API keys; teams re-run regression sets at full context during the first two "
                         "weeks, which lifts Anthropic token volume roughly 20% before it settles at the new mix.",
                 confidence="high", magnitude_pct=22, uncertainty="The post gives a window, not a token estimate; the bump size is the forecast's assumption.")
    S.model_event(provider="anthropic", model_ids=["claude-opus-5.5", "claude-sonnet-5.5", "claude-haiku-5.5"], kind="adoption",
                  announced_on=date(2026, 3, 20), effective_on=date(2026, 4, 1), details={"event_id": ev.id, "ramp_days": C.RAMP_DAYS})
    S.message(ev, "slack", at(date(2026, 3, 20), 16, 40), ai_lead, ["#announcements"], "#announcements",
              f"**{ai_lead.name}** · {fmt(date(2026, 3, 20))} 08:40 — Claude Opus 5.5 / Sonnet 5.5 / Haiku 5.5 are live in our Anthropic org. "
              f"The 4.5 models stay available until **Apr 30**; company default keys switch to the 5.5 line-up on **Wed Apr 1**. "
              f"List prices are unchanged ($15/$75 Opus, $3/$15 Sonnet, $1/$5 Haiku). If you own a pipeline, re-run your regression set on 5.5 at full context before cutting over — "
              f"expect a couple of weeks of elevated usage while comparisons run.\n\n"
              f"**{infra_lead.name}** 09:02 — reminder that eval runs should go through the shared batch queue so we can see them in cost reports.")
    S.message(ev, "gmail", at(date(2026, 3, 23), 15, 10), ai_lead, [f"{l.name}" for l in eng_leads], "Claude 5.5 cut-over plan and what it does to April spend",
              email_header(ai_lead.name, ["eng-leads@" + C.EMAIL_DOMAIN, "finance-ai-spend@" + C.EMAIL_DOMAIN], "Claude 5.5 cut-over plan and what it does to April spend", at(date(2026, 3, 23), 15, 10)) +
              "Team leads,\n\nSummary of Friday's announcement for planning purposes:\n\n"
              "- Default keys move to the 5.5 family on April 1. No price change per token.\n"
              "- Each team re-runs its regression set once at full context. Based on the Gemini 3.5 cut-over in February, plan for roughly +20% Anthropic tokens in the first two weeks of April, then back to trend.\n"
              "- Teams with their own migration tasks (AI Labs, Safety & Trust, Support Automation, Marketplace) will file Asana tasks so the work is visible.\n\n"
              "Finance: this is a timing effect, not a new run-rate. Please do not flag April week 1–2 as an overrun.\n\n" + ai_lead.first)

    # --- GPT-5.5 release and adoption May 26 ----------------------------------------------------
    S.model_event(provider="openai", model_ids=["gpt-5.5", "gpt-5.5-mini"], kind="release",
                  announced_on=date(2026, 5, 12), effective_on=date(2026, 5, 12),
                  details={"note": "GPT-5.5 and GPT-5.5 mini released", "list_price_usd_per_mtok": {"gpt-5.5": [2.5, 15.0], "gpt-5.5-mini": [0.5, 2.0]}})
    ev = S.event(kind="model_release", scope="company", team_ids=all_team_ids, person_ids=[], project=None,
                 starts_on=date(2026, 5, 26), ends_on=date(2026, 6, 8), multiplier=1.0, announced_on=date(2026, 5, 14),
                 title="GPT-5.5 replaces GPT-5.2 as the OpenAI default from May 26",
                 summary="OpenAI released GPT-5.5 and GPT-5.5 mini on May 12 with higher list prices than 5.2 ($2.50 vs $1.75 input). "
                         "Infrastructure switched the company gateway default on May 26; OpenAI-heavy teams (Marketplace, Payments, Freight, "
                         "Support Automation) see a cost step-up from the price difference plus a short comparison-run bump.",
                 confidence="high", magnitude_pct=12, uncertainty="The gateway switch is dated; how fast teams pin to the new model is not.")
    S.model_event(provider="openai", model_ids=["gpt-5.5", "gpt-5.5-mini"], kind="adoption",
                  announced_on=date(2026, 5, 14), effective_on=date(2026, 5, 26), details={"event_id": ev.id, "ramp_days": C.RAMP_DAYS})
    S.message(ev, "teams", at(date(2026, 5, 14), 17, 30), infra_lead, ["Engineering (all)"], "Engineering › General",
              f"**{infra_lead.name}** · {fmt(date(2026, 5, 14))} 09:30 — Heads up: the LLM gateway default for `openai/*` moves from GPT-5.2 to **GPT-5.5** on **Tue May 26**. "
              f"GPT-5.2 stays pinnable until Jul 31. Note the price difference: 5.5 is $2.50 in / $15 out vs $1.75 / $14 for 5.2, and 5.5 mini is $0.50 / $2.00. "
              f"If your service is latency- or cost-sensitive, pin explicitly before the 26th.")

    # --- Policy: Gemini for all employees (June 1) -----------------------------------------------
    ev = S.event(kind="policy_change", scope="company", team_ids=all_team_ids, person_ids=[], project=None,
                 starts_on=date(2026, 6, 1), ends_on=None, multiplier=1.0, announced_on=date(2026, 5, 20),
                 provider_shift={"google": 0.10, "anthropic": -0.05, "openai": -0.05},
                 title="Gemini enabled for all employees from June 1",
                 summary="Security and IT finished the data-handling review for Google's enterprise terms. From June 1 every employee "
                         "may use Gemini models through the company gateway and the Gemini Enterprise seats; previously only Maps & Routing "
                         "and Data Platform had access. Google's share of tokens rises company-wide at the expense of the other providers.",
                 confidence="medium", magnitude_pct=0, uncertainty="Adoption is voluntary; the share shift is an estimate from the first weeks.")
    S.model_event(provider="google", model_ids=["gemini-3.5-pro", "gemini-3.5-flash"], kind="policy",
                  announced_on=date(2026, 5, 20), effective_on=date(2026, 6, 1), details={"event_id": ev.id, "provider_shift": ev.provider_shift})
    S.message(ev, "gmail", at(date(2026, 5, 20), 16, 0), sec_lead, ["all-employees@" + C.EMAIL_DOMAIN], "AI tooling policy update: Gemini approved for all teams",
              email_header(sec_lead.name, ["all-employees@" + C.EMAIL_DOMAIN], "AI tooling policy update: Gemini approved for all teams", at(date(2026, 5, 20), 16, 0)) +
              "All,\n\nThe Security and Legal review of Google's enterprise data-handling terms is complete. Effective **Monday June 1**:\n\n"
              "- Gemini 3.5 Pro and Flash are approved for all employees through the LLM gateway (`google/*`).\n"
              "- Gemini Enterprise seats are available on request through the IT portal.\n"
              "- The approved-data classification is unchanged: no rider or driver PII in prompts outside the gated environments.\n\n"
              "Until now only Maps & Routing and Data Platform had Gemini access. Finance has been told to expect a shift of spend toward Google and a corresponding dip on the other two providers.\n\n" + sec_lead.name + "\nSecurity")

    # --- Pricing changes --------------------------------------------------------------------------
    ev = S.event(kind="pricing_change", scope="company", team_ids=all_team_ids, person_ids=[], project=None,
                 starts_on=date(2026, 8, 1), ends_on=None, multiplier=1.0, announced_on=date(2026, 7, 22),
                 title="OpenAI cuts GPT-5.5 mini prices 40% from Aug 1",
                 summary="OpenAI's account team confirmed GPT-5.5 mini drops to $0.30 input / $1.20 output per million tokens on Aug 1 "
                         "(from $0.50 / $2.00). The same token volume costs less; Support Automation and Payments & Risk, which run mini "
                         "for classification, see the largest savings.",
                 confidence="high", magnitude_pct=-4, claim_type="observed_event", uncertainty="Only mini changes; the GPT-5.5 price is unchanged.")
    S.model_event(provider="openai", model_ids=["gpt-5.5-mini"], kind="price_change", announced_on=date(2026, 7, 22), effective_on=date(2026, 8, 1),
                  details={"event_id": ev.id, "input_usd_per_mtok": 0.30, "cached_input_usd_per_mtok": 0.03, "output_usd_per_mtok": 1.20})
    S.message(ev, "gmail", at(date(2026, 7, 22), 20, 15), fin_lead, ["finance-ai-spend@" + C.EMAIL_DOMAIN], "Fwd: GPT-5.5 mini pricing change effective August 1",
              email_header(fin_lead.name, ["finance-ai-spend@" + C.EMAIL_DOMAIN], "Fwd: GPT-5.5 mini pricing change effective August 1", at(date(2026, 7, 22), 20, 15)) +
              "Forwarding from our OpenAI account team for the record.\n\n> Effective August 1, 2026, GPT-5.5 mini list pricing changes to $0.30 per million input tokens "
              "(cached input $0.03) and $1.20 per million output tokens. GPT-5.5 pricing is unchanged. No action is needed on your side.\n\n"
              "For the model: same tokens, ~40% less on the mini line. Support Automation and Payments run most of their classification volume on mini.\n\n" + fin_lead.first)
    ev = S.event(kind="pricing_change", scope="company", team_ids=all_team_ids, person_ids=[], project=None,
                 starts_on=date(2026, 9, 15), ends_on=None, multiplier=1.0, announced_on=date(2026, 9, 9),
                 title="Anthropic lowers Claude Haiku 5.5 to $0.80 / $4.00 from Sep 15",
                 summary="Anthropic announced a Haiku 5.5 price reduction to $0.80 input / $4.00 output per million tokens effective Sep 15. "
                         "Haiku carries about 15% of Anthropic tokens, so the company effect is small but real.",
                 confidence="high", magnitude_pct=-1, claim_type="observed_event", uncertainty="None; the price is published.")
    S.model_event(provider="anthropic", model_ids=["claude-haiku-5.5"], kind="price_change", announced_on=date(2026, 9, 9), effective_on=date(2026, 9, 15),
                  details={"event_id": ev.id, "input_usd_per_mtok": 0.80, "cached_input_usd_per_mtok": 0.08, "output_usd_per_mtok": 4.00})
    S.message(ev, "slack", at(date(2026, 9, 9), 17, 45), ai_lead, ["#ai-platform"], "#ai-platform",
              f"**{ai_lead.name}** · {fmt(date(2026, 9, 9))} 09:45 — FYI Anthropic is cutting Haiku 5.5 to $0.80 / $4.00 per MTok from **Sep 15** (was $1 / $5). Nothing to change on our side; the gateway picks up list pricing.")

    # --- Tool change: Copilot seats retired Oct 1 -------------------------------------------------
    copilot_users = [p for p in people if p.tool == "GitHub Copilot"]
    ev = S.event(kind="tool_change", scope="company", team_ids=sorted({p.team_id for p in copilot_users}), person_ids=[p.id for p in copilot_users],
                 project=None, starts_on=date(2026, 10, 1), ends_on=None, multiplier=1.0, announced_on=date(2026, 9, 8),
                 title="GitHub Copilot seats retired Oct 1; holders move to Cursor",
                 summary=f"IT consolidated coding-assistant seats: the {len(copilot_users)} remaining GitHub Copilot seats end on Oct 1 and "
                         "each holder gets a Cursor seat instead. Seat fees change (Copilot $39 to Cursor $40) and Cursor usage above the "
                         "included allowance bills as overage, so the component mix for Freight and Security shifts from October.",
                 confidence="high", magnitude_pct=3, uncertainty="How much of the moved usage lands in Cursor overage depends on each person's habits.")
    S.task(ev, "monday", "IT › Seat consolidation", "Retire GitHub Copilot seats and provision Cursor", sec_lead, at(date(2026, 9, 8), 18, 0),
           date(2026, 10, 1), "Done", f"| Item | Owner | Due | Status |\n|---|---|---|---|\n| Retire GitHub Copilot seats ({len(copilot_users)} seats) | IT | Oct 1 | Done |\n"
           f"| Provision Cursor seats for former Copilot users | IT | Sep 29 | Done |\n| Notify Freight and Security leads | {sec_lead.name} | Sep 10 | Done |",
           prev_status="Working on it", status_changed_at=at(date(2026, 10, 1), 16, 0))
    S.message(ev, "slack", at(date(2026, 9, 8), 19, 20), sec_lead, ["#eng-tools"], "#eng-tools",
              f"**{sec_lead.name}** · {fmt(date(2026, 9, 8))} 11:20 — Seat consolidation: we are retiring the remaining GitHub Copilot seats on **Oct 1**. "
              f"Everyone affected gets a Cursor seat (invites go out Sep 29). Nothing changes for Claude Code or API access. Cost-wise the seat fee is about the same; "
              f"heavy users will show up as Cursor overage instead of a flat fee, so finance will see the mix move.")

    # --- Hackathons ------------------------------------------------------------------------------
    ev = S.event(kind="hackathon", scope="company", team_ids=all_team_ids, person_ids=[], project=None,
                 starts_on=date(2026, 6, 8), ends_on=date(2026, 6, 12), multiplier=1.32, announced_on=date(2026, 5, 28),
                 title="Mobility AI Week hackathon, Jun 8-12", claim_type="stated_plan",
                 summary="The company-wide hackathon runs Jun 8-12 with API credits opened on every team key. Past hackathon weeks ran about "
                         "30% above a normal week; the Friday demo day ends the bump.",
                 confidence="high", magnitude_pct=32, uncertainty="Participation is voluntary; the multiplier is based on last year's week.")
    S.message(ev, "slack", at(date(2026, 5, 28), 17, 0), people_lead, ["#announcements"], "#announcements",
              f"**{people_lead.name}** · {fmt(date(2026, 5, 28))} 09:00 — Mobility AI Week is **Jun 8-12**. Teams can use any approved model; the platform team has lifted "
              f"rate limits on the hackathon keys for the week. Demo day is Friday Jun 12 at 1pm PT. Expect your normal roadmap work to slow down that week.")
    ev = S.event(kind="hackathon", scope="company", team_ids=all_team_ids, person_ids=[], project=None,
                 starts_on=date(2026, 11, 9), ends_on=date(2026, 11, 13), multiplier=1.30, announced_on=date(2026, 10, 15),
                 title="Q4 'Build Week' hackathon planned for Nov 9-13",
                 summary="A second hackathon week is scheduled for Nov 9-13 with the same open-credit arrangement as June. The June week ran "
                         "about 30% above trend, so the same bump is expected in the second week of November.",
                 confidence="medium", magnitude_pct=30, uncertainty="Scheduled but not yet started; participation could differ from June.")
    S.message(ev, "slack", at(date(2026, 10, 15), 17, 30), people_lead, ["#announcements"], "#announcements",
              f"**{people_lead.name}** · {fmt(date(2026, 10, 15))} 09:30 — Save the date: Q4 Build Week is **Nov 9-13**, same format as Mobility AI Week in June (open credits on hackathon keys, demo day Friday). Sign-ups open Oct 27.")

    # --- Holiday / closure notices ---------------------------------------------------------------
    notices = [
        (date(2026, 1, 14), date(2026, 1, 19), "Martin Luther King Jr. Day"),
        (date(2026, 2, 11), date(2026, 2, 16), "Presidents' Day"),
        (date(2026, 3, 20), date(2026, 3, 27), "Recharge Friday"),
        (date(2026, 5, 20), date(2026, 5, 25), "Memorial Day"),
        (date(2026, 6, 15), date(2026, 6, 19), "Juneteenth"),
        (date(2026, 6, 29), date(2026, 7, 3), "Independence Day (observed)"),
        (date(2026, 8, 7), date(2026, 8, 14), "Recharge Friday"),
        (date(2026, 9, 2), date(2026, 9, 7), "Labor Day"),
        (date(2026, 10, 12), date(2026, 11, 26), "Thanksgiving (office closed Nov 26-27)"),
        (date(2026, 10, 12), date(2026, 12, 21), "Year-end shutdown Dec 21 - Jan 1"),
    ]
    for sent, holiday, label in notices:
        end = holiday
        if "Thanksgiving" in label:
            end = date(2026, 11, 27)
        if "shutdown" in label:
            end = date(2027, 1, 1)
        ev = S.event(kind="holiday_notice", scope="company", team_ids=all_team_ids, person_ids=[], project=None,
                     starts_on=holiday, ends_on=end, multiplier=1.0, announced_on=sent,
                     title=f"Office closed: {label}", claim_type="observed_event",
                     summary=f"People Ops notice: the US offices are closed for {label} ({fmt(holiday)}{'' if end == holiday else ' to ' + fmt(end)}). "
                             "Usage on closure days has run at a quarter or less of a normal weekday all year.",
                     confidence="high", magnitude_pct=-75, uncertainty="Teams on call (Infrastructure & SRE) keep some activity.")
        S.message(ev, "gmail", at(sent, 16, 30), people_lead, ["all-employees@" + C.EMAIL_DOMAIN], f"Reminder: offices closed for {label}",
                  email_header(people_lead.name, ["all-employees@" + C.EMAIL_DOMAIN], f"Reminder: offices closed for {label}", at(sent, 16, 30)) +
                  (f"Hi all,\n\nA reminder that US offices are closed on **{holiday.strftime('%A %B %-d')}** for {label}. On-call rotations continue as scheduled. "
                   "Please set your calendar status so colleagues in other regions know.\n\n" if end == holiday else
                   f"Hi all,\n\nPlanning ahead: US offices will be closed **{holiday.strftime('%A %B %-d')} through {end.strftime('%A %B %-d')}** ({label}). "
                   "Please wrap up anything that needs a decision before then and set your out-of-office. On-call rotations continue as scheduled.\n\n") +
                  people_lead.name + "\nPeople Operations")

    # --- Fable 5.1: released Oct 17, pilots Oct 31, company-wide Nov 16 (future) -------------------
    S.model_event(provider="anthropic", model_ids=["claude-fable-5.1"], kind="release", announced_on=date(2026, 10, 17), effective_on=date(2026, 10, 17),
                  details={"note": "Claude Fable 5.1 released", "list_price_usd_per_mtok": {"claude-fable-5.1": [25.0, 125.0]}})
    pilots = [p.id for p in by_team["ai-labs"]] + [p.id for p in by_team["safety-trust"]]
    ev_pilot = S.event(kind="model_change", scope="team", team_ids=["ai-labs", "safety-trust"], person_ids=pilots, project="Model Adoption Program",
                       starts_on=date(2026, 10, 31), ends_on=date(2026, 11, 15), multiplier=1.40, announced_on=date(2026, 10, 20),
                       model_override={"anthropic": {"claude-fable-5.1": 0.55, "claude-opus-5.5": 0.15, "claude-sonnet-5.5": 0.30}},
                       title="Claude Fable 5.1 pilot starts Oct 31 for AI Labs and Safety & Trust",
                       summary="Anthropic released Claude Fable 5.1 on Oct 17 at $25 / $125 per million tokens, well above Opus 5.5. The AI Labs lead "
                               "scheduled a two-week pilot from Oct 31 for AI Labs and Safety & Trust: they move about half their Anthropic traffic to "
                               "Fable 5.1 and run side-by-side evaluations, so their Anthropic spend roughly doubles for the pilot window.",
                       confidence="high", magnitude_pct=95, uncertainty="Pilot scope could narrow if the evaluations show no quality gain; the token volume estimate is the lead's.")
    S.model_event(provider="anthropic", model_ids=["claude-fable-5.1"], kind="adoption", announced_on=date(2026, 10, 20), effective_on=date(2026, 10, 31),
                  details={"event_id": ev_pilot.id, "scope": "pilot", "teams": ["ai-labs", "safety-trust"]})
    ev_all = S.event(kind="model_change", scope="company", team_ids=all_team_ids, person_ids=[], project="Model Adoption Program",
                     starts_on=date(2026, 11, 16), ends_on=date(2026, 12, 4), multiplier=1.0, announced_on=date(2026, 10, 20),
                     title="Claude Fable 5.1 planned as a company default option from Nov 16",
                     summary="If the pilot holds, Fable 5.1 is added to the company default line-up on Nov 16 with about 30% of Anthropic tokens "
                             "expected to move to it. At $25 / $125 per million tokens that is roughly a 45% increase in Anthropic cost per token "
                             "for the moved share, plus a comparison-run bump similar to April's.",
                     confidence="medium", magnitude_pct=25, uncertainty="Conditional on the pilot; the 30% share and the Nov 16 date are both the current plan, not a decision.")
    S.model_event(provider="anthropic", model_ids=["claude-fable-5.1"], kind="adoption", announced_on=date(2026, 10, 20), effective_on=date(2026, 11, 16),
                  details={"event_id": ev_all.id, "scope": "company", "ramp_days": C.RAMP_DAYS, "conditional_on": ev_pilot.id})
    S.message(ev_pilot, "slack", at(date(2026, 10, 20), 16, 15), ai_lead, ["#announcements"], "#announcements",
              f"**{ai_lead.name}** · {fmt(date(2026, 10, 20))} 08:15 — Anthropic shipped **Claude Fable 5.1** on Friday. It is priced at $25 / $125 per MTok, so this is not a drop-in swap. "
              f"Plan:\n• **Oct 31**: two-week pilot in AI Labs and Safety & Trust (side-by-side evals, ~half of Anthropic traffic on Fable).\n"
              f"• **Nov 16**: if the quality gain holds, Fable 5.1 joins the default line-up company-wide; we expect ~30% of Anthropic tokens to move.\n"
              f"Finance is looped in; pilot teams should expect their Anthropic line to roughly double for the two pilot weeks.\n\n"
              f"**{by_team['safety-trust'][0].name}** 08:40 — Trip Audio Review is the pilot workload on our side. We'll keep the eval batch on the shared queue.",
              team_ids=all_team_ids, person_ids=[])
    S.message(ev_all, "gmail", at(date(2026, 10, 22), 17, 5), fin_lead, ["finance-ai-spend@" + C.EMAIL_DOMAIN], "Fwd: Claude Fable 5.1 pricing and committed-use options",
              email_header(fin_lead.name, ["finance-ai-spend@" + C.EMAIL_DOMAIN, ai_lead.name], "Fwd: Claude Fable 5.1 pricing and committed-use options", at(date(2026, 10, 22), 17, 5)) +
              "Forwarding the pricing note from the Anthropic account team so we have it on file for Q4 planning.\n\n"
              "> Claude Fable 5.1 list pricing is $25 per million input tokens ($2.50 cached) and $125 per million output tokens. Opus 5.5, Sonnet 5.5 and Haiku 5.5 pricing is unchanged. "
              "Committed-use discounts are available for annual commitments above $500k.\n\n"
              f"If the Nov 16 company-wide step happens as {ai_lead.first} described, the Anthropic line goes up about 45% on the moved share. I would like to see a projection for Q4 with and without the Nov 16 step before we talk about reallocations.\n\n" + fin_lead.first)
    S.task(ev_pilot, "asana", "AI Labs › Model Adoption Program", "Fable 5.1 pilot: side-by-side evaluation on Agent Evaluation Harness", by_team["ai-labs"][1], at(date(2026, 10, 20), 18, 0),
           date(2026, 11, 13), "Not started", f"**Assignee:** {by_team['ai-labs'][1].name} · **Status:** Not started · **Due:** Nov 13\n\n"
           "Run the full harness on Claude Fable 5.1 vs Opus 5.5 with identical prompts and full context. Route ~50% of AI Labs Anthropic traffic to Fable from Oct 31. Report quality delta and cost per solved task by Nov 13.")
    S.task(ev_pilot, "asana", "Safety & Trust › Trip Audio Review Tooling", "Fable 5.1 pilot on audio review summaries (Oct 31 - Nov 13)", by_team["safety-trust"][2], at(date(2026, 10, 21), 17, 0),
           date(2026, 11, 13), "Not started", f"**Assignee:** {by_team['safety-trust'][2].name} · **Status:** Not started · **Due:** Nov 13\n\n"
           "Mirror the production review-summary batch onto Fable 5.1 for two weeks and compare reviewer acceptance rate. Expect double the Anthropic token volume for the window.")


# ---------------------------------------------------------------------------------------------
# team-level storylines (scripted)
# ---------------------------------------------------------------------------------------------

def team_storylines(S: Storyline, by_team: dict, rnd: random.Random) -> None:
    def members(team_id: str, frac: float, skip_lead: bool = True) -> list:
        ps = by_team[team_id][1:] if skip_lead else by_team[team_id]
        k = max(1, round(len(ps) * frac))
        return sorted(rnd.sample(ps, k), key=lambda p: p.id)

    def lead(team_id: str) -> Person:
        return by_team[team_id][0]

    # Freight: AI Dispatch v2 on hold Mar 2 - Apr 20, then on hold again from Nov 2 (future).
    t, L = "freight", lead("freight")
    crew = members(t, 0.6)
    ev = S.event(kind="project_paused", scope="team", team_ids=[t], person_ids=[p.id for p in crew], project="AI Dispatch v2",
                 starts_on=date(2026, 3, 2), ends_on=date(2026, 4, 19), multiplier=0.45, announced_on=date(2026, 2, 27),
                 title="Freight put AI Dispatch v2 on hold pending the carrier contract review",
                 summary=f"{L.name} told the Freight channel on Feb 27 that AI Dispatch v2 is on hold until the carrier contract review finishes. "
                         f"The {len(crew)} engineers on the project moved to maintenance work, and their coding-assistant and API usage dropped to under half for seven weeks.",
                 confidence="high", magnitude_pct=-55, uncertainty="The restart date was not stated when the hold began.")
    S.message(ev, "teams", at(date(2026, 2, 27), 22, 10), L, ["Freight Engineering"], "Freight › Engineering",
              f"**{L.name}** · {fmt(date(2026, 2, 27))} 14:10 — Team: **AI Dispatch v2 is on hold for now.** Legal needs to finish the carrier contract review before we ship anything that changes load assignment. "
              f"{', '.join(p.first for p in crew)} — please park the dispatch branches and pick up the maintenance backlog with {by_team[t][-1].first} starting Monday. I will let you know as soon as we have a restart date.\n\n"
              f"**{crew[0].name}** 14:22 — understood, parking the eval harness runs too.")
    S.task(ev, "monday", "Freight › Roadmap 2026", "AI Dispatch v2", L, at(date(2026, 1, 12), 18, 0), date(2026, 5, 29), "On hold",
           f"| Project | Owner | Timeline | Status |\n|---|---|---|---|\n| AI Dispatch v2 | {L.name} | Jan 12 - May 29 | **On hold** (was Working on it) |\n\n"
           f"Status changed by {L.name} on Feb 27: *on hold pending carrier contract review*.", prev_status="Working on it", status_changed_at=at(date(2026, 2, 27), 22, 15))
    ev2 = S.event(kind="project_resumed", scope="team", team_ids=[t], person_ids=[p.id for p in crew], project="AI Dispatch v2",
                  starts_on=date(2026, 4, 20), ends_on=date(2026, 5, 15), multiplier=1.25, announced_on=date(2026, 4, 16),
                  title="AI Dispatch v2 restarts Apr 20 with a compressed schedule",
                  summary="The contract review cleared and the project restarted on Apr 20 with the original end date, so the team ran above its earlier pace to catch up.",
                  confidence="high", magnitude_pct=25, uncertainty="Catch-up intensity is inferred from the compressed timeline.")
    S.message(ev2, "teams", at(date(2026, 4, 16), 17, 0), L, ["Freight Engineering"], "Freight › Engineering",
              f"**{L.name}** · {fmt(date(2026, 4, 16))} 09:00 — Good news: Legal signed off. **AI Dispatch v2 restarts Monday Apr 20.** We are keeping the May 29 target, so it will be a compressed few weeks. Branches can come back off the shelf.")
    ev3 = S.event(kind="project_paused", scope="team", team_ids=[t], person_ids=[p.id for p in crew], project="AI Dispatch v2",
                  starts_on=date(2026, 11, 2), ends_on=date(2027, 1, 10), multiplier=0.45, announced_on=date(2026, 10, 21),
                  title="AI Dispatch v2 goes back on hold from Nov 2 until January",
                  summary=f"{L.name} announced on Oct 21 that AI Dispatch v2 phase 2 is on hold from Nov 2 until the January planning cycle, "
                          f"because the shipper pilot was pushed by the customer. The same {len(crew)} people move to maintenance; the March hold cut their usage by more than half.",
                  confidence="high", magnitude_pct=-55, uncertainty="January restart is the stated plan; the customer could move the pilot again.")
    S.message(ev3, "teams", at(date(2026, 10, 21), 21, 30), L, ["Freight Engineering"], "Freight › Engineering",
              f"**{L.name}** · {fmt(date(2026, 10, 21))} 13:30 — Update from the shipper pilot: the customer moved their go-live to Q1, so **AI Dispatch v2 phase 2 is on hold from Mon Nov 2 until January planning**. "
              f"Same drill as March — {', '.join(p.first for p in crew)} roll onto the maintenance and document-extraction backlog. Thanks for the flexibility.")
    S.task(ev3, "monday", "Freight › Roadmap 2026", "AI Dispatch v2 - phase 2", L, at(date(2026, 6, 1), 18, 0), date(2026, 12, 18), "On hold",
           f"| Project | Owner | Timeline | Status |\n|---|---|---|---|\n| AI Dispatch v2 - phase 2 | {L.name} | Jun 1 - Dec 18 → Jan 11 - Mar 5 | **On hold from Nov 2** |\n\n"
           f"Timeline moved by {L.name} on Oct 21: *customer pilot moved to Q1*.", prev_due_on=date(2026, 12, 18), prev_status="Working on it", status_changed_at=at(date(2026, 10, 21), 21, 35))

    # Marketplace & Pricing: Surge Model Retrain pulled forward (Asana due date Sep 30 -> Aug 21), weekend pushes.
    t, L = "marketplace-pricing", lead("marketplace-pricing")
    crew = members(t, 0.7)
    ev = S.event(kind="project_accelerated", scope="team", team_ids=[t], person_ids=[p.id for p in crew], project="Surge Model Retrain",
                 starts_on=date(2026, 7, 27), ends_on=date(2026, 8, 21), multiplier=1.38, weekend_multiplier=0.75, announced_on=date(2026, 7, 27),
                 title="Surge Model Retrain due date pulled forward from Sep 30 to Aug 21",
                 summary=f"{L.name} changed the Asana due date for the Surge Model Retrain from Sep 30 to Aug 21 to land before the back-to-school demand peak. "
                         f"{len(crew)} people worked the retrain and its evaluation runs for four weeks, including two Saturdays, so Marketplace API usage ran well above trend.",
                 confidence="high", magnitude_pct=38, uncertainty="The weekend work was stated in Slack, not planned; the end date held.")
    S.task(ev, "asana", "Marketplace › Surge Model Retrain", "Retrain surge model on H1 trips and ship to 10% of cities", crew[0], at(date(2026, 6, 15), 17, 0),
           date(2026, 8, 21), "In progress", f"# Retrain surge model on H1 trips and ship to 10% of cities\n\n**Assignee:** {crew[0].name} · **Status:** In progress · **Due:** Aug 21 (was Sep 30)\n\n"
           f"**{L.name}** changed the due date to **Aug 21** (was Sep 30) on Jul 27: *we need this live before the back-to-school peak.*\n\n"
           f"Scope: retrain on H1 2026 trips, run the offline eval suite on GPT-5.5 for explanation generation, ship to 10% of cities behind a flag.",
           prev_due_on=date(2026, 9, 30), status_changed_at=at(date(2026, 7, 27), 16, 30))
    S.message(ev, "slack", at(date(2026, 7, 27), 16, 35), L, ["#marketplace-eng"], "#marketplace-eng",
              f"**{L.name}** · {fmt(date(2026, 7, 27))} 08:35 — Pulling the surge retrain in to **Aug 21** (was end of Sep). We need the new model live before back-to-school. "
              f"{', '.join(p.first for p in crew)} are on it; everything else on the board slides. Expect the eval queue to be busy for the next four weeks.")
    for sat in (date(2026, 8, 8), date(2026, 8, 15)):
        S.message(ev, "slack", at(sat, 19, 40), crew[1], ["#marketplace-eng"], "#marketplace-eng",
                  f"**{crew[1].name}** · {sat.strftime('%a %b %-d')} 11:40 — pushing through the weekend on the surge retrain, eval sweep #{3 if sat.day == 8 else 5} is running on the batch queue now. "
                  f"{crew[0].first} and I will be on until the numbers come back.\n\n**{crew[0].name}** 11:52 — same, I have the city-level comparison running in parallel.")

    # Eats Delivery: Order Tracking Overhaul delayed three weeks (monday timeline), then catch-up.
    t, L = "eats-delivery", lead("eats-delivery")
    crew = members(t, 0.6)
    ev = S.event(kind="project_deferred", scope="team", team_ids=[t], person_ids=[p.id for p in crew], project="Order Tracking Overhaul",
                 starts_on=date(2026, 6, 3), ends_on=date(2026, 6, 19), multiplier=0.68, announced_on=date(2026, 6, 3),
                 title="Order Tracking Overhaul launch moved back three weeks (Jun 15 to Jul 6)",
                 summary=f"The monday.com roadmap item for the Order Tracking Overhaul moved its launch from Jun 15 to Jul 6 after the courier-app dependency slipped. "
                         f"The {len(crew)} people on it spent the first weeks of June on design re-work with much less code generation, then ran hot to the new date.",
                 confidence="high", magnitude_pct=-32, uncertainty="The dip is inferred from the dependency slip; the catch-up afterwards is the usual pattern.")
    S.task(ev, "monday", "Eats › Delivery Roadmap", "Order Tracking Overhaul", L, at(date(2026, 3, 2), 18, 0), date(2026, 7, 6), "Working on it",
           f"| Project | Owner | Launch | Status |\n|---|---|---|---|\n| Order Tracking Overhaul | {L.name} | **Jul 6** (was Jun 15) | Working on it |\n\n"
           f"Timeline moved by {L.name} on Jun 3: *courier app dependency slipped; re-plan the tracking surface against the new API*.",
           prev_due_on=date(2026, 6, 15), status_changed_at=at(date(2026, 6, 3), 20, 0))
    S.message(ev, "slack", at(date(2026, 6, 3), 20, 5), L, ["#eats-delivery"], "#eats-delivery",
              f"**{L.name}** · {fmt(date(2026, 6, 3))} 12:05 — Order Tracking launch moves to **Jul 6** (was Jun 15); the courier-app API we depend on slipped. "
              f"{', '.join(p.first for p in crew)} — spend the next two weeks on the re-plan with design, then we build against the new contract.")
    S.event(kind="project_accelerated", scope="team", team_ids=[t], person_ids=[p.id for p in crew], project="Order Tracking Overhaul",
            starts_on=date(2026, 6, 22), ends_on=date(2026, 7, 6), multiplier=1.22, announced_on=date(2026, 6, 3),
            title="Order Tracking Overhaul build phase compressed into Jun 22 - Jul 6",
            summary="After the re-plan the same people built against the new API in two weeks instead of four, so late June ran above the team's trend.",
            confidence="medium", magnitude_pct=22, uncertainty="Inferred from the compressed build window rather than stated.")

    # Support Automation: Reply Drafting Rollout to all markets from Sep 1, batch jobs over weekends.
    t, L = "support-automation", lead("support-automation")
    crew = members(t, 0.75)
    ev = S.event(kind="project_accelerated", scope="team", team_ids=[t], person_ids=[p.id for p in crew], project="Reply Drafting Rollout",
                 starts_on=date(2026, 9, 1), ends_on=date(2026, 12, 18), multiplier=1.55, weekend_multiplier=0.60, announced_on=date(2026, 8, 24),
                 title="Reply Drafting rolls out to all markets from Sep 1; nightly and weekend batch drafting",
                 summary=f"{L.name}'s rollout plan expands reply drafting from three pilot markets to all markets starting Sep 1, with the backfill batches running nightly and over weekends. "
                         "Support Automation API volume rises by more than half and its weekends no longer look like weekends.",
                 confidence="high", magnitude_pct=55, uncertainty="The plan is approved through Q4; the per-market ramp order could change volumes week to week.")
    S.message(ev, "gmail", at(date(2026, 8, 24), 16, 0), L, ["finance-ai-spend@" + C.EMAIL_DOMAIN], "Reply Drafting rollout plan: Sep 1 to all markets (heads-up on API spend)",
              email_header(L.name, ["finance-ai-spend@" + C.EMAIL_DOMAIN, lead("ai-labs").name], "Reply Drafting rollout plan: Sep 1 to all markets (heads-up on API spend)", at(date(2026, 8, 24), 16, 0)) +
              "Hi finance,\n\nAs discussed in planning, Reply Drafting goes from the three pilot markets to **all markets starting Sep 1**. What this does to spend:\n\n"
              "- The live drafting volume scales with ticket volume, roughly 4x the pilot.\n- Historical backfill (so agents see drafts on open tickets) runs as nightly batches and **over weekends** through October.\n"
              "- Most drafting runs on GPT-5.5 mini and Claude Haiku 5.5; summaries on Sonnet 5.5.\n\nExpect our API line to run about 1.5x the August rate from September through year end. This is in the approved plan; please do not flag it as an overrun.\n\n" + L.first)
    S.task(ev, "asana", "Support Automation › Reply Drafting Rollout", "Rollout to all markets (wave 1-4) and backfill open tickets", crew[0], at(date(2026, 8, 24), 17, 0),
           date(2026, 10, 30), "In progress", f"# Rollout to all markets (wave 1-4) and backfill open tickets\n\n**Assignee:** {crew[0].name} · **Status:** In progress · **Due:** Oct 30\n\n"
           "- [x] Wave 1 (US West) Sep 1\n- [x] Wave 2 (US East, Canada) Sep 15\n- [x] Wave 3 (UK, EU) Oct 1\n- [ ] Wave 4 (LatAm, APAC) Oct 27\n- [ ] Backfill batches: nightly + weekends, cap concurrency at 16")

    # Infrastructure & SRE: Saturday incidents.
    t, L = "infra-sre", lead("infra-sre")
    for sat, title_bit in ((date(2026, 2, 21), "regional gateway outage"), (date(2026, 7, 18), "CI runner storage saturation")):
        crew = members(t, 0.5)
        ev = S.event(kind="incident", scope="team", team_ids=[t], person_ids=[p.id for p in crew], project="Incident Response Copilot",
                     starts_on=sat, ends_on=sat + timedelta(days=2), multiplier=1.45, weekend_multiplier=1.05, announced_on=sat, claim_type="observed_event",
                     title=f"Saturday incident: {title_bit} ({fmt(sat)})",
                     summary=f"A SEV-1 {title_bit} ran from Saturday {fmt(sat)} into Monday. The on-call group used the incident copilot and log-analysis prompts heavily, so Infrastructure's weekend usage spiked to above a normal weekday.",
                     confidence="high", magnitude_pct=45, uncertainty="One-off; no forward effect beyond the post-incident review.")
        S.message(ev, "slack", at(sat, 15, 12), crew[0], ["#incidents"], "#incidents",
                  f"**{crew[0].name}** · {sat.strftime('%a %b %-d')} 07:12 — :rotating_light: **SEV-1 declared**: {title_bit}. Incident channel #inc-{sat.strftime('%m%d')}. "
                  f"{crew[1].first if len(crew) > 1 else L.first} is IC, I am running the copilot on the gateway logs. Expect updates every 30 min.\n\n"
                  f"**{L.name}** 07:30 — paging the secondary. Keep all the log triage on the incident key so we can account for it later.")

    # Data Platform: Warehouse Cost Governance paused in August.
    t, L = "data-platform", lead("data-platform")
    crew = members(t, 0.5)
    ev = S.event(kind="project_paused", scope="team", team_ids=[t], person_ids=[p.id for p in crew], project="Warehouse Cost Governance",
                 starts_on=date(2026, 8, 3), ends_on=date(2026, 8, 28), multiplier=0.50, announced_on=date(2026, 7, 31),
                 title="Warehouse Cost Governance paused for August pending the vendor contract",
                 summary=f"{L.name} paused the Warehouse Cost Governance project for August while procurement renegotiated the warehouse vendor contract; the {len(crew)} people on it covered on-call and documentation and used about half their usual tokens.",
                 confidence="high", magnitude_pct=-50, uncertainty="The pause had a stated end (Aug 28) and resumed on time.")
    S.message(ev, "slack", at(date(2026, 7, 31), 21, 0), L, ["#data-platform"], "#data-platform",
              f"**{L.name}** · {fmt(date(2026, 7, 31))} 13:00 — Pausing **Warehouse Cost Governance for August**: procurement is mid-negotiation on the warehouse contract and the governance rules depend on the outcome. "
              f"{', '.join(p.first for p in crew)} — docs and on-call for August, we pick it back up **Aug 31**.")

    # AI Labs: Agent Evaluation Harness nightly runs Apr 13 - May 29.
    t, L = "ai-labs", lead("ai-labs")
    crew = members(t, 0.8)
    ev = S.event(kind="project_accelerated", scope="team", team_ids=[t], person_ids=[p.id for p in crew], project="Agent Evaluation Harness",
                 starts_on=date(2026, 4, 13), ends_on=date(2026, 5, 29), multiplier=1.5, weekend_multiplier=0.55, announced_on=date(2026, 4, 9),
                 title="Agent Evaluation Harness runs nightly across all three providers through May",
                 summary="AI Labs scheduled nightly harness runs on Claude 5.5, GPT-5.2 and Gemini 3.5 for seven weeks to produce the model-adoption scorecard. Runs are large and continue over weekends.",
                 confidence="high", magnitude_pct=50, uncertainty="Run count per night was planned; actual prompt sizes grew during the period.")
    S.task(ev, "asana", "AI Labs › Agent Evaluation Harness", "Nightly cross-provider harness runs for the adoption scorecard", crew[0], at(date(2026, 4, 9), 17, 0),
           date(2026, 5, 29), "Complete", f"# Nightly cross-provider harness runs for the adoption scorecard\n\n**Assignee:** {crew[0].name} · **Status:** Complete · **Due:** May 29\n\n"
           "Run the full harness nightly (incl. weekends) on Claude Opus/Sonnet 5.5, GPT-5.2, Gemini 3.5 Pro. ~2,400 tasks per run at full context. Output feeds the Model Adoption Program scorecard.",
           prev_status="In progress", status_changed_at=at(date(2026, 5, 29), 23, 0))

    # Safety & Trust: Trip Audio Review Tooling accelerated for a regulator deadline.
    t, L = "safety-trust", lead("safety-trust")
    crew = members(t, 0.6)
    ev = S.event(kind="project_accelerated", scope="team", team_ids=[t], person_ids=[p.id for p in crew], project="Trip Audio Review Tooling",
                 starts_on=date(2026, 8, 10), ends_on=date(2026, 9, 15), multiplier=1.3, announced_on=date(2026, 8, 10),
                 title="Trip Audio Review deadline moved up to Sep 15 for a regulator filing",
                 summary=f"An Asana due-date change by {L.name} pulled Trip Audio Review Tooling from Oct 30 to Sep 15 to meet a state regulator's filing date. The {len(crew)} engineers on it ran more review-summary batches than planned.",
                 confidence="high", magnitude_pct=30, uncertainty="The task does not say how much of the work was already done.")
    S.task(ev, "asana", "Safety & Trust › Trip Audio Review Tooling", "Reviewer tooling GA for state filing", crew[0], at(date(2026, 6, 22), 17, 0), date(2026, 9, 15), "Complete",
           f"# Reviewer tooling GA for state filing\n\n**Assignee:** {crew[0].name} · **Status:** Complete · **Due:** Sep 15 (was Oct 30)\n\n**{L.name}** changed the due date to **Sep 15** (was Oct 30) on Aug 10: *regulator filing date confirmed*.\n\n"
           f"**{crew[0].name}** commented: pulling the remaining summary-quality passes into the next five weeks.", prev_due_on=date(2026, 10, 30), prev_status="In progress", status_changed_at=at(date(2026, 9, 15), 22, 0))

    # Payments & Risk: Fraud Rules Migration on hold from Oct 12 until the Q4 change freeze lifts (Jan 11).
    t, L = "payments-risk", lead("payments-risk")
    crew = members(t, 0.55)
    ev = S.event(kind="project_paused", scope="team", team_ids=[t], person_ids=[p.id for p in crew], project="Fraud Rules Migration",
                 starts_on=date(2026, 10, 12), ends_on=date(2027, 1, 10), multiplier=0.5, announced_on=date(2026, 10, 9),
                 title="Fraud Rules Migration on hold from Oct 12 until the Q4 change freeze lifts",
                 summary=f"{L.name} put the Fraud Rules Migration on hold from Oct 12: payments enters its Q4 change freeze early and the migration cannot ship until Jan 11. "
                         f"The {len(crew)} people on it move to monitoring and model-review work at roughly half their recent usage for the rest of the year.",
                 confidence="high", magnitude_pct=-50, uncertainty="Freeze dates are firm; the people could be re-assigned to other API-heavy work.")
    S.message(ev, "gmail", at(date(2026, 10, 9), 22, 40), L, [p.name for p in crew], "Fraud Rules Migration: on hold through the Q4 freeze",
              email_header(L.name, [p.name for p in crew] + ["finance-ai-spend@" + C.EMAIL_DOMAIN], "Fraud Rules Migration: on hold through the Q4 freeze", at(date(2026, 10, 9), 22, 40)) +
              f"Team,\n\nThe payments change freeze starts **Mon Oct 12** this year (two weeks earlier than usual) and runs to **Jan 11**. Since the Fraud Rules Migration cannot ship inside the freeze, "
              f"**the project is on hold for now**. Please wrap up open PRs by Friday and move to the monitoring and model-review rotation.\n\nFinance (cc): expect our API usage to drop for the rest of Q4; the migration budget carries into Q1.\n\n" + L.first)
    S.task(ev, "monday", "Payments › Risk Roadmap", "Fraud Rules Migration", L, at(date(2026, 5, 4), 18, 0), date(2027, 2, 27), "On hold",
           f"| Project | Owner | Timeline | Status |\n|---|---|---|---|\n| Fraud Rules Migration | {L.name} | May 4 - Dec 11 → Jan 11 - Feb 27 | **On hold** (was Working on it) |\n\n"
           f"Status changed by {L.name} on Oct 9: *Q4 change freeze starts Oct 12*.", prev_due_on=date(2026, 12, 11), prev_status="Working on it", status_changed_at=at(date(2026, 10, 9), 22, 45))

    # Maps & Routing: ETA Model v7 retrain on Gemini 3.5 right after adoption.
    t, L = "maps-routing", lead("maps-routing")
    crew = members(t, 0.6)
    ev = S.event(kind="project_accelerated", scope="team", team_ids=[t], person_ids=[p.id for p in crew], project="ETA Model v7",
                 starts_on=date(2026, 2, 24), ends_on=date(2026, 3, 20), multiplier=1.3, announced_on=date(2026, 2, 12), claim_type="stated_plan",
                 title="ETA Model v7 retrain moved to Gemini 3.5 Pro the week of adoption",
                 summary="Maps & Routing ran the ETA v7 retrain and its evaluation on Gemini 3.5 Pro from Feb 24, as stated in the adoption thread, lifting the team's Google usage for four weeks.",
                 confidence="medium", magnitude_pct=30, uncertainty="The retrain was planned; its token volume was not estimated in the thread.")
    S.task(ev, "asana", "Maps › ETA Model v7", "Retrain ETA v7 explanations on Gemini 3.5 Pro", crew[0], at(date(2026, 2, 12), 19, 0), date(2026, 3, 20), "Complete",
           f"# Retrain ETA v7 explanations on Gemini 3.5 Pro\n\n**Assignee:** {crew[0].name} · **Status:** Complete · **Due:** Mar 20\n\nSwitch the explanation generator and the eval set to Gemini 3.5 Pro; run the full city regression at full context before cutting over.",
           prev_status="In progress", status_changed_at=at(date(2026, 3, 20), 22, 0))

    # Rider App: Rider Support Copilot launch slips Sep 14 -> Oct 19.
    t, L = "rider-app", lead("rider-app")
    crew = members(t, 0.5)
    ev = S.event(kind="project_deferred", scope="team", team_ids=[t], person_ids=[p.id for p in crew], project="Rider Support Copilot",
                 starts_on=date(2026, 8, 31), ends_on=date(2026, 9, 18), multiplier=0.72, announced_on=date(2026, 8, 31),
                 title="Rider Support Copilot launch moved from Sep 14 to Oct 19",
                 summary=f"The monday.com roadmap moved the Rider Support Copilot launch back five weeks after app-review feedback. The {len(crew)} people on it did less generation work during the re-scope, then ramped back up for the October date.",
                 confidence="high", magnitude_pct=-28, uncertainty="The re-scope length is the lead's estimate.")
    S.task(ev, "monday", "Rider › App Roadmap", "Rider Support Copilot", L, at(date(2026, 5, 18), 18, 0), date(2026, 10, 19), "Working on it",
           f"| Project | Owner | Launch | Status |\n|---|---|---|---|\n| Rider Support Copilot | {L.name} | **Oct 19** (was Sep 14) | Working on it |\n\nTimeline moved by {L.name} on Aug 31: *app review feedback requires a re-scope of the escalation flow*.",
           prev_due_on=date(2026, 9, 14), status_changed_at=at(date(2026, 8, 31), 17, 0))
    S.event(kind="project_accelerated", scope="team", team_ids=[t], person_ids=[p.id for p in crew], project="Rider Support Copilot",
            starts_on=date(2026, 9, 21), ends_on=date(2026, 10, 19), multiplier=1.2, announced_on=date(2026, 8, 31),
            title="Rider Support Copilot build resumes Sep 21 toward the Oct 19 launch",
            summary="After the re-scope the same group built toward the new date at a higher pace than its summer trend.",
            confidence="medium", magnitude_pct=20, uncertainty="Inferred from the new launch date.")

    # Driver App: Driver Assist Chat scope increase Oct 5 - Dec 11 (partly future).
    t, L = "driver-app", lead("driver-app")
    crew = members(t, 0.6)
    ev = S.event(kind="project_accelerated", scope="team", team_ids=[t], person_ids=[p.id for p in crew], project="Driver Assist Chat",
                 starts_on=date(2026, 10, 5), ends_on=date(2026, 12, 11), multiplier=1.3, announced_on=date(2026, 10, 2),
                 title="Driver Assist Chat scope expanded; due Dec 11",
                 summary=f"An Asana epic assigned to {crew[0].name} expands Driver Assist Chat from FAQ answers to earnings and trip-issue resolution, due Dec 11. "
                         f"{len(crew)} people are on it and the team expects higher Anthropic usage through the quarter.",
                 confidence="high", magnitude_pct=30, uncertainty="The epic estimates effort, not tokens; the multiplier is based on comparable Q2 work.")
    S.task(ev, "asana", "Driver › Driver Assist Chat", "Expand Driver Assist Chat to earnings and trip-issue resolution", crew[0], at(date(2026, 10, 2), 17, 0), date(2026, 12, 11), "In progress",
           f"# Expand Driver Assist Chat to earnings and trip-issue resolution\n\n**Assignee:** {crew[0].name} · **Status:** In progress · **Due:** Dec 11\n\n"
           f"Added by {L.name} on Oct 2. Scope grows from FAQ to earnings explanations and trip-issue resolution with tool calls into the support backend. Team: {', '.join(p.first for p in crew)}. Expect heavier Sonnet 5.5 usage through the quarter.")

    # Security: Vendor Review Automation paused for the SOC 2 audit window.
    t, L = "security", lead("security")
    crew = members(t, 0.6)
    ev = S.event(kind="project_paused", scope="team", team_ids=[t], person_ids=[p.id for p in crew], project="Vendor Review Automation",
                 starts_on=date(2026, 4, 6), ends_on=date(2026, 4, 24), multiplier=0.6, announced_on=date(2026, 4, 2),
                 title="Vendor Review Automation paused during the SOC 2 audit window",
                 summary="Security paused its automation project for three weeks in April while the team supported the SOC 2 audit; usage dipped accordingly.",
                 confidence="high", magnitude_pct=-40, uncertainty="None; the window was fixed.")
    S.message(ev, "slack", at(date(2026, 4, 2), 17, 20), L, ["#security"], "#security",
              f"**{L.name}** · {fmt(date(2026, 4, 2))} 09:20 — Audit fieldwork is **Apr 6-24**. Vendor Review Automation is paused for those three weeks; {', '.join(p.first for p in crew)} are on evidence collection with me.")

    # Finance & Legal: quarter-close weeks.
    t, L = "finance-legal", lead("finance-legal")
    crew = [p for p in by_team[t] if "Analyst" in p.role or p.is_lead]
    for start in (date(2026, 1, 5), date(2026, 4, 1), date(2026, 7, 1), date(2026, 10, 1)):
        end = business_days_from(start, 7)
        ev = S.event(kind="quarter_close", scope="team", team_ids=[t], person_ids=[p.id for p in crew], project="Close Automation",
                     starts_on=start, ends_on=end, multiplier=1.5, announced_on=start - timedelta(days=4), claim_type="observed_event",
                     title=f"Quarter close: {fmt(start)} - {fmt(end)}",
                     summary="The finance analysts run reconciliation and variance-explanation prompts heavily during the close calendar; usage rises for the first seven business days of each quarter.",
                     confidence="high", magnitude_pct=50, uncertainty="Recurring pattern; magnitude varies with the number of open items.")
        S.message(ev, "outlook", at(start - timedelta(days=4), 16, 0), L, ["FP&A"], f"Close calendar: {fmt(start)} - {fmt(end)}",
                  email_header(L.name, ["fpa@" + C.EMAIL_DOMAIN], f"Close calendar: {fmt(start)} - {fmt(end)}", at(start - timedelta(days=4), 16, 0)) +
                  f"Team,\n\nClose runs **{fmt(start)} through {fmt(end)}**. Reconciliations and variance commentary are due by day 5; the Close Automation prompts are approved for all accounts this cycle.\n\n{L.first}")

    # Marketing & Comms: summer campaign crunch, Q4 holiday campaign (future).
    t, L = "marketing-comms", lead("marketing-comms")
    crew = members(t, 0.7)
    for (s, e, label, announced) in ((date(2026, 6, 8), date(2026, 6, 22), "summer rider campaign", date(2026, 6, 4)),
                                     (date(2026, 11, 2), date(2026, 11, 25), "holiday campaign", date(2026, 10, 19))):
        ev = S.event(kind="project_accelerated", scope="team", team_ids=[t], person_ids=[p.id for p in crew], project="Lifecycle Campaign Generator",
                     starts_on=s, ends_on=e, multiplier=1.4, announced_on=announced,
                     title=f"Marketing content crunch for the {label} ({fmt(s)} - {fmt(e)})",
                     summary=f"The {label} launches on {fmt(e)}; the content team generates and localizes variants for three weeks beforehand, roughly 40% above its normal pace.",
                     confidence="high" if s < C.AS_OF else "medium", magnitude_pct=40,
                     uncertainty="Variant count is set by the brief; the localization pass can grow it.")
        S.task(ev, "asana", "Marketing › Campaigns", f"{label.title()}: generate and localize variants", crew[0], at(announced, 17, 0), e, "In progress" if s < C.AS_OF else "Not started",
               f"# {label.title()}: generate and localize variants\n\n**Assignee:** {crew[0].name} · **Due:** {fmt(e)}\n\n~120 variants x 9 locales through the Lifecycle Campaign Generator; brand-voice check on every variant.")

    # People & Recruiting: hiring freeze Aug 17 - Oct 5.
    t, L = "people-recruiting", lead("people-recruiting")
    crew = [p for p in by_team[t] if "Recruiter" in p.role]
    ev = S.event(kind="hiring_freeze", scope="team", team_ids=[t], person_ids=[p.id for p in crew], project="Interview Note Summaries",
                 starts_on=date(2026, 8, 17), ends_on=date(2026, 10, 4), multiplier=0.55, announced_on=date(2026, 8, 13),
                 title="Hiring freeze Aug 17 to Oct 5",
                 summary="A hiring freeze cut the interview volume for seven weeks; recruiters' use of interview-note summaries and job-description drafting fell by about half.",
                 confidence="high", magnitude_pct=-45, uncertainty="None; the freeze lifted on the stated date.")
    S.message(ev, "gmail", at(date(2026, 8, 13), 16, 0), L, ["recruiting@" + C.EMAIL_DOMAIN], "Hiring freeze: Aug 17 through Oct 5",
              email_header(L.name, ["recruiting@" + C.EMAIL_DOMAIN], "Hiring freeze: Aug 17 through Oct 5", at(date(2026, 8, 13), 16, 0)) +
              "Team,\n\nLeadership approved a hiring freeze from **Aug 17 through Oct 5** for all non-critical roles. Pipelines pause at the current stage; interview loops already scheduled for next week go ahead. Expect a quiet few weeks.\n\n" + L.first)
    S.message(ev, "gmail", at(date(2026, 10, 1), 16, 0), L, ["recruiting@" + C.EMAIL_DOMAIN], "Freeze lifts Monday Oct 5",
              email_header(L.name, ["recruiting@" + C.EMAIL_DOMAIN], "Freeze lifts Monday Oct 5", at(date(2026, 10, 1), 16, 0)) +
              "The hiring freeze lifts **Monday Oct 5** as planned. Reopen your pipelines and reschedule paused loops.\n\n" + L.first)


# ---------------------------------------------------------------------------------------------
# person-level storylines (sampled)
# ---------------------------------------------------------------------------------------------

def person_storylines(S: Storyline, teams: list, people: list, by_team: dict, rnd: random.Random) -> None:
    def manager(p: Person) -> Person:
        return by_team[p.team_id][0]

    def random_window(start: date, end: date, min_days: int, max_days: int):
        span = (end - start).days - max_days
        s = start + timedelta(days=rnd.randint(0, max(0, span)))
        s = nearest_weekday(s, 0)  # start on a Monday
        length = rnd.randint(min_days, max_days)
        return s, s + timedelta(days=length - 1)

    non_leads = [p for p in people if not p.is_lead]

    # Onboarding: 10 people start during the year.
    joiners = rnd.sample(non_leads, 10)
    for p in joiners:
        p.start_date = nearest_weekday(date(2026, 2, 2) + timedelta(days=rnd.randint(0, 220)), 0)
        m = manager(p)
        ev = S.event(kind="onboarding", scope="person", team_ids=[p.team_id], person_ids=[p.id], project=None,
                     starts_on=p.start_date, ends_on=p.start_date + timedelta(days=27), multiplier=1.0, announced_on=p.start_date, claim_type="observed_event",
                     title=f"{p.first} joined {next(t.name for t in teams if t.id == p.team_id)} on {fmt(p.start_date)}",
                     summary=f"A Slack welcome thread shows {p.name} started on {fmt(p.start_date)} as {p.role}. Usage starts near zero and ramps over the first four weeks as seats and access are set up.",
                     confidence="high", magnitude_pct=None, uncertainty="Ramp speed varies by person.")
        S.message(ev, "slack", at(p.start_date, 17, 0), m, [f"#{p.team_id}"], f"#{p.team_id}",
                  f"**{m.name}** · {fmt(p.start_date)} 09:00 — welcome {p.first}! {p.first} joins us as {p.role}. Cursor/Claude Code seat and API workspace access are set up; pair with {by_team[p.team_id][1].first if by_team[p.team_id][1].id != p.id else by_team[p.team_id][2].first} this week.\n\n"
                  f"**{p.name}** 09:14 — thanks all, excited to be here.")

    # Departures: 5 people leave during the year.
    leavers = rnd.sample([p for p in non_leads if p not in joiners], 5)
    people_lead = by_team["people-recruiting"][0]
    for p in leavers:
        p.end_date = nearest_weekday(date(2026, 3, 2) + timedelta(days=rnd.randint(0, 200)), 4)  # a Friday
        ev = S.event(kind="departure", scope="person", team_ids=[p.team_id], person_ids=[p.id], project=None,
                     starts_on=p.end_date + timedelta(days=1), ends_on=None, multiplier=0.0, announced_on=workday(p.end_date - timedelta(days=10)), claim_type="observed_event",
                     title=f"{p.first}'s last day is {fmt(p.end_date)}",
                     summary=f"An offboarding notice from People Ops gives {p.name}'s last day as {fmt(p.end_date)}; seats are removed and usage stops.",
                     confidence="high", magnitude_pct=-100, uncertainty="None.")
        S.message(ev, mail_channel(p), at(workday(p.end_date - timedelta(days=10)), 18, 0), people_lead, [manager(p).name, "it-helpdesk@" + C.EMAIL_DOMAIN], f"Offboarding: {p.name} (last day {fmt(p.end_date)})",
                  email_header(people_lead.name, [manager(p).name, "it-helpdesk@" + C.EMAIL_DOMAIN], f"Offboarding: {p.name} (last day {fmt(p.end_date)})", at(workday(p.end_date - timedelta(days=10)), 18, 0)) +
                  f"Hi {manager(p).first},\n\n{p.name}'s last day is **{p.end_date.strftime('%A %B %-d')}**. IT will remove the coding-assistant seat and API workspace access at end of day. Please reassign open tasks before then.\n\n{people_lead.first}\nPeople Operations")

    # Out of office: ~40% of people, 1-3 weeks; some after AS_OF (announced before).
    pool = [p for p in people if p not in leavers]
    ooo_people = rnd.sample(pool, int(len(pool) * 0.42))
    for i, p in enumerate(ooo_people):
        if i < 9:  # future OOO announced before AS_OF
            s, e = random_window(date(2026, 10, 26), date(2026, 12, 18), 5, 12)
            announced = workday(C.AS_OF - timedelta(days=rnd.randint(1, 12)))
        else:
            s, e = random_window(date(2026, 1, 12), date(2026, 10, 23), 5, 19)
            announced = workday(s - timedelta(days=rnd.randint(3, 14)))
        if p.start_date > s or (p.end_date and p.end_date < e):
            continue
        reason = rnd.choice(["vacation", "vacation", "vacation", "parental leave", "conference travel", "medical leave", "jury duty"])
        ev = S.event(kind="out_of_office", scope="person", team_ids=[p.team_id], person_ids=[p.id], project=None,
                     starts_on=s, ends_on=e, multiplier=0.03, announced_on=announced, claim_type="observed_event",
                     title=f"{p.first} out of office {fmt(s)} - {fmt(e)} ({reason})",
                     summary=f"The team's monday.com availability board and {p.first}'s message mark {p.name} out of office from {fmt(s)} to {fmt(e)} ({reason}); usage stops for the window.",
                     confidence="high", magnitude_pct=-97, uncertainty="Return date could shift by a day or two." if reason != "vacation" else "")
        if task_tool(p) == "monday":
            S.task(ev, "monday", f"{next(t.name for t in teams if t.id == p.team_id)} › Team availability", f"{p.name} - Out of office", p, at(announced, 18, 0), e, "Out of office",
                   f"# Team availability\n\n| Person | Status | Dates | Note |\n|---|---|---|---|\n| {p.name} | Out of office | {fmt(s)} - {fmt(e)} | {reason} |")
        else:
            S.task(ev, "asana", f"{next(t.name for t in teams if t.id == p.team_id)} › Team calendar", f"OOO: {p.name} ({fmt(s)} - {fmt(e)})", p, at(announced, 18, 0), e, "Scheduled",
                   f"# OOO: {p.name}\n\n**Dates:** {fmt(s)} - {fmt(e)} · **Reason:** {reason} · **Backup:** {manager(p).name}")
        ch = chat_channel(p)
        if rnd.random() < 0.5 or s > C.AS_OF:
            S.message(ev, ch, at(announced, 18, 30), p, [f"#{p.team_id}"], f"#{p.team_id}" if ch == "slack" else f"{next(t.name for t in teams if t.id == p.team_id)} › General",
                      f"**{p.name}** · {fmt(announced)} 10:30 — heads up, I'm out **{fmt(s)} - {fmt(e)}** ({reason}). {manager(p).first} has context on my open items; I won't be checking messages.")
        else:
            S.message(ev, mail_channel(p), at(s, 14, 0), p, ["(auto-reply)"], f"Automatic reply: Out of office until {fmt(e + timedelta(days=1))}",
                      email_header(p.name, ["(auto-reply)"], f"Automatic reply: Out of office until {fmt(e + timedelta(days=1))}", at(s, 14, 0)) +
                      f"I am out of the office from {fmt(s)} and back on {fmt(e + timedelta(days=1))} with no access to email. For anything urgent please contact {manager(p).name}.")

    # Extra load / crunch: ~20% of people, 2-3 weeks, includes a Saturday message; some future.
    busy = {pid for ev in S.events if ev.scope == 'team' and ev.kind in ('project_paused', 'project_deferred', 'hiring_freeze') for pid in ev.person_ids}
    crunch_people = rnd.sample([p for p in pool if p not in ooo_people[:9] and p.id not in busy and not p.is_lead], int(len(pool) * 0.2))
    for i, p in enumerate(crunch_people):
        team = next(t for t in teams if t.id == p.team_id)
        project = rnd.choice(team.projects)
        if i < 6:
            s, e = random_window(date(2026, 10, 26), date(2026, 12, 11), 10, 19)
            announced = workday(C.AS_OF - timedelta(days=rnd.randint(1, 10)))
        else:
            s, e = random_window(date(2026, 1, 12), date(2026, 10, 16), 10, 21)
            announced = workday(s - timedelta(days=rnd.randint(0, 5)))
        if p.start_date > s or (p.end_date and p.end_date < e):
            continue
        m = manager(p)
        mult = round(rnd.uniform(1.6, 2.1), 2)
        ev = S.event(kind="extra_load", scope="person", team_ids=[p.team_id], person_ids=[p.id], project=project,
                     starts_on=s, ends_on=e, multiplier=mult, weekend_multiplier=0.8, announced_on=announced,
                     title=f"{p.first} took on the {project} push ({fmt(s)} - {fmt(e)})",
                     summary=f"{m.name} assigned {p.name} the {project} delivery with a {fmt(e)} due date on top of current work. {p.first} said they would be heads-down, including weekends; usage runs at roughly {mult:.1f}x the prior baseline for the window.",
                     confidence="high", magnitude_pct=int((mult - 1) * 100), uncertainty="The task gives a due date, not an effort estimate.")
        S.task(ev, task_tool(p), f"{team.name} › {project}", f"{project}: deliver by {fmt(e)}", p, at(announced, 17, 0), e,
               "In progress" if s <= C.AS_OF else "Not started",
               (f"# {project}: deliver by {fmt(e)}\n\n**Assignee:** {p.name} · **Added by:** {m.name} · **Due:** {fmt(e)}\n\nTaking this on in addition to current scope. Expect heavy coding-assistant and API usage until the due date."
                if task_tool(p) == "asana" else
                f"| Item | Owner | Due | Status |\n|---|---|---|---|\n| {project}: deliver by {fmt(e)} | {p.name} | {fmt(e)} | {'Working on it' if s <= C.AS_OF else 'Not started'} |\n\nAdded by {m.name} on {fmt(announced)}."))
        ch = chat_channel(p)
        where = f"#{p.team_id}" if ch == "slack" else f"{team.name} › General"
        S.message(ev, ch, at(announced, 20, 0), p, [where], where,
                  f"**{p.name}** · {fmt(announced)} 12:00 — picking up the **{project}** delivery for {fmt(e)} on top of my current work. Going to be heads-down for the next few weeks; expect slower reviews from me.\n\n"
                  f"**{m.name}** 12:08 — thank you. Drop anything that is not {project} or on-call.")
        sat = nearest_weekday(s + timedelta(days=5), 5)
        if sat <= min(e, C.AS_OF):
            S.message(ev, ch, at(sat, 21, 15), p, [where], where,
                      f"**{p.name}** · {sat.strftime('%a %b %-d')} 13:15 — working through the weekend on {project}; have the generation runs going so Monday is review-only.")

    # Model change tasks after the April and May adoptions: 14 people.
    mc_people = rnd.sample([p for p in pool if p not in crunch_people and not p.is_lead and p.id not in busy], 14)
    for i, p in enumerate(mc_people):
        team = next(t for t in teams if t.id == p.team_id)
        project = rnd.choice(team.projects)
        if i < 8:
            adoption, model_name, override = date(2026, 4, 1), "Claude Sonnet 5.5", {"anthropic": {"claude-sonnet-5.5": 0.7, "claude-opus-5.5": 0.3}}
            if i % 3 == 0:
                model_name, override = "Claude Opus 5.5", {"anthropic": {"claude-opus-5.5": 0.75, "claude-sonnet-5.5": 0.25}}
        else:
            adoption, model_name, override = date(2026, 5, 26), "GPT-5.5", {"openai": {"gpt-5.5": 0.85, "gpt-5.5-mini": 0.15}}
        s = adoption + timedelta(days=rnd.randint(0, 12))
        e = s + timedelta(days=13)
        if p.start_date > s or (p.end_date and p.end_date < e):
            continue
        ev = S.event(kind="model_change", scope="person", team_ids=[p.team_id], person_ids=[p.id], project=project,
                     starts_on=s, ends_on=e + timedelta(days=16), multiplier=1.35, announced_on=s - timedelta(days=2),
                     model_override=override,
                     title=f"{p.first} migrates {project} to {model_name}",
                     summary=f"An Asana task assigned to {p.name} migrates {project} to {model_name}. Early runs use longer contexts for the comparison, so {p.first}'s API usage runs about a third above baseline for two weeks and the model mix shifts to {model_name}.",
                     confidence="high", magnitude_pct=35, uncertainty="The task does not give a token estimate; the comparison window is the usual two weeks.")
        S.task(ev, "asana", f"{team.name} › {project}", f"Migrate {project} to {model_name}", p, at(s - timedelta(days=2), 17, 0), e, "Complete" if e < C.AS_OF else "In progress",
               f"# Migrate {project} to {model_name}\n\n**Assignee:** {p.name} · **Due:** {fmt(e)}\n\nSwitch the default model to {model_name}; re-run the regression set at full context before cutting over. Expect higher token volume during the comparison runs.",
               prev_status="In progress" if e < C.AS_OF else None, status_changed_at=at(e, 22, 0) if e < C.AS_OF else None)

    # Weekend-heavy individuals who post on Saturdays about a high period (not tied to a project push).
    for p in rnd.sample([p for p in pool if p.team_id in ("ai-labs", "infra-sre", "marketplace-pricing", "support-automation") and not p.is_lead], 4):
        sat = nearest_weekday(date(2026, 3, 2) + timedelta(days=rnd.randint(0, 200)), 5)
        ev = S.event(kind="extra_load", scope="person", team_ids=[p.team_id], person_ids=[p.id], project=None,
                     starts_on=sat - timedelta(days=5), ends_on=sat + timedelta(days=8), multiplier=1.5, weekend_multiplier=0.85, announced_on=sat, claim_type="observed_event",
                     title=f"{p.first}'s Saturday message shows a high-intensity stretch around {fmt(sat)}",
                     summary=f"{p.name} posted on Saturday {fmt(sat)} about running batches through the weekend; the surrounding two weeks run well above {p.first}'s baseline.",
                     confidence="medium", magnitude_pct=50, uncertainty="Observed, not planned; no end date was stated.")
        S.message(ev, chat_channel(p), at(sat, 18, 20), p, [f"#{p.team_id}"], f"#{p.team_id}",
                  f"**{p.name}** · {sat.strftime('%a %b %-d')} 10:20 — in the zone this week, batch runs going all weekend so I can compare results Monday. Don't wait on me for reviews until Tuesday.")


def build_storylines(teams: list, people: list, rnd: random.Random) -> Storyline:
    by_team = {t.id: [p for p in people if p.team_id == t.id] for t in teams}
    for t in teams:  # lead first
        by_team[t.id].sort(key=lambda p: (not p.is_lead, p.id))
    S = Storyline()
    company_storylines(S, teams, people, by_team, rnd)
    team_storylines(S, by_team, rnd)
    person_storylines(S, teams, people, by_team, rnd)
    S.events.sort(key=lambda e: (e.announced_on, e.id))
    S.messages.sort(key=lambda m: m.sent_at)
    S.tasks.sort(key=lambda t: t.created_at)
    return S
