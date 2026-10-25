"""People directory, person attribution on import, and the generated daily per-person seed export
(frontend-integration-design §2.1, §2.2, §3)."""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from app.config import Settings
from app.core.errors import DomainError
from app.db import models as m
from app.db.base import SchemaOutdated, check_schema, create_all, make_engine
from app.seed import daily_spend
from app.seed.northstar import PEOPLE, SPEND_FILE
from reference_data import ANALYST, upload

CATEGORY_TARGETS = {
    ("research", "subscription_fee"): ("5000", None, None, None),
    ("research", "direct_api"): ("40000", None, 1_000_000, 200_000),
    ("research", "included_usage"): (None, "3000", 500_000, 100_000),
    ("product", "subscription_fee"): ("4000", None, None, None),
    ("product", "billable_overage"): ("16000", None, None, None),
    ("engineering", "subscription_fee"): ("4000", None, None, None),
    ("engineering", "included_usage"): (None, "2500", 400_000, 80_000),
    ("engineering", "direct_api"): ("26000", None, None, None),
}
TEAM_OF_ACCOUNT = {"ws-research": "research", "ws-product": "product", "ws-engineering": "engineering"}
EMAIL_TO_PERSON = {p["email"]: p for p in PEOPLE}


# ---- generator -------------------------------------------------------------------------------


def test_daily_export_files_are_generated_and_committed():
    assert daily_spend.check() == []
    assert daily_spend.main(["--check"]) == 0
    seed = SPEND_FILE.read_bytes()
    assert daily_spend.PLANTED_DUPLICATE.read_bytes() == seed  # P1: byte-identical
    reexport = daily_spend.PLANTED_REEXPORT.read_bytes()
    assert reexport != seed and b"\r\n" in reexport and b"\r\n" not in seed


def test_daily_rows_are_deterministic_and_complete():
    rows = daily_spend.rows()
    assert rows == daily_spend.rows()
    assert len(rows) == 616
    assert [r["record_id"] for r in rows] == sorted(r["record_id"] for r in rows)
    assert len({r["record_id"] for r in rows}) == 616
    counts = defaultdict(int)
    for r in rows:
        counts[TEAM_OF_ACCOUNT[r["source_account"]]] += 1
    assert counts == {"research": 260, "product": 160, "engineering": 196}
    assert {r["occurred_at"][:10] for r in rows} == {f"2026-10-{d:02d}" for d in range(1, 21)}
    assert all(r["value_kind"] == "simulated" and r["unit"] == "USD" for r in rows)


def test_daily_rows_sum_exactly_to_team_category_targets():
    sums: dict[tuple[str, str], list] = defaultdict(lambda: [Decimal(0), Decimal(0), 0, 0])
    for r in daily_spend.rows():
        key = (TEAM_OF_ACCOUNT[r["source_account"]], r["cost_category"])
        acc = sums[key]
        acc[0] += Decimal(r["amount"] or "0")
        acc[1] += Decimal(r["notional_value"] or "0")
        acc[2] += int(r["input_tokens"] or 0)
        acc[3] += int(r["output_tokens"] or 0)
    assert set(sums) == set(CATEGORY_TARGETS)
    for key, (amount, notional, tin, tout) in CATEGORY_TARGETS.items():
        got = sums[key]
        assert got[0] == Decimal(amount or "0"), key
        assert got[1] == Decimal(notional or "0"), key
        assert got[2] == (tin or 0) and got[3] == (tout or 0), key


def test_every_amount_positive_whole_dollars_and_team_level_rows_are_included_usage():
    for r in daily_spend.rows():
        value = r["amount"] or r["notional_value"]
        assert value.endswith(".00") and Decimal(value) > 0, r["record_id"]
        if r["cost_category"] == "included_usage":
            assert r["user_email"] == "" and r["amount"] == ""
        else:
            person = EMAIL_TO_PERSON[r["user_email"]]
            assert person["team"] == TEAM_OF_ACCOUNT[r["source_account"]]
            assert r["record_id"] == f"ns-2026p1-{r['occurred_at'][:10].replace('-', '')}-{person['id']}-{r['cost_category']}"


def _daily_api(person_id: str) -> dict[date, Decimal]:
    email = next(p["email"] for p in PEOPLE if p["id"] == person_id)
    return {date.fromisoformat(r["occurred_at"][:10]): Decimal(r["amount"])
            for r in daily_spend.rows() if r["user_email"] == email and r["cost_category"] == "direct_api"}


def _weekday_avg(series: dict[date, Decimal], lo: date, hi: date) -> Decimal:
    vals = [v for d, v in series.items() if lo <= d <= hi and d.weekday() < 5]
    return sum(vals) / len(vals)


def test_trends_and_start_dates_shape_the_past_spend():
    hana = [r for r in daily_spend.rows() if r["user_email"] == "hana.sato@northstar.example"]
    assert hana and min(r["occurred_at"][:10] for r in hana) == "2026-10-13"
    leila = _daily_api("research-leila-novak")
    assert _weekday_avg(leila, date(2026, 10, 14), date(2026, 10, 20)) < \
        _weekday_avg(leila, date(2026, 10, 1), date(2026, 10, 13)) / 2
    omar = _daily_api("research-omar-haddad")
    assert _weekday_avg(omar, date(2026, 10, 19), date(2026, 10, 20)) < \
        _weekday_avg(omar, date(2026, 10, 1), date(2026, 10, 16)) * Decimal("0.6")


def test_split_is_largest_remainder_with_earlier_ties():
    assert daily_spend.split(10, [1, 1, 1]) == [4, 3, 3]
    assert daily_spend.split(7, [3, 1]) == [5, 2]
    assert sum(daily_spend.split(40000, [7, 13, 29, 1])) == 40000
    with pytest.raises(ValueError):
        daily_spend.split(5, [0, 0])


# ---- seeded people and spend --------------------------------------------------------------------


def test_seed_has_fifteen_people(seeded, client):
    people = client.get("/api/people").json()
    assert len(people) == 15
    per_team = defaultdict(int)
    for p in people:
        per_team[p["team"]] += 1
        assert p["is_simulated"] and p["active"] and p["email"].endswith("@northstar.example")
        assert set(p["integrations"]) <= set(m.INTEGRATIONS) and p["primary_tool"]
    assert per_team == {"research": 6, "product": 4, "engineering": 5}
    assert [(p["team"], p["name"]) for p in people] == sorted((p["team"], p["name"]) for p in people)
    product = client.get("/api/people", params={"team": "product"}).json()
    assert {p["id"] for p in product} == {"product-maya-patel", "product-noah-kim", "product-zara-ali",
                                          "product-felix-weber"}
    ava = client.get("/api/people/research-ava-chen").json()
    assert ava["role"] == "Research lead" and ava["primary_tool"] == "Claude Code"
    assert ava["integrations"] == ["slack", "asana"]
    assert client.get("/api/people", params={"team": "marketing"}).status_code == 422
    assert client.get("/api/people/nobody").status_code == 404


def test_person_spend_sums_to_team_spend(seeded, client):
    summary = {t["team"]: Decimal(t["recorded_spend"]) for t in client.get("/api/spend/summary").json()["teams"]}
    assert summary == {"research": Decimal("45000.00"), "product": Decimal("20000.00"),
                       "engineering": Decimal("30000.00")}
    items = client.get("/api/spend/records", params={"limit": 1000}).json()["items"]
    assert len(items) == 616
    person_team = {p["id"]: p["team"] for p in PEOPLE}
    by_team: dict[str, Decimal] = defaultdict(Decimal)
    for r in items:
        if r["cost_category"] == "included_usage":
            assert r["person"] is None
            continue
        assert r["person"] is not None and person_team[r["person"]] == r["team"]
        if r["counts_toward_spend"]:
            by_team[r["team"]] += Decimal(r["amount"])
    assert dict(by_team) == summary
    omar = client.get("/api/spend/records", params={"person": "research-omar-haddad"}).json()
    assert omar["total"] == 40 and {r["person"] for r in omar["items"]} == {"research-omar-haddad"}
    assert client.get("/api/spend/records", params={"person": "nobody"}).status_code == 422


# ---- import-time person attribution -------------------------------------------------------------

HEADER = "record_id,occurred_at,source_account,user_email,provider,cost_category,amount,unit\n"


def _record(client, key: str) -> dict:
    items = client.get("/api/spend/records", params={"limit": 1000}).json()["items"]
    return next(r for r in items if r["source_record_key"] == key)


def test_user_email_resolves_only_to_a_person_on_the_mapped_team(seeded, client):
    csv = HEADER + (
        "u-1,2026-10-18T00:00:00Z,ws-research,Omar.Haddad@Northstar.Example,anthropic,direct_api,10.00,USD\n"
        "u-2,2026-10-18T00:00:00Z,ws-research,maya.patel@northstar.example,anthropic,direct_api,20.00,USD\n"
        "u-3,2026-10-18T00:00:00Z,ws-research,someone@else.example,anthropic,direct_api,30.00,USD\n"
        "u-4,2026-10-18T00:00:00Z,ws-unknown,omar.haddad@northstar.example,anthropic,direct_api,40.00,USD\n"
        "u-5,2026-10-18T00:00:00Z,ws-research,,anthropic,direct_api,50.00,USD\n"
    )
    r = upload(client, csv, filename="people.csv")
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["stats"]["person_resolved"] == 1 and body["stats"]["person_unresolved"] == 3
    assert "person_unresolved" in {w["code"] for w in body["warnings"]}
    assert _record(client, "u-1")["person"] == "research-omar-haddad"
    other_team = _record(client, "u-2")  # an email never moves spend to another team
    assert other_team["team"] == "research" and other_team["person"] is None
    assert _record(client, "u-3")["person"] is None
    unmapped = _record(client, "u-4")
    assert unmapped["team"] == "unattributed" and unmapped["person"] is None
    assert _record(client, "u-5")["person"] is None


def test_invalid_user_email_fails_the_batch(seeded, client):
    csv = HEADER + "u-9,2026-10-18T00:00:00Z,ws-research,not-an-email,anthropic,direct_api,10.00,USD\n"
    err = upload(client, csv, filename="bad.csv").json()["error"]
    assert err["code"] == "import_failed"
    assert [e["code"] for e in err["details"]["batch"]["errors"]] == ["invalid_user_email"]


def test_remapping_clears_person_not_on_the_new_team(seeded, client):
    r = client.put("/api/team-mappings", headers=ANALYST, json={
        "source_kind": "northstar_billing", "source_account": "ws-research", "team_id": "product",
        "effective_from": "2026-01-01"})
    assert r.status_code == 200, r.text
    moved = client.get("/api/spend/records", params={"team": "product", "limit": 1000}).json()["items"]
    research_rows = [i for i in moved if i["source_account"] == "ws-research"]
    assert len(research_rows) == 260 and all(i["person"] is None for i in research_rows)
    assert all(i["person"] is not None for i in moved
               if i["source_account"] == "ws-product" and i["cost_category"] != "included_usage")


# ---- model constraints and schema guard ---------------------------------------------------------


def test_person_constraints(seeded, session):
    session.add(m.Person(id="unattributed", team_id="research", name="Nobody"))
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()
    session.add(m.Person(id="research-dup", team_id="research", name="Dup", email="ava.chen@northstar.example"))
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


def test_create_people_validates_all_or_nothing(seeded, session, clock):
    from app.services import people as svc

    with pytest.raises(DomainError) as exc:
        svc.create_people(session, [
            {"id": "research-new", "team": "research", "name": "New Person", "email": "new@northstar.example"},
            {"id": "Bad Id", "team": "marketing", "name": "", "email": "AVA.CHEN@northstar.example",
             "integrations": ["fax"]},
        ], clock=clock)
    codes = {r["code"] for r in exc.value.details["reasons"]}
    assert codes == {"invalid_person_id", "unknown_team", "name_required", "duplicate_email", "unknown_integration"}
    assert session.get(m.Person, "research-new") is None


def test_check_schema_names_missing_column(tmp_path):
    db = tmp_path / "old.db"
    engine = make_engine(db)
    create_all(engine)
    check_schema(engine)  # current schema passes
    with engine.begin() as conn:
        conn.execute(text("PRAGMA foreign_keys=OFF"))
        conn.execute(text("DROP TABLE usage_records"))
        conn.execute(text("CREATE TABLE usage_records (id VARCHAR(64) PRIMARY KEY, team_id VARCHAR(64))"))
    with pytest.raises(SchemaOutdated, match=r"usage_records\.person_id"):
        check_schema(engine)
    engine.dispose()
    from app.main import create_app

    with pytest.raises(SchemaOutdated, match="python -m app.seed"):
        create_app(Settings(db_path=db, droid_runner="fake", forecast_provider="placeholder"))


def test_check_schema_reports_missing_table(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'empty.db'}")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE teams (id VARCHAR(64) PRIMARY KEY)"))
    with pytest.raises(SchemaOutdated, match="people"):
        check_schema(engine)
    engine.dispose()
