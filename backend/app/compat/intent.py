"""Free chat text -> a typed agent run request (or a clarifying question). Deterministic, no model.

The parse can be wrong, so every reply states how the text was read (`Intent.read_as`). Rules
(docs/frontend-alignment.md §4.3):
- refresh / rebase / update + a stale proposal  -> propose_allocation {stale_proposal_id}
- redistribute / rebalance / move / reallocate / shift / transfer -> propose_allocation {mode: transfer}
  (an amount, if given, caps the funds moved)
- add / additional / more / extra / increase / top up + budget words or an amount
  -> propose_allocation {mode: addition, amount}. No amount -> ask; never default an amount.
- what changed / read the documents / interpret / context -> interpret_corpus
- anything else -> answer_question with the text as the instruction
The team named in the text becomes `prioritize`; without one, the team whose projection exceeds its
allocation by the most. With no projection available and no team named, compat asks.
Amounts are parsed as Decimal strings ("50k" -> "50000.00"); a float never reaches the backend.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping, Sequence

from app.core.money import MoneyError, money_str, parse_money

_TRANSFER = re.compile(r"\b(redistribut\w*|rebalanc\w*|reallocat\w*|move|moving|shift\w*|transfer\w*)\b")
_ADDITION = re.compile(r"\b(add|adding|additional|more|extra|increase\w*|top[- ]?up|grow|expand)\b")
_BUDGET_WORDS = re.compile(r"\b(budget|funding|funds|money|envelope|allocation|spend)\b")
_INTERPRET = re.compile(r"(what('s| has)? changed|what is new|what's new|read (the )?(docs|documents|corpus)|"
                        r"\binterpret\w*|\bcontext\b|\bsignals?\b)")
_REFRESH = re.compile(r"\b(refresh\w*|rebase\w*|redo|update the proposal|refreshed)\b")
_PROPOSAL_ID = re.compile(r"\b(prop_[a-z0-9]+)\b")
_AMOUNT = re.compile(
    r"(?P<dollar>\$)\s*(?P<a>\d[\d,]*(?:\.\d+)?)\s*(?P<s1>k|m|thousand|million)?\b"
    r"|\b(?P<b>\d[\d,]*(?:\.\d+)?)\s*(?P<s2>k|m|thousand|million)\b"
    r"|\b(?P<c>\d{1,3}(?:,\d{3})+(?:\.\d+)?)\b"
    r"|\b(?P<d>\d{5,}(?:\.\d+)?)\b",
    re.IGNORECASE,
)
_SCALE = {"k": Decimal(1000), "thousand": Decimal(1000), "m": Decimal(1_000_000), "million": Decimal(1_000_000)}


@dataclass
class Intent:
    """Either `run` (an AgentRunCreate body) or `ask` (a clarifying reply, nothing is run)."""

    read_as: str
    run: dict[str, Any] | None = None
    ask: str | None = None
    notes: list[str] = field(default_factory=list)


def parse_amount(text: str) -> str | None:
    """First money amount in the text as a canonical decimal string, or None. Raises MoneyError on an
    amount that is not valid money (e.g. three decimal places)."""
    for m in _AMOUNT.finditer(text):
        raw = m.group("a") or m.group("b") or m.group("c") or m.group("d")
        suffix = (m.group("s1") or m.group("s2") or "").lower()
        try:
            value = Decimal(raw.replace(",", ""))
        except InvalidOperation:
            continue
        if suffix:
            value = value * _SCALE[suffix]
        return money_str(parse_money(value))
    return None


def find_team(text: str, teams: Sequence[tuple[str, str]]) -> str | None:
    """First active team (id or display name) mentioned in the text, by position."""
    best: tuple[int, str] | None = None
    for team_id, name in teams:
        for word in {team_id.lower(), name.lower()}:
            m = re.search(rf"\b{re.escape(word)}\b", text)
            if m and (best is None or m.start() < best[0]):
                best = (m.start(), team_id)
    return best[1] if best else None


def most_over(gaps: Mapping[str, Decimal]) -> str | None:
    """Team whose projection exceeds its allocation by the most (ties broken by id)."""
    over = sorted(((g, t) for t, g in gaps.items() if g > 0), key=lambda x: (-x[0], x[1]))
    return over[0][1] if over else None


def parse(content: str, *, teams: Sequence[tuple[str, str]], gaps: Mapping[str, Decimal],
          stale_proposal_ids: Sequence[str] = ()) -> Intent:
    text = " ".join(content.lower().split())
    names = {t: n for t, n in teams}
    instruction = content.strip()[:4000]

    if _REFRESH.search(text) and (_PROPOSAL_ID.search(text) or stale_proposal_ids):
        m = _PROPOSAL_ID.search(text)
        pid = m.group(1) if m else stale_proposal_ids[0]
        return Intent(read_as=f"refresh stale proposal {pid} against the current budget",
                      run={"task_type": "propose_allocation", "instruction": instruction,
                           "params": {"stale_proposal_id": pid}})

    is_transfer = bool(_TRANSFER.search(text))
    is_addition = not is_transfer and bool(_ADDITION.search(text))
    if is_transfer or is_addition:
        try:
            amount = parse_amount(text)
        except MoneyError as exc:
            return Intent(read_as="a budget request with an amount I could not read",
                          ask=f"I could not read that amount ({exc}). Give it in dollars with at most two "
                              "decimal places, for example \"add $50,000 prioritizing Research\".")
        if is_addition and amount is None and not _BUDGET_WORDS.search(text):
            is_addition = False  # "more" in a plain question: answer it instead
        if is_transfer or is_addition:
            team = find_team(text, teams)
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
                team = most_over(gaps)
                if team is None:
                    return Intent(read_as="a budget request without a team",
                                  ask="Which team should this prioritize? Name one of: "
                                      + ", ".join(n for _, n in teams) + ".")
                team_note = " (no team named; picked the team furthest over its allocation)"
            label = names.get(team, team)
            if is_transfer:
                params: dict[str, Any] = {"mode": "transfer", "prioritize": team}
                read = f"redistribute the existing budget toward {label}{team_note}"
                if amount is not None:
                    params["amount"] = amount
                    read += f", moving at most {_dollars(amount)}"
                return Intent(read_as=read, run={"task_type": "propose_allocation", "instruction": instruction,
                                                 "params": params})
            return Intent(read_as=f"add {_dollars(amount)} to the envelope, prioritize {label}{team_note}",
                          run={"task_type": "propose_allocation", "instruction": instruction,
                               "params": {"mode": "addition", "amount": amount, "prioritize": team}})

    if _INTERPRET.search(text):
        return Intent(read_as="read the company documents and record what changed",
                      run={"task_type": "interpret_corpus", "instruction": instruction})
    return Intent(read_as="a question about spend, budgets and projections (read-only)",
                  run={"task_type": "answer_question", "instruction": instruction})


def _dollars(amount: str) -> str:
    return f"${Decimal(amount):,.2f}"
