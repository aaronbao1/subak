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
| Scope (checked at startup on every run) | `restrict_tools` = the eight `northstar___*` ids (nine from run 4, with `rebase_proposal`). `list_tools()` reported exactly those plus `Script`, `ToolSearch`, `WaitForScript` as allowed. Autonomy LOW, built-in skills disabled, empty temp cwd. The raw-request permission gate was installed as the session's interaction dispatcher |

## Runs

| # | Run id | Task | Result | Steps | Gate allowed / cancelled | Duration | factory_credits |
|---|---|---|---|---|---|---|---|
| 1 | `run_16200471-…` | `interpret_corpus` | succeeded | 33 | 33 / 0 | 94.4 s | 49921.0 |
| 2 | `run_a3801169-…` | `propose_allocation` addition 50000.00, prioritize research | succeeded, but no draft (see below) | 5 | 3 / 0 | 37.2 s | 22083.0 |
| 3 | `run_866ee1ba-…` | same as #2, after the prompt fix | succeeded, 1 pending draft | 5 | 3 / 0 | 23.6 s | 20175.0 |
| 4 | `run_498d1800-…` | `propose_allocation` with `stale_proposal_id` (stale-proposal recovery) | succeeded, 1 rebased pending draft | 1 | 1 / 0 | 22.5 s | 13661.0 |
| 5 | in-process app, temp DB | `answer_question` with `params.chart = {kind: spend_vs_allocation}` | succeeded, 1 chart attached | 3 | 1 / 0 | 18.3 s | 14475.0 |

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

### Run 4: stale-proposal recovery

- Setup over HTTP, with no Droid involved: finance drafted outcome A (a transfer: product → research
  25k, product → engineering 5k) and outcome B (an addition: +50k, research 35k / engineering 15k),
  both on v1. `fin-alice` applied A, and the budget moved to v2. Approving B then returned 409
  `stale_proposal`.
- The run used the nine-tool allowlist, now including `northstar___rebase_proposal`. The startup
  scope check passed. The gate allowed one Script and cancelled none.
- Droid made one `rebase_proposal` call. It created `prop_0624ade6-…`: `pending_review`, an addition,
  `base_version` 2, `rebased_from_proposal_id` = B, requester `droid:<run>`. Its rationale is Droid's
  note followed by the original rationale.
- The summary, taken from `stale_context`:
  - v1 → v2, with a per-team table: base, current, and the result if the draft is approved;
  - the transfer that moved the budget, who applied it, and that the envelope stayed unchanged;
  - the new draft is an addition of new money;
  - the backend's `no_evidence_cited` warning;
  - that research and engineering would get the new money on top of the transfer already applied.
  It said "pending_review", that a fresh finance review is needed and that nothing was applied. It
  ended with limitations: no business need established, and no documents or forecast checked.
- The budget stayed at v2 (85k / 50k / 65k, 200k). B stayed `stale`.

### Run 5: answer_question with a chart

- This run was made in-process (`create_app` + `TestClient`, `DROID_RUNNER=sdk`, `DROID_TIMEOUT_S=300`, fresh
  seeded temp DB) rather than against a running server.
- It used the ten-tool allowlist, which adds `northstar___build_chart_spec`. The startup scope check passed:
  `list_tools()` reported exactly the ten ids plus `Script`, `ToolSearch` and `WaitForScript`.
- The steps were `get_budgets`, `get_spend_summary` and `build_chart_spec` (`spend_vs_allocation`,
  6 rows). The gate allowed one Script and cancelled none.
- `output.charts[0]` is the spec the toolbox built. Its title is "Recorded spend vs allocation by
  team | 2026-P1 | USD | simulated data (fictional Northstar example)".
- The summary:
  - repeated the chart's title and its value-kind labels (`planned` = internal allocation,
    `simulated` = recorded spend);
  - gave the period and the as-of date;
  - ended with limitations.
- No proposal or signal was created, and the budget stayed at v1.

## Live reruns, 2026-10-24 evening (`../evals/results/rerun-2026-10-24*/`)

Three more live runs after the gate fixes (`live_runs.log` 13 -> 16; the cap was raised to 16 for the
last one, with approval). Each run's database and gate decisions are kept, so every cancellation below
has its recorded reason.

| Run | Fixture | Scenario result | Gate | factory_credits | Cause |
|---|---|---|---|---:|---|
| 14 | transfer | `arithmetic_transfer_200k` **fail** (no draft) | 1 cancel | 59,571 | Droid passed its rationale in a `// @input` block; the gate lexed that text as code (apostrophe -> "unterminated string literal"). Fixed in `f1c9e79`. |
| 15 | forecast_unavailable | `forecast_unavailable_warns` **pass** (8/8 checks) | 0 cancels | 63,486 | Fixed by `d78af01` (strings are data, so citing `research-eval-plan` no longer trips `eval`). |
| 16 | transfer | `arithmetic_transfer_200k` **fail** (no draft) | 1 cancel | 40,625 | A Script indexed with a variable (`reads[i].name`, the pattern droid's own Script guide teaches). Still refused on purpose; `c58d58e` adds a bounded retry turn carrying the refusal reason. |

**Current live score: 7 pass, 3 fail, 1 not run** (11 scenarios; `forecast_unavailable_warns` now
passes). The transfer fixes (input blocks, retry turn) are covered by unit tests and a differential
test against droid's own Script splitter, but are **not yet confirmed live**. `addition_vs_transfer`
and `never_claims_saved` were not re-run (they also need the addition fixture).

## What the live runs showed that the fake could not

1. **The gate works on the real wire format.** The `Script` permission request has
   `details.type = "script"`, which is not in SDK 0.5.0's `ToolConfirmationType`. That is why the
   SDK's own parser fails and cancels the call. The inner MCP call then raises a second request with
   `details.type = "mcp_tool"`, `serverName = "northstar"` and `toolName = "northstar___<tool>"`.
   The gate approved both kinds, one at a time, only after checking the script source and the
   server/tool name. In these five product runs no other tool use was requested.
2. **Droid writes scripts the static check accepts.** Over the 41 permission requests of the five
   product runs (33 + 3 + 3 + 1 + 1 in the table above; the earlier figure of 39 counted runs 1-3
   only), none was a false refusal. This covers the product runs only: the later eval runs had two gate
   cancellations (transfer and forecast_unavailable, the two that ended without drafting) whose
   requests were not kept, so a false refusal there cannot be ruled out (`../evals/README.md`).
3. **Usage arrives as the `Usage` dataclass.** It is stored as plain JSON, and credits are visible
   per run.

## Bounded authority, as exercised

- The Droid process saw only the read and draft tools (eight, then nine with `rebase_proposal`, which only creates a new pending draft, then ten with the read-only `build_chart_spec`). The startup check refuses to run if
  `list_tools()` shows anything else allowed besides the three code-mode meta tools.
- No apply, approve, decide or reject tool exists. A script that names one is refused by the gate,
  and the toolbox has no such method.
- The decision endpoint needs `finance_approver`. Droid's role gets 403 there (covered by tests).
- Scripts that use `fetch`, `import`, `require`, `eval`, `Function`, `process`, `globalThis`,
  constructor or prototype access, `tools[...]`, aliasing, or any non-northstar `tools.*` are
  cancelled before they run (unit-tested in `tests/test_sdk_runner.py`).
