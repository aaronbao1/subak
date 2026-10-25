"""Corpus documents: list/search, detail, version chain, upload."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps import get_clock, get_ids
from app.core.actors import FINANCE_ROLES, Actor, require_role
from app.core.clock import Clock, IdFactory
from app.db.models import CorpusDocument
from app.db.session import get_session
from app.schemas.documents import (
    DocumentDetail,
    DocumentIn,
    DocumentIngestResult,
    DocumentList,
    DocumentSummary,
    DocumentVersions,
)
from app.services import corpus as svc

router = APIRouter(prefix="/api", tags=["documents"])


def _ref(session: Session, doc_id: str | None) -> dict | None:
    if not doc_id:
        return None
    d = session.get(CorpusDocument, doc_id)
    return None if d is None else {"id": d.id, "doc_key": d.doc_key, "version": d.version, "title": d.title}


def summary_dict(session: Session, d: CorpusDocument, *, content: bool = False) -> dict:
    out = {
        "id": d.id, "doc_key": d.doc_key, "version": d.version, "title": d.title, "origin": d.origin,
        "doc_type": d.doc_type, "plan_status": d.plan_status, "authored_at": d.authored_at,
        "effective_from": d.effective_from, "effective_to": d.effective_to, "team_tags": d.team_tags,
        "project_tags": d.project_tags, "author": d.author, "content_hash": d.content_hash,
        "is_simulated": d.is_simulated, "is_current": d.superseded_by_document_id is None,
        "supersedes": _ref(session, d.supersedes_document_id),
        "superseded_by": _ref(session, d.superseded_by_document_id),
    }
    if content:
        out["content"] = d.content
    return out


@router.get("/documents", response_model=DocumentList)
def list_documents(
    q: str | None = Query(default=None, max_length=500),
    team: str | None = None,
    project: str | None = None,
    doc_type: str | None = None,
    origin: str | None = None,
    include_superseded: bool = True,
    session: Session = Depends(get_session),
):
    hits = svc.search_documents(
        session, q=q, team=team, project=project, doc_type=doc_type, origin=origin,
        include_superseded=include_superseded,
    )
    items = [{**summary_dict(session, d), "score": score, "matches": matches} for d, matches, score in hits]
    return {
        "query": q,
        "filters": {"team": team, "project": project, "doc_type": doc_type, "origin": origin,
                    "include_superseded": include_superseded},
        "count": len(items),
        "items": items,
    }


@router.get("/documents/by-key/{doc_key}/versions", response_model=DocumentVersions)
def document_versions(doc_key: str, session: Session = Depends(get_session)):
    docs = svc.versions(session, doc_key)
    return {
        "doc_key": doc_key,
        "current_version": docs[-1].version,
        "versions": [summary_dict(session, d) for d in docs],
    }


@router.get("/documents/{document_id}", response_model=DocumentDetail)
def get_document(document_id: str, session: Session = Depends(get_session)):
    return summary_dict(session, svc.get_document(session, document_id), content=True)


@router.post("/documents", response_model=DocumentIngestResult, status_code=201)
def create_document(
    body: DocumentIn,
    session: Session = Depends(get_session),
    actor: Actor = Depends(require_role("importer", *FINANCE_ROLES)),
    clock: Clock = Depends(get_clock),
    ids: IdFactory = Depends(get_ids),
):
    outcome = svc.ingest_document(session, body, clock=clock, ids=ids)
    session.commit()
    payload = {
        "created": outcome.created,
        "duplicate_of_version": outcome.duplicate_of_version,
        "document": summary_dict(session, outcome.document, content=True),
    }
    if not outcome.created:
        return JSONResponse(status_code=200, content=DocumentIngestResult.model_validate(payload).model_dump(mode="json"))
    return payload
