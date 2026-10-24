# Northstar Droid agent

Where and how Factory Droid is used at runtime in the Northstar AI-spend workspace. Droid does product
work inside the running backend: it reads the company corpus, connects facts across documents, records
cited context signals, and drafts allocation proposals for finance review. It never applies a change.

## Pieces

| Piece | Location | What it does |
|---|---|---|
| `DroidRunner` interface, `AgentTask`, `AgentToolbox`, `RunnerUnavailable` | `backend/app/agent/runner.py` | the contract every runner implements |
| Tool definitions (single source of truth) | `backend/app/agent/tools.py` | names, descriptions, input schemas; generates `northstar_droid/tool_manifest.json` |
| `BackendToolbox` | `backend/app/agent/toolbox.py` | the tools, implemented on the backend service layer as role `droid_agent`; records every call |
| `FakeDroidRunner` | `backend/app/agent/fake_runner.py` | deterministic scripted investigation (default, tests) |
| Runner selection | `backend/app/agent/loader.py` | `DROID_RUNNER=fake` (default) or `sdk` |
| `SdkDroidRunner` | `agent/northstar_droid/sdk_runner.py` | real Droid SDK session; lazy import |
| SDK MCP tools | `agent/northstar_droid/sdk_tools.py` | same tools as in-process MCP tools on the SDK's loopback server |
| Prompts | `agent/northstar_droid/prompts/` | system rules (bounded authority, honesty) and task prompts |
| HTTP | `backend/app/api/routes_agent.py` | `POST /api/agent/runs`, `GET /api/agent/runs/{id}`, SSE `GET /api/agent/runs/{id}/events`, `GET /api/agent/tools` |

`agent/` imports `app.*`: the SDK runner runs inside the backend process (the tool functions call the
service layer directly, no extra network auth surface). The backend adds `agent/` to `sys.path` only
when `DROID_RUNNER=sdk`; tests get it via `pythonpath = [".", "../agent"]`.

## Tools (read + draft only)

`search_corpus`, `read_document`, `get_spend_summary`, `get_budgets`, `get_forecast` (persists a
citable snapshot), `list_signals`, `record_signal` (backend verifies every quote verbatim against the
stored document version), `draft_proposal` (backend computes before/after, validates arithmetic,
rejects a stale `base_version`; result is `pending_review`).

There is no apply / approve / decide / reject tool. Approval is `POST /api/proposals/{id}/decision`,
which requires `finance_approver`; Droid's role gets 403 `role_forbidden` there, and the attempt is
recorded in decision events. Only finance roles can start a run. Per run, the toolbox caps tool calls
(80), signals (20) and drafts (3); identical signals and identical pending drafts are reused instead of
stacked when an investigation is re-run.

## Runners

**FakeDroidRunner** (`runner_kind=fake`, events `source=fake_runner`, signals `produced_by=droid_fake`).
Not a model: a fixed playbook that does real work through the toolbox.
- `interpret_corpus`: lists and reads all documents; detects supersession from the stored chain and
  checks the text (older research thread says "next period", approved plan says "current planning
  period") and emits `supersession_detected` / `conflict_detected`; records five cited signals:
  research expansion (current, supersedes the thread signal), old research timeline (superseded),
  product timing shift (current; cites v2 and the v1 sentence it replaces), engineering continuation
  (current), marketing brainstorm (informal, no budgeted team). A missing expected passage is reported
  as a warning, never invented.
- `propose_allocation`: reads current signals (interprets first if none for the prioritized team),
  budget, spend, forecast. Addition: covers projected overruns (prioritized team first), splits the
  rest half to the prioritized team and half across other overrun teams: +50k gives research +35k,
  engineering +15k (95k/80k/75k, envelope 250k). Transfer: moves projected headroom (never below
  recorded spend) to overruns: product -> research 25k, product -> engineering 5k (85k/50k/65k, 200k).
  Forecast unavailable: addition goes to the prioritized team with a `forecast_unavailable` warning; a
  transfer is not drafted (recorded spend alone is not evidence of underspend). A stale base version is
  re-read once. The run reports the draft as pending finance review, never as saved.
- `answer_question`: read-only per-team comparison.

**SdkDroidRunner** (`DROID_RUNNER=sdk`). Uses `droid-sdk` (Python, import `droid_sdk`): a `Session` per
run with the in-process `northstar` MCP server, autonomy LOW, built-in skills disabled, an empty temp
directory as cwd, a permission handler that proceeds only for MCP tool actions on `northstar` and
cancels everything else, and an attempt to `restrict_tools` to the discovered Northstar tool ids (it
fails closed if they are not visible). Streamed SDK events map onto the same activity events.
Provider-reported usage is stored as such.

Requirements: `FACTORY_API_KEY` in the backend environment (read by the SDK; never stored or logged),
`pip install 'droid-sdk[mcp]==0.5.0'` into `backend/.venv`, and the `droid` CLI on PATH (or
`DROID_EXECUTABLE`). If any is missing, `POST /api/agent/runs` returns 503 `runner_unavailable` with a
`reason` (`missing_api_key`, `sdk_not_installed`, `droid_cli_missing`, `sdk_api_mismatch`, ...) and the
run is recorded as `unavailable`. There is no silent fallback to the fake runner.

**Status: the SDK runner is unverified.** No Factory key or `droid` CLI was available when it was
written; it follows `backend/docs/droid-sdk-notes.md`. Points to confirm live are marked `verify` in
`sdk_runner.py` (permission-request attribute names, tool-id strings for `restrict_tools`, question
handler response, `tags` type).

## Activity stream

Every run stores ordered events (`agent_run_events`) and a step log (`agent_run_steps`, one row per
tool call that actually ran). `GET /api/agent/runs/{id}/events` streams them as Server-Sent Events,
replaying a finished run or following a running one (`"wait": false` on create) until `run_finished`.
See `backend/README.md` for the frame format.

## Tests

`backend/tests/test_agent.py`: cited quotes match stored content exactly; the old research thread is
superseded by the current-plan signal; outcome A and B drafts are `pending_review` and the budget is
unchanged; Droid's decision attempt is 403 while a finance approver can apply; tool list has no
decide capability and matches the manifest; step log equals tool calls; forecast-unavailable
behaviour; runner output cannot claim unrecorded work; crashes are recorded as failed; SSE order,
resume and background runs; SDK gating (no key, no SDK) and the permission filter.

Regenerate the manifest after changing a tool: `cd backend && .venv/bin/python -m app.agent.tools`.
