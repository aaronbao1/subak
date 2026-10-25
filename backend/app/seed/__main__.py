"""`python -m app.seed` - seed the database at BACKEND_DB_PATH with the Northstar example if empty.

Options:
  --with-planted   also load the planted-error pack (backend/seed/planted/) into that database:
                   duplicate exports, cumulative-counter session, unmapped provider project, two extra
                   documents. Company totals then show 1,800.00 unattributed and partial coverage.
  --check-planted  replay the planted pack (incl. the outdated-proposal and self-approval scenarios) on a
                   throwaway database and compare every result with backend/seed/answer_key.md.
                   Never touches BACKEND_DB_PATH. Exit code 1 if any check differs.

Context signals (fresh seed only; one audited `interpret_corpus` run, see app/seed/interpret.py):
  (default)        run the deterministic stand-in once; signals are labeled `droid_fake`.
  --no-signals     seed without interpreting the corpus (no context signals).
  --live-signals   interpret with the real Droid (DROID_RUNNER=sdk requirements: FACTORY_API_KEY, the
                   droid-sdk package and the `droid` CLI). Checked before the database is touched; if
                   anything is missing it exits 2 and seeds nothing. Never falls back to the stand-in.
On an already seeded database nothing is re-interpreted (exit 1 with --live-signals, else 0).
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
    signals = parser.add_mutually_exclusive_group()
    signals.add_argument("--live-signals", action="store_true",
                         help="interpret the corpus with the real Droid after a fresh seed (no fallback)")
    signals.add_argument("--no-signals", action="store_true", help="do not interpret the corpus after seeding")
    args = parser.parse_args(argv)

    if args.check_planted:
        from app.seed.planted import format_checks, run_planted_checks

        checks = run_planted_checks()
        print(format_checks(checks))
        return 0 if all(c.passed for c in checks) else 1

    settings = Settings.from_env()
    mode = "live" if args.live_signals else "none" if args.no_signals else "fake"
    live_runner = None
    if mode == "live":  # preflight before the database is touched
        from app.agent.loader import load_runner
        from app.agent.runner import RunnerUnavailable

        try:
            live_runner = load_runner("sdk")
        except RunnerUnavailable as exc:
            print(f"--live-signals needs the real Droid: {exc}. Nothing was seeded.", file=sys.stderr)
            return 2
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
    code = 0
    try:
        created = seed(session, clock=clock, ids=ids)
        print(f"{'seeded' if created else 'already seeded'}: {settings.db_path}")
        if mode != "none" and not created:
            print("already seeded; signals are only interpreted on a fresh seed "
                  "(delete the DB or use /api/admin/reset)")
            code = 1 if mode == "live" else 0
        elif mode != "none":
            from app.seed.interpret import interpret_at_seed

            result = interpret_at_seed(make_session_factory(engine), settings=settings, clock=clock, ids=ids,
                                       mode=mode, runner=live_runner)
            if result.succeeded:
                print(f"signals: {result.signal_count} recorded by {result.produced_by} (run {result.run_id})")
            else:
                kept = (f"{result.signal_count} signal(s) recorded before it stopped are kept"
                        if result.signal_count else "the database is seeded without Droid signals")
                print(f"signals: interpretation run {result.run_id} ended {result.status}: {result.error}; {kept}",
                      file=sys.stderr)
                code = 1
        if args.with_planted:
            from app.seed.planted import load_planted

            for row in load_planted(session, clock=clock, ids=ids):
                print("planted:", ", ".join(f"{k}={v}" for k, v in row.items()))
    finally:
        session.close()
        engine.dispose()
    return code


if __name__ == "__main__":
    sys.exit(main())
