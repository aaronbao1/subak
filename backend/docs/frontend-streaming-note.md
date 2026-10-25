# Note for the frontend: showing Droid activity while a chat reply is pending

**Status: a proposal only. No file under `frontend/` was changed for this.** The chat contract stays
as it is: `sendMessage` is one synchronous `POST /api/threads/main/messages` that returns
`[userMessage, assistantMessage]`, and it keeps working unchanged. The code below is something you can
adopt if you want the drawer to show progress instead of a blank wait.

## Why

Under `DROID_RUNNER=sdk` a reply can take tens of seconds (up to `DROID_TIMEOUT_S`, default 120 s).
The backend now has two things that make this shorter and visible:

- `DROID_CHAT_MODEL` / `DROID_CHAT_REASONING_EFFORT` (for example `low`) apply to chat tasks only
  (`answer_question`, `propose_allocation`). Corpus interpretation keeps `DROID_MODEL`.
- A proposal request now starts from the signals already on file (`python -m app.seed` records them
  once), so Droid normally skips re-reading the documents.

Every run also writes a live event log, which the backend already serves as Server-Sent Events.

## What the backend already serves (core API, not `/compat`)

These are on the backend origin (`http://localhost:8787`), not under `/compat/api`. CORS allows
localhost origins and any request header. Shapes are the core API's (snake_case, money as decimal
strings), not the `contracts/index.ts` types, so use them only for the activity feed.

| Call | What it does |
|---|---|
| `GET /api/agent/runs?limit=5` | Newest runs first: `{count, items: AgentRunOut[]}`. Each item has `id`, `task_type`, `status` (`running`, `succeeded`, `failed`, `unavailable`), `started_at`, `events_url`. |
| `GET /api/agent/runs/{id}/events` | SSE. Each message is `id: <seq>`, `event: <type>`, `data: <json>` with `{seq, type, source, data, at}`. It replays stored events, then follows the run and closes after `run_finished`. Resume with `Last-Event-ID` (the browser's `EventSource` does this) or `?after=<seq>`. No headers are needed. |
| `POST /api/agent/runs` with `{"task_type", "instruction", "params", "wait": false}` | Starts a run in the background and answers `202` with the run (`id`, `events_url`). It needs `X-Actor-Id` and `X-Actor-Role: finance_analyst` headers. |

Event `type`s you will see: `run_started`, `runner_config` (model and reasoning effort; no secrets),
`tool_call` (`data.tool`, `data.args`), `tool_result` (`data.tool`, `data.summary`, `data.is_error`),
`assistant_text` (`data.text`), `signal_recorded`, `proposal_drafted`, `permission`, `warning`,
`error`, `run_finished` (`data.status`, `data.summary`). Droid can only read and draft; no event
means a budget changed.

## Option A (recommended): keep `sendMessage` and add an activity feed beside it

This works with no backend change and no change to the `DataClient` contract. While the synchronous
POST is in flight, look up the run it started and stream its events. When the POST resolves, close the
stream and render the reply as today. The thread, the intent parsing and the proposal cards keep
coming from `/compat` exactly as now.

```ts
// e.g. src/lib/data/activity.ts (a suggestion; not added to the repo)
const ORIGIN = (process.env.NEXT_PUBLIC_API_URL ?? "").replace(/\/compat\/?$/, "");

export type ActivityLine = { seq: number; text: string };

function describe(type: string, data: Record<string, unknown>): string | null {
  switch (type) {
    case "tool_call": return `Reading ${String(data.tool).replaceAll("_", " ")}…`;
    case "assistant_text": return String(data.text ?? "").slice(0, 200);
    case "signal_recorded": return "Recorded a context signal";
    case "proposal_drafted": return "Drafted a proposal for review";
    case "warning": return `Note: ${String(data.message ?? data.code ?? "")}`;
    case "error": return `Error: ${String(data.message ?? data.code ?? "")}`;
    default: return null; // run_started, runner_config, tool_result, permission, run_finished
  }
}

/** Follow the newest running chat run that started after `since`. Returns a stop function. */
export function followChatRun(since: Date, onLine: (l: ActivityLine) => void): () => void {
  let source: EventSource | null = null;
  let stopped = false;
  const tryAttach = async (attempt: number) => {
    if (stopped || attempt > 20) return;
    const res = await fetch(`${ORIGIN}/api/agent/runs?limit=5`, { cache: "no-store" }).catch(() => null);
    const runs = res?.ok ? ((await res.json()).items as { id: string; status: string; started_at: string }[]) : [];
    const run = runs.find((r) => r.status === "running" && new Date(r.started_at) >= since);
    if (!run) { setTimeout(() => tryAttach(attempt + 1), 250); return; }
    source = new EventSource(`${ORIGIN}/api/agent/runs/${encodeURIComponent(run.id)}/events`);
    const handler = (ev: MessageEvent) => {
      const e = JSON.parse(ev.data) as { seq: number; type: string; data: Record<string, unknown> };
      const text = describe(e.type, e.data);
      if (text) onLine({ seq: e.seq, text });
      if (e.type === "run_finished") source?.close();
    };
    for (const t of ["tool_call", "assistant_text", "signal_recorded", "proposal_drafted", "warning", "error", "run_finished"]) {
      source.addEventListener(t, handler as EventListener);
    }
  };
  void tryAttach(0);
  return () => { stopped = true; source?.close(); };
}
```

In the drawer's `send` (sketch):

```ts
const since = new Date(Date.now() - 1000); // allow for clock skew between browser and backend
const stop = process.env.NEXT_PUBLIC_API_URL ? followChatRun(since, (l) => setActivity((a) => [...a, l])) : () => {};
try {
  await sendMessage(THREAD, trimmed); // unchanged: the reply still comes from this POST
} finally {
  stop();
  setActivity([]);
}
```

Limits of option A:

- It finds the run by time. With one person using the demo that is fine. If two runs start within
  the same moment, the feed may follow the other one. It never changes what the reply says.
- A message that the backend answers without a run (it asks you to clarify) starts no run, so the feed
  stays empty and stops when the POST returns.
- On the mock client there is no backend, so leave the feed off (the `NEXT_PUBLIC_API_URL` check above).

## Option B: drive the run yourself with `wait: false`

Call `POST /api/agent/runs` with `wait: false` and the actor headers, open `EventSource` on the
returned `events_url` (a path such as `/api/agent/runs/<id>/events`; prefix it with the backend origin), and read the final `GET /api/agent/runs/{id}` when `run_finished` arrives.
This gives the exact run id, but it skips what `/compat` does for chat: it does not store the message
in thread `main`, does not parse the request (amount, mode, team), and returns core shapes instead of
`AssistantMessage`. You would have to rebuild those in the UI, so option A is simpler for the demo.

If you would rather have the exact run id without that work, the backend could add an optional field
(for example the run id on a `202` from the compat chat POST). That is not built, because it would
change the frozen contract. Tell the backend owner if you want it.

## Nothing else changes

- Errors from the chat POST are still `{"error": "<plain sentence>"}`, shown verbatim.
- Approve and Dismiss still go through `/compat/api/proposals/{id}/apply` and `/reject`.
- Dismissing a stale proposal records a rejected decision and leaves the budgets alone.
