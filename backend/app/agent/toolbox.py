"""BackendToolbox: Droid's scoped capabilities, implemented on the backend service layer.

- Acts as the `droid_agent` role with actor id `droid:<run id>`; services enforce the same rules as
  the HTTP API (citation verification, arithmetic validation, stale base version, ...).
- Every call is recorded as an `agent_run_steps` row (the visible work record) and streamed as
  `tool_call` / `tool_result` events. Only calls that actually ran are recorded.
- Each tool runs in its own transaction: a refused call rolls back completely and comes back to the
  runner as a `ToolError` with the backend's error code.
- Per-run budgets cap tool calls and draft writes so a misbehaving model cannot flood the workspace.
- There is no method that decides, applies, approves or rejects a proposal.
"""

from __future__ import annotations

import threading
from decimal import Decimal
from typing import Any, Callable

from pydantic import TypeAdapter, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.agent.runner import EventSource, ToolError
from app.agent.tools import TOOLS
from app.api.routes_documents import summary_dict
from app.core.actors import Actor
from app.core.clock import Clock, IdFactory
from app.core.errors import DomainError
from app.db.models import AgentRunEvent, AgentRunStep, ContextSignal, Proposal
from app.db.session import transaction
from app.schemas.budget import BudgetState
from app.schemas.documents import DocumentDetail, DocumentSearchItem
from app.schemas.forecasts import ForecastSnapshotOut
from app.schemas.proposals import ProposalCreate, ProposalOut
from app.schemas.signals import ContextSignalIn, ContextSignalOut
from app.schemas.spending import SpendSummary
from app.services import budget as budget_svc
from app.services import corpus as corpus_svc
from app.services import coverage as coverage_svc
from app.services import forecasts as forecast_svc
from app.services import proposals as proposal_svc
from app.services import signals as signal_svc
from app.services import spending as spending_svc

MAX_TOOL_CALLS = 80
MAX_SIGNALS = 20
MAX_PROPOSALS = 3
MAX_SEARCH_RESULTS = 20

_PROPOSAL_ADAPTER = TypeAdapter(ProposalCreate)


def _short(value: Any, limit: int = 300) -> str:
    text = str(value)
    return text if len(text) <= limit else text[: limit - 3] + "..."


class BackendToolbox:
    def __init__(
        self,
        *,
        session_factory: sessionmaker,
        run_id: str,
        source: EventSource,
        runner_kind: str,
        clock: Clock,
        ids: IdFactory,
        forecast_provider: Any,
        start_seq: int = 0,
    ) -> None:
        self._factory = session_factory
        self.run_id = run_id
        self.source: EventSource = source
        self._runner_kind = runner_kind
        self._clock = clock
        self._ids = ids
        self._provider = forecast_provider
        self.actor = Actor(id=f"droid:{run_id}", role="droid_agent")
        self._lock = threading.Lock()
        self._event_seq = start_seq
        self._step_seq = 0
        self.signal_ids: list[str] = []
        self.proposal_ids: list[str] = []
        self._writes = {"record_signal": 0, "draft_proposal": 0}

    # ---- activity stream ---------------------------------------------------------------------

    def emit(self, type: str, data: dict | None = None, *, source: EventSource | None = None) -> None:
        with self._lock:
            self._event_seq += 1
            seq = self._event_seq
        with transaction(self._factory) as s:
            s.add(AgentRunEvent(id=self._ids.new_id("evt_"), created_at=self._clock.now(), run_id=self.run_id,
                                seq=seq, type=type, source=source or self.source, data=data or {},
                                at=self._clock.now()))

    @property
    def event_seq(self) -> int:
        return self._event_seq

    # ---- generic dispatch (used by the SDK MCP wrappers) ---------------------------------------

    def call(self, name: str, args: dict[str, Any] | None = None) -> dict:
        tool = next((t for t in TOOLS if t.name == name), None)
        if tool is None:
            raise ToolError(name, "unknown_tool", f"no tool named {name!r}")
        try:
            parsed = tool.input_model.model_validate(args or {})
        except ValidationError as exc:
            raise ToolError(name, "invalid_arguments", "tool arguments are invalid",
                            {"errors": exc.errors(include_url=False, include_context=False)}) from exc
        return getattr(self, name)(**parsed.model_dump())

    # ---- step recording ----------------------------------------------------------------------

    def _invoke(self, tool: str, args: dict[str, Any], fn: Callable[[Session], dict],
                summarize: Callable[[dict], str]) -> dict:
        if self._step_seq >= MAX_TOOL_CALLS:
            err = ToolError(tool, "tool_budget_exhausted", f"a run may make at most {MAX_TOOL_CALLS} tool calls")
            self.emit("error", err.as_dict())
            raise err
        self._step_seq += 1
        seq = self._step_seq
        self.emit("tool_call", {"step": seq, "tool": tool, "args": args})
        try:
            with transaction(self._factory) as s:
                result = fn(s)
        except DomainError as exc:
            err = ToolError(tool, exc.code, exc.message, exc.details)
            self._record_step(seq, tool, args, f"error {exc.code}: {_short(exc.message)}")
            self.emit("tool_result", {"step": seq, "tool": tool, "is_error": True, "code": exc.code,
                                      "summary": _short(exc.message)})
            raise err from exc
        except ValidationError as exc:
            err = ToolError(tool, "invalid_arguments", "tool arguments are invalid",
                            {"errors": exc.errors(include_url=False, include_context=False)})
            self._record_step(seq, tool, args, "error invalid_arguments")
            self.emit("tool_result", {"step": seq, "tool": tool, "is_error": True, "code": "invalid_arguments",
                                      "summary": _short(exc)})
            raise err from exc
        summary = summarize(result)
        self._record_step(seq, tool, args, summary)
        self.emit("tool_result", {"step": seq, "tool": tool, "is_error": False, "summary": summary})
        return result

    def _record_step(self, seq: int, tool: str, args: dict, summary: str) -> None:
        with transaction(self._factory) as s:
            s.add(AgentRunStep(id=self._ids.new_id("step_"), created_at=self._clock.now(), run_id=self.run_id,
                               seq=seq, tool=tool, args=args, result_summary=summary, at=self._clock.now()))

    def _period(self, s: Session):
        return coverage_svc.resolve_period(s, None, self._clock.now())

    # ---- read tools --------------------------------------------------------------------------

    def search_corpus(self, query: str = "", team: str | None = None, project: str | None = None,
                      include_superseded: bool = True) -> dict:
        args = {"query": query, "team": team, "project": project, "include_superseded": include_superseded}

        def fn(s: Session) -> dict:
            hits = corpus_svc.search_documents(s, q=query or None, team=team, project=project,
                                               include_superseded=include_superseded)
            items = [DocumentSearchItem.model_validate({**summary_dict(s, d), "score": score, "matches": m})
                     .model_dump(mode="json") for d, m, score in hits[:MAX_SEARCH_RESULTS]]
            return {"query": query, "count": len(items), "total_matches": len(hits), "items": items}

        return self._invoke("search_corpus", args, fn, lambda r: f"{r['count']} document(s)")

    def read_document(self, document_id: str) -> dict:
        def fn(s: Session) -> dict:
            d = corpus_svc.get_document(s, document_id)
            return DocumentDetail.model_validate(summary_dict(s, d, content=True)).model_dump(mode="json")

        return self._invoke("read_document", {"document_id": document_id}, fn,
                            lambda r: f"{r['doc_key']} v{r['version']} ({r['plan_status']}, "
                                      f"{'current' if r['is_current'] else 'superseded'})")

    def get_spend_summary(self) -> dict:
        def fn(s: Session) -> dict:
            out = spending_svc.spend_summary(s, self._period(s), clock=self._clock)
            return SpendSummary.model_validate(out).model_dump(mode="json")

        return self._invoke("get_spend_summary", {}, fn,
                            lambda r: f"company total {r['company_total']} {r['unit']}, "
                                      f"coverage {r['coverage']['status']}")

    def get_budgets(self) -> dict:
        def fn(s: Session) -> dict:
            p, env = budget_svc.resolve_envelope(s, None, self._clock)
            return BudgetState.model_validate(budget_svc.budget_state(s, p, env)).model_dump(mode="json")

        return self._invoke("get_budgets", {}, fn,
                            lambda r: f"envelope {r['envelope_total']} {r['unit']}, version {r['state_version']}")

    def get_forecast(self) -> dict:
        def fn(s: Session) -> dict:
            result = forecast_svc.forecast_for_period(s, self._provider, self._period(s), clock=self._clock)
            snap = forecast_svc.snapshot(s, result, clock=self._clock, ids=self._ids)
            return ForecastSnapshotOut.model_validate(forecast_svc.snapshot_out(snap)).model_dump(mode="json")

        return self._invoke("get_forecast", {}, fn,
                            lambda r: f"{r['availability']} ({r['provider']}), snapshot {r['id']}")

    def list_signals(self, status: str | None = None, team: str | None = None) -> dict:
        def fn(s: Session) -> dict:
            items = [ContextSignalOut.model_validate(signal_svc.signal_out(s, sig)).model_dump(mode="json")
                     for sig in signal_svc.list_signals(s, team=team, status=status)]
            return {"count": len(items), "items": items}

        return self._invoke("list_signals", {"status": status, "team": team}, fn, lambda r: f"{r['count']} signal(s)")

    # ---- draft-level writes ------------------------------------------------------------------

    def _check_write_budget(self, tool: str, limit: int) -> None:
        if self._writes[tool] >= limit:
            err = ToolError(tool, "write_budget_exhausted", f"a run may make at most {limit} {tool} calls")
            self.emit("error", err.as_dict())
            raise err

    def record_signal(self, signal: dict) -> dict:
        self._check_write_budget("record_signal", MAX_SIGNALS)
        payload = {k: v for k, v in dict(signal).items() if k != "agent_run_id"}

        def fn(s: Session) -> dict:
            body = ContextSignalIn.model_validate({**payload, "agent_run_id": self.run_id})
            existing = _same_signal(s, body)
            if existing is not None:
                return {**ContextSignalOut.model_validate(signal_svc.signal_out(s, existing)).model_dump(mode="json"),
                        "already_recorded": True}
            sig, corrected = signal_svc.create_signal(s, body, actor=self.actor, runner_kind=self._runner_kind,
                                                      clock=self._clock, ids=self._ids)
            return {**ContextSignalOut.model_validate(signal_svc.signal_out(s, sig, corrected)).model_dump(mode="json"),
                    "already_recorded": False}

        result = self._invoke("record_signal", {"signal": payload}, fn,
                              lambda r: f"signal {r['id']} ({r['status']}"
                                        f"{', already recorded' if r['already_recorded'] else ''})")
        self._writes["record_signal"] += 1
        if result["id"] not in self.signal_ids:
            self.signal_ids.append(result["id"])
        return result

    def draft_proposal(self, proposal: dict) -> dict:
        self._check_write_budget("draft_proposal", MAX_PROPOSALS)
        payload = {k: v for k, v in dict(proposal).items() if k != "agent_run_id"}

        def fn(s: Session) -> dict:
            body = _PROPOSAL_ADAPTER.validate_python({**payload, "agent_run_id": self.run_id})
            existing = _same_pending_proposal(s, body)
            if existing is not None:
                return {**ProposalOut.model_validate(proposal_svc.proposal_out(s, existing)).model_dump(mode="json"),
                        "already_drafted": True}
            p = proposal_svc.create_proposal(s, body, actor=self.actor, clock=self._clock, ids=self._ids)
            return {**ProposalOut.model_validate(proposal_svc.proposal_out(s, p)).model_dump(mode="json"),
                    "already_drafted": False}

        result = self._invoke("draft_proposal", {"proposal": payload}, fn,
                              lambda r: f"proposal {r['id']} {r['action_type']} {r['status']}"
                                        f"{' (already drafted)' if r['already_drafted'] else ''}; not applied")
        self._writes["draft_proposal"] += 1
        if result["id"] not in self.proposal_ids:
            self.proposal_ids.append(result["id"])
        return result


def _same_signal(s: Session, body: ContextSignalIn) -> ContextSignal | None:
    """An identical Droid signal (same claim, same exact citations) is reused, not duplicated."""
    want = sorted((c.document_id, c.quote) for c in body.citations)
    q = select(ContextSignal).where(
        ContextSignal.summary == body.summary, ContextSignal.status == body.status,
        ContextSignal.change_type == body.change_type, ContextSignal.produced_by != "finance",
    )
    for sig in s.scalars(q):
        if sig.team_id == body.team and sorted((c.document_id, c.quote) for c in sig.citations) == want:
            return sig
    return None


def _norm_lines(lines: list) -> list[tuple]:
    out = []
    for ln in lines:
        d = ln if isinstance(ln, dict) else ln.model_dump()
        if isinstance(d.get("amount"), float):
            return []  # let the proposal service reject it with `float_not_allowed`
        try:
            amount = Decimal(str(d.get("amount")))
        except Exception:  # noqa: BLE001 - invalid amounts are reported by the proposal service
            return []
        out.append((d.get("from_team"), d.get("to_team"), amount))
    return sorted(out, key=lambda t: (str(t[0]), str(t[1]), t[2]))


def _same_pending_proposal(s: Session, body) -> Proposal | None:
    """Re-running the same investigation does not stack identical pending drafts for finance."""
    want = _norm_lines(body.lines)
    if not want:
        return None
    q = select(Proposal).where(Proposal.status == "pending_review", Proposal.action_type == body.action_type,
                               Proposal.base_version == body.base_version, Proposal.created_by_role == "droid_agent")
    for p in s.scalars(q):
        if _norm_lines(p.lines) == want:
            return p
    return None
