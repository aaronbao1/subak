"""Runtime settings read from environment variables (no credentials are ever read here)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

BACKEND_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = BACKEND_ROOT / "data" / "app.db"
DEFAULT_PORT = 8787
# Any port on localhost / 127.0.0.1 (frontend dev servers). No credentials are allowed.
DEFAULT_CORS_ORIGIN_REGEX = r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"

FORECAST_PROVIDERS = ("placeholder", "unavailable")
DROID_RUNNERS = ("fake", "sdk")


class SettingsError(ValueError):
    """Raised when an environment variable holds an unsupported value."""


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    db_path: Path = DEFAULT_DB_PATH
    port: int = DEFAULT_PORT
    cors_origin_regex: str = DEFAULT_CORS_ORIGIN_REGEX
    forecast_provider: str = "placeholder"
    droid_runner: str = "fake"
    allow_reset: bool = False

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.db_path}"

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Settings":
        env = os.environ if env is None else env

        db_path = Path(env.get("BACKEND_DB_PATH") or DEFAULT_DB_PATH).expanduser()

        raw_port = env.get("BACKEND_PORT") or str(DEFAULT_PORT)
        try:
            port = int(raw_port)
        except ValueError as exc:
            raise SettingsError(f"BACKEND_PORT must be an integer, got {raw_port!r}") from exc
        if not 1 <= port <= 65535:
            raise SettingsError(f"BACKEND_PORT out of range: {port}")

        forecast_provider = (env.get("FORECAST_PROVIDER") or "placeholder").strip().lower()
        if forecast_provider not in FORECAST_PROVIDERS:
            raise SettingsError(
                f"FORECAST_PROVIDER must be one of {FORECAST_PROVIDERS}, got {forecast_provider!r}"
            )

        droid_runner = (env.get("DROID_RUNNER") or "fake").strip().lower()
        if droid_runner not in DROID_RUNNERS:
            raise SettingsError(f"DROID_RUNNER must be one of {DROID_RUNNERS}, got {droid_runner!r}")

        return cls(
            db_path=db_path,
            port=port,
            cors_origin_regex=env.get("BACKEND_CORS_ORIGIN_REGEX") or DEFAULT_CORS_ORIGIN_REGEX,
            forecast_provider=forecast_provider,
            droid_runner=droid_runner,
            allow_reset=_truthy(env.get("BACKEND_ALLOW_RESET")),
        )
