"""Agent runs: validate the task, pick the runner, build the scoped toolbox, execute, record honestly.

- A run row is written before the runner starts, so even an unavailable or crashing runner leaves an
  audit record (`unavailable` / `failed` with the error).
- The run's `proposal_ids` / `signal_ids` come from what the toolbox actually recorded, not from what
  the runner claims.
- Runs never apply anything: the toolbox has no decide capability, and the run output says so.
"""

from __future__ import annotations

import math
import threading
import traceback
from collections.abc import Callable
from decimal import Decimal
from typing import Any

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agent.loader import load_runner
from app.agent.runner import AgentTask, RunnerUnavailable
from app.agent.toolbox import BackendToolbox
from app.core.actors import Actor
from app.core.errors import DomainError
from app.db.models import AgentRun, AgentRunEvent, AgentRunStep, ContextSignal, CorpusDocument, Proposal, Team
from app.db.session import transaction
from app.schemas.agent import AgentRunCreate, AnswerParams, ProposeParams

MAX_BACKGROUND_RUNS = 2
# interpret_corpus `params.document_ids`: a scoped batch (python -m app.interpret). Matches the
# toolbox's search cap, so a scoped run always sees every document it was given.
MAX_SCOPE_DOCUMENTS = 20
_background = threading.BoundedSemaphore(MAX_BACKGROUND_RUNS)


def _validation(reasons: list[dict]) -> DomainError:
    return DomainError("validation_failed", 422, "agent run request is invalid: "
                       + ", ".join(sorted({r["code"] for r in reasons})), {"reasons": reasons})


def build_task(session: Session, body: AgentRunCreate) -> AgentTask:
    params: dict[str, Any] = {}
    if body.task_type == "propose_allocation":
        try:
            p = ProposeParams.model_validate(body.params)
        except ValidationError as exc:
            raise _validation([{"code": "invalid_params", "message": e["msg"], "field": ".".join(map(str, e["loc"]))}
                               for e in exc.errors()]) from exc
        if p.stale_proposal_id is not None:
            return AgentTask(type=body.task_type, instruction=body.instruction,
                             params=_recovery_params(session, body.params, p.stale_proposal_id))
        reasons = []
        team = session.get(Team, p.prioritize)
        if team is None or not team.active:
            reasons.append({"code": "unknown_team", "message": f"unknown or inactive team {p.prioritize!r}",
                            "field": "params.prioritize"})
        if p.source_team is not None:
            source = session.get(Team, p.source_team)
            if source is None or not source.active:
                reasons.append({"code": "unknown_team", "message": f"unknown or inactive team {p.source_team!r}",
                                "field": "params.source_team"})
            if p.mode != "transfer" or p.source_team == p.prioritize:
                reasons.append({"code": "invalid_source_team", "message": "source_team requires a transfer to a different team",
                                "field": "params.source_team"})
        amount = p.amount
        if p.mode == "addition" and amount is None:
            amount = Decimal("50000.00")
        if amount is not None and amount <= 0:
            reasons.append({"code": "non_positive_amount", "message": "amount must be greater than zero",
                            "field": "params.amount"})
        if reasons:
            raise _validation(reasons)
        params = {"mode": p.mode, "prioritize": p.prioritize}
        if p.source_team is not None:
            params["source_team"] = p.source_team
        if amount is not None:
            params["amount"] = str(amount)
    elif body.task_type == "answer_question" and body.params:
        try:
            a = AnswerParams.model_validate(body.params)
        except ValidationError as exc:
            raise _validation([{"code": "invalid_params", "message": e["msg"], "field": ".".join(map(str, e["loc"]))}
                               for e in exc.errors()]) from exc
        if a.chart is not None:
            params = {"chart": a.chart.model_dump(exclude_none=True)}
        if a.forecast_context is not None:
            params["forecast_context"] = a.forecast_context.model_dump(exclude_none=True)
    elif body.task_type == "interpret_corpus" and body.params:
        params = _scope_params(session, body.params)
    elif body.params:
        raise _validation([{"code": "unexpected_params", "message": f"{body.task_type} takes no params",
                            "field": "params"}])
    return AgentTask(type=body.task_type, instruction=body.instruction, params=params)


def _scope_params(session: Session, raw: dict[str, Any]) -> dict[str, Any]:
    """interpret_corpus takes `document_ids` (interpret only these current documents) and, with them,
    an optional `credit_budget` (a positive number of factory_credits the sdk runner stops the run at;
    the interpret CLI passes the remaining cap). Anything else is still `unexpected_params`."""
    extra = sorted(k for k in raw if k not in ("document_ids", "credit_budget"))
    if extra:
        raise _validation([{"code": "unexpected_params",
                            "message": f"interpret_corpus takes only document_ids, not {', '.join(extra)}",
                            "field": "params"}])
    ids = raw.get("document_ids")
    if (not isinstance(ids, list) or not ids or len(ids) > MAX_SCOPE_DOCUMENTS
            or not all(isinstance(i, str) and i for i in ids) or len(set(ids)) != len(ids)):
        raise _validation([{"code": "invalid_params",
                            "message": f"document_ids must be 1-{MAX_SCOPE_DOCUMENTS} distinct document ids",
                            "field": "params.document_ids"}])
    reasons = []
    for doc_id in ids:
        doc = session.get(CorpusDocument, doc_id)
        if doc is None:
            reasons.append({"code": "unknown_document", "message": f"document {doc_id!r} not found",
                            "field": "params.document_ids"})
        elif doc.superseded_by_document_id is not None:
            reasons.append({"code": "document_superseded",
                            "message": f"document {doc_id!r} is superseded; scope only current documents",
                            "field": "params.document_ids"})
    budget = raw.get("credit_budget")
    if "credit_budget" in raw and (isinstance(budget, bool) or not isinstance(budget, (int, float))
                                   or not math.isfinite(budget) or not budget > 0):
        reasons.append({"code": "invalid_params", "message": "credit_budget must be a finite positive number",
                        "field": "params.credit_budget"})
    if reasons:
        raise _validation(reasons)
    out: dict[str, Any] = {"document_ids": list(ids)}
    if "credit_budget" in raw:
        out["credit_budget"] = float(budget)
    return out


def _recovery_params(session: Session, raw: dict[str, Any], proposal_id: str) -> dict[str, Any]:
    extra = sorted(k for k in raw if k != "stale_proposal_id")
    if extra:
        raise _validation([{"code": "conflicting_params",
                            "message": "stale_proposal_id recovers an existing proposal; it cannot be combined "
                                       f"with {', '.join(extra)}", "field": "params"}])
    if session.get(Proposal, proposal_id) is None:
        raise _validation([{"code": "unknown_proposal", "message": f"proposal {proposal_id!r} not found",
                            "field": "params.stale_proposal_id"}])
    return {"stale_proposal_id": proposal_id}


def start_run(app_state: Any, body: AgentRunCreate, *, actor: Actor,
              on_created: Callable[[str], None] | None = None,
              on_created_in_session: Callable[[Session, str], None] | None = None) -> tuple[str, bool]:
    """Create and execute (or schedule) a run. Returns (run_id, finished)."""
    settings = app_state.settings
    clock, ids = app_state.clock, app_state.id_factory
    factory = app_state.session_factory
    kind = settings.droid_runner

    with transaction(factory) as s:
        task = build_task(s, body)

    injected = getattr(app_state, "droid_runner", None)
    runner, unavailable = None, None
    if injected is not None:
        runner = injected
        kind = getattr(injected, "kind", kind)
    else:
        try:
            runner = load_runner(kind)
        except RunnerUnavailable as exc:
            unavailable = exc

    now = clock.now()
    run_id = ids.new_id("run_")
    with transaction(factory) as s:
        s.add(AgentRun(
            id=run_id, created_at=now, task_type=task.type,
            input={"task": task.model_dump(mode="json"), "initiated_by": {"id": actor.id, "role": actor.role}},
            runner_kind=kind, status="unavailable" if unavailable else "running",
            error=str(unavailable) if unavailable else None, started_at=now,
            finished_at=now if unavailable else None,
        ))
        if on_created_in_session is not None:
            s.flush()
            on_created_in_session(s, run_id)
    if on_created is not None:
        on_created(run_id)
    source = "droid_sdk" if kind == "sdk" else "fake_runner"
    toolbox = BackendToolbox(session_factory=factory, run_id=run_id, source=source, runner_kind=kind,
                             clock=clock, ids=ids, forecast_provider=app_state.forecast_provider,
                             forecast_service=getattr(app_state, "forecast_service", None),
                             forecast_context=task.params.get("forecast_context"),
                             rebase_target=(task.params.get("stale_proposal_id")
                                            if task.type == "propose_allocation" else None),
                             doc_scope=(task.params.get("document_ids")
                                        if task.type == "interpret_corpus" else None))
    if unavailable is not None:
        toolbox.emit("error", {"code": "runner_unavailable", "reason": unavailable.reason, "message": str(unavailable)},
                     source="backend")
        toolbox.emit("run_finished", {"status": "unavailable", "applied_changes": False}, source="backend")
        raise DomainError("runner_unavailable", 503, str(unavailable),
                          {"runner_kind": kind, "reason": unavailable.reason, "run_id": run_id})

    toolbox.emit("run_started", {"task_type": task.type, "runner_kind": kind, "params": task.params,
                                 "simulated": kind == "fake"}, source="backend")
    if body.wait:
        execute(app_state, run_id, runner, task, toolbox)
        return run_id, True
    if not _background.acquire(blocking=False):
        _finish(factory, clock, run_id, "failed", None, "too many concurrent background runs")
        toolbox.emit("run_finished", {"status": "failed", "applied_changes": False,
                                      "error": "too many concurrent background runs"}, source="backend")
        raise DomainError("runner_busy", 429, f"at most {MAX_BACKGROUND_RUNS} background runs may run at once",
                          {"run_id": run_id})

    def _bg() -> None:
        try:
            execute(app_state, run_id, runner, task, toolbox)
        finally:
            _background.release()

    threading.Thread(target=_bg, name=f"agent-{run_id}", daemon=True).start()
    return run_id, False


def execute(app_state: Any, run_id: str, runner: Any, task: AgentTask, toolbox: BackendToolbox) -> None:
    factory, clock = app_state.session_factory, app_state.clock
    try:
        out = runner.run(task, toolbox)
    except RunnerUnavailable as exc:
        _finish(factory, clock, run_id, "unavailable", None, str(exc))
        toolbox.emit("error", {"code": "runner_unavailable", "reason": exc.reason, "message": str(exc)}, source="backend")
        toolbox.emit("run_finished", {"status": "unavailable", "applied_changes": False}, source="backend")
        return
    except Exception as exc:  # noqa: BLE001 - any runner failure is recorded, never swallowed silently
        msg = f"{type(exc).__name__}: {exc}"
        _finish(factory, clock, run_id, "failed",
                {"proposal_ids": toolbox.proposal_ids, "signal_ids": toolbox.signal_ids,
                 "traceback_tail": traceback.format_exc(limit=3)[-1500:]}, msg)
        toolbox.emit("error", {"code": "runner_failed", "message": msg}, source="backend")
        toolbox.emit("run_finished", {"status": "failed", "applied_changes": False,
                                      "proposal_ids": toolbox.proposal_ids, "signal_ids": toolbox.signal_ids},
                     source="backend")
        return
    output = out.model_dump(mode="json")
    output["proposal_ids"] = list(toolbox.proposal_ids)
    output["signal_ids"] = list(toolbox.signal_ids)
    if toolbox.charts:  # charts the toolbox actually built (a runner cannot claim one it did not build)
        output["charts"] = list(toolbox.charts)
    if toolbox.budget_exhausted:  # a tool/write budget refused calls: the run may be incomplete
        output["budget_exhausted"] = list(toolbox.budget_exhausted)
    if toolbox.forecast_receipts:
        output["forecast_receipts"] = list(toolbox.forecast_receipts)
    output["applied_changes"] = False
    _finish(factory, clock, run_id, "succeeded", output, None)
    finished = {"status": "succeeded", "summary": out.summary, "applied_changes": False,
                "proposal_ids": output["proposal_ids"], "signal_ids": output["signal_ids"]}
    if out.usage:
        finished["usage"] = out.usage  # provider-reported (SDK); the fake runner reports none
    toolbox.emit("run_finished", finished, source="backend")


def _finish(factory, clock, run_id: str, status: str, output: dict | None, error: str | None) -> None:
    with transaction(factory) as s:
        run = s.get(AgentRun, run_id)
        run.status = status
        run.output = output
        run.error = error
        run.finished_at = clock.now()


def get_run(session: Session, run_id: str) -> AgentRun:
    run = session.get(AgentRun, run_id)
    if run is None:
        raise DomainError("not_found", 404, f"agent run {run_id!r} not found")
    return run


def list_runs(session: Session, limit: int = 50) -> list[AgentRun]:
    return list(session.scalars(select(AgentRun).order_by(AgentRun.started_at.desc(), AgentRun.id.desc()).limit(limit)))


def events_after(session: Session, run_id: str, after: int) -> list[AgentRunEvent]:
    return list(session.scalars(select(AgentRunEvent).where(AgentRunEvent.run_id == run_id, AgentRunEvent.seq > after)
                                .order_by(AgentRunEvent.seq)))


def event_out(e: AgentRunEvent) -> dict:
    return {"seq": e.seq, "type": e.type, "source": e.source, "data": e.data, "at": e.at}


def run_out(session: Session, run: AgentRun) -> dict:
    output = run.output or {}
    proposal_ids = output.get("proposal_ids") or []
    if run.status == "running" or not proposal_ids:
        proposal_ids = list(session.scalars(select(Proposal.id).where(Proposal.agent_run_id == run.id)
                                            .order_by(Proposal.created_at, Proposal.id)))
    proposals = []
    for pid in proposal_ids:
        p = session.get(Proposal, pid)
        if p is not None:
            proposals.append({"id": p.id, "action_type": p.action_type, "status": p.status})
    steps = session.scalars(select(AgentRunStep).where(AgentRunStep.run_id == run.id).order_by(AgentRunStep.seq))
    task = run.input.get("task", {})
    return {
        "id": run.id, "task_type": run.task_type, "instruction": task.get("instruction", ""),
        "params": task.get("params", {}), "initiated_by": run.input.get("initiated_by", {}),
        "runner_kind": run.runner_kind, "status": run.status, "simulated": run.runner_kind == "fake",
        "summary": output.get("summary"), "output": run.output, "error": run.error, "proposals": proposals,
        "signal_ids": output.get("signal_ids") if run.status != "running" and "signal_ids" in output else list(
            session.scalars(select(ContextSignal.id).where(ContextSignal.agent_run_id == run.id)
                            .order_by(ContextSignal.created_at, ContextSignal.id))),
        "applied_changes": False,
        "steps": [{"seq": st.seq, "tool": st.tool, "args": st.args, "result_summary": st.result_summary, "at": st.at}
                  for st in steps],
        "events": [event_out(e) for e in events_after(session, run.id, 0)],
        "events_url": f"/api/agent/runs/{run.id}/events",
        "started_at": run.started_at, "finished_at": run.finished_at,
    }


def event_count(session: Session, run_id: str) -> int:
    return session.scalar(select(func.count()).select_from(AgentRunEvent).where(AgentRunEvent.run_id == run_id)) or 0
