"""Chat speed settings and signal reuse in SdkDroidRunner (frontend-integration-design.md §8).

Runs against the fake `droid_sdk` (tests/fake_droid_sdk.py); never calls Factory."""

from __future__ import annotations

import sys

import pytest
from fastapi.testclient import TestClient

import fake_droid_sdk
from app.agent.fake_runner import FakeDroidRunner
from app.agent.loader import load_runner
from app.agent.runner import AgentTask, RunnerUnavailable
from app.config import Settings
from app.main import create_app
from app.seed.interpret import interpret_at_seed
from app.seed.northstar import seed
from northstar_droid import sdk_runner
from northstar_droid.sdk_runner import CHAT_TASKS, REUSE_SIGNALS_NOTE, SdkDroidRunner
from northstar_droid.sdk_tools import NORTHSTAR_TOOL_IDS

ANALYST = {"X-Actor-Id": "fin-ana", "X-Actor-Role": "finance_analyst"}
LOAD = 'text(await tools.ToolSearch({query:"select:' + ",".join(sorted(NORTHSTAR_TOOL_IDS)) + '"}));'
INTERPRET_MARKER = "Interpretation steps, if needed:"


@pytest.fixture
def fake_sdk(monkeypatch):
    mod = fake_droid_sdk.build()
    monkeypatch.setitem(sys.modules, "droid_sdk", mod)
    monkeypatch.setitem(sys.modules, "droid_sdk.mcp", mod.mcp)
    return mod


@pytest.fixture
def cli(tmp_path):
    exe = tmp_path / "droid"
    exe.write_text("#!/bin/sh\nexit 1\n")
    exe.chmod(0o755)
    return str(exe)


def _env(cli, **extra):
    return {"FACTORY_API_KEY": "placeholder-not-a-key", "DROID_EXECUTABLE": cli, **extra}


def _app(tmp_path, clock, id_factory, runner, *, interpreted: bool):
    app = create_app(Settings(db_path=tmp_path / "chat.db", droid_runner="sdk"), clock=clock, id_factory=id_factory,
                     droid_runner=runner)
    s = app.state.session_factory()
    seed(s, clock=clock, ids=id_factory)
    s.close()
    if interpreted:
        interpret_at_seed(app.state.session_factory, settings=app.state.settings, clock=clock, ids=id_factory,
                          mode="fake")
    return app


def _run(app, task_type, params=None):
    body = {"task_type": task_type}
    if params is not None:
        body["params"] = params
    with TestClient(app) as c:
        return c.post("/api/agent/runs", json=body, headers=ANALYST).json()


# ---- configuration -----------------------------------------------------------------------------


def test_from_env_reads_chat_settings(fake_sdk, cli):
    r = load_runner("sdk", _env(cli, DROID_MODEL="base-model", DROID_CHAT_MODEL=" chat-model ",
                                DROID_CHAT_REASONING_EFFORT=" LOW "))
    assert isinstance(r, SdkDroidRunner)
    assert (r.model, r.chat_model, r.chat_reasoning_effort) == ("base-model", "chat-model", "low")
    plain = load_runner("sdk", _env(cli))
    assert plain.chat_model is None and plain.chat_reasoning_effort is None


def test_bad_reasoning_effort_is_bad_config(fake_sdk, cli):
    with pytest.raises(RunnerUnavailable) as exc:
        load_runner("sdk", _env(cli, DROID_CHAT_REASONING_EFFORT="turbo"))
    assert exc.value.reason == "bad_config"
    assert "turbo" in str(exc.value) and "xhigh" in str(exc.value) and "placeholder" not in str(exc.value)


def test_effort_values_match_the_sdk_enums():
    assert tuple(e.value for e in fake_droid_sdk.ReasoningEffort) == sdk_runner.REASONING_EFFORTS
    try:
        import importlib

        real = importlib.import_module("droid_sdk")
    except ImportError:  # pragma: no cover - the SDK is optional
        return
    if hasattr(real, "ReasoningEffort") and not hasattr(real, "SCENARIO"):
        assert tuple(e.value for e in real.ReasoningEffort) == sdk_runner.REASONING_EFFORTS


def test_settings_for_applies_chat_overrides_only_to_chat_tasks():
    r = SdkDroidRunner(executable="/x", model="base", chat_model="fast", chat_reasoning_effort="low")
    assert CHAT_TASKS == {"answer_question", "propose_allocation"}
    assert r.settings_for(AgentTask(type="answer_question")) == ("fast", "low")
    assert r.settings_for(AgentTask(type="propose_allocation", params={"stale_proposal_id": "p"})) == ("fast", "low")
    assert r.settings_for(AgentTask(type="interpret_corpus")) == ("base", None)
    only_effort = SdkDroidRunner(executable="/x", model="base", chat_reasoning_effort="minimal")
    assert only_effort.settings_for(AgentTask(type="answer_question")) == ("base", "minimal")


# ---- what reaches droid_sdk.Session --------------------------------------------------------------


@pytest.mark.parametrize("task_type,params,model,effort", [
    ("answer_question", None, "fast", "low"),
    ("propose_allocation", {"mode": "addition", "amount": "50000.00", "prioritize": "research"}, "fast", "low"),
    ("interpret_corpus", None, "base", None),
])
def test_session_gets_chat_model_and_effort(fake_sdk, tmp_path, clock, id_factory, task_type, params, model, effort):
    fake_sdk.SCENARIO = [fake_droid_sdk.Step(LOAD)]
    runner = SdkDroidRunner(executable="/nonexistent/droid", timeout_s=5, model="base", chat_model="fast",
                            chat_reasoning_effort="low")
    app = _app(tmp_path, clock, id_factory, runner, interpreted=False)
    try:
        out = _run(app, task_type, params)
        assert out["status"] == "succeeded", out["error"]
        session = fake_droid_sdk.STATE["session"]
        assert session.model == model
        if effort is None:
            assert session.reasoning_effort is None
        else:
            assert session.reasoning_effort == fake_droid_sdk.ReasoningEffort(effort)
        cfg = [e for e in out["events"] if e["type"] == "runner_config"]
        assert len(cfg) == 1 and cfg[0]["source"] == "backend"
        assert cfg[0]["data"] == {"task_type": task_type, "model": model, "reasoning_effort": effort or "default"}
    finally:
        app.state.engine.dispose()


def test_session_without_overrides_passes_no_effort_kwarg(fake_sdk, tmp_path, clock, id_factory, monkeypatch):
    seen: dict = {}
    original = fake_sdk.Session

    class OldSession(original):  # an SDK without the reasoning_effort kwarg
        def __init__(self, *, cwd=None, model=None, config=None, interactions=None, runtime=None):
            seen["model"] = model
            super().__init__(cwd=cwd, model=model, config=config, interactions=interactions, runtime=runtime)

    monkeypatch.setattr(fake_sdk, "Session", OldSession)
    fake_sdk.SCENARIO = [fake_droid_sdk.Step(LOAD)]
    app = _app(tmp_path, clock, id_factory, SdkDroidRunner(executable="/nonexistent/droid", timeout_s=5),
               interpreted=False)
    try:
        out = _run(app, "answer_question")
        assert out["status"] == "succeeded", out["error"]
        assert seen == {"model": None}
        cfg = next(e for e in out["events"] if e["type"] == "runner_config")
        assert cfg["data"]["model"] == "default" and cfg["data"]["reasoning_effort"] == "default"
    finally:
        app.state.engine.dispose()


# ---- signal reuse in propose_allocation ------------------------------------------------------------


PROPOSE = {"mode": "addition", "amount": "50000.00", "prioritize": "research"}


def test_propose_prompt_reuses_current_signals(fake_sdk, tmp_path, clock, id_factory):
    fake_sdk.SCENARIO = [fake_droid_sdk.Step(LOAD)]
    app = _app(tmp_path, clock, id_factory, SdkDroidRunner(executable="/nonexistent/droid", timeout_s=5),
               interpreted=True)
    try:
        out = _run(app, "propose_allocation", PROPOSE)
        assert out["status"] == "succeeded", out["error"]
        assert [s["tool"] for s in out["steps"]] == ["list_signals"]
        assert out["steps"][0]["args"] == {"status": "current", "team": None}
        prompt = fake_droid_sdk.STATE["prompt"]
        assert INTERPRET_MARKER not in prompt and REUSE_SIGNALS_NOTE in prompt
        with TestClient(app) as c:
            current = c.get("/api/signals", params={"status": "current"}).json()["items"]
        assert current
        for sig in current:
            assert f"| {sig['id']} |" in prompt
        assert "research-eval-plan v" in prompt and "(company)" in prompt
    finally:
        app.state.engine.dispose()


def test_propose_prompt_includes_interpretation_without_current_signals(fake_sdk, tmp_path, clock, id_factory):
    fake_sdk.SCENARIO = [fake_droid_sdk.Step(LOAD)]
    app = _app(tmp_path, clock, id_factory, SdkDroidRunner(executable="/nonexistent/droid", timeout_s=5),
               interpreted=False)
    try:
        out = _run(app, "propose_allocation", PROPOSE)
        assert [s["tool"] for s in out["steps"]] == ["list_signals"]
        prompt = fake_droid_sdk.STATE["prompt"]
        assert INTERPRET_MARKER in prompt and REUSE_SIGNALS_NOTE not in prompt
    finally:
        app.state.engine.dispose()


def test_task_prompt_needs_a_signal_for_the_prioritized_team():
    task = AgentTask(type="propose_allocation", params={"mode": "transfer", "prioritize": "product"})
    research_only = [{"id": "sig_1", "team": "research", "scope": "team", "signal_kind": "steady", "title": "t",
                      "citations": [{"doc_key": "k", "version": 1, "quote": "a | b"}]}]
    prompt = sdk_runner.task_prompt(task, research_only)
    assert "| sig_1 | research |" in prompt and INTERPRET_MARKER in prompt and REUSE_SIGNALS_NOTE not in prompt
    product = research_only + [{"id": "sig_2", "team": "product", "scope": "person", "signal_kind": "tool_change",
                                "title": "Tool | switch", "citations": []}]
    prompt = sdk_runner.task_prompt(task, product)
    assert "| sig_2 | product | person | tool_change | Tool / switch |" in prompt
    assert INTERPRET_MARKER not in prompt and REUSE_SIGNALS_NOTE in prompt
    assert sdk_runner.task_prompt(task) == sdk_runner.task_prompt(task, [])


def test_stale_recovery_and_other_tasks_do_not_pre_read(fake_sdk, tmp_path, clock, id_factory):
    fake_sdk.SCENARIO = [fake_droid_sdk.Step(LOAD)]
    app = _app(tmp_path, clock, id_factory, SdkDroidRunner(executable="/nonexistent/droid", timeout_s=5),
               interpreted=True)
    try:
        for task_type in ("answer_question", "interpret_corpus"):
            out = _run(app, task_type)
            assert out["status"] == "succeeded" and out["steps"] == []
    finally:
        app.state.engine.dispose()


def test_fake_runner_propose_after_interpret_makes_no_reads(tmp_path, clock, id_factory):
    app = create_app(Settings(db_path=tmp_path / "f.db"), clock=clock, id_factory=id_factory,
                     droid_runner=FakeDroidRunner())
    s = app.state.session_factory()
    seed(s, clock=clock, ids=id_factory, interpret="fake")
    s.close()
    try:
        out = _run(app, "propose_allocation", PROPOSE)
        tools = [st["tool"] for st in out["steps"]]
        assert "search_corpus" not in tools and "read_document" not in tools and tools[0] == "list_signals"
        assert out["proposals"] and out["proposals"][0]["status"] == "pending_review"
    finally:
        app.state.engine.dispose()
