#!/usr/bin/env python3
"""Add three source-backed, amount-free updates after final company publication.

All intake writes use the native API with a finance analyst identity. No Droid,
proposal, approval, forecast refresh, or funding operation is performed.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'backend'), str(ROOT / 'src'), str(ROOT / 'agent')]

from fastapi.testclient import TestClient
from app.core.clock import FrozenClock

UPDATES = (
    ('uber-task-0002', 'ai-labs', 'Model Adoption Program'),
    ('uber-msg-0025', 'freight', 'AI Dispatch v2'),
    ('uber-msg-0034', 'payments-risk', 'Fraud Rules Migration'),
)
ANALYST = {'X-Actor-Id': 'company-update-intake', 'X-Actor-Role': 'finance_analyst'}
PROTECTED_TABLES = (
    'budget_envelopes', 'budget_allocations', 'budget_snapshots', 'decisions',
    'decision_events', 'proposals', 'allocation_draft_submissions',
    'forecast_snapshots', 'forecast_input_snapshots', 'forecast_jobs',
    'forecast_runs', 'forecast_publications', 'forecast_scenarios',
)


def protected_state(database):
    """Read-only exact fingerprints include every native budget and forecast bundle."""
    state = {}
    with sqlite3.connect(Path(database).resolve().as_uri() + '?mode=ro', uri=True) as conn:
        for table in PROTECTED_TABLES:
            digest = hashlib.sha256()
            count = 0
            for row in conn.execute(f'SELECT * FROM {table} ORDER BY 1'):
                digest.update(json.dumps(row, separators=(',', ':'), default=str).encode())
                digest.update(b'\n')
                count += 1
            state[table] = {'rows': count, 'sha256': digest.hexdigest()}
    return state


def _get(client, path):
    response = client.get(path)
    if response.status_code != 200:
        raise RuntimeError(f'Unable to read {path}: HTTP {response.status_code}')
    return response.json()


def seed_requests(app, client):
    """Resolve all exact current sources before creating any idempotent intake rows."""
    before = protected_state(app.state.settings.db_path)
    payloads = []
    for key, team, project in UPDATES:
        chain = _get(client, f'/api/documents/by-key/{key}/versions')
        current = next((row for row in chain['versions'] if row['version'] == chain['current_version']), None)
        if current is None or not current['is_current'] or team not in current['team_tags']:
            raise ValueError(f'The current {key} source must belong to {team}.')
        doc = _get(client, '/api/documents/' + current['id'])
        payloads.append({
            'client_request_id': 'company-source-update-v1:' + key,
            'team_id': team, 'title': project + ' update', 'request_kind': 'project',
            'project_name': project, 'narrative': doc['content'], 'requested_amount': None,
            'unit': 'USD', 'period_start': '2026-10-01', 'period_end_exclusive': '2027-01-01',
            'source_ref': f"{key} v{doc['version']} · {doc['id']} · {doc['title']}",
            'evidence_refs': [{'kind': 'document', 'id': doc['id'], 'version': doc['version'],
                               'note': 'Exact source update; no funding amount was requested.'}],
        })
    requests = []
    for payload in payloads:
        response = client.post('/api/budget-requests', json=payload, headers=ANALYST)
        if response.status_code not in (200, 201):
            raise RuntimeError(f"Update intake failed for {payload['client_request_id']}: HTTP {response.status_code}")
        row = response.json()
        assert row['requested_amount'] is None and row['remaining_requested_amount'] is None
        assert row['status'] == 'submitted' and row['approved_amount'] == '0.00'
        assert not row['linked_proposal_ids'] and not row['decision_ids']
        assert row['narrative'] == payload['narrative'].strip()
        assert row['evidence_refs'][0]['id'] == payload['evidence_refs'][0]['id']
        requests.append(row)
    assert protected_state(app.state.settings.db_path) == before, 'Update intake changed protected financial state.'
    return requests


def seed(directory, source):
    # Import the fixture adapter only for this dedicated entry point. Tests can
    # exercise native intake independently of the full-company source manifest.
    sys.path.insert(0, str(ROOT / 'datagen'))
    from company_preview import FINAL, ISSUANCES, make_app

    runtime = json.loads((directory / 'runtime.json').read_text())
    clock = FrozenClock(datetime.fromisoformat(runtime['clock'].replace('Z', '+00:00')))
    if runtime.get('published_vintages') != len(ISSUANCES) or clock.now() != FINAL:
        raise ValueError('Wait for the complete final company publication before seeding updates.')
    if Path(runtime['source_directory']).resolve() != source.resolve():
        raise ValueError('Source directory must match the prepared company runtime.')
    database = directory / 'app.db'
    before = protected_state(database)
    app = make_app(directory, source, clock, worker=False)
    try:
        with TestClient(app) as client:
            requests = seed_requests(app, client)
        after = protected_state(database)
        assert after == before, 'Seeder changed budgets, decisions, proposals, or saved forecasts.'
        report = {'clock': runtime['clock'], 'live_request_performed': False,
                  'request_count': len(requests), 'requests': requests,
                  'protected_state_before': before, 'protected_state_after': after,
                  'protected_state_unchanged': True}
        (directory / 'source-update-requests.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
        return report
    finally:
        app.state.engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', required=True, type=Path)
    parser.add_argument('--source', required=True, type=Path)
    args = parser.parse_args()
    report = seed(args.directory, args.source)
    print(json.dumps({key: report[key] for key in ('request_count', 'clock', 'protected_state_unchanged',
                                                 'live_request_performed')}, indent=2))


if __name__ == '__main__':
    main()
