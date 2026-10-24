"""Shared fixtures: every test gets a fresh temp SQLite file, a frozen clock, sequential ids."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import Settings
from app.core.clock import FrozenClock, SequentialIdFactory
from app.main import create_app

FROZEN_AT = datetime(2026, 10, 24, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests never inherit a developer's runtime env (e.g. DROID_RUNNER=sdk or a real DB path)."""
    for name in (
        "BACKEND_DB_PATH",
        "BACKEND_PORT",
        "BACKEND_CORS_ORIGIN_REGEX",
        "BACKEND_ALLOW_RESET",
        "FORECAST_PROVIDER",
        "DROID_RUNNER",
        "FACTORY_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "test.db"


@pytest.fixture
def settings(db_path: Path) -> Settings:
    return Settings(db_path=db_path, droid_runner="fake", forecast_provider="placeholder")


@pytest.fixture
def clock() -> FrozenClock:
    return FrozenClock(FROZEN_AT)


@pytest.fixture
def id_factory() -> SequentialIdFactory:
    return SequentialIdFactory()


@pytest.fixture
def app(settings: Settings, clock: FrozenClock, id_factory: SequentialIdFactory):
    application = create_app(settings, clock=clock, id_factory=id_factory)
    yield application
    application.state.engine.dispose()


@pytest.fixture
def client(app) -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c


@pytest.fixture
def session(app) -> Iterator[Session]:
    s = app.state.session_factory()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


@pytest.fixture
def seeded(app):
    """The full Northstar seed (period, teams, mappings, budget v1, spend, corpus)."""
    from app.seed.northstar import seed

    s = app.state.session_factory()
    try:
        assert seed(s, clock=app.state.clock, ids=app.state.id_factory)
    finally:
        s.close()
    return app
