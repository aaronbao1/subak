"""Declarative base and engine/session factory for SQLite at BACKEND_DB_PATH."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import Engine, MetaData, create_engine, event, inspect
from sqlalchemy.orm import DeclarativeBase, sessionmaker

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def _sqlite_pragmas(dbapi_conn, _record) -> None:  # pragma: no cover - trivial
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA foreign_keys=ON")
    cur.execute("PRAGMA journal_mode=WAL")
    cur.execute("PRAGMA busy_timeout=5000")
    cur.close()


def make_engine(db_path: Path | str) -> Engine:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        f"sqlite:///{path}",
        connect_args={"check_same_thread": False},
        future=True,
    )
    event.listen(engine, "connect", _sqlite_pragmas)
    return engine


def make_session_factory(engine: Engine) -> sessionmaker:
    return sessionmaker(bind=engine, expire_on_commit=False, autoflush=False, future=True)


def create_all(engine: Engine) -> None:
    from app.db import models  # noqa: F401  (register tables)

    Base.metadata.create_all(engine)
    # create_all skips the indexes of tables that already exist; add any new index to an existing file
    # (CREATE INDEX IF NOT EXISTS; no data change, no migration needed).
    # An index on a column the file lacks is skipped: check_schema then reports the outdated file.
    insp = inspect(engine)
    for table in Base.metadata.sorted_tables:
        have = {c["name"] for c in insp.get_columns(table.name)}
        for index in table.indexes:
            if {c.name for c in index.columns} <= have:
                index.create(engine, checkfirst=True)


class SchemaOutdated(RuntimeError):
    """The SQLite file was created by an older backend. There are no migrations: `create_all` does not
    add columns to an existing table, so a stale file would otherwise fail later as an opaque 500."""


def check_schema(engine: Engine) -> None:
    """Raise `SchemaOutdated` if any mapped table in the database lacks a mapped column."""
    from app.db import models  # noqa: F401  (register tables)

    insp = inspect(engine)
    existing_tables = set(insp.get_table_names())
    missing: list[str] = []
    for table in Base.metadata.sorted_tables:
        if table.name not in existing_tables:
            missing.append(table.name)
            continue
        have = {c["name"] for c in insp.get_columns(table.name)}
        missing += [f"{table.name}.{c.name}" for c in table.columns if c.name not in have]
    if missing:
        db = engine.url.database or "the database"
        raise SchemaOutdated(
            f"{db} predates this backend (missing {', '.join(missing)}). "
            "Delete it and run `python -m app.seed`."
        )
