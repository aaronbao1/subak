"""FakeDroidRunner: a deterministic, scripted investigation of the Northstar story.

It is labeled `fake` everywhere (runner_kind, event source `fake_runner`, signal produced_by
`droid_fake`). It is NOT a language model: it follows a fixed playbook, but it does real work through
the same scoped toolbox the SDK runner gets, so every claim it makes is verified by the backend:

- interpret_corpus: lists and reads the corpus; detects supersession from the stored supersedes chain
  and checks the conflicting timelines in the text (older thread "next period" vs approved plan "this
  period"); records cited signals (research expansion current, old research thread superseded, product
  timing shift, engineering continuation, marketing idea informal), six person-scope signals (person ids
  from `list_people`, kept only when the person is on the team and named in the text) and one
  company-scope model change. Every quote is located verbatim in the stored content first; an expected
  passage that is missing is reported, never invented.
- propose_allocation: reads budgets, spend, forecast (snapshot) and current signals (interpreting the
  corpus first if no current signal exists) and drafts outcome B (addition, prioritize research) or
  outcome A (transfer). The proposal stays `pending_review`; the runner never reports it as saved.
- propose_allocation with `stale_proposal_id` (stale-proposal recovery): finance's approval was refused
  with 409 `stale_proposal`. Calls `rebase_proposal`, explains what changed since the original's base
  version (per-team changes and the decisions that moved the budget) and offers the rebased draft as a
  NEW `pending_review` proposal. If the same intent no longer fits, it says why and drafts nothing.
- answer_question: a read-only per-team comparison of allocation, recorded spend and projection. With
  `params.chart` it also calls the read-only `build_chart_spec` tool; the spec lands in `output.charts`.
"""

from __future__ import annotations

import re
from decimal import ROUND_DOWN, Decimal
from typing import Any

from app.agent.runner import AgentRunOutput, AgentTask, AgentToolbox, ToolError

CENT = Decimal("0.01")
ZERO = Decimal("0.00")

# Playbook: which passages matter in each known document. Quotes are verified against stored content.
PLAYBOOK: dict[str, dict[str, Any]] = {
    "research-eval-plan": {
        "quotes": ["This plan expands model-evaluation work during the current planning period.",
                   "This plan supersedes the earlier email thread that proposed pushing the expansion to next period."],
        "uncertainty_quote": "Exact token volumes are not yet known; they depend on how many model updates ship.",
        "team": "research", "project": "model-evaluation", "change_type": "expansion",
        "scope": "team", "signal_kind": "project_accelerated",
        "title": "Research model-evaluation expansion moves into the current period",
        "summary": "Approved research plan (2026-10-08) expands model-evaluation work in the current planning "
                   "period; larger evaluation sweeps start this period instead of next.",
        "uncertainty": "Plan is approved but exact token volumes are not yet known and depend on how many model "
                       "updates ship; the plan does not justify a specific cost multiplier.",
    },
    "research-timeline-thread": {
        "quotes": ["we will push the model-evaluation expansion to next period.",
                   "Nothing here is approved yet; we will confirm in the formal plan."],
        "team": "research", "project": "model-evaluation", "change_type": "timing_shift",
        "scope": "team", "signal_kind": "project_deferred",
        "title": "Older thread: research expansion pushed to next period",
        "summary": "Older research email thread (2026-09-03) said the model-evaluation expansion would be pushed "
                   "to next period; this timeline is no longer the current plan.",
        "uncertainty": "Informal correspondence, never approved; kept only as history of the earlier timeline.",
    },
    "product-launch-plan": {
        "quotes": ["The general-availability launch milestone moves to the following period after customer pilot\nfeedback.",
                   "Near-term launch rehearsal is reduced this period; prompt tuning continues at a lower level."],
        "older_quotes": ["The general-availability launch milestone for the assistant workspace lands in the current period."],
        "team": "product", "project": "workspace-launch", "change_type": "timing_shift",
        "scope": "team", "signal_kind": "project_deferred",
        "title": "Product GA launch moves to the following period",
        "summary": "Product launch update (2026-10-14) moves the GA milestone to the following period, reducing "
                   "near-term launch rehearsal compared with the August plan (which had launch this period).",
        "uncertainty": "Timing depends on customer pilot feedback; lower near-term work is not by itself an "
                       "authorization to take product's allocation.",
    },
    "engineering-platform-note": {
        "quotes": ["Platform migration work continues through the current period at the current pace."],
        "team": "engineering", "project": "platform", "change_type": "continuation",
        "scope": "team", "signal_kind": "steady",
        "title": "Engineering platform migration continues at the current pace",
        "summary": "Engineering platform migration continues through the current period at the current pace; "
                   "seats stay flat.",
        "uncertainty": "A management note, not a budget plan; overage is expected to track the migration backlog.",
    },
    "marketing-ideas-slack": {
        "quotes": ["no budget or approval for it yet though", "just brainstorming, not a plan"],
        "team": None, "project": "campaigns", "change_type": "other",
        "scope": "team", "signal_kind": None, "title": "Marketing idea: personalized AI demo videos",
        "summary": "Marketing Slack brainstorm about personalized AI demo videos; an idea, not a plan.",
        "uncertainty": "Informal suggestion with no budget or approval; marketing is not a budgeted team here.",
    },
    # Person-scope documents (frontend-integration-design §5.1/§5.2): person_ids come from the document's
    # person_tags, kept only when the person is on `team` and named in the text.
    "research-harness-asana": {
        "quotes": ["Leila, please stay on the design doc longer and hold the harness build until the design "
                   "review signs off on 2026-11-03.",
                   "I will pause the implementation branch and keep my API runs to the design spikes."],
        "team": "research", "project": "model-evaluation", "change_type": "reduction",
        "scope": "person", "signal_kind": "project_deferred",
        "title": "Leila Novak's harness build deferred to Nov 3",
        "summary": "Ava Chen asked Leila Novak (Asana, 2026-10-14) to stay on the design doc and hold the "
                   "eval-harness build until the design review on 2026-11-03; Leila is pausing the "
                   "implementation branch.",
        "uncertainty": "The task does not say how much API usage the design spikes use, or whether the design "
                       "review will sign off on 2026-11-03.",
    },
    "research-model-switch-slack": {
        "quotes": ["from Monday 2026-10-19 I'm moving the nightly eval sweeps from the large model to the smaller "
                   "model tier.",
                   "just the cheaper tier for everything except the final comparison runs."],
        "team": "research", "project": "model-evaluation", "change_type": "reduction",
        "scope": "person", "signal_kind": "model_change",
        "title": "Omar Haddad moving eval sweeps to a cheaper model tier",
        "summary": "Omar Haddad said (Slack, 2026-10-16) that from 2026-10-19 his nightly eval sweeps move to "
                   "the smaller, cheaper model tier, except the final comparison runs.",
        "uncertainty": "The thread gives no prices or token volumes for either tier, and does not say how many "
                       "final comparison runs stay on the large model.",
    },
    "research-availability-monday": {
        "quotes": ["Out of office 2026-10-26 to 2026-10-30, no eval runs scheduled while I am away."],
        "team": "research", "project": None, "change_type": "reduction",
        "scope": "person", "signal_kind": "out_of_office",
        "title": "Theo Brandt out of office Oct 26-30",
        "summary": "Theo Brandt is out of office 2026-10-26 to 2026-10-30 (monday.com), with no eval runs "
                   "scheduled while away.",
        "uncertainty": "The board does not say whether teammates pick up his runs while he is away, or what "
                       "his usual daily usage is.",
    },
    "engineering-cutover-monday": {
        "quotes": ["the cutover regression suite now starts 2026-10-22 instead of mid-November.",
                   "Sofia Reyes will run the full regression suite with Claude Code daily until the cutover "
                   "completes."],
        "team": "engineering", "project": "platform", "change_type": "expansion",
        "scope": "person", "signal_kind": "project_accelerated",
        "title": "Sofia Reyes's cutover regression runs start Oct 22",
        "summary": "Arjun Rao moved the platform cutover regression suite up to 2026-10-22 from mid-November "
                   "(monday.com); Sofia Reyes runs it daily with Claude Code until cutover.",
        "uncertainty": "The item does not say when the cutover completes or how much usage a daily suite "
                       "takes. The engineering platform note (2026-10-12) says the migration continues at the "
                       "current pace; this item moves one person's work earlier and does not say that the team "
                       "total changes.",
    },
    "engineering-welcome-slack": {
        "quotes": ["Welcome Hana Sato, who joined the platform team today; her Claude Code seat and API key are "
                   "active from 2026-10-13."],
        "team": "engineering", "project": "platform", "change_type": "expansion",
        "scope": "person", "signal_kind": "onboarding",
        "title": "Hana Sato joined the platform team",
        "summary": "Hana Sato joined engineering on 2026-10-13 (Slack); her Claude Code seat and API key are "
                   "active from that date.",
        "uncertainty": "The message does not say how much she will use the seat or the API key while ramping up.",
    },
    "product-tool-switch-slack": {
        "quotes": ["From 2026-10-21 I'm moving my launch-tuning scripts off my Codex seat and onto the OpenAI API "
                   "directly.",
                   "it will show up as API usage instead of seat overage."],
        "team": "product", "project": "workspace-launch", "change_type": "continuation",
        "scope": "person", "signal_kind": "tool_change",
        "title": "Felix Weber moving tuning scripts to the OpenAI API",
        "summary": "Felix Weber said (Slack, 2026-10-19) that from 2026-10-21 his launch-tuning scripts move from "
                   "his Codex seat to the OpenAI API; the work is unchanged and shows up as API usage instead of "
                   "seat overage.",
        "uncertainty": "The thread does not compare API prices with seat overage, so whether the cost goes up or "
                       "down is not known.",
    },
    # Company-scope announcement: no team, no people; it applies to every team.
    "company-model-announcement-slack": {
        "quotes": ["Starting 2026-11-02, every team's default model moves to the new mid-tier model that "
                   "platform approved this week.",
                   "the net effect on each team's bill is not known yet."],
        "team": None, "project": None, "change_type": "other",
        "scope": "company", "signal_kind": "model_change",
        "title": "Company-wide default model change from Nov 2",
        "summary": "From 2026-11-02 every team's default model moves to a new mid-tier model (Slack "
                   "#announcements); per-token prices are lower but long-context runs use more tokens, and the "
                   "net effect is not known.",
        "uncertainty": "The announcement gives no prices or volumes and says the net effect on each team's bill "
                       "is not known yet.",
    },
}

TEAM_KEYS = ("research-eval-plan", "product-launch-plan", "engineering-platform-note", "marketing-ideas-slack")
PERSON_KEYS = ("research-harness-asana", "research-model-switch-slack", "research-availability-monday",
               "engineering-cutover-monday", "engineering-welcome-slack", "product-tool-switch-slack")
COMPANY_KEYS = ("company-model-announcement-slack",)

_NEXT = re.compile(r"\bnext period\b", re.IGNORECASE)
_THIS = re.compile(r"\b(this period|current period|current planning period)\b", re.IGNORECASE)


def _d(value: Any) -> Decimal:
    return Decimal(str(value)).quantize(CENT)


def _m(value: Decimal) -> str:
    return str(value.quantize(CENT))


class FakeDroidRunner:
    kind = "fake"

    def run(self, task: AgentTask, tools: AgentToolbox) -> AgentRunOutput:
        if task.type == "interpret_corpus":
            out = self._interpret(tools)
            return AgentRunOutput(summary=out["summary"], findings=out["findings"], warnings=out["warnings"])
        if task.type == "propose_allocation" and task.params.get("stale_proposal_id"):
            return self._recover_stale(task.params["stale_proposal_id"], tools)
        if task.type == "propose_allocation":
            return self._propose(task, tools)
        return self._answer(task, tools)

    # ---- interpret ---------------------------------------------------------------------------

    def _interpret(self, tools: AgentToolbox) -> dict[str, Any]:
        tools.emit("assistant_text", {"text": "Reading the company corpus to find what is planned or changing."})
        listing = tools.search_corpus(query="")
        docs = [tools.read_document(item["id"]) for item in listing["items"]]
        by_id = {d["id"]: d for d in docs}
        findings: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []

        # 1. Supersession and conflicting timelines, from the stored chain AND the text itself.
        for d in docs:
            newer_ref = d.get("superseded_by")
            if not newer_ref:
                continue
            newer = by_id.get(newer_ref["id"]) or tools.read_document(newer_ref["id"])
            kind = "new_version" if newer["doc_key"] == d["doc_key"] else "explicit_cross_document"
            event = {
                "older": _ref(d), "newer": _ref(newer), "kind": kind,
                "newer_plan_status": newer["plan_status"],
                "explanation": (f"{newer['title']} ({newer['authored_at'][:10]}, {newer['plan_status']}) supersedes "
                                f"{d['title']} ({d['authored_at'][:10]}, {d['plan_status']})."),
            }
            tools.emit("supersession_detected", event)
            findings.append({"type": "supersession", **event})
            if _NEXT.search(d["content"]) and _THIS.search(newer["content"]):
                conflict = {
                    "older": _ref(d), "newer": _ref(newer), "topic": ", ".join(newer["project_tags"]) or None,
                    "older_says": _sentence_with(d["content"], _NEXT),
                    "newer_says": _sentence_with(newer["content"], _THIS),
                    "resolution": "the newer approved document explicitly supersedes the older one; the older "
                                  "timeline is kept as history and is not treated as current",
                }
                tools.emit("conflict_detected", conflict)
                findings.append({"type": "conflict", **conflict})

        # 2. Cited signals. The older thread is recorded first so the current plan can supersede it.
        current_by_key = {d["doc_key"]: d for d in docs if d["is_current"]}
        recorded: dict[str, dict] = {}
        thread = next((d for d in docs if d["doc_key"] == "research-timeline-thread"), None)
        if thread is not None:
            status = "superseded" if thread.get("superseded_by") else "conflicting"
            sig = self._signal(tools, thread, PLAYBOOK["research-timeline-thread"], status=status, warnings=warnings)
            if sig:
                recorded["research-timeline-thread"] = sig
        people = tools.list_people()["items"]
        for key in TEAM_KEYS + PERSON_KEYS + COMPANY_KEYS:
            doc = current_by_key.get(key)
            if doc is None:
                warnings.append({"code": "expected_document_missing", "message": f"no current document {key!r}"})
                tools.emit("warning", warnings[-1])
                continue
            rules = PLAYBOOK[key]
            if doc["plan_status"] == "cancelled":
                status = "cancelled"
            elif doc["plan_status"] in ("informal", "draft"):
                status = "informal"
            else:
                status = "current"
            older_doc = None
            if rules.get("older_quotes") and doc.get("supersedes"):
                older_doc = by_id.get(doc["supersedes"]["id"])
            supersedes_signal = None
            if key == "research-eval-plan" and "research-timeline-thread" in recorded:
                prior = recorded["research-timeline-thread"]
                if prior["superseded_by_signal_id"] is None:
                    supersedes_signal = prior["id"]
            person_ids: list[str] = []
            if rules["scope"] == "person":
                person_ids = _confirmed_people(doc, rules["team"], people, tools, warnings)
                if not person_ids:
                    warnings.append({"code": "person_signal_skipped", "document_id": doc["id"],
                                     "message": f"no tagged person on {rules['team']} is named in {doc['doc_key']} "
                                                f"v{doc['version']}; no person signal recorded (never guessed)"})
                    tools.emit("warning", warnings[-1])
                    continue
            sig = self._signal(tools, doc, rules, status=status, warnings=warnings, older_doc=older_doc,
                               supersedes_signal_id=supersedes_signal, person_ids=person_ids)
            if sig:
                recorded[key] = sig

        for d in docs:
            if d["doc_key"] not in PLAYBOOK:
                warnings.append({"code": "document_not_interpreted", "document_id": d["id"],
                                 "message": f"{d['doc_key']} v{d['version']} is outside the fake runner's playbook"})
                tools.emit("warning", warnings[-1])

        current = [s for s in recorded.values() if s["status"] == "current"]
        summary = (f"Read {len(docs)} documents; recorded {len(recorded)} cited signals ({len(current)} current). "
                   + " ".join(f["explanation"] for f in findings if f["type"] == "supersession"))
        tools.emit("assistant_text", {"text": summary})
        return {"summary": summary, "findings": findings, "warnings": warnings, "signals": recorded}

    def _signal(self, tools: AgentToolbox, doc: dict, rules: dict, *, status: str, warnings: list,
                older_doc: dict | None = None, supersedes_signal_id: str | None = None,
                person_ids: list[str] | None = None) -> dict | None:
        citations = []
        for quote in rules["quotes"] + ([rules["uncertainty_quote"]] if rules.get("uncertainty_quote") else []):
            c = _cite(doc, quote)
            if c is None:
                warnings.append({"code": "expected_passage_missing", "document_id": doc["id"],
                                 "message": f"passage not found in {doc['doc_key']} v{doc['version']}: {quote[:60]!r}"})
                tools.emit("warning", warnings[-1])
                continue
            citations.append(c)
        if older_doc is not None:
            for quote in rules.get("older_quotes", []):
                c = _cite(older_doc, quote)
                if c is not None:
                    citations.append(c)
        if not citations:
            return None
        for c in citations:
            tools.emit("evidence_found", {"document_id": c["document_id"], "doc_key": c["doc_key"],
                                          "version": c["version"], "quote": c["quote"],
                                          "char_start": c["char_start"], "char_end": c["char_end"]})
        body = {
            "team": rules["team"], "project": rules["project"], "summary": rules["summary"],
            "change_type": rules["change_type"], "status": status, "uncertainty": rules["uncertainty"],
            "applies_from": doc.get("effective_from"), "applies_to": doc.get("effective_to"),
            "citations": [{k: c[k] for k in ("document_id", "quote", "char_start", "char_end")} for c in citations],
            "scope": rules.get("scope", "team"), "person_ids": list(person_ids or []),
            "signal_kind": rules.get("signal_kind"), "title": rules.get("title"),
        }
        if supersedes_signal_id:
            body["supersedes_signal_id"] = supersedes_signal_id
        try:
            sig = tools.record_signal(body)
        except ToolError as exc:
            warnings.append({"code": exc.code, "message": f"signal for {doc['doc_key']} refused: {exc.message}"})
            tools.emit("warning", warnings[-1])
            return None
        tools.emit("signal_recorded", {"signal_id": sig["id"], "team": sig["team"], "scope": sig["scope"],
                                       "person_ids": sig["person_ids"], "signal_kind": sig["signal_kind"],
                                       "status": sig["status"],
                                       "change_type": sig["change_type"], "summary": sig["summary"],
                                       "citations": len(sig["citations"]),
                                       "already_recorded": sig.get("already_recorded", False),
                                       "supersedes_signal_ids": sig["supersedes_signal_ids"]})
        return sig

    # ---- propose -----------------------------------------------------------------------------

    def _propose(self, task: AgentTask, tools: AgentToolbox) -> AgentRunOutput:
        params = task.params
        mode = params.get("mode", "addition")
        prioritize = params.get("prioritize", "research")
        warnings: list[dict[str, Any]] = []
        findings: list[dict[str, Any]] = []

        signals = tools.list_signals(status="current")["items"]
        if not any(s["team"] == prioritize for s in signals):
            tools.emit("assistant_text", {"text": f"No current context signal for {prioritize}; interpreting the "
                                                  "corpus first."})
            interp = self._interpret(tools)
            findings.extend(interp["findings"])
            warnings.extend(interp["warnings"])
            signals = tools.list_signals(status="current")["items"]

        budget = tools.get_budgets()
        spend = tools.get_spend_summary()
        forecast = tools.get_forecast()
        alloc = {a["team"]: _d(a["amount"]) for a in budget["allocations"]}
        recorded = {a["team"]: _d(a["recorded_spend"]) for a in budget["allocations"]}
        if prioritize not in alloc:
            return self._no_proposal(tools, f"unknown team {prioritize!r}", warnings, findings)

        fc = forecast["forecast"]
        projected: dict[str, Decimal] = {}
        if fc["availability"] in ("available", "partial"):
            for p in fc["projections"]:
                amt = _d(p["amount"])
                projected[p["team"]] = amt + recorded.get(p["team"], ZERO) if fc["basis"] == "remaining" else amt
        else:
            warnings.append({"code": "forecast_unavailable",
                             "message": f"forecast unavailable ({fc.get('reason')}); drafting from budget, spend and "
                                        "context only"})
            tools.emit("warning", warnings[-1])
        if spend["coverage"]["status"] != "complete":
            warnings.append({"code": "spend_coverage_incomplete",
                             "message": f"recorded spend coverage is {spend['coverage']['status']}"})
            tools.emit("warning", warnings[-1])

        gaps = {t: projected[t] - alloc[t] for t in alloc if t in projected}
        for t in sorted(gaps):
            findings.append({"type": "projection_gap", "team": t, "allocation": _m(alloc[t]),
                             "projected": _m(projected[t]), "recorded_spend": _m(recorded[t]),
                             "projected_minus_allocation": _m(gaps[t])})

        if mode == "addition":
            amount = _d(params.get("amount", "50000.00"))
            lines, reasoning = _addition_lines(amount, prioritize, gaps)
            body = {"action_type": "addition", "envelope_increase": _m(amount),
                    "lines": [{"to_team": t, "amount": _m(a)} for t, a in lines]}
        else:
            if not projected:
                return self._no_proposal(
                    tools, "a transfer needs projections to show headroom; recorded spend alone is not evidence that "
                           "a team will underspend", warnings, findings)
            cap = _d(params["amount"]) if params.get("amount") is not None else None
            moves, reasoning = _transfer_lines(prioritize, alloc, recorded, projected, cap)
            if not moves:
                return self._no_proposal(tools, "no team has projected headroom to transfer from", warnings, findings)
            body = {"action_type": "transfer",
                    "lines": [{"from_team": f, "to_team": t, "amount": _m(a)} for f, t, a in moves]}

        receiving = {ln["to_team"] for ln in body["lines"]}
        giving = {ln.get("from_team") for ln in body["lines"]} - {None}
        evidence = [{"kind": "signal", "id": s["id"], "note": s["summary"][:200]} for s in signals
                    if s["team"] in receiving | giving]
        evidence.append({"kind": "forecast_snapshot", "id": forecast["id"],
                         "note": f"{fc['availability']}: {fc['method_label']}"})
        evidence.append({"kind": "spend_summary", "id": spend["period"]["id"],
                         "note": f"recorded spend {spend['company_total']} {spend['unit']}"})
        superseded = tools.list_signals(status="superseded")["items"]
        rationale = _rationale(mode, prioritize, reasoning, signals, superseded, fc)
        body.update({"base_version": budget["state_version"], "rationale": rationale, "evidence_refs": evidence})

        try:
            proposal = tools.draft_proposal(body)
        except ToolError as exc:
            if exc.code != "stale_base_version":
                return self._no_proposal(tools, f"backend refused the draft ({exc.code}): {exc.message}", warnings,
                                         findings, details=exc.as_dict())
            # The budget moved while we were reading; re-read once and draft against the current state.
            tools.emit("warning", {"code": "stale_base_version", "message": "budget changed; re-reading"})
            budget = tools.get_budgets()
            body["base_version"] = budget["state_version"]
            try:
                proposal = tools.draft_proposal(body)
            except ToolError as exc2:
                return self._no_proposal(tools, f"backend refused the draft ({exc2.code}): {exc2.message}",
                                         warnings, findings, details=exc2.as_dict())

        tools.emit("proposal_drafted", {
            "proposal_id": proposal["id"], "action_type": proposal["action_type"], "status": proposal["status"],
            "applied": False, "requires_finance_approval": True, "base_version": proposal["base_version"],
            "envelope_increase": proposal["envelope_increase"], "before": proposal["before"],
            "after": proposal["after"], "deltas": proposal["deltas"], "warnings": proposal["warnings"],
            "already_drafted": proposal.get("already_drafted", False),
        })
        after = proposal["after"]
        kind = "addition to the envelope" if proposal["action_type"] == "addition" else "transfer between teams"
        summary = (f"Drafted proposal {proposal['id']} ({kind}) for finance review: "
                   + ", ".join(f"{t} {a}" for t, a in sorted(after["allocations"].items()))
                   + f"; envelope {after['total']} {proposal['unit']}. It is pending_review and has NOT been applied; "
                   f"saved allocations remain at version {proposal['base_version']} until a finance approver decides.")
        tools.emit("assistant_text", {"text": summary})
        warnings.extend(proposal["warnings"])
        return AgentRunOutput(summary=summary, findings=findings, warnings=warnings)

    def _no_proposal(self, tools: AgentToolbox, reason: str, warnings: list, findings: list,
                     details: dict | None = None) -> AgentRunOutput:
        warnings.append({"code": "no_proposal_drafted", "message": reason, **({"details": details} if details else {})})
        tools.emit("warning", warnings[-1])
        summary = f"No proposal drafted: {reason}. Nothing was changed."
        tools.emit("assistant_text", {"text": summary})
        return AgentRunOutput(summary=summary, findings=findings, warnings=warnings)

    # ---- stale-proposal recovery ---------------------------------------------------------------

    def _recover_stale(self, proposal_id: str, tools: AgentToolbox) -> AgentRunOutput:
        tools.emit("assistant_text", {"text": f"Finance's approval of {proposal_id} was refused as stale; checking "
                                              "what changed and re-drafting it on the current budget."})
        warnings: list[dict[str, Any]] = []
        findings: list[dict[str, Any]] = []
        rationale = (f"Rebased by Droid after finance's approval of {proposal_id} was refused as stale (the budget "
                     "moved after it was drafted). Same lines; the backend recomputed before/after on the current "
                     "budget version. Needs a fresh finance review.")
        try:
            result = tools.rebase_proposal(proposal_id=proposal_id, rationale=rationale)
        except ToolError as exc:
            ctx = exc.details.get("stale_context")
            if ctx:
                findings.append({"type": "stale_context", **ctx})
            what = _changes_text(ctx) if ctx else ""
            if exc.code == "proposal_not_stale":
                reason = (f"{proposal_id} is not stale ({exc.details.get('status')}, base version "
                          f"{exc.details.get('base_version', ctx['base_version'] if ctx else '?')}); nothing to rebase")
            elif exc.code == "validation_failed":
                codes = ", ".join(sorted({r["code"] for r in exc.details.get("reasons", [])})) or exc.code
                reason = (f"the same lines no longer fit the current budget ({codes}). {what}A fresh proposal "
                          "against the current state is needed; finance can start a new propose_allocation run")
            else:
                reason = f"rebase refused ({exc.code}): {exc.message}"
            return self._no_proposal(tools, reason.rstrip(". "), warnings, findings, details=_err_details(exc))

        ctx = result["stale_context"]
        new = result["proposal"]
        findings.append({"type": "stale_context", **ctx})
        tools.emit("proposal_drafted", {
            "proposal_id": new["id"], "action_type": new["action_type"], "status": new["status"],
            "applied": False, "requires_finance_approval": True, "base_version": new["base_version"],
            "rebased_from_proposal_id": new["rebased_from_proposal_id"],
            "envelope_increase": new["envelope_increase"], "before": new["before"], "after": new["after"],
            "deltas": new["deltas"], "warnings": new["warnings"], "already_drafted": False,
        })
        kind = "addition to the envelope" if new["action_type"] == "addition" else "transfer between teams"
        after = new["after"]
        summary = (f"{proposal_id} was drafted against budget version {ctx['base_version']} and was not applied: "
                   f"the budget is now at version {ctx['current_version']}. {_changes_text(ctx)}"
                   f"Rebased draft {new['id']} ({kind}, same lines) on version {new['base_version']}: "
                   + ", ".join(f"{t} {a}" for t, a in sorted(after["allocations"].items()))
                   + f"; envelope {after['total']} {new['unit']}. It is pending_review and needs a fresh finance "
                   f"review; nothing has been applied and saved allocations remain at version {new['base_version']}.")
        if new["warnings"]:
            summary += " Warnings: " + "; ".join(w.get("message", w.get("code", "")) for w in new["warnings"]) + "."
        tools.emit("assistant_text", {"text": summary})
        warnings.extend(new["warnings"])
        return AgentRunOutput(summary=summary, findings=findings, warnings=warnings)

    # ---- answer ------------------------------------------------------------------------------

    def _answer(self, task: AgentTask, tools: AgentToolbox) -> AgentRunOutput:
        """Allocation vs recorded vs projected per team, keeping units, dates and uncertainty visible:
        the period and as-of date, that totals are to date, spend coverage (partial / missing data and
        unattributed spend are called out, never hidden), and how projections are labeled."""
        if task.params.get("forecast_context"):
            return self._answer_forecast(task, tools)
        budget = tools.get_budgets()
        spend = tools.get_spend_summary()
        forecast = tools.get_forecast()["forecast"]
        unit = budget["unit"]
        proj = {p["team"]: p["amount"] for p in forecast["projections"]}
        team_cov = {t["team"]: t["coverage"]["status"] for t in spend["teams"]}
        rows = []
        for a in budget["allocations"]:
            rows.append({"type": "team_comparison", "team": a["team"], "allocation": a["amount"],
                         "recorded_spend": a["recorded_spend"], "projected": proj.get(a["team"]),
                         "coverage_status": team_cov.get(a["team"], a.get("coverage_status", "missing")),
                         "unit": unit})
        period = spend["period"]
        cov = spend["coverage"]
        unattributed = spend["unattributed"]
        coverage_row = {"type": "spend_coverage", "status": cov["status"], "period": period["id"],
                        "as_of": spend["as_of"], "company_total": spend["company_total"],
                        "unattributed_spend": unattributed["recorded_spend"],
                        "unattributed_records": unattributed["record_count"], "notes": cov["notes"], "unit": unit}
        warnings: list[dict] = []

        def team_text(r: dict) -> str:
            proj_txt = r["projected"] if r["projected"] is not None else "unavailable"
            flag = "" if r["coverage_status"] == "complete" else f" [spend data {r['coverage_status']}]"
            return (f"{r['team']}: allocation {r['allocation']}, recorded {r['recorded_spend']}{flag}, "
                    f"projected {proj_txt}")

        latest = max((str(t.get("last_record_at"))[:10] for t in spend["teams"] if t.get("last_record_at")),
                     default=None)
        through = f" (latest record dated {latest})" if latest else ""
        parts = [f"Period {period['id']} ({period['starts_on']} to {period['ends_on']}), {unit}; recorded spend "
                 f"is to date as of {spend['as_of']}{through}.", "; ".join(team_text(r) for r in rows) + "."]
        if cov["status"] != "complete":
            msg = f"Spend coverage is {cov['status']}: the recorded figures may be incomplete"
            if unattributed["record_count"]:
                msg += (f"; {unattributed['recorded_spend']} {unit} from {unattributed['record_count']} "
                        f"unattributed record(s) is counted in the company total ({spend['company_total']}) "
                        "but in no team's figures")
            parts.append(msg + ".")
            warnings.append({"code": "spend_coverage_incomplete", "message": msg,
                             "details": {"status": cov["status"], "notes": cov["notes"]}})
        else:
            parts.append(f"Spend coverage is complete; company total {spend['company_total']} {unit}.")
        if forecast["availability"] == "unavailable":
            parts.append(f"Projections are unavailable ({forecast.get('reason') or 'no forecast'}); "
                         "no projected figures are shown.")
            warnings.append({"code": "forecast_unavailable",
                             "message": forecast.get("reason") or "forecast unavailable"})
        else:
            label = f"Projections are {forecast['value_kind']} ({forecast['method_label']}), not measured spend"
            if forecast["availability"] == "partial":
                label += f"; partial: no projection for {', '.join(forecast.get('missing_teams') or [])}"
            parts.append(label + ".")
        chart_findings: list[dict] = []
        if task.params.get("chart"):
            try:
                chart = tools.build_chart_spec(**task.params["chart"])
            except ToolError as exc:
                msg = f"Chart not built: {exc.code}: {exc.message}"
                parts.append(msg + ".")
                warnings.append({"code": "chart_not_built", "message": msg, "details": exc.as_dict()})
            else:
                chart_findings.append({"type": "chart", "kind": chart["kind"], "metric": chart["metric"],
                                       "team": chart["team"], "title": chart["title"],
                                       "row_count": chart["row_count"], "value_kinds": chart["value_kinds"]})
                parts.append(f"Chart built from backend data only: \"{chart['title']}\" "
                             f"({chart['row_count']} row(s); Vega-Lite v5 spec in output.charts).")
        if task.instruction.strip():
            # The fake runner is a fixed playbook: it never pretends to have understood a free-text
            # question or to have run an analysis it does not support (token multipliers, new scenarios).
            msg = ("Limitation: the deterministic fake runner does not interpret free-text questions; this is "
                   "the standard per-team comparison. Analyses beyond it (for example token multipliers or "
                   "scenarios the forecast provider does not supply) are not computed.")
            parts.append(msg)
            warnings.append({"code": "question_not_interpreted", "message": msg,
                             "details": {"instruction": task.instruction[:500]}})
        summary = " ".join(parts)
        tools.emit("assistant_text", {"text": summary})
        for w in warnings:
            tools.emit("warning", w)
        return AgentRunOutput(summary=summary, findings=rows + [coverage_row] + chart_findings, warnings=warnings)

    def _answer_forecast(self, task: AgentTask, tools: AgentToolbox) -> AgentRunOutput:
        """The deterministic runner handles exact forecast context through stored receipts."""
        context = task.params["forecast_context"]
        action = context.get("action", "explain")
        scope = {"scope_type":context.get("scope_type", "company"),"scope_id":context.get("scope_id")}
        try:
            if action == "compare":
                if not context.get("compare_run_id"):
                    raise ToolError("compare_forecasts", "invalid_arguments", "compare_run_id is required")
                receipt = tools.compare_forecasts(run_ids=[context["run_id"],context["compare_run_id"]], **scope)
            elif action == "preview":
                receipt = tools.preview_forecast_scenario(run_id=context["run_id"],drivers=context.get("drivers", []), **scope)
            elif action == "refresh":
                if not context.get("idempotency_key"):
                    raise ToolError("request_forecast_refresh", "invalid_arguments", "idempotency_key is required")
                receipt = tools.request_forecast_refresh(idempotency_key=context["idempotency_key"])
            else:
                receipt = tools.explain_forecast(run_id=context["run_id"],driver_id=context.get("driver_id"), **scope)
        except ToolError as exc:
            summary = f"Forecast request for {context['run_id']} could not be completed: {exc.message}."
            tools.emit("assistant_text", {"text":summary})
            return AgentRunOutput(summary=summary,warnings=[exc.as_dict()])
        parts = [f"Forecast {context['run_id']} ({scope['scope_type']} {scope['scope_id'] or ''})."]
        if receipt.get("summary"):
            parts.append(str(receipt["summary"]))
        bundles = receipt.get("runs", [receipt])
        limitations = []
        for bundle in bundles:
            for view in bundle.get("views", []):
                quarter = view.get("quarter_outlook", {})
                unit = view.get("target", {}).get("unit", "")
                amount = quarter.get("base")
                parts.append(f"{view.get('run_id',bundle.get('run_id',''))}: {quarter.get('label','Conditional quarter continuation')} "
                             f"{quarter.get('start','')} to {quarter.get('end','')}, "
                             f"base {amount if amount is not None else 'unavailable'} {unit}.")
                limitations.extend(str(x) for x in view.get("limitations", []))
                for driver in view.get("included_drivers", []):
                    if isinstance(driver, dict) and (not context.get("driver_id") or driver.get("id")==context["driver_id"]):
                        parts.append(f"Driver {driver.get('id')}: {driver.get('reason',driver.get('kind',''))}.")
                        for citation in driver.get("citations", []):
                            parts.append(f"Source {citation.get('source_id')} revision {citation.get('source_revision')}: "
                                         + str(citation.get("quote", "")))
            scoped_effects = [effect for view in bundle.get("views", []) for effect in view.get("driver_effects", [])]
            for effect in scoped_effects or bundle.get("driver_effects", []):
                if context.get("driver_id") and effect.get("driver_id") != context["driver_id"]:
                    continue
                effect_scope = effect.get("scope", {"type":"company","id":""})
                parts.append(f"Paired omission {effect.get('driver_id')} ({effect_scope.get('type')} {effect_scope.get('id')}): "
                             f"base effect {effect.get('base_delta','unavailable')}; {effect.get('qualification','')}")
            limitations.extend(str(x) for x in bundle.get("limitations", []))
        if action == "preview":
            parts.append(f"Hypothetical scenario receipt {receipt.get('scenario_id',receipt.get('run_id'))}: "
                         f"status {receipt.get('status', 'unknown')}; job {receipt.get('job_id', 'unknown')}; "
                         "published baseline unchanged.")
            if receipt.get("status") != "succeeded":
                parts.append("Scenario results are not available yet.")
            if receipt.get("last_error"):
                parts.append(f"Last calculation error: {receipt['last_error']}.")
        elif action == "refresh":
            parts.append(f"Refresh receipt {receipt.get('id')}: status {receipt.get('status','unknown')}; publication is reported by the stored job.")
        parts.append("Limitations: " + ("; ".join(dict.fromkeys(limitations)) or
                     "Conditional assumptions and descriptive scenario bounds; historical coverage is available only when separately reported."))
        summary = " ".join(parts)
        tools.emit("assistant_text", {"text":summary})
        return AgentRunOutput(summary=summary,findings=[{"type":"forecast_receipt","action":action,"receipt":receipt}])


# ---- helpers -----------------------------------------------------------------------------------


def _changes_text(ctx: dict) -> str:
    moved = [c for c in ctx["changes"] if Decimal(c["change"]) != 0]
    parts = []
    if moved:
        parts.append("Since then: " + ", ".join(f"{c['team']} {c['at_base']} -> {c['now']}" for c in moved)
                     + f" (envelope {ctx['at_base']['total']} -> {ctx['current']['total']}).")
    for d in ctx["decisions_since_base"]:
        lines = ", ".join((f"{ln['from_team']} -> {ln['to_team']} {ln['amount']}" if ln.get("from_team")
                           else f"+{ln['amount']} to {ln['to_team']}") for ln in d["lines"])
        parts.append(f"{d['proposal_id']} ({d['action_type']}: {lines}) was applied by {d['decided_by']} "
                     f"(version {d['from_version']} -> {d['to_version']}).")
    return (" ".join(parts) + " ") if parts else ""


def _err_details(exc: ToolError) -> dict:
    return {k: v for k, v in exc.as_dict().items() if k != "details"} | {
        "details": {k: v for k, v in exc.details.items() if k != "stale_context"}}


def _confirmed_people(doc: dict, team: str, people: list[dict], tools: AgentToolbox, warnings: list) -> list[str]:
    """The document's person tags that are on `team` AND named in its text; every dropped tag is reported."""
    by_id = {p["id"]: p for p in people}
    kept: list[str] = []
    for pid in doc.get("person_tags") or []:
        person = by_id.get(pid)
        if person is not None and person["team"] == team and person["name"] in doc["content"]:
            kept.append(pid)
            continue
        why = ("not in the people directory" if person is None else
               f"on team {person['team']}, not {team}" if person["team"] != team else
               f"{person['name']} is not named in the text")
        warnings.append({"code": "person_not_confirmed", "document_id": doc["id"], "person_id": pid,
                         "message": f"{doc['doc_key']} v{doc['version']} tags {pid!r}, but {why}; left out"})
        tools.emit("warning", warnings[-1])
    return kept


def _ref(d: dict) -> dict:
    return {"document_id": d["id"], "doc_key": d["doc_key"], "version": d["version"], "title": d["title"],
            "authored_at": d["authored_at"], "plan_status": d["plan_status"]}


def _cite(doc: dict, quote: str) -> dict | None:
    idx = doc["content"].find(quote)
    if idx < 0:
        return None
    return {"document_id": doc["id"], "doc_key": doc["doc_key"], "version": doc["version"], "quote": quote,
            "char_start": idx, "char_end": idx + len(quote)}


def _sentence_with(text: str, pattern: re.Pattern) -> str | None:
    for sentence in re.split(r"(?<=[.!?])\s+", text.replace("\n", " ")):
        if pattern.search(sentence):
            return sentence.strip()
    return None


def _addition_lines(amount: Decimal, prioritize: str, gaps: dict[str, Decimal]) -> tuple[list[tuple[str, Decimal]], str]:
    """Cover projected overruns (prioritized team first), then split any remainder half to the prioritized
    team and half evenly across the other teams with a projected overrun. Without projections all new money
    goes to the prioritized team."""
    if not gaps:
        return [(prioritize, amount)], (f"no projections available, so the full {_m(amount)} goes to the prioritized "
                                         f"team ({prioritize}); finance should revisit once a forecast is available")
    over = {t: g for t, g in gaps.items() if g > 0}
    order = [prioritize] + sorted((t for t in over if t != prioritize), key=lambda t: (-over[t], t))
    give: dict[str, Decimal] = {}
    left = amount
    for t in order:
        need = over.get(t, ZERO)
        g = min(need, left)
        if g > 0:
            give[t] = g
            left -= g
    others = [t for t in order if t != prioritize and t in over]
    if left > 0:
        if others:
            share = (left / 2 / len(others)).quantize(CENT, rounding=ROUND_DOWN)
            for t in others:
                give[t] = give.get(t, ZERO) + share
            give[prioritize] = give.get(prioritize, ZERO) + (left - share * len(others))
        else:
            give[prioritize] = give.get(prioritize, ZERO) + left
    lines = [(t, give[t]) for t in [prioritize] + sorted(t for t in give if t != prioritize) if give.get(t, ZERO) > 0]
    covered = ", ".join(f"{t} {_m(over[t])}" for t in order if t in over)
    reasoning = (f"projected overruns ({covered or 'none'}) are covered first, {prioritize} first; the remaining "
                 f"buffer is split half to {prioritize} and half across other teams with a projected overrun")
    return lines, reasoning


def _transfer_lines(prioritize: str, alloc: dict, recorded: dict, projected: dict, cap: Decimal | None):
    """Move headroom (allocation above projection, never below recorded spend) to projected overruns."""
    need = {t: projected[t] - alloc[t] for t in alloc if t in projected and projected[t] > alloc[t]}
    room = {t: min(alloc[t] - projected[t], alloc[t] - recorded.get(t, ZERO))
            for t in alloc if t in projected and projected[t] < alloc[t]}
    room = {t: r for t, r in room.items() if r > 0}
    order = ([prioritize] if prioritize in need else []) + sorted((t for t in need if t != prioritize),
                                                                  key=lambda t: (-need[t], t))
    budget_left = cap if cap is not None else sum(need.values(), ZERO)
    moves: dict[tuple[str, str], Decimal] = {}
    for dst in order:
        want = need[dst]
        for src in sorted(room, key=lambda t: (-room[t], t)):
            amt = min(want, room[src], budget_left)
            if amt <= 0:
                continue
            moves[(src, dst)] = moves.get((src, dst), ZERO) + amt
            room[src] -= amt
            want -= amt
            budget_left -= amt
    lines = [(f, t, a) for (f, t), a in moves.items()]
    reasoning = ("existing funds move from teams projected below their allocation (never below their recorded spend) "
                 f"to projected overruns, {prioritize} first; the envelope is unchanged")
    return lines, reasoning


def _rationale(mode: str, prioritize: str, reasoning: str, signals: list, superseded: list, fc: dict) -> str:
    parts = [
        ("Addition to the planning envelope" if mode == "addition" else "Transfer between teams")
        + f", prioritizing {prioritize}: {reasoning}.",
    ]
    for s in signals:
        quotes = "; ".join(f"\"{c['quote']}\" ({c['doc_key']} v{c['version']})" for c in s["citations"][:2])
        parts.append(f"Context ({s['team'] or 'company'}, {s['status']}): {s['summary']} Evidence: {quotes}.")
    for s in superseded:
        if s["team"] == prioritize:
            parts.append(f"Not relied on: {s['summary']} (superseded).")
    if fc["availability"] != "unavailable":
        parts.append(f"Projections are {fc['value_kind']} ({fc['method_label']}), not measured spend.")
    parts.append("Drafted by Droid for finance review; nothing is applied until a finance approver decides.")
    return " ".join(parts)
