"""Company-context corpus: documents, versions, supersedes links, keyword search (design.md §3.9).

Rules:
- Content is stored with normalized newlines; citation offsets index into stored content.
- A document's identity is its content plus its authoritative metadata (doc_type, plan_status,
  effective dates, team tags). An identity equal to ANY existing version of a doc_key is a no-op
  (re-importing an old export can never make an outdated version current again). Changed content, or
  the same content with changed metadata (e.g. a plan moving from draft to approved, or cancelled),
  creates version+1 that supersedes the previous latest version.
- If the latest version was already superseded by ANOTHER document (e.g. an approved plan replaced an
  email thread), that supersede carries over: the new version is born superseded by the same
  document, and the older version's link is left untouched. A newer reply on a replaced thread never
  makes that thread current again.
- A new version dated before the current version is rejected (it would wrongly become current).
- Cross-document supersedes (e.g. an approved plan superseding an older email thread) is explicit,
  must point at an older document of a different doc_key, and a document is superseded only once.
- Old versions are never deleted; search can include or exclude superseded documents, and every
  result says whether it is current.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.clock import Clock, IdFactory
from app.core.errors import DomainError
from app.db.models import CorpusDocument

SNIPPET_RADIUS = 80
MAX_MATCHES_PER_DOC = 3


def normalize_content(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def content_hash(text: str) -> str:
    return hashlib.sha256(normalize_content(text).encode("utf-8")).hexdigest()


@dataclass
class IngestOutcome:
    document: CorpusDocument
    created: bool
    duplicate_of_version: int | None = None


def _get(session: Session, document_id: str) -> CorpusDocument:
    doc = session.get(CorpusDocument, document_id)
    if doc is None:
        raise DomainError("not_found", 404, f"document {document_id!r} not found")
    return doc


def get_document(session: Session, document_id: str) -> CorpusDocument:
    return _get(session, document_id)


def versions(session: Session, doc_key: str) -> list[CorpusDocument]:
    rows = session.scalars(
        select(CorpusDocument).where(CorpusDocument.doc_key == doc_key).order_by(CorpusDocument.version)
    ).all()
    if not rows:
        raise DomainError("not_found", 404, f"no documents with doc_key {doc_key!r}")
    return list(rows)


def _resolve_supersedes_target(
    session: Session, *, document_id: str | None, doc_key: str | None, version: int | None
) -> CorpusDocument | None:
    if document_id:
        return _get(session, document_id)
    if not doc_key:
        return None
    q = select(CorpusDocument).where(CorpusDocument.doc_key == doc_key)
    if version is not None:
        target = session.scalars(q.where(CorpusDocument.version == version)).one_or_none()
    else:
        target = session.scalars(q.order_by(CorpusDocument.version.desc()).limit(1)).one_or_none()
    if target is None:
        raise DomainError(
            "supersedes_target_not_found", 422,
            f"supersedes target {doc_key!r}{'' if version is None else f' v{version}'} not found",
        )
    return target


def ingest_document(session: Session, data: Any, *, clock: Clock, ids: IdFactory) -> IngestOutcome:
    """`data` is a DocumentIn (schemas/documents.py)."""
    content = normalize_content(data.content)
    digest = content_hash(content)
    existing = versions(session, data.doc_key) if _key_exists(session, data.doc_key) else []

    identity = _identity(digest, data.doc_type, data.plan_status, data.effective_from, data.effective_to,
                         data.team_tags)
    for doc in existing:
        if _identity(doc.content_hash, doc.doc_type, doc.plan_status, doc.effective_from, doc.effective_to,
                     doc.team_tags) == identity:
            return IngestOutcome(doc, created=False, duplicate_of_version=doc.version)

    latest = existing[-1] if existing else None
    if latest is not None and data.authored_at < latest.authored_at:
        raise DomainError(
            "version_predates_current", 422,
            f"new content for {data.doc_key!r} is dated before current version v{latest.version}; "
            "an older document cannot become the current version",
            {"current_version": latest.version, "current_authored_at": latest.authored_at.isoformat()},
        )

    target = _resolve_supersedes_target(
        session,
        document_id=data.supersedes_document_id,
        doc_key=data.supersedes_doc_key,
        version=data.supersedes_version,
    )
    if target is not None:
        if target.doc_key == data.doc_key:
            raise DomainError(
                "supersedes_same_key", 422,
                "versions of the same doc_key supersede each other automatically; name another document",
            )
        if target.authored_at > data.authored_at:
            raise DomainError(
                "supersedes_newer_document", 422,
                f"{target.doc_key} v{target.version} is newer than this document and cannot be superseded by it",
            )
        if target.superseded_by_document_id is not None:
            raise DomainError(
                "already_superseded", 409,
                f"{target.doc_key} v{target.version} is already superseded",
                {"superseded_by_document_id": target.superseded_by_document_id},
            )

    doc = CorpusDocument(
        id=ids.new_id("doc_"),
        created_at=clock.now(),
        doc_key=data.doc_key,
        version=(latest.version + 1) if latest else 1,
        title=data.title,
        origin=data.origin,
        doc_type=data.doc_type,
        plan_status=data.plan_status,
        authored_at=data.authored_at,
        effective_from=data.effective_from,
        effective_to=data.effective_to,
        team_tags=list(data.team_tags),
        project_tags=list(data.project_tags),
        author=data.author,
        content=content,
        content_hash=digest,
        supersedes_document_id=(target.id if target else (latest.id if latest else None)),
        is_simulated=data.is_simulated,
    )
    session.add(doc)
    session.flush()
    if latest is not None:
        replaced_by = session.get(CorpusDocument, latest.superseded_by_document_id) \
            if latest.superseded_by_document_id else None
        if replaced_by is not None and replaced_by.doc_key != latest.doc_key:
            # Explicitly superseded by another document: keep that link and carry it to the new version.
            doc.superseded_by_document_id = replaced_by.id
        else:
            latest.superseded_by_document_id = doc.id
    if target is not None:
        target.superseded_by_document_id = doc.id
    session.flush()
    return IngestOutcome(doc, created=True)


def _identity(digest: str, doc_type: Any, plan_status: Any, effective_from: Any, effective_to: Any,
              team_tags: Any) -> tuple:
    norm_tags = tuple(sorted({str(t).strip().lower() for t in (team_tags or [])}))
    return (digest, doc_type, plan_status, effective_from, effective_to, norm_tags)


def _key_exists(session: Session, doc_key: str) -> bool:
    return bool(session.scalar(select(func.count()).where(CorpusDocument.doc_key == doc_key)))


# ---- search ----------------------------------------------------------------------------------

_TERM_RE = re.compile(r'"([^"]+)"|(\S+)')


def parse_query(q: str) -> list[str]:
    """Whitespace-separated terms, "quoted phrases" kept together, lowercase."""
    terms = []
    for phrase, word in _TERM_RE.findall(q or ""):
        term = (phrase or word).strip().lower()
        if term:
            terms.append(term)
    return terms


def _find_all(haystack: str, needle: str) -> list[int]:
    out, start = [], 0
    while True:
        idx = haystack.find(needle, start)
        if idx < 0:
            return out
        out.append(idx)
        start = idx + 1


def search_documents(
    session: Session,
    *,
    q: str | None = None,
    team: str | None = None,
    project: str | None = None,
    doc_type: str | None = None,
    origin: str | None = None,
    include_superseded: bool = True,
) -> list[tuple[CorpusDocument, list[dict[str, Any]], int]]:
    """Returns [(document, matches, score)]. All terms must match (title, content or tags).
    `matches` give exact offsets into the stored content so a caller can cite an exact quote."""
    stmt = select(CorpusDocument)
    if doc_type:
        stmt = stmt.where(CorpusDocument.doc_type == doc_type)
    if origin:
        stmt = stmt.where(CorpusDocument.origin == origin)
    if not include_superseded:
        stmt = stmt.where(CorpusDocument.superseded_by_document_id.is_(None))
    docs = session.scalars(stmt).all()
    team_l = team.lower() if team else None
    project_l = project.lower() if project else None
    terms = parse_query(q) if q else []

    results = []
    for doc in docs:
        if team_l and team_l not in [t.lower() for t in doc.team_tags]:
            continue
        if project_l and project_l not in [p.lower() for p in doc.project_tags]:
            continue
        if not terms:
            results.append((doc, [], 0))
            continue
        content_l = doc.content.lower()
        meta_l = " ".join([doc.title, *doc.team_tags, *doc.project_tags, doc.doc_key]).lower()
        score = 0
        matches: list[dict[str, Any]] = []
        ok = True
        for term in terms:
            hits = _find_all(content_l, term)
            meta_hits = meta_l.count(term)
            if not hits and not meta_hits:
                ok = False
                break
            score += len(hits) + 2 * meta_hits
            for idx in hits:
                if len(matches) >= MAX_MATCHES_PER_DOC * len(terms):
                    break
                end = idx + len(term)
                s0, s1 = max(0, idx - SNIPPET_RADIUS), min(len(doc.content), end + SNIPPET_RADIUS)
                matches.append({
                    "term": term,
                    "char_start": idx,
                    "char_end": end,
                    "text": doc.content[idx:end],
                    "snippet": doc.content[s0:s1],
                })
        if ok:
            matches.sort(key=lambda m: m["char_start"])
            results.append((doc, matches, score))

    if terms:
        results.sort(key=lambda r: (-r[2], -r[0].authored_at.timestamp(), r[0].doc_key, r[0].version))
    else:
        results.sort(key=lambda r: (r[0].authored_at, r[0].doc_key, r[0].version))
    return results


# ---- markdown with front matter (seed corpus, uploads) ------------------------------------


def _fm_value(raw: str) -> Any:
    raw = raw.strip()
    if raw.startswith("[") and raw.endswith("]"):
        return [v.strip().strip("'\"") for v in raw[1:-1].split(",") if v.strip()]
    if raw.lower() in ("true", "false"):
        return raw.lower() == "true"
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "'\"":
        return raw[1:-1]
    return raw


def parse_markdown_document(text: str) -> dict[str, Any]:
    """Parse `---\\nkey: value\\n---\\nbody`. Returns a dict suitable for DocumentIn(**...).
    `supersedes: doc-key@2` (or `doc-key`) names an explicit cross-document supersede."""
    text = normalize_content(text)
    if not text.startswith("---\n"):
        raise DomainError("front_matter_required", 422, "document must start with a --- front-matter block")
    end = text.find("\n---\n", 4)
    if end < 0:
        raise DomainError("front_matter_required", 422, "front-matter block is not closed with ---")
    meta: dict[str, Any] = {}
    for line in text[4:end].split("\n"):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            raise DomainError("invalid_front_matter", 422, f"front-matter line is not 'key: value': {line!r}")
        key, value = line.split(":", 1)
        meta[key.strip()] = _fm_value(value)
    body = text[end + len("\n---\n"):]
    if body.startswith("\n"):
        body = body[1:]
    sup = meta.pop("supersedes", None)
    if sup:
        key, _, ver = str(sup).partition("@")
        meta["supersedes_doc_key"] = key.strip()
        if ver:
            meta["supersedes_version"] = int(ver)
    authored = meta.get("authored_at")
    if isinstance(authored, str) and len(authored) == 10:
        meta["authored_at"] = datetime.combine(date.fromisoformat(authored), time(0, 0), tzinfo=timezone.utc)
    meta["content"] = body
    return meta
