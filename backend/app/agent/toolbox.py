"""BackendToolbox: Droid's scoped capabilities, implemented on the backend service layer.

- Acts as the `droid_agent` role with actor id `droid:<run id>`; services enforce the same rules as
  the HTTP API (citation verification, arithmetic validation, stale base version, ...).
- Every call is recorded as an `agent_run_steps` row (the visible work record) and streamed as
  `tool_call` / `tool_result` events. Only calls that actually ran are recorded.
- Each tool runs in its own transaction: a refused call rolls back completely and comes back to the
  runner as a `ToolError` with the backend's error code.
- Per-run budgets cap tool calls and draft writes so a misbehaving model cannot flood the workspace.
- `rebase_proposal` only creates a NEW `pending_review` draft from a stale one (the HTTP rebase route,
  which `droid_agent` may already call); it shares the draft budget with `draft_proposal`. It works only
  on the one proposal the run was asked to recover (`params.stale_proposal_id`, passed in as
  `rebase_target`): rebasing marks the original `stale`, so any other proposal, including a finance
  analyst's pending one, is refused with `rebase_not_permitted`.
- `doc_scope` (interpret_corpus with `params.document_ids`, the batched CLI `python -m app.interpret`):
  `search_corpus` lists only the scoped documents, and `read_document` or a `record_signal` citation of
  any other document is refused with `document_out_of_scope`. Unscoped runs are unchanged.
- There is no method that decides, applies, approves or rejects a proposal.
"""

from __future__ import annotations

import threading
from collections import Counter
from copy import deepcopy
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
from app.db.models import AgentRunEvent, AgentRunStep, ContextSignal, Decision, Proposal
from app.db.session import transaction
from app.schemas.budget import BudgetState
from app.schemas.charts import ChartSpecOut
from app.schemas.documents import DocumentDetail, DocumentSearchItem
from app.schemas.forecasts import ForecastSnapshotOut
from app.schemas.people import PersonOut
from app.schemas.proposals import ProposalCreate, ProposalOut, RebaseIn
from app.schemas.signals import ContextSignalIn, ContextSignalOut
from app.schemas.spending import SpendSummary
from app.services import budget as budget_svc
from app.services import charts as chart_svc
from app.services import corpus as corpus_svc
from app.services import coverage as coverage_svc
from app.services import forecasts as forecast_svc
from app.services import people as people_svc
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


def _compact_forecast_receipt(receipt: dict, *, comparison: bool = False) -> dict:
    """Keep the full receipt stored server-side and source/calc answers readable by SDK."""
    result = dict(receipt)
    if "runs" in result:
        result["runs"] = [_compact_forecast_receipt(run, comparison=True) for run in result["runs"]]
    if "snapshot" in result:
        result["snapshot"] = {k:v for k,v in result["snapshot"].items()
                              if k not in ("observations", "coverage", "evidence", "drivers", "repository_state",
                                           "repository_excluded_records", "issued_targets", "truth_revisions",
                                           "forecast_errors", "model_registry")}
        excluded = receipt["snapshot"].get("repository_excluded_records")
        if excluded is not None:
            result["snapshot"]["repository_exclusion_summary"] = {
                "count": len(excluded), "by_reason": dict(Counter(row.get("reason", "unknown") for row in excluded)),
                "detail_note": "Full excluded records and provenance remain in the stored input snapshot.",
            }
        if "model_registry" in result:
            result["snapshot"]["model_registry_ref"] = "/model_registry"
        for index, calculation in enumerate(result.get("calculations", [])):
            if ("source_revisions" in calculation and "source_revisions" in result["snapshot"]
                    and calculation["source_revisions"] == result["snapshot"]["source_revisions"]):
                result["snapshot"].pop("source_revisions", None)
                result["snapshot"]["source_revisions_ref"] = f"/calculations/{index}/source_revisions"
                break
    # Preserve exact temporal omission effects once at the top level. A schedule
    # shift can have zero quarter delta and still change the next week's work.
    def summary_effect(effect):
        return {k:v for k,v in effect.items() if k not in ("daily", "weekly")}
    if "calculations" in result:
        result["calculations"] = [summary_effect(c) for c in result["calculations"]]
    if "views" in result:
        result["views"] = [{k:([summary_effect(e) for e in v] if k == "driver_effects" else v)
                            for k,v in view.items() if k not in ("cumulative", "daily")} for view in result["views"]]
        for view in result["views"]:
            view["queued_changes"] = [{k:v for k,v in change.items() if k in
                                       ("id", "source_id", "source_revision", "kind", "scope", "status",
                                        "reason", "publication_status", "publication_reason")}
                                      for change in view.get("queued_changes", [])]
        result["detail_note"] = ("Exact daily/weekly driver omission paths are in driver_effects. Full daily/cumulative "
                                 "forecast paths, queued-source documents and input histories remain in the stored "
                                 "immutable publication and snapshot. Queued source identities and reasons are retained here.")
    if comparison:
        # Comparing publications needs their corresponding quarter/weekly values,
        # exact identities, assumptions and source effects. Full cumulative paths
        # remain in the immutable publication and its dedicated explanation tool.
        result.pop("snapshot", None)
        result["views"] = [{k:([summary_effect(e) for e in v] if k == "driver_effects" else v)
                            for k,v in view.items() if k not in ("cumulative","daily")}
                           for view in result.get("views", [])]
        for view in result["views"]:
            qualifications = []
            weeks = []
            for point in view.get("weekly", []):
                point = dict(point)
                if isinstance(point.get("historical_error_interval"), dict):
                    intervals = {}
                    for level, interval in point["historical_error_interval"].items():
                        interval = {k:v for k,v in interval.items() if k not in
                                    ("stratum", "target_ids", "truth_revisions")}
                        qualification = interval.pop("qualification", None)
                        if qualification is not None:
                            if qualification not in qualifications:
                                qualifications.append(qualification)
                            interval["qualification_index"] = qualifications.index(qualification)
                        intervals[level] = interval
                    point["historical_error_interval"] = intervals
                weeks.append(point)
            if "weekly" in view:
                view["weekly"] = weeks
            if qualifications:
                view["interval_qualifications"] = qualifications
        result["driver_effects"] = [{k:v for k,v in e.items() if k != "daily"}
                                    for e in result.get("driver_effects", [])]
        result["calculations"] = [{k:v for k,v in calculation.items() if k not in
                                   ("daily", "weekly", "components", "source_revisions")}
                                  for calculation in result.get("calculations", [])]
        result.pop("model_registry", None)
        result["detail_note"] = ("Daily paths, calibration strata/record identities, model registry, queued-source documents "
                                 "and input histories are stored in each exact publication; use explain_forecast for one run. "
                                 "Weekly interval qualification_index refers to the view's interval_qualifications.")
    return result


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
        forecast_service: Any = None,
        start_seq: int = 0,
        rebase_target: str | None = None,
        doc_scope: list[str] | None = None,
        forecast_context: dict | None = None,
    ) -> None:
        self._factory = session_factory
        self.run_id = run_id
        self.source: EventSource = source
        self._runner_kind = runner_kind
        self._clock = clock
        self._ids = ids
        self._provider = forecast_provider
        self._forecast_service = forecast_service
        self.rebase_target = rebase_target  # the only proposal rebase_proposal may touch (None: none)
        # the only documents this run may list, read or cite (None: the whole corpus)
        self.doc_scope: frozenset[str] | None = frozenset(doc_scope) if doc_scope else None
        self._forecast_context = deepcopy(forecast_context)
        self.actor = Actor(id=f"droid:{run_id}", role="droid_agent")
        self._lock = threading.Lock()
        self._event_seq = start_seq
        self._step_seq = 0
        self.signal_ids: list[str] = []
        self.proposal_ids: list[str] = []
        self.forecast_receipts: list[dict] = []
        self.charts: list[dict] = []  # every chart spec actually built, attached to the run output
        # Budget refusals ("tool_budget_exhausted", "write_budget_exhausted:<tool>"): the run may have
        # left work undone, so it is reported in the run output (the interpret CLI does not count such
        # a run's documents as interpreted).
        self.budget_exhausted: list[str] = []
        self._writes = {"record_signal": 0, "draft_proposal": 0}  # draft_proposal also counts rebases

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

    def _check_forecast_context(self, tool: str, args: dict) -> None:
        """Structured forecast requests pin capabilities as well as prompting the model."""
        context = self._forecast_context
        if not context:
            return
        action_tools = {"explain": "explain_forecast", "compare": "compare_forecasts",
                        "preview": "preview_forecast_scenario", "refresh": "request_forecast_refresh"}
        expected_tool = action_tools[context.get("action", "explain")]
        forecast_tools = set(action_tools.values()) | {"get_forecast"}
        draft_tools = {definition.name for definition in TOOLS if definition.kind == "draft"}
        current_forecast_chart = tool == "build_chart_spec" and args.get("kind") == "projection_vs_allocation"
        if tool not in forecast_tools | draft_tools and not current_forecast_chart:
            return
        expected = {"scope_type": context.get("scope_type", "company"), "scope_id": context.get("scope_id")}
        if expected_tool == "compare_forecasts" and tool == "explain_forecast":
            # A comparison can drill into either pinned publication, never latest.
            if (args.get("run_id") in (context["run_id"], context.get("compare_run_id"))
                    and args.get("scope_type") == expected["scope_type"]
                    and args.get("scope_id") == expected["scope_id"]
                    and (context.get("driver_id") is None or args.get("driver_id") == context["driver_id"])):
                return
        if expected_tool == "request_forecast_refresh":
            expected = {"idempotency_key": context.get("idempotency_key")}
        elif expected_tool == "compare_forecasts":
            expected["run_ids"] = [context["run_id"], context.get("compare_run_id")]
        else:
            expected["run_id"] = context["run_id"]
            if expected_tool == "explain_forecast":
                expected["driver_id"] = context.get("driver_id")
            else:
                expected["drivers"] = context.get("drivers", [])
        if tool != expected_tool or args != expected:
            raise DomainError("forecast_context_mismatch", 403,
                              "The tool must preserve the requested forecast action, run, scope and assumptions",
                              {"requested_action": context.get("action", "explain"), "allowed_tool": expected_tool})

    def _invoke(self, tool: str, args: dict[str, Any], fn: Callable[[Session], dict],
                summarize: Callable[[dict], str]) -> dict:
        if self._step_seq >= MAX_TOOL_CALLS:
            err = ToolError(tool, "tool_budget_exhausted", f"a run may make at most {MAX_TOOL_CALLS} tool calls")
            if "tool_budget_exhausted" not in self.budget_exhausted:
                self.budget_exhausted.append("tool_budget_exhausted")
            self.emit("error", err.as_dict())
            raise err
        self._step_seq += 1
        seq = self._step_seq
        self.emit("tool_call", {"step": seq, "tool": tool, "args": args})
        try:
            with transaction(self._factory) as s:
                self._check_forecast_context(tool, args)
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

    def _check_scope(self, document_ids: list[str]) -> None:
        if self.doc_scope is None:
            return
        outside = sorted({d for d in document_ids if d not in self.doc_scope})
        if outside:
            raise DomainError("document_out_of_scope", 422,
                              "this run may only read and cite the documents it was scoped to",
                              {"document_ids": outside})

    def _period(self, s: Session):
        return coverage_svc.resolve_period(s, None, self._clock.now())

    # ---- read tools --------------------------------------------------------------------------

    def search_corpus(self, query: str = "", team: str | None = None, project: str | None = None,
                      include_superseded: bool = True) -> dict:
        args = {"query": query, "team": team, "project": project, "include_superseded": include_superseded}

        def fn(s: Session) -> dict:
            hits = corpus_svc.search_documents(s, q=query or None, team=team, project=project,
                                               include_superseded=include_superseded)
            if self.doc_scope is not None:
                hits = [h for h in hits if h[0].id in self.doc_scope]
            items = [DocumentSearchItem.model_validate({**summary_dict(s, d), "score": score, "matches": m})
                     .model_dump(mode="json") for d, m, score in hits[:MAX_SEARCH_RESULTS]]
            return {"query": query, "count": len(items), "total_matches": len(hits), "items": items}

        return self._invoke("search_corpus", args, fn, lambda r: f"{r['count']} document(s)")

    def read_document(self, document_id: str) -> dict:
        def fn(s: Session) -> dict:
            self._check_scope([document_id])
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

    def _forecast_operation(self, tool: str, args: dict, callback: Callable[[Any], dict]) -> dict:
        def fn(_s: Session) -> dict:
            if self._forecast_service is None:
                raise DomainError("forecast_unavailable", 503, "Published forecast service is unavailable")
            try:
                result = callback(self._forecast_service)
            except KeyError as exc:
                raise DomainError("forecast_not_found", 404, "Requested immutable forecast, scope or driver was not found") from exc
            except ValueError as exc:
                raise DomainError("invalid_forecast_request", 422, str(exc)) from exc
            # Full daily input history is available from stored snapshot; keep the
            # in-process SDK response bounded so source/calc explanations survive.
            return _compact_forecast_receipt(result)
        receipt = self._invoke(tool, args, fn, lambda r: _short({k:r.get(k) for k in
                            ("run_id", "id", "scenario_id", "status", "scope") if k in r}))
        self.forecast_receipts.append({"tool":tool,"args":args,"receipt":receipt})
        return receipt

    def explain_forecast(self, run_id: str, scope_type: str = "company", scope_id: str | None = None,
                         driver_id: str | None = None) -> dict:
        args = {"run_id":run_id,"scope_type":scope_type,"scope_id":scope_id,"driver_id":driver_id}
        return self._forecast_operation("explain_forecast", args, lambda svc: svc.explain(**args))

    def compare_forecasts(self, run_ids: list[str], scope_type: str = "company", scope_id: str | None = None) -> dict:
        args = {"run_ids":run_ids,"scope_type":scope_type,"scope_id":scope_id}
        return self._forecast_operation("compare_forecasts", args, lambda svc: svc.compare(**args))

    def preview_forecast_scenario(self, run_id: str, drivers: list[dict], scope_type: str = "company",
                                  scope_id: str | None = None) -> dict:
        args = {"run_id":run_id,"drivers":drivers,"scope_type":scope_type,"scope_id":scope_id}
        return self._forecast_operation("preview_forecast_scenario", args, lambda svc: svc.scenario(**args))

    def request_forecast_refresh(self, idempotency_key: str) -> dict:
        args = {"idempotency_key":idempotency_key}
        return self._forecast_operation("request_forecast_refresh", args, lambda svc: svc.refresh(**args))

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
            out = ForecastSnapshotOut.model_validate(forecast_svc.snapshot_out(snap)).model_dump(mode="json")
            # The snapshot keeps the daily series; Droid gets amounts, spent_to_date and share only.
            for item in [*out["forecast"]["projections"], *out["forecast"]["person_projections"]]:
                item.pop("daily", None)
            return out

        return self._invoke("get_forecast", {}, fn,
                            lambda r: f"{r['availability']} ({r['provider']}), snapshot {r['id']}")

    def list_signals(self, status: str | None = None, team: str | None = None,
                     include_company: bool = True) -> dict:
        """A team filter keeps company-scope signals (no team, apply to every team) unless include_company
        is false, so narrowing to a team never hides a company-wide change."""
        def fn(s: Session) -> dict:
            items = [ContextSignalOut.model_validate(signal_svc.signal_out(s, sig)).model_dump(mode="json")
                     for sig in signal_svc.list_signals(s, team=team, status=status,
                                                        include_company=include_company)]
            return {"count": len(items), "items": items}

        args: dict[str, Any] = {"status": status, "team": team}
        if team is not None:
            args["include_company"] = include_company
        return self._invoke("list_signals", args, fn, lambda r: f"{r['count']} signal(s)")

    def list_people(self, team: str | None = None) -> dict:
        def fn(s: Session) -> dict:
            items = [PersonOut.model_validate(people_svc.person_out(p)).model_dump(mode="json")
                     for p in people_svc.list_people(s, team=team)]
            return {"count": len(items), "items": items}

        return self._invoke("list_people", {"team": team}, fn, lambda r: f"{r['count']} person(s)")

    def build_chart_spec(self, kind: str, team: str | None = None, metric: str | None = None) -> dict:
        """Read-only: a Vega-Lite v5 spec from backend data (no forecast snapshot is persisted)."""
        args = {"kind": kind, "team": team, "metric": metric}

        def fn(s: Session) -> dict:
            out = chart_svc.build_chart(s, kind, team=team, metric=metric, provider=self._provider,
                                        clock=self._clock)
            return ChartSpecOut.model_validate(out).model_dump(mode="json")

        result = self._invoke("build_chart_spec", args, fn,
                              lambda r: f"{r['kind']} chart ({r['metric']}), {r['row_count']} row(s), "
                                        f"value kinds {', '.join(r['value_kinds'])}")
        self.charts.append(result)
        return result

    # ---- draft-level writes ------------------------------------------------------------------

    def _check_write_budget(self, tool: str, limit: int, *, counter: str | None = None) -> None:
        if self._writes[counter or tool] >= limit:
            err = ToolError(tool, "write_budget_exhausted", f"a run may make at most {limit} {tool} calls")
            if f"write_budget_exhausted:{tool}" not in self.budget_exhausted:
                self.budget_exhausted.append(f"write_budget_exhausted:{tool}")
            self.emit("error", err.as_dict())
            raise err

    def record_signal(self, signal: dict) -> dict:
        self._check_write_budget("record_signal", MAX_SIGNALS)
        payload = {k: v for k, v in dict(signal).items() if k != "agent_run_id"}

        def fn(s: Session) -> dict:
            body = ContextSignalIn.model_validate({**payload, "agent_run_id": self.run_id})
            self._check_scope([c.document_id for c in body.citations])
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

    def rebase_proposal(self, proposal_id: str, rationale: str | None = None) -> dict:
        """Re-draft a stale proposal's same lines on the current budget as a NEW pending_review proposal.

        Returns `stale_context` (what changed since the original's base version) and `proposal` (the new
        draft). A refusal (not stale, intent no longer fits, unknown id) carries `stale_context` in its
        details whenever the original exists, so Droid can still explain what changed.
        """
        if self.rebase_target is None or proposal_id != self.rebase_target:
            err = ToolError("rebase_proposal", "rebase_not_permitted",
                            "this run may only rebase the proposal it was asked to recover"
                            + (f" ({self.rebase_target})" if self.rebase_target else " (none was given)"),
                            {"proposal_id": proposal_id, "allowed_proposal_id": self.rebase_target})
            self.emit("error", err.as_dict())
            raise err
        self._check_write_budget("rebase_proposal", MAX_PROPOSALS, counter="draft_proposal")
        args = {"proposal_id": proposal_id, "rationale": rationale}

        def fn(s: Session) -> dict:
            original = proposal_svc.get_proposal(s, proposal_id)
            context = stale_context(s, original)
            note = (rationale or "").strip()
            text = f"{note}\n\nOriginal rationale ({original.id}): {original.rationale}"[:10_000] if note else None
            try:
                new = proposal_svc.rebase(s, proposal_id, RebaseIn(rationale=text), actor=self.actor,
                                          clock=self._clock, ids=self._ids)
            except DomainError as exc:
                raise DomainError(exc.code, exc.status, exc.message,
                                  {**(exc.details or {}), "stale_context": context}) from exc
            out = ProposalOut.model_validate(proposal_svc.proposal_out(s, new)).model_dump(mode="json")
            return {"stale_context": context, "proposal": out}

        result = self._invoke("rebase_proposal", args, fn,
                              lambda r: f"proposal {r['proposal']['id']} rebased from {proposal_id} onto version "
                                        f"{r['proposal']['base_version']}; {r['proposal']['status']}; not applied")
        self._writes["draft_proposal"] += 1
        if result["proposal"]["id"] not in self.proposal_ids:
            self.proposal_ids.append(result["proposal"]["id"])
        return result


def stale_context(s: Session, p: Proposal) -> dict:
    """What changed between a proposal's base version and the current budget (read-only)."""
    env = budget_svc.require_envelope(s, p.period_id)
    base_total, base = budget_svc.figures_to_decimal(p.before)
    current = budget_svc.current_figures(env)
    now_total, now = budget_svc.figures_to_decimal(current)
    changes = [{"team": t, "at_base": str(base.get(t, Decimal("0.00"))), "now": str(now.get(t, Decimal("0.00"))),
                "change": str(now.get(t, Decimal("0.00")) - base.get(t, Decimal("0.00")))}
               for t in sorted(set(base) | set(now))]
    # state_version is per envelope (per period): only decisions on this proposal's period moved it
    decided = s.scalars(select(Decision).join(Proposal, Proposal.id == Decision.proposal_id)
                        .where(Decision.to_version.is_not(None), Decision.from_version >= p.base_version,
                               Proposal.period_id == p.period_id)
                        .order_by(Decision.to_version)).all()
    moves = []
    for d in decided:
        if d.proposal_id == p.id:
            continue
        src = s.get(Proposal, d.proposal_id)
        moves.append({"decision_id": d.id, "proposal_id": d.proposal_id,
                      "action_type": src.action_type if src else None,
                      "lines": src.lines if src else [],
                      "envelope_increase": str(src.envelope_increase) if src else None,
                      "from_version": d.from_version, "to_version": d.to_version,
                      "decided_by": d.actor_id, "decided_at": d.decided_at.isoformat()})
    return {
        "original": {"id": p.id, "status": p.status, "action_type": p.action_type, "base_version": p.base_version,
                     "envelope_increase": str(p.envelope_increase), "lines": p.lines, "rationale": p.rationale},
        "base_version": p.base_version, "current_version": env.state_version,
        "is_outdated": p.base_version < env.state_version,
        "at_base": p.before, "current": current,
        "total_change": str(now_total - base_total), "changes": changes,
        "decisions_since_base": moves,
    }


def _same_signal(s: Session, body: ContextSignalIn) -> ContextSignal | None:
    """An identical Droid signal (same claim, scope, people, kind, title and exact citations) is reused,
    not duplicated. A person signal recorded without a team matches the one whose team was derived."""
    want = sorted((c.document_id, c.quote) for c in body.citations)
    q = select(ContextSignal).where(
        ContextSignal.summary == body.summary, ContextSignal.status == body.status,
        ContextSignal.change_type == body.change_type, ContextSignal.produced_by != "finance",
        ContextSignal.scope == body.scope,
    )
    for sig in s.scalars(q):
        team_ok = sig.team_id == body.team or (body.scope == "person" and body.team is None)
        if (team_ok and sorted(sig.person_ids or []) == sorted(body.person_ids)
                and sig.signal_kind == body.signal_kind and sig.title == body.title
                and sorted((c.document_id, c.quote) for c in sig.citations) == want):
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
