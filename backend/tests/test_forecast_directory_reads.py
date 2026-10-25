"""Directory reads retain current membership without decoding forecast archives."""
from copy import deepcopy
from datetime import datetime, timezone
from unittest.mock import patch

from app.core.clock import FrozenClock
from app.forecasting.demo import create_demo_app
from app.forecasting.directory import snapshot_people
from app.forecasting.persistence import ForecastStore
from app.forecasting.service import ForecastService
from app.services.people import list_people, person_out


NOW = '2026-10-26T00:00:00Z'
LEARNING = ('issued_targets', 'truth_revisions', 'forecast_errors')


def add(store, kind, payload, revision='1', *, received=NOW):
    return store.append_input(kind, kind, revision, payload, available_at=NOW, received_at=received)


def test_excluded_learning_payloads_are_not_decoded_before_latest_selection(tmp_path):
    store = ForecastStore(tmp_path / 'inputs.db')
    add(store, 'memberships', [{'revision': 1}])
    add(store, 'memberships', [{'revision': 2}], '2')
    add(store, 'memberships', [{'revision': 3}], '3', received='2026-10-27T00:00:00Z')
    for kind in LEARNING:
        add(store, kind, {'large_archive': 'x' * 100_000})
    with patch.object(store, '_input', wraps=store._input) as decode:
        records = store.input_records(NOW, latest=True, exclude_kinds=LEARNING)
    assert [(row['kind'], row['revision']) for row in records] == [('memberships', '2')]
    assert decode.call_count == 1


def test_light_snapshot_preserves_material_inputs_cutoff_and_full_default(tmp_path):
    calls = []
    def factory(*, now, tenant_id, as_of):
        calls.append((now, tenant_id, as_of))
        return {'people': [], 'memberships': [], 'teams': [], 'source_revisions': [],
                'issued_targets': [{'factory_archive': True}], 'custom_material': [{'keep': True}]}
    factory.supports_as_of = True
    store = ForecastStore(tmp_path / 'inputs.db')
    for kind in LEARNING:
        add(store, kind, {'revision': 1})
        add(store, kind, {'revision': 2}, '2')
    add(store, 'memberships', [{'person_id': 'maya', 'team_id': 'research', 'effective_from': '2026-10-01'}])
    add(store, 'memberships', [{'person_id': 'maya', 'team_id': 'product', 'effective_from': '2026-10-26'}], '2')
    add(store, 'memberships', [{'person_id': 'maya', 'team_id': 'engineering', 'effective_from': '2026-10-26'}],
        '3', received='2026-10-27T00:00:00Z')
    service = ForecastService(store, snapshot_factory=factory, now=lambda: NOW)
    full = service.current_snapshot(cutoff=NOW)
    with patch.object(store, '_input', wraps=store._input) as decode:
        light = service.current_snapshot(cutoff=NOW, include_learning=False)
    assert decode.call_count == 1
    assert calls[-1] == calls[-2]
    ignored = {*LEARNING, 'source_revisions', 'id'}
    assert {k: v for k, v in full.items() if k not in ignored} == {k: v for k, v in light.items() if k not in ignored}
    assert light['memberships'][0]['team_id'] == 'product'
    assert not any(kind in light for kind in LEARNING)
    assert all(row['kind'] not in LEARNING for row in light['source_revisions'])
    assert service.current_snapshot(cutoff=NOW) == full
    assert all(len(full[kind]) == 2 for kind in LEARNING)


def test_demo_directory_uses_current_material_membership_without_learning_decode(tmp_path):
    clock = FrozenClock(datetime(2026, 10, 26, tzinfo=timezone.utc))
    app = create_demo_app(tmp_path, clock)
    service = app.state.forecast_service
    memberships = deepcopy(service.current_snapshot()['memberships'])
    for row in memberships:
        if row['person_id'] == 'maya': row['team_id'] = 'product'
    add(service.store, 'memberships', memberships)
    for kind in LEARNING:
        add(service.store, kind, {'large_archive': 'x' * 100_000})
    expected = sorted([person_out(p) for p in snapshot_people(service.current_snapshot())], key=lambda p: p['id'])
    original = service.store._input
    def decode(row):
        assert row['kind'] not in LEARNING, 'directory read decoded unrelated learning history'
        return original(row)
    with patch.object(service.store, '_input', side_effect=decode):
        with app.state.session_factory() as session:
            actual = sorted([person_out(p) for p in list_people(session)], key=lambda p: p['id'])
    assert actual == expected
    assert next(p for p in actual if p['id'] == 'maya')['team'] == 'product'
    app.state.engine.dispose()
