# Live Factory Droid runs

This is a record of real `DROID_RUNNER=sdk` runs against Factory. It contains no keys or environment
dumps. Each run also has a line in `backend/data/live_runs.log`, which is gitignored and counts toward
the night's cap of 15 runs.

## Setup (2026-10-24)

| | |
|---|---|
| CLI / SDK | `droid` 0.249.0, `droid-sdk[mcp]` 0.5.0, Python 3.13 |
| Server | `DROID_RUNNER=sdk DROID_TIMEOUT_S=600 BACKEND_PORT=8791 python -m app.main`, started through `zsh -ic` so `FACTORY_API_KEY` comes from `~/.zshrc` |
| Data | fresh SQLite DB seeded with `python -m app.seed` (Northstar seed: budget v1, 6 documents, simulated spend) |
| Calls | `POST /api/agent/runs` as `finance_analyst`, `wait: true` |
| Scope (checked at startup on every run) | `restrict_tools` = the eight `northstar___*` ids. `list_tools()` reported exactly those plus `Script`, `ToolSearch`, `WaitForScript` as allowed. Autonomy LOW, built-in skills disabled, empty temp cwd. The raw-request permission gate was installed as the session's interaction dispatcher |

## Runs

| # | Run id | Task | Result | Steps | Gate allowed / cancelled | Duration | factory_credits |
|---|---|---|---|---|---|---|---|
| 1 | `run_16200471-…` | `interpret_corpus` | succeeded | 33 | 33 / 0 | 94.4 s | 49921.0 |
| 2 | `run_a3801169-…` | `propose_allocation` addition 50000.00, prioritize research | succeeded, but no draft (see below) | 5 | 3 / 0 | 37.2 s | 22083.0 |
| 3 | `run_866ee1ba-…` | same as #2, after the prompt fix | succeeded, 1 pending draft | 5 | 3 / 0 | 23.6 s | 20175.0 |

The credit unit is not documented. Usage comes from the SDK's `RunSuccess.usage` and is stored on
the run as `output.usage.provider_reported`.

### Run 1: interpret_corpus

- Real tool calls, recorded as `agent_run_steps`: `search_corpus`, then `read_document` on all six
  documents (several were re-read), `list_signals`, and 11 `record_signal` calls. These collapsed to 6
  stored signals because the toolbox reuses identical signals.
- Signals (`produced_by=droid_sdk`):
  - Research, current, expansion. Cites the approved research plan, and `supersedes_signal_ids`
    points at the old thread signal.
  - **Research, superseded, timing_shift.** Cites the September email thread, and
    `superseded_by_signal_id` points at the current research signal. **The superseded research
    thread is flagged.**
  - Product, current, timing_shift. Cites v2 plus the v1 passage it replaces.
  - Product, superseded. The v1 launch timeline.
  - Engineering, current, continuation.
  - Marketing brainstorm, informal, no team.
- Every quote passed the backend's verbatim check. A quote that failed would have been refused as a
  tool error, and none were.
- The run's summary names the documents it relied on and the one it did not (the marketing
  brainstorm).

### Run 2: propose_allocation, first attempt

- The steps were `list_signals`, `get_budgets`, `get_spend_summary`, `get_forecast` and
  `draft_proposal`. The draft was refused with `invalid_arguments`, because the spend-summary
  `evidence_refs` item was `{kind, period, as_of}` with no `id`.
- Droid did not retry. It reported the refusal honestly: no proposal is pending, and nothing was
  applied.
- Fix: the `draft_proposal` tool description and `prompts/propose_allocation.md` now spell out the
  ref shape (`{kind, id, version?, note?}`; a spend-summary ref uses the period id). The SDK tool
  prompt also says to correct `invalid_arguments` and retry once.

### Run 3: propose_allocation, after the fix

- Same five steps. `draft_proposal` succeeded and created proposal `prop_db236a98-…`:
  - `pending_review`, addition, `base_version` 1.
  - One line: research +50000.00. Envelope 200000.00 → 250000.00.
  - Evidence refs: `signal:<current research signal>`, `forecast_snapshot:fcs_…`,
    `spend_summary:2026-P1`.
- Droid put all 50k into research. FakeDroidRunner splits it 35k research / 15k engineering. Both
  are valid drafts. The split is the model's judgment, and finance reviews it.
- **Budget unchanged:** `GET /api/budget` showed state_version 1, envelope 200000.00, and research,
  product and engineering at 60000.00 / 80000.00 / 60000.00, before and after.
- The summary says "pending finance review" and "Nothing has been applied or approved."

## What the live runs showed that the fake could not

1. **The gate works on the real wire format.** The `Script` permission request has
   `details.type = "script"`, which is not in SDK 0.5.0's `ToolConfirmationType`. That is why the
   SDK's own parser fails and cancels the call. The inner MCP call then raises a second request with
   `details.type = "mcp_tool"`, `serverName = "northstar"` and `toolName = "northstar___<tool>"`.
   The gate approved both kinds, one at a time, only after checking the script source and the
   server/tool name. No other tool use was ever requested.
2. **Droid writes scripts the static check accepts.** Over 39 permission requests, none was a false
   refusal.
3. **Usage arrives as the `Usage` dataclass.** It is stored as plain JSON, and credits are visible
   per run.

## Bounded authority, as exercised

- The Droid process saw only the eight read and draft tools. The startup check refuses to run if
  `list_tools()` shows anything else allowed besides the three code-mode meta tools.
- No apply, approve, decide or reject tool exists. A script that names one is refused by the gate,
  and the toolbox has no such method.
- The decision endpoint needs `finance_approver`. Droid's role gets 403 there (covered by tests).
- Scripts that use `fetch`, `import`, `require`, `eval`, `Function`, `process`, `globalThis`,
  constructor or prototype access, `tools[...]`, aliasing, or any non-northstar `tools.*` are
  cancelled before they run (unit-tested in `tests/test_sdk_runner.py`).
