"""Spend summary and record drill-down (acceptance checks 3a, 3b; included usage; categories)."""

from __future__ import annotations

from reference_data import IMPORTER, upload

UNMAPPED_CSV = (
    "record_id,occurred_at,source_account,provider,model,cost_category,value_kind,amount,unit\n"
    "x-001,2026-10-18T00:00:00Z,ws-shared-sandbox,openai,gpt,direct_api,simulated,1200.00,USD\n"
)


def _teams(body):
    return {t["team"]: t for t in body["teams"]}


def test_northstar_seed_totals_45_20_30_95(seeded, client):
    body = client.get("/api/spend/summary").json()
    teams = _teams(body)
    assert {t: v["recorded_spend"] for t, v in teams.items()} == {
        "research": "45000.00", "product": "20000.00", "engineering": "30000.00"}
    assert body["company_total"] == "95000.00"
    assert body["attributed_total"] == "95000.00"
    assert body["unit"] == "USD" and body["period"]["id"] == "2026-P1"
    assert body["coverage"]["status"] == "complete"
    assert body["data_labels"] == {"simulated": True, "real_sample": False}


def test_included_usage_excluded_from_spend_but_shown_as_notional(seeded, client):
    research = _teams(client.get("/api/spend/summary").json())["research"]
    inc = research["by_cost_category"]["included_usage"]
    assert inc["amount"] is None and inc["counts_toward_spend"] is False
    assert inc["notional_value"] == "3000.00" and research["included_usage_notional"] == "3000.00"
    assert research["recorded_spend"] == "45000.00"  # 5k fee + 40k API, notional 3k not added
    records = client.get("/api/spend/records", params={"team": "research", "cost_category": "included_usage"}).json()
    assert records["total"] == 20  # one team-level row per day, Oct 1-20
    assert all(i["counts_toward_spend"] is False and i["amount"] is None and i["person"] is None
               for i in records["items"])


def test_breakdown_by_cost_category_and_value_kind(seeded, client):
    teams = _teams(client.get("/api/spend/summary").json())
    product = teams["product"]["by_cost_category"]
    assert product["subscription_fee"]["amount"] == "4000.00"
    assert product["billable_overage"]["amount"] == "16000.00"
    assert product["direct_api"]["amount"] == "0.00"
    assert product["unpriced_usage"]["amount"] is None
    assert teams["engineering"]["by_value_kind"]["simulated"] == "30000.00"
    assert teams["engineering"]["by_value_kind"]["measured"] == "0.00"


def test_unmapped_account_goes_to_unattributed_with_partial_coverage(seeded, client):
    r = upload(client, UNMAPPED_CSV, filename="sandbox.csv")
    assert r.status_code == 201, r.text
    body = client.get("/api/spend/summary").json()
    assert body["unattributed"]["recorded_spend"] == "1200.00"
    assert body["unattributed"]["source_accounts"] == [{"source": "northstar_billing:ws-shared-sandbox",
                                                        "record_count": 1}]
    assert body["attributed_total"] == "95000.00"
    assert body["company_total"] == "96200.00"
    assert body["coverage"]["status"] == "partial"
    assert all(t["coverage"]["status"] == "partial" for t in body["teams"])
    un = client.get("/api/spend/records", params={"team": "unattributed"}).json()
    assert [i["source_account"] for i in un["items"]] == ["ws-shared-sandbox"]


def test_team_without_records_reports_missing_not_zero_complete(app, client):
    from app.seed.northstar import seed

    s = app.state.session_factory()
    seed(s, clock=app.state.clock, ids=app.state.id_factory, include_spend=False)
    s.close()
    body = client.get("/api/spend/summary").json()
    assert body["coverage"]["status"] == "missing"
    assert all(t["coverage"]["status"] == "missing" for t in body["teams"])
    assert all(t["recorded_spend"] == "0.00" for t in body["teams"])


def test_overview_totals_match_budget_and_spend_endpoints(seeded, client):
    ov = client.get("/api/overview").json()
    spend = client.get("/api/spend/summary").json()
    budget = client.get("/api/budget").json()
    assert ov["company"]["recorded_spend"] == spend["company_total"] == "95000.00"
    assert ov["company"]["envelope_total"] == budget["envelope_total"] == "200000.00"
    assert ov["company"]["projected_total"] == "200000.00"
    by_team = {t["team"]: t for t in ov["teams"]}
    for a in budget["allocations"]:
        assert by_team[a["team"]]["allocation"] == a["amount"]
        assert by_team[a["team"]]["recorded_spend"] == a["recorded_spend"]
    assert by_team["research"]["projected_minus_allocation"] == "25000.00"
    assert ov["spend"] == spend and ov["budget"] == budget


def test_records_filters_validate_and_paginate(seeded, client):
    assert client.get("/api/spend/records", params={"team": "marketing"}).json()["error"]["code"] == "validation_failed"
    r = client.get("/api/spend/records", params={"value_kind": "guessed", "cost_category": "nope"})
    assert r.status_code == 422
    assert {x["code"] for x in r.json()["error"]["details"]["reasons"]} == {"unknown_value_kind", "unknown_cost_category"}
    page = client.get("/api/spend/records", params={"limit": 3, "offset": 0}).json()
    rest = client.get("/api/spend/records", params={"limit": 1000, "offset": 3}).json()
    assert page["total"] == rest["total"] == 616
    assert len(page["items"]) == 3 and len(rest["items"]) == 613
    assert not {i["id"] for i in page["items"]} & {i["id"] for i in rest["items"]}
    assert client.get("/api/spend/records", params={"limit": 0}).status_code == 422


def test_unknown_period_is_404(seeded, client):
    r = client.get("/api/spend/summary", params={"period": "1999-P9"})
    assert r.status_code == 404 and r.json()["error"]["code"] == "unknown_period"


def test_reimport_of_seed_file_does_not_change_summary(seeded, client):
    from app.seed.northstar import SPEND_FILE

    before = client.get("/api/spend/summary").json()
    r = upload(client, SPEND_FILE.read_bytes(), filename=SPEND_FILE.name, headers=IMPORTER)
    assert r.status_code == 200 and r.json()["status"] == "duplicate"
    assert client.get("/api/spend/summary").json()["company_total"] == before["company_total"]
