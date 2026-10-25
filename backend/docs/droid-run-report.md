# Droid run report (2026-10-24)

Branch `devin/backend-foundation`, 9 commits since `dc814f3` plus this report. Every change is under
`backend/` and `agent/`. Nothing in `docs/` or `frontend/` was touched, and `main` was not touched.
This is the summary for the night. The details are in the linked docs.

## Final checks (run just before this report)

| Check | Result |
|---|---|
| `cd backend && .venv/bin/pytest -q` | **501 passed, 2 skipped**, 1 warning (Starlette `httpx` deprecation, harmless). Skips: the "SDK not installed" test (it is installed here) and the opt-in upstream drift check |
| `COMPAT_UPSTREAM_CHECK=1 pytest tests/test_compat_contract.py` | 4 passed against live `origin/main` (still `9442db9`) |
| `python -m evals.run --runner fake` | **11 pass, 0 fail, 0 not run** |
| `python -m app.contract.export --check` | contract up to date |
| `python -m app.seed --check-planted` | 12/12 planted checks match the answer key |

## What was built, by module

| Module | What it does now |
|---|---|
| `app/core`, `app/db`, `app/schemas`, `app/services`, `app/api` | Run 1 foundation (see [`overnight-report.md`](overnight-report.md)): Decimal money, versioned budgets, proposals with recomputed arithmetic, finance decisions with stale-version, idempotency and no-self-approval checks, corpus with supersession, quote-verified signals, imports, coverage, overview, SSE run events |
| `app/agent` | `DroidRunner` interface, `BackendToolbox` (read and draft tools only, per-run caps), `FakeDroidRunner`, loader. New tonight: `rebase_proposal` (stale-proposal recovery) and the read-only `build_chart_spec` |
| `agent/northstar_droid` | `SdkDroidRunner`, finished and live-verified: `restrict_tools` allowlist checked at startup, empty temp cwd, built-in skills disabled, a raw-request permission gate that cancels edit, shell, file creation and network, and a Script gate that allows only the backend's own tools. Prompts were tightened (evidence refs, never claim a save). 10 tools: 7 read, 3 draft, none that decide |
| `app/api/routes_charts.py` | `GET /api/charts/{kind}` serves the same chart specs Droid can build |
| `app/compat` | `/compat/api/*`: the frontend's 15 endpoints in its exact TypeScript shapes, plus chat that maps a message to a typed Droid run and starts every reply with "Read as:". Mounted by default (`BACKEND_COMPAT=1`), not part of `contract/openapi.json` |
| `evals/` | 11 scenarios scored against [`../evals/answer_key.md`](../evals/answer_key.md), run with the fake runner or the SDK runner, with live-cap accounting through `data/live_runs.log` |
| `app/demo.py` | Scripted demo journey over HTTP: interpret, propose, 403 for Droid's role, stale 409, rebase, apply |
| Docs | [`droid-sdk-notes.md`](droid-sdk-notes.md), [`droid-live-log.md`](droid-live-log.md), [`frontend-alignment.md`](frontend-alignment.md), [`morning-runbook.md`](morning-runbook.md), [`../../agent/README.md`](../../agent/README.md) |

## Live Droid runs and credits

**13 of the 15-run cap used. 388,909 `factory_credits` in total.** No live run was made in this final
step: the checks above need nothing the fake runner cannot show. From `backend/data/live_runs.log`
(gitignored):

| # | Purpose | Result | factory_credits |
|---|---|---|---|
| 1 | SDK probe: autonomy LOW, call an MCP tool | success | 10,801 |
| 2 | SDK probe: autonomy OFF + `restrict_tools=[mcp]`, then try built-in `ls` | success (`ls` not available) | 4,708 |
| 3 | SDK probe: restrict + disabled Script/WaitForScript/ToolSearch | success | 3,433 |
| 4 | Runner: `interpret_corpus` through the backend API | succeeded | 49,921 |
| 5 | Runner: `propose_allocation` +50k prioritizing research | succeeded | 22,083 |
| 6 | Same, after the evidence_refs prompt fix | succeeded | 20,175 |
| 7 | Runner: stale-proposal recovery (`rebase_proposal`) | succeeded, 1 rebased pending draft | 13,661 |
| 8 | Runner: `answer_question` with a chart (`build_chart_spec`) | succeeded, 1 chart | 14,475 |
| 9 | Eval: interpret | success | 72,548 |
| 10 | Eval: transfer | success, but no draft | 48,468 |
| 11 | Eval: forecast_unavailable | success, but no draft | 55,076 |
| 12 | Eval: unsupported_question | success | 18,280 |
| 13 | Eval: addition_50k | success | 55,280 |

Every live run used the scoped backend tools only. In none of them could Droid approve or apply a
decision: there is no such tool, and its role gets 403 at the decision endpoint.

## Live eval scores vs fake

| Runner | Pass | Fail | Not run |
|---|---|---|---|
| fake (deterministic) | 11 | 0 | 0 |
| sdk, current scorer | **6** | **4** | 1 |
| sdk, as committed in `evals/results/sdk.*` | 7 | 3 | 1 |

The committed `results/sdk.*` were scored before the `completed_or_declined` check existed.
`forecast_unavailable_warns` passed there only because that check was missing, so the honest live
score is 6 / 4 / 1. Live failures:

- **Transfer, 2 scenarios (`addition_vs_transfer`, `arithmetic_transfer_200k`):** Droid read the
  budget, spend and forecast, then ended its turn without drafting.
- **`forecast_unavailable_warns`:** the same early end with no draft.
- **`arithmetic_addition_250k`:** a judgment difference, not a bug. Droid put all +50k into research
  (110k/80k/60k) where the answer key expects 95k/80k/75k. The draft was well-formed and pending
  review.
- **Not run:** `stale_recovery`, to keep 2 runs spare. It was verified live earlier (run 7 above).

Both early-end runs had exactly one permission-gate cancellation each, and the three good runs had
none. The leading guess is that the gate falsely refused the `draft_proposal` call. The run DBs were
in a temp dir and are gone, so this is unconfirmed. Live eval DBs and warning messages are now kept
under `backend/data/evals/sdk/`.

## Frontend `/compat` status

Point the app at `NEXT_PUBLIC_API_URL=http://localhost:8787/compat`. All 15 endpoints answer with
the exact shapes in `frontend/src/lib/contracts/index.ts`. A vendored-TS drift test enforces this,
and it passes against live `origin/main` (`9442db9`). Chat, apply, reject, stale and refresh all
work end to end under the fake runner in tests. Gaps for the frontend owner (full list in
[`frontend-alignment.md` §6](frontend-alignment.md)):

1. Included usage shows $0. The notional value exists only as text in `source`, so a field or UI
   decision is needed.
2. Unpriced token rows are not sent until the UI filters on `unit`.
3. The unattributed pseudo-team has no budget or forecast, so the team grid must handle that.
4. Context is empty until the first interpret chat, and there is no seed option for it.
5. Forecasts have no low/high range, so the band stays empty.
6. One browser acts as both analyst and approver, so separation of duties is nominal without `X-Actor-*`.
7. With the SDK runner, a chat reply blocks for 20-170 s and the contract has no streaming path.
8. `failed` and `pending` proposal statuses are never sent. Use port 8787, not 8000.

## Real, simulated, stubbed

| Status | What |
|---|---|
| **Real** | Factory Droid sessions through `SdkDroidRunner` (13 live runs), tool scoping and the permission gate, authority rules (403 for Droid, no self-approval, stale 409, idempotency), Decimal arithmetic recomputed on the server, verbatim quote checks on signals, the Codex session parser, SSE events, the `/compat` contract shapes |
| **Simulated** | All Northstar spend, budgets and documents (labeled `simulated`), the Northstar billing export format, identity (`X-Actor-*` headers, not auth) |
| **Stubbed** | Forecasts (`PlaceholderForecastProvider` returns fixed projections and is not a model), `FakeDroidRunner` (the default, scripted, labeled `runner_kind: fake`), demo identities `dashboard-analyst` / `dashboard-approver` |

The judge pitch in [`morning-runbook.md` §5](morning-runbook.md) said "passed 7 of 11". This commit
corrects it to 6 of 11, with 4 failed, to match the current scorer.

## First 3 things to do in the morning

1. **Find out why the transfer runs ended early.** Start a fresh live log
   (`mv backend/data/live_runs.log backend/data/live_runs.2026-10-24.log`), then rerun the transfer
   fixture once: `zsh -ic '.venv/bin/python -m evals.run --runner sdk --scenario arithmetic_transfer_200k --max-live 1'`.
   Read the kept DB and `permission_cancelled` detail under `data/evals/sdk/`. If the gate refused
   `draft_proposal`, fix the Script allowlist. This bug costs 3 of the 4 live failures.
2. **Rehearse the demo on the real runner.** Run the SDK server from runbook §1, then
   `python -m app.demo` (3 live runs). Then point the frontend at `/compat` (runbook §4) and send
   "add 50k prioritizing research" from the chat drawer.
3. **Update the pitch score and settle the open frontend gaps.** If step 1 improves the live
   score, update "6 of 11" in the runbook pitch. Go through the 8 `/compat` gaps above with the frontend
   owner, starting with included usage and the empty context view, which a judge would notice first.

## Update: live reruns, 2026-10-24 evening (`../evals/results/rerun-2026-10-24*/`)

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
