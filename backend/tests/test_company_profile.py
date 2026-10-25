"""Company identity is persisted independently of the financial ledger and forecast inputs."""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from budget_helpers import seed_budget


@pytest.fixture(autouse=True)
def clear_company_overrides(monkeypatch):
    monkeypatch.delenv("BACKEND_COMPANY_ID", raising=False)
    monkeypatch.delenv("BACKEND_COMPANY_NAME", raising=False)


def set_profile(session, clock, **changes):
    from app.services import company

    return company.set_profile(session, company_id=changes.pop("company_id", "acme"),
                               name=changes.pop("name", "Acme Engineering"),
                               is_simulated=changes.pop("is_simulated", True),
                               as_of=changes.pop("as_of", date(2026, 10, 24)), clock=clock, **changes)


def test_empty_meta_reports_default_company_without_creating_rows(client, session):
    response = client.get("/api/meta")
    assert response.status_code == 200, response.text
    metadata = response.json()
    assert metadata["company"] == {
        "id": "northstar", "name": "Northstar Software", "as_of": None,
        "is_simulated": True, "source": "default",
        "detail": "no company_profile record in this database; showing the Northstar default",
    }
    assert metadata["period"] is None and metadata["unit"] == "USD"
    from app.db.models import CompanyProfile
    assert session.scalar(select(func.count()).select_from(CompanyProfile)) == 0


def test_persisted_company_is_read_after_reopening_session_and_preserves_native_finances(app, client, session, clock):
    seed_budget(app)
    before_budget = client.get("/api/budget").json()
    before_period = client.get("/api/meta").json()["period"]
    set_profile(session, clock)
    session.commit()
    session.close()
    metadata = client.get("/api/meta").json()
    assert metadata["company"] == {
        "id": "acme", "name": "Acme Engineering", "as_of": "2026-10-24",
        "is_simulated": True, "source": "db",
        "detail": "company_profile record written by the data loader",
    }
    assert metadata["period"] == before_period
    assert metadata["unit"] == "USD"
    assert client.get("/api/budget").json() == before_budget
    assert client.get("/api/proposals").json() == []
    assert client.get("/api/decisions").json() == []


def test_environment_override_is_per_field_and_changes_without_restart(client, session, clock, monkeypatch):
    set_profile(session, clock)
    session.commit()
    monkeypatch.setenv("BACKEND_COMPANY_NAME", "  Another Company  ")
    metadata = client.get("/api/meta").json()["company"]
    assert (metadata["id"], metadata["name"], metadata["source"]) == ("acme", "Another Company", "env")
    monkeypatch.setenv("BACKEND_COMPANY_ID", "another")
    assert client.get("/api/meta").json()["company"]["id"] == "another"
    monkeypatch.setenv("BACKEND_COMPANY_NAME", "  ")
    metadata = client.get("/api/meta").json()["company"]
    assert (metadata["id"], metadata["name"], metadata["source"]) == ("another", "Acme Engineering", "db")
    from app.services import company
    assert company.resolve(session, env={})["id"] == "acme"


def test_profile_update_reuses_single_row_and_rolls_back_with_callers_transaction(session, clock):
    from app.db.models import CompanyProfile
    from app.services import company

    first = set_profile(session, clock)
    session.commit()
    replacement = set_profile(session, clock, company_id="other", name="Other", is_simulated=False, as_of=None)
    assert replacement.slot == first.slot == 1
    assert session.scalar(select(func.count()).select_from(CompanyProfile)) == 1
    assert company.resolve(session, env={})["is_simulated"] is False
    session.rollback()
    assert company.resolve(session, env={})["id"] == "acme"
    session.add(CompanyProfile(slot=2, company_id="second", name="Second", is_simulated=True))
    with pytest.raises(IntegrityError):
        session.flush()


@pytest.mark.parametrize("changes", [
    {"company_id": "   "}, {"company_id": "x" * 65}, {"company_id": 42},
    {"name": "\t"}, {"name": "x" * 201}, {"name": None},
    {"is_simulated": "false"}, {"is_simulated": 1},
    {"as_of": "2026-10-24"}, {"as_of": datetime(2026, 10, 24, tzinfo=timezone.utc)},
])
def test_invalid_profile_update_is_rejected_before_changing_saved_identity(session, clock, changes):
    from app.services import company

    set_profile(session, clock)
    session.commit()
    before = company.resolve(session, env={})
    with pytest.raises(ValueError):
        set_profile(session, clock, **changes)
    assert company.resolve(session, env={}) == before


@pytest.mark.parametrize(("is_simulated", "status"), [(True, "simulated"), (False, "real")])
def test_profile_provenance_is_truthful_even_when_id_retains_northstar(client, session, clock, is_simulated, status):
    set_profile(session, clock, company_id="northstar", name="Northstar Operations", is_simulated=is_simulated)
    session.commit()
    metadata = client.get("/api/meta").json()
    data_label = next(row for row in metadata["real_vs_simulated"]
                      if row["component"] == "northstar_spend_budgets_corpus")
    assert data_label["status"] == status
    assert "Northstar Operations" in data_label["detail"]
    assert metadata["company"]["is_simulated"] is is_simulated


def test_northstar_seed_persists_default_company_profile(seeded, client):
    metadata = client.get("/api/meta").json()
    assert metadata["company"] == {
        "id": "northstar", "name": "Northstar Software", "as_of": None,
        "is_simulated": True, "source": "db",
        "detail": "company_profile record written by the data loader",
    }
    data_label = next(row for row in metadata["real_vs_simulated"]
                      if row["component"] == "northstar_spend_budgets_corpus")
    assert data_label["status"] == "simulated"
    assert data_label["detail"].startswith("fictional Northstar Software example")


def test_idempotent_seed_does_not_overwrite_loaded_company_identity(seeded, session, clock):
    from app.seed.northstar import seed
    from app.services import company

    set_profile(session, clock, name="Loaded Company")
    session.commit()
    assert seed(session, clock=clock, ids=seeded.state.id_factory) is False
    assert company.resolve(session, env={})["name"] == "Loaded Company"
