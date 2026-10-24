"""Droid agent runs: start (finance only), read with step log, and stream activity events over SSE.

There is no route through which Droid can decide a proposal; approval stays on
`POST /api/proposals/{id}/decision`, which requires the finance_approver role.
"""

from __future__ import annotations

import json
import time
from collections.abc import Iterator

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.agent.tools import manifest
from app.core.actors import FINANCE_ROLES, Actor, require_role
from app.db.session import get_session
from app.schemas.agent import AgentRunCreate, AgentRunList, AgentRunOut
from app.services import agent_runs as svc

router = APIRouter(prefix="/api", tags=["agent"])

POLL_SECONDS = 0.1
HEARTBEAT_SECONDS = 10.0
MAX_STREAM_SECONDS = 600.0
TERMINAL = ("succeeded", "failed", "unavailable")


@router.get("/agent/tools")
def agent_tools() -> dict:
    """The exact tools Droid gets (read + draft only)."""
    return manifest()


@router.post("/agent/runs", response_model=AgentRunOut, status_code=201,
             responses={202: {"model": AgentRunOut}, 503: {"description": "runner_unavailable"}})
def create_run(
    body: AgentRunCreate,
    request: Request,
    actor: Actor = Depends(require_role(*FINANCE_ROLES)),
):
    run_id, finished = svc.start_run(request.app.state, body, actor=actor)
    session = request.app.state.session_factory()
    try:
        out = AgentRunOut.model_validate(svc.run_out(session, svc.get_run(session, run_id)))
    finally:
        session.close()
    if not finished:
        return JSONResponse(status_code=202, content=out.model_dump(mode="json"))
    return out


@router.get("/agent/runs", response_model=AgentRunList)
def list_runs(limit: int = Query(default=50, ge=1, le=200), session: Session = Depends(get_session)):
    items = [svc.run_out(session, r) for r in svc.list_runs(session, limit)]
    return {"count": len(items), "items": items}


@router.get("/agent/runs/{run_id}", response_model=AgentRunOut)
def get_run(run_id: str, session: Session = Depends(get_session)):
    return svc.run_out(session, svc.get_run(session, run_id))


@router.get("/agent/runs/{run_id}/events", response_class=StreamingResponse,
            responses={200: {"content": {"text/event-stream": {}}}})
def stream_events(
    run_id: str,
    request: Request,
    after: int = Query(default=0, ge=0, description="resume after this event seq"),
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
):
    """Server-Sent Events: `id: <seq>`, `event: <type>`, `data: <json>`. Replays stored events, then follows
    a running run until `run_finished`. Reconnecting clients resume via `Last-Event-ID` or `?after=`."""
    factory = request.app.state.session_factory
    s = factory()
    try:
        svc.get_run(s, run_id)  # 404 before the stream starts
    finally:
        s.close()
    start = after
    if last_event_id and last_event_id.strip().isdigit():
        start = max(start, int(last_event_id.strip()))

    def gen() -> Iterator[str]:
        last = start
        began = last_beat = time.monotonic()
        yield "retry: 2000\n\n"
        while True:
            s = factory()
            try:
                events = svc.events_after(s, run_id, last)
                status = svc.get_run(s, run_id).status
                payloads = [svc.event_out(e) for e in events]
            finally:
                s.close()
            for e in payloads:
                last = e["seq"]
                data = {**e, "at": e["at"].isoformat()}
                yield f"id: {e['seq']}\nevent: {e['type']}\ndata: {json.dumps(data, sort_keys=True)}\n\n"
                if e["type"] == "run_finished":
                    return
            if status in TERMINAL and not payloads:
                return
            now = time.monotonic()
            if now - began > MAX_STREAM_SECONDS:
                yield "event: stream_timeout\ndata: {}\n\n"
                return
            if now - last_beat > HEARTBEAT_SECONDS:
                last_beat = now
                yield ": keepalive\n\n"
            time.sleep(POLL_SECONDS)

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
