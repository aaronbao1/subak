"""`python -m app.interpret`: selection, batching, scoped runs, credit cap, idempotency, fail-closed.

Fake runner and fake `droid_sdk` only (tests/fake_droid_sdk.py); nothing talks to Factory.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone

import pytest
from sqlalchemy import func, select

import fake_droid_sdk
from app import interpret as cli
from app.agent.runner import AgentRunOutput, RunnerUnavailable, ToolError
from app.agent.toolbox import BackendToolbox
from app.core.errors import DomainError
from app.db import models as m
from app.schemas.agent import AgentRunCreate
from app.schemas.documents import DocumentIn
from app.seed.northstar import seed
from app.services import agent_runs
from app.services import corpus as corpus_svc
from app.services.coverage import resolve_period
from northstar_droid.sdk_runner import SdkDroidRunner

ALL_TEAMS = ["engineering", "product", "research"]
# Extra, non-Northstar documents (outside the fake runner's playbook).
EXTRA = [
    # company-wide notice (multi-team group goes first)
    dict(doc_key="ext-company-holiday", title="Holiday notice", team_tags=ALL_TEAMS,
         authored_at="2026-10-05T09:00:00Z", effective_from="2026-11-26", effective_to="2026-11-27"),
    # a message + task pair for one event (same team, same window)
    dict(doc_key="ext-msg-launch", title="Launch week thread", team_tags=["product"],
         authored_at="2026-10-10T09:00:00Z", effective_from="2026-11-02", effective_to="2026-11-30"),
    dict(doc_key="ext-task-launch", title="Launch week task", team_tags=["product"],
         authored_at="2026-10-10T10:00:00Z", effective_from="2026-11-02", effective_to="2026-11-30"),
    # announced before --since, window overlaps the period: only with --include-announced
    dict(doc_key="ext-announced-rollout", title="Rollout plan", team_tags=["engineering"],
         authored_at="2026-08-10T09:00:00Z", effective_from="2026-09-01", effective_to="2026-12-15"),
    # open-ended and old: never selected (already in spend history)
    dict(doc_key="ext-old-policy", title="Old policy", team_tags=["research"],
         authored_at="2026-06-01T09:00:00Z", effective_from="2026-06-01", effective_to=None),
]
NORTHSTAR_SINCE_SEP = 11  # 13 seed docs; 2 superseded (and one of those predates September)


def _add_extra(session, clock, ids, docs=EXTRA):
    for d in docs:
        corpus_svc.ingest_document(session, DocumentIn(
            origin="upload", doc_type="update", content=f"{d['title']}: details for {d['doc_key']}.", **d),
            clock=clock, ids=ids)
    session.commit()


@pytest.fixture
def seeded(app, clock, id_factory, db_path):
    s = app.state.session_factory()
    seed(s, clock=clock, ids=id_factory, include_spend=False)
    _add_extra(s, clock, id_factory)
    s.close()
    return db_path


def _main(db_path, *args, runner=None, clock, id_factory, lines=None, env=None):
    out = lines if lines is not None else []
    code = cli.main(["--db", str(db_path), *args], clock=clock, ids=id_factory, runner=runner,
                    env=env if env is not None else {}, out=out.append)
    return code, out


def _runs(app):
    s = app.state.session_factory()
    try:
        return list(s.scalars(select(m.AgentRun).order_by(m.AgentRun.started_at, m.AgentRun.id)))
    finally:
        s.close()


# ---- selection and batching ------------------------------------------------------------------------


def test_selection_since_and_announced(app, seeded, clock):
    s = app.state.session_factory()
    period = resolve_period(s, None, clock.now())
    base = cli.select_documents(s, period, since=datetime(2026, 9, 1).date(), include_announced=False)
    more = cli.select_documents(s, period, since=datetime(2026, 9, 1).date(), include_announced=True)
    s.close()
    keys = {d.doc_key for d in base}
    assert len(base) == NORTHSTAR_SINCE_SEP + 3
    assert {"ext-company-holiday", "ext-msg-launch", "ext-task-launch"} <= keys
    assert "product-launch-plan" not in {d.doc_key for d in base if d.version == 1}  # superseded v1 excluded
    assert {d.doc_key for d in more} - keys == {"ext-announced-rollout"}
    assert "ext-old-policy" not in {d.doc_key for d in more}


def _doc(key, teams, window=("2026-11-01", "2026-11-30"), at="2026-10-01T00:00:00"):
    return cli.Doc(id=f"id-{key}", doc_key=key, version=1, authored_at=at, teams=tuple(teams), window=window)


def test_batches_keep_groups_and_pairs_together():
    docs = [_doc(f"co-{i}", ALL_TEAMS, at=f"2026-10-0{i}T00:00:00") for i in range(1, 4)]
    docs += [_doc(f"a-{i}", ["a"]) for i in range(6)]
    docs += [_doc(f"b-{i}", ["b"]) for i in range(5)]
    # a large group: split only on effective windows (a message/task pair shares one)
    docs += [_doc(f"c-{i}", ["c"], window=(f"2026-11-{i // 2 + 10}", None)) for i in range(16)]
    batches = cli.plan_batches(docs, 10)
    flat = [d.doc_key for b in batches for d in b]
    assert sorted(flat) == sorted(d.doc_key for d in docs) and len(flat) == len(set(flat))
    assert all(len(b) <= 11 for b in batches)
    assert {d.doc_key for d in batches[0]} >= {"co-1", "co-2", "co-3"}  # company-wide first
    where = {d.doc_key: i for i, b in enumerate(batches) for d in b}
    assert len({where[f"a-{i}"] for i in range(6)}) == 1 and len({where[f"b-{i}"] for i in range(5)}) == 1
    for i in range(0, 16, 2):  # pairs of the large group stay together
        assert where[f"c-{i}"] == where[f"c-{i + 1}"]
    assert [d.authored_at for d in batches[0]] == sorted(d.authored_at for d in batches[0])


def test_dry_run_runs_nothing(app, seeded, clock, id_factory):
    code, out = _main(seeded, "--dry-run", "--include-announced", clock=clock, id_factory=id_factory)
    assert code == 0 and "batch 1:" in "\n".join(out)
    assert _runs(app) == []


# ---- scoped interpret_corpus --------------------------------------------------------------------------


def test_build_task_validates_document_scope(app, seeded):
    s = app.state.session_factory()
    current = s.scalars(select(m.CorpusDocument).where(m.CorpusDocument.superseded_by_document_id.is_(None))).first()
    old = s.scalars(select(m.CorpusDocument).where(m.CorpusDocument.superseded_by_document_id.is_not(None))).first()

    def codes(params):
        with pytest.raises(DomainError) as exc:
            agent_runs.build_task(s, AgentRunCreate(task_type="interpret_corpus", params=params))
        return {r["code"] for r in exc.value.details["reasons"]}

    ok = agent_runs.build_task(s, AgentRunCreate(task_type="interpret_corpus", params={"document_ids": [current.id]}))
    assert ok.params == {"document_ids": [current.id]}
    assert codes({"document_ids": ["doc_nope"]}) == {"unknown_document"}
    assert codes({"document_ids": [old.id]}) == {"document_superseded"}
    assert codes({"document_ids": []}) == {"invalid_params"}
    assert codes({"document_ids": [current.id, current.id]}) == {"invalid_params"}
    assert codes({"document_ids": [f"d{i}" for i in range(21)]}) == {"invalid_params"}
    assert codes({"document_ids": [current.id], "mode": "x"}) == {"unexpected_params"}
    s.close()


def test_toolbox_refuses_documents_outside_scope(app, seeded, clock, id_factory):
    s = app.state.session_factory()
    a, b = s.scalars(select(m.CorpusDocument.id).where(m.CorpusDocument.superseded_by_document_id.is_(None))
                     .order_by(m.CorpusDocument.doc_key)).all()[:2]
    s.add(m.AgentRun(id="run_scope", created_at=clock.now(), task_type="interpret_corpus", input={},
                     runner_kind="fake", status="running", started_at=clock.now()))
    s.commit()
    s.close()
    tb = BackendToolbox(session_factory=app.state.session_factory, run_id="run_scope", source="fake_runner",
                        runner_kind="fake", clock=clock, ids=id_factory,
                        forecast_provider=app.state.forecast_provider, doc_scope=[a])
    assert [i["id"] for i in tb.search_corpus("")["items"]] == [a]
    tb.read_document(a)
    with pytest.raises(ToolError) as exc:
        tb.read_document(b)
    assert exc.value.code == "document_out_of_scope"
    with pytest.raises(ToolError) as exc:
        tb.record_signal({"summary": "x", "change_type": "expansion", "status": "current", "uncertainty": "u",
                          "team": "research", "citations": [{"document_id": b, "quote": "details"}]})
    assert exc.value.code == "document_out_of_scope"


# ---- end to end: fake runner -------------------------------------------------------------------------


def test_fake_runner_batches_are_scoped_idempotent_and_unlogged(app, seeded, clock, id_factory, tmp_path):
    log = tmp_path / "live_runs.log"
    code, out = _main(seeded, "--include-announced", "--batch", "4", "--log", str(log),
                      clock=clock, id_factory=id_factory)
    assert code == 0, out
    assert "FAKE stand-in" in out[0]
    runs = _runs(app)
    assert runs and all(r.status == "succeeded" and r.runner_kind == "fake" for r in runs)
    scoped = [r.input["task"]["params"]["document_ids"] for r in runs]
    assert all(1 <= len(ids) <= 5 for ids in scoped)
    assert sum(len(ids) for ids in scoped) == NORTHSTAR_SINCE_SEP + 4
    warnings = [w for r in runs for w in r.output["warnings"]]
    assert not any(w["code"] == "expected_document_missing" for w in warnings)  # noise in a scoped run
    s = app.state.session_factory()
    ext_ids = set(s.scalars(select(m.CorpusDocument.id).where(m.CorpusDocument.doc_key.like("ext-%"),
                                                               m.CorpusDocument.doc_key != "ext-old-policy")))
    signals = s.scalars(select(m.ContextSignal)).all()
    cited = {c.document_id for sig in signals for c in sig.citations}
    s.close()
    # non-Northstar docs yield nothing but a labelled warning each; Northstar docs still yield signals
    assert {w["document_id"] for w in warnings if w["code"] == "document_not_interpreted"} >= ext_ids
    assert not (cited & ext_ids)
    assert signals and all(sig.produced_by == "droid_fake" for sig in signals)
    assert not log.exists()  # only sdk runs are logged

    count = len(runs)
    code, out = _main(seeded, "--include-announced", "--batch", "4", "--log", str(log),
                      clock=clock, id_factory=id_factory)
    assert code == 0 and len(_runs(app)) == count  # idempotent: nothing left to interpret
    assert f"{NORTHSTAR_SINCE_SEP + 4} already interpreted" in out[0]
    code, _ = _main(seeded, "--include-announced", "--batch", "20", "--force", "--log", str(log),
                    clock=clock, id_factory=id_factory)
    assert code == 0 and len(_runs(app)) == count + 1
    s = app.state.session_factory()
    assert s.scalar(select(func.count()).select_from(m.ContextSignal)) == len(signals)  # re-run reuses signals
    s.close()


# ---- end to end: SdkDroidRunner on the fake droid_sdk ----------------------------------------------------


@pytest.fixture
def fake_sdk(monkeypatch):
    mod = fake_droid_sdk.build()
    monkeypatch.setitem(sys.modules, "droid_sdk", mod)
    monkeypatch.setitem(sys.modules, "droid_sdk.mcp", mod.mcp)
    return mod


def test_sdk_credit_cap_stops_before_exceeding(app, seeded, clock, id_factory, tmp_path, fake_sdk):
    """The fake SDK reports 10,801 factory_credits per run. Cap 25,000: two batches run, the third
    (21,602 + 10,801 > 25,000) is not started."""
    log = tmp_path / "live_runs.log"
    runner = SdkDroidRunner(executable="/nonexistent/droid", timeout_s=5)
    code, out = _main(seeded, "--batch", "2", "--credit-cap", "25000", "--batch-estimate", "10000",
                      "--log", str(log), runner=runner, clock=clock, id_factory=id_factory)
    assert code == 0, out
    runs = _runs(app)
    assert [r.status for r in runs] == ["succeeded", "succeeded"] and all(r.runner_kind == "sdk" for r in runs)
    assert any("stopped before batch 3" in line for line in out)
    lines = log.read_text().splitlines()
    assert len(lines) == 2 and all("app.interpret batch" in ln and '"factory_credits": 10801.0' in ln
                                   for ln in lines)
    prompts = fake_droid_sdk.STATE["prompts"]
    first_ids = runs[0].input["task"]["params"]["document_ids"]
    assert "Scope: this run covers ONLY these documents" in prompts[0]
    assert all(f"- {i}" in prompts[0] for i in first_ids)


def test_sdk_estimate_alone_can_stop_before_any_run(app, seeded, clock, id_factory, tmp_path, fake_sdk):
    runner = SdkDroidRunner(executable="/nonexistent/droid", timeout_s=5)
    code, out = _main(seeded, "--credit-cap", "50000", "--log", str(tmp_path / "l.log"), runner=runner,
                      clock=clock, id_factory=id_factory)
    assert code == 0 and _runs(app) == [] and any("stopped before batch 1" in ln for ln in out)


class _NoUsageSdk:
    kind = "sdk"

    def run(self, task, tools):
        tools.search_corpus("")
        return AgentRunOutput(summary="done", usage=None)


def test_sdk_batch_without_reported_credits_stops(app, seeded, clock, id_factory, tmp_path):
    code, out = _main(seeded, "--batch", "2", "--log", str(tmp_path / "l.log"), runner=_NoUsageSdk(),
                      clock=clock, id_factory=id_factory)
    assert code == 0 and len(_runs(app)) == 1
    assert any("cap can no longer be enforced" in ln for ln in out)


# ---- fail closed ---------------------------------------------------------------------------------------


def test_sdk_unavailable_fails_closed_without_running(app, seeded, clock, id_factory):
    code, out = _main(seeded, env={"DROID_RUNNER": "sdk"}, clock=clock, id_factory=id_factory)
    assert code == 2 and "missing_api_key" in out[-1] and "Nothing was run" in out[-1]
    assert _runs(app) == []


class _Unavailable:
    kind = "sdk"

    def run(self, task, tools):
        raise RunnerUnavailable("droid went away", reason="droid_unavailable")


def test_runner_unavailable_mid_run_stops_with_no_fallback(app, seeded, clock, id_factory, tmp_path):
    log = tmp_path / "l.log"
    code, out = _main(seeded, "--batch", "2", "--log", str(log), runner=_Unavailable(),
                      clock=clock, id_factory=id_factory)
    runs = _runs(app)
    assert code == 2 and [r.status for r in runs] == ["unavailable"]
    assert not any(r.runner_kind == "fake" for r in runs)
    assert len(log.read_text().splitlines()) == 1  # the attempted live batch is logged
    s = app.state.session_factory()
    assert s.scalar(select(func.count()).select_from(m.ContextSignal)) == 0
    s.close()


def test_failed_batch_is_not_counted_done(app, seeded, clock, id_factory, tmp_path):
    class Boom:
        kind = "fake"

        def run(self, task, tools):
            raise RuntimeError("boom")

    code, _ = _main(seeded, "--batch", "2", runner=Boom(), clock=clock, id_factory=id_factory)
    assert code == 1 and [r.status for r in _runs(app)] == ["failed"]
    code, out = _main(seeded, "--batch", "2", clock=clock, id_factory=id_factory)
    assert code == 0 and "0 already interpreted" in out[0]
