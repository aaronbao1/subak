"""The Droid eval harness itself: fake-runner suite, scoring of a misbehaving runner, CLI output, live-cap gating.

Nothing here calls Factory: runners are FakeDroidRunner or local stubs injected into the app.
"""

from __future__ import annotations

import json
from decimal import Decimal

import pytest

from app.agent.fake_runner import FakeDroidRunner
from app.agent.runner import AgentRunOutput, ToolError
from evals import report, run as cli, textcheck as tc
from evals.fixtures import FIXTURES, LIVE_PRIORITY
from evals.harness import live_count, run_suite
from evals.scenarios import SCENARIOS


def _by_id(res) -> dict[str, dict]:
    return {s["id"]: s for s in res.scenarios}


@pytest.fixture(scope="module")
def fake_suite(tmp_path_factory):
    return run_suite("fake", workdir=tmp_path_factory.mktemp("evals-fake"))


def test_fake_runner_passes_every_scenario(fake_suite):
    assert len(fake_suite.scenarios) == len(SCENARIOS) >= 10
    failing = {s["id"]: s["reasons"] for s in fake_suite.scenarios if s["status"] != "pass"}
    assert not failing, failing
    assert fake_suite.live_runs_used == 0 and fake_suite.live_log_total is None
    assert set(fake_suite.fixtures) == set(FIXTURES) == set(LIVE_PRIORITY)


def test_fake_suite_reproduces_reference_outcomes(fake_suite):
    add = fake_suite.fixtures["addition_50k"].proposals[0]
    tr = fake_suite.fixtures["transfer"].proposals[0]
    assert add["after"]["allocations"] == {"research": "95000.00", "product": "80000.00", "engineering": "75000.00"}
    assert tr["after"]["allocations"] == {"research": "85000.00", "product": "50000.00", "engineering": "65000.00"}
    stale = fake_suite.fixtures["stale_recovery"]
    assert stale.proposals[0]["rebased_from_proposal_id"] == stale.setup["stale_proposal_id"]
    assert stale.budget_before["state_version"] == stale.budget_after["state_version"] == 2


class LyingRunner:
    """Does no tool work and says everything a bad agent might say."""

    kind = "fake"

    def run(self, task, tools):
        return AgentRunOutput(summary=(
            "I have applied the change and the budget has been updated. The research expansion will cost "
            "$12,345.67 in tokens at $0.002 per 1,000 tokens."))


def test_misbehaving_runner_fails_with_reasons(tmp_path):
    res = run_suite("fake", workdir=tmp_path, runner=LyingRunner())
    s = _by_id(res)
    # it recorded no signals, so it treated nothing informal as current; every other scenario fails
    assert {k for k, v in s.items() if v["status"] != "fail"} == {"informal_cancelled_not_current"}
    reasons = {k: " ".join(v["reasons"]) for k, v in s.items()}
    assert "12345.67" in reasons["no_invented_token_cost"] and "per 1,000 tokens" in reasons["no_invented_token_cost"]
    assert "no current research signal cites research-eval-plan" in reasons["superseded_research_thread"]
    assert "no addition proposal drafted" in reasons["arithmetic_addition_250k"]
    assert "budget has been updated" in reasons["never_claims_saved"]
    assert "no pending_review draft rebased" in reasons["stale_recovery_offers_rebase"]
    assert "forecast" in reasons["forecast_unavailable_warns"]


class ThreadAsCurrentRunner(FakeDroidRunner):
    """Tries to record the superseded research thread and the marketing brainstorm as current signals."""

    def run(self, task, tools):
        if task.type != "interpret_corpus":
            return super().run(task, tools)
        docs = {d["doc_key"]: d for d in tools.search_corpus("")["items"]}
        refused: list[str] = []
        for key, quote, team in (("research-timeline-thread",
                                  "we will push the model-evaluation expansion to next period.", "research"),
                                 ("marketing-ideas-slack", "just brainstorming, not a plan", "marketing")):
            try:
                tools.record_signal({"team": team if team != "marketing" else None, "project": "x",
                                     "summary": "treated as the plan", "change_type": "timing_shift",
                                     "status": "current", "uncertainty": "none",
                                     "citations": [{"document_id": docs[key]["id"], "quote": quote}]})
            except ToolError as exc:
                refused.append(exc.code)
        return AgentRunOutput(summary=f"Recorded the plan. Refused: {refused}")


def test_superseded_and_informal_sources_treated_as_current_fail(tmp_path):
    ids = ["superseded_research_thread", "informal_cancelled_not_current", "product_timing_shift_cites_v2"]
    s = _by_id(run_suite("fake", workdir=tmp_path, runner=ThreadAsCurrentRunner(), scenario_ids=ids))
    assert {k: v["status"] for k, v in s.items()} == dict.fromkeys(ids, "fail")
    ctx_summary = s["superseded_research_thread"]["checks"][0]["reason"]
    assert "succeeded" in ctx_summary
    # the backend itself refuses a current signal resting only on the superseded thread ...
    assert [c["name"] for c in s["superseded_research_thread"]["checks"] if not c["passed"]] == [
        "thread_flagged_superseded", "current_plan_cited"]
    # ... but nothing stops an informal brainstorm being called current: only the eval catches that
    assert [c["name"] for c in s["informal_cancelled_not_current"]["checks"] if not c["passed"]] == [
        "no_current_from_informal_or_cancelled", "marketing_brainstorm_not_current"]
    assert any(r.startswith("no_current_from_informal_or_cancelled")
               for r in s["informal_cancelled_not_current"]["reasons"])


class AllToResearchRunner(FakeDroidRunner):
    """A valid but different judgment: the whole addition to research (what live run 3 did)."""

    rationale = "all to research"

    def run(self, task, tools):
        if task.params.get("mode") != "addition":
            return super().run(task, tools)
        b = tools.get_budgets()
        tools.draft_proposal({"action_type": "addition", "base_version": b["state_version"],
                              "envelope_increase": "50000.00", "rationale": self.rationale,
                              "lines": [{"to_team": "research", "amount": "50000.00"}]})
        return AgentRunOutput(summary="Drafted an addition; it is pending finance review and has not been applied.")


class AllToResearchFlaggingRunner(AllToResearchRunner):
    """The same split, but the rationale names engineering's remaining projected overrun."""

    rationale = ("All to research, as prioritized. Engineering stays projected 5000.00 over its allocation; "
                 "not covered by this draft.")


def test_other_split_fails_only_when_it_hides_another_overrun(tmp_path):
    # all +50k to research leaves engineering projected 65k against 60k: a valid split, but it must say so
    ids = ["arithmetic_addition_250k", "addition_vs_transfer", "never_claims_saved"]
    s = _by_id(run_suite("fake", workdir=tmp_path, runner=AllToResearchRunner(), scenario_ids=ids))
    assert s["arithmetic_addition_250k"]["status"] == "fail"
    assert s["arithmetic_addition_250k"]["reasons"] == [
        "addition_50k:flags_other_overruns: does not flag other team(s) still projected over their "
        "allocation: engineering +5000.00"]
    assert s["addition_vs_transfer"]["status"] == "pass"
    assert s["never_claims_saved"]["status"] == "pass"


def test_other_split_passes_when_it_flags_the_other_overrun(tmp_path):
    s = _by_id(run_suite("fake", workdir=tmp_path / "f", runner=AllToResearchFlaggingRunner(),
                         scenario_ids=["arithmetic_addition_250k"]))
    assert s["arithmetic_addition_250k"]["status"] == "pass"


def test_mentions_overrun_needs_team_and_overrun_in_one_sentence():
    assert tc.mentions_overrun("Engineering stays projected 5000.00 over its allocation.", "engineering")
    assert tc.mentions_overrun("Note: engineering has a 5,000 shortfall.", "engineering")
    # listing the projection is not flagging it (live run 17's rationale)
    assert not tc.mentions_overrun("Projections: research USD 85000.00, product USD 50000.00, "
                                   "engineering USD 65000.00.", "engineering")
    assert not tc.mentions_overrun("Engineering continues. Research is over its allocation.", "engineering")
    assert not tc.mentions_overrun("Overall, engineering is steady.", "engineering")


def test_cli_writes_json_and_markdown(tmp_path):
    out = tmp_path / "results"
    code = cli.main(["--runner", "fake", "--out", str(out), "--workdir", str(tmp_path / "db"),
                     "--scenario", "superseded_research_thread", "--scenario", "addition_vs_transfer"])
    assert code == 0
    data = json.loads((out / "fake.json").read_text())
    assert data["runner"] == "fake" and data["counts"] == {"pass": 2, "fail": 0, "not_run": 0}
    assert set(data["fixtures"]) == {"interpret", "addition_50k", "transfer"}
    assert data["fixtures"]["transfer"]["proposals"][0]["action_type"] == "transfer"
    md = (out / "fake.md").read_text()
    assert "# Droid eval results: `fake` runner" in md and "**2 pass, 0 fail, 0 not run**" in md


def test_cli_exit_code_reflects_failures(tmp_path, monkeypatch):
    real = run_suite
    monkeypatch.setattr(cli, "run_suite", lambda *a, **kw: real(*a, **kw, runner=LyingRunner()))
    code = cli.main(["--runner", "fake", "--out", str(tmp_path), "--workdir", str(tmp_path / "db"),
                     "--scenario", "unsupported_question_limited"])
    assert code == 1
    data = json.loads((tmp_path / "fake.json").read_text())
    assert data["counts"] == {"pass": 0, "fail": 1, "not_run": 0}
    assert any("states_limitation" in r for r in data["scenarios"][0]["reasons"])


# ---- live (sdk) gating: no real Droid; a stub runner reports kind "sdk" ----------------------------


class StubSdkRunner(FakeDroidRunner):
    kind = "sdk"

    def run(self, task, tools):
        out = super().run(task, tools)
        return out.model_copy(update={"usage": {"provider_reported": {"factory_credits": 1.0}, "subtype": "success"}})


def _log(path, n):
    path.write_text("".join(f"2026-10-24T00:00:0{i}+00:00 | prior | success | usage=null\n" for i in range(n)))


def test_sdk_runs_nothing_when_cap_minus_reserve_is_reached(tmp_path, monkeypatch):
    import app.agent.loader as loader

    def boom(*a, **kw):
        raise AssertionError("no runner may be loaded once the live cap is reached")

    monkeypatch.setattr(loader, "load_runner", boom)
    log = tmp_path / "live_runs.log"
    _log(log, 13)
    res = run_suite("sdk", workdir=tmp_path / "db", live_log=log, live_cap=15, live_reserve=2)
    assert {s["status"] for s in res.scenarios} == {"not_run"}
    assert all("live cap: 13 runs" in s["reasons"][0] for s in res.scenarios)
    assert res.live_runs_used == 0 and live_count(log) == 13 and res.live_log_total == 13
    assert "Fixtures not run live" in res.notes[0]
    md = report.markdown(res)
    assert f"**0 pass, 0 fail, {len(SCENARIOS)} not run**" in md and "Total lines in `backend/data/live_runs.log` afterwards: 13" in md


def test_sdk_live_runs_are_logged_and_limited(tmp_path):
    log = tmp_path / "live_runs.log"
    _log(log, 10)
    res = run_suite("sdk", workdir=tmp_path / "db", runner=StubSdkRunner(), live_log=log, max_live=2)
    ran = [n for n, c in res.fixtures.items() if c.ran]
    assert ran == list(LIVE_PRIORITY[:2]) and res.live_runs_used == 2
    lines = log.read_text().splitlines()
    assert len(lines) == 12 and res.live_log_total == 12
    assert lines[-2].split(" | ")[1].startswith("evals sdk: interpret: ")
    assert lines[-1].split(" | ")[2] == "succeeded (subtype success)"
    assert '"factory_credits": 1.0' in lines[-1]
    s = _by_id(res)
    assert s["superseded_research_thread"]["status"] == "pass"
    assert s["stale_recovery_offers_rebase"]["status"] == "not_run"
    assert "max_live=2" in s["stale_recovery_offers_rebase"]["reasons"][0]
    # one more run allowed by the cap (12 < 13): only the next priority fixture runs
    res2 = run_suite("sdk", workdir=tmp_path / "db2", runner=StubSdkRunner(), live_log=log)
    assert [n for n, c in res2.fixtures.items() if c.ran] == [LIVE_PRIORITY[0]]
    assert live_count(log) == 13


class MidStreamFailure(FakeDroidRunner):
    """Mimics SdkDroidRunner when the Droid process dies after turns were already paid for: the
    DroidProcessError is mapped to RunnerUnavailable, so the run ends `unavailable`."""

    kind = "sdk"

    def run(self, task, tools):
        from app.agent.runner import RunnerUnavailable

        tools.get_budgets()
        raise RunnerUnavailable("droid process exited mid-stream", reason="droid_process_error")


def test_sdk_runs_that_fail_mid_stream_are_still_logged_against_the_cap(tmp_path):
    log = tmp_path / "live_runs.log"
    res = run_suite("sdk", workdir=tmp_path / "db", runner=MidStreamFailure(), live_log=log, max_live=1)
    ctx = res.fixtures[LIVE_PRIORITY[0]]
    assert ctx.run["status"] == "unavailable"
    assert res.live_runs_used == 1 and live_count(log) == 1
    assert log.read_text().split(" | ")[2] == "unavailable"
    assert [n for n, c in res.fixtures.items() if c.ran] == [LIVE_PRIORITY[0]]  # max_live stopped the rest


def test_live_attempt_counts_a_request_that_raised_but_not_a_preflight_refusal():
    from evals.harness import live_attempt
    from evals.scenarios import RunCtx

    assert live_attempt(RunCtx(fixture="f", runner="sdk", posted=True, error="ReadTimeout: x"))
    assert not live_attempt(RunCtx(fixture="f", runner="sdk"))
    assert not live_attempt(RunCtx(fixture="f", runner="sdk", posted=True, http_status=503,
                                   response={"error": {"code": "runner_unavailable"}}))
    assert live_attempt(RunCtx(fixture="f", runner="sdk", posted=True, http_status=201,
                               run={"status": "unavailable"}))


def test_sdk_unavailable_runner_is_not_logged_as_a_live_run(tmp_path):
    log = tmp_path / "live_runs.log"
    res = run_suite("sdk", workdir=tmp_path / "db", live_log=log, scenario_ids=["unsupported_question_limited"])
    ctx = res.fixtures["unsupported_question"]
    assert ctx.http_status == 503 and ctx.run["status"] == "unavailable"  # no FACTORY_API_KEY in tests
    assert live_count(log) == 0 and res.live_runs_used == 0
    assert res.scenarios[0]["status"] == "fail"
    assert "status='unavailable'" in res.scenarios[0]["reasons"][0]


# ---- text heuristics ------------------------------------------------------------------------------


def test_money_figures_skip_dates_counts_and_percentages():
    text = ("Period 2026-P1 (2026-10-01 to 2026-12-31): research 60000.00 USD, $95k after, 1,250,000 tokens, "
            "12% growth, 3 records, version 2, 3,500 USD accrual.")
    assert tc.money_figures(text) == [Decimal("60000.00"), Decimal("95000"), Decimal("3500")]


def test_unsupported_figures_allow_sums_and_differences_only():
    known = {Decimal("60000.00"), Decimal("85000.00")}
    assert tc.unsupported_figures("over by 25,000.00; together 145000.00", known) == []
    assert tc.unsupported_figures("3x would be $180,000", known) == [Decimal("180000")]


def test_claim_detector_respects_negation_and_third_parties():
    assert tc.unnegated_claims("The budget has been updated.") == ["The budget has been updated."]
    assert tc.unnegated_claims("I have applied the change.") == ["I have applied the change."]
    for ok in ("Nothing has been applied.", "It has NOT been applied.", "It will be applied once finance approves.",
               "Proposal prop_1 was applied by fin-alice (version 1 -> 2).", "The approved research plan expands work.",
               "The draft is saved as pending_review."):
        assert tc.unnegated_claims(ok) == [], ok
    assert tc.per_token_prices("about $0.01 per 1k tokens") == ["$0.01 per 1k tokens"]
    assert tc.states_limitation("Token prices are not available in the data.")
    assert not tc.states_limitation("Research will cost 12,000 dollars.")


def test_cli_sdk_without_live_runs_keeps_recorded_results(tmp_path):
    out = tmp_path / "results"
    out.mkdir()
    (out / "sdk.json").write_text('{"kept": true}')
    log = tmp_path / "live_runs.log"
    _log(log, 13)
    code = cli.main(["--runner", "sdk", "--out", str(out), "--workdir", str(tmp_path / "db"),
                     "--live-log", str(log)])
    assert code == 0
    assert json.loads((out / "sdk.json").read_text()) == {"kept": True}
    assert json.loads((out / "sdk.not-live.json").read_text())["counts"]["not_run"] == len(SCENARIOS)


def test_setup_droid_runs_count_against_the_live_cap(tmp_path):
    # propose_reuses_signals needs an interpret run in setup: two live runs, both logged
    log = tmp_path / "live_runs.log"
    _log(log, 10)
    res = run_suite("sdk", workdir=tmp_path / "db", runner=StubSdkRunner(), live_log=log,
                    scenario_ids=["propose_reuses_signals"])
    assert res.live_runs_used == 2 and live_count(log) == 12
    assert "setup run" in log.read_text().splitlines()[10]
    assert _by_id(res)["propose_reuses_signals"]["status"] == "pass"
    # with room for only one more run the fixture is skipped, not half-run
    _log(log, 12)
    res = run_suite("sdk", workdir=tmp_path / "db2", runner=StubSdkRunner(), live_log=log, live_cap=15,
                    live_reserve=2, scenario_ids=["propose_reuses_signals"])
    assert res.live_runs_used == 0 and live_count(log) == 12
    assert _by_id(res)["propose_reuses_signals"]["status"] == "not_run"


class WrongPeopleRunner(FakeDroidRunner):
    """Records person signals with the wrong people/kind, a team signal with people, and no company signal."""

    def run(self, task, tools):
        if task.type != "interpret_corpus":
            return super().run(task, tools)
        docs = {d["doc_key"]: d for d in tools.search_corpus("")["items"]}
        quote = "Out of office 2026-10-26 to 2026-10-30, no eval runs scheduled while I am away."
        base = {"summary": "Theo is away and saves 40% of the research budget ($9,000.00).", "change_type": "reduction",
                "status": "current", "uncertainty": "u",
                "citations": [{"document_id": docs["research-availability-monday"]["id"], "quote": quote}]}
        tools.record_signal({**base, "scope": "person", "person_ids": ["research-ava-chen"],
                             "signal_kind": "steady"})
        try:
            tools.record_signal({**base, "scope": "team", "team": "research", "person_ids": ["research-theo-brandt"]})
        except ToolError:
            pass
        return AgentRunOutput(summary="Recorded people.")


def test_person_signals_scorer_catches_wrong_people_kinds_and_figures(tmp_path):
    s = _by_id(run_suite("fake", workdir=tmp_path, runner=WrongPeopleRunner(),
                         scenario_ids=["person_signals_cited"]))["person_signals_cited"]
    assert s["status"] == "fail"
    failed = {c["name"]: c["reason"] for c in s["checks"] if not c["passed"]}
    theo = failed["person:research-availability-monday"]
    assert "research-ava-chen" in theo and "signal_kind 'steady'" in theo
    assert "want exactly one current person signal citing research-harness-asana, got 0" in failed[
        "person:research-harness-asana"]
    assert "company:company-model-announcement-slack" in failed
    assert "40%" in failed["no_new_figures"] and "$9,000.00" in failed["no_new_figures"]
    # the backend refused the team-scope signal that named a person, so the eval sees none
    assert "team_signals_name_no_people" not in failed and "person_ids_real" not in failed


class RereadingProposeRunner(FakeDroidRunner):
    """Re-reads the whole corpus before every proposal even though current signals exist."""

    def _propose(self, task, tools):
        self._interpret(tools)
        return super()._propose(task, tools)


def test_propose_reuses_signals_fails_when_the_corpus_is_reread(tmp_path):
    s = _by_id(run_suite("fake", workdir=tmp_path, runner=RereadingProposeRunner(),
                         scenario_ids=["propose_reuses_signals"]))["propose_reuses_signals"]
    assert s["status"] == "fail"
    assert [c["name"] for c in s["checks"] if not c["passed"]] == ["no_corpus_reread"]
