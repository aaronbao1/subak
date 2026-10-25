"""Compact reads retain the exact immutable quarter and ownership contract."""
from copy import deepcopy

import pytest

from app.forecasting.persistence import encode
from app.providers.engine import EngineForecastProvider
from budget_helpers import seed_budget


def _publish(app, *, synthetic=True, ownership=None):
    seed_budget(app)
    store = app.state.forecast_service.store
    now = app.state.clock.now().isoformat()
    snapshot = {'id': 'snapshot_compact', 'tenant_id': 'northstar', 'information_cutoff': now,
                'observations': ownership or [{'person_id': 'maya', 'team_id': 'research', 'date': '2026-10-02',
                                               'unused_payload': 'x' * 200_000}],
                'memberships': [{'person_id': 'maya', 'team_id': 'research'}],
                'source_revisions': [{'kind': 'observations', 'id': 'source-a'},
                                     {'kind': 'observations', 'id': 'source-a'},
                                     {'kind': 'observations'}, {'kind': 'issued_targets', 'id': 'ignored'}],
                'issued_targets': [{'unused_payload': 'x' * 200_000}]}
    if synthetic != 'missing':
        snapshot['is_synthetic'] = synthetic
    store.save_snapshot(snapshot)
    job = store.enqueue('northstar', 'compact', snapshot['id'], now)
    claimed = store.claim('test', now)
    quarter = {'start': '2026-10-01', 'end': '2027-01-01', 'complete': True,
               'base': 0.10499999999999998, 'recorded': 0.004999999999999999,
               'assumptions': ['Issued numeric values retain their original rounding.']}
    bundle = {'run_id': job['run_id'], 'procedure_version': 'test-quarter', 'views': [
        {'scope': {'type': 'team', 'id': 'research'}, 'quarter_outlook': quarter,
         'daily': [{'unused_payload': 'x' * 200_000}]},
        {'scope': {'type': 'person', 'id': 'maya'}, 'quarter_outlook': deepcopy(quarter)}],
        'calculations': [{'unused_payload': 'x' * 200_000}]}
    assert store.complete(job['id'], claimed['lease_token'], bundle, now)
    provider = EngineForecastProvider(app.state.forecast_service, app.state.session_factory)
    return store, provider, job['run_id']


@pytest.mark.parametrize('synthetic,expected_kind', [(True, 'simulated'), (False, 'estimated'),
                                                   (None, 'estimated'), ('missing', 'simulated')])
def test_compact_provider_matches_full_inputs_without_full_reads(app, monkeypatch, synthetic, expected_kind):
    store, provider, run_id = _publish(app, synthetic=synthetic)
    # Independent full-payload source: feed the same provider the original frozen
    # objects, then compare every result field against the SQL projection.
    full_run = store.get_run(run_id)
    full_snapshot = store.get_snapshot(full_run['snapshot_id'])
    compact = getattr(store, 'get_issued_quarter_inputs', None)
    assert compact is not None, 'the provider needs a compact immutable read boundary'
    monkeypatch.setattr(store, 'get_issued_quarter_inputs', lambda _: (deepcopy(full_run), deepcopy(full_snapshot)))
    expected = provider.get_forecast('2026-P1', ['research']).model_dump(mode='json')
    monkeypatch.setattr(store, 'get_issued_quarter_inputs', compact)
    def forbidden(*args, **kwargs):
        pytest.fail('native quarter reads must not decode full runs, snapshots or service views')
    monkeypatch.setattr(store, 'get_run', forbidden)
    monkeypatch.setattr(store, 'get_snapshot', forbidden)
    monkeypatch.setattr(provider.service, 'views', forbidden)
    actual = provider.get_forecast('2026-P1', ['research']).model_dump(mode='json')
    assert actual == expected
    assert actual['value_kind'] == expected_kind
    assert actual['projections'][0]['amount'] == '0.10'
    assert actual['person_projections'][0]['spent_to_date'] == '0.00'
    run, snapshot = compact(run_id)
    assert len(encode(run)) < 5000 and len(encode(snapshot)) < 2000
    assert 'id' not in snapshot['source_revisions'][2]
    assert 'effective_from' not in snapshot['memberships'][0]


def test_compact_provider_keeps_other_team_ownership_and_half_open_boundaries(app):
    ownership = [{'person_id': 'maya', 'team_id': 'research', 'date': '2026-10-01'},
                 {'person_id': 'maya', 'team_id': 'product', 'date': '2026-12-31'},
                 {'person_id': 'maya', 'team_id': 'engineering', 'date': '2027-01-01'}]
    _, provider, _ = _publish(app, ownership=ownership)
    result = provider.get_forecast('2026-P1', ['research'])
    assert result.projections and not result.person_projections
