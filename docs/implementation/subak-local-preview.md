# Subak local preview

Run commands from `/Users/aaronbao/Developer/calhacks/.worktrees/forecast-integration` using its root `.venv`. The complete company fixture lives at these paths:

```sh
SUBAK_SOURCE=.coordination/subac-current-20261025/evidence/full-company/source-complete
SUBAK_PREPARED=.coordination/subac-current-20261025/evidence/full-company/prepared-complete
```

The prepared directory contains `app.db`, immutable forecast publications, and `runtime.json` with the fixture clock. Preserve these files when switching runners. The frontend uses port **3001**, connected to the backend at **8789/compat**.

Check the installed Factory prerequisites without starting a server or making a live request:

```sh
PYTHONPATH=src:backend:agent .venv/bin/python -m app.launch \
  --env-file .env.local --check-runtime
```

The current setup has SDK **0.5.0** and CLI **0.249.0**. A blank `FACTORY_API_KEY` produces `missing_api_key`, `ready: false`, and exit status **1**. Put the key in the existing server-only `FACTORY_API_KEY` entry in `.env.local`; never use a `NEXT_PUBLIC_` variable or commit the file. Existing shell environment values take precedence over the file. Repeat the check after editing. A passing result confirms local prerequisites, not authentication, available credits, or live connectivity.

Stop the existing backend process, then restart it on the same source and prepared database with the SDK runner:

```sh
.venv/bin/python datagen/company_preview.py serve \
  --source "$SUBAK_SOURCE" --directory "$SUBAK_PREPARED" \
  --env-file .env.local --runner sdk --port 8789
```

Only the backend needs restarting after a credential change. To use the deterministic runner, substitute `--runner fake`; the database, fixture clock, and saved forecasts remain the same. The generated data retains its synthetic provenance with either runner. SDK mode never silently falls back when a live request is unavailable.

For fresh generation, preparation, source-backed update intake, and verification, follow the [complete company runbook](../../.coordination/subac-current-20261025/evidence/full-company/RUNBOOK.md). Generation requires `PYTHONHASHSEED=0` and `--no-holdout --complete-as-of-day`. Prepare a fresh output directory; do not overwrite the existing database.

## Verified local flow

The local SDK run was verified with the configured key on October 25, 2026. Spend analysis returned the exact company forecast, and a $1,000 Freight-to-Customer Support Automation transfer produced a pending review proposal with the $430,000 company budget unchanged. Neither check applied a budget change. The successful live runs took about 79–81 seconds; allow time for Factory to finish.

If newly recorded source evidence makes a proposal stale, use **Update forecast**, wait for it to finish, then request the proposal again. The assistant reuses current signals and never applies its own proposal.

The current preview is a production build. To restart the frontend after stopping its existing process:

```sh
cd frontend
npm run start -- --hostname 127.0.0.1 --port 3001
```

The ignored `frontend/.env.local` sets `NEXT_PUBLIC_API_URL=http://127.0.0.1:8789/compat`. Keep this public backend address configured at build time so the preview uses the complete company database. After frontend source changes, run `npm run build` before restarting. Open [Subak](http://127.0.0.1:3001/overview); the original landing page remains at `/`.
