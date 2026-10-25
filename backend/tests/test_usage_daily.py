"""Daily observed ledger: exact money, missing telemetry, UTC windows and attribution."""

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError
from types import SimpleNamespace

from app.db.models import ImportBatch, Person, PlanningPeriod, Team, UsageRecord


@pytest.fixture
def ledger(session, clock):
    session.add_all([
        PlanningPeriod(id="sept", label="September", starts_on=date(2026, 9, 1), ends_on=date(2026, 9, 30)),
        PlanningPeriod(id="oct", label="October", starts_on=date(2026, 10, 1), ends_on=date(2026, 10, 31)),
        Team(id="active", name="Active", active=True), Team(id="inactive", name="Inactive", active=False),
    ])
    session.flush()
    session.add_all([
        Person(id="alice", name="Alice", team_id="active", active=False),
        Person(id="bob", name="Bob", team_id="inactive", active=True),
        ImportBatch(id="batch", source_kind="native", content_hash="native", status="imported",
                    imported_by="test", value_kind_default="reported", created_at=clock.now()),
    ])
    session.commit()

    def add(key, *, occurred_at="2026-10-01T10:00:00+00:00", team="active", person="alice",
            kind="reported", category="direct_api", amount="0.10", notional=None,
            provider="a", model="same", **tokens):
        at = datetime.fromisoformat(occurred_at)
        rec = UsageRecord(id=key, source_record_key=key, import_batch_id="batch", source_kind="native",
            source_account="account", team_id=team, person_id=person,
            period_id="sept" if at.astimezone(timezone.utc).month == 9 else "oct", occurred_at=at,
            provider=provider, model=model, value_kind=kind, cost_category=category,
            counts_toward_spend=category not in ("included_usage", "unpriced_usage"),
            amount=Decimal(amount) if amount is not None else None,
            notional_value=Decimal(notional) if notional is not None else None,
            unit="USD", created_at=clock.now(), **tokens)
        session.add(rec)
        session.commit()
        return rec

    return add


def daily(client, **params):
    response = client.get("/api/usage/daily", params={"scope_type": "company", "start_date": "2026-09-30",
                          "end_date_exclusive": "2026-10-03", **params})
    assert response.status_code == 200, response.text
    return response.json()


def test_exact_costs_all_native_kinds_dimensions_and_subsets(ledger, client):
    ledger("r", kind="reported", input_tokens=100, output_tokens=20, cached_input_tokens=80, reasoning_tokens=10)
    ledger("e", kind="estimated", amount="0.20", provider="b", input_tokens=0, output_tokens=0)
    ledger("m", kind="measured", amount="0.30")
    ledger("s", kind="simulated", amount="0.40")
    ledger("included", category="included_usage", amount=None, notional="10.00", input_tokens=50, output_tokens=5)
    ledger("unpriced", category="unpriced_usage", kind="measured", amount=None, input_tokens=10, output_tokens=2)
    body = daily(client)
    bucket = body["buckets"][1]
    assert bucket["recorded_spend"] == "1.00"
    assert bucket["costs_by_value_kind"] == {"reported": "0.10", "estimated": "0.20", "measured": "0.30", "simulated": "0.40"}
    assert bucket["included_usage_notional"] == "10.00"
    assert bucket["tokens"] == {"input_tokens": 160, "output_tokens": 27, "cached_input_tokens": 80,
                                "reasoning_tokens": 10, "total_tokens": 187}
    assert bucket["token_observed_record_counts"]["total_tokens"] == 4
    assert {(b["provider"], b["model"]) for b in bucket["breakdowns"]} == {("a", "same"), ("b", "same")}
    assert bucket["record_count"] == 6 and bucket["source_refs"] == ["batch"]
    assert bucket["coverage"] == "partial" and body["synthetic"] is True
    assert body["available_start_date"] == "2026-10-01" and body["available_end_date_exclusive"] == "2026-10-02"


def test_absent_days_zero_rows_unpaired_telemetry_and_future_are_distinct(ledger, client):
    ledger("zero", amount="0.00", input_tokens=0, output_tokens=0)
    ledger("unpaired", occurred_at="2026-10-02T10:00:00+00:00", input_tokens=4)
    ledger("future", occurred_at="2026-10-25T10:00:00+00:00", amount="999.00")
    body = daily(client, end_date_exclusive="2026-10-26")
    by_day = {row["date"]: row for row in body["buckets"]}
    assert by_day["2026-09-30"]["recorded_spend"] is None
    assert by_day["2026-09-30"]["tokens"]["total_tokens"] is None
    assert by_day["2026-09-30"]["coverage"] == "missing"
    assert by_day["2026-10-01"]["recorded_spend"] == "0.00"
    assert by_day["2026-10-01"]["tokens"]["total_tokens"] == 0
    assert by_day["2026-10-02"]["tokens"]["input_tokens"] == 4
    assert by_day["2026-10-02"]["tokens"]["output_tokens"] is None
    assert by_day["2026-10-02"]["tokens"]["total_tokens"] is None
    assert by_day["2026-10-25"]["coverage"] == "future"
    assert by_day["2026-10-25"]["record_count"] == 0


def test_cross_period_utc_exclusive_boundary_and_filters(ledger, client):
    ledger("september", occurred_at="2026-10-01T00:30:00+01:00", amount="1.00")
    ledger("october", occurred_at="2026-10-01T00:00:00+00:00", amount="2.00", provider="b", model="different")
    ledger("excluded", occurred_at="2026-10-03T00:00:00+00:00", amount="100.00")
    body = daily(client)
    assert [b["recorded_spend"] for b in body["buckets"]] == ["1.00", "2.00", None]
    filtered = daily(client, provider="b", model="different")
    assert [b["recorded_spend"] for b in filtered["buckets"]] == [None, "2.00", None]
    assert filtered["source_coverage"][0]["record_count"] == 1


def test_stored_attribution_reconciles_inactive_people_teams_and_shared(ledger, client):
    ledger("person", amount="1.00")
    ledger("team-shared", person=None, amount="2.00")
    ledger("inactive", team="inactive", person="bob", amount="3.00")
    ledger("company-shared", team=None, person=None, amount="4.00")
    def amount(**kwargs):
        return daily(client, **kwargs)["buckets"][1]["recorded_spend"]
    assert amount() == "10.00"
    assert amount(scope_type="team", scope_id="active") == "3.00"
    assert amount(scope_type="person", scope_id="alice") == "1.00"
    assert amount(scope_type="shared", scope_id="active") == "2.00"
    assert amount(scope_type="team", scope_id="inactive") == "3.00"
    assert amount(scope_type="shared") == "4.00"


def test_revision_tracks_changed_native_values_but_reads_are_stable(ledger, client, session):
    row = ledger("one")
    before = daily(client)
    assert daily(client)["dataset_revision"] == before["dataset_revision"]
    row.amount = Decimal("0.11")
    session.commit()
    after = daily(client)
    assert after["dataset_revision"] != before["dataset_revision"]
    assert after["buckets"][1]["revision"] != before["buckets"][1]["revision"]
    assert after["buckets"][1]["record_count"] == 1


@pytest.mark.parametrize("params", [
    {"end_date_exclusive": "2026-09-30"}, {"end_date_exclusive": "2027-10-02"},
    {"scope_type": "team"}, {"scope_type": "person", "scope_id": "missing"},
    {"scope_type": "shared", "scope_id": "missing"}, {"scope_type": "company", "scope_id": "active"},
    {"scope_type": "invented"},
])
def test_rejects_invalid_window_and_scope(client, params):
    response = client.get("/api/usage/daily", params={"start_date": "2026-09-30",
                          "end_date_exclusive": "2026-10-03", **params})
    assert response.status_code == 422


def test_compat_daily_matches_native(client, ledger):
    ledger("one")
    params = {"scope_type": "company", "start_date": "2026-10-01", "end_date_exclusive": "2026-10-02"}
    native = client.get("/api/usage/daily", params=params)
    assert native.status_code == 200
    for prefix in ("/compat", "/compat/api"):
        alias = client.get(prefix + "/usage/daily", params=params)
        assert alias.status_code == 200, alias.text
        assert alias.json() == native.json()


def test_accepts_maximum_window_and_does_not_expose_unreceived_or_later_today(ledger, client, session, clock):
    row = ledger("unreceived", amount="5.00")
    row.created_at = datetime(2026, 10, 24, 12, 0, 1, tzinfo=timezone.utc)
    session.commit()
    ledger("later-today", occurred_at="2026-10-24T12:00:01+00:00", amount="6.00")
    body = daily(client, start_date="2025-10-24", end_date_exclusive="2026-10-25")
    assert len(body["buckets"]) == 366
    assert body["available_start_date"] is None
    assert all(row["recorded_spend"] is None for row in body["buckets"])


def test_known_forecast_directory_person_has_unavailable_ledger_attribution(client, app):
    app.state.session_factory.configure(info={"people_directory": lambda: [SimpleNamespace(id="forecast-person")]})
    body = daily(client, scope_type="person", scope_id="forecast-person")
    assert all(row["recorded_spend"] is None and row["coverage"] == "missing" for row in body["buckets"])
    assert any("unavailable attribution" in note for note in body["notes"])


def test_response_rejects_unknown_native_provenance(ledger, client):
    from app.schemas.usage import DailyUsageResponse

    ledger("one")
    body = daily(client)
    body["buckets"][1]["costs_by_value_kind"]["guessed"] = "1.00"
    with pytest.raises(ValidationError):
        DailyUsageResponse.model_validate(body)


def test_native_import_deduplication_never_doubles_daily_cost_or_tokens(seeded, client):
    from reference_data import upload

    csv = ("record_id,occurred_at,source_account,provider,model,cost_category,value_kind,amount,input_tokens,output_tokens\n"
           "daily-one,2026-10-21,ws-research,a,same,direct_api,reported,0.10,100,20\n")
    first = upload(client, csv)
    assert first.status_code == 201, first.text
    before = daily(client, start_date="2026-10-21", end_date_exclusive="2026-10-22")
    again = upload(client, csv)
    assert again.status_code == 200 and again.json()["status"] == "duplicate"
    after = daily(client, start_date="2026-10-21", end_date_exclusive="2026-10-22")
    assert after["dataset_revision"] == before["dataset_revision"]
    assert after["buckets"][0]["recorded_spend"] == "0.10"
    assert after["buckets"][0]["tokens"]["total_tokens"] == 120
    assert after["buckets"][0]["record_count"] == 1
