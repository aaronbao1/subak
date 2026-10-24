"""Declarative base and engine/session factory for SQLite at BACKEND_DB_PATH."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import Engine, MetaData, create_engine, event
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
