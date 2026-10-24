"""Acceptance check 1: importing the same source twice must not double spending. Plus parser rules."""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.db import models as m
from reference_data import ANALYST, DROID, IMPORTER, NORTHSTAR_CSV, seed_reference, upload


@pytest.fixture(autouse=True)
def _ref(session):
    seed_reference(session)


def spend_by_team(session) -> dict:
    totals: dict = defaultdict(lambda: Decimal("0.00"))
    session.expire_all()
    for r in session.scalars(select(m.UsageRecord)):
        if r.counts_toward_spend and r.amount is not None:
            totals[r.team_id] += r.amount
    return dict(totals)


def test_first_import_reports_counts_and_spend(client, session):
    r = upload(client, NORTHSTAR_CSV)
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "imported"
    assert body["record_count"] == 5
    assert body["spend_added"] == "95000.00"
    assert body["unmapped_record_count"] == 0
    assert spend_by_team(session) == {
        "research": Decimal("45000.00"), "product": Decimal("20000.00"), "engineering": Decimal("30000.00"),
    }


def test_reimport_same_file_is_duplicate_and_totals_unchanged(client, session):
    first = upload(client, NORTHSTAR_CSV).json()
    before = spend_by_team(session)
    r = upload(client, NORTHSTAR_CSV, filename="renamed.csv")
    assert r.status_code == 200
    dup = r.json()
    assert dup["status"] == "duplicate"
    assert dup["duplicate_of_batch_id"] == first["id"]
    assert dup["record_count"] == 0
    assert dup["warnings"][0]["code"] == "duplicate_file"
    assert spend_by_team(session) == before
    assert session.query(m.UsageRecord).count() == 5
    # both attempts are kept for audit
    statuses = [b["status"] for b in client.get("/api/imports").json()]
    assert statuses == ["imported", "duplicate"]


def test_overlapping_file_with_new_hash_dedupes_by_record_key(client, session):
    upload(client, NORTHSTAR_CSV)
    overlap = NORTHSTAR_CSV + "ns-006,2026-10-09,ws-product,openai,gpt,billable_overage,,1500.00,USD,,,\n"
    body = upload(client, overlap).json()
    assert body["status"] == "imported"
    assert body["record_count"] == 1
    assert body["skipped_duplicate_records"] == 5
    assert spend_by_team(session)["product"] == Decimal("21500.00")


def test_restated_record_key_with_different_values_is_skipped_and_reported(client, session):
    upload(client, NORTHSTAR_CSV)
    restated = NORTHSTAR_CSV.replace("ns-005,2026-10-08,ws-engineering,anthropic,claude,direct_api,,30000.00",
                                     "ns-005,2026-10-08,ws-engineering,anthropic,claude,direct_api,,99999.00")
    body = upload(client, restated).json()
    assert body["record_count"] == 0
    assert body["stats"]["conflicting_records"] == 1
    assert any(w["code"] == "record_key_conflict" for w in body["warnings"])
    assert spend_by_team(session)["engineering"] == Decimal("30000.00")


def test_json_import_equivalent_to_csv(client, session):
    payload = """{"records": [
      {"record_id": "j-1", "occurred_at": "2026-10-02T09:30:00Z", "source_account": "ws-research",
       "cost_category": "direct_api", "amount": "12.50", "value_kind": "reported"},
      {"record_id": "j-2", "occurred_at": "2026-10-02", "source_account": "ws-product",
       "cost_category": "unpriced_usage", "input_tokens": 1200}
    ]}"""
    body = upload(client, payload, filename="export.json").json()
    assert body["status"] == "imported" and body["record_count"] == 2
    recs = {r.source_record_key: r for r in session.scalars(select(m.UsageRecord))}
    assert recs["j-1"].value_kind == "reported" and recs["j-1"].amount == Decimal("12.50")
    assert recs["j-2"].value_kind == "simulated" and recs["j-2"].amount is None
    assert recs["j-2"].counts_toward_spend is False


def test_cost_category_and_value_kind_preserved(client, session):
    upload(client, NORTHSTAR_CSV)
    recs = {r.source_record_key: r for r in session.scalars(select(m.UsageRecord))}
    assert recs["ns-001"].cost_category == "subscription_fee" and recs["ns-001"].counts_toward_spend
    inc = recs["ns-003"]
    assert inc.cost_category == "included_usage"
    assert inc.counts_toward_spend is False
    assert inc.amount is None and inc.notional_value == Decimal("3000.00")
    assert recs["ns-004"].cost_category == "billable_overage"
    assert {r.value_kind for r in recs.values()} == {"simulated"}


def _fails_with(client, csv_text: str, code: str, **kw):
    r = upload(client, csv_text, **kw)
    assert r.status_code == 422, r.text
    err = r.json()["error"]
    assert err["code"] == "import_failed"
    codes = [e["code"] for e in err["details"]["batch"]["errors"]]
    assert code in codes, codes
    return err


HEADER = "record_id,occurred_at,source_account,cost_category,amount\n"


@pytest.mark.parametrize("row,code", [
    ("x1,2026-10-02,ws-research,included_usage,10.00", "included_usage_with_charge"),
    ("x1,2026-10-02,ws-research,unpriced_usage,1.00", "unpriced_usage_with_amount"),
    ("x1,2026-10-02,ws-research,direct_api,", "amount_required"),
    ("x1,2026-10-02,ws-research,direct_api,1.005", "too_many_decimals"),
    ("x1,2026-10-02,ws-research,direct_api,-5.00", "negative_amount"),
    ("x1,2026-10-02,ws-research,api_stuff,5.00", "unknown_cost_category"),
    ("x1,2026-10-02T10:00:00,ws-research,direct_api,5.00", "timezone_required"),
    ("x1,yesterday,ws-research,direct_api,5.00", "invalid_timestamp"),
    (",2026-10-02,ws-research,direct_api,5.00", "record_id_required"),
])
def test_invalid_row_fails_whole_batch(client, session, row, code):
    _fails_with(client, HEADER + "ok1,2026-10-02,ws-research,direct_api,5.00\n" + row + "\n", code)
    assert session.query(m.UsageRecord).count() == 0


def test_json_float_amount_rejected(client, session):
    payload = '[{"record_id": "f", "occurred_at": "2026-10-02", "source_account": "ws-research",' \
              ' "cost_category": "direct_api", "amount": 10.5}]'
    _fails_with(client, payload, "float_not_allowed", filename="x.json")


def test_failed_batch_can_be_retried_after_fix(client, session):
    bad = HEADER + "x1,2026-10-02,ws-research,direct_api,abc\n"
    _fails_with(client, bad, "invalid_amount")
    r = upload(client, HEADER + "x1,2026-10-02,ws-research,direct_api,5.00\n")
    assert r.status_code == 201
    # and re-posting the identical bad file again is still a failure, not a duplicate
    _fails_with(client, bad, "invalid_amount")


def test_conflicting_duplicate_record_id_in_file_fails(client):
    text = HEADER + "x1,2026-10-02,ws-research,direct_api,5.00\nx1,2026-10-02,ws-research,direct_api,6.00\n"
    _fails_with(client, text, "conflicting_duplicate_record_id")


def test_identical_repeated_row_in_file_counted_once(client, session):
    text = HEADER + "x1,2026-10-02,ws-research,direct_api,5.00\nx1,2026-10-02,ws-research,direct_api,5.00\n"
    body = upload(client, text).json()
    assert body["record_count"] == 1
    assert any(w["code"] == "duplicate_row_in_file" for w in body["warnings"])


def test_team_column_is_ignored_never_trusted(client, session):
    text = "record_id,occurred_at,source_account,cost_category,amount,team\n" \
           "t1,2026-10-02,shared-key-7,direct_api,5.00,research\n"
    body = upload(client, text).json()
    assert any(w["code"] == "team_column_ignored" for w in body["warnings"])
    rec = session.scalars(select(m.UsageRecord)).one()
    assert rec.team_id is None
    assert body["unmapped_record_count"] == 1
    assert body["unmapped_accounts"] == {"shared-key-7": 1}


def test_record_outside_planning_periods_is_skipped_with_warning(client, session):
    text = HEADER + "o1,2026-09-15,ws-research,direct_api,5.00\no2,2026-10-15,ws-research,direct_api,7.00\n"
    body = upload(client, text).json()
    assert body["record_count"] == 1
    assert body["stats"]["out_of_period_skipped"] == 1
    assert any(w["code"] == "outside_known_periods" and w["rows"] == [2] for w in body["warnings"])


@pytest.mark.parametrize("raw,code", [(b"", "empty_file"), (b"\xff\xfe\x00bad", "invalid_encoding")])
def test_empty_or_non_utf8_file_fails(client, raw, code):
    _fails_with(client, raw, code)


def test_missing_required_column(client):
    _fails_with(client, "record_id,occurred_at\nx,2026-10-02\n", "missing_columns")


def test_utf8_bom_and_crlf_accepted(client):
    text = "﻿" + (HEADER + "b1,2026-10-02,ws-research,direct_api,5.00\n").replace("\n", "\r\n")
    assert upload(client, text).status_code == 201


def test_unknown_source_kind_422(client):
    r = upload(client, NORTHSTAR_CSV, source_kind="mystery")
    assert r.status_code == 422 and r.json()["error"]["code"] == "unknown_source_kind"


def test_source_account_override_not_allowed_for_billing(client):
    r = upload(client, NORTHSTAR_CSV, source_account="ws-research")
    assert r.json()["error"]["code"] == "source_account_not_allowed"


def test_import_requires_importer_or_finance_role(client):
    assert upload(client, NORTHSTAR_CSV, headers=DROID).json()["error"]["code"] == "role_forbidden"
    assert client.post("/api/imports", data={"source_kind": "northstar_billing"},
                       files={"file": ("a.csv", b"x", "text/csv")}).status_code == 401
    assert upload(client, NORTHSTAR_CSV, headers=ANALYST).status_code == 201


def test_import_batch_provenance_endpoints(client):
    created = upload(client, NORTHSTAR_CSV, source_label="Northstar October export").json()
    got = client.get(f"/api/imports/{created['id']}").json()
    assert got["source_label"] == "Northstar October export"
    assert got["imported_by"] == IMPORTER["X-Actor-Id"]
    assert client.get("/api/imports/nope").status_code == 404


def test_file_too_large_rejected(client, monkeypatch):
    from app.services import imports
    monkeypatch.setattr(imports, "MAX_IMPORT_BYTES", 10)
    r = upload(client, NORTHSTAR_CSV)
    assert r.status_code == 413 and r.json()["error"]["code"] == "file_too_large"


def test_concurrent_identical_import_race_becomes_duplicate(app, session, monkeypatch):
    """A concurrent identical import that passes the hash check before the winner commits hits the
    partial unique index; it is retried and becomes a duplicate instead of a 500 or a double count."""
    from app.services import imports

    winner, loser = app.state.session_factory(), app.state.session_factory()
    kw = dict(source_kind="northstar_billing", raw=NORTHSTAR_CSV.encode(), filename="a.csv",
              actor_id="i", clock=app.state.clock)
    imports.import_and_commit(winner, ids=_PrefixIds("w"), **kw)

    real = imports.find_imported_batch
    calls = {"n": 0}

    def stale_first_read(*a):
        calls["n"] += 1
        return None if calls["n"] == 1 else real(*a)

    monkeypatch.setattr(imports, "find_imported_batch", stale_first_read)
    out = imports.import_and_commit(loser, ids=_PrefixIds("l"), **kw)
    assert calls["n"] == 2
    assert out.batch.status == "duplicate"
    assert loser.query(m.UsageRecord).count() == 5
    winner.close()
    loser.close()


class _PrefixIds:
    def __init__(self, p):
        self.p, self.n = p, 0

    def new_id(self, prefix=""):
        self.n += 1
        return f"{self.p}_{prefix}{self.n}"
