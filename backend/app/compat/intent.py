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
- what changed in the documents / read the documents / interpret / context -> interpret_corpus
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
_QUESTION_LEAD = re.compile(r"^(why|what|which|who|when|where|how|did|does|do|is|are|was|were|has|have|explain)\b")
_NEGATED_ACTION = re.compile(
    r"\b(?:do not|don['’]t|never|not)\s+(?:add\w*|increas\w*|allocat\w*|redistribut\w*|rebalanc\w*|"
    r"move|transfer\w*|shift\w*|reallocat\w*|top[- ]?up)\b.*?(?=;|[.!?](?:\s|$)|,\s|\bbut\b|\binstead\b|\band\b|$)")
_FOLLOWUP = re.compile(r"^(?:make (?:it|that)|change (?:it|that)|use|instead\b)|\binstead[.!?]*$")
_DATE_CHANGE = re.compile(r"\b(?:effective|start|end|due)\s+date\b|\beffective\s+(?:on|from)\b|"
                          r"\b(?:start|begin|end)\s+(?:on|in|next|to|back|forward|earlier|later)\b")
_DATE_VALUE = re.compile(r"\b(?:\d{4}-\d{2}-\d{2}|(?:january|february|march|april|may|june|july|august|"
                         r"september|october|november|december)\s+\d{1,2}|next\s+(?:week|month|monday|"
                         r"tuesday|wednesday|thursday|friday|saturday|sunday))\b")
_RELATIVE_DATE = re.compile(r"\b(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|a)\s+"
                            r"(?:days?|weeks?|months?)\s+(?:later|earlier)\b")
_REVISE = re.compile(r"\b(revis\w*|amend\w*)\b")
# The command part of a revise/refresh message; what follows is the requested change.
_REVISE_LEAD = re.compile(
    r"^\s*(?:please\s+)?(?:can you\s+)?(?:revis\w*|amend\w*|refresh\w*|rebase\w*|redo|update)\s*"
    r"(?:(?:this|the|that|my|it)\s*)?(?:(?:proposal|draft)\s*)?(?:prop_[a-z0-9]+\s*)?(?:[:,;\-\u2013\u2014]\s*)?")
_FILLER = re.compile(r"^(?:please|thanks|thank you|it|now)?[\s.!?]*$")
# A minus sign (or the word) directly before an amount: "-5k", "$-5,000", "minus $5,000".
_NEGATIVE = re.compile(r"(?<![\w.])[-\u2212]\s*\$?\s*\d|\$\s*[-\u2212]\s*\d|\b(?:minus|negative)\s+\$?\s*\d")
_BUDGET_WORDS = re.compile(r"\b(budget|funding|funds|money|envelope|allocation|spend)\b")
_INTERPRET = re.compile(r"(read (the )?(docs|documents|corpus)|\binterpret\w*|\bcontext\b|\bsignals?\b)")
_WHAT_CHANGED = re.compile(r"\bwhat(?:'s| has| is)? (?:changed|new)\b")
_DOCUMENT_TARGET = re.compile(r"\b(?:docs?|documents?|corpus)\b")
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
    # Typed by the transport schema; no chat transcript or runner/tool state is persisted here.
    conversation_context: dict[str, Any] = field(default_factory=dict)


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
            default_mode: str | None = None, default_team: str | None = None,
            default_source: str | None = None, default_amount: str | None = None) -> Intent | None:
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
            amount = amount or default_amount
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
    donor = source_team(text, teams) or (default_source if default_source in names else None)
    draft = {"mode": "transfer" if is_transfer else "addition"}
    if team:
        draft["prioritize"] = team
    if donor and is_transfer:
        draft["source_team"] = donor
    if amount:
        draft["amount"] = amount
    if is_addition and amount is None:
        label = names.get(team, team) if team else None
        example = label or (teams[0][1] if teams else "Research")
        return Intent(read_as=f"add budget{f' for {label}' if label else ''}",
                      ask="How much should be added to the envelope"
                          + (f" for {label}" if label else ", and for which team")
                          + f"? For example \"add $50,000 prioritizing {example}\". I will not guess an "
                          "amount.", conversation_context={"intent": "allocation", "pending_slot": "amount", "draft": draft})
    team_note = ""
    if team is None:
        team = most_over({t: g for t, g in gaps.items() if t != donor})
        if team is None:
            return Intent(read_as="a budget request without a team",
                          ask="Which team should this prioritize? Name one of: "
                              + ", ".join(n for _, n in teams) + ".",
                          conversation_context={"intent": "allocation", "pending_slot": "team", "draft": draft})
        team_note = " (no team named; picked the team furthest over its allocation)"
    label = names.get(team, team)
    if is_transfer:
        params: dict[str, Any] = {"mode": "transfer", "prioritize": team}
        read = f"redistribute the existing budget toward {label}{team_note}"
        if donor == team:
            return Intent(read_as="a transfer with the same source and destination",
                          ask="Choose a different destination team for this transfer.",
                          conversation_context={"intent": "allocation", "pending_slot": "team", "draft": draft})
        if donor is not None:
            params["source_team"] = donor
            read += f" ({names.get(donor, donor)} as the source only)"
        if amount is not None:
            params["amount"] = amount
            read += f", moving at most {_dollars(amount)}"
        return Intent(read_as=read, run={"task_type": "propose_allocation", "instruction": instruction,
                                         "params": params}, conversation_context={"intent": "allocation", "draft": params.copy()})
    return Intent(read_as=f"add {_dollars(amount)} to the envelope, prioritize {label}{team_note}",
                  run={"task_type": "propose_allocation", "instruction": instruction,
                       "params": {"mode": "addition", "amount": amount, "prioritize": team}},
                  conversation_context={"intent": "allocation", "draft": {"mode": "addition", "amount": amount, "prioritize": team}})


def _refresh(pid: str, instruction: str) -> Intent:
    return Intent(read_as="refresh the outdated draft against the current budget",
                  run={"task_type": "propose_allocation", "instruction": instruction,
                       "params": {"stale_proposal_id": pid}})


def _which(pool: Sequence[Mapping[str, Any]], verb: str) -> Intent:
    listed = "; ".join(p.get("label") or ("outdated draft" if p.get("stale") else "awaiting review")
                       for p in pool)
    return Intent(read_as=f"{verb} a proposal, but more than one is open",
                  ask=f"Which proposal should I {verb}? Select a draft from the review list. Open drafts: {listed}.")


def _revise_or_refresh(text: str, instruction: str, *, teams: Sequence[tuple[str, str]],
                       gaps: Mapping[str, Decimal], open_: Sequence[Mapping[str, Any]],
                       wants_revise: bool, context: Mapping[str, Any] | None = None) -> Intent | None:
    context = context or {}
    by_id = {p["id"]: p for p in open_}
    m = _PROPOSAL_ID.search(text)
    selected = context.get("selected_proposal_id")
    if m or selected:
        pid = m.group(1) if m else selected
        target = by_id.get(pid)
        if target is None and wants_revise:
            return Intent(read_as="revise the selected draft",
                          ask="The selected draft is not open for revision: only drafts awaiting review or outdated ones can "
                              "be revised. " + ("Select an open draft from the review list." if by_id else
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
    version = target.get("base_version")
    if selected == pid and context.get("selected_proposal_version") is not None and version != context["selected_proposal_version"]:
        return Intent(read_as="revise an outdated selection",
                      ask="The selected proposal version has changed. Select the current proposal before revising it.",
                      conversation_context={"intent": "allocation", "pending_slot": "proposal"})
    selected_context = {"intent": "allocation", "selected_proposal_id": pid}
    if version is not None:
        selected_context["selected_proposal_version"] = version
    lead = _REVISE_LEAD.match(text)
    change = text[lead.end():] if lead else text
    if _FILLER.match(change):
        change = ""
    if change:
        sub = _budget(change, instruction, teams=teams, gaps=gaps, default_mode=target.get("mode"),
                      default_team=target.get("prioritize"), default_source=target.get("source_team"),
                      default_amount=target.get("amount"))
        if sub is not None:
            sub.read_as = f"revise the selected draft: {sub.read_as}"
            if sub.run is not None:
                sub.revises = pid
            sub.conversation_context = selected_context | sub.conversation_context
            return sub
    if target.get("stale") and (not change or not wants_revise):
        return _refresh(pid, instruction)
    example_team = next((n for t, n in teams if t == target.get("prioritize")), teams[0][1] if teams else "Research")
    return Intent(read_as="revise the selected draft",
                  ask="What should change in this draft? Say it with an amount and a team, for example "
                      f"\"add $40,000 prioritizing {example_team}\" or \"move at most $10,000 toward "
                      f"{example_team}\". I will not guess the change.",
                  conversation_context=selected_context | {"pending_slot": "change", "draft": {
                      key: target[key] for key in ("mode", "amount", "prioritize", "source_team") if target.get(key) is not None}})


def parse(content: str, *, teams: Sequence[tuple[str, str]], gaps: Mapping[str, Decimal],
          stale_proposal_ids: Sequence[str] = (), open_proposals: Sequence[Mapping[str, Any]] = (),
          conversation_context: Mapping[str, Any] | None = None) -> Intent:
    """`open_proposals`: proposals awaiting review or stale, newest first, each
    {id, base_version, stale, mode, amount, prioritize, source_team, label}.
    Conversation context carries only selected draft identity and unfilled semantic slots."""
    text = " ".join(content.lower().split())
    instruction = content.strip()[:4000]
    context = dict(conversation_context or {})
    draft = dict(context.get("draft") or {})
    positive = _NEGATED_ACTION.sub("", text).strip(" ;,.")
    # Negation removes only the prohibited action. An affirmative transfer in another clause survives.
    if not positive:
        return _answer(instruction, context)
    if _QUESTION_LEAD.search(text) and not _NEGATED_ACTION.search(text):
        asks_for_context_refresh = bool(_WHAT_CHANGED.search(text) and _DOCUMENT_TARGET.search(text))
        if not asks_for_context_refresh or _ADDITION.search(text) or _TRANSFER.search(text) or _REVISE.search(text):
            return _answer(instruction, context)
    text = positive
    open_ = list(open_proposals)
    known = {p["id"] for p in open_}
    open_ += [{"id": pid, "stale": True} for pid in stale_proposal_ids if pid not in known]

    # A period label accompanying a monetary instruction is not a request to reschedule it.
    monetary_action = bool(_ADDITION.search(text) or _TRANSFER.search(text))
    amount, amount_error = _amount_or_error(text)
    date_followup = bool(_DATE_VALUE.search(text) and amount is None and amount_error is None and not monetary_action and (
        context.get("pending_slot") == "effective_date" or context.get("selected_proposal_id") or
        _REVISE.search(text) or (_FOLLOWUP.search(text) and open_)))
    if _RELATIVE_DATE.search(text) and (context.get("intent") == "scenario" or
                                      context.get("pending_slot") == "effective_date" or context.get("selected_proposal_id")):
        date_followup = True
    if _DATE_CHANGE.search(text) or date_followup:
        date_context = context | {"intent": "scenario", "pending_slot": "effective_date", "effective_date_text": instruction}
        return Intent(read_as="an effective-date change", ask="Effective-date changes are not supported for budget proposals. "
                      "The requested date is retained, but no allocation was changed. Use a dated forecast scenario to explore it.",
                      conversation_context=date_context)

    amount_reply = bool(_AMOUNT.fullmatch(re.sub(r"^(?:[-−]|minus|negative)\s*", "", text).strip(" .!?")))
    explicit_action = _budget(text, instruction, teams=teams, gaps=gaps)
    closed_selection = context.get("selected_proposal_id") and context["selected_proposal_id"] not in {
        proposal["id"] for proposal in open_
    }
    if (closed_selection and explicit_action is not None and explicit_action.run is not None
            and not (_REVISE.search(text) or _FOLLOWUP.search(text) or _REFRESH.search(text))
            and context.get("pending_slot") not in ("amount", "team", "change")):
        # Selection is editing context, not a permanent action target. Once that draft is settled,
        # a complete new instruction starts afresh; ambiguous revision follow-ups still fail below.
        context = {key: value for key, value in context.items()
                   if key not in ("selected_proposal_id", "selected_proposal_version", "draft", "pending_slot")}
        draft = {}
    followup = bool(open_ and context.get("pending_slot") not in ("amount", "team") and (
        _FOLLOWUP.search(text) or amount_reply))
    selected_action = bool(context.get("intent") == "allocation" and context.get("selected_proposal_id") and
                           explicit_action is not None)
    wants_revise = bool(_REVISE.search(text)) or followup or selected_action or bool(context.get("selected_proposal_id") and (
        _FOLLOWUP.search(text) or amount_reply or context.get("pending_slot") in ("amount", "team", "change")))
    if wants_revise or _REFRESH.search(text):
        out = _revise_or_refresh(text, instruction, teams=teams, gaps=gaps, open_=open_,
                                 wants_revise=wants_revise, context=context)
        if out is not None:
            return out

    if context.get("pending_slot") in ("amount", "team") and draft.get("mode") in ("addition", "transfer"):
        out = _budget(text, instruction, teams=teams, gaps=gaps, default_mode=draft["mode"],
                      default_team=draft.get("prioritize"), default_source=draft.get("source_team"),
                      default_amount=draft.get("amount"))
        if out is not None:
            return out

    out = explicit_action
    if out is not None:
        return out

    if _INTERPRET.search(text) or (_WHAT_CHANGED.search(text) and _DOCUMENT_TARGET.search(text)):
        return Intent(read_as="read the company documents and record what changed",
                      run={"task_type": "interpret_corpus", "instruction": instruction})
    return _answer(instruction, context)


def _answer(instruction: str, context: Mapping[str, Any]) -> Intent:
    # A read-only turn must not accidentally reuse an unfinished action on a later ambiguous reply.
    preserved = {key: value for key, value in context.items() if key not in ("draft", "pending_slot")}
    return Intent(read_as="a question about spend, budgets and projections (read-only)",
                  run={"task_type": "answer_question", "instruction": instruction},
                  conversation_context=preserved | {"intent": "explain"})


def _dollars(amount: str) -> str:
    return f"${Decimal(amount):,.2f}"
