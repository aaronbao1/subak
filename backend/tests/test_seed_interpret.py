"""Seed-time interpretation and the seed CLI signal flags (frontend-integration-design.md §7).

No live Droid run: `--live-signals` is only exercised where its preflight refuses."""

from __future__ import annotations

import sys

import fake_droid_sdk
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.config import Settings
from app.db import models as m
from app.main import create_app
from app.seed import __main__ as seed_cli
from app.seed.northstar import seed

COMPAT = "/compat/api"


def _signals(db) -> list[tuple[str, str]]:
    app = create_app(Settings(db_path=db))
    try:
        s = app.state.session_factory()
        try:
            return [(sig.produced_by, sig.scope) for sig in s.scalars(select(m.ContextSignal))]
        finally:
            s.close()
    finally:
        app.state.engine.dispose()


def test_default_seed_records_stand_in_signals_once(tmp_path, monkeypatch, capsys):
    db = tmp_path / "fresh.db"
    monkeypatch.setenv("BACKEND_DB_PATH", str(db))
    assert seed_cli.main([]) == 0
    out = capsys.readouterr().out
    assert "signals: 12 recorded by droid_fake (run run_" in out
    first = _signals(db)
    assert len(first) == 12 and {p for p, _ in first} == {"droid_fake"}
    assert {sc for _, sc in first} == {"team", "person", "company"}

    # idempotent: a reseed neither reseeds nor re-interprets
    assert seed_cli.main([]) == 0
    out = capsys.readouterr().out
    assert "already seeded: " in out and "signals are only interpreted on a fresh seed" in out
    assert len(_signals(db)) == 12

    # the run is an ordinary audited AgentRun initiated by the seed interpreter
    app = create_app(Settings(db_path=db))
    try:
        with TestClient(app) as c:
            runs = c.get("/api/agent/runs").json()["items"]
            assert len(runs) == 1 and runs[0]["task_type"] == "interpret_corpus"
            assert runs[0]["status"] == "succeeded" and runs[0]["runner_kind"] == "fake"
            # context exists on first load, through the frontend contract
            ctx = c.get(f"{COMPAT}/context")
            assert ctx.status_code == 200 and len(ctx.json()) > 0
            assert c.get("/api/budget").json()["state_version"] == 1  # nothing applied
    finally:
        app.state.engine.dispose()


def test_no_signals_flag_seeds_without_interpreting(tmp_path, monkeypatch, capsys):
    db = tmp_path / "quiet.db"
    monkeypatch.setenv("BACKEND_DB_PATH", str(db))
    assert seed_cli.main(["--no-signals"]) == 0
    out = capsys.readouterr().out
    assert "seeded: " in out and "signals:" not in out and "already seeded;" not in out
    assert _signals(db) == []
    assert seed_cli.main(["--no-signals"]) == 0
    assert "signals are only interpreted" not in capsys.readouterr().out


@pytest.mark.parametrize("prepare", ["missing", "empty"])
def test_live_signals_without_key_exits_2_and_leaves_db_untouched(tmp_path, monkeypatch, capsys, prepare):
    db = tmp_path / "live.db"
    if prepare == "empty":
        db.write_bytes(b"")
    monkeypatch.setenv("BACKEND_DB_PATH", str(db))
    assert seed_cli.main(["--live-signals"]) == 2
    err = capsys.readouterr().err
    assert "--live-signals needs the real Droid:" in err and "Nothing was seeded." in err
    if prepare == "missing":
        assert not db.exists()
    else:
        assert db.read_bytes() == b""


def test_live_signals_without_cli_exits_2(tmp_path, monkeypatch, capsys):
    mod = fake_droid_sdk.build()
    monkeypatch.setitem(sys.modules, "droid_sdk", mod)
    monkeypatch.setitem(sys.modules, "droid_sdk.mcp", mod.mcp)
    db = tmp_path / "live.db"
    monkeypatch.setenv("BACKEND_DB_PATH", str(db))
    monkeypatch.setenv("FACTORY_API_KEY", "placeholder-not-a-key")
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    monkeypatch.delenv("DROID_EXECUTABLE", raising=False)
    assert seed_cli.main(["--live-signals"]) == 2
    err = capsys.readouterr().err
    assert "droid" in err and "Nothing was seeded." in err and "placeholder-not-a-key" not in err
    assert not db.exists()


def test_live_signals_on_seeded_db_exits_1(tmp_path, monkeypatch, capsys):
    db = tmp_path / "seeded.db"
    monkeypatch.setenv("BACKEND_DB_PATH", str(db))
    assert seed_cli.main(["--no-signals"]) == 0
    monkeypatch.setattr("app.agent.loader.load_runner", lambda kind, env=None: object())  # preflight passes
    assert seed_cli.main(["--live-signals"]) == 1
    assert "signals are only interpreted on a fresh seed" in capsys.readouterr().out
    assert _signals(db) == []


def test_live_run_failure_is_reported_and_seed_kept(tmp_path, monkeypatch, capsys):
    class Broken:
        kind = "sdk"

        def run(self, task, tools):
            raise RuntimeError("Droid run did not succeed: error_during_execution")

    db = tmp_path / "broken.db"
    monkeypatch.setenv("BACKEND_DB_PATH", str(db))
    monkeypatch.setattr("app.agent.loader.load_runner", lambda kind, env=None: Broken())
    assert seed_cli.main(["--live-signals"]) == 1
    err = capsys.readouterr().err
    assert "ended failed" in err and "the database is seeded without Droid signals" in err
    assert _signals(db) == []


def test_seed_library_default_records_no_signals(session, clock, id_factory):
    assert seed(session, clock=clock, ids=id_factory) is True
    assert session.scalar(select(func.count()).select_from(m.ContextSignal)) == 0


def test_seed_library_interpret_fake(tmp_path, clock, id_factory):
    app = create_app(Settings(db_path=tmp_path / "lib.db"), clock=clock, id_factory=id_factory)
    try:
        s = app.state.session_factory()
        try:
            assert seed(s, clock=clock, ids=id_factory, interpret="fake") is True
            s.expire_all()
            rows = list(s.scalars(select(m.ContextSignal)))
            assert len(rows) == 12 and {r.produced_by for r in rows} == {"droid_fake"}
            assert seed(s, clock=clock, ids=id_factory, interpret="fake") is False
            assert s.scalar(select(func.count()).select_from(m.ContextSignal)) == 12
        finally:
            s.close()
    finally:
        app.state.engine.dispose()
    with pytest.raises(ValueError):
        seed(None, clock=clock, ids=id_factory, interpret="maybe")


def test_admin_reset_restores_stand_in_signals(tmp_path, clock, id_factory):
    app = create_app(Settings(db_path=tmp_path / "r.db", allow_reset=True), clock=clock, id_factory=id_factory)
    try:
        with TestClient(app) as c:
            assert c.post("/api/admin/reset").status_code == 200
            items = c.get("/api/signals").json()["items"]
            assert len(items) == 12 and {i["produced_by"] for i in items} == {"droid_fake"}
            assert c.post("/api/admin/reset").status_code == 200
            assert len(c.get("/api/signals").json()["items"]) == 12
            assert len(c.get(f"{COMPAT}/context").json()) > 0
    finally:
        app.state.engine.dispose()
