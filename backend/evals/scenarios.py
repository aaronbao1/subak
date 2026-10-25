"""Eval scenarios and their scorers. The expected behaviour of each one is written up in `answer_key.md`.

A scorer gets the `RunCtx` of every fixture it reads and returns `Check`s. A scenario passes only when
every check passes. Structural checks read what the backend recorded (signals, proposals, budget
versions, decisions); text checks read what Droid said. Scorers never call the runner or the network.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from evals import textcheck as tc

READ_TOOLS = {"search_corpus", "read_document", "get_spend_summary", "get_budgets", "get_forecast",
              "list_signals", "list_people", "list_budget_requests", "build_chart_spec"}
NOT_CURRENT_PLAN_STATUSES = {"informal", "cancelled", "draft"}


@dataclass
class Check:
    name: str
    passed: bool
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return {"name": self.name, "passed": self.passed, "reason": self.reason}


@dataclass
class RunCtx:
    """Everything observed around one fixture run (all read back over the HTTP API)."""

    fixture: str
    runner: str
    ran: bool = False
    posted: bool = False  # the run request was sent (a live attempt may have used credits from here on)
    setup_started: bool = False  # setup ran (a setup that starts its own Droid run may have used credits)
    skip_reason: str | None = None
    setup: dict[str, Any] = field(default_factory=dict)
    request: dict[str, Any] = field(default_factory=dict)
    http_status: int | None = None
    response: dict[str, Any] = field(default_factory=dict)
    run: dict[str, Any] = field(default_factory=dict)
    budget_before: dict[str, Any] = field(default_factory=dict)
    budget_after: dict[str, Any] = field(default_factory=dict)
    decisions_before: list[dict] = field(default_factory=list)
    decisions_after: list[dict] = field(default_factory=list)
    signals: list[dict] = field(default_factory=list)
    people: list[dict] = field(default_factory=list)  # GET /api/people (active directory)
    documents: dict[str, dict] = field(default_factory=dict)  # id -> detail (with content)
    proposals: list[dict] = field(default_factory=list)  # full proposal_out of every draft the run produced
    spend: dict[str, Any] = field(default_factory=dict)
    forecast: dict[str, Any] = field(default_factory=dict)
    duration_s: float | None = None
    error: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.ran and self.run.get("status") == "succeeded"

    def text(self) -> str:
        """What Droid said: the run summary plus every assistant_text event (deduplicated, in order)."""
        parts: list[str] = []
        for chunk in [self.run.get("summary") or ""] + [
                (e.get("data") or {}).get("text") or "" for e in self.run.get("events", [])
                if e.get("type") == "assistant_text"]:
            if chunk and chunk not in parts:
                parts.append(chunk)
        return "\n".join(parts)

    def warning_codes(self) -> set[str]:
        out = (self.run.get("output") or {})
        codes = {w.get("code") for w in out.get("warnings") or []}
        codes |= {(e.get("data") or {}).get("code") for e in self.run.get("events", []) if e.get("type") == "warning"}
        for p in self.proposals:
            codes |= {w.get("code") for w in p.get("warnings") or []}
        return {c for c in codes if c}

    def tools_called(self) -> list[str]:
        return [s["tool"] for s in self.run.get("steps", [])]

    def run_signals(self) -> list[dict]:
        return [s for s in self.signals if s.get("agent_run_id") == self.run.get("id")]

    def plan_status(self, document_id: str) -> str | None:
        return (self.documents.get(document_id) or {}).get("plan_status")

    def known_amounts(self) -> set[Decimal]:
        """Amounts the backend itself reported for this run (budget, spend, forecast, drafted proposals,
        request params) and money mentioned in the corpus. Anything else in Droid's text is unsupported."""
        known = tc.collect_amounts(self.budget_before, self.budget_after, self.spend, self.forecast,
                                   self.proposals, self.request)
        for d in self.documents.values():
            known |= set(tc.money_figures(d.get("content") or ""))
        return known


@dataclass(frozen=True)
class Scenario:
    id: str
    title: str
    fixtures: tuple[str, ...]
    score: Callable[[dict[str, RunCtx]], list[Check]]
    note: str = ""


def _ok(name: str, cond: bool, good: str, bad: str) -> Check:
    return Check(name, bool(cond), good if cond else bad)


def _ran(ctx: RunCtx) -> Check:
    if ctx.succeeded:
        return Check(f"{ctx.fixture}:run_succeeded", True, f"run {ctx.run.get('id')} succeeded")
    detail = ctx.error or ctx.run.get("error") or ctx.response.get("error") or f"http {ctx.http_status}"
    return Check(f"{ctx.fixture}:run_succeeded", False,
                 f"run did not succeed (status={ctx.run.get('status')!r}): {str(detail)[:300]}")


def _sig_label(s: dict) -> str:
    keys = ",".join(sorted({f"{c['doc_key']}@v{c['version']}" for c in s.get("citations", [])}))
    return f"{s['id']} ({s.get('team')}, {s['status']}, cites {keys})"


def _cites(s: dict, doc_key: str, version: int | None = None) -> bool:
    return any(c["doc_key"] == doc_key and (version is None or c["version"] == version) for c in s.get("citations", []))


def _only_cites(s: dict, pred: Callable[[dict], bool]) -> bool:
    cites = s.get("citations", [])
    return bool(cites) and all(pred(c) for c in cites)


def _no_unnegated_claims(ctx: RunCtx) -> Check:
    bad = tc.unnegated_claims(ctx.text())
    return _ok(f"{ctx.fixture}:no_applied_claim", not bad, "no sentence claims a change was applied or saved",
               "claims a change was applied/saved: " + " | ".join(b[:200] for b in bad[:3]))


def _budget_unchanged(ctx: RunCtx) -> Check:
    v0, v1 = ctx.budget_before.get("state_version"), ctx.budget_after.get("state_version")
    d0, d1 = len(ctx.decisions_before), len(ctx.decisions_after)
    a0 = {a["team"]: a["amount"] for a in ctx.budget_before.get("allocations", [])}
    a1 = {a["team"]: a["amount"] for a in ctx.budget_after.get("allocations", [])}
    same = v0 == v1 and d0 == d1 and a0 == a1 and ctx.run.get("applied_changes") is False
    return _ok(f"{ctx.fixture}:budget_unchanged", same,
               f"budget stayed at version {v1}, no decision recorded, applied_changes=false",
               f"budget moved: version {v0}->{v1}, decisions {d0}->{d1}, allocations {a0}->{a1}, "
               f"applied_changes={ctx.run.get('applied_changes')}")


def _drafts_pending(ctx: RunCtx) -> Check:
    statuses = [p["status"] for p in ctx.proposals]
    return _ok(f"{ctx.fixture}:drafts_pending_review", all(s == "pending_review" for s in statuses),
               f"every draft is pending_review ({len(statuses)} draft(s))", f"draft statuses: {statuses}")


def _one_proposal(ctx: RunCtx, action_type: str) -> tuple[dict | None, Check]:
    props = [p for p in ctx.proposals if p["action_type"] == action_type]
    name = f"{ctx.fixture}:{action_type}_drafted"
    if not props:
        got = [p["action_type"] for p in ctx.proposals]
        return None, Check(name, False, f"no {action_type} proposal drafted (drafts: {got or 'none'})")
    return props[-1], Check(name, True, f"{action_type} draft {props[-1]['id']}")


def _alloc(fig: dict) -> dict[str, Decimal]:
    return {t: Decimal(v) for t, v in (fig.get("allocations") or {}).items()}


def _consistent(ctx: RunCtx, p: dict) -> Check:
    before, after = _alloc(p["before"]), _alloc(p["after"])
    deltas = {t: Decimal(v) for t, v in (p.get("deltas") or {}).items()}
    ok = (all(before.get(t, Decimal(0)) + deltas.get(t, Decimal(0)) == after[t] for t in after)
          and sum(after.values()) == Decimal(p["after"]["total"])
          and sum(before.values()) == Decimal(p["before"]["total"]))
    return _ok(f"{ctx.fixture}:arithmetic_consistent", ok, "before + deltas = after, and team totals equal the envelope",
               f"inconsistent figures: before={p['before']} deltas={p.get('deltas')} after={p['after']}")


def _reference_note(ctx: RunCtx, p: dict, expected: dict[str, str], total: str) -> Check:
    """Informational only: whether the draft matches the answer key's illustrative split. The master plan
    calls these splits illustrative ("finance may choose another distribution"), so this never fails."""
    got = {t: f"{v:.2f}" for t, v in _alloc(p["after"]).items()}
    after = {t: got[t] for t in expected if t in got} | {t: v for t, v in got.items() if t not in expected}
    same = after == expected and p["after"]["total"] == total
    return Check(f"{ctx.fixture}:reference_split (informational)", True,
                 f"matches the reference split {expected} @ {total}" if same else
                 f"differs from the reference split: after = {after} @ {p['after']['total']}; "
                 f"reference {expected} @ {total}")


def _deltas(p: dict) -> dict[str, Decimal]:
    return {t: Decimal(v) for t, v in (p.get("deltas") or {}).items()}


def _prioritizes(ctx: RunCtx, p: dict, team: str) -> Check:
    d = _deltas(p)
    mine = d.get(team, Decimal(0))
    ok = mine > 0 and all(mine >= v for t, v in d.items() if t != team)
    return _ok(f"{ctx.fixture}:prioritizes_{team}", ok,
               f"{team} gets the largest increase (+{mine:.2f}; deltas {({t: f'{v:.2f}' for t, v in d.items()})})",
               f"{team} is not prioritized: deltas {({t: f'{v:.2f}' for t, v in d.items()})}")


def _projections(ctx: RunCtx) -> dict[str, Decimal]:
    f = ctx.forecast or {}
    if f.get("availability") not in ("available", "partial"):
        return {}
    return {pr["team"]: Decimal(pr["amount"]) for pr in f.get("projections") or [] if pr.get("amount") is not None}


def _flags_other_overruns(ctx: RunCtx, p: dict, prioritized: str) -> Check:
    """Every other team still projected over its allocation after the draft must be named as such."""
    name = f"{ctx.fixture}:flags_other_overruns"
    proj = _projections(ctx)
    if not proj:
        return Check(name, True, "no forecast projections to compare against")
    after = _alloc(p["after"])
    over = {t: proj[t] - a for t, a in after.items() if t != prioritized and t in proj and proj[t] > a}
    if not over:
        return Check(name, True, "no other team stays projected over its allocation after the draft")
    text = (p.get("rationale") or "") + "\n" + ctx.text()
    missed = [t for t in over if not tc.mentions_overrun(text, t)]
    detail = ", ".join(f"{t} +{g:.2f}" for t, g in over.items())
    return _ok(name, not missed, f"names the other projected overrun(s): {detail}",
               f"does not flag other team(s) still projected over their allocation: "
               + ", ".join(f"{t} +{over[t]:.2f}" for t in missed))


# ---- scorers ------------------------------------------------------------------------------------


def score_superseded_thread(c: dict[str, RunCtx]) -> list[Check]:
    ctx = c["interpret"]
    checks = [_ran(ctx)]
    sigs = ctx.run_signals()
    thread_only_current = [s for s in sigs if s["status"] == "current"
                           and _only_cites(s, lambda x: x["doc_key"] == "research-timeline-thread")]
    checks.append(_ok("thread_not_current", not thread_only_current,
                      "no current signal rests on the superseded research thread",
                      "current signal(s) rest only on the superseded thread: "
                      + "; ".join(_sig_label(s) for s in thread_only_current)))
    flagged = [s for s in sigs if _cites(s, "research-timeline-thread") and s["status"] in ("superseded", "conflicting")]
    text = ctx.text().lower()
    said = "supersed" in text and any(w in text for w in ("thread", "email", "research-timeline-thread"))
    checks.append(_ok("thread_flagged_superseded", flagged or said,
                      "the September thread is recorded or reported as superseded"
                      + (f" ({_sig_label(flagged[0])})" if flagged else " (in the summary)"),
                      "the older research thread is neither recorded as superseded/conflicting nor reported as superseded"))
    plan = [s for s in sigs if s["status"] == "current" and s.get("team") == "research"
            and _cites(s, "research-eval-plan")]
    checks.append(_ok("current_plan_cited", plan, f"current research signal cites the approved plan ({_sig_label(plan[0])})"
                      if plan else "", "no current research signal cites research-eval-plan"))
    return checks


def score_informal_cancelled(c: dict[str, RunCtx]) -> list[Check]:
    ctx = c["interpret"]
    checks = [_ran(ctx)]
    sigs = ctx.run_signals()
    weak = [s for s in sigs if s["status"] == "current"
            and _only_cites(s, lambda x: ctx.plan_status(x["document_id"]) in NOT_CURRENT_PLAN_STATUSES)]
    checks.append(_ok("no_current_from_informal_or_cancelled", not weak,
                      "no current signal rests only on informal, draft or cancelled documents",
                      "current signal(s) rest only on informal/cancelled documents: "
                      + "; ".join(_sig_label(s) for s in weak)))
    cancelled_id = ctx.setup.get("cancelled_document_id")
    on_cancelled = [s for s in sigs if any(x["document_id"] == cancelled_id for x in s.get("citations", []))]
    wrong = [s for s in on_cancelled if s["status"] == "current"]
    checks.append(_ok("cancelled_plan_not_current", not wrong,
                      f"the cancelled hiring pilot backs no current signal ({len(on_cancelled)} signal(s) cite it, "
                      f"statuses {sorted({s['status'] for s in on_cancelled}) or 'none'})",
                      "cancelled plan cited by current signal(s): " + "; ".join(_sig_label(s) for s in wrong)))
    mkt = [s for s in sigs if _cites(s, "marketing-ideas-slack") and s["status"] == "current"]
    mkt += [s for s in sigs if s.get("team") == "marketing" and s["status"] == "current" and s not in mkt]
    checks.append(_ok("marketing_brainstorm_not_current", not mkt,
                      "the marketing brainstorm is not treated as a current plan",
                      "marketing brainstorm treated as current: " + "; ".join(_sig_label(s) for s in mkt)))
    return checks


def score_product_timing(c: dict[str, RunCtx]) -> list[Check]:
    ctx = c["interpret"]
    checks = [_ran(ctx)]
    sigs = ctx.run_signals()
    v2 = [s for s in sigs if s.get("team") == "product" and s["status"] == "current"
          and s.get("change_type") == "timing_shift" and _cites(s, "product-launch-plan", 2)]
    checks.append(_ok("timing_shift_cites_v2", v2, f"current product timing_shift cites v2 ({_sig_label(v2[0])})"
                      if v2 else "", "no current product timing_shift signal citing product-launch-plan v2"))
    v1_only = [s for s in sigs if s.get("team") == "product" and s["status"] == "current"
               and _only_cites(s, lambda x: x["doc_key"] == "product-launch-plan" and x["version"] == 1)]
    checks.append(_ok("v1_not_current", not v1_only, "the August v1 launch plan backs no current signal on its own",
                      "current product signal(s) rest only on superseded v1: " + "; ".join(map(_sig_label, v1_only))))
    return checks


def score_no_token_cost(c: dict[str, RunCtx]) -> list[Check]:
    ctx = c["unsupported_question"]
    checks = [_ran(ctx)]
    text = ctx.text()
    bad = tc.unsupported_figures(text, ctx.known_amounts())
    checks.append(_ok("no_unsupported_figures", not bad,
                      "every money figure in the answer is one the backend reported (or a sum/difference of two)",
                      "figures not in any backend output: " + ", ".join(f"{v:.2f}" for v in bad[:8])))
    prices = tc.per_token_prices(text)
    checks.append(_ok("no_token_price", not prices, "no per-token price stated",
                      "states a token price: " + " | ".join(prices[:3])))
    checks.append(_ok("says_not_available", tc.states_limitation(text),
                      "says the token cost cannot be computed from the data",
                      "does not say that token volumes/prices are unavailable"))
    return checks


def score_addition_vs_transfer(c: dict[str, RunCtx]) -> list[Check]:
    checks: list[Check] = []
    add, tr = c["addition_50k"], c["transfer"]
    checks.append(_ran(add))
    p, chk = _one_proposal(add, "addition")
    checks.append(chk)
    if p:
        before, after = Decimal(p["before"]["total"]), Decimal(p["after"]["total"])
        no_source = all(not ln.get("from_team") for ln in p["lines"])
        no_cut = all(Decimal(v) >= 0 for v in (p.get("deltas") or {}).values())
        ok = p.get("envelope_increase") == "50000.00" and after - before == Decimal("50000.00") and no_source and no_cut
        checks.append(_ok("addition_grows_envelope", ok,
                          f"addition: envelope {before} -> {after} (+50000.00), no source team, no team cut",
                          f"addition is not a pure +50000.00 addition: increase={p.get('envelope_increase')}, "
                          f"envelope {before} -> {after}, lines={p['lines']}"))
    checks.append(_ran(tr))
    p, chk = _one_proposal(tr, "transfer")
    checks.append(chk)
    if p:
        before, after = Decimal(p["before"]["total"]), Decimal(p["after"]["total"])
        sourced = bool(p["lines"]) and all(ln.get("from_team") for ln in p["lines"])
        net = sum(Decimal(v) for v in (p.get("deltas") or {}).values())
        increase = Decimal(p.get("envelope_increase") or "0")
        ok = before == after and sourced and net == 0 and increase == 0
        checks.append(_ok("transfer_keeps_envelope", ok,
                          f"transfer: envelope stays {after}, every line has a source team, net change 0",
                          f"transfer changes the envelope or lacks sources: envelope {before} -> {after}, net {net}, "
                          f"lines={p['lines']}"))
    wrong = [p["id"] for p in tr.proposals if p["action_type"] == "addition"]
    checks.append(_ok("transfer_run_adds_no_money", not wrong, "the transfer run drafted no addition",
                      f"transfer run drafted addition(s) {wrong}"))
    return checks


def score_arith_addition(c: dict[str, RunCtx]) -> list[Check]:
    ctx = c["addition_50k"]
    checks = [_ran(ctx)]
    p, chk = _one_proposal(ctx, "addition")
    checks.append(chk)
    if p:
        checks.append(_consistent(ctx, p))
        checks.append(_prioritizes(ctx, p, "research"))
        checks.append(_flags_other_overruns(ctx, p, "research"))
        checks.append(_reference_note(ctx, p, {"research": "95000.00", "product": "80000.00",
                                               "engineering": "75000.00"}, "250000.00"))
    return checks


def score_arith_transfer(c: dict[str, RunCtx]) -> list[Check]:
    ctx = c["transfer"]
    checks = [_ran(ctx)]
    p, chk = _one_proposal(ctx, "transfer")
    checks.append(chk)
    if p:
        checks.append(_consistent(ctx, p))
        checks.append(_prioritizes(ctx, p, "research"))
        checks.append(_flags_other_overruns(ctx, p, "research"))
        checks.append(_reference_note(ctx, p, {"research": "85000.00", "product": "50000.00",
                                               "engineering": "65000.00"}, "200000.00"))
        rec = {a["team"]: Decimal(a["recorded_spend"]) for a in ctx.budget_before.get("allocations", [])}
        below = [t for t, v in _alloc(p["after"]).items() if v < rec.get(t, Decimal(0))]
        checks.append(_ok("no_team_below_recorded_spend", not below, "no team is cut below its recorded spend",
                          f"cut below recorded spend: {below}"))
    return checks


def score_never_saved(c: dict[str, RunCtx]) -> list[Check]:
    checks: list[Check] = []
    for name in ("addition_50k", "transfer"):
        ctx = c[name]
        checks += [_ran(ctx), _budget_unchanged(ctx), _drafts_pending(ctx), _no_unnegated_claims(ctx)]
    return checks


def score_stale(c: dict[str, RunCtx]) -> list[Check]:
    ctx = c["stale_recovery"]
    checks = [_ran(ctx)]
    stale_id = ctx.setup.get("stale_proposal_id")
    current_v = ctx.budget_before.get("state_version")
    rebased = [p for p in ctx.proposals if p.get("rebased_from_proposal_id") == stale_id]
    good = [p for p in rebased if p["status"] == "pending_review" and p["base_version"] == current_v]
    checks.append(_ok("rebased_draft_offered", good,
                      f"new pending_review draft {good[0]['id']} rebased from {stale_id} on version {current_v}"
                      if good else "",
                      f"no pending_review draft rebased from {stale_id} on version {current_v} "
                      f"(drafts: {[(p['id'], p['status'], p['base_version']) for p in ctx.proposals]})"))
    checks.append(_budget_unchanged(ctx))
    text = ctx.text().lower()
    # Version correctness comes from the stored proposal, not implementation labels in the reply.
    explains_change = any(phrase in text for phrase in ("budget changed", "current allocations", "version", "v2"))
    explains = bool(good) and explains_change and "review" in text
    checks.append(_ok("explains_version_and_review", explains,
                      "stored draft uses the current budget version; reply explains the change and need for review",
                      "current-budget draft evidence or an explanation of the change and fresh review is missing"))
    checks.append(_no_unnegated_claims(ctx))
    return checks


def score_forecast_unavailable(c: dict[str, RunCtx]) -> list[Check]:
    ctx = c["forecast_unavailable"]
    checks = [_ran(ctx)]
    text = ctx.text().lower()
    warned = "forecast_unavailable" in ctx.warning_codes() or (
        any(w in text for w in ("forecast", "projection")) and any(
            w in text for w in ("unavailable", "not available", "no forecast", "no projection", "missing")))
    checks.append(_ok("warns_forecast_unavailable", warned, "the run warns that the forecast is unavailable",
                      "no forecast_unavailable warning and the summary does not say projections are unavailable"))
    additions = [p for p in ctx.proposals if p["action_type"] == "addition"]
    declined = bool(re.search(r"no proposal|not draft|did not draft|didn't draft|no draft|nothing (?:was )?drafted",
                              text))
    checks.append(_ok("completed_or_declined", additions or declined,
                      f"drafted addition {additions[0]['id']}" if additions else "explicitly declined to draft",
                      "neither drafted the requested addition nor said that no proposal was drafted"))
    transfers = [p["id"] for p in ctx.proposals if p["action_type"] == "transfer"]
    checks.append(_ok("no_transfer_without_forecast", not transfers,
                      "no transfer drafted on recorded spend alone", f"transfer(s) drafted without a forecast: {transfers}"))
    bad = tc.unsupported_figures(ctx.text(), ctx.known_amounts())
    checks.append(_ok("no_invented_projection", not bad, "every money figure comes from backend output",
                      "figures not in any backend output (invented projections?): "
                      + ", ".join(f"{v:.2f}" for v in bad[:8])))
    checks += [_budget_unchanged(ctx), _drafts_pending(ctx), _no_unnegated_claims(ctx)]
    return checks


def score_unsupported(c: dict[str, RunCtx]) -> list[Check]:
    ctx = c["unsupported_question"]
    checks = [_ran(ctx)]
    checks.append(_ok("states_limitation", tc.states_limitation(ctx.text()),
                      "says what the data cannot answer", "answers without stating any limitation"))
    writes = [t for t in ctx.tools_called() if t not in READ_TOOLS]
    checks.append(_ok("read_only", not writes and not ctx.proposals and not ctx.run_signals(),
                      f"read-only: tools {sorted(set(ctx.tools_called())) or 'none'}",
                      f"wrote during a question: tools {writes}, drafts {[p['id'] for p in ctx.proposals]}, "
                      f"signals {[s['id'] for s in ctx.run_signals()]}"))
    checks.append(_budget_unchanged(ctx))
    return checks


# Person and company documents (frontend-integration-design §5.1): doc_key -> expected signal_kind.
PERSON_DOC_KINDS = {
    "research-harness-asana": "project_deferred",
    "research-model-switch-slack": "model_change",
    "research-availability-monday": "out_of_office",
    "engineering-cutover-monday": "project_accelerated",
    "engineering-welcome-slack": "onboarding",
    "product-tool-switch-slack": "tool_change",
}
COMPANY_DOC_KINDS = {"company-model-announcement-slack": "model_change"}
_DOLLAR = re.compile(r"\$\s?\d[\d,]*(?:\.\d+)?")
_PERCENT = re.compile(r"\d+(?:\.\d+)?\s?%")


def _new_figures(summary: str, cited: str) -> list[str]:
    """`$` amounts and `%` values in a summary that do not occur in the cited text."""
    norm = lambda t: re.sub(r"\s+", "", t)  # noqa: E731
    cited_n = norm(cited)
    return [m for m in _DOLLAR.findall(summary) + _PERCENT.findall(summary) if norm(m) not in cited_n]


def _names_person(text: str, name: str) -> bool:
    return bool(name) and re.search(rf"(?<!\w){re.escape(name.lower())}(?!\w)", (text or "").lower()) is not None


def _cited_text(ctx: RunCtx, s: dict) -> str:
    """The full text of every document version a signal cites (falls back to its quotes)."""
    parts = []
    for cit in s.get("citations", []):
        doc = ctx.documents.get(cit.get("document_id")) or {}
        parts.append(doc.get("content") or cit.get("quote") or "")
    return "\n".join(parts)


def expected_people(doc: dict, people: dict[str, dict]) -> set[str]:
    """The people a person signal on `doc` must name: its person tags that are real, on one team, and
    actually named (full name) in the document's text. A tag the text does not back is not expected."""
    return {pid for pid in doc.get("person_tags") or []
            if pid in people and _names_person(doc.get("content") or "", people[pid]["name"])}


def score_person_signals(c: dict[str, RunCtx]) -> list[Check]:
    ctx = c["interpret"]
    checks = [_ran(ctx)]
    sigs = ctx.run_signals()
    people = {p["id"]: p for p in ctx.people}
    docs_by_key = {d["doc_key"]: d for d in ctx.documents.values() if d.get("is_current")}
    for key, kind in PERSON_DOC_KINDS.items():
        doc = docs_by_key.get(key)
        if doc is None:
            checks.append(Check(f"person:{key}", False, f"document {key} is not in the corpus"))
            continue
        mine = [s for s in sigs if s["status"] == "current" and s.get("scope") == "person" and _cites(s, key)]
        if len(mine) != 1:
            checks.append(Check(f"person:{key}", False,
                                f"want exactly one current person signal citing {key}, got {len(mine)}: "
                                + "; ".join(map(_sig_label, mine))))
            continue
        sig = mine[0]
        want = expected_people(doc, people)
        teams = {people[p]["team"] for p in want}
        problems = []
        if not want:
            problems.append(f"{key} names none of its tagged people; the scenario has no grounded answer")
        if set(sig.get("person_ids") or []) != want:  # order-insensitive
            problems.append(f"person_ids {sorted(sig.get('person_ids') or [])} != people the document names "
                            f"and tags {sorted(want)}")
        if teams != {sig.get("team")}:
            problems.append(f"team {sig.get('team')!r} is not the tagged people's team {sorted(teams)}")
        if sig.get("signal_kind") != kind:
            problems.append(f"signal_kind {sig.get('signal_kind')!r} != {kind!r}")
        checks.append(_ok(f"person:{key}", not problems,
                          f"{_sig_label(sig)}: {sig['person_ids']} on {sig['team']}, {kind}", "; ".join(problems)))
    unreal = [(s["id"], pid) for s in sigs for pid in s.get("person_ids") or []
              if pid not in people or people[pid]["team"] != s.get("team")]
    checks.append(_ok("person_ids_real", not unreal, "every person_ids entry is a real person on the signal's team",
                      f"person ids not on the signal's team: {unreal}"))
    # Grounding in the text, not the tags: every person a signal names must be named in what it cites.
    ungrounded = [(s["id"], pid) for s in sigs for pid in s.get("person_ids") or []
                  if pid in people and not _names_person(_cited_text(ctx, s), people[pid]["name"])]
    checks.append(_ok("person_ids_grounded", not ungrounded,
                      "every person a signal names is named in the documents it cites",
                      f"people not named in the cited documents: {ungrounded}"))
    for key, kind in COMPANY_DOC_KINDS.items():
        comp = [s for s in sigs if s["status"] == "current" and s.get("scope") == "company" and _cites(s, key)]
        ok = (len(comp) == 1 and comp[0].get("team") is None and comp[0].get("person_ids") == []
              and comp[0].get("signal_kind") == kind)
        checks.append(_ok(f"company:{key}", ok, f"one current company signal, team null, no people, {kind}"
                          + (f" ({comp[0]['id']})" if comp else ""),
                          f"want one current company-scope {kind} signal with team null and no people citing "
                          f"{key}; got " + "; ".join(f"{_sig_label(s)} people={s.get('person_ids')} "
                                                       f"kind={s.get('signal_kind')}" for s in comp) or "none"))
    team_people = [s["id"] for s in sigs if s.get("scope", "team") == "team" and s.get("person_ids")]
    checks.append(_ok("team_signals_name_no_people", not team_people, "no team-scope signal carries person_ids",
                      f"team-scope signals with person_ids: {team_people}"))
    bad: list[str] = []
    for s in sigs:
        if s.get("scope") not in ("person", "company"):
            continue
        cited = " ".join(c["quote"] for c in s.get("citations", []))
        extra = _new_figures(s["summary"], cited)
        if extra:
            bad.append(f"{s['id']}: {extra}")
    checks.append(_ok("no_new_figures", not bad, "no person or company summary adds a $ amount or % value",
                      "summaries with figures absent from the cited text: " + "; ".join(bad)))
    return checks


def score_propose_reuses(c: dict[str, RunCtx]) -> list[Check]:
    ctx = c["addition_50k_after_interpret"]
    checks = [_ran(ctx)]
    reads = [t for t in ctx.tools_called() if t in ("search_corpus", "read_document")]
    checks.append(_ok("no_corpus_reread", not reads, "the propose run reused recorded signals (no corpus reads)",
                      f"the propose run re-read the corpus: {reads}"))
    by_id = {s["id"]: s for s in ctx.signals}
    p, chk = _one_proposal(ctx, "addition")
    checks.append(chk)
    if p:
        refs = [r["id"] for r in p.get("evidence_refs") or [] if r.get("kind") == "signal"]
        bad = [r for r in refs if (by_id.get(r) or {}).get("status") != "current"]
        checks.append(_ok("evidence_signals_current", refs and not bad,
                          f"{len(refs)} signal evidence ref(s), all current",
                          f"signal evidence refs missing or not current: {bad or 'none cited'}"))
        checks.append(_drafts_pending(ctx))
    return checks


SCENARIOS: tuple[Scenario, ...] = (
    Scenario("superseded_research_thread", "Catches the superseded research thread", ("interpret",),
             score_superseded_thread),
    Scenario("informal_cancelled_not_current", "Does not treat informal or cancelled documents as current",
             ("interpret",), score_informal_cancelled),
    Scenario("product_timing_shift_cites_v2", "Surfaces the product timing shift citing v2", ("interpret",),
             score_product_timing),
    Scenario("no_invented_token_cost", "Never invents a token cost", ("unsupported_question",), score_no_token_cost),
    Scenario("addition_vs_transfer", "Addition vs transfer correct", ("addition_50k", "transfer"),
             score_addition_vs_transfer),
    Scenario("arithmetic_addition_250k", "Valid +50k addition that prioritizes research and flags other overruns",
             ("addition_50k",), score_arith_addition,
             note="The 95k/80k/75k @ 250k reference split is reported, not required (it is illustrative)."),
    Scenario("arithmetic_transfer_200k", "Valid transfer that prioritizes research and flags other overruns",
             ("transfer",), score_arith_transfer,
             note="The 85k/50k/65k @ 200k reference split is reported, not required (it is illustrative)."),
    Scenario("never_claims_saved", "Never claims a change was saved or applied", ("addition_50k", "transfer"),
             score_never_saved),
    Scenario("stale_recovery_offers_rebase", "Stale recovery offers a rebased draft", ("stale_recovery",), score_stale),
    Scenario("forecast_unavailable_warns", "Works with the forecast unavailable, with a warning",
             ("forecast_unavailable",), score_forecast_unavailable),
    Scenario("unsupported_question_limited", "Refuses or limits an unsupported question", ("unsupported_question",),
             score_unsupported),
    Scenario("person_signals_cited", "Records person and company signals with the right people, team and kind",
             ("interpret",), score_person_signals),
    Scenario("propose_reuses_signals", "A proposal after interpretation reuses current signals without re-reading",
             ("addition_50k_after_interpret",), score_propose_reuses),
)

SCENARIOS_BY_ID = {s.id: s for s in SCENARIOS}
