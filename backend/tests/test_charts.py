"""Chart specs: Vega-Lite v5 built only from backend data, labeled, read-only; Droid tool + HTTP route."""

from __future__ import annotations

import json
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.agent.runner import ToolError
from app.config import Settings
from app.contract.export import INCOMPLETE_CSV
from app.db.models import AgentRun, ForecastSnapshot, Proposal
from app.main import create_app
from app.schemas.charts import CHART_KINDS, ChartSpecOut
from budget_helpers import APPROVER, IMPORTER_H, decide, draft, transfer_body
from test_agent import _toolbox

ANALYST = {"X-Actor-Id": "fin-ana", "X-Actor-Role": "finance_analyst"}
VEGA = "https://vega.github.io/schema/vega-lite/v5.json"


def chart(client, kind, **params):
    r = client.get(f"/api/charts/{kind}", params=params)
    assert r.status_code == 200, r.text
    body = r.json()
    ChartSpecOut.model_validate(body)
    return body


def rows(body, **match):
    return [v for v in body["spec"]["data"]["values"] if all(v.get(k) == x for k, x in match.items())]


def counts(app) -> tuple[int, int, int]:
    s = app.state.session_factory()
    try:
        return tuple(s.scalar(select(func.count()).select_from(m)) for m in (ForecastSnapshot, Proposal, AgentRun))
    finally:
        s.close()


@pytest.mark.parametrize("kind", CHART_KINDS)
def test_every_kind_is_a_labeled_vega_lite_v5_spec_with_inline_data(seeded, client, kind):
    body = chart(client, kind)
    spec = body["spec"]
    assert spec["$schema"] == VEGA
    assert body["row_count"] == len(spec["data"]["values"]) > 0
    # money stays a decimal string; the spec converts it for plotting
    for v in spec["data"]["values"]:
        if "amount" in v:
            assert isinstance(v["amount"], str) and Decimal(v["amount"]).as_tuple().exponent == -2
    if body["metric"] != "record_count":
        assert {"calculate": "toNumber(datum.amount)", "as": "value"} in spec["transform"]
    # value kinds and the simulated label are in title, subtitle and description
    assert "simulated" in spec["title"]["text"] and body["title"] == spec["title"]["text"]
    assert "2026-P1" in spec["title"]["text"] and "USD" in spec["title"]["text"]
    assert any("value kinds:" in line and "planned" in line for line in spec["title"]["subtitle"])
    for k in body["value_kinds"]:
        assert k in spec["description"]
    assert spec["usermeta"]["northstar"]["value_kinds"] == body["value_kinds"]
    assert body["data_labels"] == {"simulated": True, "real_sample": False}
    assert all(src.startswith("/api/") for src in body["sources"])


def test_chart_routes_write_nothing(seeded, client):
    before = counts(seeded)
    for kind in CHART_KINDS:
        chart(client, kind)
    chart(client, "projection_vs_allocation", metric="gap")
    assert counts(seeded) == before  # no forecast snapshot, proposal or run


def test_chart_kinds_listing(client):
    body = client.get("/api/charts").json()
    assert body["vega_lite_schema"] == VEGA
    assert [k["kind"] for k in body["kinds"]] == list(CHART_KINDS)
    assert all(k["default_metric"] == k["metrics"][0] for k in body["kinds"])


def test_spend_vs_allocation_matches_budget_state(seeded, client):
    body = chart(client, "spend_vs_allocation")
    state = client.get("/api/budget").json()
    for a in state["allocations"]:
        (alloc,) = rows(body, team=a["team"], series="allocation")
        (spent,) = rows(body, team=a["team"], series="recorded_spend")
        assert alloc["amount"] == a["amount"] and alloc["value_kind"] == "planned"
        assert spent["amount"] == a["recorded_spend"] and spent["value_kind"] == "simulated" and spent["simulated"]
    assert not rows(body, team="unattributed")
    assert body["spec"]["encoding"]["xOffset"]["field"] == "series"


def test_spend_vs_allocation_remaining_for_one_team(seeded, client):
    body = chart(client, "spend_vs_allocation", team="research", metric="remaining")
    assert [(r["team"], r["series"], r["amount"]) for r in body["spec"]["data"]["values"]] == \
        [("research", "remaining", "15000.00")]
    assert body["team"] == "research" and "team research" in body["spec"]["description"]


def test_unattributed_spend_is_its_own_column_and_coverage_partial(seeded, client):
    r = client.post("/api/imports", headers=IMPORTER_H, data={"source_kind": "northstar_billing"},
                    files={"file": ("sandbox.csv", INCOMPLETE_CSV.encode(), "text/csv")})
    assert r.status_code == 201, r.text
    body = chart(client, "spend_vs_allocation")
    (un,) = rows(body, team="unattributed")
    assert un["amount"] == "1200.00" and un["series"] == "recorded_spend"
    assert not rows(body, team="unattributed", series="allocation")
    assert body["coverage_status"] == "partial"
    assert any("unattributed" in n for n in body["notes"])
    cats = chart(client, "spend_by_cost_category", team="unattributed")
    assert [(r["cost_category"], r["amount"]) for r in cats["spec"]["data"]["values"]] == [("direct_api", "1200.00")]


def test_projection_vs_allocation_uses_forecast_without_snapshot(seeded, client):
    body = chart(client, "projection_vs_allocation")
    assert body["forecast_availability"] == "available"
    fc = {p["team"]: p["amount"] for p in client.get("/api/forecasts").json()["projections"]}
    assert {r["team"]: r["amount"] for r in rows(body, series="projected")} == fc
    assert all(r["value_kind"] == "simulated" and r["simulated"] for r in rows(body, series="projected"))
    assert any("not a forecast model" in n for n in body["notes"])
    gap = chart(client, "projection_vs_allocation", metric="gap")
    assert {r["team"]: r["amount"] for r in gap["spec"]["data"]["values"]} == \
        {"research": "25000.00", "product": "-30000.00", "engineering": "5000.00"}


def test_projection_chart_adds_recorded_spend_when_the_provider_reports_remaining(seeded, client):
    from app.providers.forecast import PlaceholderForecastProvider

    base = PlaceholderForecastProvider()

    class Remaining:
        name = "remaining-test"

        def get_forecast(self, period_id, team_ids):
            r = base.get_forecast(period_id, team_ids)
            return r.model_copy(update={"provider": self.name, "basis": "remaining"})

    spent = {a["team"]: Decimal(a["recorded_spend"]) for a in client.get("/api/budget").json()["allocations"]}
    alloc = {a["team"]: Decimal(a["amount"]) for a in client.get("/api/budget").json()["allocations"]}
    assert any(spent.values())
    seeded.state.forecast_provider = Remaining()
    try:
        body = chart(client, "projection_vs_allocation")
        got = {r["team"]: Decimal(r["amount"]) for r in rows(body, series="projected")}
        assert got == {t: v + spent[t] for t, v in
                       {"research": Decimal("85000"), "product": Decimal("50000"), "engineering": Decimal("65000")}.items()}
        assert all(r["basis"] == "remaining" for r in rows(body, series="projected"))
        assert any("recorded spend plus that remaining amount" in n for n in body["notes"])
        gap = chart(client, "projection_vs_allocation", metric="gap")
        assert {r["team"]: Decimal(r["amount"]) for r in gap["spec"]["data"]["values"]} == \
            {t: got[t] - alloc[t] for t in got}
    finally:
        seeded.state.forecast_provider = base


def test_projection_chart_with_forecast_unavailable_plots_no_projection(tmp_path, clock, id_factory):
    from app.seed.northstar import seed

    app = create_app(Settings(db_path=tmp_path / "u.db", forecast_provider="unavailable"), clock=clock,
                     id_factory=id_factory)
    s = app.state.session_factory()
    seed(s, clock=clock, ids=id_factory)
    s.close()
    try:
        with TestClient(app) as c:
            body = chart(c, "projection_vs_allocation")
            assert body["forecast_availability"] == "unavailable"
            assert not rows(body, series="projected")
            assert len(rows(body, series="allocation")) == 3
            assert "unavailable" in body["title"] and any("never zero" in n for n in body["notes"])
            gap = c.get("/api/charts/projection_vs_allocation", params={"metric": "gap"}).json()
            assert gap["row_count"] == 0
    finally:
        app.state.engine.dispose()


def test_spend_by_cost_category_never_plots_included_usage_as_spend(seeded, client):
    body = chart(client, "spend_by_cost_category")
    spend = client.get("/api/spend/summary").json()
    cats = {r["cost_category"] for r in body["spec"]["data"]["values"]}
    assert not cats & {"included_usage", "unpriced_usage"}
    for t in spend["teams"]:
        total = sum((Decimal(r["amount"]) for r in rows(body, team=t["team"])), Decimal("0.00"))
        assert str(total) == t["recorded_spend"]
    assert any("included usage notional value" in n for n in body["notes"])
    assert body["spec"]["encoding"]["y"]["stack"] == "zero"
    counted = chart(client, "spend_by_cost_category", metric="record_count")
    assert "included_usage" in {r["cost_category"] for r in counted["spec"]["data"]["values"]}
    assert "transform" not in counted["spec"] and counted["spec"]["encoding"]["y"]["field"] == "count"


def test_budget_history_follows_applied_decisions(seeded, client):
    first = chart(client, "budget_history")
    assert {r["state_version"] for r in first["spec"]["data"]["values"]} == {1}
    p = draft(client, transfer_body()).json()
    d = decide(client, p["id"], headers=APPROVER)
    assert d.status_code == 201, d.text
    body = chart(client, "budget_history")
    v2 = {r["team"]: r for r in rows(body, state_version=2)}
    assert {t: r["amount"] for t, r in v2.items()} == \
        {"research": "85000.00", "product": "50000.00", "engineering": "65000.00"}
    assert all(r["decision_id"] == d.json()["id"] and r["action_type"] == "transfer" for r in v2.values())
    assert all(r["decision_id"] is None for r in rows(body, state_version=1))
    assert body["spec"]["mark"]["type"] == "line"
    env = chart(client, "budget_history", metric="envelope_total")
    assert [(r["state_version"], r["amount"]) for r in env["spec"]["data"]["values"]] == \
        [(1, "200000.00"), (2, "200000.00")]
    one = chart(client, "budget_history", team="research")
    assert [r["amount"] for r in one["spec"]["data"]["values"]] == ["60000.00", "85000.00"]


@pytest.mark.parametrize("path,params,status,code", [
    ("/api/charts/burn_rate", {}, 404, "unknown_chart_kind"),
    ("/api/charts/budget_history", {"metric": "spend"}, 422, "unknown_metric"),
    ("/api/charts/spend_vs_allocation", {"team": "marketing"}, 422, "unknown_team"),
    ("/api/charts/spend_vs_allocation", {"team": "unattributed"}, 422, "unknown_team"),
    ("/api/charts/budget_history", {"metric": "envelope_total", "team": "research"}, 422, "team_not_applicable"),
])
def test_chart_request_errors(seeded, client, path, params, status, code):
    r = client.get(path, params=params)
    assert r.status_code == status, r.text
    err = r.json()["error"]
    if status == 404:
        assert err["code"] == code and err["details"]["kinds"] == list(CHART_KINDS)
    else:
        assert err["code"] == "validation_failed"
        assert code in {x["code"] for x in err["details"]["reasons"]}


def test_unknown_period_is_404(seeded, client):
    r = client.get("/api/charts/spend_vs_allocation", params={"period": "1999-P9"})
    assert r.status_code == 404 and r.json()["error"]["code"] == "unknown_period"


# ---- Droid tool -------------------------------------------------------------------------------------


def test_toolbox_build_chart_spec_is_recorded_and_read_only(seeded):
    tb = _toolbox(seeded)
    before = counts(seeded)
    out = tb.call("build_chart_spec", {"kind": "projection_vs_allocation", "metric": "gap"})
    assert out["kind"] == "projection_vs_allocation" and out["spec"]["$schema"] == VEGA
    assert tb.charts == [out]
    assert counts(seeded) == before
    with pytest.raises(ToolError) as bad_kind:
        tb.call("build_chart_spec", {"kind": "burn_rate"})
    assert bad_kind.value.code == "invalid_arguments"
    with pytest.raises(ToolError) as bad_team:
        tb.build_chart_spec("spend_vs_allocation", team="marketing")
    assert bad_team.value.code == "validation_failed"
    assert len(tb.charts) == 1  # refused calls build nothing
    s = seeded.state.session_factory()
    try:
        from app.db.models import AgentRunStep

        steps = s.scalars(select(AgentRunStep).where(AgentRunStep.run_id == "run_t").order_by(AgentRunStep.seq)).all()
    finally:
        s.close()
    assert [st.tool for st in steps] == ["build_chart_spec", "build_chart_spec"]  # schema refusal never ran
    assert steps[0].result_summary.startswith("projection_vs_allocation chart (gap)")
    assert steps[1].result_summary.startswith("error validation_failed")


def test_fake_answer_with_chart_attaches_the_backend_spec(seeded, client):
    r = client.post("/api/agent/runs", headers=ANALYST,
                    json={"task_type": "answer_question",
                          "params": {"chart": {"kind": "budget_history", "metric": "envelope_total"}}})
    assert r.status_code == 201, r.text
    out = r.json()
    assert out["status"] == "succeeded" and out["applied_changes"] is False
    assert out["params"] == {"chart": {"kind": "budget_history", "metric": "envelope_total"}}
    assert [s["tool"] for s in out["steps"]][-1] == "build_chart_spec"
    (spec,) = out["output"]["charts"]
    direct = chart(client, "budget_history", metric="envelope_total")
    assert spec["spec"]["data"] == direct["spec"]["data"] and spec["title"] == direct["title"]
    finding = next(f for f in out["output"]["findings"] if f["type"] == "chart")
    assert finding["title"] == spec["title"] and "Chart built from backend data only" in out["summary"]


def test_fake_answer_chart_refusal_is_a_warning_not_a_chart(seeded, client):
    out = client.post("/api/agent/runs", headers=ANALYST,
                      json={"task_type": "answer_question",
                            "params": {"chart": {"kind": "spend_vs_allocation", "team": "marketing"}}}).json()
    assert out["status"] == "succeeded"
    assert "charts" not in out["output"]
    assert any(w["code"] == "chart_not_built" for w in out["output"]["warnings"])


def test_answer_without_chart_has_no_charts_key(seeded, client):
    out = client.post("/api/agent/runs", headers=ANALYST, json={"task_type": "answer_question"}).json()
    assert "charts" not in out["output"] and "build_chart_spec" not in {s["tool"] for s in out["steps"]}


@pytest.mark.parametrize("params", [{"chart": {"kind": "pie"}}, {"chart": {"kind": "budget_history", "x": 1}},
                                    {"colour": "blue"}])
def test_answer_chart_params_are_validated(seeded, client, params):
    r = client.post("/api/agent/runs", headers=ANALYST, json={"task_type": "answer_question", "params": params})
    assert r.status_code == 422, r.text
    assert {x["code"] for x in r.json()["error"]["details"]["reasons"]} == {"invalid_params"}


def test_sdk_tool_function_wraps_build_chart_spec(seeded):
    from northstar_droid.sdk_tools import tool_functions

    fns = {n: fn for n, _, fn in tool_functions(_toolbox(seeded))}
    ok = json.loads(fns["build_chart_spec"]("spend_by_cost_category", team="research"))
    assert ok["kind"] == "spend_by_cost_category" and {r["team"] for r in ok["spec"]["data"]["values"]} == {"research"}
    refused = json.loads(fns["build_chart_spec"]("budget_history", metric="spend"))
    assert refused["error"]["code"] == "validation_failed"


def test_sdk_prompt_names_the_requested_chart():
    from app.agent.runner import AgentTask
    from northstar_droid.sdk_runner import task_prompt

    text = task_prompt(AgentTask(type="answer_question", params={"chart": {"kind": "budget_history"}}))
    assert "build_chart_spec" in text and '{"kind": "budget_history"}' in text
    assert "northstar___build_chart_spec" in text
