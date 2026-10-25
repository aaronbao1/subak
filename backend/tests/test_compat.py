"""Frontend compat layer (/compat/api): shapes, seed numbers, chat -> proposal -> apply, authority, errors.

FakeDroidRunner only; no live Droid. Every response is re-validated against app/compat/schemas.py (the
Pydantic mirror of the frontend's TypeScript contract, itself drift-checked in test_compat_contract.py).
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from pydantic import TypeAdapter
from sqlalchemy import func, select

from app.compat import intent, mappers
from app.compat import schemas as S
from app.compat.errors import ALREADY_APPLIED, ALREADY_REJECTED, STALE
from app.config import Settings
from app.db.models import AgentRun, AssistantMessage, ForecastSnapshot
from app.main import create_app
from app.seed.northstar import seed

API = "/compat/api"
IMPORTER = {"X-Actor-Id": "imp-1", "X-Actor-Role": "importer"}
SPENT = {"research": 45000, "product": 20000, "engineering": 30000}
ALLOCATED = {"research": 60000, "product": 80000, "engineering": 60000}
PROJECTED = {"research": 85000, "product": 50000, "engineering": 65000}
OUTCOME_B = {"research": 95000, "product": 80000, "engineering": 75000}

SHAPES = {
    "company": S.Company, "teams": list[S.Team], "spending": list[S.SpendingRecord], "budgets": list[S.Budget],
    "forecasts": list[S.Forecast], "context": list[S.ContextItem], "documents": list[S.CompanyDocument],
    "proposals": list[S.AllocationProposal], "decisions": list[S.Decision], "threads/main": list[S.AssistantMessage],
}


@pytest.fixture
def c(seeded) -> TestClient:
    with TestClient(seeded) as client:
        yield client


def get(c, path, model=None, status=200):
    r = c.get(f"{API}/{path}")
    assert r.status_code == status, r.text
    body = r.json()
    if model is not None:
        TypeAdapter(model).validate_python(body)
    return body


def say(c, text, thread="main", headers=None):
    r = c.post(f"{API}/threads/{thread}/messages", json={"content": text}, headers=headers or {})
    assert r.status_code == 200, r.text
    user, reply = TypeAdapter(list[S.AssistantMessage]).validate_python(r.json())
    assert user.role == "user" and user.content == text and reply.role == "assistant"
    return r.json()[1]


def by_team(rows, field):
    return {r["teamId"]: r[field] for r in rows}


def assert_error(r, status, message=None):
    assert r.status_code == status, r.text
    body = r.json()
    assert isinstance(body["error"], str) and body["error"] and isinstance(body["code"], str)
    if message is not None:
        assert body["error"] == message
    return body


# ---- shapes and seed numbers -------------------------------------------------------------------


def test_every_read_route_validates_against_the_frontend_contract(c):
    say(c, "what changed in the documents?")  # context and threads non-empty
    for path, model in SHAPES.items():
        body = get(c, path, model)
        assert body or path in ("proposals", "decisions"), path
    doc_id = get(c, "documents")[0]["id"]
    get(c, f"documents/{doc_id}", S.CompanyDocument)


def test_company_period_and_demo_label(c):
    co = get(c, "company")
    assert co == {"id": "northstar", "name": "Northstar Software", "isDemo": True, "budgetUnit": "usd",
                  "currentPeriod": {"start": "2026-10-01", "end": "2026-12-31", "label": "Northstar planning period"}}


def test_teams_get_frontend_color_tokens(c):
    teams = get(c, "teams")
    assert [t["id"] for t in teams] == ["engineering", "product", "research"]
    assert [t["color"] for t in teams] == ["var(--chart-1)", "var(--chart-2)", "var(--chart-3)"]
    assert all("description" not in t for t in teams)  # not stored: omitted, not invented
    # Team.lead is derived from the person whose role ends with " lead".
    assert {t["id"]: t["lead"] for t in teams} == {"engineering": "Arjun Rao", "product": "Maya Patel",
                                                  "research": "Ava Chen"}


def test_seed_totals_through_compat(c):
    rows = get(c, "spending")
    spent: dict[str, int] = {}
    for r in rows:
        spent[r["teamId"]] = spent.get(r["teamId"], 0) + r["amount"]
    assert spent == SPENT
    assert all(isinstance(r["amount"], int) and r["unit"] == "usd" and r["complete"] for r in rows)
    assert by_team(get(c, "budgets"), "allocated") == ALLOCATED
    assert {b["version"] for b in get(c, "budgets")} == {"1"}
    fc = get(c, "forecasts")
    team_fc = [f for f in fc if "personId" not in f]
    assert by_team(team_fc, "projected") == PROJECTED
    assert all(f["status"] == "available" and f["basis"] == "full_period" and f["origin"] == "placeholder"
               and "low" not in f and "high" not in f for f in fc)


def test_included_usage_counts_zero_and_is_labeled(c):
    rows = [r for r in get(c, "spending") if r["component"] == "included_usage"]
    assert {r["teamId"] for r in rows} == {"research", "engineering"}
    assert all(r["amount"] == 0 and r["provenance"] == "usage_only" for r in rows)
    research = next(r for r in rows if r["teamId"] == "research" and r["date"] == "2026-10-01")
    assert "notional value $" in research["source"] and "is not counted as spend" in research["source"]
    assert "(simulated)" in research["source"].lower() or "simulated" in research["source"].lower()


def test_spending_filters(c):
    assert {r["teamId"] for r in get(c, "spending?teamId=product")} == {"product"}
    rows = get(c, "spending?from=2026-10-10&to=2026-10-15")
    assert rows and all("2026-10-10" <= r["date"] <= "2026-10-15" for r in rows)
    assert get(c, "spending?teamId=nobody") == []
    assert_error(c.get(f"{API}/spending?from=not-a-date"), 422)


def test_unattributed_spend_gets_a_pseudo_team_and_marks_partial(c):
    csv = ("record_id,occurred_at,source_account,provider,cost_category,value_kind,amount,unit\n"
           "mk-1,2026-10-18T00:00:00Z,ws-marketing,openai,direct_api,simulated,700.00,USD\n"
           "cx-1,2026-10-18T00:00:00Z,ws-research,openai,unpriced_usage,measured,,USD\n")
    r = c.post("/api/imports", data={"source_kind": "northstar_billing"},
               files={"file": ("extra.csv", csv.encode(), "text/csv")}, headers=IMPORTER)
    assert r.status_code in (200, 201), r.text
    teams = get(c, "teams", list[S.Team])
    assert teams[-1]["id"] == "unattributed" and teams[-1]["color"] == "var(--muted-foreground)"
    rows = get(c, "spending", list[S.SpendingRecord])
    un = [r for r in rows if r["teamId"] == "unattributed"]
    assert len(un) == 1 and un[0]["amount"] == 700 and un[0]["complete"] is False
    # Company total is not understated; unpriced token rows never become dollars.
    assert sum(r["amount"] for r in rows) == sum(SPENT.values()) + 700
    assert all(r["component"] != "unpriced_usage" for r in rows)
    # `complete` is per day: the unattributed row is partial, the teams' own days stay complete (the
    # period-wide coverage flag would have marked every day of every team partial).
    assert all(r["complete"] for r in rows if r["teamId"] != "unattributed")


def test_documents_list_has_bodies_and_supersession(c):
    docs = get(c, "documents")
    assert len(docs) == 13 and all(d["body"].strip() for d in docs)
    v1 = next(d for d in docs if d["title"].startswith("Product launch plan - assistant"))
    assert v1["supersededBy"] and v1["kind"] == "plan" and v1["origin"].endswith("(simulated)")
    assert get(c, f"documents/{v1['id']}")["body"] == v1["body"]
    # DataClient.getDocument resolves to `CompanyDocument | undefined`: an unknown id is 200 null, not 404
    r = c.get(f"{API}/documents/doc_missing")
    assert r.status_code == 200 and r.json() is None


def test_context_is_empty_until_interpreted_then_cited(c):
    assert get(c, "context") == []
    say(c, "Read the documents and tell me what changed")
    items = get(c, "context", list[S.ContextItem])
    research = [i for i in items if i["teamIds"] == ["research"]]
    # The research plan and the thread it supersedes (person-scope research items cite other documents).
    current = next(i for i in research if "supersedes" in i)
    old = next(i for i in research if "supersededBy" in i)
    assert current["expectedEffect"] == "increase" and current["confidence"] == "high"
    assert current["claimType"] == "stated_plan" and current["kind"] == "plan"
    assert old["confidence"] == "low" and old["supersededBy"] == current["id"]
    assert current["supersedes"] == [old["id"]]
    product = next(i for i in items if i["teamIds"] == ["product"]
                   and i["sources"][0]["title"].startswith("Product launch plan"))
    # G5: a timing shift's direction comes from its typed kind (the launch is deferred -> decrease).
    assert product["expectedEffect"] == "decrease" and product["signal"] == "project_deferred"
    for i in items:
        assert i["sources"] and all(s["excerpt"] and s["locator"].startswith("chars ") for s in i["sources"])
        assert len(i["title"]) <= mappers.TITLE_MAX
    by_product = get(c, "context?teamId=product")
    assert product["id"] in {i["id"] for i in by_product}
    assert all(i["teamIds"] == ["product"] or i["scope"] == "company" for i in by_product)


def test_read_routes_never_write(c, seeded):
    s = seeded.state.session_factory()
    try:
        before = (s.scalar(select(func.count()).select_from(ForecastSnapshot)),
                  s.scalar(select(func.count()).select_from(AgentRun)))
        for path in SHAPES:
            get(c, path)
        s.expire_all()
        after = (s.scalar(select(func.count()).select_from(ForecastSnapshot)),
                 s.scalar(select(func.count()).select_from(AgentRun)))
    finally:
        s.close()
    assert before == after == (0, 0)


# ---- chat -> proposal -> apply / reject ---------------------------------------------------------


def test_chat_addition_then_apply_once(c):
    reply = say(c, "Add 50k prioritizing research")
    assert reply["content"].startswith("**Read as:** add $50,000.00 to the envelope, prioritize Research.")
    assert "Simulated" in reply["content"] and reply["toolCalls"] and reply["citations"]
    pid = reply["proposalId"]
    p = get(c, f"proposals/{pid}", S.AllocationProposal)
    assert p["kind"] == "add_budget" and p["status"] == "proposed" and p["basedOnBudgetVersion"] == "1"
    assert p["totalBefore"] == 200000 and p["totalAfter"] == 250000 and p["addedAmount"] == 50000
    assert by_team(p["lines"], "after") == OUTCOME_B and by_team(p["lines"], "before") == ALLOCATED
    assert sum(ln["after"] for ln in p["lines"]) == p["totalAfter"]
    assert [f["teamId"] for f in p["forecastsReviewed"]] == ["engineering", "product", "research"]
    assert by_team(get(c, "budgets"), "allocated") == ALLOCATED  # drafting changes nothing

    r = c.post(f"{API}/proposals/{pid}/apply", json={"note": "Covers the approved research plan"})
    assert r.status_code == 200, r.text
    d = S.Decision.model_validate(r.json()).model_dump(exclude_none=True)
    assert d["action"] == "applied" and d["kind"] == "add_budget" and d["appliedBy"] == "Finance approver (demo)"
    assert d["note"] == "Covers the approved research plan" and d["rationale"] == p["rationale"]
    assert by_team(d["lines"], "after") == OUTCOME_B
    assert d["forecastsReviewed"] == p["forecastsReviewed"]
    budgets = get(c, "budgets")
    assert by_team(budgets, "allocated") == OUTCOME_B and {b["version"] for b in budgets} == {"2"}
    assert get(c, f"proposals/{pid}")["status"] == "applied"

    assert_error(c.post(f"{API}/proposals/{pid}/apply", json={}), 409, ALREADY_APPLIED)
    assert_error(c.post(f"{API}/proposals/{pid}/reject", json={}), 409, ALREADY_APPLIED)
    assert by_team(get(c, "budgets"), "allocated") == OUTCOME_B
    [dec] = get(c, "decisions", list[S.Decision])
    assert dec["id"] == d["id"]


def test_apply_without_note_uses_default_reason(c):
    pid = say(c, "add $50,000 for research")["proposalId"]
    r = c.post(f"{API}/proposals/{pid}/apply", json={})
    # The stored default reason is not finance's words, so it is not returned as a note (the UI quotes notes).
    assert r.status_code == 200 and "note" not in r.json()
    [d] = get(c, "decisions")
    assert "note" not in d


def test_stale_proposal_refused_then_refreshed_via_chat(c):
    transfer = say(c, "rebalance the budget toward research")
    assert transfer["content"].startswith("**Read as:** redistribute the existing budget toward Research")
    tid = transfer["proposalId"]
    t = get(c, f"proposals/{tid}")
    assert t["kind"] == "redistribute" and t["totalAfter"] == t["totalBefore"] and "addedAmount" not in t
    add = say(c, "add 50k prioritizing research")["proposalId"]
    assert get(c, f"proposals/{tid}")["status"] == "proposed"
    assert c.post(f"{API}/proposals/{add}/apply", json={}).status_code == 200
    assert get(c, f"proposals/{tid}")["status"] == "stale"  # base version moved

    assert_error(c.post(f"{API}/proposals/{tid}/apply", json={}), 409, STALE)
    assert get(c, f"proposals/{tid}")["status"] == "stale"
    assert by_team(get(c, "budgets"), "allocated") == OUTCOME_B

    refreshed = say(c, "Please refresh the proposal")
    assert refreshed["content"].startswith(f"**Read as:** refresh stale proposal {tid}")
    new = get(c, f"proposals/{refreshed['proposalId']}", S.AllocationProposal)
    assert new["revisesProposalId"] == tid and new["basedOnBudgetVersion"] == "2" and new["status"] == "proposed"


def test_reject_records_a_decision_and_changes_nothing(c):
    pid = say(c, "add 50k prioritizing research")["proposalId"]
    r = c.post(f"{API}/proposals/{pid}/reject", json={})
    assert r.status_code == 200, r.text
    p = S.AllocationProposal.model_validate(r.json())
    assert p.status == "rejected"
    [d] = get(c, "decisions")
    assert d["action"] == "rejected" and d["proposalId"] == pid and by_team(d["lines"], "after") == OUTCOME_B
    assert by_team(get(c, "budgets"), "allocated") == ALLOCATED
    assert {b["version"] for b in get(c, "budgets")} == {"1"}
    assert_error(c.post(f"{API}/proposals/{pid}/reject", json={}), 409, ALREADY_REJECTED)
    assert_error(c.post(f"{API}/proposals/{pid}/apply", json={}), 409, ALREADY_REJECTED)


def test_lists_are_newest_first(c):
    first = say(c, "add 50k prioritizing research")["proposalId"]
    c.post(f"{API}/proposals/{first}/reject", json={})
    second = say(c, "add 20k prioritizing engineering")["proposalId"]
    c.post(f"{API}/proposals/{second}/reject", json={})
    assert [p["id"] for p in get(c, "proposals")] == [second, first]
    assert [d["proposalId"] for d in get(c, "decisions")] == [second, first]


# ---- authority ----------------------------------------------------------------------------------


def test_chat_actor_cannot_approve_its_own_run_anywhere(c):
    pid = say(c, "add 50k prioritizing research")["proposalId"]
    as_requester = {"X-Actor-Id": "dashboard-analyst", "X-Actor-Role": "finance_approver"}
    r = c.post(f"/api/proposals/{pid}/decision", json={"outcome": "approve", "rationale": "mine"},
               headers={**as_requester, "Idempotency-Key": "k-1"})
    assert r.status_code == 403 and r.json()["error"]["code"] == "self_approval_forbidden"
    body = assert_error(c.post(f"{API}/proposals/{pid}/apply", json={}, headers=as_requester), 403)
    assert body["code"] == "self_approval_forbidden" and "cannot approve" in body["error"]
    assert get(c, f"proposals/{pid}")["status"] == "proposed"


def test_header_identity_overrides_demo_actor_and_roles_still_apply(c):
    pid = say(c, "add 50k prioritizing research")["proposalId"]
    analyst = {"X-Actor-Id": "fin-ana", "X-Actor-Role": "finance_analyst"}
    assert assert_error(c.post(f"{API}/proposals/{pid}/apply", json={}, headers=analyst), 403)["code"] == "role_forbidden"
    droid = {"X-Actor-Id": "droid", "X-Actor-Role": "droid_agent"}
    assert assert_error(c.post(f"{API}/proposals/{pid}/reject", json={}, headers=droid), 403)["code"] == "role_forbidden"
    assert_error(c.post(f"{API}/proposals/{pid}/apply", json={}, headers={"X-Actor-Id": "x"}), 401)
    r = c.post(f"{API}/proposals/{pid}/apply", json={}, headers={"X-Actor-Id": "fin-bob", "X-Actor-Role": "finance_approver"})
    assert r.status_code == 200 and r.json()["appliedBy"] == "fin-bob"


# ---- chat behavior ------------------------------------------------------------------------------


def test_chat_asks_instead_of_guessing_an_amount(c, seeded):
    reply = say(c, "can we add more budget for product?")
    assert "How much should be added" in reply["content"] and "proposalId" not in reply
    s = seeded.state.session_factory()
    try:
        assert s.scalar(select(func.count()).select_from(AgentRun)) == 0
    finally:
        s.close()


def test_question_is_read_only_answer(c):
    reply = say(c, "How is product tracking against its allocation?")
    assert reply["content"].startswith("**Read as:** a question")
    assert "proposalId" not in reply and reply["toolCalls"]
    assert by_team(get(c, "budgets"), "allocated") == ALLOCATED


def test_threads_persist_in_order_and_are_isolated(c):
    say(c, "How is research doing?")
    say(c, "add 10k for engineering", thread="other")
    main = get(c, "threads/main", list[S.AssistantMessage])
    other = get(c, "threads/other")
    assert [m["role"] for m in main] == ["user", "assistant"] and len(other) == 2
    assert {m["threadId"] for m in main} == {"main"} and other[1].get("proposalId")
    assert get(c, "threads/never-used") == []


def test_empty_message_is_a_plain_422(c):
    assert_error(c.post(f"{API}/threads/main/messages", json={"content": "  "}), 422)
    assert_error(c.post(f"{API}/threads/main/messages", json={}), 422)


def test_runner_unavailable_is_a_reply_not_a_5xx(tmp_path, clock, id_factory):
    app = create_app(Settings(db_path=tmp_path / "sdk.db", droid_runner="sdk"), clock=clock, id_factory=id_factory)
    s = app.state.session_factory()
    try:
        seed(s, clock=clock, ids=id_factory)
    finally:
        s.close()
    try:
        with TestClient(app) as c:
            reply = say(c, "add 50k prioritizing research")
            assert "unavailable" in reply["content"] and "Nothing was changed" in reply["content"]
            assert "proposalId" not in reply
            assert by_team(get(c, "budgets"), "allocated") == ALLOCATED
    finally:
        app.state.engine.dispose()


def test_reset_wipes_threads(tmp_path, clock, id_factory):
    app = create_app(Settings(db_path=tmp_path / "r.db", allow_reset=True), clock=clock, id_factory=id_factory)
    try:
        with TestClient(app) as c:
            c.post("/api/admin/reset")
            say(c, "How is research doing?")
            assert len(get(c, "threads/main")) == 2
            c.post("/api/admin/reset")
            assert get(c, "threads/main") == []
            s = app.state.session_factory()
            try:
                assert s.scalar(select(func.count()).select_from(AssistantMessage)) == 0
            finally:
                s.close()
    finally:
        app.state.engine.dispose()


# ---- errors, mounting, CORS ---------------------------------------------------------------------


def test_errors_are_plain_strings(c):
    r = c.get(f"{API}/proposals/prop_missing")  # getProposal resolves to `AllocationProposal | undefined`
    assert r.status_code == 200 and r.json() is None
    assert_error(c.post(f"{API}/proposals/prop_missing/apply", json={}), 404, "That proposal does not exist.")
    assert_error(c.get(f"{API}/nope"), 404)
    # /api keeps the structured envelope.
    assert c.get("/api/proposals/prop_missing").json()["error"]["code"] == "proposal_not_found"


def test_unseeded_database_answers_plain_errors(client):
    body = assert_error(client.get(f"{API}/company"), 503, "The database is not seeded yet; run `python -m app.seed`.")
    assert body["code"] == "not_seeded"
    # Every list route the store loads answers 200 [] so nothing else fails on a fresh DB.
    for path in ("teams", "people", "spending", "budgets", "forecasts", "context", "documents", "proposals",
                 "decisions", "threads/main"):
        r = client.get(f"{API}/{path}")
        assert r.status_code == 200 and r.json() == [], (path, r.text)


def test_forecast_unavailable_mode(tmp_path, clock, id_factory):
    app = create_app(Settings(db_path=tmp_path / "u.db", forecast_provider="unavailable"), clock=clock,
                     id_factory=id_factory)
    s = app.state.session_factory()
    try:
        seed(s, clock=clock, ids=id_factory)
    finally:
        s.close()
    try:
        with TestClient(app) as c:
            fc = get(c, "forecasts", list[S.Forecast])
            assert len([f for f in fc if "personId" not in f]) == 3 and len(fc) == 3 + 15
            assert all(f["status"] == "unavailable" and f["unavailableReason"] and "projected" not in f for f in fc)
            reply = say(c, "add 50k")  # no team, no projection to pick one: ask
            assert "Which team" in reply["content"]
    finally:
        app.state.engine.dispose()


def test_compat_is_not_in_openapi_and_can_be_disabled(client, tmp_path, clock, id_factory):
    assert not any(p.startswith("/compat") for p in client.get("/openapi.json").json()["paths"])
    app = create_app(Settings(db_path=tmp_path / "off.db", compat=False), clock=clock, id_factory=id_factory)
    try:
        with TestClient(app) as c:
            r = c.get(f"{API}/teams")
            assert r.status_code == 404 and isinstance(r.json()["error"], dict)
    finally:
        app.state.engine.dispose()


def test_backend_compat_env_flag():
    assert Settings.from_env({}).compat is True
    assert Settings.from_env({"BACKEND_COMPAT": "0"}).compat is False


def test_cors_allows_the_next_dev_server(c):
    r = c.options(f"{API}/proposals/x/apply", headers={
        "Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type"})
    assert r.status_code == 200 and r.headers["access-control-allow-origin"] == "http://localhost:3000"
    r = c.get(f"{API}/teams", headers={"Origin": "http://localhost:3000"})
    assert r.headers["access-control-allow-origin"] == "http://localhost:3000"


# ---- pure helpers ------------------------------------------------------------------------------


TEAMS = [("engineering", "Engineering"), ("product", "Product"), ("research", "Research")]
GAPS = {"research": Decimal("25000.00"), "engineering": Decimal("5000.00"), "product": Decimal("-30000.00")}


@pytest.mark.parametrize("text,amount", [
    ("add 50k", "50000.00"), ("add $50,000 now", "50000.00"), ("add 1.5m", "1500000.00"),
    ("add 25000 dollars", "25000.00"), ("in 2026 add $12.5k", "12500.00"), ("refresh prop_000001", None),
    ("add 50 thousand", "50000.00"), ("add more", None),
])
def test_parse_amount(text, amount):
    assert intent.parse_amount(text) == amount


@pytest.mark.parametrize("text,task,params", [
    ("Add 50k prioritizing research", "propose_allocation", {"mode": "addition", "amount": "50000.00", "prioritize": "research"}),
    ("add $30,000 to the budget", "propose_allocation", {"mode": "addition", "amount": "30000.00", "prioritize": "research"}),
    ("move up to 10k into Engineering", "propose_allocation", {"mode": "transfer", "amount": "10000.00", "prioritize": "engineering"}),
    ("rebalance", "propose_allocation", {"mode": "transfer", "prioritize": "research"}),
    ("what changed in the docs?", "interpret_corpus", None),
    ("which team spends the most?", "answer_question", None),
    ("show me more about product", "answer_question", None),
])
def test_intent_rules(text, task, params):
    parsed = intent.parse(text, teams=TEAMS, gaps=GAPS)
    assert parsed.ask is None and parsed.run["task_type"] == task
    assert parsed.run.get("params") == params
    assert parsed.read_as


@pytest.mark.parametrize("text,amount", [
    ("add 5000 dollars to research", "5000.00"), ("increase research budget by 7500 USD", "7500.00"),
    ("Move 5000 from product to research", "5000.00"), ("in 2026 add 5000", "5000.00"),
    ("add 2026 to research", None), ("plan for 2026-P1", None),
])
def test_parse_amount_plain_four_digits_and_dollar_words(text, amount):
    assert intent.parse_amount(text.lower()) == amount


@pytest.mark.parametrize("text,prioritize", [
    ("Move 5000 from product to research", "research"),
    ("shift budget from research to product", "product"),
    ("move funds out of engineering toward Product", "product"),
    ("take money from research and move it into engineering", "engineering"),
])
def test_transfer_prioritizes_the_destination_never_the_source(text, prioritize):
    p = intent.parse(text, teams=TEAMS, gaps=GAPS)
    assert p.run["params"]["mode"] == "transfer" and p.run["params"]["prioritize"] == prioritize
    assert f"toward {dict(TEAMS)[prioritize]}" in p.read_as and "as the source" in p.read_as


def test_transfer_from_a_team_alone_never_prioritizes_that_team():
    gaps = {"research": Decimal("-1.00"), "engineering": Decimal("5000.00"), "product": Decimal("9000.00")}
    p = intent.parse("move money from product", teams=TEAMS, gaps=gaps)
    assert p.run["params"]["prioritize"] == "engineering"


@pytest.mark.parametrize("text", [
    "add 20000 credits to research", "add 2,000,000 tokens to research", "move 5k tokens to product",
    "add 300 GPU hours for research", "add €5000 to research", "add 5000 EUR to research",
])
def test_amounts_in_other_units_ask_instead_of_drafting_usd(text):
    p = intent.parse(text, teams=TEAMS, gaps=GAPS)
    assert p.run is None and p.ask and "dollars" in p.ask and "not convert" in p.ask


def test_intent_refresh_and_questions():
    p = intent.parse("refresh it", teams=TEAMS, gaps=GAPS, stale_proposal_ids=["prop_000009"])
    assert p.run["params"] == {"stale_proposal_id": "prop_000009"}
    p = intent.parse("rebase prop_000002 please", teams=TEAMS, gaps=GAPS)
    assert p.run["params"] == {"stale_proposal_id": "prop_000002"}
    assert intent.parse("add budget", teams=TEAMS, gaps=GAPS).ask
    assert intent.parse("add $1.234 to research", teams=TEAMS, gaps=GAPS).ask
    assert "Which team" in intent.parse("add 5k", teams=TEAMS, gaps={}).ask


def test_mapper_scalars():
    assert mappers.num(Decimal("60000.00")) == 60000 and isinstance(mappers.num(Decimal("60000.00")), int)
    assert mappers.num(Decimal("12.50")) == 12.5 and mappers.num(None) is None
    assert mappers.derived_title("Short. Second.") == "Short"
    long = "word " * 40
    assert len(mappers.derived_title(long)) <= mappers.TITLE_MAX and mappers.derived_title(long).endswith("…")
    assert mappers.team_color(5) == "var(--chart-1)"
