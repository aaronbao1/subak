"""Optional dashboard transport retains exact points and reconstructible drivers."""
from copy import deepcopy
from importlib import import_module, util
import json


def _bundle():
    first = {'id': 'same-id', 'parameters': {'z': 0.10499999999999998, 'a': 1}, 'text': 'x' * 2000}
    changed = {**first, 'parameters': {'z': 2, 'a': 1}}
    reordered = {**first, 'parameters': {'a': 1, 'z': 0.10499999999999998}}
    return {'run_id': 'issued-run', 'calculations': [{'audit': 'kept by the full endpoint'}],
            'views': [
                {'scope': {'type': 'team', 'id': 'research'},
                 'weekly': [{'base': 0.10499999999999998, 'complete': True,
                             'new_unknown_field': {'retained': True}}],
                 'included_drivers': [first, changed, first, reordered], 'queued_changes': [changed]},
                {'scope': {'type': 'person', 'id': 'maya'}, 'included_drivers': [first], 'queued_changes': []},
                {'scope': {'type': 'shared', 'id': 'unknown'}, 'included_drivers': None}],
            'current_actuals': {'revision': 'actuals-v1', 'as_of': '2026-10-25T00:00:00Z',
                               'observations': [{'quantity': 12}], 'coverage': [], 'required_sources': ['ledger'],
                               'status': 'available', 'custom_metadata': 'preserved'},
            'other_top_level_metadata': {'preserved': True}}


def _compact(bundle):
    assert util.find_spec('app.forecasting.dashboard_transport') is not None, 'compact dashboard transport is missing'
    return import_module('app.forecasting.dashboard_transport').dashboard_transport(bundle)


def _hydrate(compact):
    result = {key: deepcopy(value) for key, value in compact.items() if key not in ('transport', 'driver_pool')}
    for view in result.get('views', []):
        for field, refs in [('included_drivers', 'included_driver_refs'), ('queued_changes', 'queued_change_refs')]:
            if refs in view:
                keys = view.pop(refs)
                view[field] = None if keys is None else [deepcopy(compact['driver_pool'][key]) for key in keys]
    return result


def test_compact_round_trip_preserves_points_driver_content_order_and_missing_values():
    original = _bundle()
    frozen = deepcopy(original)
    result = _compact(original)
    assert original == frozen
    assert result['transport'] == 'forecast-dashboard-v1'
    assert list(result['driver_pool']) == ['d0', 'd1', 'd2']
    assert result['views'][0]['included_driver_refs'] == ['d0', 'd1', 'd0', 'd2']
    assert result['views'][0]['queued_change_refs'] == ['d1']
    assert result['views'][1]['included_driver_refs'] == ['d0']
    assert result['views'][2]['included_driver_refs'] is None
    assert 'queued_change_refs' not in result['views'][2]
    expected = deepcopy(original)
    del expected['calculations']
    for key in ('observations', 'coverage', 'required_sources'):
        del expected['current_actuals'][key]
    assert _hydrate(result) == expected
    # Numeric lexemes and object insertion order must survive the actual JSON wire.
    wire = json.loads(json.dumps(result, allow_nan=False))
    hydrated = _hydrate(wire)
    assert hydrated['views'][0]['weekly'][0]['base'] == 0.10499999999999998
    assert list(hydrated['views'][0]['included_drivers'][0]['parameters']) == ['z', 'a']
    assert list(hydrated['views'][0]['included_drivers'][3]['parameters']) == ['a', 'z']
    assert len(json.dumps(result)) < len(json.dumps(original))


def test_default_native_route_stays_full_and_compact_is_opt_in(app, client, monkeypatch):
    bundle = _bundle()
    monkeypatch.setattr(app.state.forecast_service, 'views', lambda *args: deepcopy(bundle))
    plain = client.get('/api/forecast-views')
    assert plain.status_code == 200 and plain.json() == bundle
    compact = client.get('/api/forecast-views?compact=true')
    assert compact.status_code == 200
    assert compact.json().get('transport') == 'forecast-dashboard-v1'
    assert compact.json() == _compact(bundle)
    assert client.get('/api/forecast-views?compact=false').json() == bundle


def test_empty_or_unavailable_actuals_do_not_invent_content():
    for original in ({'views': []}, {'views': [], 'current_actuals': None},
                     {'views': [], 'current_actuals': {'status': 'unavailable', 'reason': 'offline'}}):
        result = _compact(original)
        assert result['driver_pool'] == {}
        assert _hydrate(result) == original
