"""Northstar budget reference state and proposal/decision request builders for budget tests."""

from __future__ import annotations

import itertools

from app.services import budget as budget_svc
from reference_data import ANALYST, DROID, NORTHSTAR_CSV, seed_reference, upload

APPROVER = {"X-Actor-Id": "fin-alice", "X-Actor-Role": "finance_approver"}
APPROVER_2 = {"X-Actor-Id": "fin-bob", "X-Actor-Role": "finance_approver"}
IMPORTER_H = {"X-Actor-Id": "importer-1", "X-Actor-Role": "importer"}

INITIAL = {"research": "60000.00", "product": "80000.00", "engineering": "60000.00"}

OUTCOME_A_LINES = [  # redistribution: envelope stays 200k
    {"from_team": "product", "to_team": "research", "amount": "25000.00"},
    {"from_team": "product", "to_team": "engineering", "amount": "5000.00"},
]
OUTCOME_B_LINES = [  # addition: +50k
    {"to_team": "research", "amount": "35000.00"},
    {"to_team": "engineering", "amount": "15000.00"},
]

_keys = itertools.count(1)


def seed_budget(app, *, with_spend: bool = False, client=None) -> None:
    s = app.state.session_factory()
    try:
        seed_reference(s)
        budget_svc.create_envelope(s, period_id="2026-P1", unit="USD", allocations=INITIAL,
                                   clock=app.state.clock, ids=app.state.id_factory)
        s.commit()
    finally:
        s.close()
    if with_spend:
        assert client is not None
        r = upload(client, NORTHSTAR_CSV)
        assert r.status_code == 201, r.text


def transfer_body(lines=None, *, base_version=1, **extra) -> dict:
    return {"action_type": "transfer", "base_version": base_version,
            "rationale": "research model-evaluation expansion; product launch moved to next period",
            "lines": OUTCOME_A_LINES if lines is None else lines, **extra}


def addition_body(lines=None, *, increase="50000.00", base_version=1, **extra) -> dict:
    return {"action_type": "addition", "base_version": base_version, "envelope_increase": increase,
            "rationale": "add 50k prioritizing research", "lines": OUTCOME_B_LINES if lines is None else lines,
            **extra}


def draft(client, body: dict, headers=DROID):
    return client.post("/api/proposals", json=body, headers=headers)


def decide(client, proposal_id: str, outcome="approve", *, headers=APPROVER, key: str | None = None,
           rationale="reviewed against approved plans", **extra):
    key = key or f"key-{next(_keys)}"
    return client.post(
        f"/api/proposals/{proposal_id}/decision",
        json={"outcome": outcome, "rationale": rationale, **extra},
        headers={**headers, "Idempotency-Key": key},
    )


def allocations(client) -> dict[str, str]:
    state = client.get("/api/budget").json()
    return {a["team"]: a["amount"] for a in state["allocations"]}


def reasons(resp) -> set[str]:
    return {r["code"] for r in resp.json()["error"]["details"]["reasons"]}


__all__ = ["ANALYST", "DROID"]
