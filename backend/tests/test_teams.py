"""Team mapping: provider accounts never imply ownership; mappings are explicit and re-resolvable."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.db import models as m
from reference_data import ANALYST, IMPORTER, seed_reference, upload

CSV = ("record_id,occurred_at,source_account,cost_category,amount\n"
       "a1,2026-10-02,shared-key-7,direct_api,100.00\n"
       "a2,2026-11-15,shared-key-7,direct_api,50.00\n")


@pytest.fixture(autouse=True)
def _ref(session):
    seed_reference(session)


def test_list_teams_and_mappings(client):
    assert [t["id"] for t in client.get("/api/teams").json()] == ["engineering", "product", "research"]
    assert len(client.get("/api/team-mappings").json()) == 4


def test_mapping_change_reattributes_records(client, session):
    upload(client, CSV)
    assert {r.team_id for r in session.scalars(select(m.UsageRecord))} == {None}
    r = client.put("/api/team-mappings", headers=ANALYST, json={
        "source_kind": "northstar_billing", "source_account": "shared-key-7",
        "team_id": "engineering", "effective_from": "2026-01-01"})
    assert r.status_code == 200
    assert r.json()["reattributed_records"] == 2
    session.expire_all()
    assert {r.team_id for r in session.scalars(select(m.UsageRecord))} == {"engineering"}
    assert client.get("/api/coverage").json()["unattributed"]["record_count"] == 0


def test_effective_dated_mapping_splits_by_date(client, session):
    upload(client, CSV)
    for team, day in (("engineering", "2026-01-01"), ("product", "2026-11-01")):
        client.put("/api/team-mappings", headers=ANALYST, json={
            "source_kind": "northstar_billing", "source_account": "shared-key-7",
            "team_id": team, "effective_from": day})
    session.expire_all()
    got = {r.source_record_key: r.team_id for r in session.scalars(select(m.UsageRecord))}
    assert got == {"a1": "engineering", "a2": "product"}


def test_mapping_effective_after_record_leaves_it_unattributed(client, session):
    client.put("/api/team-mappings", headers=ANALYST, json={
        "source_kind": "northstar_billing", "source_account": "shared-key-7",
        "team_id": "research", "effective_from": "2026-11-01"})
    upload(client, CSV)
    got = {r.source_record_key: r.team_id for r in session.scalars(select(m.UsageRecord))}
    assert got == {"a1": None, "a2": "research"}


def test_mapping_to_unknown_team_rejected(client):
    r = client.put("/api/team-mappings", headers=ANALYST, json={
        "source_kind": "northstar_billing", "source_account": "x", "team_id": "marketing",
        "effective_from": "2026-01-01"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "unknown_team"


def test_mapping_requires_finance_role(client):
    r = client.put("/api/team-mappings", headers=IMPORTER, json={
        "source_kind": "northstar_billing", "source_account": "x", "team_id": "research",
        "effective_from": "2026-01-01"})
    assert r.status_code == 403 and r.json()["error"]["code"] == "role_forbidden"
