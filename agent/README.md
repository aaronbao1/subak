# Northstar Droid agent

Northstar is an AI-spend planning workspace for finance teams. Factory Droid runs **inside the running
backend** as the analyst that reads the company's documents and drafts budget changes. It works only
through tools the backend implements, and it cannot apply anything: every change waits for a human
finance approver.

## For the Factory track judges

**Where Droid runs in the product.** Three product moments start a Droid run (`POST /api/agent/runs`,
or a chat message in the Next.js app through `/compat/api/threads/{id}/messages`):

| Moment | Task | What Droid does |
|---|---|---|
| "What changed?" | `interpret_corpus` | reads plans, emails and launch docs; records cited context signals; flags documents that a newer one supersedes |
| "Add 50k, prioritize research" / "rebalance toward research" | `propose_allocation` (`addition` / `transfer`) | reads signals, budget, spend and forecast; drafts a proposal for finance review |
| An approval refused as stale (409 `stale_proposal`) | `propose_allocation` + `stale_proposal_id` | re-drafts the same lines on the current budget and explains what moved it |
| Any other question, optionally with a chart | `answer_question` | read-only answer with backend-built Vega-Lite chart specs |

**Which tools, and why read + draft only.** Ten tools, all served by the backend's own service layer
under role `droid_agent`: seven read tools (`search_corpus`, `read_document`, `get_spend_summary`,
`get_budgets`, `get_forecast`, `list_signals`, `build_chart_spec`) and three draft tools
(`record_signal`, `draft_proposal`, `rebase_proposal`). Moving money between teams is a finance
decision, so the authority to decide stays with a person. Droid's job is the slow part: reading
everything, connecting facts across documents, and doing arithmetic the backend can check. There is
no apply, approve, decide or reject tool.

**How access is bounded** (each layer is enforced in code, and the first three were checked on live runs):
1. `restrict_tools` allowlist set to exactly the ten `northstar___*` ids; before sending the prompt the
   runner calls `list_tools()` and refuses to run if anything else is allowed (except the three
   code-mode meta tools the SDK cannot remove).
2. A raw-request permission gate approves only `northstar` MCP calls and `Script`s that call nothing but
   `tools.northstar.<known tool>`; edit, shell, file creation, `fetch`/`import`/`eval` and other servers
   are cancelled.
3. Empty temp cwd, Autonomy LOW, built-in skills disabled; the Factory key comes from the environment
   and is never stored or logged.
4. The backend checks every write: quotes must match the stored document version verbatim, proposal
   arithmetic is recomputed, a stale `base_version` is refused, and per-run caps limit tool calls (80),
   signals (20) and drafts (3).
5. Approval is `POST /api/proposals/{id}/decision` and needs `finance_approver`. Droid's role gets 403,
   and the attempt is logged. Requesters cannot approve their own drafts.

**How its activity is shown.** Each run stores ordered events and a step log (one row per tool call
that actually ran). `GET /api/agent/runs/{id}/events` streams them over SSE: `tool_call`,
`tool_result`, `evidence_found`, `supersession_detected`, `signal_recorded`, `proposal_drafted`,
`permission`, `run_finished` and more. In the frontend, each chat reply carries the run's tool calls,
its citations (document, date and the verbatim quote with its character range) and the id of
the drafted proposal, which the app shows with per-team before/after figures.
`runner_kind` and `source` label every run and event as fake or real Droid, and Factory's reported
usage (`factory_credits`, tokens) is stored on the run.

**Real vs fake runner.** `DROID_RUNNER=fake` (default, and every test) is a deterministic scripted
playbook that uses the same toolbox; it is not a model. `DROID_RUNNER=sdk` runs a real Factory Droid
session per run through `droid-sdk` 0.5.0. If the key, SDK or CLI is missing it returns 503
`runner_unavailable` and never quietly falls back to the fake.

**Live results (2026-10-24, `droid` 0.249.0).** 13 live runs in total, 388,909 `factory_credits`
reported by Factory:
- 3 scoping probes (18,942 credits): proved the allowlist and gate on the real wire format.
- 5 product runs through the backend API (120,315 credits; `../backend/docs/droid-live-log.md`):
  interpret (6 cited signals, superseded thread flagged), +50k addition (one `pending_review` draft,
  budget unchanged; the first attempt exposed a ref-shape bug, which was fixed), stale-proposal
  recovery (a rebased draft on v2 that explains the transfer that moved the budget) and a chart answer.
  Across the 41 permission requests of these five product runs (33 + 3 + 3 + 1 + 1 in the run table)
  the gate made no false refusal and nothing outside `northstar` was requested. That claim covers the
  product runs only; the eval runs below had two cancellations that could not be examined.
- 5 eval runs (249,652 credits; `../backend/evals/results/sdk.md`): **6 pass, 4 fail, 1 not run** of
  11 scenarios under the current scorer. The committed `sdk.md` / `sdk.json` say 7 / 3 / 1 because they
  were scored before the `completed_or_declined` check existed; `forecast_unavailable_warns` passed only
  for that reason (`../backend/evals/README.md`). Passes: superseded thread, informal/cancelled
  documents, product timing shift citing v2, no invented token cost, unsupported question limited, never
  claims saved. Failures: Droid put the whole +50k into research instead of the answer key's 35k/15k
  split (a valid draft, but a different judgment); the transfer run ended its turn without drafting (two
  scenarios); and the forecast-unavailable run also ended without drafting. Those two early-ending runs
  are exactly the two eval runs where the gate cancelled a request (`permission_cancelled: 1` each in
  `sdk.json`). The run databases and events are gone, so whether the gate refused the `draft_proposal`
  script (a false refusal) or Droid simply stopped cannot be settled; treat the cancellation as a
  possible cause. The fake runner passes 11/11.
- Credits per run ranged from 13,661 (stale recovery) to 72,548 (interpret in evals). The credit unit
  is not documented by Factory.

How to run all of this: [`../backend/docs/morning-runbook.md`](../backend/docs/morning-runbook.md).

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
| Prompts | `agent/northstar_droid/prompts/` | `system.md` (bounded authority, evidence and honesty rules) and one prompt per task: `interpret_corpus`, `propose_allocation`, `recover_stale_proposal`, `answer_question` |
| HTTP | `backend/app/api/routes_agent.py` | `POST /api/agent/runs`, `GET /api/agent/runs/{id}`, SSE `GET /api/agent/runs/{id}/events`, `GET /api/agent/tools` |

`agent/` imports `app.*`: the SDK runner runs inside the backend process (the tool functions call the
service layer directly, no extra network auth surface). The backend adds `agent/` to `sys.path` only
when `DROID_RUNNER=sdk`; tests get it via `pythonpath = [".", "../agent"]`.

## Tools (read + draft only)

`search_corpus`, `read_document`, `get_spend_summary`, `get_budgets`, `get_forecast` (persists a
citable snapshot), `list_signals`, `build_chart_spec` (read-only Vega-Lite v5 spec from backend data:
spend vs allocation, projection vs allocation, spend by cost category, budget history; labeled with
value kinds and simulated data; persists nothing; specs the toolbox built are attached to the run as
`output.charts[]`), `record_signal` (backend verifies every quote verbatim against the
stored document version), `draft_proposal` (backend computes before/after, validates arithmetic,
rejects a stale `base_version`; result is `pending_review`), `rebase_proposal` (stale-proposal
recovery: re-drafts a stale proposal's same lines on the current budget as a NEW `pending_review`
proposal through the same service as `POST /api/proposals/{id}/rebase`; returns `stale_context`,
i.e. base vs current figures, per-team changes and the decisions applied since; a refusal carries the
same context in `details.stale_context`; shares the per-run draft budget).

There is no apply / approve / decide / reject tool. Approval is `POST /api/proposals/{id}/decision`,
which requires `finance_approver`; Droid's role gets 403 `role_forbidden` there, and the attempt is
recorded in decision events. Only finance roles can start a run. Per run, the toolbox caps tool calls
(80), signals (20) and drafts plus rebases (3); identical signals and identical pending drafts are reused instead of
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
- `propose_allocation` with `params.stale_proposal_id` (stale-proposal recovery, after finance's
  approval was refused with 409 `stale_proposal`): calls `rebase_proposal`, explains the version step,
  per-team changes and the decision(s) that moved the budget, and reports the rebased draft as
  `pending_review` needing a fresh review. Not stale -> `proposal_not_stale`, nothing drafted. Lines no
  longer fit -> the validation reasons plus what changed, nothing drafted.
- `answer_question`: read-only per-team comparison. With `params.chart = {kind, team?, metric?}` it
  also calls `build_chart_spec` and reports the chart's title; a refused chart is a `chart_not_built`
  warning.

**SdkDroidRunner** (`DROID_RUNNER=sdk`, events `source=droid_sdk`, signals `produced_by=droid_sdk`).
Uses `droid-sdk` (Python, import `droid_sdk`). Each run gets its own `Session`, set up like this:
- the in-process `northstar` MCP server, whose tools Droid sees as `northstar___<tool>`;
- `restrict_tools` set to exactly those ten ids;
- Autonomy LOW, built-in skills disabled, and an empty temp directory as cwd.

Before the prompt is sent, the runner calls `list_tools()`. It refuses to run
(`tool_allowlist_mismatch` / `tools_not_visible`) unless the allowed set is exactly our ten ids plus
`Script`, `ToolSearch` and `WaitForScript`. Those three are code-mode meta tools that the allowlist
cannot remove.

Droid calls our tools from a `Script` (`await tools.northstar.<tool>({...})`). SDK 0.5.0 cannot parse
the `Script` permission request, so the runner replaces the session's interaction dispatcher with its
own `PermissionGate`, which decides on the raw request:
- It proceeds once for an `mcp_tool` confirmation on `northstar` for a known tool.
- It proceeds once for a `Script` whose source only uses `tools.ToolSearch` and
  `tools.northstar.<known tool>`, and contains no `fetch`, `import`, `require`, `eval`, `Function`,
  `process`, `globalThis`, constructor/prototype access, `tools[...]` or aliasing.
- Everything else is cancelled: edit, exec, create, apply_patch, other servers. Questions are
  cancelled too.

Every decision is a `permission` event. The startup check guarantees that the Droid process sees no
apply, approve or decide tool, and the gate refuses any script that names one. Provider-reported
usage (`factory_credits` and token counts) is stored on the run as `output.usage.provider_reported`
and repeated in `run_finished`.

Requirements:
- `FACTORY_API_KEY` in the backend environment. The SDK reads it; we never store or log it.
- `pip install -e "backend[sdk]"`, which pins `droid-sdk[mcp]==0.5.0`.
- The `droid` CLI on PATH, or set `DROID_EXECUTABLE`. `DROID_TIMEOUT_S` defaults to 120. Live
  interpret runs took about 95 s, so use 300 or more for the demo.

If any requirement is missing, `POST /api/agent/runs` returns 503 `runner_unavailable` with a `reason`
(`missing_api_key`, `sdk_not_installed`, `droid_cli_missing`, `sdk_api_mismatch`, ...) and the run is
recorded as `unavailable`. There is no silent fallback to the fake runner.

**Status: live-verified on 2026-10-24** with `droid` 0.249.0 and droid-sdk 0.5.0. See
`backend/docs/droid-live-log.md`:
- An interpret run recorded 6 cited signals and flagged the superseded research thread.
- A +50k propose run left one `pending_review` draft, and the budget was unchanged.
- A stale-proposal recovery run rebased the refused addition into a new `pending_review` draft on
  version 2, explained the transfer that moved the budget, and left the budget unchanged.
- Tests use a fake `droid_sdk` stub (`backend/tests/fake_droid_sdk.py`) and never call Factory.

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

`backend/tests/test_sdk_runner.py` covers the SDK runner against the fake SDK stub:
- end-to-end runs through the API (real toolbox steps, permission events, usage, budget unchanged);
- session scoping;
- refusal when the allowlist does not match;
- failure and question handling;
- the gate's allow and refuse cases for scripts and confirmation types.

Regenerate the manifest after changing a tool: `cd backend && .venv/bin/python -m app.agent.tools`.
