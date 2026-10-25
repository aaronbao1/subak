"""Corpus ingestion: origin/date/team tags, versions, supersedes links, search (check 4b groundwork)."""

from __future__ import annotations

import pytest

from app.core.errors import DomainError
from app.services.corpus import parse_markdown_document, parse_query
from reference_data import ANALYST, DROID, IMPORTER

THREAD = {
    "doc_key": "research-timeline-thread", "title": "Re: eval timeline", "origin": "email_export",
    "doc_type": "correspondence", "plan_status": "informal", "authored_at": "2026-09-03T15:00:00Z",
    "team_tags": ["research"], "project_tags": ["model-eval"], "author": "r.lead", "is_simulated": True,
    "content": "We will push the model-evaluation work to next period.\nBudget stays flat until then.",
}
PLAN = {
    "doc_key": "research-eval-plan", "title": "Approved research evaluation plan", "origin": "upload",
    "doc_type": "plan", "plan_status": "approved", "authored_at": "2026-10-08T09:00:00Z",
    "effective_from": "2026-10-01", "effective_to": "2026-12-31",
    "team_tags": ["Research"], "project_tags": ["model-eval"], "is_simulated": True,
    "supersedes_doc_key": "research-timeline-thread",
    "content": "This approved plan expands model-evaluation work this period.\r\n"
               "It supersedes the earlier email thread timeline.",
}
LAUNCH_V1 = {
    "doc_key": "product-launch-plan", "title": "Product launch plan", "origin": "upload", "doc_type": "plan",
    "plan_status": "approved", "authored_at": "2026-08-20T09:00:00Z", "team_tags": ["product"],
    "project_tags": ["launch"], "is_simulated": True,
    "content": "Launch milestone lands in the current period.",
}
LAUNCH_V2 = {**LAUNCH_V1, "doc_type": "update", "authored_at": "2026-10-14T09:00:00Z",
             "content": "Update: the launch milestone moves to the following period."}
ENG = {
    "doc_key": "engineering-platform-note", "title": "Platform note", "origin": "slack_export",
    "doc_type": "note", "authored_at": "2026-10-12T09:00:00Z", "team_tags": ["engineering"],
    "content": "Platform work continues through the current period.", "is_simulated": True,
}


def post(client, doc, headers=IMPORTER):
    return client.post("/api/documents", json=doc, headers=headers)


@pytest.fixture
def corpus(client):
    ids = {}
    for name, doc in (("thread", THREAD), ("plan", PLAN), ("v1", LAUNCH_V1), ("v2", LAUNCH_V2), ("eng", ENG)):
        r = post(client, doc)
        assert r.status_code == 201, r.text
        ids[name] = r.json()["document"]["id"]
    return ids


def test_document_keeps_origin_date_tags(client, corpus):
    d = client.get(f"/api/documents/{corpus['plan']}").json()
    assert d["origin"] == "upload" and d["plan_status"] == "approved"
    assert d["authored_at"] == "2026-10-08T09:00:00Z"
    assert d["team_tags"] == ["research"]  # normalized
    assert d["effective_from"] == "2026-10-01"
    assert "\r" not in d["content"]
    assert d["is_simulated"] is True


def test_new_version_links_supersedes_and_keeps_old_version(client, corpus):
    v = client.get("/api/documents/by-key/product-launch-plan/versions").json()
    assert v["current_version"] == 2
    v1, v2 = v["versions"]
    assert v1["id"] == corpus["v1"] and v1["is_current"] is False
    assert v1["superseded_by"]["id"] == corpus["v2"]
    assert v2["supersedes"]["version"] == 1 and v2["is_current"] is True
    old = client.get(f"/api/documents/{corpus['v1']}").json()
    assert old["content"] == LAUNCH_V1["content"]  # original material stays inspectable


def test_explicit_cross_document_supersede(client, corpus):
    thread = client.get(f"/api/documents/{corpus['thread']}").json()
    assert thread["is_current"] is False
    assert thread["superseded_by"]["doc_key"] == "research-eval-plan"
    plan = client.get(f"/api/documents/{corpus['plan']}").json()
    assert plan["supersedes"]["doc_key"] == "research-timeline-thread" and plan["is_current"]


def test_reupload_identical_content_is_noop(client, corpus):
    r = post(client, LAUNCH_V1)  # an old export re-imported after v2 exists
    assert r.status_code == 200
    body = r.json()
    assert body["created"] is False and body["duplicate_of_version"] == 1
    assert client.get("/api/documents/by-key/product-launch-plan/versions").json()["current_version"] == 2


def test_crlf_variant_of_same_content_is_noop(client, corpus):
    r = post(client, {**PLAN, "content": PLAN["content"].replace("\r\n", "\n")})
    assert r.status_code == 200 and r.json()["created"] is False


def test_version_dated_before_current_rejected(client, corpus):
    r = post(client, {**LAUNCH_V1, "content": "late-arriving older draft", "authored_at": "2026-09-01T00:00:00Z"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "version_predates_current"


def test_supersede_rules(client, corpus):
    newer = post(client, {**ENG, "doc_key": "old-memo", "authored_at": "2026-01-01T00:00:00Z",
                          "content": "old memo", "supersedes_doc_key": "engineering-platform-note"})
    assert newer.json()["error"]["code"] == "supersedes_newer_document"
    again = post(client, {**ENG, "doc_key": "another-plan", "content": "another",
                          "supersedes_doc_key": "research-timeline-thread"})
    assert again.status_code == 409 and again.json()["error"]["code"] == "already_superseded"
    same = post(client, {**LAUNCH_V2, "content": "v3", "authored_at": "2026-10-20T00:00:00Z",
                         "supersedes_doc_key": "product-launch-plan"})
    assert same.json()["error"]["code"] == "supersedes_same_key"
    missing = post(client, {**ENG, "doc_key": "x", "content": "x", "supersedes_doc_key": "nope"})
    assert missing.json()["error"]["code"] == "supersedes_target_not_found"


@pytest.mark.parametrize("patch", [
    {"doc_key": "Bad Key"}, {"content": "   "}, {"authored_at": "2026-10-01T00:00:00"},
    {"doc_type": "memo"}, {"effective_from": "2026-12-01", "effective_to": "2026-11-01"}, {"surprise": 1},
])
def test_document_validation(client, patch):
    r = post(client, {**ENG, **patch})
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_failed"


def test_upload_roles(client):
    assert post(client, ENG, headers=DROID).json()["error"]["code"] == "role_forbidden"
    assert post(client, ENG, headers=ANALYST).status_code == 201


def test_search_finds_terms_with_exact_offsets(client, corpus):
    res = client.get("/api/documents", params={"q": "model-evaluation"}).json()
    keys = [i["doc_key"] for i in res["items"]]
    assert set(keys) == {"research-eval-plan", "research-timeline-thread"}
    plan = next(i for i in res["items"] if i["doc_key"] == "research-eval-plan")
    detail = client.get(f"/api/documents/{plan['id']}").json()
    m = plan["matches"][0]
    assert detail["content"][m["char_start"]:m["char_end"]].lower() == "model-evaluation"
    assert plan["is_current"] is True
    thread = next(i for i in res["items"] if i["doc_key"] == "research-timeline-thread")
    assert thread["is_current"] is False  # stale material is labeled, not hidden


def test_search_excluding_superseded(client, corpus):
    res = client.get("/api/documents", params={"q": "launch milestone", "include_superseded": "false"}).json()
    assert [(i["doc_key"], i["version"]) for i in res["items"]] == [("product-launch-plan", 2)]


def test_search_all_terms_and_phrases(client, corpus):
    assert client.get("/api/documents", params={"q": '"current period" platform'}).json()["count"] == 1
    assert client.get("/api/documents", params={"q": "platform banana"}).json()["count"] == 0
    assert parse_query('a "b c"  D') == ["a", "b c", "d"]


def test_filters_by_team_project_type(client, corpus):
    r = client.get("/api/documents", params={"team": "research"}).json()
    assert {i["doc_key"] for i in r["items"]} == {"research-eval-plan", "research-timeline-thread"}
    r = client.get("/api/documents", params={"project": "launch"}).json()
    assert r["count"] == 2
    r = client.get("/api/documents", params={"doc_type": "correspondence"}).json()
    assert [i["doc_key"] for i in r["items"]] == ["research-timeline-thread"]
    assert client.get("/api/documents").json()["count"] == 5


def test_missing_document_and_key_404(client):
    assert client.get("/api/documents/nope").status_code == 404
    assert client.get("/api/documents/by-key/nope/versions").status_code == 404


def test_parse_markdown_front_matter():
    md = ("---\ndoc_key: research-eval-plan\ntitle: Approved plan\ndoc_type: plan\nplan_status: approved\n"
          "authored_at: 2026-10-08\nteam_tags: [research]\nsupersedes: research-timeline-thread@1\n"
          "is_simulated: true\n---\n\nBody line one.\n")
    meta = parse_markdown_document(md)
    assert meta["supersedes_doc_key"] == "research-timeline-thread" and meta["supersedes_version"] == 1
    assert meta["team_tags"] == ["research"] and meta["is_simulated"] is True
    assert meta["content"] == "Body line one.\n"
    assert meta["authored_at"].tzinfo is not None
    with pytest.raises(DomainError):
        parse_markdown_document("no front matter")


def test_new_version_of_superseded_thread_stays_superseded(client, corpus):
    """Thread v2 (one more reply, dated before the plan) must not undo the plan's explicit supersede."""
    r = post(client, {**THREAD, "authored_at": "2026-09-05T10:00:00Z",
                      "content": THREAD["content"] + "\nAgreed, revisit next period."})
    assert r.status_code == 201, r.text
    v2 = r.json()["document"]
    assert v2["version"] == 2 and v2["is_current"] is False
    assert v2["superseded_by"]["id"] == corpus["plan"]
    v1 = client.get(f"/api/documents/{corpus['thread']}").json()
    assert v1["superseded_by"]["id"] == corpus["plan"]  # the plan's link is not overwritten
    current = client.get("/api/documents", params={"q": "model-evaluation", "include_superseded": "false"}).json()
    items = current["items"] if isinstance(current, dict) else current
    assert {d["doc_key"] for d in items} == {"research-eval-plan"}


def test_same_content_with_changed_plan_status_creates_a_version(client, corpus):
    r = post(client, {**LAUNCH_V2, "plan_status": "cancelled", "authored_at": "2026-10-20T09:00:00Z"})
    assert r.status_code == 201, r.text
    doc = r.json()["document"]
    assert doc["version"] == 3 and doc["plan_status"] == "cancelled" and doc["is_current"] is True
    # Re-importing the older (approved) export is still a no-op and cannot make it current again.
    again = post(client, LAUNCH_V2)
    assert again.status_code == 200 and again.json()["duplicate_of_version"] == 2
    assert client.get("/api/documents/by-key/product-launch-plan/versions").json()["current_version"] == 3
