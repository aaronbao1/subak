"""Compat layer against the current frontend contract (frontend-integration-design §1, §6).

The frontend store loads 10 GETs with `Promise.all`; one non-200 renders nothing. These tests run that
exact load on a fresh seeded app, validate every body against app/compat/schemas.py (drift-checked
against the TypeScript contract), and check that the JSON numbers the UI adds up reconcile:
person spend + team-level rows == team totals, person forecasts == team forecasts, and
complete-days spend + sum(daily) == projected. FakeDroidRunner only.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from pydantic import TypeAdapter
from sqlalchemy import func, select, update

from app.compat import mappers
from app.compat import schemas as S
from app.compat.errors import ALREADY_REJECTED, STALE
from app.compat.router import DISMISS_NOTE, REJECT_NOTE
from app.db.models import BudgetEnvelope, Decision, ForecastSnapshot, Proposal

API = "/compat/api"
SPENT = {"research": 45000, "product": 20000, "engineering": 30000}
PROJECTED = {"research": 85000, "product": 50000, "engineering": 65000}
ALLOCATED = {"research": 60000, "product": 80000, "engineering": 60000}
OUTCOME_B = {"research": 95000, "product": 80000, "engineering": 75000}
TEAM_SIZES = {"research": 6, "product": 4, "engineering": 5}

# store.load(): getCompany, getTeams, getPeople, getSpending, getBudgets, getForecasts, getContext,
# getProposals, getDecisions, getThread("main") - in that order, all at once.
STORE_LOAD = [
    ("company", S.Company), ("teams", list[S.Team]), ("people", list[S.Person]),
    ("spending", list[S.SpendingRecord]), ("budgets", list[S.Budget]), ("forecasts", list[S.Forecast]),
    ("context", list[S.ContextItem]), ("proposals", list[S.AllocationProposal]),
    ("decisions", list[S.Decision]), ("threads/main", list[S.AssistantMessage]),
]


@pytest.fixture
def c(seeded) -> TestClient:
    with TestClient(seeded) as client:
        yield client


def get(c, path, model=None):
    r = c.get(f"{API}/{path}")
    assert r.status_code == 200, (path, r.text)
    body = r.json()
    if model is not None:
        TypeAdapter(model).validate_python(body)
    return body


def say(c, text):
    r = c.post(f"{API}/threads/main/messages", json={"content": text})
    assert r.status_code == 200, r.text
    return r.json()[1]


def store_load(c) -> dict:
    return {path: get(c, path, model) for path, model in STORE_LOAD}


def interpret(c) -> None:
    say(c, "Read the documents and tell me what changed")


# ---- the store load ----------------------------------------------------------------------------


def test_store_load_sequence_on_a_fresh_seeded_app(c):
    state = store_load(c)
    assert state["company"]["currentPeriod"] == {"start": "2026-10-01", "end": "2026-12-31",
                                                 "label": "Northstar planning period"}
    assert state["context"] == [] and state["proposals"] == [] and state["decisions"] == []
    assert state["threads/main"] == []
    assert len(state["people"]) == 15 and state["spending"] and state["forecasts"]
    # And again once Droid (fake) has interpreted the corpus and drafted / decided a proposal.
    interpret(c)
    pid = say(c, "add 50k prioritizing research")["proposalId"]
    assert c.post(f"{API}/proposals/{pid}/apply", json={}).status_code == 200
    state = store_load(c)
    assert state["context"] and len(state["proposals"]) == 1 and len(state["decisions"]) == 1
    assert len(state["threads/main"]) == 4


def test_store_load_reconciles_spend_and_forecasts(c):
    interpret(c)
    state = store_load(c)
    team_ids = {t["id"] for t in state["teams"]}
    people = {p["id"]: p for p in state["people"]}
    assert all(p["teamId"] in team_ids for p in people.values())

    # Spending: person rows + team-level rows == team totals (exact integers in JSON).
    person_sum, team_level = Counter(), Counter()
    for r in state["spending"]:
        assert isinstance(r["amount"], int)
        if "personId" in r:
            assert people[r["personId"]]["teamId"] == r["teamId"]
            person_sum[r["teamId"]] += r["amount"]
        else:
            team_level[r["teamId"]] += r["amount"]
    assert {t: person_sum[t] + team_level[t] for t in SPENT} == SPENT
    assert dict(team_level) == {"research": 0, "engineering": 0}  # included usage only, $0 in compat
    assert dict(person_sum) == SPENT

    # Forecasts: what the store splits by personId.
    team_fc = [f for f in state["forecasts"] if "personId" not in f]
    person_fc = [f for f in state["forecasts"] if "personId" in f]
    assert {f["teamId"]: f["projected"] for f in team_fc} == PROJECTED
    assert sorted(f["personId"] for f in person_fc) == sorted(people)
    by_team = defaultdict(int)
    for f in person_fc:
        assert f["status"] == "available" and f["basis"] == "full_period" and f["origin"] == "placeholder"
        assert people[f["personId"]]["teamId"] == f["teamId"] and isinstance(f["projected"], int)
        by_team[f["teamId"]] += f["projected"]
    assert dict(by_team) == PROJECTED

    # Frontend rule for full_period: spend on complete days + sum(daily) == projected (team and person).
    assert all(r["complete"] for r in state["spending"])
    spent_by_person = Counter()
    for r in state["spending"]:
        if "personId" in r:
            spent_by_person[r["personId"]] += r["amount"]
    for f in team_fc:
        assert SPENT[f["teamId"]] + sum(pt["projected"] for pt in f["daily"]) == f["projected"]
    for f in person_fc:
        assert spent_by_person[f["personId"]] + sum(pt["projected"] for pt in f["daily"]) == f["projected"]

    # Per day, persons sum to the team; 72 points from the day after as-of (Oct 20 is complete).
    days = [(date(2026, 10, 21) + timedelta(days=i)).isoformat() for i in range(72)]
    for f in team_fc:
        assert [pt["date"] for pt in f["daily"]] == days
        members = [p for p in person_fc if p["teamId"] == f["teamId"]]
        for i, pt in enumerate(f["daily"]):
            assert sum(m["daily"][i]["projected"] for m in members) == pt["projected"]


# ---- people / teams / spending -----------------------------------------------------------------


def test_people_shape(c):
    people = get(c, "people", list[S.Person])
    assert Counter(p["teamId"] for p in people) == TEAM_SIZES
    assert [(p["teamId"], p["name"]) for p in people] == sorted((p["teamId"], p["name"]) for p in people)
    ava = next(p for p in people if p["id"] == "research-ava-chen")
    assert ava == {"id": "research-ava-chen", "teamId": "research", "name": "Ava Chen", "role": "Research lead",
                   "email": "ava.chen@northstar.example", "integrations": ["slack", "asana"],
                   "primaryTool": "Claude Code"}
    assert all(p["email"].endswith("@northstar.example") and p["integrations"] for p in people)


def test_spending_person_ids_and_row_ids(c):
    rows = get(c, "spending")
    person_rows = [r for r in rows if "personId" in r]
    team_rows = [r for r in rows if "personId" not in r]
    assert person_rows and team_rows and all(r["component"] == "included_usage" for r in team_rows)
    r = person_rows[0]
    assert r["id"] == f"{r['teamId']}:{r['personId']}:{r['date']}:{r['component']}:{r['provider']}"
    t = team_rows[0]
    assert t["id"] == f"{t['teamId']}:{t['date']}:{t['component']}:{t['provider']}"
    assert len({r["id"] for r in rows}) == len(rows)
    assert not any(r["personId"] == "research-hana-sato" for r in person_rows)  # not a research person
    hana = [r for r in person_rows if r["personId"] == "engineering-hana-sato"]
    assert hana and min(r["date"] for r in hana) >= "2026-10-13"  # joined Oct 13
    assert {r["teamId"] for r in get(c, "spending?teamId=research")} == {"research"}


# ---- forecasts ---------------------------------------------------------------------------------


def test_forecast_items_order_ids_and_labels(c):
    fc = get(c, "forecasts", list[S.Forecast])
    teams = [f for f in fc if "personId" not in f]
    persons = [f for f in fc if "personId" in f]
    assert fc == teams + persons  # team items first
    assert [f["teamId"] for f in teams] == sorted(PROJECTED)
    assert [(f["teamId"], f["personId"]) for f in persons] == sorted((f["teamId"], f["personId"]) for f in persons)
    leila = next(f for f in persons if f["personId"] == "research-leila-novak")
    assert leila["id"] == "fc-research-2026-P1-research-leila-novak"
    assert leila["assumptions"][0].startswith("Share of the team placeholder in proportion to recorded spend")
    assert leila["assumptions"][1] == "Full-period total, includes spend to date"
    assert mappers.PERSON_SPLIT_LIMITATION in leila["limitations"]
    assert mappers.SIMULATED_LIMITATION in leila["limitations"]
    assert "low" not in leila and "high" not in leila
    research = next(f for f in teams if f["teamId"] == "research")
    assert "Sum of 6 individual placeholder projections" in research["assumptions"]
    assert not any(a.startswith("Includes ") for a in research["assumptions"])  # no priced team-level spend


def test_forecast_unavailable_propagates_to_people(tmp_path, clock, id_factory):
    from app.config import Settings
    from app.main import create_app
    from app.seed.northstar import seed

    app = create_app(Settings(db_path=tmp_path / "u.db", forecast_provider="unavailable"), clock=clock,
                     id_factory=id_factory)
    s = app.state.session_factory()
    try:
        seed(s, clock=clock, ids=id_factory)
    finally:
        s.close()
    try:
        with TestClient(app) as client:
            fc = get(client, "forecasts", list[S.Forecast])
            persons = [f for f in fc if "personId" in f]
            assert len(persons) == 15
            assert all(f["status"] == "unavailable" and f["unavailableReason"] and "projected" not in f
                       and "daily" not in f and f["assumptions"] == [] for f in persons)
    finally:
        app.state.engine.dispose()


def test_forecasts_reviewed_are_team_level_only(c):
    pid = say(c, "add 50k prioritizing research")["proposalId"]
    p = get(c, f"proposals/{pid}", S.AllocationProposal)
    assert [f["teamId"] for f in p["forecastsReviewed"]] == ["engineering", "product", "research"]
    assert not any("personId" in f for f in p["forecastsReviewed"])
    r = c.post(f"{API}/proposals/{pid}/apply", json={})
    assert r.status_code == 200
    assert not any("personId" in f for f in r.json()["forecastsReviewed"])


# ---- context / documents -----------------------------------------------------------------------


def test_context_person_team_and_company_items(c):
    interpret(c)
    items = get(c, "context", list[S.ContextItem])
    people = {p["id"]: p for p in get(c, "people")}
    assert all(i["scope"] in ("person", "team", "company") and isinstance(i["personIds"], list) for i in items)

    person_items = [i for i in items if i["scope"] == "person"]
    assert {pid for i in person_items for pid in i["personIds"]} == {
        "research-leila-novak", "research-omar-haddad", "research-theo-brandt", "engineering-sofia-reyes",
        "engineering-hana-sato", "product-felix-weber"}
    for i in person_items:
        assert i["personIds"] and i["signal"] and len(i["teamIds"]) == 1
        assert all(people[pid]["teamId"] == i["teamIds"][0] for pid in i["personIds"])
    leila = next(i for i in person_items if i["personIds"] == ["research-leila-novak"])
    assert leila["signal"] == "project_deferred" and leila["title"] == "Leila Novak's harness build deferred to Nov 3"
    assert leila["expectedEffect"] == "decrease"
    src = leila["sources"][0]
    assert src["integration"] == "asana" and src["author"] == "Ava Chen (Research lead)"
    hana = next(i for i in person_items if i["personIds"] == ["engineering-hana-sato"])
    assert hana["signal"] == "onboarding" and hana["claimType"] == "observed_event"

    [company] = [i for i in items if i["scope"] == "company"]
    assert company["personIds"] == [] and company["signal"] == "model_change"
    assert company["teamIds"] == ["engineering", "product", "research"]
    assert company["sources"][0]["integration"] == "slack"

    team_items = [i for i in items if i["scope"] == "team"]
    assert team_items and all(i["personIds"] == [] for i in team_items)
    assert all(len(i["title"]) <= 120 for i in items)
    for team in ("research", "product", "engineering"):
        filtered = get(c, f"context?teamId={team}", list[S.ContextItem])
        assert company["id"] in {i["id"] for i in filtered}
        assert all(team in i["teamIds"] or not i["teamIds"] for i in filtered)


def test_documents_person_ids_integration_and_origin_label(c):
    docs = {d["title"]: d for d in get(c, "documents", list[S.CompanyDocument])}
    asana = docs["Asana: Eval harness v2 - implementation"]
    assert asana["personIds"] == ["research-leila-novak"] and asana["integration"] == "asana"
    assert asana["origin"] == "Asana export (simulated)"
    monday = next(d for d in docs.values() if d["integration"] == "monday")
    assert monday["origin"] == "monday.com export (simulated)"
    assert {d["integration"] for d in docs.values()} == {"asana", "slack", "monday", "email", "document"}
    email = next(d for d in docs.values() if d["integration"] == "email")
    assert email["origin"] == "Email export (simulated)" and email["personIds"] == []
    assert all(isinstance(d["personIds"], list) for d in docs.values())


# ---- reject / dismiss --------------------------------------------------------------------------


def _counts(app):
    s = app.state.session_factory()
    try:
        env = s.scalar(select(BudgetEnvelope))
        return (env.state_version, s.scalar(select(func.count()).select_from(ForecastSnapshot)))
    finally:
        s.close()


def _two_proposals_one_applied(c):
    """A transfer drafted on v1, then an addition applied: the transfer's base version is now outdated."""
    tid = say(c, "rebalance the budget toward research")["proposalId"]
    add = say(c, "add 50k prioritizing research")["proposalId"]
    assert c.post(f"{API}/proposals/{add}/apply", json={}).status_code == 200
    return tid


def test_dismiss_of_a_stale_proposal_records_a_rejected_decision(c, seeded):
    tid = _two_proposals_one_applied(c)
    r = c.post(f"{API}/proposals/{tid}/apply", json={})  # marks it stale, readable message
    assert r.status_code == 409 and r.json()["error"] == STALE
    assert get(c, f"proposals/{tid}")["status"] == "stale"
    before = _counts(seeded)

    r = c.post(f"{API}/proposals/{tid}/reject", json={})
    assert r.status_code == 200, r.text
    assert S.AllocationProposal.model_validate(r.json()).status == "rejected"
    d = next(d for d in get(c, "decisions", list[S.Decision]) if d["proposalId"] == tid)
    assert d["action"] == "rejected" and "note" not in d and d["appliedBy"] == "Finance approver (demo)"
    assert {b["teamId"]: b["allocated"] for b in get(c, "budgets")} == OUTCOME_B
    assert {b["version"] for b in get(c, "budgets")} == {"2"}
    assert _counts(seeded) == before
    s = seeded.state.session_factory()
    try:
        dec = s.scalar(select(Decision).where(Decision.proposal_id == tid))
        assert dec.from_version == 2 and dec.to_version is None and dec.after is None
    finally:
        s.close()
    # Settled now: a second dismiss or apply is a readable 409; a rebase is no longer possible.
    r = c.post(f"{API}/proposals/{tid}/reject", json={})
    assert r.status_code == 409 and r.json()["error"] == ALREADY_REJECTED
    r = c.post(f"/api/proposals/{tid}/rebase", headers={"X-Actor-Id": "fin-ana", "X-Actor-Role": "finance_analyst"})
    assert r.status_code == 409


def test_dismiss_of_a_pending_proposal_on_an_outdated_version(c, seeded):
    tid = _two_proposals_one_applied(c)
    assert get(c, f"proposals/{tid}")["status"] == "stale"  # UI status; backend still pending_review
    before = _counts(seeded)
    r = c.post(f"{API}/proposals/{tid}/reject", json={})
    assert r.status_code == 200 and r.json()["status"] == "rejected"
    d = next(d for d in get(c, "decisions") if d["proposalId"] == tid)
    assert "note" not in d
    s = seeded.state.session_factory()
    try:  # the backend still records why: the dismiss reason is the stored rationale
        assert s.scalar(select(Decision).where(Decision.proposal_id == tid)).rationale == DISMISS_NOTE
    finally:
        s.close()
    assert {b["teamId"]: b["allocated"] for b in get(c, "budgets")} == OUTCOME_B
    assert _counts(seeded) == before


def test_plain_reject_stores_the_reject_note_but_does_not_quote_it(c):
    pid = say(c, "add 50k prioritizing research")["proposalId"]
    assert c.post(f"{API}/proposals/{pid}/reject", json={}).status_code == 200
    [d] = get(c, "decisions")
    assert "note" not in d and d["appliedBy"] == "Finance approver (demo)"
    [backend] = c.get("/api/decisions").json()
    assert backend["rationale"] == REJECT_NOTE  # the backend audit trail keeps the reason
    assert {b["teamId"]: b["allocated"] for b in get(c, "budgets")} == ALLOCATED


def test_core_decision_route_rejects_stale_but_never_approves_it(c):
    tid = _two_proposals_one_applied(c)
    approver = {"X-Actor-Id": "fin-bob", "X-Actor-Role": "finance_approver"}
    r = c.post(f"/api/proposals/{tid}/decision", json={"outcome": "approve", "rationale": "go"},
               headers={**approver, "Idempotency-Key": "a-1"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "stale_proposal"
    assert c.get(f"/api/proposals/{tid}").json()["status"] == "stale"
    r = c.post(f"/api/proposals/{tid}/decision", json={"outcome": "approve", "rationale": "again"},
               headers={**approver, "Idempotency-Key": "a-2"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "proposal_not_pending"
    droid = {"X-Actor-Id": "droid", "X-Actor-Role": "droid_agent"}
    r = c.post(f"/api/proposals/{tid}/decision", json={"outcome": "reject", "rationale": "no"},
               headers={**droid, "Idempotency-Key": "r-0"})
    assert r.status_code == 403  # the role rule still comes first
    r = c.post(f"/api/proposals/{tid}/decision", json={"outcome": "reject", "rationale": "not used"},
               headers={**approver, "Idempotency-Key": "r-1"})
    assert r.status_code in (200, 201), r.text
    assert r.json()["outcome"] == "rejected" and r.json()["to_version"] is None
    assert c.get(f"/api/proposals/{tid}").json()["status"] == "rejected"


def test_revised_applied_and_rejected_still_cannot_be_rejected(c, seeded):
    tid = _two_proposals_one_applied(c)
    s = seeded.state.session_factory()
    try:  # what /revise leaves behind: the original is `revised`
        s.execute(update(Proposal).where(Proposal.id == tid).values(status="revised"))
        s.commit()
    finally:
        s.close()
    r = c.post(f"{API}/proposals/{tid}/reject", json={})
    assert r.status_code == 409 and r.json()["code"] == "proposal_not_pending"
    assert r.json()["error"] == "This proposal was replaced by a revised one and can no longer be decided."
    applied = next(p["id"] for p in get(c, "proposals") if p["status"] == "applied")
    assert c.post(f"{API}/proposals/{applied}/reject", json={}).status_code == 409


def test_readable_error_messages(c):
    from app.compat.errors import MESSAGES, plain_message

    assert MESSAGES["already_applied"] == "This proposal was already applied; it cannot be applied or rejected again."
    assert MESSAGES["already_rejected"] == "This proposal was already rejected."
    assert MESSAGES["stale_proposal"].startswith("The budget changed after this proposal was drafted")
    for code in ("self_approval_forbidden", "role_forbidden", "proposal_not_found", "not_seeded"):
        assert MESSAGES[code].endswith((".", "`."))
    assert plain_message("proposal_not_pending", "x", {"status": "revised"}).startswith("This proposal was replaced")


def test_explicit_forecast_demo_directory_matches_unavailable_person_forecasts(tmp_path, clock, id_factory):
    from app.config import Settings
    from app.main import create_app
    from app.seed.northstar import seed

    app = create_app(Settings(db_path=tmp_path / "engine-demo.db", forecast_provider="engine",
                              forecast_demo=True, forecast_worker=False), clock=clock, id_factory=id_factory)
    with app.state.session_factory() as session:
        seed(session, clock=clock, ids=id_factory)
    try:
        with TestClient(app) as client:
            people = get(client, "people", list[S.Person])
            assert len(people) == 6  # explicit canonical demonstration directory, not the 15 DB seed people
            forecasts = get(client, "forecasts", list[S.Forecast])
            persons = [f for f in forecasts if "personId" in f]
            assert {f["personId"] for f in persons} == {p["id"] for p in people}
            assert all(f["status"] == "unavailable" and "projected" not in f for f in forecasts)
            assert not app.state.forecast_service.store.publication()
            from app.compat.router import router
            paths = [r.path for r in router.routes]
            assert paths.count(f"{API}/people") == 1
    finally:
        app.state.engine.dispose()
