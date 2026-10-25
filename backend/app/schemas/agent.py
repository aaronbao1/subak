"""Agent runs: create request, run output with step log, and streamed activity events."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from app.schemas.charts import ChartRequest
from app.schemas.common import InModel, MoneyStr, OutModel

TaskType = Literal["interpret_corpus", "propose_allocation", "answer_question"]


class ProposeParams(InModel):
    mode: Literal["addition", "transfer"] = "addition"
    # addition: new money entering the envelope (default 50000.00); transfer: optional cap on funds moved.
    amount: MoneyStr | None = None
    prioritize: str = "research"
    # An explicit transfer source is binding; the runner cannot substitute another donor.
    source_team: str | None = Field(default=None, min_length=1, max_length=200)
    # Stale-proposal recovery: finance's approval of this proposal was refused (409 stale_proposal).
    # Droid explains what changed since its base version and offers a rebased draft. Not combinable
    # with mode/amount/prioritize.
    stale_proposal_id: str | None = Field(default=None, min_length=1, max_length=200)


class ForecastQuestionContext(InModel):
    action: Literal["explain", "compare", "preview", "refresh"] = "explain"
    run_id: str = Field(min_length=1, max_length=200)
    scope_type: Literal["company", "team", "person", "shared"] = "company"
    scope_id: str | None = Field(default=None, max_length=200)
    driver_id: str | None = Field(default=None, max_length=200)
    compare_run_id: str | None = Field(default=None, max_length=200)
    drivers: list[dict[str, Any]] = Field(default_factory=list, max_length=50)
    idempotency_key: str | None = Field(default=None, max_length=200)


class AnswerParams(InModel):
    forecast_context: ForecastQuestionContext | None = None
    # Optional: also build this chart with the read-only `build_chart_spec` tool; the spec is attached to
    # the run output as `output.charts[]` (only charts the toolbox actually built).
    chart: ChartRequest | None = None


class AgentRunCreate(InModel):
    task_type: TaskType
    instruction: str = Field(default="", max_length=4000)
    params: dict[str, Any] = Field(default_factory=dict)
    # true: run to completion before responding (201). false: start in the background (202) and follow
    # GET /api/agent/runs/{id}/events (SSE) for live activity.
    wait: bool = True


class AgentStepOut(OutModel):
    seq: int
    tool: str
    args: dict[str, Any]
    result_summary: str | None
    at: datetime


class AgentEventOut(OutModel):
    seq: int
    type: str
    source: Literal["fake_runner", "droid_sdk", "backend"]
    data: dict[str, Any]
    at: datetime


class RunProposalRef(OutModel):
    id: str
    action_type: Literal["addition", "transfer"]
    # Current status, read live: a drafted proposal is pending_review until finance decides it.
    status: str


class AgentRunOut(OutModel):
    id: str
    task_type: TaskType
    instruction: str
    params: dict[str, Any]
    initiated_by: dict[str, str]
    runner_kind: Literal["fake", "sdk"]
    status: Literal["running", "succeeded", "failed", "unavailable"]
    # Real-vs-simulated label for the UI: the fake runner is a scripted playbook, not a model.
    simulated: bool
    summary: str | None
    output: dict[str, Any] | None
    error: str | None
    proposals: list[RunProposalRef]
    signal_ids: list[str]
    # Droid can only draft: a run never applies an allocation change.
    applied_changes: Literal[False] = False
    steps: list[AgentStepOut]
    events: list[AgentEventOut]
    events_url: str
    started_at: datetime
    finished_at: datetime | None


class AgentRunList(OutModel):
    count: int
    items: list[AgentRunOut]
