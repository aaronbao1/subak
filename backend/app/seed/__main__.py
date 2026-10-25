"""`python -m app.seed` - seed the database at BACKEND_DB_PATH with the Northstar example if empty.

Options:
  --with-planted   also load the planted-error pack (backend/seed/planted/) into that database:
                   duplicate exports, cumulative-counter session, unmapped provider project, two extra
                   documents. Company totals then show 1,800.00 unattributed and partial coverage.
  --check-planted  replay the planted pack (incl. the outdated-proposal and self-approval scenarios) on a
                   throwaway database and compare every result with backend/seed/answer_key.md.
                   Never touches BACKEND_DB_PATH. Exit code 1 if any check differs.
"""

from __future__ import annotations

import argparse
import sys

from app.config import Settings
from app.core.clock import SystemClock, UuidIdFactory
from app.db.base import SchemaOutdated, check_schema, create_all, make_engine, make_session_factory
from app.seed.northstar import seed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.seed", description="Seed the Northstar example.")
    parser.add_argument("--with-planted", action="store_true", help="also load the planted-error pack")
    parser.add_argument("--check-planted", action="store_true",
                        help="verify the planted pack against the answer key on a temporary database")
    args = parser.parse_args(argv)

    if args.check_planted:
        from app.seed.planted import format_checks, run_planted_checks

        checks = run_planted_checks()
        print(format_checks(checks))
        return 0 if all(c.passed for c in checks) else 1

    settings = Settings.from_env()
    engine = make_engine(settings.db_path)
    create_all(engine)
    try:
        check_schema(engine)
    except SchemaOutdated as exc:
        print(f"error: {exc}", file=sys.stderr)
        engine.dispose()
        return 2
    session = make_session_factory(engine)()
    clock, ids = SystemClock(), UuidIdFactory()
    try:
        created = seed(session, clock=clock, ids=ids)
        print(f"{'seeded' if created else 'already seeded'}: {settings.db_path}")
        if args.with_planted:
            from app.seed.planted import load_planted

            for row in load_planted(session, clock=clock, ids=ids):
                print("planted:", ", ".join(f"{k}={v}" for k, v in row.items()))
    finally:
        session.close()
        engine.dispose()
    return 0


if __name__ == "__main__":
    sys.exit(main())
