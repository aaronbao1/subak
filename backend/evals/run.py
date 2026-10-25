"""CLI: `python -m evals.run --runner fake|sdk` (from `backend/`).

- `fake`: FakeDroidRunner, every fixture, no credentials, deterministic.
- `sdk`: the real SdkDroidRunner (needs FACTORY_API_KEY in the environment, droid-sdk and the droid CLI;
  never read or logged here). Each fixture is one live run, gated by the global cap in
  `backend/data/live_runs.log` (default: stop at 15 - 2 spare). Skipped fixtures leave their scenarios
  `not_run`; nothing falls back to the fake runner.

Writes `evals/results/<runner>.json` and `evals/results/<runner>.md`. Exit status 1 if any scenario failed.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from app.config import BACKEND_ROOT
from evals import report
from evals.harness import DEFAULT_LIVE_LOG, LIVE_CAP, LIVE_RESERVE, run_suite
from evals.scenarios import SCENARIOS_BY_ID

RESULTS_DIR = Path(__file__).resolve().parent / "results"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m evals.run", description=__doc__.splitlines()[0])
    ap.add_argument("--runner", choices=("fake", "sdk"), required=True)
    ap.add_argument("--scenario", action="append", choices=sorted(SCENARIOS_BY_ID), help="repeatable; default all")
    ap.add_argument("--out", type=Path, default=RESULTS_DIR)
    ap.add_argument("--workdir", type=Path, default=None,
                    help="where per-fixture SQLite files go (default: temp for fake; backend/data/evals/sdk for sdk, "
                         "kept so a live run can be inspected afterwards)")
    ap.add_argument("--live-log", type=Path, default=DEFAULT_LIVE_LOG)
    ap.add_argument("--live-cap", type=int, default=LIVE_CAP)
    ap.add_argument("--live-reserve", type=int, default=LIVE_RESERVE)
    ap.add_argument("--max-live", type=int, default=None, help="at most this many live runs in this invocation")
    args = ap.parse_args(argv)

    if args.runner == "sdk":
        os.environ.setdefault("DROID_TIMEOUT_S", "600")  # live interpret runs take ~95-170 s
        if args.workdir is None:
            args.workdir = BACKEND_ROOT / "data" / "evals" / "sdk"  # gitignored; keeps the live DBs
    res = run_suite(args.runner, scenario_ids=args.scenario, workdir=args.workdir, live_log=args.live_log,
                    live_cap=args.live_cap, live_reserve=args.live_reserve, max_live=args.max_live)
    c = res.counts
    if args.runner == "sdk" and res.live_runs_used == 0 and (args.out / "sdk.json").exists():
        # nothing ran live (cap reached or runner unavailable): keep the last recorded live results
        print("no live run was made; the existing sdk results are kept and this result goes to sdk.not-live.*")
        jp, mp = report.write(res, args.out, stem="sdk.not-live")
    else:
        jp, mp = report.write(res, args.out)
    print(f"{args.runner}: {c['pass']} pass, {c['fail']} fail, {c['not_run']} not run -> {jp} , {mp}")
    for s in res.scenarios:
        print(f"  {s['status']:7} {s['id']}: {s['reasons'][0][:160] if s['reasons'] else ''}")
    if args.runner == "sdk":
        print(f"live runs used: {res.live_runs_used}; live_runs.log total: {res.live_log_total}")
    return 1 if c["fail"] else 0


if __name__ == "__main__":
    sys.exit(main())
