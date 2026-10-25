"""`python -m app.interpret` - interpret the period-relevant corpus in batches, under a credit cap.

    python -m app.interpret --since 2026-09-01 [--include-announced] --batch 10 --credit-cap 600000

Selection (backend/docs/uber-interpret-notes.md): current documents (not superseded) authored on or
after `--since`; with `--include-announced` also documents authored earlier whose effective window
(with an end date) overlaps the current planning period. The period comes from the clock.

Batching: documents are grouped by their team-tag set (company-wide and multi-team groups first), and
whole groups are packed first-fit up to `--batch` documents, allowing one extra rather than splitting a
group (a Slack/email message and its Asana/monday task share a team set, so pairs stay together). A
group too large for one batch is split on its effective windows. Inside a batch: by `authored_at`.

Each batch is one audited `interpret_corpus` AgentRun scoped to its documents (`params.document_ids`;
the toolbox refuses anything outside the scope), started as finance analyst `interpret-cli`. Signals go
through the normal record_signal path (quote verification, person/team/company scope). Nothing here
can change a budget.

- Runner: `DROID_RUNNER` (fake by default). `sdk` is preflighted before anything runs; if it is
  unavailable the command exits 2 and runs nothing. There is no fallback to the fake runner.
- Credit cap: before each batch the CLI stops if `spent + max(largest batch so far, --batch-estimate)`
  would exceed `--credit-cap`. `spent` sums provider-reported `factory_credits`
  (`output.usage.provider_reported.factory_credits`, also parsed from a failed run's error). An sdk
  batch that reports no credits stops the run (the cap could no longer be enforced). The fake runner
  reports none and costs 0.
- Idempotent: a document (doc_key + version) already covered by a succeeded scoped interpret_corpus run
  with the same runner kind is skipped (`--force` re-runs). Ids change on every reload, keys do not.
- sdk runs append one line per batch to `backend/data/live_runs.log` (`--log` to override), in the
  evals harness format; note the evals live cap counts those lines too.
- `--dry-run` prints the selection and batch plan and runs nothing.

Exit codes: 0 done (including a stop at the cap), 1 a batch failed, 2 runner unavailable / bad input.
Prints no secrets and no environment variables.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.config import BACKEND_ROOT, Settings, SettingsError
from app.core.actors import Actor
from app.core.clock import Clock, IdFactory, SystemClock, UuidIdFactory
from app.core.errors import DomainError
from app.db import models as m
from app.services.agent_runs import MAX_SCOPE_DOCUMENTS

INTERPRET_CLI = Actor("interpret-cli", "finance_analyst")
DEFAULT_LOG = BACKEND_ROOT / "data" / "live_runs.log"
DEFAULT_BATCH_ESTIMATE = 75_000
_CREDITS_IN_ERROR = re.compile(r'"factory_credits":\s*([0-9.]+)')


# ---- selection -----------------------------------------------------------------------------------


@dataclass(frozen=True)
class Doc:
    id: str
    doc_key: str
    version: int
    authored_at: str
    teams: tuple[str, ...]
    window: tuple[str | None, str | None]

    @property
    def key(self) -> tuple[str, int]:
        return (self.doc_key, self.version)


def _doc(d: m.CorpusDocument) -> Doc:
    return Doc(d.id, d.doc_key, d.version, d.authored_at.isoformat(), tuple(sorted(d.team_tags or [])),
               (d.effective_from.isoformat() if d.effective_from else None,
                d.effective_to.isoformat() if d.effective_to else None))


def select_documents(session: Session, period: m.PlanningPeriod, *, since: date,
                     include_announced: bool) -> list[Doc]:
    out = []
    for d in session.scalars(select(m.CorpusDocument).where(m.CorpusDocument.superseded_by_document_id.is_(None))
                             .order_by(m.CorpusDocument.authored_at, m.CorpusDocument.doc_key)):
        recent = d.authored_at.date() >= since
        announced = (include_announced and d.effective_from is not None and d.effective_to is not None
                     and d.effective_from <= period.ends_on and d.effective_to >= period.starts_on)
        if recent or announced:
            out.append(_doc(d))
    return out


def interpreted_keys(session: Session, runner_kind: str) -> set[tuple[str, int]]:
    """doc_key+version covered by a succeeded scoped interpret_corpus run of this runner kind."""
    done: set[tuple[str, int]] = set()
    runs = session.scalars(select(m.AgentRun).where(m.AgentRun.task_type == "interpret_corpus",
                                                    m.AgentRun.status == "succeeded",
                                                    m.AgentRun.runner_kind == runner_kind))
    for run in runs:
        ids = ((run.input or {}).get("task") or {}).get("params", {}).get("document_ids") or []
        for doc_id in ids:
            d = session.get(m.CorpusDocument, doc_id)
            if d is not None:
                done.add((d.doc_key, d.version))
    return done


def plan_batches(docs: Sequence[Doc], size: int) -> list[list[Doc]]:
    """Group by team-tag set (multi-team first), pack whole groups up to `size` (+1 rather than split)."""
    size = max(1, min(size, MAX_SCOPE_DOCUMENTS - 1))
    groups: dict[tuple[str, ...], list[Doc]] = defaultdict(list)
    for d in docs:
        groups[d.teams].append(d)
    order = sorted(groups, key=lambda t: (-len(t), t))
    units: list[list[Doc]] = []  # each unit is never split across batches
    for teams in order:
        group = groups[teams]
        if len(group) <= size + 1:
            units.append(group)
            continue
        by_window: dict[tuple, list[Doc]] = defaultdict(list)  # message + task of one event share a window
        for d in group:
            by_window[d.window].append(d)
        for w in sorted(by_window, key=lambda w: min(x.authored_at for x in by_window[w])):
            chunk = by_window[w]
            units.extend(chunk[i:i + size] for i in range(0, len(chunk), size))
    # First fit in group order: a unit joins the first batch it fits (up to `size`, else `size + 1`).
    batches: list[list[Doc]] = []
    for unit in units:
        target = next((b for b in batches if len(b) + len(unit) <= size), None) \
            or next((b for b in batches if len(b) + len(unit) == size + 1), None)
        if target is None:
            batches.append(list(unit))
        else:
            target.extend(unit)
    return [sorted(b, key=lambda d: (d.authored_at, d.doc_key)) for b in batches]


# ---- running -------------------------------------------------------------------------------------


@dataclass
class BatchResult:
    index: int
    run_id: str | None
    status: str
    doc_keys: list[str]
    credits: float | None
    signal_count: int = 0
    error: str | None = None


@dataclass
class Report:
    selected: int = 0
    skipped_done: int = 0
    batches_planned: int = 0
    results: list[BatchResult] = field(default_factory=list)
    spent: float = 0.0
    stopped_at_cap: bool = False
    stop_reason: str | None = None

    @property
    def exit_code(self) -> int:
        return 1 if any(r.status != "succeeded" for r in self.results) else 0


def _credits(run: m.AgentRun) -> float | None:
    usage = (run.output or {}).get("usage") or {}
    value = (usage.get("provider_reported") or {}).get("factory_credits")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    match = _CREDITS_IN_ERROR.search(run.error or "")
    return float(match.group(1)) if match else None


def _append_log(path: Path, at: str, purpose: str, result: str, usage: Any) -> None:
    """Same one-line format as the evals harness (`ts | purpose | result | usage={...}`)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    line = f"{at} | {purpose} | {result} | usage={json.dumps(usage, sort_keys=True, default=str)}"
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line.replace("\n", " ") + "\n")


def run_batches(session_factory: sessionmaker, *, settings: Settings, clock: Clock, ids: IdFactory,
                runner: Any, runner_kind: str, since: date, include_announced: bool, batch_size: int,
                credit_cap: float, batch_estimate: float = DEFAULT_BATCH_ESTIMATE, force: bool = False,
                dry_run: bool = False, log_path: Path = DEFAULT_LOG, forecast_provider: Any = None,
                out: Callable[[str], None] = print) -> Report:
    from app.providers.forecast import provider_from_settings
    from app.services import agent_runs
    from app.services.coverage import resolve_period
    from app.schemas.agent import AgentRunCreate

    report = Report()
    s = session_factory()
    try:
        period = resolve_period(s, None, clock.now())
        docs = select_documents(s, period, since=since, include_announced=include_announced)
        done = set() if force else interpreted_keys(s, runner_kind)
    finally:
        s.close()
    report.selected = len(docs)
    todo = [d for d in docs if d.key not in done]
    report.skipped_done = len(docs) - len(todo)
    batches = plan_batches(todo, batch_size)
    report.batches_planned = len(batches)
    label = " (FAKE stand-in: scripted, no model; non-Northstar documents yield no signals)" \
        if runner_kind == "fake" else ""
    out(f"period {period.id} ({period.starts_on}..{period.ends_on}); runner {runner_kind}{label}; "
        f"selected {len(docs)} document(s) (since {since}{', + announced' if include_announced else ''}); "
        f"{report.skipped_done} already interpreted; {len(batches)} batch(es) of <= {batch_size + 1}; "
        f"credit cap {credit_cap:,.0f}")
    for i, b in enumerate(batches, 1):
        teams = sorted({t for d in b for t in d.teams})
        out(f"  batch {i}: {len(b)} doc(s) [{', '.join(teams) if len(teams) <= 4 else f'{len(teams)} teams'}] "
            + " ".join(d.doc_key for d in b))
    if dry_run or not batches:
        return report

    provider = forecast_provider or provider_from_settings(settings.forecast_provider)
    if forecast_provider is None and callable(getattr(provider, "bind", None)):
        provider.bind(session_factory, clock)
    state = SimpleNamespace(settings=replace(settings, droid_runner=runner_kind), clock=clock, id_factory=ids,
                            session_factory=session_factory, forecast_provider=provider, droid_runner=runner)
    largest = 0.0
    for i, batch in enumerate(batches, 1):
        projected = report.spent + max(largest, batch_estimate)
        if projected > credit_cap:
            report.stopped_at_cap = True
            report.stop_reason = (f"stopped before batch {i}: spent {report.spent:,.0f} + next-batch estimate "
                                  f"{max(largest, batch_estimate):,.0f} would exceed the cap {credit_cap:,.0f}")
            out(report.stop_reason)
            break
        keys = [f"{d.doc_key}@v{d.version}" for d in batch]
        body = AgentRunCreate(task_type="interpret_corpus", wait=True,
                              instruction=f"Batch {i}/{len(batches)} of the period-relevant corpus.",
                              params={"document_ids": [d.id for d in batch]})
        try:
            run_id, _ = agent_runs.start_run(state, body, actor=INTERPRET_CLI)
        except DomainError as exc:
            run_id = (exc.details or {}).get("run_id")
            result = BatchResult(i, run_id, "unavailable" if exc.code == "runner_unavailable" else "failed",
                                 keys, None, error=exc.message)
        else:
            s = session_factory()
            try:
                run = s.get(m.AgentRun, run_id)
                count = len((run.output or {}).get("signal_ids") or [])
                result = BatchResult(i, run_id, run.status, keys, _credits(run), count, run.error)
            finally:
                s.close()
        report.results.append(result)
        credits = result.credits or 0.0
        report.spent += credits
        largest = max(largest, credits)
        out(f"  batch {i}: {result.status} run {result.run_id}; {result.signal_count} signal(s); "
            f"credits {'n/a' if result.credits is None else f'{result.credits:,.0f}'}; "
            f"spent {report.spent:,.0f}" + (f"; error: {result.error[:300]}" if result.error else ""))
        if runner_kind == "sdk":
            _append_log(log_path, clock.now().isoformat(),
                        f"app.interpret batch {i}/{len(batches)}: run {result.run_id} docs {' '.join(keys)}",
                        f"{result.status}; {result.signal_count} signal(s); spent {report.spent:,.0f} of cap "
                        f"{credit_cap:,.0f}" + (f"; error: {result.error[:300]}" if result.error else ""),
                        {"factory_credits": result.credits})
        if result.status != "succeeded":
            report.stop_reason = f"batch {i} ended {result.status}; later batches were not run"
            out(report.stop_reason)
            break
        if runner_kind == "sdk" and result.credits is None:
            report.stop_reason = (f"batch {i} reported no factory_credits; stopping because the credit cap "
                                  "can no longer be enforced")
            out(report.stop_reason)
            break
    done_count = sum(len(r.doc_keys) for r in report.results if r.status == "succeeded")
    out(f"done: {done_count} document(s) interpreted in {sum(r.status == 'succeeded' for r in report.results)} "
        f"batch(es); {sum(r.signal_count for r in report.results)} signal(s); credits spent {report.spent:,.0f}")
    return report


# ---- entry point ---------------------------------------------------------------------------------


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m app.interpret", description=__doc__.split("\n\n")[0])
    p.add_argument("--since", type=date.fromisoformat, default=date(2026, 9, 1),
                   help="interpret documents authored on or after this date (default 2026-09-01)")
    p.add_argument("--include-announced", action="store_true",
                   help="also documents authored earlier whose effective window overlaps the current period")
    p.add_argument("--batch", type=int, default=10, help="documents per batch (default 10, +1 to keep a pair)")
    p.add_argument("--credit-cap", type=float, default=600_000, help="stop before exceeding this many credits")
    p.add_argument("--batch-estimate", type=float, default=DEFAULT_BATCH_ESTIMATE,
                   help="credits assumed for the next batch before one has run (default 75000)")
    p.add_argument("--db", type=Path, default=None, help="SQLite path (default BACKEND_DB_PATH or data/app.db)")
    p.add_argument("--log", type=Path, default=DEFAULT_LOG, help="sdk run log (default backend/data/live_runs.log)")
    p.add_argument("--force", action="store_true", help="re-run documents already interpreted")
    p.add_argument("--dry-run", action="store_true", help="print the selection and batch plan; run nothing")
    return p


def main(argv: Sequence[str] | None = None, *, clock: Clock | None = None, ids: IdFactory | None = None,
         runner: Any = None, env: dict[str, str] | None = None, out: Callable[[str], None] = print) -> int:
    from app.agent.loader import load_runner
    from app.agent.runner import RunnerUnavailable
    from app.db.base import check_schema, make_engine, make_session_factory

    args = _parser().parse_args(argv)
    if args.batch < 1 or args.credit_cap <= 0 or args.batch_estimate < 0:
        out("--batch must be >= 1, --credit-cap > 0 and --batch-estimate >= 0")
        return 2
    try:
        settings = Settings.from_env(env)
    except SettingsError as exc:
        out(f"bad settings: {exc}")
        return 2
    if args.db is not None:
        settings = replace(settings, db_path=args.db)
    kind = getattr(runner, "kind", None) or settings.droid_runner
    if runner is None and not args.dry_run:
        try:  # preflight before anything runs; never falls back to the fake runner
            runner = load_runner(kind, env)
        except RunnerUnavailable as exc:
            out(f"DROID_RUNNER={kind} is unavailable ({exc.reason}): {exc}. Nothing was run.")
            return 2
    if not settings.db_path.exists():
        out(f"database {settings.db_path} does not exist; seed or load it first")
        return 2
    engine = make_engine(settings.db_path)
    try:
        check_schema(engine)
        report = run_batches(make_session_factory(engine), settings=settings, clock=clock or SystemClock(),
                             ids=ids or UuidIdFactory(), runner=runner, runner_kind=kind, since=args.since,
                             include_announced=args.include_announced, batch_size=args.batch,
                             credit_cap=args.credit_cap, batch_estimate=args.batch_estimate, force=args.force,
                             dry_run=args.dry_run, log_path=args.log, out=out)
    except DomainError as exc:
        out(f"{exc.code}: {exc.message}")
        return 2
    finally:
        engine.dispose()
    if any(r.status == "unavailable" for r in report.results):
        return 2
    return report.exit_code


if __name__ == "__main__":  # pragma: no cover - entry point
    sys.exit(main())
