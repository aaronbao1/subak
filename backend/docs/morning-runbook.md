# Morning runbook

Everything here runs from the repo root unless a step says `cd backend`. The Factory key lives in
`~/.zshrc`. Start live commands with `zsh -ic '...'` so the key is loaded. Never paste it into a
command, a file or a chat. To check that it is present without printing it:

```bash
zsh -ic '[ -n "$FACTORY_API_KEY" ] && echo set'
zsh -ic 'command -v droid && droid --version'      # expect ~/.local/bin/droid, 0.249.0 or later
```

Live budget: `backend/data/live_runs.log` (gitignored) has one line per live Droid run. Last night
used 13 of the 15-run cap. The eval harness reads this file and keeps 2 runs in reserve. Each run
costs about 14k-73k `factory_credits`. A new day needs a fresh budget: move the old log aside
(`mv backend/data/live_runs.log backend/data/live_runs.2026-10-24.log`). Whether to do that is your
call.

## 0. One-time setup

```bash
python3 -m venv backend/.venv
backend/.venv/bin/pip install -e "backend[dev,sdk]"   # sdk pins droid-sdk[mcp]==0.5.0
cd backend && .venv/bin/pytest -q                      # all green, never calls Factory
```

## 1. Run the backend

Fake runner (no credits, deterministic), on a fresh demo DB:

```bash
cd backend
rm -f data/demo.db
BACKEND_DB_PATH=data/demo.db .venv/bin/python -m app.seed
BACKEND_DB_PATH=data/demo.db BACKEND_ALLOW_RESET=1 .venv/bin/python -m app.main     # http://127.0.0.1:8787
```

Real Droid. This is the same DB and port with the SDK runner. Runs take 20-170 s, so use a long timeout:

```bash
cd backend
zsh -ic 'DROID_RUNNER=sdk DROID_TIMEOUT_S=600 BACKEND_DB_PATH=data/demo.db BACKEND_ALLOW_RESET=1 .venv/bin/python -m app.main'
```

Check that it is the real runner. A missing key, SDK or CLI shows up here as 503 `runner_unavailable`
on the first run, never as a silent fake:

```bash
curl -s http://127.0.0.1:8787/health
curl -s http://127.0.0.1:8787/api/meta | python3 -c 'import json,sys; m=json.load(sys.stdin); print(m["runner_kind"], m["forecast_provider"])'
curl -s http://127.0.0.1:8787/api/agent/tools | python3 -c 'import json,sys; print([t["name"] for t in json.load(sys.stdin)["tools"]])'
```

Reset the demo data between rehearsals (only when `BACKEND_ALLOW_RESET=1` is set):
`curl -s -X POST http://127.0.0.1:8787/api/admin/reset`.

## 2. Demo journey end to end

With the server from step 1 running on a freshly seeded or reset DB, in a second terminal:

```bash
cd backend
.venv/bin/python -m app.demo                    # 3 Droid runs: interpret, propose, recover
.venv/bin/python -m app.demo --skip-interpret   # 2 Droid runs
```

What it does: it shows the runner and the budget (v1, 200k), lists Droid's 10 tools (none can
decide), and then has Droid interpret the corpus (signals, with the old research thread flagged
superseded). Droid then drafts +50k for research as `pending_review`, and the budget does not move.
Droid's role tries to approve and gets **403**. A finance analyst drafts the redistribution and
`fin-alice` applies it (v2). Approving Droid's v1 draft now gets **409 `stale_proposal`**. Droid
recovers it as a new `pending_review` draft on v2 that explains what changed. `fin-alice` applies it
(v3). Exit code 0 means every step behaved.

Two things to expect with the SDK runner:
- Droid may split the 50k differently from the fake runner, which gives 35k/15k. Live runs put all
  50k into research. Both are valid drafts.
- If a propose run ends without a draft, the script stops and prints Droid's summary. This happened
  once live on a transfer.

Each Droid run that the script makes counts as a live run. Append a line to `data/live_runs.log` for
each one. The script does not write the log, because it only talks HTTP.

Follow a run live in another terminal. Start it with `"wait": false` and stream its events:

```bash
H='-H X-Actor-Id:fin-ana -H X-Actor-Role:finance_analyst -H Content-Type:application/json'
curl -s $H -d '{"task_type":"interpret_corpus","wait":false}' http://127.0.0.1:8787/api/agent/runs   # note "id"
curl -N http://127.0.0.1:8787/api/agent/runs/<run id>/events
```

## 3. Evals

```bash
cd backend
.venv/bin/python -m evals.run --runner fake                       # 11 scenarios, seconds, no credits
zsh -ic '.venv/bin/python -m evals.run --runner sdk --scenario stale_recovery --max-live 1'
```

- Results go to `evals/results/<runner>.{json,md}`. A live invocation overwrites `results/sdk.*`, so
  commit or copy last night's file first if you want to keep it.
- The harness runs live only while the log has fewer than `--live-cap` (15) minus `--live-reserve` (2)
  lines. With 13 lines it runs nothing until you add `--live-reserve 0` or start a fresh log.
- The full live set is 6 runs, about 270k credits.
- Current live score: 11 pass, 0 fail, 0 not run (latest result per scenario, see `evals/README.md`).
  Before the final reruns 18-20 it was 8 pass, 2 fail, 1 not run.
  Before the arithmetic scorer change it was 7 pass, 3 fail, 1 not run, after the evening reruns (see `evals/README.md`,
  "Live reruns"). Last night's score was 6 pass, 4 fail, 1 not run under the current scorer. The committed
  `results/sdk.*` still say 7 / 3 / 1: they were scored before the `completed_or_declined` check
  existed, and `forecast_unavailable_warns` passed only because of that. The two runs that ended
  without drafting each had one gate cancellation that could not be examined. See `evals/README.md`.

## 4. Point the frontend at the backend

The Next.js app lives on `origin/main` under `frontend/`. This branch does not contain it. To check
it out without touching this branch, use a separate worktree:

```bash
git fetch origin
git worktree add --detach ../cal-hacks-13-main origin/main
cd ../cal-hacks-13-main/frontend
echo 'NEXT_PUBLIC_API_URL=http://localhost:8787/compat' > .env.local
npm install && npm run dev                                         # http://localhost:3000
```

- The backend serves the app's 15 endpoints under `/compat/api/*`, which is on by default
  (`BACKEND_COMPAT`). CORS already allows any localhost port.
- Check it with `curl -s http://127.0.0.1:8787/compat/api/company`.
- Chat messages become typed Droid runs. Every reply starts with **Read as:**, which says how the
  message was understood. Phrases that work:
  - "what changed in the documents?" runs interpret.
  - "add 50k prioritizing research" runs an addition.
  - "rebalance the budget toward research" runs a transfer.
  - "please refresh the proposal" runs stale-proposal recovery.
  - Anything else runs a read-only answer.
- Apply and Reject in the UI act as the demo approver `dashboard-approver`. Chats run as
  `dashboard-analyst`, so the self-approval rule still holds.
- Under the SDK runner a chat reply waits for the whole run, which takes 20-170 s.
- The context view is empty until the first interpret run.
- Known gaps (included usage, token-only rows, forecast ranges) are listed in
  [`frontend-alignment.md`](frontend-alignment.md).

## 5. The Droid integration in 60 seconds (for judges)

> Finance teams spend most of their time digging through emails, Slack threads and plan docs just to
> figure out what each team actually needs. The math is easy; the digging is the job: an approved
> research plan, an older email thread it replaced, a product launch that slipped. Northstar hands that
> digging to Factory Droid, which reads the company's documents inside our backend. When finance asks "add 50k, prioritize
> research" or "what changed?", the backend starts a real Droid session. That session sees exactly
> ten tools that we implement, seven to read and three to draft, enforced by a `restrict_tools`
> allowlist we verify before every run. A permission gate cancels anything else: edits, shell,
> file creation, network. Droid's tool calls run as generated code, so the gate statically checks every
> script before it runs, and we red-teamed it: no bypasses found. Droid records signals whose quotes the backend checks word for word against
> the stored document, and it drafts proposals whose arithmetic the backend recomputes. Then it
> stops: there is no approve tool, its role gets 403 at the decision endpoint, and a human approves.
> Everything it did is on screen: every tool call, the citations, and the before/after figures,
> streamed live, labeled real or fake, with Factory's credit usage on each run. When the budget
> moves under a pending draft, the approval is refused as stale and Droid re-drafts on the new
> numbers and explains what changed. Live, Droid caught the superseded research thread and never
> claimed to have saved anything. Its latest live run of each of our 11 eval scenarios passes, and we
> publish every earlier failure and what we changed to fix it.

Supporting docs: [`../../agent/README.md`](../../agent/README.md) (design, bounds, live results),
[`droid-live-log.md`](droid-live-log.md) (each live run), [`../evals/results/sdk.md`](../evals/results/sdk.md).
