"""Context signals: verified ingest, citation currency, curation (design.md §3.10).

Rules:
- Every signal cites at least one specific document version with an exact quote. The backend checks
  `content[char_start:char_end] == quote`; if offsets are missing or wrong it locates the exact quote
  itself (first occurrence) and reports `offsets_corrected`. A quote that is not verbatim in the
  cited version is 422 `citation_not_found`.
- `citation_currency` is computed at read time from the cited document, so a later version of a
  plan makes older citations visibly `superseded`.
- A `current` signal whose citations are all superseded documents is 422
  `signal_cites_superseded_only` (on create and when finance marks a signal current).
- `produced_by` is derived from the caller, never trusted from the body: finance roles -> `finance`,
  the Droid role -> the runner kind of its agent run (or the configured runner).
- Signals are never hard-deleted once used as evidence; delete is refused with 409 `signal_in_use`.
- Scope (frontend-integration-design §2.4): `person` signals name active people who all work on one
  team (the team is derived when omitted and must match when given); `team` signals name no people;
  `company` signals have no team and no people and apply to every team. Every violation is 422
  `validation_failed` with `reasons[].code` (`person_ids_required`, `unknown_person`,
  `person_team_mismatch`, `person_ids_not_allowed`, `team_not_allowed`).
- Person attribution is grounded in the cited text, not in metadata: every person a `person` signal names
  must be named in at least one cited document version (full name, or a first name no other active person
  shares; case-insensitive, whole words). A document's person tags alone are not enough. A person the cited
  text does not name is 422 `validation_failed` with `reasons[].code == "person_not_in_citations"`.
"""

from __future__ import annotations

import re

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.actors import FINANCE_ROLES, Actor
from app.core.clock import Clock, IdFactory
from app.core.errors import DomainError
from app.db.models import AgentRun, ContextSignal, CorpusDocument, Proposal, SignalCitation, Team
from app.schemas.signals import ContextSignalIn, ContextSignalPatch
from app.services import people as people_svc


def _fail(code: str, message: str, reasons: list[dict]) -> DomainError:
    return DomainError(code, 422, message, {"reasons": reasons})


def _verify_citation(doc: CorpusDocument, quote: str, start: int | None, end: int | None) -> tuple[int, int, bool] | None:
    if start is not None and end is not None and doc.content[start:end] == quote:
        return start, end, False
    idx = doc.content.find(quote)
    if idx < 0:
        return None
    return idx, idx + len(quote), start is not None


def _producer(session: Session, actor: Actor, agent_run_id: str | None, runner_kind: str) -> str:
    if actor.role in FINANCE_ROLES:
        return "finance"
    if agent_run_id:
        run = session.get(AgentRun, agent_run_id)
        if run is not None:
            return f"droid_{run.runner_kind}"
    return f"droid_{runner_kind}"


def get_signal(session: Session, signal_id: str) -> ContextSignal:
    sig = session.get(ContextSignal, signal_id)
    if sig is None:
        raise DomainError("not_found", 404, f"signal {signal_id!r} not found")
    return sig


def _scope_reasons(session: Session, body: ContextSignalIn) -> tuple[list[dict], str | None]:
    """Validate scope / person_ids / team. Returns (reasons, effective team)."""
    reasons: list[dict] = []
    team = body.team
    if body.scope == "person":
        if not body.person_ids:
            reasons.append({"code": "person_ids_required", "field": "person_ids",
                            "message": "a person-scope signal must name at least one person (ids from list_people)"})
            return reasons, team
        people = []
        for pid in body.person_ids:
            try:
                person = people_svc.get_person(session, pid)
            except DomainError:
                person = None
            if person is None or not person.active:
                reasons.append({"code": "unknown_person", "field": "person_ids", "person_id": pid,
                                "message": f"unknown or inactive person {pid!r}"})
            else:
                people.append(person)
        teams = sorted({p.team_id for p in people})
        if len(teams) > 1:
            reasons.append({"code": "person_team_mismatch", "field": "person_ids", "teams": teams,
                            "message": f"all people in one signal must be on one team, got {teams}"})
        elif teams and team is not None and team != teams[0]:
            reasons.append({"code": "person_team_mismatch", "field": "team", "teams": teams,
                            "message": f"team {team!r} does not match the people's team {teams[0]!r}"})
        elif teams and team is None:
            team = teams[0]
    elif body.scope == "team":
        if body.person_ids:
            reasons.append({"code": "person_ids_not_allowed", "field": "person_ids",
                            "message": "a team-scope signal names no people; use scope person"})
    else:  # company
        if body.team is not None:
            reasons.append({"code": "team_not_allowed", "field": "team",
                            "message": "a company-scope signal applies to every team; leave team null"})
        if body.person_ids:
            reasons.append({"code": "person_ids_not_allowed", "field": "person_ids",
                            "message": "a company-scope signal names no people"})
    return reasons, team


def _names(text: str, name: str) -> bool:
    return bool(name) and re.search(rf"(?<!\w){re.escape(name.lower())}(?!\w)", text.lower()) is not None


def _ungrounded_people(session: Session, person_ids: list[str], docs: list[CorpusDocument]) -> list[dict]:
    """Reasons for each person id that no cited document version names in its text."""
    if not person_ids:
        return []
    active = people_svc.list_people(session)
    first_counts: dict[str, int] = {}
    for p in active:
        first = p.name.split()[0].lower() if p.name.split() else ""
        first_counts[first] = first_counts.get(first, 0) + 1
    reasons = []
    for pid in person_ids:
        try:
            person = people_svc.get_person(session, pid)
        except DomainError:
            person = None
        if person is None:
            continue  # already reported by _scope_reasons
        parts = person.name.split()
        first = parts[0] if parts else ""
        unique_first = len(parts) > 1 and first_counts.get(first.lower(), 0) == 1
        if any(_names(d.content, person.name) or (unique_first and _names(d.content, first)) for d in docs):
            continue
        reasons.append({"code": "person_not_in_citations", "field": "person_ids", "person_id": pid,
                        "document_ids": [d.id for d in docs],
                        "message": f"{person.name} ({pid}) is not named in any cited document; a person-scope "
                                   "signal may only name people the cited text names"})
    return reasons


def create_signal(
    session: Session, body: ContextSignalIn, *, actor: Actor, runner_kind: str, clock: Clock, ids: IdFactory
) -> tuple[ContextSignal, set[tuple[str, int]]]:
    reasons, team_id = _scope_reasons(session, body)
    if body.team is not None:
        team = session.get(Team, body.team)
        if team is None or not team.active:
            reasons.append({"code": "unknown_team", "message": f"unknown or inactive team {body.team!r}",
                            "field": "team"})
    if body.agent_run_id is not None and session.get(AgentRun, body.agent_run_id) is None:
        reasons.append({"code": "unknown_agent_run", "message": f"agent run {body.agent_run_id!r} not found",
                        "field": "agent_run_id"})
    prior = None
    if body.supersedes_signal_id is not None:
        prior = session.get(ContextSignal, body.supersedes_signal_id)
        if prior is None:
            reasons.append({"code": "unknown_signal", "message": f"signal {body.supersedes_signal_id!r} not found",
                            "field": "supersedes_signal_id"})
        elif prior.superseded_by_signal_id is not None:
            raise DomainError("already_superseded", 409, f"signal {prior.id} is already superseded",
                              {"superseded_by_signal_id": prior.superseded_by_signal_id})
    if reasons:
        raise _fail("validation_failed", "signal is invalid", reasons)

    verified: list[tuple[CorpusDocument, str, int, int, bool]] = []
    missing: list[dict] = []
    seen: set[tuple[str, int, int]] = set()
    for i, c in enumerate(body.citations):
        doc = session.get(CorpusDocument, c.document_id)
        if doc is None:
            missing.append({"code": "unknown_document", "line": i, "document_id": c.document_id,
                            "message": f"document {c.document_id!r} not found"})
            continue
        span = _verify_citation(doc, c.quote, c.char_start, c.char_end)
        if span is None:
            missing.append({"code": "citation_not_found", "line": i, "document_id": doc.id,
                            "doc_key": doc.doc_key, "version": doc.version,
                            "message": f"quote does not occur verbatim in {doc.doc_key} v{doc.version}"})
            continue
        start, end, corrected = span
        if (doc.id, start, end) in seen:
            continue
        seen.add((doc.id, start, end))
        verified.append((doc, c.quote, start, end, corrected))
    if missing:
        code = "citation_not_found" if any(m["code"] == "citation_not_found" for m in missing) else "unknown_document"
        raise _fail(code, "every citation must quote a stored document version exactly", missing)

    if body.scope == "person":
        ungrounded = _ungrounded_people(session, list(body.person_ids), [d for d, *_ in verified])
        if ungrounded:
            raise _fail("validation_failed", "signal is invalid", ungrounded)

    if body.status == "current" and all(d.superseded_by_document_id is not None for d, *_ in verified):
        raise _fail("signal_cites_superseded_only",
                    "a current signal cannot rest only on superseded documents; cite the newer version",
                    [{"code": "signal_cites_superseded_only", "document_id": d.id, "doc_key": d.doc_key,
                      "version": d.version, "superseded_by_document_id": d.superseded_by_document_id,
                      "message": f"{d.doc_key} v{d.version} has been superseded"} for d, *_ in verified])

    if body.status == "current" and all(d.plan_status == "cancelled" for d, *_ in verified):
        raise _fail("signal_cites_cancelled_only",
                    "a current signal cannot rest only on cancelled documents; record it as cancelled",
                    [{"code": "signal_cites_cancelled_only", "document_id": d.id, "doc_key": d.doc_key,
                      "version": d.version, "plan_status": d.plan_status,
                      "message": f"{d.doc_key} v{d.version} is cancelled"} for d, *_ in verified])

    now = clock.now()
    sig = ContextSignal(
        id=ids.new_id("sig_"), created_at=now, team_id=team_id, scope=body.scope, person_ids=list(body.person_ids),
        signal_kind=body.signal_kind, title=body.title, project=body.project, summary=body.summary,
        change_type=body.change_type, applies_from=body.applies_from, applies_to=body.applies_to,
        status=body.status, uncertainty=body.uncertainty,
        produced_by=_producer(session, actor, body.agent_run_id, runner_kind), agent_run_id=body.agent_run_id,
    )
    session.add(sig)
    session.flush()
    corrected_flags: set[tuple[str, int]] = set()
    for doc, quote, start, end, corrected in verified:
        session.add(SignalCitation(id=ids.new_id("cit_"), created_at=now, signal_id=sig.id, document_id=doc.id,
                                   quote=quote, char_start=start, char_end=end))
        if corrected:
            corrected_flags.add((doc.id, start))
    if prior is not None:
        prior.superseded_by_signal_id = sig.id
        prior.status = "superseded"
    session.flush()
    session.refresh(sig)
    from app.forecasting.native_evidence import capture_signal_documents
    capture_signal_documents(session, sig, now=now)
    if prior is not None:
        capture_signal_documents(session, prior, now=now)
    return sig, corrected_flags


def list_signals(session: Session, *, team: str | None = None, status: str | None = None,
                 project: str | None = None, scope: str | None = None, person: str | None = None,
                 include_company: bool = False) -> list[ContextSignal]:
    """`include_company` adds every company-scope signal to a `team` filter (company signals have no team
    but apply to every team). `person` matches signals whose person_ids contain that id."""
    q = select(ContextSignal).order_by(ContextSignal.created_at, ContextSignal.id)
    if team == "none":
        q = q.where(ContextSignal.team_id.is_(None))
    elif team and include_company:
        q = q.where(or_(ContextSignal.team_id == team, ContextSignal.scope == "company"))
    elif team:
        q = q.where(ContextSignal.team_id == team)
    if status:
        q = q.where(ContextSignal.status == status)
    if project:
        q = q.where(ContextSignal.project == project)
    if scope:
        q = q.where(ContextSignal.scope == scope)
    rows = list(session.scalars(q))
    if person:
        # Filtered in Python so the JSON containment check stays portable across databases.
        rows = [r for r in rows if person in (r.person_ids or [])]
    return rows


def patch_signal(session: Session, signal_id: str, body: ContextSignalPatch, *, clock: Clock) -> ContextSignal:
    sig = get_signal(session, signal_id)
    if body.superseded_by_signal_id is not None:
        if body.superseded_by_signal_id == sig.id:
            raise DomainError("validation_failed", 422, "a signal cannot supersede itself",
                              {"reasons": [{"code": "self_supersede", "message": "a signal cannot supersede itself"}]})
        newer = session.get(ContextSignal, body.superseded_by_signal_id)
        if newer is None:
            raise DomainError("validation_failed", 422, "superseding signal not found",
                              {"reasons": [{"code": "unknown_signal",
                                            "message": f"signal {body.superseded_by_signal_id!r} not found"}]})
        sig.superseded_by_signal_id = newer.id
        sig.status = "superseded"
    if body.status is not None:
        if body.status == "current" and sig.superseded_by_signal_id is not None and body.superseded_by_signal_id is None:
            raise DomainError("validation_failed", 422, "signal is superseded by another signal",
                              {"reasons": [{"code": "signal_superseded",
                                            "message": f"superseded by {sig.superseded_by_signal_id}"}]})
        if body.status == "current":
            docs = [session.get(CorpusDocument, c.document_id) for c in sig.citations]
            if docs and all(d.superseded_by_document_id is not None for d in docs):
                raise DomainError("signal_cites_superseded_only", 422,
                                  "a current signal cannot rest only on superseded documents",
                                  {"reasons": [{"code": "signal_cites_superseded_only", "document_id": d.id,
                                                "message": f"{d.doc_key} v{d.version} has been superseded"}
                                               for d in docs]})
        if body.superseded_by_signal_id is None:
            sig.status = body.status
    if body.uncertainty is not None:
        if not body.uncertainty.strip():
            raise DomainError("validation_failed", 422, "uncertainty must not be blank",
                              {"reasons": [{"code": "uncertainty_required", "message": "uncertainty is required"}]})
        sig.uncertainty = body.uncertainty.strip()
    session.flush()
    from app.forecasting.native_evidence import capture_signal_documents
    capture_signal_documents(session, sig, now=clock.now())
    return sig


def delete_signal(session: Session, signal_id: str) -> None:
    sig = get_signal(session, signal_id)
    documents = [session.get(CorpusDocument, c.document_id) for c in sig.citations]
    users = [p.id for p in session.scalars(select(Proposal))
             if any(r.get("kind") == "signal" and r.get("id") == sig.id for r in (p.evidence_refs or []))]
    successors = list(session.scalars(select(ContextSignal.id).where(ContextSignal.superseded_by_signal_id == sig.id)))
    if users or successors or sig.superseded_by_signal_id:
        raise DomainError("signal_in_use", 409,
                          "this signal is part of the evidence trail and cannot be deleted; mark it superseded instead",
                          {"cited_by_proposals": users, "supersedes_signals": successors,
                           "superseded_by_signal_id": sig.superseded_by_signal_id})
    for c in list(sig.citations):
        session.delete(c)
    session.delete(sig)
    session.flush()
    from app.forecasting.native_evidence import capture_native_documents
    trusted_clock = session.info.get('forecast_clock')
    if trusted_clock is not None:
        capture_native_documents(session, documents, now=trusted_clock())


def signal_out(session: Session, sig: ContextSignal, corrected: set[tuple[str, int]] | None = None) -> dict:
    cites = []
    for c in sorted(sig.citations, key=lambda c: (c.document_id, c.char_start)):
        doc = session.get(CorpusDocument, c.document_id)
        cites.append({
            "id": c.id, "document_id": doc.id, "doc_key": doc.doc_key, "version": doc.version, "title": doc.title,
            "quote": c.quote, "char_start": c.char_start, "char_end": c.char_end,
            "citation_currency": "superseded" if doc.superseded_by_document_id else "current",
            "superseded_by_document_id": doc.superseded_by_document_id,
            "offsets_corrected": (c.document_id, c.char_start) in (corrected or set()),
        })
    predecessors = list(session.scalars(
        select(ContextSignal.id).where(ContextSignal.superseded_by_signal_id == sig.id).order_by(ContextSignal.id)
    ))
    return {
        "id": sig.id, "team": sig.team_id, "scope": sig.scope, "person_ids": list(sig.person_ids or []),
        "signal_kind": sig.signal_kind, "title": sig.title, "project": sig.project, "summary": sig.summary,
        "change_type": sig.change_type, "applies_from": sig.applies_from, "applies_to": sig.applies_to,
        "status": sig.status, "uncertainty": sig.uncertainty, "produced_by": sig.produced_by,
        "agent_run_id": sig.agent_run_id, "superseded_by_signal_id": sig.superseded_by_signal_id,
        "supersedes_signal_ids": predecessors, "citations": cites,
        "needs_review": sig.status == "current" and bool(cites)
                        and all(c["citation_currency"] == "superseded" for c in cites),
        "created_at": sig.created_at,
    }
