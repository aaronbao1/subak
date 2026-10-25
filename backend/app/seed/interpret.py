"""Seed-time corpus interpretation (backend/docs/frontend-integration-design.md §7).

`python -m app.seed` runs one `interpret_corpus` task right after a fresh seed so the dashboard has
context cards on first load. It is a normal audited `AgentRun` started through `agent_runs.start_run`
as a finance analyst (`seed-interpreter`); its signals are labeled with the runner that produced them
(`droid_fake` for the stand-in, `droid_sdk` for the real Droid). Nothing here can change a budget.

- `mode="fake"`: the deterministic stand-in (`FakeDroidRunner`), no credentials.
- `mode="live"`: the real Droid. The caller preflights `load_runner("sdk")` and passes the runner in;
  there is no fallback to the stand-in.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from types import SimpleNamespace
from typing import Any, Literal

from sqlalchemy import func, select

from app.agent.fake_runner import FakeDroidRunner
from app.config import Settings
from app.core.actors import Actor
from app.core.clock import Clock, IdFactory
from app.core.errors import DomainError
from app.db import models as m
from app.providers.forecast import ForecastProvider, provider_from_settings
from app.schemas.agent import AgentRunCreate

InterpretMode = Literal["none", "fake", "live"]
SEED_INTERPRETER = Actor("seed-interpreter", "finance_analyst")
PRODUCER = {"fake": "droid_fake", "live": "droid_sdk"}


@dataclass(frozen=True)
class SeedInterpretation:
    run_id: str | None
    status: str  # succeeded | failed | unavailable
    signal_count: int
    produced_by: str
    error: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.status == "succeeded"


def interpret_at_seed(session_factory: Any, *, settings: Settings, clock: Clock, ids: IdFactory,
                      mode: Literal["fake", "live"], runner: Any = None,
                      forecast_provider: ForecastProvider | None = None) -> SeedInterpretation:
    """Run `interpret_corpus` once on an already seeded (and committed) database."""
    if mode not in PRODUCER:
        raise ValueError(f"unknown interpret mode {mode!r}")
    if mode == "fake":
        runner = FakeDroidRunner()
    elif runner is None:
        from app.agent.loader import load_runner

        runner = load_runner("sdk")  # raises RunnerUnavailable; never falls back to the stand-in
    state = SimpleNamespace(
        settings=replace(settings, droid_runner="fake" if mode == "fake" else "sdk"),
        clock=clock, id_factory=ids, session_factory=session_factory,
        forecast_provider=forecast_provider or provider_from_settings(settings.forecast_provider),
        droid_runner=runner,
    )
    from app.services import agent_runs

    try:
        run_id, _ = agent_runs.start_run(state, AgentRunCreate(task_type="interpret_corpus", wait=True),
                                         actor=SEED_INTERPRETER)
    except DomainError as exc:
        return SeedInterpretation((exc.details or {}).get("run_id"), "unavailable", 0, PRODUCER[mode], exc.message)
    s = session_factory()
    try:
        run = s.get(m.AgentRun, run_id)
        count = s.scalar(select(func.count()).select_from(m.ContextSignal)
                         .where(m.ContextSignal.agent_run_id == run_id)) or 0
        return SeedInterpretation(run_id, run.status, int(count), PRODUCER[mode], run.error)
    finally:
        s.close()
