"""Product reads and decisions must refer to the same immutable numerical publication."""
from datetime import datetime, timezone
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from app.config import Settings
from app.main import create_app
from app.core.clock import FrozenClock, SequentialIdFactory
from app.seed.northstar import seed


def _app(tmp_path):
    clock = FrozenClock(datetime(2026, 10, 24, 12, tzinfo=timezone.utc))
    app = create_app(Settings(db_path=tmp_path/'engine.db',forecast_provider='engine',forecast_demo=True,
                              forecast_worker=False),clock=clock,id_factory=SequentialIdFactory())
    with app.state.session_factory() as session:
        seed(session,clock=clock,ids=app.state.id_factory)
    return app


def test_engine_provider_uses_issued_quarter_and_exposes_people(tmp_path):
    app = _app(tmp_path)
    with TestClient(app) as client:
        service=app.state.forecast_service
        job=service.refresh('integration-publication', scheduled_for='2026-10-19T00:00:00Z')
        assert app.state.forecast_worker.process_one()
        assert service.store.get_job(job['id'])['status']=='succeeded'
        bundle=service.views(scope_type='team')
        expected={v['scope']['id']:v['quarter_outlook']['base'] for v in bundle['views']}
        actual=client.get('/api/forecasts').json()
        assert actual['provider']=='engine'
        assert actual['forecast_run_id']==job['run_id']
        assert actual['basis']=='full_period_total'
        assert {p['team']:float(p['amount']) for p in actual['projections']} == pytest.approx(expected,abs=.005)
        people=client.get('/compat/api/people')
        assert people.status_code==200
        assert people.json() and all(p['teamId'] for p in people.json())
        assert client.get('/compat/api/forecast-views').status_code==200
        assert client.get('/api/forecast-runs/'+job['run_id']+'/explanation').status_code==200
        # Reads never mint another run or rewrite the publication.
        assert service.store.publication()['run_id']==job['run_id']


def test_default_startup_selects_real_engine_without_synthetic_inputs(tmp_path):
    settings=Settings.from_env({'BACKEND_DB_PATH':str(tmp_path/'empty.db'),'FORECAST_WORKER':'0'})
    assert settings.forecast_provider=='engine'
    app=create_app(settings)
    assert app.state.forecast_provider.name=='engine'
    assert not app.state.forecast_service.current_snapshot()['observations']


def test_material_evidence_queues_and_invalidates_dependent_proposal(tmp_path):
    from budget_helpers import draft, transfer_body, decide, allocations, INITIAL, ANALYST
    from app.forecasting.fixtures import northstar_evidence
    app=_app(tmp_path)
    with TestClient(app) as client:
        service=app.state.forecast_service
        job=service.refresh('before-update');app.state.forecast_worker.process_one()
        before=service.store.get_run(job['run_id'])['bundle']
        receipt=client.post('/api/forecasts/snapshots',headers=ANALYST).json()
        body=transfer_body(evidence_refs=[{'kind':'forecast_snapshot','id':receipt['id']}])
        response=draft(client,body);assert response.status_code==201,response.text
        proposal=response.json()['id']
        # Derived error bookkeeping is not new commercial or workload evidence.
        service.store.append_input('forecast_errors','score-receipt','1',{'status':'scored','absolute_error':2},
            available_at='2026-10-24T12:00:00Z',received_at='2026-10-24T12:00:00Z')
        assert client.get('/api/proposals/'+proposal).json()['status']=='pending_review'
        from app.services.forecast_freshness import stale_forecast_refs
        with app.state.session_factory() as session:
            assert stale_forecast_refs(session,body['evidence_refs'],app.state.clock.now())==[]
        event=dict(northstar_evidence()[0],source_id='new-manager-update',available_at='2026-10-24T11:00:00Z')
        added=client.post('/api/forecast-evidence',json=event)
        assert added.status_code==201,added.text
        assert service.store.publication()['run_id']==job['run_id']
        assert service.store.get_run(job['run_id'])['bundle']==before
        assert client.get('/api/proposals/'+proposal).json()['status']=='stale'
        assert decide(client,proposal).status_code==409
        assert allocations(client)==INITIAL
        # Ingestion can win before a draft starts: an old forecast must not create
        # a newly pending proposal after the invalidation callback already ran.
        late=draft(client,body)
        assert late.status_code==422,late.text
        assert 'stale_forecast_evidence' in late.text


def test_structured_ask_droid_preserves_run_scope_and_receipt(tmp_path):
    app=_app(tmp_path)
    with TestClient(app) as client:
        job=app.state.forecast_service.refresh('ask-droid');app.state.forecast_worker.process_one()
        context={'action':'explain','run_id':job['run_id'],'scope_type':'team','scope_id':'research'}
        response=client.post('/compat/api/threads/forecast-demo/messages',json={'content':'Why did research change?', 'forecast_context':context})
        assert response.status_code==200,response.text
        assistant=response.json()[-1]
        assert job['run_id'] in assistant['content']
        assert any(t['name']=='explain_forecast' for t in assistant['toolCalls'])


def test_repository_actuals_are_connected_without_invented_daily_coverage(tmp_path):
    app=_app(tmp_path)
    from app.forecasting.repository import repository_snapshot_factory
    app.state.forecast_service.snapshot_factory=repository_snapshot_factory(app.state.session_factory,clock=app.state.clock.now)
    with TestClient(app) as client:
        current=client.get('/api/forecast-views').json()['current_actuals']
        assert sum(Decimal(str(r['quantity'])) for r in current['observations'])==Decimal('95000.00')
        assert current['coverage']==[]
        assert all(r['meter']=='usd' for r in current['observations'])
        job=app.state.forecast_service.refresh('real-imports')
        app.state.forecast_worker.process_one()
        company=app.state.forecast_service.views(scope_type='company')['views'][0]
        assert company['components']['recorded']==95000
        assert company['quarter_outlook']['complete'] is False
        assert company['quarter_outlook']['base'] is None


def test_cached_approval_cannot_overtake_arriving_evidence(tmp_path):
    from budget_helpers import draft, transfer_body, ANALYST, INITIAL, allocations
    from app.forecasting.fixtures import northstar_evidence
    from app.core.actors import Actor
    from app.core.errors import DomainError
    from app.db.models import Proposal
    from app.schemas.decisions import DecisionCreate
    from app.services.decisions import decide
    app=_app(tmp_path)
    with TestClient(app) as client:
        service=app.state.forecast_service
        service.refresh('race');app.state.forecast_worker.process_one()
        receipt=client.post('/api/forecasts/snapshots',headers=ANALYST).json()
        pid=draft(client,transfer_body(evidence_refs=[{'kind':'forecast_snapshot','id':receipt['id']}])).json()['id']
        with app.state.session_factory() as held:
            proposal=held.get(Proposal,pid)
            assert proposal.status=='pending_review'
            service.ingest_evidence(dict(northstar_evidence()[0],source_id='race-update',available_at='2026-10-24T11:00:00Z'))
            with pytest.raises(DomainError):
                decide(held,pid,DecisionCreate(outcome='approve',rationale='cached approval'),
                       actor=Actor('other-finance','finance_approver'),idempotency_key='race',clock=app.state.clock,ids=app.state.id_factory)
        assert allocations(client)==INITIAL
        assert client.get('/api/budget').json()['state_version']==1


def test_delayed_older_revision_does_not_stale_newly_issued_receipt(tmp_path):
    from app.services.forecast_freshness import revision_from_snapshot,current_revision
    app=_app(tmp_path)
    store=app.state.forecast_service.store
    store.append_input('coverage','same-source','new',[],available_at='2026-10-23T00:00:00Z',received_at='2026-10-23T00:00:00Z')
    store.append_input('coverage','same-source','old',[],available_at='2026-10-22T00:00:00Z',received_at='2026-10-24T00:00:00Z')
    snapshot=app.state.forecast_service.current_snapshot()
    with app.state.session_factory() as session:
        assert current_revision(session,'northstar',app.state.clock.now())==revision_from_snapshot(snapshot)
