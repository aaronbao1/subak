"""Execute eval fixtures against a runner, score scenarios, and enforce the live-run cap.

Every fixture runs on its own fresh SQLite file under `workdir`, seeded with the Northstar seed, through
the real FastAPI app in-process (`TestClient`). Setup is done by finance/importer roles over HTTP. The
run is started as `finance_analyst` with `wait: true`; everything scored is read back over the API.

Live (sdk) runs: before each one the global log (`backend/data/live_runs.log`, gitignored) is counted.
A fixture runs live only while `count < cap - reserve` and fewer than `max_live` runs were made in this
invocation; otherwise it is skipped (its scenarios are `not_run`), never silently replaced by the fake.
After each live run one line is appended: ISO time | purpose | result | usage.
"""

from __future__ import annotations

import json
import re
import shutil
import tempfile
import time
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from app.config import BACKEND_ROOT, Settings
from app.core.clock import FrozenClock, SequentialIdFactory
from app.main import create_app
from app.seed.northstar import seed
from evals.fixtures import ANALYST, FIXTURES, LIVE_PRIORITY, Fixture
from evals.scenarios import SCENARIOS, Check, RunCtx, Scenario

FROZEN_AT = datetime(2026, 10, 24, 12, 0, 0, tzinfo=timezone.utc)
DEFAULT_LIVE_LOG = BACKEND_ROOT / "data" / "live_runs.log"
LIVE_CAP = 15
LIVE_RESERVE = 2


def live_count(path: Path) -> int:
    try:
        return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    except FileNotFoundError:
        return 0


def append_live_line(path: Path, purpose: str, result: str, usage: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = f"{datetime.now(timezone.utc).isoformat()} | {purpose} | {result} | usage={json.dumps(usage, default=str)}"
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line.replace("\n", " ") + "\n")


def _usage(ctx: RunCtx) -> Any:
    out = ctx.run.get("output") or {}
    usage = (out.get("usage") or {}).get("provider_reported")
    if usage is None and ctx.run.get("error"):
        m = re.search(r"usage=(\{.*\})", ctx.run["error"])
        if m:
            try:
                usage = json.loads(m.group(1))
            except ValueError:
                usage = None
    return usage


def execute_fixture(fx: Fixture, runner_kind: str, workdir: Path, *, runner: Any | None = None) -> RunCtx:
    """Run one fixture on a fresh seeded DB. `runner` injects a DroidRunner (tests); otherwise the backend
    loads the runner named by `runner_kind` exactly as the API does (no fallback)."""
    ctx = RunCtx(fixture=fx.name, runner=runner_kind)
    db = workdir / f"{fx.name}.db"
    for p in (db, db.with_name(db.name + "-journal")):
        p.unlink(missing_ok=True)
    settings = Settings(db_path=db, droid_runner=runner_kind, forecast_provider=fx.forecast_provider)
    deterministic = runner_kind == "fake"
    app = create_app(settings, clock=FrozenClock(FROZEN_AT) if deterministic else None,
                     id_factory=SequentialIdFactory() if deterministic else None, droid_runner=runner)
    try:
        s = app.state.session_factory()
        try:
            seed(s, clock=app.state.clock, ids=app.state.id_factory)
        finally:
            s.close()
        with TestClient(app) as client:
            ctx.setup = fx.setup(client) if fx.setup else {}
            ctx.budget_before = client.get("/api/budget").json()
            ctx.decisions_before = client.get("/api/decisions").json()
            ctx.request = {**fx.request(ctx.setup), "wait": True}
            started = time.monotonic()
            resp = client.post("/api/agent/runs", json=ctx.request, headers=ANALYST)
            ctx.duration_s = round(time.monotonic() - started, 2)
            ctx.ran = True
            ctx.http_status = resp.status_code
            ctx.response = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
            run_id = ctx.response.get("id") or ((ctx.response.get("error") or {}).get("details") or {}).get("run_id")
            if run_id:
                ctx.run = client.get(f"/api/agent/runs/{run_id}").json()
            ctx.budget_after = client.get("/api/budget").json()
            ctx.decisions_after = client.get("/api/decisions").json()
            ctx.signals = client.get("/api/signals").json()["items"]
            ctx.spend = client.get("/api/spend/summary").json()
            ctx.forecast = client.get("/api/forecasts").json()
            for d in client.get("/api/documents").json()["items"]:
                ctx.documents[d["id"]] = client.get(f"/api/documents/{d['id']}").json()
            for p in ctx.run.get("proposals", []):
                ctx.proposals.append(client.get(f"/api/proposals/{p['id']}").json())
    except Exception as exc:  # noqa: BLE001 - a broken fixture is reported, not raised
        ctx.error = f"{type(exc).__name__}: {exc}"
    finally:
        app.state.engine.dispose()
    return ctx


@dataclass
class SuiteResult:
    runner: str
    generated_at: str
    fixtures: dict[str, RunCtx]
    scenarios: list[dict[str, Any]]
    live_runs_used: int = 0
    live_log_total: int | None = None
    notes: list[str] = field(default_factory=list)

    @property
    def counts(self) -> dict[str, int]:
        out = {"pass": 0, "fail": 0, "not_run": 0}
        for s in self.scenarios:
            out[s["status"]] += 1
        return out


def score(scenario: Scenario, ctxs: dict[str, RunCtx]) -> dict[str, Any]:
    missing = [n for n in scenario.fixtures if not ctxs.get(n) or not ctxs[n].ran]
    base = {"id": scenario.id, "title": scenario.title, "fixtures": list(scenario.fixtures), "note": scenario.note}
    if missing:
        reasons = sorted({ctxs[n].skip_reason or ctxs[n].error or "not run" for n in missing if n in ctxs})
        return {**base, "status": "not_run", "checks": [],
                "reasons": [f"fixture(s) {', '.join(missing)} not run: {'; '.join(reasons)}"]}
    try:
        checks = scenario.score({n: ctxs[n] for n in scenario.fixtures})
    except Exception as exc:  # noqa: BLE001 - a scorer crash is a failed scenario with the reason
        checks = [Check("scorer", False, f"scorer raised {type(exc).__name__}: {exc}")]
    failed = [c for c in checks if not c.passed]
    return {**base, "status": "fail" if failed else "pass", "checks": [c.as_dict() for c in checks],
            "reasons": [f"{c.name}: {c.reason}" for c in failed] or [f"{len(checks)} check(s) passed"]}


def run_suite(runner_kind: str, *, scenario_ids: Iterable[str] | None = None, workdir: Path | None = None,
              runner: Any | None = None, live_log: Path = DEFAULT_LIVE_LOG, live_cap: int = LIVE_CAP,
              live_reserve: int = LIVE_RESERVE, max_live: int | None = None) -> SuiteResult:
    wanted = [s for s in SCENARIOS if scenario_ids is None or s.id in set(scenario_ids)]
    needed = {f for s in wanted for f in s.fixtures}
    order = [f for f in LIVE_PRIORITY if f in needed] + sorted(needed - set(LIVE_PRIORITY))
    own_tmp = workdir is None
    workdir = Path(tempfile.mkdtemp(prefix="northstar-evals-")) if own_tmp else workdir
    workdir.mkdir(parents=True, exist_ok=True)
    live = runner_kind == "sdk"
    ctxs: dict[str, RunCtx] = {}
    used = 0
    notes: list[str] = []
    try:
        for name in order:
            fx = FIXTURES[name]
            if live:
                count = live_count(live_log)
                limit = live_cap - live_reserve
                if count >= limit:
                    ctxs[name] = RunCtx(fixture=name, runner=runner_kind, skip_reason=(
                        f"live cap: {count} runs in live_runs.log, cap {live_cap} with {live_reserve} kept spare"))
                    continue
                if max_live is not None and used >= max_live:
                    ctxs[name] = RunCtx(fixture=name, runner=runner_kind,
                                        skip_reason=f"max_live={max_live} reached in this invocation")
                    continue
            ctx = execute_fixture(fx, runner_kind, workdir, runner=runner)
            ctxs[name] = ctx
            if live and ctx.ran and ctx.run.get("status") in ("succeeded", "failed"):
                used += 1
                result = ctx.run.get("status")
                subtype = ((ctx.run.get("output") or {}).get("usage") or {}).get("subtype")
                append_live_line(live_log, f"evals sdk: {name}: {fx.purpose}",
                                 f"{result}" + (f" (subtype {subtype})" if subtype else ""), _usage(ctx))
        scenarios = [score(s, ctxs) for s in wanted]
    finally:
        if own_tmp:
            shutil.rmtree(workdir, ignore_errors=True)
    if live:
        skipped = [n for n, c in ctxs.items() if not c.ran]
        if skipped:
            notes.append(f"Fixtures not run live: {', '.join(skipped)} "
                         f"({'; '.join(sorted({ctxs[n].skip_reason or '' for n in skipped}))}).")
    return SuiteResult(runner=runner_kind, generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                       fixtures=ctxs, scenarios=scenarios, live_runs_used=used,
                       live_log_total=live_count(live_log) if live else None, notes=notes)
