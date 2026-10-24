"""The DroidRunner interface (design.md §6): what a runner gets, what it returns, how it fails.

A runner never touches the database or HTTP directly. It receives an `AgentToolbox`, which is the ONLY
set of capabilities it has: read tools plus two draft-level writes (record a cited signal, draft a
proposal in `pending_review`). There is no decide/apply/approve capability anywhere in this interface;
approval is a finance-only HTTP endpoint the runner cannot reach (bounded authority).

Two implementations:
- `app.agent.fake_runner.FakeDroidRunner` - deterministic scripted investigation (default, tests).
- `northstar_droid.sdk_runner.SdkDroidRunner` (in `agent/`) - the real Factory Droid SDK, loaded
  lazily and only when `DROID_RUNNER=sdk` and `FACTORY_API_KEY` is set.
"""

from __future__ import annotations

from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

TaskType = Literal["interpret_corpus", "propose_allocation", "answer_question"]
RunnerKind = Literal["fake", "sdk"]
EventSource = Literal["fake_runner", "droid_sdk", "backend"]

# Activity events streamed to the UI. Stable and SDK-independent (droid-sdk-notes.md §4).
EVENT_TYPES = (
    "run_started",
    "tool_call",
    "tool_result",
    "evidence_found",
    "supersession_detected",
    "conflict_detected",
    "signal_recorded",
    "proposal_drafted",
    "assistant_text",
    "warning",
    "error",
    "run_finished",
)


class AgentTask(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: TaskType
    instruction: str = ""
    params: dict[str, Any] = Field(default_factory=dict)


class AgentRunOutput(BaseModel):
    """What a runner reports. The backend overwrites `proposal_ids`/`signal_ids` with what the toolbox
    actually recorded, so a runner cannot claim work it did not do."""

    model_config = ConfigDict(extra="forbid")

    summary: str
    signal_ids: list[str] = Field(default_factory=list)
    proposal_ids: list[str] = Field(default_factory=list)
    findings: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[dict[str, Any]] = Field(default_factory=list)
    usage: dict[str, Any] | None = None  # provider-reported (SDK) usage, never estimated
    session_id: str | None = None


class ToolError(Exception):
    """A tool call the backend refused (validation, stale state, unknown id). Runners see the code."""

    def __init__(self, tool: str, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(f"{tool}: {code}: {message}")
        self.tool = tool
        self.code = code
        self.message = message
        self.details = details or {}

    def as_dict(self) -> dict[str, Any]:
        return {"tool": self.tool, "code": self.code, "message": self.message, "details": self.details}


class RunnerUnavailable(Exception):
    """The selected runner cannot run (no key, SDK or CLI missing). Surfaced as 503, never faked."""

    def __init__(self, message: str, *, reason: str = "runner_unavailable") -> None:
        super().__init__(message)
        self.reason = reason


@runtime_checkable
class AgentToolbox(Protocol):
    """The only capabilities a runner gets. Every call is recorded as an `agent_run_steps` row."""

    run_id: str
    source: EventSource

    # read
    def search_corpus(self, query: str = "", team: str | None = None, project: str | None = None,
                      include_superseded: bool = True) -> dict: ...
    def read_document(self, document_id: str) -> dict: ...
    def get_spend_summary(self) -> dict: ...
    def get_budgets(self) -> dict: ...
    def get_forecast(self) -> dict: ...
    def list_signals(self, status: str | None = None, team: str | None = None) -> dict: ...

    # draft-level writes (never change allocations)
    def record_signal(self, signal: dict) -> dict: ...
    def draft_proposal(self, proposal: dict) -> dict: ...

    # activity stream
    def emit(self, type: str, data: dict | None = None) -> None: ...

    # no decide / apply / approve capability exists


class DroidRunner(Protocol):
    kind: RunnerKind

    def run(self, task: AgentTask, tools: AgentToolbox) -> AgentRunOutput: ...
