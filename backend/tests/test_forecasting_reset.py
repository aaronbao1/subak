"""Guarded demo reset clears every old forecast identity, including live-worker races."""
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from threading import Event

from fastapi.testclient import TestClient
import pytest

from app.config import Settings
from app.main import create_app
from app.forecasting.fixtures import northstar_evidence


def test_enabled_reset_clears_old_canonical_records_and_reseeds(tmp_path, clock, id_factory):
    app=create_app(Settings(db_path=tmp_path/'reset.db',allow_reset=True,forecast_worker=False,forecast_demo=True),clock=clock,id_factory=id_factory)
    with TestClient(app) as client:
        svc=app.state.forecast_service
        job=svc.refresh('old');app.state.forecast_worker.process_one()
        evidence=svc.ingest_evidence(northstar_evidence()[0])
        scenario=svc.scenario(job['run_id'],[])
        assert svc.store.publication() is not None
        old_input_ids={r['id'] for r in svc.store.input_records(svc.now())}
        assert client.post('/api/admin/reset').status_code==200
        assert svc.store.publication() is None
        assert not old_input_ids.intersection(r['id'] for r in svc.store.input_records(svc.now()))
        assert not any(r['kind']!='repository_state' for r in svc.store.input_records(svc.now()))
        assert svc.store.list_jobs()==[]
        for method,arg in [(svc.store.get_run,job['run_id']),(svc.store.get_job,evidence['interpretation_job_id']),(svc.store.get_scenario,scenario['scenario_id'])]:
            with pytest.raises(KeyError):method(arg)
        assert client.get('/api/spend/summary').json()['company_total']=='95000.00'
        fresh=svc.refresh('old')
        assert fresh['id']!=job['id']
        app.state.forecast_worker.process_one()
        assert svc.store.get_job(fresh['id'])['status']=='succeeded'


def test_disabled_reset_preserves_existing_canonical_publication(tmp_path, clock):
    app=create_app(Settings(db_path=tmp_path/'guard.db',forecast_worker=False,forecast_demo=True),clock=clock)
    with TestClient(app) as client:
        svc=app.state.forecast_service
        job=svc.refresh('keep');app.state.forecast_worker.process_one()
        assert client.post('/api/admin/reset').status_code==403
        assert svc.store.publication()['run_id']==job['run_id']


def test_reset_waits_for_active_worker_and_cannot_restore_old_result(tmp_path, clock):
    app=create_app(Settings(db_path=tmp_path/'race.db',allow_reset=True,forecast_worker=False,forecast_demo=True),clock=clock)
    with TestClient(app) as client:
        svc=app.state.forecast_service
        actual=svc.builder;entered=Event();release=Event()
        def blocked(*args,**kwargs):
            entered.set()
            assert release.wait(5)
            return actual(*args,**kwargs)
        svc.builder=blocked
        job=svc.refresh('inflight')
        with ThreadPoolExecutor(max_workers=2) as pool:
            computing=pool.submit(app.state.forecast_worker.process_one)
            assert entered.wait(5)
            resetting=pool.submit(client.post,'/api/admin/reset')
            try:
                with pytest.raises(TimeoutError):resetting.result(timeout=.05)
            finally:
                release.set()
            assert computing.result(timeout=5)
            assert resetting.result(timeout=5).status_code==200
        assert svc.store.publication() is None
        with pytest.raises(KeyError):svc.store.get_job(job['id'])


def test_reset_seed_failure_rolls_back_canonical_and_legacy_data(tmp_path, clock, monkeypatch):
    import app.seed.northstar as seed_module
    app=create_app(Settings(db_path=tmp_path/'rollback.db',allow_reset=True,forecast_worker=False,forecast_demo=True),clock=clock)
    with TestClient(app) as client:
        assert client.post('/api/admin/reset').status_code==200
        svc=app.state.forecast_service
        job=svc.refresh('preserve-on-error');app.state.forecast_worker.process_one()
        original=svc.store.get_run(job['run_id'])
        def fail_seed(*args,**kwargs):
            raise RuntimeError('injected reseed failure')
        monkeypatch.setattr(seed_module,'seed',fail_seed)
        with pytest.raises(RuntimeError,match='injected reseed failure'):
            client.post('/api/admin/reset')
        assert svc.store.get_run(job['run_id'])==original
        assert svc.store.publication()['run_id']==job['run_id']
        assert client.get('/api/spend/summary').json()['company_total']=='95000.00'


def test_reset_respects_forecast_operation_in_another_process(tmp_path, clock):
    import subprocess
    import sys
    app=create_app(Settings(db_path=tmp_path/'process.db',allow_reset=True,forecast_worker=False),clock=clock)
    script="""import sys
from app.forecasting.persistence import ForecastStore
store=ForecastStore(sys.argv[1])
with store.operation():
    print('held',flush=True)
    sys.stdin.readline()
"""
    child=subprocess.Popen([sys.executable,'-c',script,str(app.state.settings.db_path)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
    try:
        assert child.stdout.readline().strip()=='held'
        with TestClient(app) as client,ThreadPoolExecutor(max_workers=1) as pool:
            resetting=pool.submit(client.post,'/api/admin/reset')
            try:
                with pytest.raises(TimeoutError):resetting.result(timeout=.05)
            finally:
                child.communicate('\n',timeout=5)
            assert resetting.result(timeout=5).status_code==200
    finally:
        if child.poll() is None:
            child.kill();child.wait()
