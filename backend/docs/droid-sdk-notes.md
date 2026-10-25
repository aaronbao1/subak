# Factory Droid SDK: runtime integration notes

Researched 2026-10-24 for the in-product Droid integration. Sources are the
public Factory docs and SDK repo (cited inline). `docs.factory.ai/*` now
308-redirects to `docs.factory.com/*`.

Local state at time of writing: the `droid` CLI is **not installed** on the dev
machine and **no `FACTORY_API_KEY` is available**. Everything below about live
behavior is from docs, not from running it. Default runtime and tests use
`FakeDroidRunner`.

## 1. What we can rely on

| Fact | Source |
|---|---|
| Python package `droid-sdk`, import `droid_sdk`; latest 0.5.0 (2026-09-24); Python >= 3.10; deps `pydantic>=2`, `typing-extensions`. Apache-2.0. | https://docs.factory.com/sdk/python, https://pypi.org/pypi/droid-sdk/json |
| Optional extra `droid-sdk[mcp]` (`mcp>=1.27,<2`, `starlette>=0.40`, `uvicorn>=0.31,<1`) for in-process tools. | https://pypi.org/pypi/droid-sdk/json |
| The SDK **spawns the local `droid` CLI as a subprocess** (must be on `PATH`, or override via `Runtime(executable=...)`). Local subprocess sessions only. asyncio only. One active turn per session. | https://docs.factory.com/sdk/python |
| Auth: an existing local `droid` login, or `FACTORY_API_KEY` from env (or `api_key=` argument). Key is passed via child env, never argv/logs/exceptions. Keys are created at app.factory.ai/settings/api-keys and look like `fk-...`. | https://docs.factory.com/sdk/python, https://github.com/Factory-AI/droid-sdk-python, https://docs.factory.com/droid-exec/overview |
| CLI install: `curl -fsSL https://app.factory.ai/cli | sh` (to `~/.local/bin/droid`) or Homebrew. Needs glibc Linux (no Alpine) if containerized. | https://docs.factory.com/droid-exec/overview |
| TypeScript SDK `@factory/droid-sdk` (Node >= 18) has the same shape (run/createSession/resumeSession/stream, `tool()` + `createSdkMcpServer`). We use Python. | https://docs.factory.com/sdk/typescript |

## 2. Python API surface (the parts we use)

From https://docs.factory.com/sdk/python unless noted.

### One-shot vs session
- `run(prompt, *, cwd, model, reasoning_effort, images, files, output, timeout, config: SessionConfig, interactions: InteractionHandlers, runtime: Runtime, api_key) -> RunResult[T]` — one turn, creates/closes its own session (the saved session remains resumable).
- `Session(cwd, model, reasoning_effort, config, interactions, runtime, api_key)` — lazy; subprocess starts on `open()` / `async with`. Turns only via `session.stream(...)` (there is no `session.run`).
- `Session.resume(session_id, interactions, mcp_servers, runtime, api_key, disabled_tools, auto_reject_permission_requests, disable_builtin_skills, session_source)` — restores history/cwd/settings; **handlers and MCP servers must be reattached**; cannot change `cwd`/`model`.
- `list_sessions(cwd=, all_workspaces=, limit=)` reads local saved sessions without starting Droid. `list_models(...)`.
- Session methods: `interrupt()`, `close()`, `update_settings(...)`, `settings`, `context()`, `on_notification(cb, type=None)`, `list_tools(...)`, `list_mcp_servers()`, `list_mcp_tools()`, `fork()`, `compact()`, `rewind()`.

### SessionConfig (scoping)
`mode` (`Mode.AUTO` / `Mode.SPEC`), `autonomy`, `mcp_servers`, `tags`, `session_source`,
`auto_reject_permission_requests`, `disable_builtin_skills`, `system_prompt`
(string replaces default; `{"type": "preset", "preset": "droid", "append": ...}` appends),
`additional_tools`, `enabled_tools`, `disabled_tools`, `restrict_tools` (sets of tool IDs;
bare strings raise `TypeError`; `restrict_tools` is an allowlist that never elevates permissions).

- `Autonomy.OFF | LOW | MEDIUM | HIGH` (OFF asks before every action; LOW = edits + read-only commands).
- `InteractionHandlers(on_permission=..., on_question=...)`. Permission handler is sync in the example: `def handler(request: PermissionRequest) -> PermissionResponse: return request.respond(ToolConfirmationOutcome.PROCEED_ONCE)`; deny with `ToolConfirmationOutcome.CANCEL` (https://raw.githubusercontent.com/Factory-AI/droid-sdk-python/main/examples/interactions.py). Action types include `EditAction`, `ExecuteAction`, `CreateFile`, `ApplyPatchAction`, `McpToolAction`, ... (in `droid_sdk.permissions`).
- CLI-level naming for MCP tools is `MCP:<server>` / `MCP:<server>/<tool>` (https://docs.factory.com/droid-exec/overview). Whether the SDK tool-ID sets use the same strings is **not documented**; resolve at runtime with `session.list_tools()` (returns IDs, `allowed`, `source`).

### Streaming events (`async with session.stream(prompt, include_partial_messages=..., timeout=...) as stream`)
- Default: `UserMessage`, `AssistantMessage`, `ToolCall(name, tool_use_id, input)`, `ToolResult(tool_use_id, tool_name, content, is_error)`, `HookExecution`, `ErrorEvent(message, error_type, timestamp)`, terminal `RunResult`.
- With partials: `TextDelta`, `TextComplete`, `ThinkingDelta`, `ThinkingComplete`, `ToolCallDelta`, `ToolProgress(update.type in tool_call|tool_result|error|status|message)`, `TokenUsageUpdate`, `WorkingStateChanged`, `PermissionResolved`, `SettingsUpdated`, `McpStatusChanged`, ...
- `RunResult`: `RunSuccess` / `RunInterrupted` / `RunFailure` (`error_during_execution`, `error_structured_output`); fields `subtype, text, messages, usage, duration, turn_count, session_id, output, structured_output, error`. `usage` includes `input_tokens, output_tokens, cache_*_tokens, thinking_tokens, factory_credits`.
- Exiting the `async with` interrupts unfinished work. Errors: `SessionBusyError` (2nd concurrent stream), `RunTimeoutError`, `StreamIncompleteError`, `DroidConnectionError`, `DroidProcessError`, `DroidProtocolError`; all derive `DroidError`.
- Matching pattern (https://raw.githubusercontent.com/Factory-AI/droid-sdk-python/main/examples/stream_events.py): `match event: case ToolCall(): ... case ToolResult(): ...`.

### Structured output
`output=` accepts a Pydantic `BaseModel` subclass (typed `RunResult[Model]`) or `JsonSchema({...})`. Failure is subtype `error_structured_output`. Useful for getting a `DraftProposal` shape, **but the backend still validates it** — SDK validation is not our authority.

### Observability
`Runtime(executable, args, env, observability=Observability(logger, metrics, tracing))`; sinks exclude prompts/tool I/O/credentials. Hooks are file-configured (`.factory/hooks.json`) only.

## 3. Exposing backend tools to Droid

Options:

1. **In-process SDK MCP tools (recommended).** `from droid_sdk.mcp import tool, create_sdk_mcp_server, ToolResponse`. `@tool(name, description)` on a fully type-annotated (sync or async) function; the input schema is derived from type hints into a Pydantic model with `extra="forbid"`; a return annotation is required (`str`/`ToolResponse` = text; other object-schema types = structured content). `create_sdk_mcp_server(name, tools, version="1.0.0")` serves loopback-only Streamable HTTP on `127.0.0.1:<ephemeral>/mcp` with a random bearer token per start; pass via `SessionConfig(mcp_servers=[server])`. Source: https://raw.githubusercontent.com/Factory-AI/droid-sdk-python/main/src/droid_sdk/mcp.py, https://raw.githubusercontent.com/Factory-AI/droid-sdk-python/main/examples/sdk_mcp.py
   - Tool functions call our **service layer directly** (same process), so no extra auth surface, and the token-protected loopback server is the only transport.
2. **External HTTP MCP** (`HttpMcpServerConfig(name, url, headers, oauth)`): only if we later split processes. Needs its own auth.
3. **Plain HTTP / shell (curl to FastAPI)**: rejected — requires granting execute permissions and gives Droid unscoped access.

Tool set (read + draft only; no apply/approve tool exists):
`get_budget_state`, `get_spend_summary`, `get_data_quality`, `search_documents`, `read_document`,
`get_forecast`, `draft_redistribution_proposal`, `draft_addition_proposal`.
Draft tools persist proposals in `draft`/`pending_review` status with the
budget-state version they were based on and cited evidence IDs. Approval stays
a finance-only HTTP endpoint outside Droid's reach (bounded authority).

Scoping: `Autonomy.OFF` or `LOW`, `restrict_tools` = only our MCP tools (exact IDs
confirmed via `list_tools()` at startup; fail closed if they don't match),
`disable_builtin_skills=True`, `cwd` = an empty sandbox dir (not the repo), and an
`on_permission` handler that returns `PROCEED_ONCE` only for `McpToolAction` on our
server and `CANCEL` for everything else (Edit/Execute/CreateFile/ApplyPatch).
`on_question` cancels (or relays to UI later).

## 4. Streaming visible activity to the UI

Backend wraps `session.stream(..., include_partial_messages=True)` and maps SDK
events to our own `AgentEvent` schema (stable, SDK-independent), stored per run
and pushed via SSE (`GET /agent/runs/{id}/events`):

| SDK event | AgentEvent.type |
|---|---|
| `TextDelta` / `AssistantMessage` | `assistant_text` |
| `ToolCall` | `tool_call` (name, sanitized input) |
| `ToolResult` | `tool_result` (name, is_error, short summary) |
| `PermissionResolved` | `permission` |
| `ErrorEvent` | `error` |
| `RunResult` | `run_finished` (subtype, usage, session_id) |

Thinking deltas are dropped. `FakeDroidRunner` emits the same `AgentEvent`
sequence deterministically, so the frontend and tests never depend on the SDK.
Every event carries `source: "droid_sdk" | "fake_runner"` for honest real-vs-simulated labeling.

## 5. Auth / env vars (ours + SDK)

- `FACTORY_API_KEY` — read by the SDK from env; we never store, log, or request it.
- `DROID_RUNNER=fake|sdk` (ours; default `fake`). `sdk` requires `droid` on PATH and
  a key or local login; otherwise startup reports "droid unavailable" and falls back to fake with a visible label.
- `DROID_EXECUTABLE` (ours, optional) -> `Runtime(executable=...)`.
- `DROID_MODEL` (ours, optional; omit for user default; `"auto"` = Factory Router).
- `DROID_TIMEOUT_S` (ours, default 120).

## 6. Unknowns / risks (as of research; see §7 for live answers)

- Exact tool-ID strings for SDK MCP tools in `restrict_tools` (CLI uses `MCP:<server>/<tool>`); verify with `list_tools()` once a key exists.
- Minimum `droid` CLI version for SDK MCP and custom system prompts (older versions raise `DroidProtocolError` / `SessionError`); no minimum is documented.
- `PermissionRequest` attribute names beyond `options`/`respond()` are not documented in the examples; inspect `droid_sdk.permissions` when installed.
- Whether MCP tool calls prompt for permission under `Autonomy.LOW` (TS docs: "Tool calls still follow autonomy and permission rules").
- Concurrency: one turn per session and one subprocess per session — need a per-run session and a small concurrency cap.
- Session storage is local to the `droid` user dir (`~/.factory`); resume across server restarts relies on that.
- Cost/rate limits (`factory_credits` per run) are unknown; record `usage` as provider-reported.
- SDK is pre-1.0 (0.x, weekly releases): pin `droid-sdk[mcp]==0.5.0` as an optional extra, import lazily so the backend runs without it.

## 7. Verified live (2026-10-24)

Three live turns via a throwaway probe (not committed): `droid` CLI **0.249.0**, `droid-sdk` **0.5.0**
(`mcp` 1.30.0), Python 3.13, empty temp `cwd`, `disable_builtin_skills=True`, in-process SDK MCP server
`probe` with one tool `echo_number(n: int) -> str`. Default session settings reported:
model `gpt-6.1-sol`, reasoning `high`, mode `auto`. The SDK added its own tag `sdk {language: python, version: 0.5.0}`.

### Resolved unknowns

| Unknown (§6) | Verified answer |
|---|---|
| Tool-ID strings | SDK MCP tools are `<server>___<tool>` (**three** underscores), e.g. `probe___echo_number` (so ours: `northstar___get_budget_state`, ...). Not `MCP:<server>/<tool>`. `ToolInfo.source` was `None`; category `READ`. `list_mcp_tools()` gives `server_name='probe'`, `name='echo_number'`, `is_read_only=None`, input schema from type hints. |
| Built-in tool IDs | `ApplyPatch, AskUser, ConnectApp, CreateAutomation, DeleteAutomation, DismissHandoffItems, EditAutomation, EndFeatureRun, Execute, ExitSpecMode, FetchUrl, GenerateDroid, GenerateImage, Glob, Grep, ListAutomations, ListAutomationTemplates, Loop, LS, ProposeMission, Read, ReadAutomation, RunAutomation, Script, Skill, StageSettingsChanges, StartMissionRun, Task, TaskOutput, TaskStop, TodoWrite, ToolSearch, WaitForScript, WebSearch`. |
| `restrict_tools` effect | `list_tools(restrict_tools=["probe___echo_number"])` still leaves `Script`, `ToolSearch`, `WaitForScript` allowed (meta tools are not removable by the allowlist). `update_settings(restrict_tools=..., autonomy=...)` is accepted and reflected in `session.settings`. With `disabled_tools={"Script","WaitForScript","ToolSearch"}` in `SessionConfig`, `ToolSearch` still listed as allowed. |
| How MCP tools are called | **Not as direct tool calls.** The CLI uses a code-mode `Script` tool: the model first runs `Script` -> `tools.ToolSearch({query:"select:probe___echo_number"})` to load the deferred tool, then a second `Script` with `await tools.probe.echo_number({n:7})`. `ToolCall.name` is `Script` (inner `ToolSearch` shows as its own `ToolCall`/`ToolResult`), never `probe___echo_number`. With `Script` disabled the model reported it could not reach the tool (no call, no permission request). |
| Permission prompts at LOW / OFF | Yes, at both. The `ToolSearch` Script ran without a prompt; the Script that invokes the MCP tool raised a permission request at `Autonomy.LOW` and again at `OFF`. **Our `on_permission` handler was never invoked**: SDK 0.5.0 failed to parse the request (`permission_request_from_wire`), emitted `ErrorEvent(message="Permission interaction handler failed", error_type=DROID_CLIENT_ERROR)` and fell back to `cancel` (`PermissionResolved(selected_option=CANCEL, tool_use_ids=())`, tool result `"Error: Tool execution cancelled by user"`, `is_error=True`). The MCP handler was never called. Fail-closed, but it means **our tools cannot currently execute through the SDK with this CLI/SDK pair at LOW/OFF**. |
| `PermissionRequest` shape (from installed source) | `PermissionRequest(actions: tuple[PermissionAction], options: tuple[PermissionOption(label, value: ToolConfirmationOutcome)], associated_session_ids)`; there is no `.action`. `respond(outcome)` raises `ValueError` if the outcome was not offered. `McpToolAction(tool_use, tool_name, impact_level, server_name, actual_tool_name)`. The SDK schema has no confirmation-details type for `Script`, which is the likely parse failure (raw wire shape not captured). |
| Question handler | `QuestionRequest(tool_call_id, questions)`; cancel with `request.cancel()` (returns `QuestionResponse`), not `respond(...)`. |
| Stream event types seen (`include_partial_messages=True`) | `WorkingStateChanged`, `UserMessage`, `AssistantMessage` (content blocks; `.text` was `''` for tool-only turns), `ToolCallDelta`, `ToolCall`, `ToolResult`, `TokenUsageUpdate`, `ErrorEvent`, `PermissionResolved`, `ThinkingDelta`, `ThinkingComplete`, `TextDelta`, `TextComplete`, `SessionTitleUpdated`, terminal `RunSuccess`. Not seen: `ToolProgress`, `HookExecution`, `SettingsUpdated`, `McpStatusChanged`. |
| `RunResult` / usage | `RunSuccess(subtype="success", text, messages, usage: Usage, duration: timedelta, turn_count, session_id, output, structured_output, output_validation_error, success, interrupted)`. A run whose tools were all cancelled still ends `success` with empty `text`. `Usage` is a frozen **dataclass** (not Pydantic; use `dataclasses.asdict`): `input_tokens, output_tokens, cache_creation_tokens, cache_read_tokens, thinking_tokens, factory_credits: float`. Observed per turn: 10801.0, 4708.0, 3433.0 `factory_credits` (unit not documented). `TokenUsageUpdate` is cumulative per session (15509.0 after turns 1+2). |
| Turn latency | 3 to 5 s per short turn. |
| Minimum CLI version | 0.249.0 works for SDK MCP servers, `list_tools`, `update_settings`; custom `system_prompt` not exercised. |

### Contradicts earlier notes / current `sdk_runner.py`
- `ToolConfirmationOutcome` is **not** exported from `droid_sdk.permissions` (import from `droid_sdk`); the runner's import fails as `sdk_not_installed`.
- `SessionConfig.tags` takes `SessionTag(name=..., metadata=...)` objects, not strings.
- `list_tools()` returns `list[ToolInfo]` directly (no `.tools`).
- `ToolCall`/`ToolResult` names are `Script`/`ToolSearch`, so "non-northstar tool call" warnings would fire for every legitimate call; the tool ID separator is `___`.
- `PermissionRequest` has `actions` (tuple), not `action`; even so the handler is not reached for `Script` requests (above).
- Usage needs `dataclasses.asdict`, not `model_dump`.

### Next options (untested)
Autonomy `MEDIUM`/`HIGH` may auto-approve the `Script` call (still bounded by `restrict_tools`, since Script can only reach allowed tools, and our toolbox has no apply/approve tool); or an SDK release that parses Script permission requests; or an external HTTP MCP server with `skip_permissions` semantics. Each needs a live check before relying on it.

### Resolved by the SDK runner (2026-10-24, see `droid-live-log.md`)
- The raw `Script` permission request has `details.type = "script"`, which is missing from SDK 0.5.0's
  `ToolConfirmationType`, so `permission_request_from_wire` fails. The MCP call inside the script then
  raises a second request with `details.type = "mcp_tool"`, `serverName = "northstar"` and
  `toolName = "northstar___<tool>"`, which the SDK can parse. `toolUse.input.script` carries the full
  script source.
- `SdkDroidRunner` replaces `session._dispatcher` with its own `PermissionGate`. The gate takes the raw
  params and returns `{"selectedOption": ...}`, and it statically checks the script source, so
  Autonomy can stay LOW. With this in place our tools execute: all 41 requests of the five product runs
  were approved correctly (39 of 39 when this was first written, after runs 1-3). The eval runs later
  had two cancellations that were not kept, see `../evals/README.md`. This relies on a private attribute of the pinned 0.5.0, and the runner refuses to start
  (`sdk_api_mismatch`) if that attribute is missing.
