"""Droid agent runs: fake runner investigation, citations, supersession, bounded authority, SSE, SDK gating."""

from __future__ import annotations

import importlib
import inspect
import json
import sys

import pytest
from fastapi.testclient import TestClient

from app.agent import tools as tool_defs
from app.agent.runner import AgentRunOutput, AgentToolbox, ToolError
from app.agent.toolbox import BackendToolbox
from app.config import Settings
from app.main import create_app
from budget_helpers import APPROVER, decide

ANALYST = {"X-Actor-Id": "fin-ana", "X-Actor-Role": "finance_analyst"}
INITIAL = {"research": "60000.00", "product": "80000.00", "engineering": "60000.00"}
FORBIDDEN = tool_defs.FORBIDDEN_TOOL_WORDS


def run(client, task_type="propose_allocation", params=None, headers=ANALYST, **extra):
    body = {"task_type": task_type, **({"params": params} if params is not None else {}), **extra}
    return client.post("/api/agent/runs", json=body, headers=headers)


def allocations(client) -> dict[str, str]:
    return {a["team"]: a["amount"] for a in client.get("/api/budget").json()["allocations"]}


def signals_by(client):
    items = client.get("/api/signals").json()["items"]
    return items


def sse(client, run_id, **kw) -> list[dict]:
    headers = kw.pop("headers", {})
    with client.stream("GET", f"/api/agent/runs/{run_id}/events", params=kw, headers=headers) as resp:
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        text = "".join(resp.iter_text())
    events = []
    for block in text.split("\n\n"):
        fields = dict(line.split(": ", 1) for line in block.splitlines() if ": " in line and not line.startswith(":"))
        if "data" in fields and "event" in fields:
            events.append({"id": int(fields["id"]), "event": fields["event"], **json.loads(fields["data"])})
    return events


# ---- interpretation -----------------------------------------------------------------------------


def test_fake_interpret_cites_exact_sources(seeded, client):
    r = run(client, "interpret_corpus")
    assert r.status_code == 201, r.text
    out = r.json()
    assert out["status"] == "succeeded" and out["runner_kind"] == "fake" and out["simulated"] is True
    assert len(out["signal_ids"]) == 12
    for sig in signals_by(client):
        assert sig["produced_by"] == "droid_fake" and sig["agent_run_id"] == out["id"]
        assert sig["citations"]
        for c in sig["citations"]:
            doc = client.get(f"/api/documents/{c['document_id']}").json()
            assert doc["content"][c["char_start"]:c["char_end"]] == c["quote"]
    evidence = [e for e in out["events"] if e["type"] == "evidence_found"]
    assert evidence and all(e["data"]["quote"] for e in evidence)
    team_statuses = sorted(s["status"] for s in signals_by(client) if s["scope"] == "team")
    assert team_statuses == ["current", "current", "current", "informal", "superseded"]
    assert sorted((s["scope"], s["status"]) for s in signals_by(client) if s["scope"] != "team") == (
        [("company", "current")] + [("person", "current")] * 6)


def test_fake_interpret_marks_old_research_thread_superseded(seeded, client):
    out = run(client, "interpret_corpus").json()
    sigs = {(s["team"], s["status"]): s for s in signals_by(client) if s["scope"] == "team"}
    old = sigs[("research", "superseded")]
    new = sigs[("research", "current")]
    assert old["superseded_by_signal_id"] == new["id"]
    assert new["supersedes_signal_ids"] == [old["id"]]
    assert {c["doc_key"] for c in old["citations"]} == {"research-timeline-thread"}
    assert all(c["citation_currency"] == "superseded" for c in old["citations"])
    assert {c["doc_key"] for c in new["citations"]} == {"research-eval-plan"}
    assert all(c["citation_currency"] == "current" for c in new["citations"])
    assert "next period" in old["citations"][0]["quote"] or "next period" in old["citations"][1]["quote"]

    types = [e["type"] for e in out["events"]]
    sup = [e["data"] for e in out["events"] if e["type"] == "supersession_detected"]
    assert {(s["older"]["doc_key"], s["newer"]["doc_key"], s["kind"]) for s in sup} == {
        ("research-timeline-thread", "research-eval-plan", "explicit_cross_document"),
        ("product-launch-plan", "product-launch-plan", "new_version"),
    }
    conflict = next(e["data"] for e in out["events"] if e["type"] == "conflict_detected")
    assert conflict["older"]["doc_key"] == "research-timeline-thread"
    assert conflict["newer"]["doc_key"] == "research-eval-plan"
    assert "next period" in conflict["older_says"] and "current" in conflict["newer_says"]
    assert types.index("supersession_detected") < types.index("signal_recorded")
    # The marketing brainstorm stays informal and is not attached to a budgeted team.
    assert sigs[(None, "informal")]["project"] == "campaigns"


def test_rerunning_interpretation_does_not_duplicate_signals(seeded, client):
    first = run(client, "interpret_corpus").json()
    second = run(client, "interpret_corpus").json()
    assert second["status"] == "succeeded"
    assert len(signals_by(client)) == 12
    assert sorted(second["signal_ids"]) == sorted(first["signal_ids"])


# ---- proposals and bounded authority ------------------------------------------------------------


@pytest.mark.parametrize("params, amount, total, kind", [
    ({"mode": "addition", "amount": "50.00", "prioritize": "research"}, "$50.00", "$200,050.00", "new funding"),
    ({"mode": "transfer", "amount": "40.00", "prioritize": "research", "source_team": "product"},
     "$40.00", "$200,000.00", "redistribution"),
])
def test_proposal_summary_is_plain_finance_language_with_audit_details_retained(seeded, client, params, amount, total, kind):
    out = run(client, params=params).json()
    summary = out["summary"]
    assert amount in summary and total in summary and kind in summary
    assert "finance review" in summary and "Nothing has been applied" in summary
    assert "prop_" not in summary and "pending_review" not in summary and "version" not in summary
    drafted = next(event["data"] for event in out["events"] if event["type"] == "proposal_drafted")
    assert drafted["proposal_id"] == out["proposals"][0]["id"]
    assert drafted["status"] == "pending_review" and drafted["base_version"] == 1
    assert drafted["after"]["total"] == total.removeprefix("$").replace(",", "")


def test_propose_run_leaves_pending_proposal_and_budget_unchanged(seeded, client):
    out = run(client, params={"mode": "addition", "amount": "50000.00", "prioritize": "research"}).json()
    assert out["status"] == "succeeded" and out["applied_changes"] is False
    assert [p["status"] for p in out["proposals"]] == ["pending_review"]
    p = client.get(f"/api/proposals/{out['proposals'][0]['id']}").json()
    assert p["action_type"] == "addition" and p["envelope_increase"] == "50000.00"
    assert p["after"] == {"total": "250000.00",
                          "allocations": {"research": "95000.00", "product": "80000.00", "engineering": "75000.00"}}
    assert p["origin"] == "droid_run" and p["agent_run_id"] == out["id"]
    assert p["requester"]["role"] == "droid_agent"
    kinds = {e["kind"] for e in p["evidence_refs"]}
    assert {"signal", "forecast_snapshot", "spend_summary"} <= kinds
    assert "superseded" in p["rationale"]  # explains what it did not rely on
    assert allocations(client) == INITIAL
    assert client.get("/api/budget").json()["state_version"] == 1
    drafted = next(e for e in out["events"] if e["type"] == "proposal_drafted")["data"]
    assert drafted["applied"] is False and drafted["requires_finance_approval"] is True
    assert "Nothing has been applied" in out["summary"]
    finished = out["events"][-1]
    assert finished["type"] == "run_finished" and finished["data"]["applied_changes"] is False


def test_droid_cannot_apply_its_draft_only_finance_can(seeded, client):
    out = run(client).json()
    pid = out["proposals"][0]["id"]
    droid = {"X-Actor-Id": f"droid:{out['id']}", "X-Actor-Role": "droid_agent"}
    r = decide(client, pid, headers=droid)
    assert r.status_code == 403 and r.json()["error"]["code"] == "role_forbidden"
    assert allocations(client) == INITIAL
    ok = decide(client, pid, headers=APPROVER)
    assert ok.status_code == 201
    assert allocations(client) == {"research": "95000.00", "product": "80000.00", "engineering": "75000.00"}
    # The run now reports the proposal's live status; the run itself still applied nothing.
    again = client.get(f"/api/agent/runs/{out['id']}").json()
    assert again["proposals"][0]["status"] == "applied" and again["applied_changes"] is False


def test_toolbox_has_no_decide_capability(seeded, client):
    names = set(tool_defs.TOOL_NAMES)
    assert names == {"search_corpus", "read_document", "get_spend_summary", "get_budgets", "get_forecast",
                     "list_signals", "list_people", "list_budget_requests", "build_chart_spec", "record_signal", "draft_proposal", "rebase_proposal",
                     "explain_forecast", "compare_forecasts", "preview_forecast_scenario", "request_forecast_refresh"}
    assert {t.name for t in tool_defs.TOOLS if t.kind == "draft"} == {"record_signal", "draft_proposal",
                                                                      "rebase_proposal", "preview_forecast_scenario", "request_forecast_refresh"}
    for container in (BackendToolbox, AgentToolbox):
        public = {n for n, _ in inspect.getmembers(container) if not n.startswith("_")}
        assert not {n for n in public if any(w in n for w in FORBIDDEN)}, container
    assert not [n for n in names if any(w in n for w in FORBIDDEN)]
    served = client.get("/api/agent/tools").json()
    assert [t["name"] for t in served["tools"]] == list(tool_defs.TOOL_NAMES)


def test_tool_manifest_is_generated_from_definitions():
    assert tool_defs.MANIFEST_PATH.read_text(encoding="utf-8") == tool_defs.render_manifest(), \
        "run: .venv/bin/python -m app.agent.tools"


def test_propose_transfer_drafts_outcome_a(seeded, client):
    out = run(client, params={"mode": "transfer", "prioritize": "research"}).json()
    p = client.get(f"/api/proposals/{out['proposals'][0]['id']}").json()
    assert p["action_type"] == "transfer" and p["envelope_increase"] == "0.00"
    assert p["after"] == {"total": "200000.00",
                          "allocations": {"research": "85000.00", "product": "50000.00", "engineering": "65000.00"}}
    assert allocations(client) == INITIAL
    product_signal = [e for e in p["evidence_refs"] if e["kind"] == "signal"]
    assert product_signal, "transfer cites the product timing-shift signal as evidence"


def test_repeat_propose_reuses_identical_pending_draft(seeded, client):
    a = run(client).json()
    b = run(client).json()
    assert a["proposals"][0]["id"] == b["proposals"][0]["id"]
    assert len(client.get("/api/proposals", params={"status": "pending_review"}).json()) == 1


def test_run_steps_match_toolbox_calls(seeded, client):
    out = run(client).json()
    calls = [e["data"] for e in out["events"] if e["type"] == "tool_call"]
    results = [e["data"] for e in out["events"] if e["type"] == "tool_result"]
    assert [s["seq"] for s in out["steps"]] == list(range(1, len(out["steps"]) + 1))
    assert [(s["seq"], s["tool"]) for s in out["steps"]] == [(c["step"], c["tool"]) for c in calls]
    assert len(results) == len(calls)
    assert [e["seq"] for e in out["events"]] == list(range(1, len(out["events"]) + 1))
    tools_used = {s["tool"] for s in out["steps"]}
    assert {"search_corpus", "read_document", "get_budgets", "get_forecast", "draft_proposal"} <= tools_used


def test_propose_with_forecast_unavailable_adds_warning(tmp_path, clock, id_factory):
    app = create_app(Settings(db_path=tmp_path / "u.db", forecast_provider="unavailable"), clock=clock,
                     id_factory=id_factory)
    from app.seed.northstar import seed

    s = app.state.session_factory()
    seed(s, clock=clock, ids=id_factory)
    s.close()
    with TestClient(app) as client:
        out = run(client).json()
        assert out["status"] == "succeeded"
        p = client.get(f"/api/proposals/{out['proposals'][0]['id']}").json()
        assert "forecast_unavailable" in {w["code"] for w in p["warnings"]}
        assert p["lines"] == [{"from_team": None, "to_team": "research", "amount": "50000.00"}]
        # A transfer cannot be justified without projections: nothing is drafted, and it says so.
        t = run(client, params={"mode": "transfer"}).json()
        assert t["status"] == "succeeded" and t["proposals"] == []
        assert "no_proposal_drafted" in {w["code"] for w in t["output"]["warnings"]}
        assert allocations(client) == INITIAL
    app.state.engine.dispose()


# ---- request validation and roles -----------------------------------------------------------------


@pytest.mark.parametrize("headers", [{"X-Actor-Id": "d", "X-Actor-Role": "droid_agent"},
                                     {"X-Actor-Id": "i", "X-Actor-Role": "importer"}])
def test_only_finance_can_start_runs(seeded, client, headers):
    r = run(client, headers=headers)
    assert r.status_code == 403 and r.json()["error"]["code"] == "role_forbidden"


@pytest.mark.parametrize("task_type,params,code", [
    ("propose_allocation", {"prioritize": "marketing"}, "unknown_team"),
    ("propose_allocation", {"amount": "-5.00"}, "non_positive_amount"),
    ("propose_allocation", {"amount": 50000.5}, "invalid_params"),
    ("propose_allocation", {"mode": "shuffle"}, "invalid_params"),
    ("interpret_corpus", {"mode": "addition"}, "unexpected_params"),
])
def test_invalid_run_params_rejected(seeded, client, task_type, params, code):
    r = run(client, task_type, params)
    assert r.status_code == 422
    assert code in {x["code"] for x in r.json()["error"]["details"]["reasons"]}
    assert client.get("/api/agent/runs").json()["count"] == 0


# ---- runner honesty ---------------------------------------------------------------------------------


class _LyingRunner:
    kind = "fake"

    def run(self, task, tools):
        return AgentRunOutput(summary="applied everything", proposal_ids=["prop_invented"], signal_ids=["sig_x"])


class _CrashingRunner:
    kind = "fake"

    def run(self, task, tools):
        tools.get_budgets()
        raise RuntimeError("model went sideways")


def _app_with(tmp_path, clock, id_factory, runner):
    app = create_app(Settings(db_path=tmp_path / "r.db"), clock=clock, id_factory=id_factory, droid_runner=runner)
    from app.seed.northstar import seed

    s = app.state.session_factory()
    seed(s, clock=clock, ids=id_factory)
    s.close()
    return app


def test_run_output_ids_come_from_toolbox_not_runner_claims(tmp_path, clock, id_factory):
    app = _app_with(tmp_path, clock, id_factory, _LyingRunner())
    with TestClient(app) as client:
        out = run(client).json()
        assert out["output"]["proposal_ids"] == [] and out["signal_ids"] == [] and out["proposals"] == []
    app.state.engine.dispose()


def test_runner_crash_is_recorded_as_failed(tmp_path, clock, id_factory):
    app = _app_with(tmp_path, clock, id_factory, _CrashingRunner())
    with TestClient(app) as client:
        out = run(client).json()
        assert out["status"] == "failed" and "model went sideways" in out["error"]
        assert [s["tool"] for s in out["steps"]] == ["get_budgets"]
        assert out["events"][-1]["type"] == "run_finished"
        assert allocations(client) == INITIAL
    app.state.engine.dispose()


def _toolbox(app, run_id="run_t", rebase_target=None):
    from app.db.models import AgentRun
    from app.db.session import transaction

    with transaction(app.state.session_factory) as s:
        s.add(AgentRun(id=run_id, task_type="propose_allocation", input={}, runner_kind="fake", status="running",
                       started_at=app.state.clock.now()))
    return BackendToolbox(session_factory=app.state.session_factory, run_id=run_id, source="fake_runner",
                          runner_kind="fake", clock=app.state.clock, ids=app.state.id_factory,
                          forecast_provider=app.state.forecast_provider, rebase_target=rebase_target)


def test_toolbox_refuses_invented_quote_and_records_failed_step(seeded):
    tb = _toolbox(seeded)
    doc = tb.search_corpus(query="model-evaluation", include_superseded=False)["items"][0]
    with pytest.raises(ToolError) as exc:
        tb.record_signal({"team": "research", "summary": "x", "change_type": "expansion", "status": "current",
                          "uncertainty": "u", "citations": [{"document_id": doc["id"], "quote": "tokens will triple"}]})
    assert exc.value.code == "citation_not_found"
    s = seeded.state.session_factory()
    from app.db.models import AgentRunStep, ContextSignal

    steps = s.query(AgentRunStep).filter_by(run_id="run_t").order_by(AgentRunStep.seq).all()
    assert steps[-1].tool == "record_signal" and steps[-1].result_summary.startswith("error citation_not_found")
    assert s.query(ContextSignal).count() == 0
    s.close()


def test_toolbox_draft_against_old_version_is_refused_as_stale(seeded, client):
    tb = _toolbox(seeded)
    p = tb.draft_proposal({"action_type": "transfer", "base_version": 1, "rationale": "a",
                           "lines": [{"from_team": "product", "to_team": "research", "amount": "1000.00"}]})
    assert decide(client, p["id"], headers=APPROVER).status_code == 201  # budget moves to version 2
    with pytest.raises(ToolError) as exc:
        tb.draft_proposal({"action_type": "addition", "base_version": 1, "rationale": "b",
                           "envelope_increase": "10.00", "lines": [{"to_team": "research", "amount": "10.00"}]})
    assert exc.value.code == "stale_base_version"
    assert exc.value.details["current_version"] == 2


def test_toolbox_caps_writes_per_run(seeded):
    from app.agent import toolbox as tbmod

    tb = _toolbox(seeded)
    for i in range(tbmod.MAX_PROPOSALS):
        tb.draft_proposal({"action_type": "transfer", "base_version": 1, "rationale": "r",
                           "lines": [{"from_team": "product", "to_team": "research", "amount": f"{i + 1}.00"}]})
    with pytest.raises(ToolError) as exc:
        tb.draft_proposal({"action_type": "transfer", "base_version": 1, "rationale": "r",
                           "lines": [{"from_team": "product", "to_team": "research", "amount": "99.00"}]})
    assert exc.value.code == "write_budget_exhausted"


# ---- streaming ------------------------------------------------------------------------------------


def test_sse_replays_events_in_order_and_ends_with_run_finished(seeded, client):
    out = run(client).json()
    events = sse(client, out["id"])
    assert [e["id"] for e in events] == [e["seq"] for e in out["events"]]
    assert events[0]["event"] == "run_started" and events[-1]["event"] == "run_finished"
    kinds = {e["event"] for e in events}
    assert {"tool_call", "tool_result", "evidence_found", "supersession_detected", "signal_recorded",
            "proposal_drafted"} <= kinds
    assert {e["source"] for e in events} == {"backend", "fake_runner"}


def test_sse_resumes_after_last_event_id(seeded, client):
    out = run(client, "interpret_corpus").json()
    total = len(out["events"])
    tail = sse(client, out["id"], headers={"Last-Event-ID": str(total - 2)})
    assert [e["id"] for e in tail] == [total - 1, total]
    assert sse(client, out["id"], after=total) == []


def test_background_run_streams_live_until_finished(seeded, client):
    r = run(client, wait=False)
    assert r.status_code == 202
    run_id = r.json()["id"]
    events = sse(client, run_id)
    assert events[-1]["event"] == "run_finished" and events[-1]["data"]["status"] == "succeeded"
    final = client.get(f"/api/agent/runs/{run_id}").json()
    assert final["status"] == "succeeded" and final["proposals"][0]["status"] == "pending_review"


def test_unknown_run_is_404(client):
    assert client.get("/api/agent/runs/nope").status_code == 404
    assert client.get("/api/agent/runs/nope/events").status_code == 404


# ---- SDK runner gating ----------------------------------------------------------------------------


def test_sdk_mode_without_key_returns_503_runner_unavailable(tmp_path, clock, id_factory):
    app = create_app(Settings(db_path=tmp_path / "s.db", droid_runner="sdk"), clock=clock, id_factory=id_factory)
    from app.seed.northstar import seed

    s = app.state.session_factory()
    seed(s, clock=clock, ids=id_factory)
    s.close()
    with TestClient(app) as client:
        r = run(client)
        assert r.status_code == 503
        err = r.json()["error"]
        assert err["code"] == "runner_unavailable" and err["details"]["reason"] == "missing_api_key"
        rec = client.get(f"/api/agent/runs/{err['details']['run_id']}").json()
        assert rec["status"] == "unavailable" and rec["runner_kind"] == "sdk" and rec["simulated"] is False
        assert client.get("/api/proposals").json() == []
        assert client.get("/api/meta").json()["runner_kind"] == "sdk"
    app.state.engine.dispose()


def test_sdk_mode_with_key_but_no_sdk_installed_is_503(tmp_path, clock, id_factory, monkeypatch):
    if importlib.util.find_spec("droid_sdk") is not None:
        pytest.skip("droid-sdk is installed here")
    monkeypatch.setenv("FACTORY_API_KEY", "placeholder-not-a-key")
    app = create_app(Settings(db_path=tmp_path / "k.db", droid_runner="sdk"), clock=clock, id_factory=id_factory)
    from app.seed.northstar import seed

    s = app.state.session_factory()
    seed(s, clock=clock, ids=id_factory)
    s.close()
    with TestClient(app) as client:
        r = run(client)
        assert r.status_code == 503 and r.json()["error"]["details"]["reason"] == "sdk_not_installed"
    app.state.engine.dispose()


def test_sdk_runner_imports_without_sdk_and_never_loads_it_eagerly():
    mod = importlib.import_module("northstar_droid.sdk_runner")
    if importlib.util.find_spec("droid_sdk") is None:
        assert "droid_sdk" not in sys.modules
    from app.agent.runner import RunnerUnavailable

    with pytest.raises(RunnerUnavailable) as exc:
        mod.SdkDroidRunner.from_env({})
    assert exc.value.reason == "missing_api_key"


def test_sdk_permission_handler_allows_only_northstar_mcp_tools():
    from northstar_droid.sdk_runner import is_northstar_action

    class McpToolAction:
        def __init__(self, server_name, tool_name):
            self.server_name, self.tool_name = server_name, tool_name

    class ExecuteAction:
        command = "rm -rf /"

    class Req:
        def __init__(self, action):
            self.action = action

    assert is_northstar_action(Req(McpToolAction("northstar", "draft_proposal")))
    assert not is_northstar_action(Req(McpToolAction("northstar", "apply_proposal")))
    assert not is_northstar_action(Req(McpToolAction("other", "search_corpus")))
    assert not is_northstar_action(Req(ExecuteAction()))


def test_sdk_tool_functions_wrap_the_same_tools(seeded):
    from northstar_droid.sdk_tools import tool_functions

    tb = _toolbox(seeded)
    fns = tool_functions(tb)
    assert [n for n, _, _ in fns] == list(tool_defs.TOOL_NAMES)
    for _, _, fn in fns:
        hints = inspect.get_annotations(fn)
        assert hints.get("return") in ("str", str)
    by_name = {n: fn for n, _, fn in fns}
    budget = json.loads(by_name["get_budgets"]())
    assert budget["state_version"] == 1
    refused = json.loads(by_name["read_document"]("doc_missing"))
    assert refused["error"]["code"] == "not_found"


# ---- answer_question (Factory milestone 3: units, dates, uncertainty) ----------------------------


def test_answer_question_reports_period_units_and_complete_coverage(seeded, client):
    out = run(client, task_type="answer_question").json()
    assert out["status"] == "succeeded" and out["applied_changes"] is False
    summary = out["summary"]
    assert "2026-P1" in summary and "USD" in summary and "to date" in summary
    assert "research: allocation 60000.00, recorded 45000.00, projected 85000.00" in summary
    assert "Spend coverage is complete" in summary
    assert "simulated" in summary and "not measured spend" in summary
    cov = next(f for f in out["output"]["findings"] if f["type"] == "spend_coverage")
    assert cov["status"] == "complete" and cov["unattributed_spend"] == "0.00"
    lead = summary.split("\n\n", 1)[0]
    assert len(lead) <= 320 and f"{cov['company_total']} USD" in lead
    assert "2026-10-01" in lead and "2026-12-31" in lead and "Spend coverage is complete" in lead
    assert "\n- research: allocation 60000.00" in summary
    assert "research:" not in lead


def test_answer_question_says_when_spend_is_partial_and_unattributed(seeded, client):
    from app.config import BACKEND_ROOT
    raw = (BACKEND_ROOT / "seed" / "planted" / "04_unmapped_provider_project.csv").read_bytes()
    r = client.post("/api/imports", data={"source_kind": "northstar_billing"},
                    files={"file": ("04.csv", raw, "text/csv")},
                    headers={"X-Actor-Id": "importer-1", "X-Actor-Role": "importer"})
    assert r.status_code == 201, r.text
    out = run(client, task_type="answer_question").json()
    summary = out["summary"]
    assert "Spend coverage is partial" in summary
    assert "1800.00 USD from 1 unattributed record(s)" in summary and "96800.00" in summary
    assert "[spend data partial]" in summary
    assert "spend_coverage_incomplete" in {w["code"] for w in out["output"]["warnings"]}
    rows = [f for f in out["output"]["findings"] if f["type"] == "team_comparison"]
    assert {r["coverage_status"] for r in rows} == {"partial"}
    lead = summary.split("\n\n", 1)[0]
    assert len(lead) <= 320 and "96800.00 USD" in lead and "Spend coverage is partial" in lead
    assert "1800.00 USD" in lead and "not assigned to a team" in lead


def test_answer_question_with_forecast_unavailable_is_not_labeled_simulated(tmp_path, clock, id_factory):
    app = create_app(Settings(db_path=tmp_path / "u.db", forecast_provider="unavailable"), clock=clock,
                     id_factory=id_factory)
    from app.seed.northstar import seed

    s = app.state.session_factory()
    seed(s, clock=clock, ids=id_factory)
    s.close()
    with TestClient(app) as client:
        out = run(client, task_type="answer_question").json()
        summary = out["summary"]
        assert "Projections are unavailable" in summary and "projected unavailable" in summary
        assert "simulated unavailable" not in summary and "projections are simulated" not in summary.lower()
        assert "forecast_unavailable" in {w["code"] for w in out["output"]["warnings"]}
    app.state.engine.dispose()


def test_answer_question_states_limitation_for_free_text_it_cannot_interpret(seeded, client):
    out = run(client, task_type="answer_question",
              instruction="What token multiplier should research expect next year?").json()
    assert out["status"] == "succeeded" and out["applied_changes"] is False
    assert "Limitation:" in out["summary"] and "not computed" in out["summary"]
    assert "question_not_interpreted" in {w["code"] for w in out["output"]["warnings"]}
    plain = run(client, task_type="answer_question").json()
    assert "question_not_interpreted" not in {w["code"] for w in plain["output"]["warnings"]}
