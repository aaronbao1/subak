"""Select the DroidRunner from settings. No silent fallback from `sdk` to `fake`.

- `DROID_RUNNER=fake` (default): FakeDroidRunner, no credentials, deterministic.
- `DROID_RUNNER=sdk`: `agent/northstar_droid/sdk_runner.py`. Requires `FACTORY_API_KEY` in the
  environment (read by the SDK itself; never stored or logged here), the `droid-sdk` package, and the
  `droid` CLI. If anything is missing this raises `RunnerUnavailable` and the API answers 503
  `runner_unavailable`, so the demo can never misrepresent which runner ran.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping
from pathlib import Path

from app.agent.fake_runner import FakeDroidRunner
from app.agent.runner import DroidRunner, RunnerUnavailable

AGENT_DIR = Path(__file__).resolve().parents[3] / "agent"


def _ensure_agent_path() -> None:
    p = str(AGENT_DIR)
    if AGENT_DIR.is_dir() and p not in sys.path:
        sys.path.append(p)


def load_runner(kind: str, env: Mapping[str, str] | None = None) -> DroidRunner:
    env = os.environ if env is None else env
    if kind == "fake":
        return FakeDroidRunner()
    if kind != "sdk":
        raise RunnerUnavailable(f"unknown runner kind {kind!r}", reason="unknown_runner")
    if not (env.get("FACTORY_API_KEY") or "").strip():
        raise RunnerUnavailable(
            "DROID_RUNNER=sdk but FACTORY_API_KEY is not set in the backend environment; no run was started",
            reason="missing_api_key",
        )
    _ensure_agent_path()
    try:
        from northstar_droid.sdk_runner import SdkDroidRunner
    except ImportError as exc:  # agent/ package missing or broken
        raise RunnerUnavailable(f"SDK runner module could not be imported: {exc}", reason="sdk_runner_missing") from exc
    return SdkDroidRunner.from_env(env)
