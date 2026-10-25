"""Capture native documents and verified signal references in their write transaction.

One source stream per document key prevents repeated signals from duplicating a
numerical fact. Only the stored source passage is interpreted; agent summaries,
legacy multipliers and current directory metadata never become measurements.
"""
from __future__ import annotations

from contextlib import nullcontext
import json
import sqlite3

from sqlalchemy import select

from app.db.models import ContextSignal, CorpusDocument, SignalCitation
from .evidence import extract_event
from .persistence import iso


def _snapshot(session, now):
    service = session.info.get('forecast_service')
    if service is not None and not getattr(service.snapshot_factory, 'supports_as_of', False):
        return service.snapshot_factory(now=iso(now), tenant_id='northstar')
    from .repository import repository_snapshot_factory
    return repository_snapshot_factory(lambda: nullcontext(session), clock=lambda: now)(
        now=iso(now), tenant_id='northstar', as_of=False)


def capture_native_documents(session, documents, *, now):
    """Append immutable evidence beside the mutation; rollback removes both.

Standalone legacy sessions without a forecast store keep their original contract.
No separate connection, background race or read-side write is introduced.
"""
    store = session.info.get('forecast_store')
    if store is None:
        return
    session.flush()
    trusted_clock = session.info.get('forecast_clock')
    if trusted_clock is not None:
        now = max(iso(now), iso(trusted_clock()))
    connection = session.connection().connection.driver_connection
    if not connection.in_transaction:
        connection.execute('BEGIN IMMEDIATE')
    old_factory = connection.row_factory
    connection.row_factory = sqlite3.Row
    try:
        snapshot = None
        for key in sorted({doc.doc_key for doc in documents if doc is not None}):
            versions = list(session.scalars(select(CorpusDocument).where(
                CorpusDocument.doc_key == key).order_by(CorpusDocument.version)))
            if not versions:
                continue
            doc = versions[-1]
            refs = []
            blocked = bool(doc.superseded_by_document_id) or doc.plan_status in ('cancelled', 'informal', 'draft')
            citations = session.execute(select(SignalCitation, ContextSignal).join(
                ContextSignal, SignalCitation.signal_id == ContextSignal.id).where(
                SignalCitation.document_id.in_([d.id for d in versions])).order_by(
                ContextSignal.id, SignalCitation.document_id, SignalCitation.char_start)).all()
            by_signal = {}
            for citation, signal in citations:
                ref = by_signal.setdefault(signal.id, {'id': signal.id, 'status': signal.status,
                    'scope': signal.scope, 'team_id': signal.team_id,
                    'person_ids': list(signal.person_ids or []), 'citations': []})
                ref['citations'].append({'document_id': citation.document_id, 'quote': citation.quote,
                                        'char_start': citation.char_start, 'char_end': citation.char_end})
                if citation.document_id == doc.id and signal.status in ('cancelled', 'conflicting'):
                    blocked = True
            refs = list(by_signal.values())
            payload = {'document': {'id': doc.id, 'doc_key': doc.doc_key, 'version': doc.version,
                'origin': doc.origin, 'integration': doc.integration, 'plan_status': doc.plan_status,
                'content_hash': doc.content_hash, 'superseded_by_document_id': doc.superseded_by_document_id},
                'signal_refs': refs, 'status': 'informal' if blocked else 'current'}
            if len(doc.project_tags or []) == 1:
                payload['project_id'] = doc.project_tags[0]
            if len(doc.person_tags or []) == 1:
                payload['person_id'] = doc.person_tags[0]
            source_id = 'native:document:' + key
            previous = connection.execute("""SELECT * FROM forecast_inputs WHERE tenant_id='northstar'
                AND kind='evidence' AND source_id=? ORDER BY available_at DESC,received_at DESC,rowid DESC LIMIT 1""",
                (source_id,)).fetchone()
            old = json.loads(previous['payload']) if previous is not None else None
            content = {'source': 'native_document', 'source_id': source_id, 'text': doc.content,
                       'occurred_at': iso(doc.authored_at), 'payload': payload,
                       'is_synthetic': bool(doc.is_simulated)}
            if old is not None:
                comparable = {k: v for k, v in old['envelope'].items() if k not in ('revision', 'available_at')}
                comparable['payload'].pop('supersedes', None)
                if comparable == content:
                    continue
                if old.get('drivers'):
                    payload['supersedes'] = old['drivers'][0]['id']
            envelope = dict(content, revision=int(previous['revision']) + 1 if previous else 1,
                            available_at=iso(now))
            if snapshot is None:
                snapshot = _snapshot(session, now)
            drivers = extract_event(envelope, snapshot)
            from .service import ForecastService
            ForecastService.validate_drivers(drivers)
            store._append_input(connection, 'evidence', source_id, envelope['revision'],
                                {'envelope': envelope, 'drivers': drivers}, now, now, 'northstar')
    finally:
        connection.row_factory = old_factory


def capture_signal_documents(session, signal, *, now):
    session.flush()
    documents = [session.get(CorpusDocument, c.document_id) for c in signal.citations]
    capture_native_documents(session, documents, now=now)
