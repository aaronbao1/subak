from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.forecasting.routes import router
from app.forecasting.persistence import ForecastStore
from app.forecasting.service import ForecastService
from app.forecasting.worker import ForecastWorker


def test_refresh_routes_require_idempotency_and_expose_frozen_explanation(tmp_path):
    def fixture(*, now, tenant_id):
        return {'id': 'base', 'tenant_id': tenant_id, 'information_cutoff': now, 'forecast_start': '2026-10-26', 'history_complete_through': '2026-10-25'}
    def build(snapshot, *, run_id, generated_at, drivers=None):
        return {'run_id': run_id, 'views': [], 'calculations': [{'id':'calc1'}]}
    svc = ForecastService(ForecastStore(tmp_path/'f.db'), snapshot_factory=fixture, builder=build, now=lambda:'2026-10-26T00:00:00Z')
    app = FastAPI()
    app.state.forecast_service = svc
    app.include_router(router)
    with TestClient(app) as client:
        assert client.post('/api/forecast-refreshes').status_code == 422
        first = client.post('/api/forecast-refreshes', headers={'Idempotency-Key':'click'})
        assert first.status_code == 202
        job = first.json()
        assert client.post('/api/forecast-refreshes', headers={'Idempotency-Key':'click'}).json()['id'] == job['id']
        assert client.get('/api/forecast-refreshes/'+job['id']).json()['status'] == 'queued'
        claim = svc.store.claim('test-worker','2026-10-26T00:00:00Z',lease_seconds=0)
        duplicate = client.post('/api/forecast-refreshes', headers={'Idempotency-Key':'click'}).json()
        assert 'lease_token' not in duplicate
        assert 'lease_owner' not in duplicate
        ForecastWorker(svc).process_one()
        assert client.get('/api/forecast-refreshes/'+job['id']).json()['status'] == 'succeeded'
        assert client.get('/api/forecast-runs/'+job['run_id']+'/explanation').json()['calculations'] == [{'id':'calc1'}]
        assert client.get('/api/forecast-runs/missing/explanation').status_code == 404
        assert client.get('/api/forecast-views?scope_type=invalid').status_code == 422
        assert client.post('/api/forecast-runs/'+job['run_id']+'/scenarios', json={'drivers':[]}).status_code == 201
