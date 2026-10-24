"""`python -m app.demo` - walk the Northstar demo journey against a running backend over HTTP.

Steps (each prints one short block):
  1. meta: which Droid runner the server is using (fake or sdk) and that the data is simulated
  2. tools: the exact tools Droid gets; asserts there is no apply / approve / decide tool
  3. Droid interprets the corpus into cited signals (one Droid run)
  4. Droid drafts a +50k addition prioritizing research (one Droid run); the budget does not move
  5. Droid's role tries to approve its own draft -> 403 role_forbidden
  6. a finance analyst drafts the redistribution (outcome A) by hand; a finance approver applies it -> v2
  7. the approver tries to apply Droid's addition -> 409 stale_proposal (it was drafted on v1)
  8. Droid recovers the stale proposal (one Droid run): a NEW pending_review draft on v2
  9. the approver applies the rebased draft -> v3

Start the server on a freshly seeded DB first (see docs/morning-runbook.md). With the SDK runner each
Droid step takes 20-170 s and spends Factory credits: 3 Droid runs by default, 2 with --skip-interpret.
Exit code 0 when every step behaved as expected, 1 otherwise. Prints no headers and no secrets.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from typing import Any

import httpx

ANALYST = {"X-Actor-Id": "fin-ana", "X-Actor-Role": "finance_analyst"}
APPROVER = {"X-Actor-Id": "fin-alice", "X-Actor-Role": "finance_approver"}
DROID = {"X-Actor-Id": "droid-demo", "X-Actor-Role": "droid_agent"}
DECIDE_TOOLS = ("apply", "approve", "decide", "reject")
OUTCOME_A_LINES = [
    {"from_team": "product", "to_team": "research", "amount": "25000.00"},
    {"from_team": "product", "to_team": "engineering", "amount": "5000.00"},
]


class StepFailed(Exception):
    pass


def _budget(client: httpx.Client) -> tuple[int, str, dict[str, str]]:
    r = client.get("/api/budget")
    if r.status_code != 200:
        raise StepFailed(f"GET /api/budget returned {r.status_code}; is the DB seeded (python -m app.seed)?")
    b = r.json()
    return b["state_version"], b["envelope_total"], {a["team"]: a["amount"] for a in b["allocations"]}


def _fmt_budget(version: int, envelope: str, alloc: dict[str, str]) -> str:
    teams = ", ".join(f"{t} {a}" for t, a in sorted(alloc.items()))
    return f"v{version}, envelope {envelope} ({teams})"


def _run(client: httpx.Client, body: dict[str, Any]) -> dict[str, Any]:
    r = client.post("/api/agent/runs", headers=ANALYST, json={**body, "wait": True})
    if r.status_code != 201:
        raise StepFailed(f"agent run returned {r.status_code}: {r.text[:300]}")
    run = r.json()
    if run["status"] != "succeeded":
        raise StepFailed(f"run {run['id']} ended {run['status']}: {run.get('error')}")
    return run


def _approve(client: httpx.Client, proposal_id: str, key: str, rationale: str) -> httpx.Response:
    return client.post(f"/api/proposals/{proposal_id}/decision",
                       headers={**APPROVER, "Idempotency-Key": key},
                       json={"outcome": "approve", "rationale": rationale})


def run_journey(client: httpx.Client, *, skip_interpret: bool = False,
                out: Callable[[str], None] = print) -> bool:
    """Run every step against `client` (base URL already set). Returns True when all behaved."""
    state: dict[str, Any] = {}

    def meta() -> None:
        m = client.get("/api/meta").json()
        out(f"   runner: {m.get('runner_kind', '?')}; "
            f"forecast provider: {m.get('forecast_provider', '?')}; period: {(m.get('period') or {}).get('id', '?')}")
        state["start"] = _budget(client)
        out(f"   budget: {_fmt_budget(*state['start'])}")

    def tools() -> None:
        names = [t["name"] for t in client.get("/api/agent/tools").json()["tools"]]
        out(f"   {len(names)} tools: {', '.join(names)}")
        bad = [n for n in names if any(word in n for word in DECIDE_TOOLS)]
        if bad:
            raise StepFailed(f"Droid has a decision tool: {bad}")
        out("   no apply / approve / decide / reject tool")

    def interpret() -> None:
        run = _run(client, {"task_type": "interpret_corpus"})
        signals = client.get("/api/signals").json()["items"]
        by_status: dict[str, int] = {}
        for s in signals:
            by_status[s["status"]] = by_status.get(s["status"], 0) + 1
        out(f"   run {run['id']} ({run['runner_kind']}): {len(run['steps'])} tool calls, "
            f"{len(signals)} signals {by_status}")
        if not by_status.get("superseded"):
            raise StepFailed("no superseded signal: the old research thread was not flagged")

    def propose() -> None:
        run = _run(client, {"task_type": "propose_allocation",
                            "params": {"mode": "addition", "amount": "50000.00", "prioritize": "research"}})
        drafts = [p for p in run["proposals"] if p["action_type"] == "addition"]
        if not drafts:
            raise StepFailed(f"run {run['id']} drafted no addition; summary: {(run.get('summary') or '')[:300]}")
        p = client.get(f"/api/proposals/{drafts[0]['id']}").json()
        state["addition"] = p["id"]
        out(f"   run {run['id']}: draft {p['id']} {p['status']} on v{p['base_version']}, "
            f"after {p['after']['allocations']} @ {p['after']['total']}")
        if p["status"] != "pending_review" or _budget(client) != state["start"]:
            raise StepFailed("the draft is not pending_review or the budget moved")
        out("   budget unchanged: nothing is applied until finance approves")

    def droid_cannot_approve() -> None:
        r = client.post(f"/api/proposals/{state['addition']}/decision",
                        headers={**DROID, "Idempotency-Key": "demo-droid-attempt"},
                        json={"outcome": "approve", "rationale": "self-approval attempt"})
        code = r.json().get("error", {}).get("code")
        out(f"   droid_agent approve -> {r.status_code} {code}")
        if r.status_code != 403:
            raise StepFailed("Droid's role was not refused")

    def apply_transfer() -> None:
        r = client.post("/api/proposals", headers=ANALYST, json={
            "action_type": "transfer", "base_version": state["start"][0], "lines": OUTCOME_A_LINES,
            "rationale": "research model-evaluation expansion; product launch moved to next period"})
        if r.status_code != 201:
            raise StepFailed(f"transfer draft returned {r.status_code}: {r.text[:300]}")
        r = _approve(client, r.json()["id"], "demo-approve-transfer", "approved research plan; launch moved")
        if r.status_code != 201:
            raise StepFailed(f"transfer approval returned {r.status_code}: {r.text[:300]}")
        out(f"   transfer applied by fin-alice -> {_fmt_budget(*_budget(client))}")

    def stale() -> None:
        r = _approve(client, state["addition"], "demo-approve-addition", "approved research plan; +50k")
        code = r.json().get("error", {}).get("code")
        out(f"   approve Droid's v1 addition -> {r.status_code} {code}")
        if r.status_code != 409 or code != "stale_proposal":
            raise StepFailed("a proposal drafted on an old budget version was not refused")

    def recover() -> None:
        run = _run(client, {"task_type": "propose_allocation", "params": {"stale_proposal_id": state["addition"]}})
        if not run["proposals"]:
            raise StepFailed(f"run {run['id']} drafted nothing; summary: {(run.get('summary') or '')[:300]}")
        p = client.get(f"/api/proposals/{run['proposals'][0]['id']}").json()
        state["rebased"] = p["id"]
        out(f"   run {run['id']}: draft {p['id']} {p['status']} on v{p['base_version']}, "
            f"rebased from {p['rebased_from_proposal_id']}")
        if p["status"] != "pending_review" or p["rebased_from_proposal_id"] != state["addition"]:
            raise StepFailed("the recovery draft is not a pending rebase of the stale proposal")

    def apply_rebased() -> None:
        r = _approve(client, state["rebased"], "demo-approve-rebased", "re-reviewed on the current budget")
        if r.status_code != 201:
            raise StepFailed(f"rebased approval returned {r.status_code}: {r.text[:300]}")
        out(f"   rebased draft applied by fin-alice -> {_fmt_budget(*_budget(client))}")

    steps: list[tuple[str, Callable[[], None]]] = [
        ("meta", meta), ("Droid's tools", tools),
        *([] if skip_interpret else [("Droid interprets the corpus", interpret)]),
        ("Droid drafts +50k for research", propose), ("Droid cannot approve", droid_cannot_approve),
        ("finance applies the redistribution", apply_transfer), ("stale proposal is refused", stale),
        ("Droid recovers the stale proposal", recover), ("finance applies the rebased draft", apply_rebased),
    ]
    for i, (title, fn) in enumerate(steps, 1):
        out(f"{i}. {title}")
        try:
            fn()
        except StepFailed as exc:
            out(f"   FAILED: {exc}")
            return False
    out("journey complete")
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.demo", description="Run the Northstar demo journey.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8787")
    parser.add_argument("--skip-interpret", action="store_true", help="skip the interpret run (one Droid run fewer)")
    parser.add_argument("--timeout", type=float, default=600.0, help="per-request timeout in seconds")
    args = parser.parse_args(argv)
    with httpx.Client(base_url=args.base_url, timeout=args.timeout) as client:
        try:
            ok = run_journey(client, skip_interpret=args.skip_interpret)
        except httpx.HTTPError as exc:
            print(f"cannot reach {args.base_url}: {exc}")
            return 1
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
