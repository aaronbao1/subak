"""Droid tool definitions: the single source of truth for what Droid can call.

Both runners use exactly these tools: the FakeDroidRunner calls the toolbox methods directly, and the
SDK runner (`agent/northstar_droid/sdk_tools.py`) exposes the same names and input schemas to Droid as
in-process MCP tools. `agent/northstar_droid/tool_manifest.json` is generated from this module
(`python -m app.agent.tools`) and a test keeps them in sync.

Read tools plus two draft-level writes. There is deliberately NO apply / approve / decide / reject
tool: a drafted proposal is `pending_review` until a finance approver decides it over HTTP.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.proposals import AdditionCreate, TransferCreate
from app.schemas.signals import ContextSignalIn, SignalStatus


class _In(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SearchCorpusIn(_In):
    query: Annotated[str, Field(max_length=500)] = ""
    team: str | None = None
    project: str | None = None
    include_superseded: bool = True


class ReadDocumentIn(_In):
    document_id: Annotated[str, Field(min_length=1, max_length=200)]


class NoArgsIn(_In):
    pass


class ListSignalsIn(_In):
    status: SignalStatus | None = None
    team: str | None = None


class RecordSignalIn(_In):
    """A ContextSignalIn without `agent_run_id`: the toolbox stamps the run id itself."""

    signal: dict[str, Any]


class DraftProposalIn(_In):
    """An AdditionCreate | TransferCreate without `agent_run_id`: the toolbox stamps the run id."""

    proposal: dict[str, Any]


Kind = Literal["read", "draft"]


@dataclass(frozen=True)
class ToolDef:
    name: str
    kind: Kind
    description: str
    input_model: type[BaseModel]

    def input_schema(self) -> dict[str, Any]:
        if self.name == "record_signal":
            return _strip_run_id(ContextSignalIn.model_json_schema())
        if self.name == "draft_proposal":
            return {
                "oneOf": [_strip_run_id(AdditionCreate.model_json_schema()),
                          _strip_run_id(TransferCreate.model_json_schema())],
                "discriminator": {"propertyName": "action_type"},
            }
        return self.input_model.model_json_schema()


def _strip_run_id(schema: dict[str, Any]) -> dict[str, Any]:
    schema = json.loads(json.dumps(schema))
    schema.get("properties", {}).pop("agent_run_id", None)
    if "required" in schema:
        schema["required"] = [r for r in schema["required"] if r != "agent_run_id"]
    return schema


TOOLS: tuple[ToolDef, ...] = (
    ToolDef("search_corpus", "read",
            "Search company documents (plans, updates, email/Slack exports). All terms must match; "
            "\"quoted phrases\" supported. Returns document summaries with is_current, supersedes/"
            "superseded_by links and exact match offsets usable for citations. Empty query lists all.",
            SearchCorpusIn),
    ToolDef("read_document", "read",
            "Read one document version in full, with origin, plan_status, dates, team/project tags and "
            "its supersedes chain. Quote text from `content` verbatim when citing.",
            ReadDocumentIn),
    ToolDef("get_spend_summary", "read",
            "Recorded spend for the current planning period by team, cost category and value kind, with "
            "coverage. Included usage is display-only and never counts as spend.",
            NoArgsIn),
    ToolDef("get_budgets", "read",
            "Current saved internal budget state: envelope total, per-team allocations, recorded spend, "
            "remaining, and state_version (use it as base_version when drafting).",
            NoArgsIn),
    ToolDef("get_forecast", "read",
            "Projections from the configured ForecastProvider (placeholder, not a model). Persists a "
            "snapshot and returns its id so a proposal can cite exactly what it relied on. May be "
            "`unavailable`; never treat that as zero.",
            NoArgsIn),
    ToolDef("list_signals", "read",
            "Context signals already recorded (by finance or earlier Droid runs), with citation currency.",
            ListSignalsIn),
    ToolDef("record_signal", "draft",
            "Record a cited context signal (what is planned/changing, team, timing, status current|"
            "superseded|conflicting|informal, uncertainty). Every citation must quote a stored document "
            "version exactly; the backend verifies it. A current signal may not rest only on superseded "
            "documents. Does not change any budget.",
            RecordSignalIn),
    ToolDef("draft_proposal", "draft",
            "Draft an allocation proposal for finance review: action_type `addition` (new money enters "
            "the envelope) or `transfer` (existing money moves between teams; envelope unchanged). The "
            "backend computes before/after and validates arithmetic. The result is pending_review and is "
            "NOT applied; only a finance approver can apply it.",
            DraftProposalIn),
)

TOOL_NAMES: tuple[str, ...] = tuple(t.name for t in TOOLS)
FORBIDDEN_TOOL_WORDS = ("apply", "approve", "decide", "decision", "reject", "delete", "reset")


def manifest() -> dict[str, Any]:
    return {
        "server": "northstar",
        "note": "Generated by `python -m app.agent.tools`. Read + draft only; no apply/approve tool exists.",
        "tools": [{"name": t.name, "kind": t.kind, "description": t.description, "input_schema": t.input_schema()}
                  for t in TOOLS],
    }


MANIFEST_PATH = Path(__file__).resolve().parents[3] / "agent" / "northstar_droid" / "tool_manifest.json"


def render_manifest() -> str:
    return json.dumps(manifest(), indent=2, sort_keys=True) + "\n"


if __name__ == "__main__":  # pragma: no cover
    MANIFEST_PATH.write_text(render_manifest(), encoding="utf-8")
    print(f"wrote {MANIFEST_PATH}", file=sys.stderr)
