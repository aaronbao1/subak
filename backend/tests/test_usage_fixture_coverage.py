"""Only the verified, opted-in source inventory can promote native daily coverage.

The fixture writes actual source CSVs and imports them through the native importer.
These tests never substitute row presence for the manifest's completion receipt.
"""

from datetime import date
from decimal import Decimal
import json
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.core.clock import FrozenClock
from app.db.models import BudgetRequest, ImportBatch, UsageRecord
from app.forecasting.company_fixture import company_fixture_snapshot_factory
from app.schemas.forecasts import ForecastResult, TeamProjection
from app.schemas.usage import DailyUsageResponse
from app.services import budget_requests, usage
from test_company_fixture_snapshot import company, instant


def source_session(company, now="2026-01-04T00:00:00Z", *, attached=True, transform=None):
    factory, source, _ = company
    clock = FrozenClock(instant(now))
    session = factory()
    if attached:
        source_factory = company_fixture_snapshot_factory(factory, source, clock.now)
        def selected_factory(**kwargs):
            result = source_factory(**kwargs)
            if transform is not None:
                transform(result)
            return result
        session.info["forecast_service"] = SimpleNamespace(
            snapshot_factory=selected_factory)
    return session, clock


def daily(company, *, now="2026-01-04T00:00:00Z", attached=True,
          scope_type="company", scope_id=None, transform=None,
          start_date=date(2026, 1, 1), end_date_exclusive=date(2026, 1, 5), **filters):
    session, clock = source_session(company, now, attached=attached, transform=transform)
    try:
        result = usage.daily_usage(session, scope_type=scope_type, scope_id=scope_id,
            start_date=start_date, end_date_exclusive=end_date_exclusive,
            provider=filters.get("provider"), model=filters.get("model"), clock=clock)
        return DailyUsageResponse.model_validate(result).model_dump(mode="json")
    finally:
        session.close()


@pytest.mark.parametrize("scope", [
    {"scope_type": "company"}, {"scope_type": "team", "scope_id": "eng"},
    {"scope_type": "person", "scope_id": "a"},
])
def test_exact_received_source_inventory_promotes_scope_without_changing_values(company, scope):
    body = daily(company, **scope)
    first = body["buckets"][0]
    assert first["coverage"] == "complete"
    assert first["recorded_spend"] == "1.30"
    assert first["included_usage_notional"] == "999.00"
    assert first["tokens"]["total_tokens"] == 2_000_202
    assert first["record_count"] == 4
    assert body["buckets"][2]["coverage"] == "partial"
    assert body["buckets"][3]["coverage"] != "complete"


def test_attested_person_zero_is_money_zero_without_inventing_token_telemetry(company):
    bucket = daily(company, scope_type="person", scope_id="a")["buckets"][1]
    assert bucket["coverage"] == "complete"
    assert bucket["recorded_spend"] == "0.00"
    assert bucket["record_count"] == 0
    assert all(value is None for value in bucket["tokens"].values())


def test_zero_only_window_preserves_the_attestation_provenance(company):
    body = daily(company, scope_type="person", scope_id="a", start_date=date(2026, 1, 2),
                 end_date_exclusive=date(2026, 1, 3))
    bucket = body["buckets"][0]
    assert bucket["coverage"] == "complete" and bucket["recorded_spend"] == "0.00"
    assert bucket["record_count"] == 0
    assert body["synthetic"] is True
    assert bucket["source_refs"]


def test_empty_scope_without_explicit_observation_never_becomes_known_zero(company):
    body = daily(company, scope_type="team", scope_id="other")
    assert all(row["recorded_spend"] is None for row in body["buckets"])
    assert all(row["coverage"] != "complete" for row in body["buckets"])


def test_native_rows_without_opted_in_source_receipt_remain_partial(company):
    body = daily(company, attached=False)
    assert body["buckets"][0]["coverage"] == "partial"
    assert body["buckets"][1]["coverage"] == "missing"
    assert body["buckets"][1]["recorded_spend"] is None


def test_provider_model_filter_does_not_inherit_unscoped_source_completeness(company):
    body = daily(company, provider="openai", model="A")
    assert body["buckets"][0]["coverage"] == "partial"
    assert body["buckets"][0]["recorded_spend"] == "0.10"


@pytest.mark.parametrize("damage", ["missing_included", "same_count_amount_change", "unexpected_row"])
def test_native_inventory_damage_revokes_completeness(company, damage):
    factory, _, _ = company
    with factory() as session:
        row = session.scalar(select(UsageRecord).where(UsageRecord.source_record_key == "api-a"))
        if damage == "missing_included":
            session.delete(session.scalar(select(UsageRecord).where(UsageRecord.source_record_key == "included")))
        elif damage == "same_count_amount_change":
            row.amount = Decimal("0.11")
        else:
            session.add(UsageRecord(id="extra", import_batch_id=row.import_batch_id,
                source_kind="northstar_billing", source_record_key="extra", source_account="ws-eng",
                team_id="eng", person_id="a", period_id="q1", occurred_at=row.occurred_at,
                created_at=row.created_at, amount=Decimal("0.50"), unit="USD",
                cost_category="direct_api", counts_toward_spend=True, value_kind="simulated"))
        session.commit()
    body = daily(company)
    assert body["buckets"][0]["coverage"] == "partial"
    assert body["buckets"][0]["recorded_spend"] == {
        "missing_included": "1.30", "same_count_amount_change": "1.31", "unexpected_row": "1.80",
    }[damage]


def test_receipt_and_day_close_cutoffs_cannot_be_bypassed_by_manifest(company):
    before = daily(company, now="2026-01-01T23:59:59Z")
    assert all(row["coverage"] != "complete" for row in before["buckets"])
    received = daily(company, now="2026-01-02T00:00:00Z")
    assert received["buckets"][0]["coverage"] == "complete"
    assert received["buckets"][1]["coverage"] != "complete"
    factory, _, _ = company
    with factory() as session:
        session.scalar(select(ImportBatch)).created_at = instant("2026-01-05T00:00:00Z")
        session.commit()
    unavailable = daily(company)
    assert all(row["coverage"] != "complete" for row in unavailable["buckets"])


@pytest.mark.parametrize("damage", ["future_availability", "wrong_revision", "count_mismatch", "unrelated_receipt"])
def test_receipt_proof_must_match_revision_counts_availability_and_native_batches(company, damage):
    def alter(snapshot):
        if damage == "future_availability":
            snapshot["coverage"][0]["available_at"] = "2026-01-05T00:00:00Z"
        elif damage == "wrong_revision":
            snapshot["company_fixture_manifest"]["revision"] = "different-manifest"
        elif damage == "count_mismatch":
            snapshot["company_fixture_manifest"]["days"][0]["posted_record_count"] -= 1
        else:
            snapshot["source_revisions"] = [{"kind": "unrelated", "source_id": "no-native-receipt"}]
    body = daily(company, transform=alter)
    assert body["buckets"][0]["coverage"] == "partial"
    assert body["buckets"][0]["recorded_spend"] == "1.30"


def test_native_change_between_receipt_and_ledger_read_revokes_completeness(company):
    factory, _, _ = company
    def remove_nonbillable_after_receipt(_snapshot):
        # A removed included row leaves dollars unchanged. Monetary equality is
        # insufficient to reuse a receipt from the earlier native revision.
        with factory() as other_session:
            row = other_session.scalar(select(UsageRecord).where(UsageRecord.source_record_key == "included"))
            other_session.delete(row)
            other_session.commit()
    body = daily(company, transform=remove_nonbillable_after_receipt)
    assert body["buckets"][0]["recorded_spend"] == "1.30"
    assert body["buckets"][0]["coverage"] == "partial"


def test_request_local_receipt_cache_does_not_survive_committed_native_deletion(company):
    session, clock = source_session(company)
    def read():
        return usage.daily_usage(session, scope_type="company", scope_id=None,
            start_date=date(2026, 1, 1), end_date_exclusive=date(2026, 1, 2),
            provider=None, model=None, clock=clock)["buckets"][0]
    try:
        assert read()["coverage"] == "complete"
        session.delete(session.scalar(select(UsageRecord).where(UsageRecord.source_record_key == "included")))
        session.commit()
        after = read()
        assert after["recorded_spend"] == Decimal("1.30")
        assert after["record_count"] == 3
        assert after["coverage"] == "partial"
    finally:
        session.close()


def test_receipt_and_daily_records_must_use_one_coherent_native_revision(company, monkeypatch):
    factory, _, _ = company
    original = usage.source_completion
    def delete_after_verification(session, now):
        receipt = original(session, now)
        with factory() as other_session:
            row = other_session.scalar(select(UsageRecord).where(UsageRecord.source_record_key == "included"))
            other_session.delete(row)
            other_session.commit()
        return receipt
    monkeypatch.setattr(usage, "source_completion", delete_after_verification)
    bucket = daily(company)["buckets"][0]
    assert bucket["recorded_spend"] == "1.30"
    # A pinned old read with all four records may remain complete. If the daily
    # query sees the deletion, its earlier inventory proof must be withdrawn.
    if bucket["record_count"] == 3:
        assert bucket["coverage"] == "partial"
    else:
        assert bucket["record_count"] == 4 and bucket["included_usage_notional"] == "999.00"


def assess(company, now, *, attached=True):
    session, clock = source_session(company, now, attached=attached)
    try:
        request = BudgetRequest(team_id="eng", period_id="q1", request_kind="team", unit="USD",
                                requested_amount=Decimal("1.00"))
        forecast = ForecastResult(provider="test", availability="available", target_period="q1",
            method_label="Isolated test", projections=[TeamProjection(team="eng", amount="2.00")])
        return budget_requests._assessment(session, request, forecast, clock=clock)
    finally:
        session.close()


def test_request_qualification_uses_receipt_for_all_closed_days_not_row_presence(company):
    # Jan 3 is only partially supplied, so its closed day restores the caveat.
    partial = assess(company, "2026-01-04T00:00:00Z")["qualification"].lower()
    assert "incomplete source coverage" in partial
    # Opt into the separately completed source variant, including its changed
    # source CSV and matching native cents, not just a metadata relabel.
    factory, source, _ = company
    ref_path = source / "backend" / "reference.json"
    reference = json.loads(ref_path.read_text())
    reference["company"]["complete_through"] = "2026-01-03"
    ref_path.write_text(json.dumps(reference))
    calendar = source / "csv" / "calendar.csv"
    calendar.write_text(calendar.read_text().replace("2026-01-03,1,0", "2026-01-03,0,0"))
    billing = source / "backend" / "billing" / "all.csv"
    billing.write_text(billing.read_text().replace("simulated,0.40,USD", "simulated,0.80,USD"))
    with factory() as session:
        session.scalar(select(UsageRecord).where(UsageRecord.source_record_key == "partial")).amount = Decimal("0.80")
        session.commit()
    qualified = assess(company, "2026-01-04T00:00:00Z")["qualification"].lower()
    assert "incomplete source coverage" not in qualified
    assert "2026-01-03" in qualified
    unattested = assess(company, "2026-01-04T00:00:00Z", attached=False)["qualification"].lower()
    assert "incomplete source coverage" in unattested


def test_request_native_total_must_match_the_attested_closed_day_total(company):
    # The fixture deliberately imports future Jan 3 usage in its Jan 2 batch.
    # The older request subtotal includes it; a Jan 2 receipt cannot attest it.
    result = assess(company, "2026-01-03T00:00:00Z")
    assert result["recorded_spend"] == "1.70"
    assert "incomplete source coverage" in result["qualification"].lower()
