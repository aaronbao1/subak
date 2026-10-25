"""Minimal Northstar reference rows for ingestion tests (period, teams, mappings).

Kept separate from the future seed module so these tests do not depend on it.
"""

from __future__ import annotations

import json
from datetime import date

from app.db import models as m

IMPORTER = {"X-Actor-Id": "importer-1", "X-Actor-Role": "importer"}
ANALYST = {"X-Actor-Id": "ana", "X-Actor-Role": "finance_analyst"}
DROID = {"X-Actor-Id": "droid", "X-Actor-Role": "droid_agent"}

MAPPINGS = {
    "northstar_billing": {
        "ws-research": "research",
        "ws-product": "product",
        "ws-engineering": "engineering",
    },
    "codex_sessions": {"codex-research-laptops": "research"},
}

NORTHSTAR_CSV = """record_id,occurred_at,source_account,provider,model,cost_category,value_kind,amount,unit,notional_value,input_tokens,output_tokens
ns-001,2026-10-01,ws-research,anthropic,,subscription_fee,,5000.00,USD,,,
ns-002,2026-10-05,ws-research,anthropic,claude,direct_api,,40000.00,USD,,1000000,200000
ns-003,2026-10-06,ws-research,anthropic,claude,included_usage,,,USD,3000.00,500000,100000
ns-004,2026-10-07,ws-product,openai,gpt,billable_overage,,20000.00,USD,,,
ns-005,2026-10-08,ws-engineering,anthropic,claude,direct_api,,30000.00,USD,,,
"""


def seed_reference(session, *, mappings: dict | None = None) -> None:
    session.add(m.PlanningPeriod(
        id="2026-P1", label="Northstar planning period",
        starts_on=date(2026, 10, 1), ends_on=date(2026, 12, 31),
    ))
    session.add_all([m.Team(id=t, name=t.title()) for t in ("research", "product", "engineering")])
    session.flush()
    for kind, accounts in (MAPPINGS if mappings is None else mappings).items():
        for acct, team in accounts.items():
            session.add(m.TeamMapping(
                source_kind=kind, source_account=acct, team_id=team,
                effective_from=date(2026, 1, 1), created_by="seed",
            ))
    session.commit()


def upload(client, content: str | bytes, *, source_kind="northstar_billing", filename="export.csv",
           headers=None, **form):
    data = {"source_kind": source_kind, **form}
    body = content.encode() if isinstance(content, str) else content
    return client.post(
        "/api/imports", data=data, files={"file": (filename, body, "text/plain")},
        headers=headers or IMPORTER,
    )


def codex_lines(session_id: str, snapshots: list[tuple[str, dict | None]], *, model="gpt-5-codex",
                meta_first=True) -> str:
    """Build a Codex-format JSONL session. Each snapshot is (timestamp, total_token_usage or None)."""
    lines = []
    if meta_first:
        lines.append({"timestamp": snapshots[0][0], "type": "session_meta",
                      "payload": {"id": session_id, "cwd": "/redacted", "originator": "codex_cli"}})
    lines.append({"timestamp": snapshots[0][0], "type": "turn_context", "payload": {"model": model}})
    for ts, usage in snapshots:
        info = None if usage is None else {
            "total_token_usage": {**usage, "total_tokens": sum(usage.values())},
            "last_token_usage": usage,
        }
        lines.append({"timestamp": ts, "type": "event_msg", "payload": {"type": "token_count", "info": info}})
        lines.append({"timestamp": ts, "type": "response_item", "payload": {"type": "message", "content": "ignored"}})
    return "\n".join(json.dumps(x) for x in lines) + "\n"


def usage(i: int, c: int, o: int, r: int = 0) -> dict:
    return {"input_tokens": i, "cached_input_tokens": c, "output_tokens": o, "reasoning_output_tokens": r}
