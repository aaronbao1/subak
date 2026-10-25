"""Regression tests: drawer quick prompts and Revise/refresh through /compat chat, negative chat amounts,
system notes, per-day `complete` with unattributed spend, and grounded person attribution (backend
signal check, the Droid's list_signals team filter, the person eval and the propose prompt's table)."""

from __future__ import annotations

from collections import Counter
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.agent.toolbox import BackendToolbox
from app.compat import intent
from app.db.models import AgentRun
from app.db.session import transaction
from evals.scenarios import RunCtx, score_person_signals
from northstar_droid.sdk_runner import signals_table

API = "/compat/api"
TEAMS = [("engineering", "Engineering"), ("product", "Product"), ("research", "Research")]
GAPS = {"research": Decimal("25000"), "engineering": Decimal("5000"), "product": Decimal("-30000")}
ALLOCATED = {"research": 60000, "product": 80000, "engineering": 60000}
SPENT = {"research": 45000, "product": 20000, "engineering": 30000}
PROJECTED = {"research": 85000, "product": 50000, "engineering": 65000}
FINANCE = {"X-Actor-Id": "fin-ana", "X-Actor-Role": "finance_analyst"}


@pytest.fixture
def c(seeded) -> TestClient:
    with TestClient(seeded) as client:
        yield client


def get(c, path):
    r = c.get(f"{API}/{path}")
    assert r.status_code == 200, (path, r.text)
    return r.json()


def say(c, text):
    r = c.post(f"{API}/threads/main/messages", json={"content": text})
    assert r.status_code == 200, r.text
    return r.json()[-1]


def allocations(c):
    return {b["teamId"]: b["allocated"] for b in get(c, "budgets")}


# ---- quick prompt: "We have another $25,000 to allocate this week." ------------------------------


def test_another_amount_to_allocate_chip_drafts_an_addition(c):
    reply = say(c, "We have another $25,000 to allocate this week.")
    assert reply["content"].startswith("**Read as:** add $25,000.00 to the envelope"), reply["content"]
    p = get(c, f"proposals/{reply['proposalId']}")
    assert p["kind"] == "add_budget" and p["addedAmount"] == 25000
    assert p["totalAfter"] - p["totalBefore"] == 25000
    assert allocations(c) == ALLOCATED  # drafted, not applied


@pytest.mark.parametrize("text", [
    "why did you allocate $25,000 to research?",
    "another question: what is research spending on?",
    "how should we allocate the budget?",
])
def test_allocate_and_another_without_a_request_stay_questions(text):
    p = intent.parse(text, teams=TEAMS, gaps=GAPS)
    assert p.ask is None and p.run["task_type"] == "answer_question", p.read_as


# ---- negative amounts ----------------------------------------------------------------------------


@pytest.mark.parametrize("text", [
    "add -5k prioritizing research",
    "add $-5,000 for research",
    "add minus $5,000 to research",
    "move -10k toward research",
    "add −5k for research",
])
def test_negative_chat_amount_asks_instead_of_drafting(text):
    p = intent.parse(text, teams=TEAMS, gaps=GAPS)
    assert p.run is None and p.ask and "negative" in p.read_as, (text, p.read_as)


def test_hyphenated_words_are_not_negative_amounts():
    p = intent.parse("top-up 5k for research", teams=TEAMS, gaps=GAPS)
    assert p.run["params"] == {"mode": "addition", "amount": "5000.00", "prioritize": "research"}


def test_negative_amount_through_chat_drafts_nothing(c):
    reply = say(c, "add -5k prioritizing research")
    assert "negative" in reply["content"] and reply.get("proposalId") is None
    assert get(c, "proposals") == []


# ---- Revise / "Ask for a refreshed proposal" (prefill "Revise this proposal: ") ------------------


def test_revise_prefill_on_one_pending_proposal_asks_what_to_change(c):
    pid = say(c, "add 50k prioritizing research")["proposalId"]
    reply = say(c, "Revise this proposal: ")
    assert reply.get("proposalId") is None and "What should change in this draft?" in reply["content"]
    assert get(c, f"proposals/{pid}")["status"] == "proposed"


def test_revise_with_a_change_replaces_the_open_proposal(c):
    pid = say(c, "add 50k prioritizing research")["proposalId"]
    reply = say(c, "Revise this proposal: make it 40k for research instead")
    new = reply["proposalId"]
    assert new and new != pid, reply["content"]
    assert reply["content"].startswith("**Read as:** revise the selected draft: add $40,000.00 to the envelope")
    assert "This draft replaces the earlier version" in reply["content"]
    assert "prop_" not in reply["content"]
    p = get(c, f"proposals/{new}")
    assert p["revisesProposalId"] == pid and p["addedAmount"] == 40000 and p["status"] == "proposed"
    assert get(c, f"proposals/{pid}")["status"] == "revised"
    assert allocations(c) == ALLOCATED
    # the revised one can no longer be decided
    assert c.post(f"{API}/proposals/{pid}/apply", json={}).status_code == 409


def test_revise_without_an_amount_asks_and_changes_nothing(c):
    pid = say(c, "add 50k prioritizing research")["proposalId"]
    reply = say(c, "Revise this proposal: put more into research")
    assert reply.get("proposalId") is None and "How much" in reply["content"]
    assert get(c, f"proposals/{pid}")["status"] == "proposed"


def test_revise_prefill_on_a_stale_proposal_refreshes_that_proposal(c):
    tid = say(c, "rebalance the budget toward research")["proposalId"]
    add = say(c, "add 50k prioritizing research")["proposalId"]
    assert c.post(f"{API}/proposals/{add}/apply", json={}).status_code == 200
    assert get(c, f"proposals/{tid}")["status"] == "stale"
    reply = say(c, "Revise this proposal: ")
    assert reply["content"].startswith("**Read as:** refresh the outdated draft"), reply["content"]
    new = reply["proposalId"]
    assert new and get(c, f"proposals/{new}")["revisesProposalId"] == tid


def test_revise_prefill_with_several_open_proposals_asks_which(c):
    tid = say(c, "rebalance the budget toward research")["proposalId"]
    aid = say(c, "add 50k prioritizing research")["proposalId"]
    reply = say(c, "Revise this proposal: ")
    assert reply.get("proposalId") is None
    assert "Which proposal should I revise?" in reply["content"]
    assert "Select a draft" in reply["content"] and "prop_" not in reply["content"]
    assert {p["id"]: p["status"] for p in get(c, "proposals")} == {tid: "proposed", aid: "proposed"}
    # naming one revises that one, keeping its mode (a transfer: the amount caps what moves)
    reply = say(c, f"Revise {tid}: 10k")
    new = reply["proposalId"]
    assert reply["content"].startswith("**Read as:** revise the selected draft: redistribute"), reply["content"]
    p = get(c, f"proposals/{new}")
    assert p["kind"] == "redistribute" and p["revisesProposalId"] == tid
    statuses = {p["id"]: p["status"] for p in get(c, "proposals")}
    assert statuses[tid] == "revised" and statuses[aid] == "proposed"


def test_refresh_with_several_stale_proposals_asks_then_refreshes_the_named_one(c):
    older = say(c, "rebalance the budget toward research")["proposalId"]
    newer = say(c, "add 20k prioritizing product")["proposalId"]
    assert newer != older
    add = say(c, "add 50k prioritizing research")["proposalId"]
    assert c.post(f"{API}/proposals/{add}/apply", json={}).status_code == 200
    reply = say(c, "refresh the proposal")
    assert reply.get("proposalId") is None and "Which proposal should I refresh?" in reply["content"]
    reply = say(c, f"refresh {older}")
    assert reply["content"].startswith("**Read as:** refresh the outdated draft")
    assert get(c, f"proposals/{reply['proposalId']}")["revisesProposalId"] == older
    assert get(c, f"proposals/{newer}")["status"] == "stale"


def test_revise_of_a_settled_proposal_asks(c):
    pid = say(c, "add 50k prioritizing research")["proposalId"]
    assert c.post(f"{API}/proposals/{pid}/reject", json={}).status_code == 200
    reply = say(c, f"Revise {pid}: add 40k for research")
    assert reply.get("proposalId") is None and "not open for revision" in reply["content"]


# ---- system notes are not finance notes ----------------------------------------------------------


def test_apply_with_a_real_note_returns_it(c):
    pid = say(c, "add 50k prioritizing research")["proposalId"]
    d = c.post(f"{API}/proposals/{pid}/apply", json={"note": "Covers the eval sprint"}).json()
    assert d["note"] == "Covers the eval sprint"
    assert get(c, "decisions")[0]["note"] == "Covers the eval sprint"


# ---- per-day `complete` with unattributed spend (the --with-planted state) -----------------------


def test_unattributed_records_do_not_mark_every_team_day_partial(seeded):
    from app.seed.planted import load_planted

    s = seeded.state.session_factory()
    try:
        load_planted(s, clock=seeded.state.clock, ids=seeded.state.id_factory)
        s.commit()
    finally:
        s.close()
    with TestClient(seeded) as c:
        rows = get(c, "spending")
        assert any(r["teamId"] == "unattributed" for r in rows)
        team_rows = [r for r in rows if r["teamId"] in SPENT]
        assert team_rows and all(r["complete"] for r in team_rows)
        complete_spend = Counter()
        for r in team_rows:
            if r["complete"]:
                complete_spend[r["teamId"]] += r["amount"]
        assert dict(complete_spend) == SPENT
        for f in get(c, "forecasts"):
            if "personId" in f or f["teamId"] not in SPENT:
                continue
            assert complete_spend[f["teamId"]] + sum(pt["projected"] for pt in f["daily"]) == f["projected"]
            assert f["projected"] == PROJECTED[f["teamId"]]


# ---- person attribution is grounded in the cited text --------------------------------------------


def _doc(c, key):
    return next(d for d in c.get("/api/documents").json()["items"] if d["doc_key"] == key)


def _person_signal(doc, person_ids, quote):
    return {"scope": "person", "person_ids": person_ids, "signal_kind": "model_change", "summary": "s",
            "change_type": "other", "status": "current", "uncertainty": "u",
            "citations": [{"document_id": doc["id"], "quote": quote}]}


def test_signal_refuses_a_person_the_cited_document_does_not_name(c):
    doc = _doc(c, "research-model-switch-slack")
    detail = c.get(f"/api/documents/{doc['id']}").json()
    assert "Theo Brandt" not in detail["content"] and "Omar Haddad" in detail["content"]
    quote = detail["content"][:40]
    r = c.post("/api/signals", json=_person_signal(doc, ["research-theo-brandt"], quote), headers=FINANCE)
    assert r.status_code == 422, r.text
    reasons = r.json()["error"]["details"]["reasons"]
    assert [x["code"] for x in reasons] == ["person_not_in_citations"]
    assert reasons[0]["person_id"] == "research-theo-brandt"
    r = c.post("/api/signals", json=_person_signal(doc, ["research-omar-haddad"], quote), headers=FINANCE)
    assert r.status_code == 201, r.text
    assert r.json()["person_ids"] == ["research-omar-haddad"]


def _toolbox(app, run_id="run_g"):
    with transaction(app.state.session_factory) as s:
        s.add(AgentRun(id=run_id, task_type="answer_question", input={}, runner_kind="fake", status="running",
                       started_at=app.state.clock.now()))
    return BackendToolbox(session_factory=app.state.session_factory, run_id=run_id, source="fake_runner",
                          runner_kind="fake", clock=app.state.clock, ids=app.state.id_factory,
                          forecast_provider=app.state.forecast_provider)


def test_droid_cannot_attach_an_unnamed_teammate(seeded):
    from app.agent.runner import ToolError

    tb = _toolbox(seeded)
    doc = next(d for d in tb.search_corpus(query="")["items"] if d["doc_key"] == "research-model-switch-slack")
    content = tb.read_document(doc["id"])["content"]
    with pytest.raises(ToolError) as exc:
        tb.record_signal(_person_signal(doc, ["research-theo-brandt"], content[:40]))
    assert exc.value.code == "validation_failed"
    assert exc.value.details["reasons"][0]["code"] == "person_not_in_citations"


def test_droid_list_signals_team_filter_keeps_company_signals(c, seeded):
    doc = _doc(c, "company-model-announcement-slack")
    quote = c.get(f"/api/documents/{doc['id']}").json()["content"][:40]
    body = {"scope": "company", "signal_kind": "model_change", "summary": "default model change",
            "change_type": "other", "status": "current", "uncertainty": "u",
            "citations": [{"document_id": doc["id"], "quote": quote}]}
    r = c.post("/api/signals", json=body, headers=FINANCE)
    assert r.status_code == 201, r.text
    company_id = r.json()["id"]
    tb = _toolbox(seeded)
    ids = [s["id"] for s in tb.call("list_signals", {"status": "current", "team": "research"})["items"]]
    assert company_id in ids
    only_team = tb.call("list_signals", {"status": "current", "team": "research", "include_company": False})
    assert company_id not in [s["id"] for s in only_team["items"]]


# ---- the person eval checks the text, not just the tags ------------------------------------------


PEOPLE = [{"id": "research-omar-haddad", "team": "research", "name": "Omar Haddad"},
          {"id": "research-ava-chen", "team": "research", "name": "Ava Chen"},
          {"id": "research-theo-brandt", "team": "research", "name": "Theo Brandt"}]


def _ctx(content: str, tags: list[str], person_ids: list[str]) -> RunCtx:
    doc = {"id": "doc_1", "doc_key": "research-model-switch-slack", "version": 1, "is_current": True,
           "person_tags": tags, "content": content}
    sig = {"id": "sig_1", "agent_run_id": "run_1", "status": "current", "scope": "person", "team": "research",
           "person_ids": person_ids, "signal_kind": "model_change", "summary": "switch",
           "citations": [{"document_id": "doc_1", "doc_key": doc["doc_key"], "version": 1, "quote": "switch"}]}
    return RunCtx(fixture="interpret", runner="fake", ran=True, run={"id": "run_1", "status": "succeeded"},
                  people=PEOPLE, documents={"doc_1": doc}, signals=[sig])


def _checks(ctx):
    return {ch.name: ch for ch in score_person_signals({"interpret": ctx})}


def test_person_eval_fails_when_the_tagged_person_is_not_named_in_the_text():
    checks = _checks(_ctx("We switch the eval model next week.", ["research-omar-haddad"], ["research-omar-haddad"]))
    assert not checks["person:research-model-switch-slack"].passed
    assert not checks["person_ids_grounded"].passed


def test_person_eval_fails_when_a_signal_copies_a_tag_the_text_does_not_back():
    ctx = _ctx("Omar Haddad: we switch the eval model.", ["research-theo-brandt", "research-omar-haddad"],
               ["research-theo-brandt", "research-omar-haddad"])
    checks = _checks(ctx)
    assert not checks["person:research-model-switch-slack"].passed
    assert "research-theo-brandt" in checks["person_ids_grounded"].reason


def test_person_eval_is_order_insensitive():
    ctx = _ctx("Omar Haddad and Ava Chen: we switch the eval model.", ["research-omar-haddad", "research-ava-chen"],
               ["research-ava-chen", "research-omar-haddad"])
    checks = _checks(ctx)
    assert checks["person:research-model-switch-slack"].passed, checks["person:research-model-switch-slack"].reason
    assert checks["person_ids_grounded"].passed


# ---- propose prompt signal table ------------------------------------------------------------------


def test_signals_table_labels_company_only_for_company_scope():
    table = signals_table([
        {"id": "sig_t", "team": None, "scope": "team", "signal_kind": "steady", "title": "marketing idea"},
        {"id": "sig_c", "team": None, "scope": "company", "signal_kind": "model_change", "title": "default model"},
    ])
    assert "| sig_t | (no team) | team |" in table
    assert "| sig_c | (company) | company |" in table
