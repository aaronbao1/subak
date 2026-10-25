"""Boundary regressions discovered by the architecture integration audit."""
from datetime import datetime, timezone
from copy import deepcopy

from fastapi.testclient import TestClient
import pytest

from app.config import Settings
from app.core.clock import FrozenClock, SequentialIdFactory
from app.main import create_app
from app.seed.northstar import seed


def _published_app(tmp_path):
    clock = FrozenClock(datetime(2026, 10, 24, 12, tzinfo=timezone.utc))
    app = create_app(Settings(db_path=tmp_path / 'audit.db', forecast_provider='engine',
                              forecast_demo=True, forecast_worker=False),
                     clock=clock, id_factory=SequentialIdFactory())
    with app.state.session_factory() as session:
        seed(session, clock=clock, ids=app.state.id_factory)
    service = app.state.forecast_service
    job = service.refresh('audit-publication', scheduled_for='2026-10-19T00:00:00Z')
    assert app.state.forecast_worker.process_one()
    assert service.store.get_job(job['id'])['status'] == 'succeeded'
    return app, job


def test_current_actuals_have_a_content_revision_independent_of_read_time_and_publication(tmp_path):
    app, job = _published_app(tmp_path)
    service = app.state.forecast_service
    snapshot = service.current_snapshot()
    service.snapshot_factory = lambda **kwargs: deepcopy(snapshot)
    original = deepcopy(service.store.get_run(job['run_id'])['bundle'])
    before = service.current_actuals()
    app.state.clock.advance(minutes=1)
    reread = service.current_actuals()
    assert reread['as_of'] != before['as_of']
    assert reread['revision'] == before['revision']
    snapshot['observations'][0]['quantity'] += 1
    corrected = service.current_actuals()
    assert corrected['revision'] != before['revision']
    assert service.store.get_run(job['run_id'])['bundle'] == original


def test_legacy_issued_quarter_survives_unavailable_current_actuals(tmp_path):
    app, job = _published_app(tmp_path)
    with TestClient(app) as client:
        baseline = client.get('/api/forecasts').json()
        assert baseline['forecast_run_id'] == job['run_id']
        assert baseline['projections']

        def unavailable_repository(**kwargs):
            raise RuntimeError('current actuals temporarily unavailable')

        app.state.forecast_service.snapshot_factory = unavailable_repository
        result = client.get('/api/forecasts').json()
        assert result['forecast_run_id'] == job['run_id'], result
        assert result['projections'] == baseline['projections']


@pytest.mark.parametrize('new_received,old_received', [
    ('2026-10-23T00:00:00Z', '2026-10-24T12:00:00Z'),
    ('2026-10-24T11:30:00Z', '2026-10-24T11:00:00Z'),
])
def test_superseded_delayed_input_keeps_current_finance_proposal(tmp_path, new_received, old_received):
    from budget_helpers import ANALYST, draft, transfer_body
    from app.services.forecast_freshness import stale_forecast_refs

    app, _ = _published_app(tmp_path)
    service = app.state.forecast_service
    service.store.append_input('evidence', 'audit-source', '2', {'drivers': []},
                               available_at='2026-10-23T00:00:00Z', received_at=new_received)
    job = service.refresh('with-newest-evidence')
    assert app.state.forecast_worker.process_one()
    with TestClient(app) as client:
        receipt = client.post('/api/forecasts/snapshots', headers=ANALYST).json()
        refs = [{'kind': 'forecast_snapshot', 'id': receipt['id']}]
        response = draft(client, transfer_body(evidence_refs=refs))
        assert response.status_code == 201, response.text
        pid = response.json()['id']

        # This arrives later but was available before the revision already used.
        # Latest input selection correctly retains revision 2.
        service.store.append_input('evidence', 'audit-source', '1', {'drivers': []},
                                   available_at='2026-10-22T00:00:00Z', received_at=old_received)
        with app.state.session_factory() as session:
            assert stale_forecast_refs(session, refs, app.state.clock.now()) == []
        assert client.get('/api/proposals/' + pid).json()['status'] == 'pending_review'


def test_canonical_issued_views_survive_unavailable_current_actuals(tmp_path):
    app, job = _published_app(tmp_path)
    with TestClient(app, raise_server_exceptions=False) as client:
        baseline = client.get('/api/forecast-views').json()
        assert baseline['run_id'] == job['run_id']
        assert baseline['views']

        def unavailable_repository(**kwargs):
            raise RuntimeError('current actuals temporarily unavailable')

        app.state.forecast_service.snapshot_factory = unavailable_repository
        response = client.get('/api/forecast-views')
        assert response.status_code == 200, response.text
        result = response.json()
        assert result['views'] == baseline['views']
        assert result['publication'] == baseline['publication']
        assert result['current_actuals']['status'] == 'unavailable'
        assert result['current_actuals']['reason']
        assert 'observations' not in result['current_actuals']


@pytest.mark.parametrize('source_id,available_at,received_at', [
    ('audit-source', '2026-10-24T11:00:00Z', '2026-10-24T12:00:00Z'),
    ('audit-source', '2026-10-23T00:00:00Z', '2026-10-24T12:00:00Z'),
    ('audit-source', '2026-10-23T00:00:00Z', '2026-10-23T00:00:00Z'),
    ('other-source', '2026-10-22T00:00:00Z', '2026-10-24T12:00:00Z'),
])
def test_new_current_input_still_invalidates_finance_proposal(tmp_path, source_id, available_at, received_at):
    from budget_helpers import ANALYST, draft, transfer_body
    from app.services.forecast_freshness import stale_forecast_refs

    app, _ = _published_app(tmp_path)
    service = app.state.forecast_service
    service.store.append_input('evidence', 'audit-source', '2', {'drivers': []},
                               available_at='2026-10-23T00:00:00Z', received_at='2026-10-23T00:00:00Z')
    service.refresh('with-newest-evidence')
    assert app.state.forecast_worker.process_one()
    with TestClient(app) as client:
        receipt = client.post('/api/forecasts/snapshots', headers=ANALYST).json()
        refs = [{'kind': 'forecast_snapshot', 'id': receipt['id']}]
        response = draft(client, transfer_body(evidence_refs=refs))
        assert response.status_code == 201, response.text
        pid = response.json()['id']
        service.store.append_input('evidence', source_id, '3', {'drivers': []},
                                   available_at=available_at, received_at=received_at)
        with app.state.session_factory() as session:
            assert stale_forecast_refs(session, refs, app.state.clock.now()) == [receipt['id']]
        retired = client.get('/api/proposals/' + pid).json()
        assert retired['status'] == 'stale'
        assert datetime.fromisoformat(retired['updated_at'].replace('Z', '+00:00')) == app.state.clock.now()


@pytest.mark.parametrize('old_cutoff', ['2026-10-19T00:00:00Z', '2026-10-24T00:00:00Z'])
def test_overtaken_refresh_is_issued_without_claiming_publication(tmp_path, old_cutoff):
    from app.forecasting.persistence import ForecastStore

    store = ForecastStore(tmp_path / 'publication.db')
    for snapshot_id, cutoff in [('old', old_cutoff), ('new', '2026-10-24T00:00:00Z')]:
        store.save_snapshot({'id': snapshot_id, 'tenant_id': 'northstar', 'information_cutoff': cutoff})
        store.enqueue('northstar', snapshot_id, snapshot_id, '2026-10-24T12:00:00Z')
    old = store.claim('old-worker', '2026-10-24T12:00:00Z')
    new = store.claim('new-worker', '2026-10-24T12:00:00Z')
    assert store.complete(new['id'], new['lease_token'], {'views': [{}]}, '2026-10-24T12:00:01Z')
    assert store.complete(old['id'], old['lease_token'], {'views': [{}]}, '2026-10-24T12:00:02Z')
    assert store.publication()['run_id'] == new['run_id']
    published = store.get_run(new['run_id'])['bundle']['views'][0]['publication']
    assert published['published_at'] == '2026-10-24T12:00:01.000000Z'
    receipt = store.get_run(old['run_id'])['bundle']['views'][0]['publication']
    assert receipt['issued_at'] == '2026-10-24T12:00:02.000000Z'
    assert receipt.get('published_at') is None


def test_scenario_never_claims_issuance_or_publication(tmp_path):
    app, parent = _published_app(tmp_path)
    service = app.state.forecast_service
    publication = service.store.publication()
    scenario = service.scenario(parent['run_id'], [])
    assert scenario['status'] == 'succeeded'
    assert scenario['views']
    assert service.store.publication() == publication
    for view in scenario['views']:
        assert view['publication'].get('issued_at') is None
        assert view['publication'].get('published_at') is None


def test_future_available_input_is_not_material_until_known(tmp_path):
    from budget_helpers import ANALYST, decide, draft, transfer_body
    from app.services.forecast_freshness import stale_forecast_refs

    app, _ = _published_app(tmp_path)
    app.state.forecast_service.refresh('current-before-future-source')
    assert app.state.forecast_worker.process_one()
    with TestClient(app) as client:
        receipt = client.post('/api/forecasts/snapshots', headers=ANALYST).json()
        refs = [{'kind': 'forecast_snapshot', 'id': receipt['id']}]
        response = draft(client, transfer_body(evidence_refs=refs))
        assert response.status_code == 201, response.text
        pid = response.json()['id']
        app.state.forecast_service.store.append_input('evidence', 'future-source', '1', {'drivers': []},
            available_at='2026-10-25T00:00:00Z', received_at='2026-10-24T12:00:00Z')
        with app.state.session_factory() as session:
            assert stale_forecast_refs(session, refs, app.state.clock.now()) == []
        assert client.get('/api/proposals/' + pid).json()['status'] == 'pending_review'
        app.state.clock.advance(days=1)
        with app.state.session_factory() as session:
            assert stale_forecast_refs(session, refs, app.state.clock.now()) == [receipt['id']]
        assert decide(client, pid).status_code == 409
