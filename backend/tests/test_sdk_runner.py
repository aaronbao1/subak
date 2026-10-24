"""SdkDroidRunner against a fake `droid_sdk` stub (tests/fake_droid_sdk.py). Never calls Factory.

Covers the live-verified integration shape: tool ids `northstar___<tool>`, Script-mediated tool calls,
the raw-request permission gate, the startup allowlist check, event mapping and provider usage.
"""

from __future__ import annotations

import sys

import pytest
from fastapi.testclient import TestClient

import fake_droid_sdk
from app.agent import tools as tool_defs
from app.config import Settings
from app.main import create_app
from northstar_droid import sdk_runner
from northstar_droid.sdk_runner import SdkDroidRunner, check_script, decide_permission, usage_dict
from northstar_droid.sdk_tools import NORTHSTAR_TOOL_IDS

ANALYST = {"X-Actor-Id": "fin-ana", "X-Actor-Role": "finance_analyst"}
INITIAL = {"research": "60000.00", "product": "80000.00", "engineering": "60000.00"}
Step = fake_droid_sdk.Step


@pytest.fixture
def fake_sdk(monkeypatch):
    mod = fake_droid_sdk.build()
    monkeypatch.setitem(sys.modules, "droid_sdk", mod)
    monkeypatch.setitem(sys.modules, "droid_sdk.mcp", mod.mcp)
    return mod


@pytest.fixture
def sdk_app(tmp_path, clock, id_factory):
    app = create_app(Settings(db_path=tmp_path / "sdk.db", droid_runner="sdk"), clock=clock, id_factory=id_factory,
                     droid_runner=SdkDroidRunner(executable="/nonexistent/droid", timeout_s=5))
    from app.seed.northstar import seed

    s = app.state.session_factory()
    seed(s, clock=clock, ids=id_factory)
    s.close()
    yield app
    app.state.engine.dispose()


@pytest.fixture
def sdk_client(sdk_app):
    with TestClient(sdk_app) as c:
        yield c


def post_run(client, task_type="propose_allocation", params=None):
    body = {"task_type": task_type, "params": params if params is not None else {}}
    if task_type != "propose_allocation":
        body.pop("params")
    return client.post("/api/agent/runs", json=body, headers=ANALYST)


def allocations(client) -> dict[str, str]:
    return {a["team"]: a["amount"] for a in client.get("/api/budget").json()["allocations"]}


LOAD = 'text(await tools.ToolSearch({query:"select:' + ",".join(sorted(NORTHSTAR_TOOL_IDS)) + '"}));'


def _record_research_signal(call):
    docs = call("search_corpus", query="research", include_superseded=False)["items"]
    doc = call("read_document", document_id=docs[0]["id"])
    quote = doc["content"][:60]
    call("record_signal", summary="Research expansion is the current plan.", change_type="expansion",
         status="current", uncertainty="Timing within the period is not established.", team="research",
         citations=[{"document_id": doc["id"], "quote": quote}])


def _draft_addition(call):
    budget = call("get_budgets")
    call("draft_proposal", action_type="addition", base_version=budget["state_version"],
         rationale="Prioritize research per the current plan.", envelope_increase="50000.00",
         lines=[{"to_team": "research", "amount": "35000.00"}, {"to_team": "engineering", "amount": "15000.00"}])


def _full_scenario():
    return [
        Step(LOAD),
        Step("const d = JSON.parse(await tools.northstar.search_corpus({query: 'research'}));\n"
             "const doc = await tools.northstar.read_document({document_id: d.items[0].id});\n"
             "text(await tools.northstar.record_signal({summary: 'x'}));", _record_research_signal),
        Step("text(await tools.Execute({command: 'curl http://127.0.0.1:8787/api/proposals'}));",
             lambda call: pytest.fail("a refused Script must not run")),
        Step("text(await tools.northstar.get_budgets({}));\ntext(await tools.northstar.draft_proposal({}));",
             _draft_addition),
    ]


# ---- end to end through the HTTP API ------------------------------------------------------------


def test_sdk_run_records_real_tool_steps_and_leaves_budget_unchanged(fake_sdk, sdk_client):
    fake_sdk.SCENARIO = _full_scenario()
    r = post_run(sdk_client, params={"mode": "addition", "amount": "50000.00", "prioritize": "research"})
    assert r.status_code == 201, r.text
    out = r.json()
    assert out["status"] == "succeeded", out["error"]
    assert out["runner_kind"] == "sdk" and out["simulated"] is False and out["applied_changes"] is False
    assert [s["tool"] for s in out["steps"]] == ["search_corpus", "read_document", "record_signal",
                                                  "get_budgets", "draft_proposal"]
    # every Droid-side event carries source droid_sdk; lifecycle events are the backend's
    for e in out["events"]:
        assert e["source"] == ("backend" if e["type"] in ("run_started", "run_finished") else "droid_sdk")
    perms = [e["data"] for e in out["events"] if e["type"] == "permission"]
    assert [p["decision"] for p in perms] == ["proceed_once", "proceed_once", "cancel", "proceed_once"]
    assert "tools.Execute" in perms[2]["tool_uses"][0]["script_excerpt"]
    assert any(e["type"] == "warning" and e["data"]["code"] == "droid_tool_error" for e in out["events"])
    # drafted, not applied
    assert len(out["proposals"]) == 1 and out["proposals"][0]["status"] == "pending_review"
    assert allocations(sdk_client) == INITIAL
    sig = sdk_client.get("/api/signals").json()["items"][0]
    assert sig["produced_by"] == "droid_sdk" and sig["agent_run_id"] == out["id"]
    # provider-reported usage is stored as such
    usage = out["output"]["usage"]
    assert usage["provider_reported"]["factory_credits"] == 10801.0
    assert usage["permission_allowed"] == 3 and usage["permission_cancelled"] == 1
    assert usage["scope"]["allowed_tools"] == sorted(NORTHSTAR_TOOL_IDS | sdk_runner.META_TOOL_IDS)
    finished = out["events"][-1]
    assert finished["type"] == "run_finished" and finished["data"]["usage"]["provider_reported"]["input_tokens"] == 366


def test_sdk_session_is_scoped(fake_sdk, sdk_client):
    fake_sdk.SCENARIO = [Step(LOAD)]
    assert post_run(sdk_client, "interpret_corpus").json()["status"] == "succeeded"
    session = fake_droid_sdk.STATE["session"]
    kw = session.config.kw
    assert kw["autonomy"] == fake_sdk.Autonomy.LOW and kw["disable_builtin_skills"] is True
    assert set(kw["restrict_tools"]) == NORTHSTAR_TOOL_IDS
    assert [s.name for s in kw["mcp_servers"]] == ["northstar"]
    assert sorted(kw["mcp_servers"][0].tools) == sorted(tool_defs.TOOL_NAMES)
    assert all(isinstance(t, fake_sdk.SessionTag) for t in kw["tags"])
    assert "northstar-droid-" in str(session.cwd) and session.runtime.executable == "/nonexistent/droid"
    assert isinstance(session._dispatcher, sdk_runner.PermissionGate)
    assert set(fake_droid_sdk.STATE["list_tools_kw"]["restrict_tools"]) == NORTHSTAR_TOOL_IDS
    prompt = fake_droid_sdk.STATE["prompt"]
    assert "tools.northstar.<tool>" in prompt and "northstar___draft_proposal" in prompt


def test_sdk_refuses_to_run_when_allowlist_does_not_match(fake_sdk, sdk_client):
    def leaky(session, kw):
        return [fake_sdk.ToolInfo(i, True) for i in NORTHSTAR_TOOL_IDS] + [fake_sdk.ToolInfo("Execute", True)]

    fake_sdk.LIST_TOOLS = leaky
    fake_sdk.SCENARIO = [Step(LOAD, lambda call: pytest.fail("must not run"))]
    out = post_run(sdk_client, "interpret_corpus").json()
    assert out["status"] == "unavailable" and "Execute" in out["error"]
    assert any(e["type"] == "error" and e["data"].get("reason") == "tool_allowlist_mismatch" for e in out["events"])
    assert out["steps"] == [] and "prompt" not in fake_droid_sdk.STATE


def test_sdk_refuses_to_run_when_tools_are_not_visible(fake_sdk, sdk_client):
    fake_sdk.LIST_TOOLS = lambda session, kw: [fake_sdk.ToolInfo("Script", True)]
    out = post_run(sdk_client, "interpret_corpus").json()
    assert out["status"] == "unavailable"
    assert any(e["data"].get("reason") == "tools_not_visible" for e in out["events"] if e["type"] == "error")


def test_sdk_refuses_unknown_northstar_tool_ids(fake_sdk, sdk_client):
    fake_sdk.LIST_TOOLS = lambda session, kw: ([fake_sdk.ToolInfo(i, True) for i in NORTHSTAR_TOOL_IDS]
                                               + [fake_sdk.ToolInfo("northstar___apply_proposal", False)])
    out = post_run(sdk_client, "interpret_corpus").json()
    assert out["status"] == "unavailable" and "apply_proposal" in out["error"]


def test_sdk_run_failure_is_recorded_as_failed(fake_sdk, sdk_client):
    fake_sdk.RESULT = fake_sdk.RunFailure(error=fake_sdk.ErrorEvent("model exploded"),
                                          usage=fake_sdk.Usage(1, 2, 0, 0, 0, 5.0))
    out = post_run(sdk_client, "interpret_corpus").json()
    assert out["status"] == "failed" and "error_during_execution" in out["error"] and "model exploded" in out["error"]
    assert "factory_credits" in out["error"]  # credits spent on a failed run are still reported


def test_sdk_questions_are_cancelled(fake_sdk, sdk_client):
    fake_sdk.QUESTION = True
    out = post_run(sdk_client, "interpret_corpus").json()
    assert out["status"] == "succeeded"
    assert fake_droid_sdk.STATE["question_answer"] == {"cancelled": True, "answers": []}
    assert any(e["type"] == "warning" and e["data"]["code"] == "question_cancelled" for e in out["events"])


def test_sdk_typed_mcp_confirmation_is_allowed_only_for_northstar(fake_sdk, sdk_client):
    fake_sdk.SCENARIO = [
        Step("text(await tools.northstar.get_budgets({}))", lambda call: call("get_budgets"),
             extra_tool_uses=[{"toolUse": {"type": "tool_use", "id": "m1", "name": "northstar___get_budgets",
                                           "input": {}},
                               "details": {"type": "mcp_tool", "toolName": "northstar___get_budgets",
                                           "serverName": "northstar", "actualToolName": "get_budgets",
                                           "impactLevel": "low"}}]),
        Step("text(await tools.northstar.get_budgets({}))", lambda call: pytest.fail("must not run"),
             extra_tool_uses=[{"toolUse": {"type": "tool_use", "id": "m2", "name": "other___x", "input": {}},
                               "details": {"type": "mcp_tool", "toolName": "other___x", "serverName": "other",
                                           "impactLevel": "low"}}]),
    ]
    out = post_run(sdk_client, "interpret_corpus").json()
    assert [s["tool"] for s in out["steps"]] == ["get_budgets"]
    assert [e["data"]["decision"] for e in out["events"] if e["type"] == "permission"] == ["proceed_once", "cancel"]


# ---- stale-proposal recovery and prompts ----------------------------------------------------------


def test_sdk_stale_recovery_rebases_into_a_new_pending_draft(fake_sdk, sdk_client):
    from budget_helpers import APPROVER, addition_body, decide, draft, transfer_body

    a = draft(sdk_client, transfer_body()).json()
    b = draft(sdk_client, addition_body()).json()
    assert decide(sdk_client, a["id"], headers=APPROVER).status_code == 201
    assert decide(sdk_client, b["id"], headers=APPROVER).json()["error"]["code"] == "stale_proposal"
    after_a = allocations(sdk_client)
    fake_sdk.SCENARIO = [
        Step(LOAD),
        Step(f"text(await tools.northstar.rebase_proposal({{proposal_id: '{b['id']}', rationale: 'stale'}}));",
             lambda call: call("rebase_proposal", proposal_id=b["id"], rationale="Approval refused as stale.")),
    ]
    r = post_run(sdk_client, params={"stale_proposal_id": b["id"]})
    assert r.status_code == 201, r.text
    out = r.json()
    assert out["status"] == "succeeded" and out["applied_changes"] is False
    assert [s["tool"] for s in out["steps"]] == ["rebase_proposal"]
    assert len(out["proposals"]) == 1 and out["proposals"][0]["status"] == "pending_review"
    new = sdk_client.get(f"/api/proposals/{out['proposals'][0]['id']}").json()
    assert new["rebased_from_proposal_id"] == b["id"] and new["base_version"] == 2
    assert allocations(sdk_client) == after_a
    prompt = fake_droid_sdk.STATE["prompt"]
    assert "Stale-proposal recovery" in prompt and b["id"] in prompt and "northstar___rebase_proposal" in prompt
    assert "{proposal_id}" not in prompt


@pytest.mark.parametrize("task", [
    {"type": "interpret_corpus"},
    {"type": "propose_allocation", "params": {"mode": "transfer", "prioritize": "research"}},
    {"type": "propose_allocation", "params": {"stale_proposal_id": "prop_x"}},
    {"type": "answer_question", "instruction": "What will research spend next year?"},
])
def test_task_prompts_carry_the_honesty_rules(task):
    from app.agent.runner import AgentTask

    prompt = sdk_runner.task_prompt(AgentTask(**task))
    for placeholder in ("{params}", "{proposal_id}", "{tool_ids}", "{{"):
        assert placeholder not in prompt
    low = " ".join(prompt.lower().split())
    assert "never" in low and "limitation" in low
    if task["type"] == "interpret_corpus":
        assert "exactly" in low and "superseded" in low and "informal" in low and "cancelled" in low
        assert "conflicting" in low
    elif task.get("params", {}).get("stale_proposal_id"):
        assert "rebase_proposal" in prompt and "stale_context" in prompt and "pending_review" in prompt
        assert "decisions_since_base" in prompt and "never say it is saved" in low
    elif task["type"] == "propose_allocation":
        assert "addition" in low and "transfer" in low and "envelope total is unchanged" in low
        assert "token prices" in low and "do not claim it is saved" in low
    else:
        assert "never estimate" in low and "changed nothing" in low and "What will research spend" in prompt


def test_system_prompt_bounds_authority_and_forbids_invented_costs():
    system = " ".join(sdk_runner.load_prompt("system").lower().split())
    assert "never invent token volumes" in system and "never say a change is saved" in system
    assert "quote it exactly" in system and "addition" in system and "transfer" in system
    assert "rebase" in system and "limitations" in system


# ---- the gate as a pure function -----------------------------------------------------------------


def _raw(*tool_uses, options=("proceed_once", "cancel")):
    return {"toolUses": list(tool_uses), "options": [{"label": o, "value": o} for o in options]}


def _script(code, ctype="script"):
    return {"toolUse": {"type": "tool_use", "id": "t", "name": "Script", "input": {"script": code}},
            "details": {"type": ctype}}


@pytest.mark.parametrize("code", [
    "text(await tools.northstar.search_corpus({query: ''}))",
    "for (const id of ['a','b']) { text(await tools . northstar . read_document({document_id: id})); }",
    LOAD,
    "const r = JSON.parse(await tools.northstar.get_forecast({})); text(r.availability);",
    "text(await tools.northstar.rebase_proposal({proposal_id: 'prop_1', rationale: 'budget moved'}))",
])
def test_gate_allows_scripts_that_only_call_northstar_tools(code):
    assert check_script(code)[0], check_script(code)
    assert decide_permission(_raw(_script(code)))[0] == "proceed_once"


@pytest.mark.parametrize("code", [
    "text(await tools.Execute({command: 'ls'}))",
    "text(await tools.northstar.apply_proposal({id: 'p1'}))",
    "text(await tools.northstar.decide({id: 'p1'}))",
    "text(await tools['Execute']({command: 'ls'}))",
    "const t = tools; text(await t.Execute({command: 'ls'}))",
    "text(await tools?.northstar?.get_budgets({}))",
    "text(await tools.other.search({}))",
    "await fetch('http://127.0.0.1:8787/api/proposals/p1/decision', {method: 'POST'})",
    "const m = await import('fs'); text(m.readFileSync('/etc/passwd'))",
    "require('child_process').execSync('id')",
    "text(({}).constructor.constructor('return this')())",
    "eval('1+1')",
    "text(globalThis)",
    "text(process.env)",
    "",
    "a" * (sdk_runner.MAX_SCRIPT_CHARS + 1),
])
def test_gate_refuses_scripts_that_reach_anything_else(code):
    assert not check_script(code)[0]
    assert decide_permission(_raw(_script(code)))[0] == "cancel"


@pytest.mark.parametrize("code", [
    # rationale text may use words that are forbidden as code; string contents are not code
    "text(await tools.northstar.draft_proposal({rationale: 'This team needs this, with care; self-serve.'}))",
    "const r = JSON.parse(await tools.northstar.get_budgets({})); text(`total ${r.total} (${r.items[0].team})`);",
    "const r = JSON.parse(await tools.northstar.get_budgets({})); text(Math.round(r.total * 100) / 100 / 2);",
    "// it's a comment\ntext(await tools.northstar.get_budgets({}))",
    "const r = JSON.parse(await tools.northstar.get_budgets({})); text(r['allocations'][0].team);",
])
def test_gate_allows_ordinary_javascript_around_northstar_calls(code):
    assert check_script(code)[0], check_script(code)


@pytest.mark.parametrize("code", [
    # member access to `tools` and routes to the global object
    "await this.tools.Execute({command: 'ls'})",
    "await self.tools.Execute({command: 'ls'})",
    "await window.tools.Execute({})",
    "await x?.tools.Execute({})",
    "const t = this['to' + 'ols']; await t.Execute({})",
    "const g = (function () { return this })(); await g['to' + 'ols'].Execute({})",
    "text(`${this}`)",
    "with (o) { text(1) }",
    "function f() { return arguments.callee }",
    "text(Object.getPrototypeOf(text))",
    "Error.prepareStackTrace = (e, s) => s",
    "setTimeout('1+1')",
    # unicode / hex escapes spell any identifier
    "await \\u0074ools.Execute({command: 'ls'})",
    "\\u0065val('1')",
    "\\u{74}ools.Execute({})",
    "const k = 'to\\x6fls'",
    # computed keys can spell constructor / tools at run time
    "const k = 'constr' + 'uctor'; const F = [][k][k]; F('return 1')()",
    "const k = 'constr' + 'uctor'; const {[k]: A} = []; text(A)",
    "const o = {}; text(o[k])",
    "text(x?.['constructor'])",
    "text(x['tools'])",
    # the lexer refuses what could make it misread where a string ends
    "if (1) /\"/; x[atob('dG9vbHM=')].Execute(); \"/",
    "x = 1 <!-- \"\nfoo()\n\"",
    "const ok = /\"/.test(s)",
    "a // c\u2028this.tools.Execute({})",
    "text('unterminated)",
    "text(await tools.northstar.get_budgets({})",
])
def test_gate_refuses_bypasses_of_the_static_check(code):
    assert not check_script(code)[0], code
    assert decide_permission(_raw(_script(code)))[0] == "cancel"


@pytest.mark.parametrize("ctype", ["edit", "exec", "create", "apply_patch", "ask_user", "sandbox_violation"])
def test_gate_never_allows_dangerous_confirmation_types(ctype):
    assert decide_permission(_raw(_script("text(await tools.northstar.get_budgets({}))", ctype)))[0] == "cancel"


def test_gate_requires_every_tool_use_to_be_allowed_and_proceed_once_offered():
    good = _script("text(await tools.northstar.get_budgets({}))")
    shell = {"toolUse": {"type": "tool_use", "id": "x", "name": "Execute", "input": {"command": "rm -rf /"}},
             "details": {"type": "exec", "fullCommand": "rm -rf /"}}
    assert decide_permission(_raw(good, shell))[0] == "cancel"
    assert decide_permission(_raw(good, options=("proceed_always", "cancel")))[0] == "cancel"
    assert decide_permission(_raw())[0] == "cancel"
    assert decide_permission({"garbage": True})[0] == "cancel"
    assert decide_permission(None)[0] == "cancel"


def test_usage_dict_handles_the_sdk_dataclass():
    u = fake_droid_sdk.Usage(1, 2, 3, 4, 5, 6.5)
    assert usage_dict(u) == {"input_tokens": 1, "output_tokens": 2, "cache_creation_tokens": 3,
                             "cache_read_tokens": 4, "thinking_tokens": 5, "factory_credits": 6.5}
    assert usage_dict(None) is None and usage_dict({"a": 1}) == {"a": 1}


def test_loader_selects_sdk_runner_when_key_sdk_and_cli_present(fake_sdk, tmp_path):
    from app.agent.loader import load_runner
    from app.agent.runner import RunnerUnavailable

    cli = tmp_path / "droid"
    cli.write_text("#!/bin/sh\nexit 1\n")
    cli.chmod(0o755)
    runner = load_runner("sdk", {"FACTORY_API_KEY": "placeholder-not-a-key", "DROID_EXECUTABLE": str(cli),
                                 "DROID_TIMEOUT_S": "30"})
    assert isinstance(runner, SdkDroidRunner) and runner.timeout_s == 30.0 and runner.executable == str(cli)
    with pytest.raises(RunnerUnavailable) as exc:
        load_runner("sdk", {"FACTORY_API_KEY": "placeholder-not-a-key", "DROID_EXECUTABLE": str(cli),
                            "DROID_TIMEOUT_S": "soon"})
    assert exc.value.reason == "bad_config"


def test_sdk_mode_without_cli_is_503_never_fake(fake_sdk, tmp_path, clock, id_factory, monkeypatch):
    monkeypatch.setenv("FACTORY_API_KEY", "placeholder-not-a-key")
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    monkeypatch.delenv("DROID_EXECUTABLE", raising=False)
    app = create_app(Settings(db_path=tmp_path / "n.db", droid_runner="sdk"), clock=clock, id_factory=id_factory)
    from app.seed.northstar import seed

    s = app.state.session_factory()
    seed(s, clock=clock, ids=id_factory)
    s.close()
    with TestClient(app) as client:
        r = post_run(client, "interpret_corpus")
        assert r.status_code == 503
        assert r.json()["error"]["code"] == "runner_unavailable"
        assert r.json()["error"]["details"]["reason"] == "droid_cli_missing"
        assert client.get("/api/signals").json()["items"] == []
    app.state.engine.dispose()


def test_sdk_answer_with_chart_attaches_only_the_chart_the_toolbox_built(fake_sdk, sdk_client):
    fake_sdk.SCENARIO = [
        Step(LOAD),
        Step("text(await tools.northstar.build_chart_spec({kind: 'spend_vs_allocation'}));",
             lambda call: call("build_chart_spec", kind="spend_vs_allocation")),
    ]
    r = sdk_client.post("/api/agent/runs", headers=ANALYST,
                        json={"task_type": "answer_question", "params": {"chart": {"kind": "spend_vs_allocation"}}})
    assert r.status_code == 201, r.text
    out = r.json()
    assert out["status"] == "succeeded", out["error"]
    assert [s["tool"] for s in out["steps"]] == ["build_chart_spec"]
    (spec,) = out["output"]["charts"]
    assert spec["kind"] == "spend_vs_allocation" and spec["spec"]["$schema"].endswith("vega-lite/v5.json")
    assert "build_chart_spec" in fake_droid_sdk.STATE["prompt"]
    assert allocations(sdk_client) == INITIAL
