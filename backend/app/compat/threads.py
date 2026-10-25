"""Assistant thread store and run -> AssistantMessage rendering.

Messages live in `assistant_messages` (created on startup with the other tables, wiped by
`/api/admin/reset`). The agent run a message triggered is the audit record; this table only remembers
the conversation so `GET /compat/api/threads/{id}` can replay it.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.clock import Clock, IdFactory
from app.db.models import AssistantMessage, ContextSignal, CorpusDocument
from app.compat import mappers
from app.services import signals as signal_svc

SUMMARY_MAX = 240
SIMULATED_NOTE = ("_Simulated: this reply comes from the deterministic fake Droid runner (a scripted playbook, "
                  "not a model). Proposals still need a finance approver._")


def message_out(m: AssistantMessage) -> dict:
    out: dict[str, Any] = {"id": m.id, "threadId": m.thread_id, "role": m.role, "content": m.content,
                           "createdAt": mappers.iso(m.created_at)}
    if m.proposal_id:
        out["proposalId"] = m.proposal_id
    if m.citations:
        out["citations"] = m.citations
    if m.tool_calls:
        out["toolCalls"] = m.tool_calls
    return out


def list_messages(session: Session, thread_id: str) -> list[AssistantMessage]:
    return list(session.scalars(select(AssistantMessage).where(AssistantMessage.thread_id == thread_id)
                                .order_by(AssistantMessage.seq)))


def add_message(session: Session, thread_id: str, role: str, content: str, *, clock: Clock, ids: IdFactory,
                agent_run_id: str | None = None, proposal_id: str | None = None,
                citations: list[dict] | None = None, tool_calls: list[dict] | None = None) -> AssistantMessage:
    seq = (session.scalar(select(func.max(AssistantMessage.seq)).where(AssistantMessage.thread_id == thread_id))
           or 0) + 1
    m = AssistantMessage(id=ids.new_id("msg_"), thread_id=thread_id, seq=seq, role=role, content=content,
                         agent_run_id=agent_run_id, proposal_id=proposal_id, citations=citations or [],
                         tool_calls=tool_calls or [], created_at=clock.now())
    session.add(m)
    session.flush()
    return m


def _one_line(text: str | None, limit: int = SUMMARY_MAX) -> str:
    t = " ".join((text or "").split())
    return t if len(t) <= limit else t[: limit - 1].rstrip() + "…"


def tool_calls(run: dict) -> list[dict]:
    """The run's real tool steps, one line each."""
    return [{"name": st["tool"], "summary": _one_line(st.get("result_summary")) or f"called {st['tool']}"}
            for st in run.get("steps") or []]


def citations(session: Session, run: dict, proposal: dict | None) -> list[dict]:
    """The signals the drafted proposal cites; without a proposal, the signals this run recorded."""
    if proposal is not None:
        signal_ids = [r["id"] for r in proposal.get("evidence_refs") or [] if r.get("kind") == "signal"]
    else:
        signal_ids = list(run.get("signal_ids") or [])
    refs: list[dict] = []
    seen: set[str] = set()
    for sid in signal_ids:
        if sid in seen:
            continue
        seen.add(sid)
        sig = session.get(ContextSignal, sid)
        if sig is None:
            continue
        out = signal_svc.signal_out(session, sig)
        for c in out["citations"]:
            refs.append(mappers.source_ref(c, session.get(CorpusDocument, c["document_id"])))
    return mappers.dedupe_refs(refs)


def reply_text(read_as: str, run: dict) -> str:
    parts = [f"**Read as:** {read_as}."]
    status = run.get("status")
    if status == "succeeded":
        texts: list[str] = []
        if run.get("summary"):
            texts.append(run["summary"])
        for e in run.get("events") or []:
            if e.get("type") == "assistant_text":
                t = (e.get("data") or {}).get("text")
                if t and t not in texts:
                    texts.append(t)
        parts.extend(texts or ["The run finished without a summary."])
        if run.get("proposals"):
            parts.append("Nothing has been applied. A finance approver must review the proposal and apply or "
                         "reject it.")
    elif status == "unavailable":
        parts.append(f"The assistant is unavailable: {run.get('error') or 'runner unavailable'}. Nothing was "
                     "changed.")
    else:
        parts.append(f"The assistant run {status or 'did not finish'}: {run.get('error') or 'no detail'}. "
                     "Nothing was changed.")
    if run.get("simulated"):
        parts.append(SIMULATED_NOTE)
    return "\n\n".join(parts)
