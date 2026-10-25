#!/usr/bin/env python3
"""Load the generated dataset into a backend SQLite database through the backend's own services.

Run with the backend's virtual environment (Python 3.12+), from the repository root:

    backend/.venv/bin/python datagen/load_backend.py                       # -> backend/data/uber.db
    backend/.venv/bin/python datagen/load_backend.py --db /tmp/uber.db --reset
    BACKEND_DB_PATH=backend/data/uber.db backend/.venv/bin/python -m app.main   # serve it (run from backend/)

What it does, in order: planning periods (four quarters), teams, billing-account -> team mappings, one
budget envelope per quarter, every corpus document (messages and tasks, in file order), then every
billing CSV through `imports.run_import` (dedupe, period lookup and team attribution happen there).
Nothing in the backend package is modified; this script only drives its public services.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date
from pathlib import Path

from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.clock import SystemClock, UuidIdFactory  # noqa: E402
from app.db import models as m  # noqa: E402
from app.db.base import Base, create_all, make_engine, make_session_factory  # noqa: E402
from app.forecasting.persistence import ForecastStore  # noqa: E402
from app.schemas.documents import DocumentIn  # noqa: E402
from app.services import budget as budget_svc  # noqa: E402
from app.services import company as company_svc  # noqa: E402  (backend-owner edit: company record)
from app.services import corpus as corpus_svc  # noqa: E402
from app.services import imports as import_svc  # noqa: E402
from app.services import people as people_svc  # noqa: E402

SOURCE_KIND = "northstar_billing"
ACTOR = "uber-datagen"

CANONICAL_TABLES = (
    'forecast_publications', 'forecast_scenarios', 'forecast_runs', 'forecast_jobs',
    'forecast_input_snapshots', 'forecast_inputs',
    'forecast_repository_row_versions', 'forecast_repository_captures', 'forecast_schema_versions',
)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out-dir", default=str(ROOT / "datagen" / "out"), help="generator output directory")
    ap.add_argument("--db", default=str(ROOT / "backend" / "data" / "uber.db"), help="SQLite file to create or fill")
    ap.add_argument("--reset", action="store_true", help="atomically replace repository and forecast state in --db")
    ap.add_argument("--skip-spend", action="store_true", help="load reference data and corpus only")
    args = ap.parse_args(argv)

    out = Path(args.out_dir)
    ref = json.loads((out / "backend" / "reference.json").read_text(encoding="utf-8"))
    db_path = Path(args.db)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = make_engine(db_path)
    store = ForecastStore(db_path)
    clock, ids = SystemClock(), UuidIdFactory()
    t0 = time.time()
    try:
        # Fence the entire load, including gaps between phase/import commits.
        # Workers use the shared side of this cross-process maintenance lock.
        with store.operation(exclusive=True):
            if args.reset:
                with engine.connect() as connection:
                    connection.exec_driver_sql('BEGIN EXCLUSIVE')
                    try:
                        for table in CANONICAL_TABLES:
                            connection.exec_driver_sql(f'DROP TABLE IF EXISTS {table}')
                        Base.metadata.drop_all(connection)
                        Base.metadata.create_all(connection)
                        store.migrate(connection=connection.connection.driver_connection)
                        # Loader commits remain savepoints until the whole reset
                        # succeeds. Rejected files restore the preceding company.
                        with Session(bind=connection, join_transaction_mode='create_savepoint') as session:
                            result = _load_dataset(session, out, ref, db_path, args.skip_spend, clock, ids)
                        if result:
                            connection.rollback()
                            print('load rejected; reset rolled back and the previous database was restored')
                        else:
                            connection.commit()
                    except BaseException:
                        connection.rollback()
                        raise
            else:
                create_all(engine)
                # Offline bulk loading deliberately has no forecast_store session
                # binding: do not archive the full 331k-row history per CSV. App
                # startup captures the completed data at its actual receipt time.
                with make_session_factory(engine)() as session:
                    result = _load_dataset(session, out, ref, db_path, args.skip_spend, clock, ids)
    finally:
        engine.dispose()
    if result == 0:
        print(f"done in {time.time() - t0:.1f}s -> {db_path}")
    return result


def _load_dataset(session, out, ref, db_path, skip_spend, clock, ids):
    # Backend-owner edit (minimal): store reference.json's company so /api/meta and /compat/api/company
    # name it ("Uber (simulated)") without env vars. BACKEND_COMPANY_ID/NAME still override at serve time.
    # Written before the "already loaded" check so an existing DB gets the record too. A reference without
    # a company id (e.g. a minimal test dataset) leaves the record untouched.
    co = ref.get("company") or {}
    if co.get("id") and co.get("name"):
        company_svc.set_profile(session, company_id=co["id"], name=co["name"], is_simulated=co.get("simulated", True),
                                as_of=date.fromisoformat(co["as_of"]) if co.get("as_of") else None, clock=clock)
        session.commit()
    if session.get(m.PlanningPeriod, ref["periods"][0]["id"]) is not None:
        print(f"{db_path} already holds the dataset (period {ref['periods'][0]['id']} exists); use --reset to reload")
        return 0
    now = clock.now()
    for p in ref["periods"]:
        session.add(m.PlanningPeriod(id=p["id"], label=p["label"], starts_on=date.fromisoformat(p["starts_on"]),
                                     ends_on=date.fromisoformat(p["ends_on"]), created_at=now))
    session.add_all([m.Team(id=t["id"], name=t["name"], created_at=now) for t in ref["teams"]])
    session.flush()
    for kind, accounts in ref["team_mappings"].items():
        for account, team in sorted(accounts.items()):
            session.add(m.TeamMapping(id=ids.new_id("map_"), created_at=now, source_kind=kind, source_account=account, team_id=team,
                                      effective_from=date.fromisoformat(ref["periods"][0]["starts_on"]), created_by=ACTOR))
    session.flush()
    # People before corpus and spend: export emails and document person tags resolve against them.
    people_svc.create_people(session, ref["people"], clock=clock)
    for period_id, allocations in ref["budgets"].items():
        budget_svc.create_envelope(session, period_id=period_id, unit="USD", allocations=allocations, clock=clock, ids=ids)
    session.commit()
    print(f"reference: {len(ref['periods'])} periods, {len(ref['teams'])} teams, {len(ref['people'])} people, "
          f"{sum(len(a) for a in ref['team_mappings'].values())} mappings, {len(ref['budgets'])} budget envelopes")

    docs = sorted((out / "backend" / "corpus").glob("*.md"))
    created = dup = 0
    for path in docs:
        data = DocumentIn(**corpus_svc.parse_markdown_document(path.read_text(encoding="utf-8")))
        res = corpus_svc.ingest_document(session, data, clock=clock, ids=ids)
        created += int(res.created)
        dup += int(not res.created)
    session.commit()
    print(f"corpus: {created} documents ingested, {dup} duplicates skipped")

    if not skip_spend:
        total_records = total_unmapped = 0
        for path in sorted((out / "backend" / "billing").glob("*.csv")):
            outcome = import_svc.run_import(session, source_kind=SOURCE_KIND, raw=path.read_bytes(), filename=path.name, actor_id=ACTOR,
                                            clock=clock, ids=ids, source_label=f"{ref['company']['name']} billing export")
            session.commit()
            b = outcome.batch
            codes = sorted({w["code"] for w in (b.error_details or {}).get("warnings", [])}) if b.error_details else []
            errs = (b.error_details or {}).get("errors", []) if b.error_details else []
            stats = (b.error_details or {}).get("stats", {}) if b.error_details else {}
            print(f"import {path.name}: {b.status} records={b.record_count} unmapped={b.unmapped_record_count} "
                  f"people_resolved={stats.get('person_resolved', '?')} warnings={codes or '-'}"
                  + (f" ERRORS={errs[:3]}" if errs else ""))
            total_records += b.record_count
            total_unmapped += b.unmapped_record_count
            if b.status == "failed":
                return 1
        print(f"spend: {total_records} usage records, {total_unmapped} unmapped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
