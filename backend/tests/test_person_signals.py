"""Person and company context (frontend-integration-design §2.3, §2.4, §5): corpus person tags and
integrations, signal scope validation, filters, dedupe, the list_people tool and the fake runner's
person/company signals."""

from __future__ import annotations

import pytest

from app.agent import tools as tool_defs
from app.agent.fake_runner import COMPANY_KEYS, PERSON_KEYS, PLAYBOOK, TEAM_KEYS
from app.agent.runner import ToolError
from app.seed.northstar import CORPUS_DIR
from app.services import corpus as corpus_svc
from test_agent import _toolbox, run

DROID = {"X-Actor-Id": "droid-t", "X-Actor-Role": "droid_agent"}
IMPORTER = {"X-Actor-Id": "importer-1", "X-Actor-Role": "importer"}

EXPECTED = {  # doc_key -> (scope, person_ids, team, signal_kind, title)
    "research-harness-asana": ("person", ["research-leila-novak"], "research", "project_deferred",
                               "Leila Novak's harness build deferred to Nov 3"),
    "research-model-switch-slack": ("person", ["research-omar-haddad"], "research", "model_change",
                                    "Omar Haddad moving eval sweeps to a cheaper model tier"),
    "research-availability-monday": ("person", ["research-theo-brandt"], "research", "out_of_office",
                                     "Theo Brandt out of office Oct 26-30"),
    "engineering-cutover-monday": ("person", ["engineering-sofia-reyes"], "engineering", "project_accelerated",
                                   "Sofia Reyes's cutover regression runs start Oct 22"),
    "engineering-welcome-slack": ("person", ["engineering-hana-sato"], "engineering", "onboarding",
                                  "Hana Sato joined the platform team"),
    "product-tool-switch-slack": ("person", ["product-felix-weber"], "product", "tool_change",
                                  "Felix Weber moving tuning scripts to the OpenAI API"),
    "company-model-announcement-slack": ("company", [], None, "model_change",
                                         "Company-wide default model change from Nov 2"),
    "research-eval-plan": ("team", [], "research", "project_accelerated",
                           "Research model-evaluation expansion moves into the current period"),
    "research-timeline-thread": ("team", [], "research", "project_deferred",
                                 "Older thread: research expansion pushed to next period"),
    "product-launch-plan": ("team", [], "product", "project_deferred",
                            "Product GA launch moves to the following period"),
    "engineering-platform-note": ("team", [], "engineering", "steady",
                                  "Engineering platform migration continues at the current pace"),
    "marketing-ideas-slack": ("team", [], None, None, "Marketing idea: personalized AI demo videos"),
}


def _doc(client, key: str) -> dict:
    versions = client.get(f"/api/documents/by-key/{key}/versions").json()["versions"]
    return client.get(f"/api/documents/{versions[-1]['id']}").json()


def _signal(doc_id: str, quote: str, **extra) -> dict:
    return {"summary": "s", "change_type": "other", "status": "current", "uncertainty": "u",
            "citations": [{"document_id": doc_id, "quote": quote}], **extra}


OMAR_QUOTE = "just the cheaper tier for everything except the final comparison runs."
ANNOUNCE_QUOTE = "the net effect on each team's bill is not known yet."


# ---- corpus -------------------------------------------------------------------------------------


def test_every_playbook_quote_is_verbatim_in_the_seed_corpus():
    docs = {}
    for path in sorted(CORPUS_DIR.glob("*.md")):
        meta = corpus_svc.parse_markdown_document(path.read_text(encoding="utf-8"))
        docs.setdefault(meta["doc_key"], []).append(meta)
    for key in PERSON_KEYS + COMPANY_KEYS:
        (meta,) = docs[key]
        rules = PLAYBOOK[key]
        assert rules["quotes"]
        for quote in rules["quotes"]:
            assert quote in meta["content"], (key, quote)
        assert "next period" not in meta["content"].lower() and "this period" not in meta["content"].lower()
        assert meta["is_simulated"] is True and meta["integration"] in ("slack", "asana", "monday")
        assert meta.get("person_tags", []) == EXPECTED[key][1], key
    assert set(PERSON_KEYS + COMPANY_KEYS + TEAM_KEYS) | {"research-timeline-thread"} == set(docs)


def test_seeded_documents_carry_integration_and_person_tags(seeded, client):
    asana = _doc(client, "research-harness-asana")
    assert asana["integration"] == "asana" and asana["person_tags"] == ["research-leila-novak"]
    company = _doc(client, "company-model-announcement-slack")
    assert company["integration"] == "slack" and company["person_tags"] == []
    assert company["team_tags"] == ["research", "product", "engineering"]
    plan = _doc(client, "research-eval-plan")
    assert plan["integration"] is None and plan["person_tags"] == []


def test_ingest_refuses_unknown_person_tag(seeded, client):
    body = {"doc_key": "eng-note-x", "title": "x", "doc_type": "note", "authored_at": "2026-10-20T00:00:00Z",
            "content": "Mateo Silva is moving to Cursor.", "person_tags": ["engineering-nobody"],
            "integration": "slack"}
    r = client.post("/api/documents", json=body, headers=IMPORTER)
    assert r.status_code == 422 and r.json()["error"]["code"] == "unknown_person"
    assert r.json()["error"]["details"]["reasons"][0]["person_id"] == "engineering-nobody"
    r = client.post("/api/documents", json={**body, "person_tags": ["Engineering-Mateo-Silva"]}, headers=IMPORTER)
    assert r.status_code == 201
    doc = r.json()["document"]
    assert doc["person_tags"] == ["engineering-mateo-silva"] and doc["integration"] == "slack"
    bad = client.post("/api/documents", json={**body, "doc_key": "eng-note-y", "integration": "teams"},
                      headers=IMPORTER)
    assert bad.status_code == 422


# ---- signal scope validation --------------------------------------------------------------------


def _codes(r) -> list[str]:
    assert r.status_code == 422, r.text
    err = r.json()["error"]
    assert err["code"] == "validation_failed"
    return [x["code"] for x in err["details"]["reasons"]]


def test_person_scope_rules(seeded, client):
    omar = _doc(client, "research-model-switch-slack")["id"]
    post = lambda body: client.post("/api/signals", json=body, headers=DROID)  # noqa: E731
    assert _codes(post(_signal(omar, OMAR_QUOTE, scope="person"))) == ["person_ids_required"]
    assert _codes(post(_signal(omar, OMAR_QUOTE, scope="person", person_ids=["research-nobody"]))) == [
        "unknown_person"]
    assert _codes(post(_signal(omar, OMAR_QUOTE, scope="person",
                               person_ids=["research-omar-haddad", "product-felix-weber"]))) == [
        "person_team_mismatch"]
    assert _codes(post(_signal(omar, OMAR_QUOTE, scope="person", team="product",
                               person_ids=["research-omar-haddad"]))) == ["person_team_mismatch"]
    # team omitted -> derived from the person; ids are normalized and deduplicated
    r = post(_signal(omar, OMAR_QUOTE, scope="person", signal_kind="model_change", title="  Omar tier switch ",
                     person_ids=["Research-Omar-Haddad", "research-omar-haddad"]))
    assert r.status_code == 201, r.text
    sig = r.json()
    assert (sig["scope"], sig["team"], sig["person_ids"], sig["signal_kind"], sig["title"]) == (
        "person", "research", ["research-omar-haddad"], "model_change", "Omar tier switch")


def test_team_and_company_scope_rules(seeded, client):
    omar = _doc(client, "research-model-switch-slack")["id"]
    ann = _doc(client, "company-model-announcement-slack")["id"]
    post = lambda body: client.post("/api/signals", json=body, headers=DROID)  # noqa: E731
    assert _codes(post(_signal(omar, OMAR_QUOTE, team="research", person_ids=["research-omar-haddad"]))) == [
        "person_ids_not_allowed"]
    assert _codes(post(_signal(ann, ANNOUNCE_QUOTE, scope="company", team="research"))) == ["team_not_allowed"]
    assert _codes(post(_signal(ann, ANNOUNCE_QUOTE, scope="company", person_ids=["research-omar-haddad"]))) == [
        "person_ids_not_allowed"]
    bad_kind = post(_signal(ann, ANNOUNCE_QUOTE, scope="company", signal_kind="vacation"))
    assert bad_kind.status_code == 422
    too_long = post(_signal(ann, ANNOUNCE_QUOTE, scope="company", title="x" * 121))
    assert too_long.status_code == 422
    r = post(_signal(ann, ANNOUNCE_QUOTE, scope="company", signal_kind="model_change"))
    assert r.status_code == 201 and r.json()["team"] is None and r.json()["person_ids"] == []
    # default scope stays team for every existing caller
    r = post(_signal(omar, OMAR_QUOTE, team="research"))
    assert r.status_code == 201 and r.json()["scope"] == "team" and r.json()["signal_kind"] is None


def test_signal_filters_scope_person_and_company(seeded, client):
    run(client, "interpret_corpus")
    get = lambda **p: client.get("/api/signals", params=p).json()["items"]  # noqa: E731
    leila = get(person="research-leila-novak")
    assert [s["person_ids"] for s in leila] == [["research-leila-novak"]]
    assert len(get(scope="person")) == 6 and len(get(scope="company")) == 1
    research = get(team="research")
    with_company = get(team="research", include_company="true")
    assert len(with_company) == len(research) + 1
    assert {s["scope"] for s in with_company} - {s["scope"] for s in research} == {"company"}
    assert all(s["team"] is None for s in get(team="none", scope="company"))


# ---- tools --------------------------------------------------------------------------------------


def test_list_people_tool_is_read_only_and_listed(seeded):
    assert next(t for t in tool_defs.TOOLS if t.name == "list_people").kind == "read"
    tb = _toolbox(seeded)
    out = tb.list_people(team="engineering")
    assert out["count"] == 5 and {p["team"] for p in out["items"]} == {"engineering"}
    assert {"id", "name", "role", "primary_tool", "integrations"} <= set(out["items"][0])
    assert tb.call("list_people", {})["count"] == 15
    with pytest.raises(ToolError) as exc:
        tb.call("list_people", {"team": "engineering", "extra": 1})
    assert exc.value.code == "invalid_arguments"


def test_record_signal_tool_scopes_and_dedupe(seeded, client):
    tb = _toolbox(seeded)
    omar = _doc(client, "research-model-switch-slack")["id"]
    body = _signal(omar, OMAR_QUOTE, scope="person", person_ids=["research-omar-haddad"], signal_kind="model_change",
                   title="Omar tier switch")
    first = tb.record_signal(body)
    assert first["already_recorded"] is False and first["team"] == "research"
    again = tb.record_signal(body)
    assert again["already_recorded"] is True and again["id"] == first["id"]
    other_kind = tb.record_signal({**body, "signal_kind": "tool_change"})
    assert other_kind["already_recorded"] is False and other_kind["id"] != first["id"]
    with pytest.raises(ToolError) as exc:
        tb.record_signal({**body, "person_ids": ["product-felix-weber"], "team": "research"})
    assert exc.value.code == "validation_failed"
    assert exc.value.details["reasons"][0]["code"] == "person_team_mismatch"


def test_sdk_record_signal_passes_scope_fields():
    from northstar_droid.sdk_tools import tool_functions

    calls = []

    class Box:
        def call(self, name, args):
            calls.append((name, args))
            return {"ok": True}

    fns = {n: f for n, _, f in tool_functions(Box())}
    fns["record_signal"](summary="s", change_type="other", status="current", uncertainty="u", citations=[],
                         scope="person", person_ids=["research-omar-haddad"], signal_kind="model_change", title="t")
    fns["list_people"](team="research")
    sig = calls[0][1]["signal"]
    assert (sig["scope"], sig["person_ids"], sig["signal_kind"], sig["title"]) == (
        "person", ["research-omar-haddad"], "model_change", "t")
    assert calls[1] == ("list_people", {"team": "research"})


# ---- fake runner --------------------------------------------------------------------------------


def test_fake_interpret_records_person_and_company_signals(seeded, client):
    out = run(client, "interpret_corpus").json()
    assert out["status"] == "succeeded" and len(out["signal_ids"]) == 12
    codes = {w["code"] for w in out["output"]["warnings"]}
    assert "document_not_interpreted" not in codes and "person_not_confirmed" not in codes
    sigs = client.get("/api/signals").json()["items"]
    by_key = {}
    for s in sigs:
        keys = {c["doc_key"] for c in s["citations"]}
        key = "product-launch-plan" if "product-launch-plan" in keys else next(iter(keys))
        by_key[key] = s
    assert set(by_key) == set(EXPECTED)
    for key, (scope, people, team, kind, title) in EXPECTED.items():
        s = by_key[key]
        assert (s["scope"], s["person_ids"], s["team"], s["signal_kind"], s["title"]) == (
            scope, people, team, kind, title), key
        assert s["produced_by"] == "droid_fake"
    assert by_key["engineering-cutover-monday"]["change_type"] == "expansion"
    assert by_key["product-tool-switch-slack"]["change_type"] == "continuation"
    assert by_key["research-availability-monday"]["applies_to"] == "2026-10-30"
    steps = [s["tool"] for s in out["steps"]]
    assert steps.count("list_people") == 1
    recorded = [e["data"] for e in out["events"] if e["type"] == "signal_recorded"]
    assert {(e["scope"], tuple(e["person_ids"]), e["signal_kind"]) for e in recorded if e["scope"] != "team"} == {
        (sc, tuple(p), k) for sc, p, _, k, _ in EXPECTED.values() if sc != "team"}


def _new_harness_version(client, tags: list[str], content: str) -> None:
    body = {"doc_key": "research-harness-asana", "title": "Asana: Eval harness v2 - implementation",
            "origin": "seed", "doc_type": "update", "plan_status": "approved",
            "authored_at": "2026-10-15T00:00:00Z", "effective_from": "2026-10-14", "effective_to": "2026-11-03",
            "team_tags": ["research"], "project_tags": ["model-evaluation"], "person_tags": tags,
            "integration": "asana", "is_simulated": True, "content": content}
    r = client.post("/api/documents", json=body, headers=IMPORTER)
    assert r.status_code == 201, r.text


HARNESS_TEXT = ("Assignee: {who}\n\nAva Chen commented: Leila, please stay on the design doc longer and hold the "
                "harness build until the design review signs off on 2026-11-03.\n\nReply: Understood. I will pause "
                "the implementation branch and keep my API runs to the design spikes.\n")


def test_fake_runner_drops_tags_it_cannot_confirm(seeded, client):
    # Felix is on product, not research: dropped; Leila is named: kept.
    _new_harness_version(client, ["research-leila-novak", "product-felix-weber"],
                         HARNESS_TEXT.format(who="Leila Novak"))
    out = run(client, "interpret_corpus").json()
    warns = [w for w in out["output"]["warnings"] if w["code"] == "person_not_confirmed"]
    assert [w["person_id"] for w in warns] == ["product-felix-weber"]
    sig = next(s for s in client.get("/api/signals", params={"person": "research-leila-novak"}).json()["items"])
    assert sig["person_ids"] == ["research-leila-novak"] and sig["citations"][0]["version"] == 2


def test_fake_runner_never_guesses_a_person_the_text_does_not_name(seeded, client):
    _new_harness_version(client, ["research-leila-novak"], HARNESS_TEXT.format(who="L. Novak"))
    out = run(client, "interpret_corpus").json()
    codes = [w["code"] for w in out["output"]["warnings"]]
    assert "person_not_confirmed" in codes and "person_signal_skipped" in codes
    assert client.get("/api/signals", params={"person": "research-leila-novak"}).json()["items"] == []
    assert len(out["signal_ids"]) == 11


def test_propose_after_interpret_reads_no_documents(seeded, client):
    run(client, "interpret_corpus")
    out = run(client, params={"mode": "addition", "amount": "50000.00", "prioritize": "research"}).json()
    tools = [s["tool"] for s in out["steps"]]
    assert "read_document" not in tools and "search_corpus" not in tools
    assert [p["status"] for p in out["proposals"]] == ["pending_review"]
