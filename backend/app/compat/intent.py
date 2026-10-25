"""Free chat text -> a typed agent run request (or a clarifying question). Deterministic, no model.

The parse can be wrong, so every reply states how the text was read (`Intent.read_as`). Rules
(docs/frontend-alignment.md §4.3):
- revise / amend [this proposal | prop_x][: change] (the dashboard's Revise and "Ask for a refreshed proposal"
  buttons prefill "Revise this proposal: ") targets the proposal named by id, else the only open proposal;
  with several open and no id, compat asks which (it never picks one silently). The change text is read
  like a budget request, defaulting to the target's mode and favoured team ("make it 40k for research").
  A change that drafts -> propose_allocation, and compat marks the target `revised` by the new draft. No
  change text: a stale target is refreshed, a pending one gets a question about what to change.
- refresh / rebase / update + a stale proposal  -> propose_allocation {stale_proposal_id}; with several
  stale proposals and no id, compat asks which.
- redistribute / rebalance / move / reallocate / shift / transfer -> propose_allocation {mode: transfer}
  (an amount, if given, caps the funds moved)
- add / additional / more / extra / increase / top up + budget words or an amount
  -> propose_allocation {mode: addition, amount}. No amount -> ask; never default an amount.
  "another" / "allocate" count as an addition only next to a dollar amount and outside a question
  ("We have another $25,000 to allocate this week", not "why did you allocate $25,000 to Research?").
- A negative amount ("add -5k", "minus $5,000") is never read as a positive one: compat asks.
- what changed / read the documents / interpret / context -> interpret_corpus
- anything else -> answer_question with the text as the instruction
The team named as the destination ("to / toward / into / for / prioritizing <team>") becomes
`prioritize`; a team named only as a source ("from <team>") never does. Without a destination, the
first team named that is not a source; without one, the team whose projection exceeds its allocation
by the most. With no projection available and no team named, compat asks.
Amounts are parsed as Decimal strings ("50k" -> "50000.00", "5000 dollars", "7500 USD"); a float never
reaches the backend. A bare four-digit number counts unless it looks like a year (1900-2100). An amount
in another unit (credits, tokens, hours, EUR, ...) is never read as USD: compat asks instead.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping, Sequence

from app.core.money import MoneyError, money_str, parse_money

_TRANSFER = re.compile(r"\b(redistribut\w*|rebalanc\w*|reallocat\w*|move|moving|shift\w*|transfer\w*)\b")
_ADDITION = re.compile(r"\b(add|adding|additional|more|extra|increase\w*|top[- ]?up|grow|expand)\b")
# Addition words that are only a budget request when an amount comes with them ("another $25,000 to allocate").
_ADDITION_WITH_AMOUNT = re.compile(r"\b(another|allocate)\b")
# A question about an allocation ("why did you allocate $25,000 ...?") is not a request to add one.
_QUESTION_LEAD = re.compile(r"^(why|what|which|who|when|where|did|does|do|is|are|was|were|has|have|explain)\b")
_REVISE = re.compile(r"\b(revis\w*|amend\w*)\b")
# The command part of a revise/refresh message; what follows is the requested change.
_REVISE_LEAD = re.compile(
    r"^\s*(?:please\s+)?(?:can you\s+)?(?:revis\w*|amend\w*|refresh\w*|rebase\w*|redo|update)\s*"
    r"(?:(?:this|the|that|my|it)\s*)?(?:(?:proposal|draft)\s*)?(?:prop_[a-z0-9]+\s*)?(?:[:,;\-\u2013\u2014]\s*)?")
_FILLER = re.compile(r"^(?:please|thanks|thank you|it|now)?[\s.!?]*$")
# A minus sign (or the word) directly before an amount: "-5k", "$-5,000", "minus $5,000".
_NEGATIVE = re.compile(r"(?<![\w.])[-\u2212]\s*\$?\s*\d|\$\s*[-\u2212]\s*\d|\b(?:minus|negative)\s+\$?\s*\d")
_BUDGET_WORDS = re.compile(r"\b(budget|funding|funds|money|envelope|allocation|spend)\b")
_INTERPRET = re.compile(r"(what('s| has)? changed|what is new|what's new|read (the )?(docs|documents|corpus)|"
                        r"\binterpret\w*|\bcontext\b|\bsignals?\b)")
_REFRESH = re.compile(r"\b(refresh\w*|rebase\w*|redo|update the proposal|refreshed)\b")
_PROPOSAL_ID = re.compile(r"\b(prop_[a-z0-9]+)\b")
_NUM = r"\d[\d,]*(?:\.\d+)?"
_AMOUNT = re.compile(
    rf"(?P<dollar>\$)\s*(?P<a>{_NUM})\s*(?P<s1>k|m|thousand|million)?\b"
    rf"|\b(?P<b>{_NUM})\s*(?P<s2>k|m|thousand|million)\b"
    rf"|\b(?P<e>{_NUM})\s*(?:dollars?|usd|bucks)\b"
    r"|\b(?P<c>\d{1,3}(?:,\d{3})+(?:\.\d+)?)\b"
    r"|\b(?P<d>\d{4,}(?:\.\d+)?)\b",
    re.IGNORECASE,
)
# A number followed by a unit that is not the envelope's dollars. Never converted, never read as USD.
_OTHER_UNIT = re.compile(
    rf"(?:\b{_NUM}\s*(?:k|m|thousand|million)?\s*"
    r"(?P<unit>credits?|tokens?|gpu[- ]?hours?|hours?|hrs?|seats?|requests?|calls?|eur|euros?|gbp|pounds?|"
    r"yen|jpy|inr|rupees?|cad|aud)\b)"
    rf"|(?P<sym>[€£¥₹])\s*{_NUM}",
    re.IGNORECASE,
)
_DESTINATION = r"(?:to|toward|towards|into|for|prioriti[sz]\w*|favou?r\w*)\s+(?:the\s+)?"
_SOURCE = r"(?:from|out of|away from)\s+(?:the\s+)?"
_SCALE = {"k": Decimal(1000), "thousand": Decimal(1000), "m": Decimal(1_000_000), "million": Decimal(1_000_000)}


@dataclass
class Intent:
    """Either `run` (an AgentRunCreate body) or `ask` (a clarifying reply, nothing is run)."""

    read_as: str
    run: dict[str, Any] | None = None
    ask: str | None = None
    notes: list[str] = field(default_factory=list)
    # A proposal the run's draft replaces (chat revise): compat marks it `revised` by the new draft.
    revises: str | None = None


def parse_amount(text: str) -> str | None:
    """The money amount in the text as a canonical decimal string, or None. Explicit dollar amounts
    ("$5,000", "5k", "5000 dollars") win over bare numbers; a bare four-digit number that looks like a year
    is not an amount. Raises MoneyError on an amount that is not valid money (e.g. three decimal places)."""
    bare: str | None = None
    for m in _AMOUNT.finditer(text):
        raw = m.group("a") or m.group("b") or m.group("e") or m.group("c") or m.group("d")
        suffix = (m.group("s1") or m.group("s2") or "").lower()
        try:
            value = Decimal(raw.replace(",", ""))
        except InvalidOperation:
            continue
        if suffix:
            value = value * _SCALE[suffix]
        if m.group("dollar") or m.group("e") or suffix:
            return money_str(parse_money(value))
        if m.group("d") and len(raw) == 4 and 1900 <= value <= 2100:
            continue  # "in 2026": a year, not an amount
        if bare is None:
            bare = money_str(parse_money(value))
    return bare


def other_unit(text: str) -> str | None:
    """The first non-dollar unit an amount in the text is given in ("credits", "tokens", "EUR", ...)."""
    m = _OTHER_UNIT.search(text)
    if m is None:
        return None
    return (m.group("unit") or m.group("sym")).lower()


def _mentions(text: str, teams: Sequence[tuple[str, str]]) -> list[tuple[int, int, str]]:
    found = []
    for team_id, name in teams:
        for word in {team_id.lower(), name.lower()}:
            for m in re.finditer(rf"\b{re.escape(word)}\b", text):
                found.append((m.start(), m.end(), team_id))
    return sorted(found)


def find_team(text: str, teams: Sequence[tuple[str, str]]) -> str | None:
    """The team the text asks to favour: the first one named as a destination ("to research", "toward
    Product", "prioritizing research"); else the first one mentioned that is not named as a source
    ("from product"). A source team is never returned."""
    mentions = _mentions(text, teams)
    for start, _, team in mentions:
        if re.search(rf"{_DESTINATION}$", text[:start]):
            return team
    for start, _, team in mentions:
        if not re.search(rf"{_SOURCE}$", text[:start]):
            return team
    return None


def source_team(text: str, teams: Sequence[tuple[str, str]]) -> str | None:
    """The first team named as a source ("from product")."""
    for start, _, team in _mentions(text, teams):
        if re.search(rf"{_SOURCE}$", text[:start]):
            return team
    return None


def most_over(gaps: Mapping[str, Decimal]) -> str | None:
    """Team whose projection exceeds its allocation by the most (ties broken by id)."""
    over = sorted(((g, t) for t, g in gaps.items() if g > 0), key=lambda x: (-x[0], x[1]))
    return over[0][1] if over else None


def _amount_or_error(text: str) -> tuple[str | None, Intent | None]:
    try:
        return parse_amount(text), None
    except MoneyError as exc:
        return None, Intent(read_as="a budget request with an amount I could not read",
                            ask=f"I could not read that amount ({exc}). Give it in dollars with at most two "
                                "decimal places, for example \"add $50,000 prioritizing Research\".")


def _budget(text: str, instruction: str, *, teams: Sequence[tuple[str, str]], gaps: Mapping[str, Decimal],
            default_mode: str | None = None, default_team: str | None = None) -> Intent | None:
    """An addition / transfer request in `text` as an Intent (a run or a question), or None when the text is
    not a budget request. `default_mode` / `default_team` come from a proposal being revised: an amount with
    no mode word keeps the proposal's mode, and no team named keeps the team it favoured."""
    names = {t: n for t, n in teams}
    is_transfer = bool(_TRANSFER.search(text))
    is_addition = not is_transfer and bool(_ADDITION.search(text))
    loose = (not is_transfer and not is_addition and bool(_ADDITION_WITH_AMOUNT.search(text))
             and not _QUESTION_LEAD.search(text))
    if not (is_transfer or is_addition or loose or default_mode):
        return None
    unit = other_unit(text)
    if unit is not None:
        return Intent(read_as=f"a budget request with an amount in {unit}, not dollars",
                      ask=f"The budget envelope is in dollars, and I will not convert {unit} into dollars or "
                          "read them as dollars. Give the amount in dollars, for example \"add $50,000 "
                          "prioritizing Research\".")
    amount, err = _amount_or_error(text)
    if err is not None:
        return err
    if loose:
        if amount is None:
            if not default_mode:
                return None  # "another question": not a budget request
        else:
            is_addition = True
    if not (is_transfer or is_addition):
        if default_mode and amount is not None:
            is_transfer, is_addition = default_mode == "transfer", default_mode == "addition"
        elif default_mode and (find_team(text, teams) or _BUDGET_WORDS.search(text)):
            is_transfer, is_addition = default_mode == "transfer", default_mode == "addition"
        else:
            return None
    if amount is not None and _NEGATIVE.search(text):
        return Intent(read_as="a budget request with a negative amount",
                      ask=f"That amount reads as negative ({_dollars(amount)} with a minus sign). An addition "
                          "adds new money and a redistribution moves existing money, so the amount is always "
                          "positive. To take money from a team, ask to move it, for example \"move at most "
                          "$5,000 from Product to Research\".")
    if is_addition and amount is None and not default_mode and not _BUDGET_WORDS.search(text):
        return None  # "more" in a plain question: answer it instead
    team = find_team(text, teams) or (default_team if default_team in names else None)
    if is_addition and amount is None:
        label = names.get(team, team) if team else None
        example = label or (teams[0][1] if teams else "Research")
        return Intent(read_as=f"add budget{f' for {label}' if label else ''}",
                      ask="How much should be added to the envelope"
                          + (f" for {label}" if label else ", and for which team")
                          + f"? For example \"add $50,000 prioritizing {example}\". I will not guess an "
                          "amount.")
    team_note = ""
    if team is None:
        donor = source_team(text, teams)
        team = most_over({t: g for t, g in gaps.items() if t != donor})
        if team is None:
            return Intent(read_as="a budget request without a team",
                          ask="Which team should this prioritize? Name one of: "
                              + ", ".join(n for _, n in teams) + ".")
        team_note = " (no team named; picked the team furthest over its allocation)"
    label = names.get(team, team)
    if is_transfer:
        params: dict[str, Any] = {"mode": "transfer", "prioritize": team}
        read = f"redistribute the existing budget toward {label}{team_note}"
        donor = source_team(text, teams)
        if donor is not None and donor != team:
            read += f" (you named {names.get(donor, donor)} as the source; the draft picks which teams fund it)"
        if amount is not None:
            params["amount"] = amount
            read += f", moving at most {_dollars(amount)}"
        return Intent(read_as=read, run={"task_type": "propose_allocation", "instruction": instruction,
                                         "params": params})
    return Intent(read_as=f"add {_dollars(amount)} to the envelope, prioritize {label}{team_note}",
                  run={"task_type": "propose_allocation", "instruction": instruction,
                       "params": {"mode": "addition", "amount": amount, "prioritize": team}})


def _refresh(pid: str, instruction: str) -> Intent:
    return Intent(read_as=f"refresh stale proposal {pid} against the current budget",
                  run={"task_type": "propose_allocation", "instruction": instruction,
                       "params": {"stale_proposal_id": pid}})


def _which(pool: Sequence[Mapping[str, Any]], verb: str) -> Intent:
    listed = "; ".join(f"{p['id']} ({p.get('label') or ('stale' if p.get('stale') else 'awaiting review')})"
                       for p in pool)
    first = pool[0]["id"]
    stale = next((p["id"] for p in pool if p.get("stale")), None)
    example = (f"\"Revise {first}: add $40,000 prioritizing Research\"" if verb == "revise" else f"\"refresh {first}\"")
    if verb == "revise" and stale:
        example += f" or \"refresh {stale}\""
    return Intent(read_as=f"{verb} a proposal, but more than one is open",
                  ask=f"Which proposal should I {verb}? Open proposals: {listed}. Name it by id, for example "
                      f"{example}.")


def _revise_or_refresh(text: str, instruction: str, *, teams: Sequence[tuple[str, str]],
                       gaps: Mapping[str, Decimal], open_: Sequence[Mapping[str, Any]],
                       wants_revise: bool) -> Intent | None:
    by_id = {p["id"]: p for p in open_}
    m = _PROPOSAL_ID.search(text)
    if m:
        pid = m.group(1)
        target = by_id.get(pid)
        if target is None and wants_revise:
            return Intent(read_as=f"revise {pid}",
                          ask=f"{pid} is not open for revision: only proposals awaiting review or stale ones can "
                              "be revised. " + (f"Open proposals: {', '.join(by_id)}." if by_id else
                                                "There is no open proposal right now."))
        if target is None:
            return _refresh(pid, instruction)  # the backend says plainly if it cannot be refreshed
    else:
        pool = list(open_) if wants_revise else [p for p in open_ if p.get("stale")]
        if not pool:
            if wants_revise:
                return Intent(read_as="revise a proposal",
                              ask="There is no open proposal to revise right now. Ask for a new one instead, for "
                                  "example \"add $50,000 prioritizing Research\".")
            return None  # "refresh" with nothing stale: read the text as usual
        if len(pool) > 1:
            return _which(pool, "revise" if wants_revise else "refresh")
        target = pool[0]
    pid = target["id"]
    lead = _REVISE_LEAD.match(text)
    change = text[lead.end():] if lead else text
    if _FILLER.match(change):
        change = ""
    if change:
        sub = _budget(change, instruction, teams=teams, gaps=gaps, default_mode=target.get("mode"),
                      default_team=target.get("prioritize"))
        if sub is not None:
            sub.read_as = f"revise {pid}: {sub.read_as}"
            if sub.run is not None:
                sub.revises = pid
            return sub
    if target.get("stale") and (not change or not wants_revise):
        return _refresh(pid, instruction)
    example_team = next((n for t, n in teams if t == target.get("prioritize")), teams[0][1] if teams else "Research")
    return Intent(read_as=f"revise {pid}",
                  ask=f"What should change in {pid}? Say it with an amount and a team, for example \"Revise {pid}: "
                      f"add $40,000 prioritizing {example_team}\" or \"Revise {pid}: move at most $10,000 toward "
                      f"{example_team}\". I will not guess the change.")


def parse(content: str, *, teams: Sequence[tuple[str, str]], gaps: Mapping[str, Decimal],
          stale_proposal_ids: Sequence[str] = (), open_proposals: Sequence[Mapping[str, Any]] = ()) -> Intent:
    """`open_proposals`: proposals awaiting review or stale, newest first, each
    {id, stale, mode, prioritize, label}. `stale_proposal_ids` (older callers) adds stale ones by id."""
    text = " ".join(content.lower().split())
    instruction = content.strip()[:4000]
    open_ = list(open_proposals)
    known = {p["id"] for p in open_}
    open_ += [{"id": pid, "stale": True} for pid in stale_proposal_ids if pid not in known]

    wants_revise = bool(_REVISE.search(text))
    if wants_revise or _REFRESH.search(text):
        out = _revise_or_refresh(text, instruction, teams=teams, gaps=gaps, open_=open_,
                                 wants_revise=wants_revise)
        if out is not None:
            return out

    out = _budget(text, instruction, teams=teams, gaps=gaps)
    if out is not None:
        return out

    if _INTERPRET.search(text):
        return Intent(read_as="read the company documents and record what changed",
                      run={"task_type": "interpret_corpus", "instruction": instruction})
    return Intent(read_as="a question about spend, budgets and projections (read-only)",
                  run={"task_type": "answer_question", "instruction": instruction})


def _dollars(amount: str) -> str:
    return f"${Decimal(amount):,.2f}"
