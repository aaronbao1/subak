"""Native corpus and signal writes must reach the same frozen forecast evidence."""
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.config import Settings
from app.core.clock import FrozenClock, SequentialIdFactory
from app.main import create_app
from app.seed.northstar import seed


IMPORTER = {'X-Actor-Id': 'importer', 'X-Actor-Role': 'importer'}
ANALYST = {'X-Actor-Id': 'analyst', 'X-Actor-Role': 'finance_analyst'}
TEXT = 'Atlas workload is 2.4 work_units per day from 2026-10-26 through 2026-11-15.'


def document(**changes):
    return dict(doc_key='native-atlas-work', title='Atlas approved workload', origin='upload',
                doc_type='plan', plan_status='approved', authored_at='2026-10-23T12:00:00Z',
                team_tags=['research'], project_tags=['atlas'], content=TEXT, is_simulated=True, **changes)


def native_item(client, key='native-atlas-work'):
    return next(item for item in client.get('/api/forecast-evidence').json()['items']
                if item['envelope']['source_id'] == 'native:document:' + key)


def test_native_document_queues_supported_driver_and_preserves_frozen_source(tmp_path):
    clock = FrozenClock(datetime(2026, 10, 24, 12, tzinfo=timezone.utc))
    app = create_app(Settings(db_path=tmp_path/'native.db', forecast_demo=True, forecast_worker=False),
                     clock=clock, id_factory=SequentialIdFactory())
    with app.state.session_factory() as session:
        seed(session, clock=clock, ids=app.state.id_factory)
    with TestClient(app) as client:
        response = client.post('/api/documents', json=document(), headers=IMPORTER)
        assert response.status_code == 201, response.text
        doc = response.json()['document']
        item = native_item(client)
        assert item['envelope']['source'] == 'native_document'
        assert item['envelope']['text'] == TEXT
        driver, = item['drivers']
        assert driver['status'] == 'eligible'
        assert driver['parameters']['exposure'] == 2.4
        assert driver['queue_status'] == 'queued'
        assert item['envelope']['payload']['document']['id'] == doc['id']
        assert driver['citations'][0]['quote'] == TEXT
        service = app.state.forecast_service
        job = service.refresh('native-document')
        assert app.state.forecast_worker.process_one(job_id=job['id'])
        before = service.store.get_snapshot(job['snapshot_id'])
        assert driver['id'] in {d['id'] for d in service.views()['views'][0]['included_drivers']}
        revised = {**document(), 'plan_status': 'cancelled', 'authored_at': '2026-10-24T12:00:00Z'}
        clock.advance(minutes=1)
        assert client.post('/api/documents', json=revised, headers=IMPORTER).status_code == 201
        latest = native_item(client)
        assert latest['drivers'][0]['status'] == 'context_only'
        assert latest['drivers'][0]['supersedes'] == driver['id']
        assert service.store.get_snapshot(job['snapshot_id']) == before
        assert driver['id'] not in {d['id'] for d in service.current_snapshot()['drivers']}


def test_native_signal_uses_document_passage_not_agent_summary(seeded, client, clock):
    response = client.post('/api/documents', json={**document(), 'content': 'The Atlas plan is being discussed.'}, headers=IMPORTER)
    assert response.status_code == 201, response.text
    doc = response.json()['document']
    body = {'scope': 'team', 'team': 'research', 'project': 'atlas', 'change_type': 'expansion',
            'status': 'current', 'summary': TEXT, 'uncertainty': 'No numerical workload was supplied.',
            'citations': [{'document_id': doc['id'], 'quote': doc['content']}]}
    signal = client.post('/api/signals', json=body, headers=ANALYST)
    assert signal.status_code == 201, signal.text
    item = native_item(client)
    assert item['envelope']['text'] == doc['content']
    assert item['drivers'][0]['status'] == 'context_only'
    assert signal.json()['id'] in {r['id'] for r in item['envelope']['payload']['signal_refs']}
    assert len([i for i in client.get('/api/forecast-evidence').json()['items']
                if i['envelope']['source_id'] == 'native:document:native-atlas-work']) == 1


def test_native_document_and_evidence_rollback_together(seeded, clock):
    from app.schemas.documents import DocumentIn
    from app.services.corpus import ingest_document
    service = seeded.state.forecast_service
    before = [r['id'] for r in service.store.input_records(clock.now())]
    with seeded.state.session_factory() as session:
        ingest_document(session, DocumentIn(**document()), clock=clock, ids=seeded.state.id_factory)
        assert session.connection().exec_driver_sql(
            "SELECT count(*) FROM forecast_inputs WHERE source_id='native:document:native-atlas-work'").scalar() == 1
        session.rollback()
    assert [r['id'] for r in service.store.input_records(clock.now())] == before


def test_seed_interpretation_records_native_signal_refs_in_canonical_evidence(seeded, client, clock):
    from app.seed.interpret import interpret_at_seed
    result = interpret_at_seed(seeded.state.session_factory, settings=seeded.state.settings,
                               clock=clock, ids=seeded.state.id_factory, mode='fake',
                               forecast_provider=seeded.state.forecast_provider)
    assert result.succeeded
    signals = client.get('/api/signals').json()['items']
    items = client.get('/api/forecast-evidence').json()['items']
    refs = {ref['id'] for item in items for ref in item['envelope']['payload'].get('signal_refs', [])}
    assert {s['id'] for s in signals} <= refs
    assert all(d['status'] == 'context_only' for item in items for d in item['drivers'])


def test_preexisting_cli_seed_is_captured_at_startup_without_backdated_receipt(tmp_path):
    from app.db.base import create_all, make_engine, make_session_factory
    clock = FrozenClock(datetime(2026, 10, 24, 12, tzinfo=timezone.utc))
    path = tmp_path/'preexisting.db'
    engine = make_engine(path)
    create_all(engine)
    with make_session_factory(engine)() as session:
        seed(session, clock=clock, ids=SequentialIdFactory())
    engine.dispose()
    clock.advance(days=1)
    app = create_app(Settings(db_path=path, forecast_worker=False), clock=clock)
    store = app.state.forecast_service.store
    rows = store.input_records(clock.now(), kinds=('evidence',))
    assert rows
    assert all(r['received_at'] == '2026-10-25T12:00:00.000000Z' for r in rows)
    assert store.input_records('2026-10-24T12:00:00Z', kinds=('evidence',)) == []
    before = [r['id'] for r in rows]
    app.state.forecast_service.evidence()
    app.state.forecast_service.current_snapshot()
    assert [r['id'] for r in store.input_records(clock.now(), kinds=('evidence',))] == before


def test_native_signal_curation_demotes_source_without_summary_arithmetic(tmp_path):
    clock = FrozenClock(datetime(2026, 10, 24, 12, tzinfo=timezone.utc))
    app = create_app(Settings(db_path=tmp_path/'curation.db', forecast_demo=True, forecast_worker=False),
                     clock=clock, id_factory=SequentialIdFactory())
    with app.state.session_factory() as session:
        seed(session, clock=clock, ids=app.state.id_factory)
    with TestClient(app) as client:
        doc = client.post('/api/documents', json=document(), headers=IMPORTER).json()['document']
        body = {'scope': 'team', 'team': 'research', 'project': 'atlas', 'change_type': 'expansion',
                'status': 'current', 'summary': 'Use a hundred times more.', 'uncertainty': 'Source may conflict.',
                'citations': [{'document_id': doc['id'], 'quote': TEXT}]}
        response = client.post('/api/signals', json=body, headers=ANALYST)
        assert response.status_code == 201, response.text
        assert native_item(client)['drivers'][0]['parameters']['exposure'] == 2.4
        signal_id = response.json()['id']
        assert client.patch('/api/signals/'+signal_id, json={'status': 'conflicting'}, headers=ANALYST).status_code == 200
        assert native_item(client)['drivers'][0]['status'] == 'context_only'
        assert client.patch('/api/signals/'+signal_id, json={'status': 'current'}, headers=ANALYST).status_code == 200
        assert native_item(client)['drivers'][0]['status'] == 'eligible'
