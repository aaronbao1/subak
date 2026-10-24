"""Context signals (acceptance checks 4a, 4b): exact citations, currency, curation, guarded delete."""

from __future__ import annotations

import pytest

ANALYST = {"X-Actor-Id": "ana", "X-Actor-Role": "finance_analyst"}
DROID = {"X-Actor-Id": "droid", "X-Actor-Role": "droid_agent"}
IMPORTER = {"X-Actor-Id": "imp", "X-Actor-Role": "importer"}

PLAN_QUOTE = "This plan expands model-evaluation work during the current planning period."
THREAD_QUOTE = "we will push the model-evaluation expansion to next period."


def doc_id(client, key, version=None):
    vs = client.get(f"/api/documents/by-key/{key}/versions").json()["versions"]
    return vs[-1]["id"] if version is None else next(v["id"] for v in vs if v["version"] == version)


def body(document_id, quote, **extra):
    return {"team": "research", "project": "model-evaluation", "change_type": "expansion", "status": "current",
            "summary": "Research evaluation expands this period.", "uncertainty": "volume unknown",
            "citations": [{"document_id": document_id, "quote": quote, **extra.pop("cite", {})}], **extra}


@pytest.fixture
def docs(seeded, client):
    return {"plan": doc_id(client, "research-eval-plan"), "thread": doc_id(client, "research-timeline-thread"),
            "v1": doc_id(client, "product-launch-plan", 1), "v2": doc_id(client, "product-launch-plan", 2)}


def test_signal_citation_resolves_to_document_version_and_exact_quote(docs, client):
    r = client.post("/api/signals", json=body(docs["plan"], PLAN_QUOTE), headers=DROID)
    assert r.status_code == 201, r.text
    sig = r.json()
    cite = sig["citations"][0]
    assert (cite["doc_key"], cite["version"], cite["citation_currency"]) == ("research-eval-plan", 1, "current")
    content = client.get(f"/api/documents/{cite['document_id']}").json()["content"]
    assert content[cite["char_start"]:cite["char_end"]] == PLAN_QUOTE
    assert sig["produced_by"] == "droid_fake" and sig["needs_review"] is False
    assert client.get(f"/api/signals/{sig['id']}").json() == {**sig, "citations": [{**cite, "offsets_corrected": False}]}


def test_citation_quote_not_in_document_rejected(docs, client):
    r = client.post("/api/signals", json=body(docs["plan"], "research budget doubles this period"), headers=DROID)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "citation_not_found"
    assert client.get("/api/signals").json()["count"] == 0


def test_wrong_offsets_are_corrected_to_the_exact_quote(docs, client):
    r = client.post("/api/signals", json=body(docs["plan"], PLAN_QUOTE, cite={"char_start": 0, "char_end": 10}),
                    headers=DROID)
    assert r.status_code == 201
    cite = r.json()["citations"][0]
    assert cite["offsets_corrected"] is True and cite["char_start"] > 0


def test_unknown_document_and_unknown_team_rejected(docs, client):
    r = client.post("/api/signals", json=body("doc_nope", PLAN_QUOTE), headers=DROID)
    assert r.status_code == 422 and r.json()["error"]["code"] == "unknown_document"
    r = client.post("/api/signals", json=body(docs["plan"], PLAN_QUOTE, team="marketing"), headers=DROID)
    assert r.status_code == 422
    assert r.json()["error"]["details"]["reasons"][0]["code"] == "unknown_team"


def test_citation_currency_marks_superseded_document(docs, client):
    r = client.post("/api/signals", json=body(docs["thread"], THREAD_QUOTE, status="superseded"), headers=DROID)
    assert r.status_code == 201
    assert r.json()["citations"][0]["citation_currency"] == "superseded"
    assert r.json()["citations"][0]["superseded_by_document_id"] == docs["plan"]


def test_current_signal_citing_only_superseded_docs_rejected(docs, client):
    r = client.post("/api/signals", json=body(docs["thread"], THREAD_QUOTE), headers=DROID)
    assert r.status_code == 422 and r.json()["error"]["code"] == "signal_cites_superseded_only"
    mixed = body(docs["v2"], "The general-availability launch milestone moves to the following period", team="product")
    mixed["citations"].append({"document_id": docs["v1"], "quote": "launch milestone for the assistant workspace"})
    r = client.post("/api/signals", json=mixed, headers=DROID)
    assert r.status_code == 201
    assert sorted(c["citation_currency"] for c in r.json()["citations"]) == ["current", "superseded"]


def test_new_document_version_makes_existing_signal_need_review(docs, client):
    sig = client.post("/api/signals", json=body(docs["plan"], PLAN_QUOTE), headers=DROID).json()
    doc = client.get(f"/api/documents/{docs['plan']}").json()
    new = {k: doc[k] for k in ("doc_key", "title", "origin", "doc_type", "plan_status", "team_tags",
                                "project_tags", "is_simulated")}
    new.update(authored_at="2026-10-20T00:00:00Z", content="Revised: evaluation expansion is cancelled.")
    assert client.post("/api/documents", json=new, headers=IMPORTER).status_code == 201
    again = client.get(f"/api/signals/{sig['id']}").json()
    assert again["citations"][0]["citation_currency"] == "superseded"
    assert again["needs_review"] is True


def test_finance_role_marks_producer_finance_and_importer_forbidden(docs, client):
    r = client.post("/api/signals", json=body(docs["plan"], PLAN_QUOTE), headers=ANALYST)
    assert r.json()["produced_by"] == "finance"
    r = client.post("/api/signals", json=body(docs["plan"], PLAN_QUOTE), headers=IMPORTER)
    assert r.status_code == 403 and r.json()["error"]["code"] == "role_forbidden"
    assert client.post("/api/signals", json=body(docs["plan"], PLAN_QUOTE)).status_code == 401


def test_body_validation(docs, client):
    no_cites = {**body(docs["plan"], PLAN_QUOTE), "citations": []}
    assert client.post("/api/signals", json=no_cites, headers=DROID).status_code == 422
    blank = body(docs["plan"], PLAN_QUOTE, uncertainty="   ")
    assert client.post("/api/signals", json=blank, headers=DROID).status_code == 422
    backwards = body(docs["plan"], PLAN_QUOTE, applies_from="2026-12-01", applies_to="2026-10-01")
    assert client.post("/api/signals", json=backwards, headers=DROID).status_code == 422
    forged = body(docs["plan"], PLAN_QUOTE, produced_by="finance")
    assert client.post("/api/signals", json=forged, headers=DROID).status_code == 422


def test_supersede_signal_chain_and_filters(docs, client):
    old = client.post("/api/signals", json=body(docs["plan"], PLAN_QUOTE), headers=DROID).json()
    new = client.post("/api/signals", json=body(docs["plan"], PLAN_QUOTE, supersedes_signal_id=old["id"],
                                                summary="Refined reading."), headers=DROID).json()
    old_now = client.get(f"/api/signals/{old['id']}").json()
    assert old_now["status"] == "superseded" and old_now["superseded_by_signal_id"] == new["id"]
    assert new["supersedes_signal_ids"] == [old["id"]]
    again = client.post("/api/signals", json=body(docs["plan"], PLAN_QUOTE, supersedes_signal_id=old["id"]),
                        headers=DROID)
    assert again.status_code == 409 and again.json()["error"]["code"] == "already_superseded"
    assert [s["id"] for s in client.get("/api/signals", params={"status": "current"}).json()["items"]] == [new["id"]]
    assert client.get("/api/signals", params={"team": "product"}).json()["count"] == 0


def test_patch_is_finance_only_and_rechecks_currency(docs, client):
    sig = client.post("/api/signals", json=body(docs["thread"], THREAD_QUOTE, status="superseded"),
                      headers=DROID).json()
    assert client.patch(f"/api/signals/{sig['id']}", json={"status": "current"}, headers=DROID).status_code == 403
    r = client.patch(f"/api/signals/{sig['id']}", json={"status": "current"}, headers=ANALYST)
    assert r.status_code == 422 and r.json()["error"]["code"] == "signal_cites_superseded_only"
    r = client.patch(f"/api/signals/{sig['id']}", json={"status": "conflicting", "uncertainty": "contradicts plan"},
                     headers=ANALYST)
    assert r.status_code == 200 and r.json()["status"] == "conflicting"
    assert client.patch(f"/api/signals/{sig['id']}", json={"summary": "x"}, headers=ANALYST).status_code == 422


def test_delete_refused_once_cited_by_a_proposal(docs, client):
    sig = client.post("/api/signals", json=body(docs["plan"], PLAN_QUOTE), headers=DROID).json()
    spare = client.post("/api/signals", json=body(docs["plan"], PLAN_QUOTE), headers=DROID).json()
    prop = {"action_type": "transfer", "base_version": 1, "rationale": "r",
            "lines": [{"from_team": "product", "to_team": "research", "amount": "1000.00"}],
            "evidence_refs": [{"kind": "signal", "id": sig["id"]}]}
    assert client.post("/api/proposals", json=prop, headers=DROID).status_code == 201
    r = client.delete(f"/api/signals/{sig['id']}", headers=ANALYST)
    assert r.status_code == 409 and r.json()["error"]["code"] == "signal_in_use"
    assert client.delete(f"/api/signals/{spare['id']}", headers=DROID).status_code == 403
    assert client.delete(f"/api/signals/{spare['id']}", headers=ANALYST).status_code == 204
    assert client.get(f"/api/signals/{spare['id']}").status_code == 404
