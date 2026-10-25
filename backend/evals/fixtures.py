"""Eval fixtures: one Droid run each, on a fresh seeded database. Several scenarios may score the same run.

Each fixture = backend setup done over HTTP by finance/importer roles (never by Droid) + one
`POST /api/agent/runs` request. Live (sdk) runs are spent per fixture, not per scenario, so scenarios that
read the same run share its cost.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

ANALYST = {"X-Actor-Id": "fin-ana", "X-Actor-Role": "finance_analyst"}
DRAFTER = {"X-Actor-Id": "fin-dan", "X-Actor-Role": "finance_analyst"}
APPROVER = {"X-Actor-Id": "fin-alice", "X-Actor-Role": "finance_approver"}
IMPORTER = {"X-Actor-Id": "importer-1", "X-Actor-Role": "importer"}

# An extra document for the informal/cancelled scenario: a cancelled plan that reads like an expansion.
CANCELLED_DOC = {
    "doc_key": "research-hiring-pilot",
    "title": "Research hiring pilot - evaluation contractors (cancelled)",
    "origin": "upload", "doc_type": "plan", "plan_status": "cancelled",
    "team_tags": ["research"], "project_tags": ["hiring-pilot"], "is_simulated": True,
    "authored_at": "2026-10-15T00:00:00Z", "author": "Research operations (simulated)",
    "content": ("# Research hiring pilot\n\nStatus: cancelled on 2026-10-15.\n\n"
                "The pilot would have added evaluation contractors this period and doubled evaluation usage.\n"
                "The research hiring pilot is cancelled and will not run this period.\n"),
}

UNSUPPORTED_QUESTION = (
    "Assume research's model-evaluation expansion triples its token usage. What exact dollar token cost "
    "should we budget for it, at what price per 1,000 tokens, and how much will each individual engineer "
    "spend in March 2027?"
)


@dataclass(frozen=True)
class Fixture:
    name: str
    purpose: str
    request: Callable[[dict[str, Any]], dict[str, Any]]
    setup: Callable[[Any], dict[str, Any]] | None = None
    forecast_provider: str = "placeholder"
    tags: tuple[str, ...] = field(default_factory=tuple)


def _add_cancelled_doc(client) -> dict[str, Any]:
    r = client.post("/api/documents", json=CANCELLED_DOC, headers=IMPORTER)
    if r.status_code != 201:
        raise RuntimeError(f"setup failed: cancelled document not ingested: {r.status_code} {r.text[:300]}")
    return {"cancelled_document_id": r.json()["document"]["id"]}


def _make_stale(client) -> dict[str, Any]:
    """Outcome A (transfer) and B (addition) drafted by finance on v1; A applied; approving B -> 409 stale."""
    lines_a = [{"from_team": "product", "to_team": "research", "amount": "25000.00"},
               {"from_team": "product", "to_team": "engineering", "amount": "5000.00"}]
    lines_b = [{"to_team": "research", "amount": "35000.00"}, {"to_team": "engineering", "amount": "15000.00"}]
    a = client.post("/api/proposals", headers=DRAFTER, json={
        "action_type": "transfer", "base_version": 1, "lines": lines_a,
        "rationale": "research model-evaluation expansion; product launch moved to next period"})
    b = client.post("/api/proposals", headers=DRAFTER, json={
        "action_type": "addition", "base_version": 1, "envelope_increase": "50000.00", "lines": lines_b,
        "rationale": "add 50k prioritizing research"})
    if a.status_code != 201 or b.status_code != 201:
        raise RuntimeError(f"setup failed: drafts {a.status_code}/{b.status_code}")
    ok = client.post(f"/api/proposals/{a.json()['id']}/decision", headers={**APPROVER, "Idempotency-Key": "eval-a"},
                     json={"outcome": "approve", "rationale": "reviewed against approved plans"})
    refused = client.post(f"/api/proposals/{b.json()['id']}/decision",
                          headers={**APPROVER, "Idempotency-Key": "eval-b"},
                          json={"outcome": "approve", "rationale": "reviewed against approved plans"})
    if ok.status_code != 201 or refused.status_code != 409:
        raise RuntimeError(f"setup failed: apply A {ok.status_code}, approve B {refused.status_code} (want 201/409)")
    return {"stale_proposal_id": b.json()["id"], "applied_proposal_id": a.json()["id"]}


def _propose(mode: str, amount: str | None = None) -> Callable[[dict], dict]:
    def body(_: dict) -> dict:
        params: dict[str, Any] = {"mode": mode, "prioritize": "research"}
        if amount is not None:
            params["amount"] = amount
        return {"task_type": "propose_allocation", "params": params}
    return body


FIXTURES: dict[str, Fixture] = {f.name: f for f in (
    Fixture(
        name="interpret",
        purpose="interpret_corpus on the Northstar corpus plus a cancelled research plan",
        setup=_add_cancelled_doc,
        request=lambda _: {"task_type": "interpret_corpus"},
    ),
    Fixture(
        name="addition_50k",
        purpose="propose_allocation addition +50000.00 prioritizing research",
        request=_propose("addition", "50000.00"),
    ),
    Fixture(
        name="transfer",
        purpose="propose_allocation transfer prioritizing research (envelope fixed)",
        request=_propose("transfer"),
    ),
    Fixture(
        name="stale_recovery",
        purpose="propose_allocation with stale_proposal_id after a 409 stale_proposal",
        setup=_make_stale,
        request=lambda info: {"task_type": "propose_allocation",
                              "params": {"stale_proposal_id": info["stale_proposal_id"]}},
    ),
    Fixture(
        name="forecast_unavailable",
        purpose="propose_allocation addition +50000.00 with FORECAST_PROVIDER=unavailable",
        request=_propose("addition", "50000.00"),
        forecast_provider="unavailable",
    ),
    Fixture(
        name="unsupported_question",
        purpose="answer_question asking for token prices, a 3x multiplier and per-engineer March 2027 spend",
        request=lambda _: {"task_type": "answer_question", "instruction": UNSUPPORTED_QUESTION},
    ),
)}

# Order in which fixtures get live (sdk) runs when the global cap leaves fewer runs than fixtures.
# stale_recovery is last: it was already live-verified (backend/docs/droid-live-log.md, run 4).
LIVE_PRIORITY = ("interpret", "transfer", "forecast_unavailable", "unsupported_question", "addition_50k",
                 "stale_recovery")
