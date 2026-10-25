# Local backend runtime

From the repository root, use the root Python environment shared by the numerical engine and backend:

```sh
PYTHONPATH=src:backend:agent .venv/bin/python -m app.launch --check-runtime
PYTHONPATH=src:backend:agent .venv/bin/python -m app.launch --runner sdk
```

The launcher reads the repository's `.env.local` on the server before building settings. An explicit `--env-file /absolute/path/to/file` selects a different file; an explicitly selected file must exist. Existing process environment values take precedence. `--runner fake|sdk` and `--port 8787` override their corresponding settings. The normal launcher uses repository data and the system clock; use the dedicated fixture launcher to preserve its database, data adapter, and fixture clock.

Only backend configuration keys are read: `FACTORY_API_KEY`, the documented `DROID_*` options, `BACKEND_*` settings, and `FORECAST_PROVIDER`, `FORECAST_DEMO`, and `FORECAST_WORKER`. No `NEXT_PUBLIC_*` values are loaded. Values support single-line quotes, comments, and optional `export`; variable interpolation and shell commands are never evaluated. Keep the Factory credential in `FACTORY_API_KEY` in this server-only file. The file is git-ignored. Never use a `NEXT_PUBLIC_` name for it.

`--check-runtime` checks credential presence, the pinned Python SDK API/MCP imports, and `droid --version`. It creates no database, starts no web server or Droid session, and makes no live Factory request. JSON output contains presence and availability only; it does not print credential values or raw CLI diagnostics. Exit status is zero when local prerequisites are present and one otherwise. A successful check does not authenticate the key or establish that the account has credits.

The SDK extra is pinned by `backend/pyproject.toml`:

```sh
uv pip install --python .venv/bin/python 'droid-sdk[mcp]==0.5.0'
```

Install the CLI using the [official Factory CLI instructions](https://docs.factory.com/droid-cli/cli-reference). Set `DROID_EXECUTABLE` to the binary path if it is outside `PATH` and `~/.local/bin/droid`. The current local setup was checked with SDK 0.5.0 and CLI 0.249.0; no live request was performed during this setup.

Data provenance and Droid execution are separate choices. Fixture observations remain simulated when the SDK runner is selected. Selecting `sdk` never silently falls back to the deterministic runner: missing prerequisites remain an explicit unavailable response when a request starts. Conversely, selecting `fake` does not claim a live SDK run occurred. Existing run/event provenance and the internal metadata API retain these facts.

For other server entry points, call `app.runtime.load_backend_env()` before `Settings.from_env()`. This keeps local credential loading out of import-time settings and browser code. `app.runtime.check_droid_runtime()` returns the same offline report for launchers that preserve a fixture database and clock.
