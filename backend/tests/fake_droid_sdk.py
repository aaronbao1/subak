"""A fake `droid_sdk` module for SdkDroidRunner tests. Never talks to Factory.

It mirrors the parts of droid-sdk 0.5.0 the runner uses, with the live-verified quirks:
- MCP tools are listed as `northstar___<tool>`; `Script`, `ToolSearch`, `WaitForScript` stay allowed.
- Droid reaches MCP tools only through a code-mode `Script`; each Script raises a raw
  `droid.request_permission` request that goes to `session._dispatcher.handle_permission(raw)`.
- `Usage` is a frozen dataclass; `RunSuccess` has `subtype="success"`.

A test sets `module.SCENARIO = [Step, ...]`; each Step is one Script: its source (what the gate sees)
and a Python callable that performs the tool calls if the gate says `proceed_once`.
"""

from __future__ import annotations

import importlib.machinery
import json
import types
from dataclasses import dataclass, field
from datetime import timedelta
from enum import Enum
from typing import Any, Callable


class Autonomy(str, Enum):
    OFF = "off"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ToolConfirmationOutcome(str, Enum):
    PROCEED_ONCE = "proceed_once"
    PROCEED_ALWAYS = "proceed_always"
    CANCEL = "cancel"


class ErrorType(str, Enum):
    DROID_CLIENT_ERROR = "droid_client_error"


@dataclass(frozen=True)
class SessionTag:
    name: str
    metadata: dict | None = None


class SessionConfig:
    def __init__(self, **kw: Any) -> None:
        for bad in ("tags",):
            if any(isinstance(t, str) for t in kw.get(bad, ())):
                raise TypeError("tags must be SessionTag objects")
        self.kw = kw


class InteractionHandlers:
    def __init__(self, on_permission=None, on_question=None) -> None:
        self.on_permission, self.on_question = on_permission, on_question


class Runtime:
    def __init__(self, executable: str | None = None) -> None:
        self.executable = executable


@dataclass(frozen=True)
class Usage:
    input_tokens: int
    output_tokens: int
    cache_creation_tokens: int
    cache_read_tokens: int
    thinking_tokens: int
    factory_credits: float | None = None


@dataclass(frozen=True)
class TokenUsageUpdate(Usage):
    pass


@dataclass(frozen=True)
class ToolCall:
    name: str
    tool_use_id: str
    input: dict


@dataclass(frozen=True)
class ToolResult:
    tool_use_id: str
    tool_name: str
    content: Any
    is_error: bool


@dataclass(frozen=True)
class AssistantMessage:
    text: str


@dataclass(frozen=True)
class ErrorEvent:
    message: str
    error_type: ErrorType = ErrorType.DROID_CLIENT_ERROR


@dataclass(frozen=True)
class PermissionResolved:
    request_id: str
    tool_use_ids: tuple
    selected_option: ToolConfirmationOutcome


@dataclass(frozen=True)
class RunSuccess:
    text: str
    usage: Usage | None
    duration: timedelta = timedelta(seconds=4)
    turn_count: int = 1
    session_id: str = "sess-fake"
    subtype: str = "success"


@dataclass(frozen=True)
class RunFailure:
    text: str = ""
    usage: Usage | None = None
    error: ErrorEvent | None = None
    session_id: str = "sess-fake"
    subtype: str = "error_during_execution"


@dataclass(frozen=True)
class ToolInfo:
    id: str
    allowed: bool
    display_name: str = ""
    source: Any = None


@dataclass
class Step:
    """One Droid Script: `source` is what the permission gate inspects; `act(call)` runs if allowed."""

    source: str
    act: Callable[[Callable[..., Any]], Any] = lambda call: None
    confirmation_type: str | None = None  # None -> unknown to the SDK (the live Script case)
    extra_tool_uses: list[dict] = field(default_factory=list)
    options: tuple[str, ...] = ("proceed_once", "proceed_always", "cancel")


# ---- mcp submodule -------------------------------------------------------------------------------


class FakeTool:
    def __init__(self, name: str, description: str, fn: Callable[..., str]) -> None:
        self.name, self.description, self.fn = name, description, fn


def tool(name: str, description: str):
    def wrap(fn):
        return FakeTool(name, description, fn)
    return wrap


class FakeServer:
    def __init__(self, name: str, tools: list[FakeTool]) -> None:
        self.name = name
        self.tools = {t.name: t for t in tools}


def create_sdk_mcp_server(name: str, tools: list[FakeTool], version: str = "1.0.0") -> FakeServer:
    return FakeServer(name, tools)


# ---- session ---------------------------------------------------------------------------------------

STATE: dict[str, Any] = {}


class Session:
    def __init__(self, *, cwd=None, model=None, config=None, interactions=None, runtime=None) -> None:
        self.cwd, self.model, self.config, self.interactions, self.runtime = cwd, model, config, interactions, runtime
        self._dispatcher = object()  # replaced by the runner's gate
        STATE["session"] = self
        self.opened = False
        self.settings = types.SimpleNamespace(restrict_tools=frozenset(config.kw.get("restrict_tools") or ()),
                                              autonomy=config.kw.get("autonomy"))

    async def __aenter__(self):
        import os
        assert os.listdir(self.cwd) == [], "sandbox cwd must be empty"
        self.opened = True
        return self

    async def __aexit__(self, *exc):
        self.opened = False
        return False

    def _server(self) -> FakeServer:
        return self.config.kw["mcp_servers"][0]

    async def list_tools(self, **kw) -> list[ToolInfo]:
        STATE["list_tools_kw"] = kw
        override = MODULE.LIST_TOOLS
        if override is not None:
            return override(self, kw)
        restrict = set(kw.get("restrict_tools") or ())
        ids = [f"{self._server().name}___{n}" for n in self._server().tools]
        out = [ToolInfo(i, allowed=(not restrict or i in restrict)) for i in ids]
        out += [ToolInfo(m, allowed=True) for m in ("Script", "ToolSearch", "WaitForScript")]
        out += [ToolInfo(b, allowed=not restrict) for b in ("Execute", "ApplyPatch", "Read", "FetchUrl")]
        return out

    def stream(self, prompt: str, *, timeout=None, include_partial_messages=False):
        STATE["prompt"] = prompt
        return _Stream(self)


class _Stream:
    def __init__(self, session: Session) -> None:
        self.session = session

    async def __aenter__(self):
        return self._events()

    async def __aexit__(self, *exc):
        return False

    async def _events(self):
        server = self.session._server()
        results: list = []

        def call(name: str, **kwargs):
            out = server.tools[name].fn(**kwargs)
            results.append(out)
            return json.loads(out)

        for i, step in enumerate(MODULE.SCENARIO):
            tid = f"call_{i}"
            yield ToolCall("Script", tid, {"script": step.source})
            details = {"type": step.confirmation_type} if step.confirmation_type else {"type": "script"}
            raw = {"toolUses": [{"toolUse": {"type": "tool_use", "id": tid, "name": "Script",
                                             "input": {"script": step.source}},
                                 "confirmationType": details["type"], "details": details},
                                *step.extra_tool_uses],
                   "options": [{"label": o, "value": o} for o in step.options]}
            answer = await self.session._dispatcher.handle_permission(raw)
            STATE.setdefault("answers", []).append(answer)
            yield PermissionResolved(f"req_{i}", (tid,), ToolConfirmationOutcome(answer["selectedOption"]))
            if answer["selectedOption"] == "proceed_once":
                step.act(call)
                yield ToolResult(tid, "Script", [{"type": "text", "text": "ok"}], False)
            else:
                yield ToolResult(tid, "Script", "Error: Tool execution cancelled by user", True)
        if MODULE.QUESTION:
            STATE["question_answer"] = await self.session._dispatcher.handle_question({"toolCallId": "q1", "questions": []})
        yield TokenUsageUpdate(10, 20, 0, 0, 0, 99.0)
        if MODULE.RESULT is not None:
            yield MODULE.RESULT
        else:
            yield AssistantMessage(MODULE.FINAL_TEXT)
            yield RunSuccess(text=MODULE.FINAL_TEXT, usage=Usage(366, 80, 10008, 9687, 0, 10801.0))


def build() -> types.ModuleType:
    """Fresh `droid_sdk` + `droid_sdk.mcp` modules (install with monkeypatch.setitem(sys.modules, ...))."""
    global MODULE
    mod = types.ModuleType("droid_sdk")
    mod.__spec__ = importlib.machinery.ModuleSpec("droid_sdk", None)
    for name, value in dict(globals()).items():
        if isinstance(value, type) and value.__module__ == __name__:
            setattr(mod, name, value)
    mcp = types.ModuleType("droid_sdk.mcp")
    mcp.__spec__ = importlib.machinery.ModuleSpec("droid_sdk.mcp", None)
    mcp.tool, mcp.create_sdk_mcp_server = tool, create_sdk_mcp_server
    mod.mcp = mcp
    mod.SCENARIO = []
    mod.LIST_TOOLS = None
    mod.QUESTION = False
    mod.RESULT = None
    mod.FINAL_TEXT = "Drafted a proposal for finance review; nothing was applied."
    STATE.clear()
    MODULE = mod
    return mod


MODULE: types.ModuleType | None = None
