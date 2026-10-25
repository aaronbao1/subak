"""Company record: company_profile row (seed / datagen loader), env override, default fallback."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.db.models import CompanyProfile, PlanningPeriod
from app.services import company as company_svc

API = "/compat/api"
REPO = Path(__file__).resolve().parents[2]


def _set_uber(app) -> None:
    s = app.state.session_factory()
    try:
        company_svc.set_profile(s, company_id="uber-sim", name="Uber (simulated)", is_simulated=True,
                                as_of=date(2026, 10, 24), clock=app.state.clock)
        s.commit()
    finally:
        s.close()


def test_seed_writes_northstar_profile(seeded):
    with TestClient(seeded) as c:
        meta = c.get("/api/meta").json()
        assert meta["company"] == {"id": "northstar", "name": "Northstar Software", "as_of": None,
                                   "is_simulated": True, "source": "db",
                                   "detail": "company_profile record written by the data loader"}
        co = c.get(f"{API}/company").json()
        assert (co["id"], co["name"]) == ("northstar", "Northstar Software")
        # Northstar labels are unchanged.
        assert meta["real_vs_simulated"][0]["detail"].startswith("fictional Northstar Software example")


def test_db_record_names_another_dataset(seeded):
    _set_uber(seeded)
    with TestClient(seeded) as c:
        meta = c.get("/api/meta").json()
        assert meta["company"]["name"] == "Uber (simulated)" and meta["company"]["as_of"] == "2026-10-24"
        assert meta["company"]["source"] == "db"
        row = meta["real_vs_simulated"][0]
        assert row["status"] == "simulated" and "Uber (simulated) dataset" in row["detail"]
        co = c.get(f"{API}/company").json()
        assert (co["id"], co["name"], co["isDemo"]) == ("uber-sim", "Uber (simulated)", True)


def test_env_overrides_db_per_field(seeded, monkeypatch):
    _set_uber(seeded)
    monkeypatch.setenv("BACKEND_COMPANY_NAME", "Acme Override")
    with TestClient(seeded) as c:
        co = c.get(f"{API}/company").json()
        assert (co["id"], co["name"]) == ("uber-sim", "Acme Override")  # id still from the row
        assert c.get("/api/meta").json()["company"]["source"] == "env"
        monkeypatch.setenv("BACKEND_COMPANY_ID", "acme")
        assert c.get(f"{API}/company").json()["id"] == "acme"


def test_no_row_falls_back_to_default_with_message(app):
    s = app.state.session_factory()
    try:
        s.add(PlanningPeriod(id="2026-P1", label="P", starts_on=date(2026, 10, 1), ends_on=date(2026, 12, 31)))
        s.commit()
    finally:
        s.close()
    with TestClient(app) as c:
        meta = c.get("/api/meta").json()
        assert meta["company"]["source"] == "default" and meta["company"]["is_simulated"] is True
        assert "no company_profile record" in meta["company"]["detail"]
        assert c.get(f"{API}/company").json()["name"] == "Northstar Software"


def test_unseeded_meta_still_answers(client):
    assert client.get("/api/meta").json()["company"]["source"] == "default"
    assert client.get(f"{API}/company").status_code == 503


def test_set_profile_replaces_single_row(session, clock):
    company_svc.set_profile(session, company_id="a", name="A", is_simulated=True, clock=clock)
    company_svc.set_profile(session, company_id="b", name="B", is_simulated=False, clock=clock)
    rows = session.query(CompanyProfile).all()
    assert [(r.slot, r.company_id, r.name, r.is_simulated) for r in rows] == [(1, "b", "B", False)]
    with pytest.raises(ValueError):
        company_svc.set_profile(session, company_id=" ", name="X", is_simulated=True, clock=clock)
    session.add(CompanyProfile(slot=2, company_id="c", name="C", is_simulated=True))
    with pytest.raises(IntegrityError):
        session.flush()


def test_datagen_loader_writes_reference_company(tmp_path):
    """Drives the real loader on a tiny reference.json (no spend, no corpus)."""
    out = tmp_path / "out"
    (out / "backend" / "corpus").mkdir(parents=True)
    ref = {"company": {"id": "uber-sim", "name": "Uber (simulated)", "simulated": True, "as_of": "2026-10-24"},
           "periods": [{"id": "2026-Q4", "label": "Q4", "starts_on": "2026-10-01", "ends_on": "2026-12-31"}],
           "teams": [{"id": "rides", "name": "Rides"}], "team_mappings": {}, "people": [], "budgets": {}}
    (out / "backend" / "reference.json").write_text(json.dumps(ref), encoding="utf-8")
    db = tmp_path / "uber.db"
    res = subprocess.run([sys.executable, str(REPO / "datagen" / "load_backend.py"), "--out-dir", str(out),
                          "--db", str(db), "--reset", "--skip-spend"], capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    from app.db.base import make_engine, make_session_factory

    engine = make_engine(db)
    try:
        s = make_session_factory(engine)()
        info = company_svc.resolve(s, env={})
        assert (info["id"], info["name"], info["as_of"], info["source"]) == (
            "uber-sim", "Uber (simulated)", date(2026, 10, 24), "db")
        s.close()
    finally:
        engine.dispose()
