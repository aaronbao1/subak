"""`python -m app.seed` - seed the database at BACKEND_DB_PATH with the Northstar example if empty."""

from __future__ import annotations

from app.config import Settings
from app.core.clock import SystemClock, UuidIdFactory
from app.db.base import create_all, make_engine, make_session_factory
from app.seed.northstar import seed


def main() -> None:
    settings = Settings.from_env()
    engine = make_engine(settings.db_path)
    create_all(engine)
    session = make_session_factory(engine)()
    try:
        created = seed(session, clock=SystemClock(), ids=UuidIdFactory())
    finally:
        session.close()
        engine.dispose()
    print(f"{'seeded' if created else 'already seeded'}: {settings.db_path}")


if __name__ == "__main__":
    main()
