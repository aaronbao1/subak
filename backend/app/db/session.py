"""Request-scoped session dependency and a transaction helper."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from fastapi import Request
from sqlalchemy.orm import Session, sessionmaker


def get_session(request: Request) -> Iterator[Session]:
    factory: sessionmaker = request.app.state.session_factory
    session = factory()
    try:
        yield session
    finally:
        session.close()


@contextmanager
def transaction(factory: sessionmaker) -> Iterator[Session]:
    """Commit on success, roll back on any exception."""
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
