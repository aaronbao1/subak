"""Finance dependencies are checked under the same SQLite write lock as approval.

Evidence arrival can retire a draft while the issued curve remains immutable. Stored
forecast receipts bind input record identities, so stale publications cannot create a
fresh-looking proposal after the ingestion transaction has already completed.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json

from sqlalchemy import text

NON_MATERIAL = frozenset({'issued_targets', 'truth_revisions', 'forecast_errors', 'model_registry', 'promotion_decisions'})


def revision_from_snapshot(snapshot: dict) -> str:
    ids = sorted(r['id'] for r in snapshot.get('source_revisions', []) if r['kind'] not in NON_MATERIAL and 'id' in r)
    return hashlib.sha256(json.dumps(ids, separators=(',', ':')).encode()).hexdigest()


def current_revision(session, tenant_id: str, now) -> str:
    rows = session.execute(text('''SELECT id,kind,source_id,available_at,received_at FROM forecast_inputs
        WHERE tenant_id=:tenant ORDER BY available_at,received_at,rowid'''), {'tenant': tenant_id}).mappings()
    latest = {}
    for row in rows:
        if row['kind'] in NON_MATERIAL:
            continue
        # Future source availability is not known evidence yet. Datetime comparison
        # avoids mismatched ISO precision ('...00Z' versus '...00.000000Z').
        available = datetime.fromisoformat(row['available_at'].replace('Z', '+00:00'))
        received = datetime.fromisoformat(row['received_at'].replace('Z', '+00:00'))
        if max(available, received) <= now:
            latest[row['kind'], row['source_id']] = row['id']
    return hashlib.sha256(json.dumps(sorted(latest.values()), separators=(',', ':')).encode()).hexdigest()


def stale_forecast_refs(session, refs: list[dict], now) -> list[str]:
    from app.db.models import ForecastSnapshot
    stale = []
    for ref in refs:
        if ref.get('kind') != 'forecast_snapshot':
            continue
        receipt = session.get(ForecastSnapshot, ref['id'])
        payload = receipt.payload if receipt else {}
        revision = payload.get('input_revision')
        changed = bool(revision and revision != current_revision(session, payload.get('tenant_id') or 'northstar', now))
        if payload.get('repository_revision'):
            from app.forecasting.repository import repository_revision
            changed = changed or payload['repository_revision'] != repository_revision(session, now)
        if changed:
            stale.append(ref['id'])
    return stale


def invalidate_dependent_proposals(conn, record: dict, *, now=None) -> None:
    """Called inside append_input's BEGIN IMMEDIATE, before evidence is committed."""
    if record['kind'] in NON_MATERIAL:
        return
    from app.forecasting.persistence import iso
    cutoff = iso(now or datetime.now(timezone.utc))
    if max(record['available_at'], record['received_at']) > cutoff:
        return
    # A delayed older revision is archived but does not replace the state used
    # by current_snapshot/current_revision. Keep the invalidation decision under
    # this same write lock at actual completion time. Interpretation retries keep
    # their original receipt times even when a newer job has already completed.
    latest = conn.execute('''SELECT id,available_at,received_at FROM forecast_inputs
        WHERE tenant_id=? AND kind=? AND source_id=? AND available_at<=? AND received_at<=?
        ORDER BY available_at DESC,received_at DESC,rowid DESC LIMIT 1''',
        (record['tenant_id'], record['kind'], record['source_id'], cutoff, cutoff)).fetchone()
    if latest and latest['id'] != record['id']:
        return
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='proposals'").fetchone():
        return
    snapshots = {r['id']: json.loads(r['payload']) for r in conn.execute(
        'SELECT id,payload FROM forecast_snapshots')}
    for proposal in conn.execute("SELECT id,evidence_refs,warnings FROM proposals WHERE status='pending_review'").fetchall():
        refs = json.loads(proposal['evidence_refs'])
        bound = [snapshots.get(r.get('id'), {}) for r in refs if r.get('kind') == 'forecast_snapshot']
        if not any(p.get('input_snapshot_id') and p.get('tenant_id', 'northstar') == record['tenant_id'] for p in bound):
            continue
        warnings = json.loads(proposal['warnings'])
        warnings.append({'code': 'forecast_evidence_changed', 'message': 'New forecast evidence requires a new forecast and proposal review.', 'input_id': record['id']})
        at = datetime.fromisoformat(cutoff.replace('Z', '+00:00')).replace(tzinfo=None).isoformat(sep=' ')
        conn.execute("UPDATE proposals SET status='stale',warnings=?,updated_at=? WHERE id=? AND status='pending_review'",
                     (json.dumps(warnings), at, proposal['id']))


def invalidate_repository_proposals(session, *, source_id, now):
    """Retire bound drafts inside the successful import/mapping transaction."""
    from app.db.models import Proposal, ForecastSnapshot
    for proposal in session.query(Proposal).filter(Proposal.status == 'pending_review'):
        refs = [r for r in proposal.evidence_refs if r.get('kind') == 'forecast_snapshot']
        if not any((receipt := session.get(ForecastSnapshot, r['id'])) is not None
                   and receipt.payload.get('repository_revision') for r in refs):
            continue
        proposal.status = 'stale'
        proposal.updated_at = now
        proposal.warnings = [*proposal.warnings, {'code': 'forecast_evidence_changed',
            'message': f'Repository source {source_id} changed; publish and review a new forecast.'}]
