"""Weekly reads slice immutable evidence without changing prospective comparisons."""
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.forecasting.persistence import ForecastStore
from app.forecasting.weekly_history import weekly_history
from test_weekly_history import target, truth, START, END, NOW


@pytest.fixture
def store(tmp_path):
    return ForecastStore(tmp_path / 'weekly.db')


def publish(store, key, *, at='2026-10-18T00:00:00Z'):
    store.save_snapshot({'id': key, 'tenant_id': 'northstar', 'information_cutoff': at})
    job = store.enqueue('northstar', key, key, at)
    claim = store.claim('worker', at, job_id=job['id'])
    t = target(id=key, run=job['run_id'], issued=at)
    view = {'scope': {'type': 'company', 'id': 'northstar'}, 'run_id': job['run_id'],
            'target': {'unit': 'USD', 'basis': 'planning', 'quantity': 'spend', 'timezone': 'UTC'},
            'weekly': [{'start': '2026-10-19', 'end': '2026-10-26', 'base': 101.23456789012345}]}
    store.complete(job['id'], claim['lease_token'], {'views': [view], 'unused': 'large archive'}, at,
                   issued_targets=[t])
    return t


class LegacyStore:
    def __init__(self, store): self.store = store
    def __getattr__(self, key):
        if key.startswith('weekly_'): raise AttributeError(key)
        return getattr(self.store, key)


def service(store):
    def views(**kwargs):
        publication = store.publication()
        return store.get_run(publication['run_id'])['bundle'] if publication else {'views': []}
    return SimpleNamespace(store=store, now=lambda: NOW, views=views)


def test_scoped_query_decodes_only_requested_targets_but_retains_global_truth_revision(store):
    t = publish(store, 'one')
    other = {**target(id='other'), 'scope_type': 'team', 'scope_id': 'research', 'is_synthetic': True}
    store.append_input('issued_targets', 'other', 1, other, available_at=t['issued_at'])
    for revision, status in [(1, 'mature'), (2, 'disputed')]:
        store.append_input('truth_revisions', t['target_id'], revision, truth(t, revision, status), available_at=NOW)
    store.append_input('truth_revisions', 'other', 1, truth(other), available_at=NOW)
    with patch.object(store, '_input', wraps=store._input) as decode:
        sliced = store.weekly_history_inputs(NOW, 'northstar', scope_type='company', scope_id='northstar')
    assert [r['payload']['target_id'] for r in sliced['records'] if r['kind'] == 'issued_targets'] == ['one']
    assert len([r for r in sliced['records'] if r['kind'] == 'truth_revisions']) == 3
    assert decode.call_count == 4
    assert sliced['synthetic'] is True


@pytest.mark.parametrize('synthetic', [False, True, None, 0, 1, '', '\0', 'false', [], [0], {}, {'a': False}])
def test_synthetic_scalar_preserves_python_truthiness_for_other_scopes(store, synthetic):
    other = {**target(id='other'), 'scope_type': 'team', 'scope_id': 'elsewhere', 'is_synthetic': synthetic}
    store.append_input('issued_targets', 'other', 1, other, available_at='2026-10-18T00:00:00Z')
    assert store.weekly_history_inputs(NOW, scope_type='company', scope_id='northstar')['synthetic'] is bool(synthetic)


def test_optimized_weekly_wire_equals_legacy_including_global_revision_and_withdrawal(store):
    t = publish(store, 'one')
    publish(store, 'late', at='2026-10-20T00:00:00Z')
    other = {**target(id='other'), 'scope_type': 'person', 'scope_id': 'somebody'}
    store.append_input('issued_targets', 'other', 1, other, available_at=t['issued_at'])
    for revision, status in [(1, 'mature'), (2, 'disputed')]:
        store.append_input('truth_revisions', t['target_id'], revision, truth(t, revision, status), available_at=NOW)
    store.append_input('truth_revisions', 'other', 1, truth(other), available_at=NOW)
    ledger = {'buckets': [], 'dataset_revision': 'same', 'synthetic': False}
    expected = weekly_history(service(LegacyStore(store)), ledger, start_date=START, end_date_exclusive=END)
    with patch.object(store, 'get_run', side_effect=AssertionError('full run decoded')), \
         patch.object(store, 'get_job', side_effect=AssertionError('full job decoded')), \
         patch.object(store, 'input_records', side_effect=AssertionError('unfiltered inputs decoded')):
        actual = weekly_history(service(store), ledger, start_date=START, end_date_exclusive=END)
    assert actual == expected
    assert actual['weeks'][0]['actual']['status'] == 'disputed'


def test_publication_metadata_is_exact_run_scope_and_has_no_shadow_fallback(store):
    t = publish(store, 'one')
    values = store.weekly_publication_metadata([t['run_id'], t['run_id'] + ':shadow', 'missing'], 'company', 'northstar')
    assert list(values) == [t['run_id']]
    assert values[t['run_id']]['published_at'].startswith('2026-10-18T00:00:00')
    assert values[t['run_id']]['sequence'] == 1
    assert store.weekly_publication_metadata([t['run_id']], 'team', 'northstar') == {}
