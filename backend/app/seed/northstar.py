"""Seed the fictional Northstar Software example (all values simulated).

- Period 2026-P1 (2026-10-01..2026-12-31), teams research / product / engineering.
- Explicit team mappings for the simulated billing workspaces (a provider account never implies a team).
- Budget v1: research 60k, product 80k, engineering 60k (envelope 200k).
- Spend imported through the normal import pipeline from `spend/northstar_export.csv`:
  research 45k, product 20k, engineering 30k (95k); included usage is notional only.
- The six-document corpus in `corpus/`, ingested in authored order so supersedes links resolve.

Seeding is idempotent: an already-seeded database is left untouched.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.clock import Clock, IdFactory
from app.db import models as m
from app.schemas.documents import DocumentIn
from app.services import budget as budget_svc
from app.services import corpus as corpus_svc
from app.services import imports as import_svc

HERE = Path(__file__).resolve().parent
CORPUS_DIR = HERE / "corpus"
SPEND_FILE = HERE / "spend" / "northstar_export.csv"

PERIOD_ID = "2026-P1"
PERIOD = {"id": PERIOD_ID, "label": "Northstar planning period", "starts_on": date(2026, 10, 1),
          "ends_on": date(2026, 12, 31)}
TEAMS = {"research": "Research", "product": "Product", "engineering": "Engineering"}
MAPPINGS = {
    "northstar_billing": {"ws-research": "research", "ws-product": "product", "ws-engineering": "engineering"},
    "codex_sessions": {"codex-research-laptops": "research"},
}
INITIAL_ALLOCATIONS = {"research": "60000.00", "product": "80000.00", "engineering": "60000.00"}
SEED_ACTOR = "seed"


def is_seeded(session: Session) -> bool:
    return session.get(m.PlanningPeriod, PERIOD_ID) is not None


def seed_reference(session: Session, *, clock: Clock, ids: IdFactory) -> None:
    now = clock.now()
    session.add(m.PlanningPeriod(created_at=now, **PERIOD))
    session.add_all([m.Team(id=t, name=n, created_at=now) for t, n in TEAMS.items()])
    session.flush()
    for kind, accounts in MAPPINGS.items():
        for account, team in sorted(accounts.items()):
            session.add(m.TeamMapping(id=ids.new_id("map_"), created_at=now, source_kind=kind,
                                      source_account=account, team_id=team, effective_from=date(2026, 1, 1),
                                      created_by=SEED_ACTOR))
    session.flush()


def seed_corpus(session: Session, *, clock: Clock, ids: IdFactory) -> list[m.CorpusDocument]:
    docs = []
    for path in sorted(CORPUS_DIR.glob("*.md")):
        data = DocumentIn(**corpus_svc.parse_markdown_document(path.read_text(encoding="utf-8")))
        docs.append(corpus_svc.ingest_document(session, data, clock=clock, ids=ids).document)
    return docs


def seed_spend(session: Session, *, clock: Clock, ids: IdFactory):
    outcome = import_svc.run_import(
        session, source_kind="northstar_billing", raw=SPEND_FILE.read_bytes(), filename=SPEND_FILE.name,
        actor_id=SEED_ACTOR, clock=clock, ids=ids, source_label="Northstar billing export (simulated)",
    )
    if outcome.batch.status != "imported":  # pragma: no cover - the seed file is fixed
        raise RuntimeError(f"seed spend import failed: {outcome.batch.error_details}")
    return outcome.batch


def seed(session: Session, *, clock: Clock, ids: IdFactory, include_spend: bool = True,
         include_corpus: bool = True, include_budget: bool = True) -> bool:
    """Seed everything; returns False (and does nothing) if the database is already seeded."""
    if is_seeded(session):
        return False
    seed_reference(session, clock=clock, ids=ids)
    if include_budget:
        budget_svc.create_envelope(session, period_id=PERIOD_ID, unit="USD", allocations=INITIAL_ALLOCATIONS,
                                   clock=clock, ids=ids)
    if include_corpus:
        seed_corpus(session, clock=clock, ids=ids)
    if include_spend:
        seed_spend(session, clock=clock, ids=ids)
    session.commit()
    return True


def reset_database(engine, session_factory, *, clock: Clock, ids: IdFactory, forecast_store=None) -> None:
    """Atomically replace the enabled demo database, including canonical forecasts.

    Advisory maintenance locking keeps other workers from reintroducing a result
    built before reset. Explicit BEGIN makes SQLite DDL plus reseeding one unit;
    failures restore the preceding schema/data rather than leaving half a reset.
    """
    from app.db.base import Base
    from app.forecasting.persistence import ForecastStore

    forecast_store = forecast_store or ForecastStore(engine.url.database)
    with forecast_store.operation(exclusive=True):
        with engine.connect() as connection:
            connection.exec_driver_sql('BEGIN EXCLUSIVE')
            try:
                for table in ('forecast_publications', 'forecast_scenarios', 'forecast_runs',
                              'forecast_jobs', 'forecast_input_snapshots', 'forecast_inputs',
                              'forecast_schema_versions'):
                    connection.exec_driver_sql(f'DROP TABLE IF EXISTS {table}')
                Base.metadata.drop_all(connection)
                Base.metadata.create_all(connection)
                forecast_store.migrate(connection=connection.connection.driver_connection)
                # Seed helpers commit their Session, while the explicit outer
                # transaction still owns all schema/data changes until success.
                info = dict(getattr(session_factory, 'kw', {}).get('info', {}))
                session = Session(bind=connection, join_transaction_mode='create_savepoint', info=info)
                try:
                    seed(session, clock=clock, ids=ids)
                finally:
                    session.close()
                connection.commit()
            except BaseException:
                connection.rollback()
                raise
