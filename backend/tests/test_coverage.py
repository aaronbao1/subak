"""Acceptance check 3b: missing data remains visibly incomplete."""

from __future__ import annotations

import pytest

from reference_data import NORTHSTAR_CSV, seed_reference, upload


@pytest.fixture(autouse=True)
def _ref(session):
    seed_reference(session)


def test_no_records_reports_missing_everywhere(client):
    cov = client.get("/api/coverage").json()
    assert cov["company"]["status"] == "missing"
    assert {t["status"] for t in cov["teams"]} == {"missing"}


def test_complete_when_every_team_has_mapped_records(client):
    upload(client, NORTHSTAR_CSV)
    cov = client.get("/api/coverage?period=2026-P1").json()
    assert cov["company"]["status"] == "complete"
    assert cov["company"]["record_count"] == 5
    assert cov["data_labels"] == {"simulated": True, "real_sample": False}
    assert any("period in progress" in n for n in cov["company"]["notes"])
    assert cov["sources"][0]["source_kind"] == "northstar_billing"


def test_team_without_records_reports_missing_not_zero_complete(client):
    text = "\n".join(l for l in NORTHSTAR_CSV.splitlines() if "ws-product" not in l) + "\n"
    upload(client, text)
    cov = client.get("/api/coverage").json()
    product = next(t for t in cov["teams"] if t["team"] == "product")
    assert product["status"] == "missing" and product["record_count"] == 0
    assert cov["company"]["status"] == "partial"
    assert any("product" in n for n in cov["company"]["notes"])


def test_unmapped_account_goes_to_unattributed_with_partial_coverage(client):
    upload(client, NORTHSTAR_CSV + "u1,2026-10-10,legacy-shared-key,,,direct_api,,750.00,USD,,,\n")
    cov = client.get("/api/coverage").json()
    assert cov["company"]["status"] == "partial"
    assert cov["company"]["unmapped_records"] == 1
    assert cov["unattributed"]["recorded_spend"] == "750.00"
    assert cov["unattributed"]["source_accounts"] == [
        {"source": "northstar_billing:legacy-shared-key", "record_count": 1}]
    assert all(t["status"] == "partial" for t in cov["teams"])
    assert "unattributed" not in {t["team"] for t in cov["teams"]}


def test_unknown_period_404(client):
    r = client.get("/api/coverage?period=2031-P9")
    assert r.status_code == 404 and r.json()["error"]["code"] == "unknown_period"


def test_team_with_billing_plus_tokens_stays_complete(client):
    from reference_data import codex_lines, usage
    upload(client, NORTHSTAR_CSV)
    cov_before = client.get("/api/coverage").json()
    assert cov_before["company"]["status"] == "complete"
    r = upload(client, codex_lines("only-tokens", [("2026-10-10T10:00:00Z", usage(500, 0, 50))]),
               source_kind="codex_sessions", filename="s.jsonl", source_account="codex-research-laptops")
    assert r.status_code == 201, r.text
    research = next(t for t in client.get("/api/coverage").json()["teams"] if t["team"] == "research")
    assert research["status"] == "complete" and research["spend_record_count"] >= 1  # it still has billing


def test_tokens_only_team_reports_partial_not_complete_zero(client):
    from reference_data import codex_lines, usage
    text = "\n".join(l for l in NORTHSTAR_CSV.splitlines() if "ws-research" not in l) + "\n"
    upload(client, text)
    r = upload(client, codex_lines("only-tokens", [("2026-10-10T10:00:00Z", usage(500, 0, 50))]),
               source_kind="codex_sessions", filename="s.jsonl", source_account="codex-research-laptops")
    assert r.status_code == 201, r.text
    cov = client.get("/api/coverage").json()
    research = next(t for t in cov["teams"] if t["team"] == "research")
    assert research["record_count"] == 1 and research["spend_record_count"] == 0
    assert research["status"] == "partial"
    assert any("not a confirmed zero" in n for n in research["notes"])
    assert cov["company"]["status"] == "partial"
