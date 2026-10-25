"""Service boundary checks use local pure builders and real SQLite state."""
from copy import deepcopy

from app.forecasting.persistence import ForecastStore
from app.forecasting.service import ForecastService
from app.forecasting.worker import ForecastWorker


def fixture_snapshot(*, now, tenant_id):
    return {'id': 'fixture', 'tenant_id': tenant_id, 'information_cutoff': now,
            'forecast_start': now[:10], 'history_complete_through': '2026-10-25',
            'observations': [{'quantity': 3}], 'drivers': [], 'coverage': [], 'required_sources': ['billing']}


def build(snapshot, *, run_id, generated_at, drivers=None):
    return {'run_id': run_id, 'snapshot_id': snapshot['id'],
            'views': [{'publication': {'forecast_start': snapshot['forecast_start'], 'history_complete_through': snapshot['history_complete_through']}, 'scope': {'type': 'company', 'id': 'northstar'}, 'value': sum(x['quantity'] for x in snapshot['observations']), 'drivers': snapshot['drivers'] if drivers is None else drivers}],
            'calculations': [{'snapshot_id': snapshot['id']}], 'driver_effects': []}


def service(tmp_path):
    clock = ['2026-10-28T03:00:00Z']
    svc = ForecastService(ForecastStore(tmp_path / 'f.db'), snapshot_factory=fixture_snapshot, builder=build, now=lambda: clock[0])
    return svc, clock


def test_missed_monday_reconstructs_monday_cutoff_and_duplicate_manual_request(tmp_path):
    svc, clock = service(tmp_path)
    weekly = svc.schedule_due()
    assert weekly['scheduled_for'].startswith('2026-10-26T00:00:00')
    assert svc.store.get_snapshot(weekly['snapshot_id'])['information_cutoff'].startswith('2026-10-26T00:00:00')
    assert svc.store.get_snapshot(weekly['snapshot_id'])['generated_at'].startswith('2026-10-28T03:00:00')
    assert svc.schedule_due()['id'] == weekly['id']
    one = svc.refresh('click')
    clock[0] = '2026-10-29T00:00:00Z'
    assert svc.refresh('click')['snapshot_id'] == one['snapshot_id']


def test_published_run_and_scenario_do_not_rebase_after_new_actuals(tmp_path):
    svc, clock = service(tmp_path)
    job = svc.refresh('one')
    assert ForecastWorker(svc).process_one()
    published = svc.views()
    assert published['views'][0]['value'] == 3
    svc.store.append_input('observations', 'billing', '2', [{'quantity': 9}], available_at=clock[0])
    assert svc.views()['views'] == published['views']
    assert svc.views()['current_actuals']['observations'][0]['quantity'] == 9
    scenario = svc.scenario(job['run_id'], [])
    assert scenario['views'][0]['value'] == 3
    assert svc.store.publication()['run_id'] == job['run_id']
    assert svc.get_scenario(scenario['scenario_id'])['views'][0]['value'] == 3
    assert svc.explain(job['run_id'])['snapshot']['observations'][0]['quantity'] == 3


def test_input_received_after_cutoff_is_never_backdated(tmp_path):
    svc, clock = service(tmp_path)
    svc.store.append_input('coverage', 'late', '1', [{'date': '2026-10-25', 'source_id': 'billing', 'complete': True}], available_at='2026-10-25T00:00:00Z', received_at='2026-10-29T00:00:00Z')
    job = svc.refresh('asof')
    snapshot = svc.store.get_snapshot(job['snapshot_id'])
    assert snapshot['coverage'] == []
    assert snapshot['required_sources'] == ['billing']


def test_new_revision_replaces_fixture_driver_from_same_source(tmp_path):
    def fixture(*, now, tenant_id):
        s = fixture_snapshot(now=now, tenant_id=tenant_id)
        s['drivers'] = [{'id':'old','source_id':'schedule','source_revision':1,'status':'eligible'}]
        return s
    svc = ForecastService(ForecastStore(tmp_path/'f.db'), snapshot_factory=fixture, builder=build, now=lambda:'2026-10-28T00:00:00Z')
    svc.store.append_input('evidence','schedule','2',{'envelope':{},'drivers':[{'id':'new','source_id':'schedule','source_revision':2,'status':'eligible'}]},available_at='2026-10-27T00:00:00Z')
    assert [d['id'] for d in svc.current_snapshot()['drivers']] == ['new']


def test_material_revision_ignores_clock_and_learning_archive(tmp_path):
    svc, clock = service(tmp_path)
    before = svc.material_revision()
    clock[0] = '2026-10-28T04:00:00Z'
    svc.store.append_input('issued_targets','target','1',{'prediction':1},available_at=clock[0])
    assert svc.material_revision() == before


def test_explanation_rejects_unknown_scope_and_driver(tmp_path):
    import pytest
    svc, _ = service(tmp_path)
    job = svc.refresh('explain')
    ForecastWorker(svc).process_one()
    with pytest.raises(KeyError):
        svc.explain(job['run_id'], 'person', 'missing')
    with pytest.raises(KeyError):
        svc.explain(job['run_id'], driver_id='missing')
    with pytest.raises(KeyError):
        svc.scenario(job['run_id'], [], 'person', 'missing')


def test_default_snapshot_is_unknown_and_never_synthetic(tmp_path):
    svc = ForecastService(ForecastStore(tmp_path/'empty.db'), builder=build, now=lambda:'2026-10-28T00:00:00Z')
    snapshot = svc.current_snapshot(tenant_id='real-company')
    assert not snapshot.get('is_synthetic', False)
    assert snapshot['observations'] == []
    assert snapshot['coverage'] == []
    assert snapshot['required_sources'] == ['repository:usage']


def test_worker_renews_lease_during_slow_build(tmp_path):
    from threading import Event
    clock=['2026-10-28T03:00:00Z']
    renewed=Event()
    first=[True]
    def controlled(snapshot, **kwargs):
        if first[0]:
            first[0]=False
            # Keep the injected clock before expiry until a real DB heartbeat
            # commits, then finish after the original lease would have expired.
            clock[0]='2026-10-28T03:00:02Z'
            assert renewed.wait(5), 'worker did not renew the active lease'
            clock[0]='2026-10-28T03:00:04Z'
        return build(snapshot, **kwargs)
    svc=ForecastService(ForecastStore(tmp_path/'heart.db'),snapshot_factory=fixture_snapshot,builder=controlled,now=lambda:clock[0])
    heartbeat=svc.store.heartbeat
    def observe_real_renewal(*args, **kwargs):
        result=heartbeat(*args, **kwargs)
        if result and clock[0]=='2026-10-28T03:00:02Z':
            renewed.set()
        return result
    svc.store.heartbeat=observe_real_renewal
    job=svc.refresh('slow')
    ForecastWorker(svc,lease_seconds=3).process_one()
    finished=svc.store.get_job(job['id'])
    assert finished['status']=='succeeded'
    assert finished['completed_at'].startswith('2026-10-28T03:00:04')


def test_refresh_freezes_registry_and_archives_all_three_procedures(tmp_path):
    from app.forecasting.fixtures import build_northstar_snapshot
    svc = ForecastService(ForecastStore(tmp_path/'learning.db'), snapshot_factory=build_northstar_snapshot, now=lambda:'2026-10-26T00:00:00Z')
    job = svc.refresh('learning')
    frozen = svc.store.get_snapshot(job['snapshot_id'])
    assert frozen['model_registry']['serving']['window_days'] == 56
    assert frozen['procedure'] == frozen['model_registry']['serving']
    ForecastWorker(svc).process_one()
    run = svc.store.get_run(job['run_id'])['bundle']
    assert {x['role'] for x in run['learning_runs']} == {'serving','shadow','reference'}
    archived = [r['payload'] for r in svc.store.input_records('2026-10-27T00:00:00Z') if r['kind'] == 'issued_targets']
    assert {r['procedure_id'] for r in archived} == {'driver-rate-weekblock-v1','driver-rate-weekblock-28-v1','seasonal_naive'}
    assert svc.current_snapshot()['model_registry']['registry_id'] == frozen['model_registry']['registry_id']


def test_scope_filter_does_not_label_company_effect_as_person_effect(tmp_path):
    svc, _ = service(tmp_path)
    def scoped(snapshot, *, run_id, generated_at, drivers=None):
        bundle = build(snapshot, run_id=run_id, generated_at=generated_at, drivers=drivers)
        bundle['views'].append({**deepcopy(bundle['views'][0]), 'scope': {'type':'person','id':'maya'}})
        bundle['driver_effects'] = [
            {'driver_id':'company-driver','scope':{'type':'company','id':'northstar'},'base_delta':100},
            {'driver_id':'person-driver','scope':{'type':'person','id':'maya'},'base_delta':12}]
        bundle['calculations'] = [{'id':'driver:company-driver','scope':{'type':'company','id':'northstar'}}, {'id':'calculation:rates'}]
        return bundle
    svc.builder = scoped
    job = svc.refresh('scope')
    ForecastWorker(svc).process_one()
    explanation = svc.explain(job['run_id'], 'person', 'maya')
    assert [r['base_delta'] for r in explanation['driver_effects']] == [12]
    assert [r['id'] for r in explanation['calculations']] == ['calculation:rates', 'driver:person-driver']


def test_second_refresh_later_clock_reuses_registry_and_manual_starts_next_whole_day(tmp_path):
    from app.forecasting.fixtures import build_northstar_snapshot
    clock = ['2026-10-26T12:00:00Z']
    svc = ForecastService(ForecastStore(tmp_path/'twice.db'), snapshot_factory=build_northstar_snapshot, now=lambda:clock[0])
    first = svc.refresh('first')
    frozen = svc.store.get_snapshot(first['snapshot_id'])
    assert frozen['forecast_start'] == '2026-10-27'
    assert frozen['history_complete_through'] == '2026-10-25'
    clock[0] = '2026-10-26T13:00:00Z'
    second = svc.refresh('second')
    assert svc.store.get_snapshot(second['snapshot_id'])['model_registry']['registry_id'] == frozen['model_registry']['registry_id']
    weekly = svc.schedule_due()
    assert svc.store.get_snapshot(weekly['snapshot_id'])['forecast_start'] == '2026-10-26'


def test_invalid_connector_payload_is_rejected_before_any_persistence(tmp_path):
    import pytest
    svc, _ = service(tmp_path)
    for bad in [
        {'source':'slack','source_id':'x','revision':1,'available_at':123,'payload':{}},
        {'source':'slack','source_id':'x','revision':1,'available_at':'2026-10-23T00:00:00Z','payload':{'supersedes':['driver1']}},
    ]:
        with pytest.raises(ValueError):
            svc.ingest_evidence(bad)
    assert svc.store.input_records('2026-10-29T00:00:00Z') == []


def test_worker_uses_actual_build_and_publication_times(tmp_path):
    from app.forecasting.fixtures import build_northstar_snapshot
    clock = ['2026-10-26T00:00:00Z']
    svc = ForecastService(ForecastStore(tmp_path/'issued.db'), snapshot_factory=build_northstar_snapshot, now=lambda:clock[0])
    job = svc.refresh('time')
    clock[0] = '2026-10-26T00:05:00Z'
    ForecastWorker(svc).process_one()
    run = svc.store.get_run(job['run_id'])['bundle']
    assert run['views'][0]['publication']['generated_at'].startswith('2026-10-26T00:05:00')
    issued = [r['payload'] for r in svc.store.input_records('2026-10-27T00:00:00Z') if r['kind']=='issued_targets']
    assert issued and all(r['issued_at'].startswith('2026-10-26T00:05:00') for r in issued)


def test_duplicate_corrected_envelope_returns_frozen_extraction(tmp_path):
    from app.forecasting.fixtures import build_northstar_snapshot, northstar_evidence
    svc = ForecastService(ForecastStore(tmp_path/'evidence.db'), snapshot_factory=build_northstar_snapshot, now=lambda:'2026-10-26T12:00:00Z')
    envelope = deepcopy(next(e for e in northstar_evidence() if e['source']=='monday'))
    envelope.update(revision=2,text='Beacon workload is 3 work_units per day from 2026-10-26 through 2026-11-15.')
    first = svc.ingest_evidence(envelope)
    assert svc.ingest_evidence(deepcopy(envelope)) == first


def test_scenario_is_persisted_job_with_no_publication_or_learning_side_effect(tmp_path):
    svc, clock = service(tmp_path)
    parent = svc.refresh('parent')
    ForecastWorker(svc).process_one()
    publication = svc.store.publication()
    before = len([r for r in svc.store.input_records(clock[0]) if r['kind']=='issued_targets'])
    scenario = svc.scenario(parent['run_id'], [])
    job = svc.store.get_job(scenario['job_id'])
    assert job['job_type'] == 'scenario' and job['status']=='succeeded'
    assert job['parent_run_id'] == parent['run_id']
    assert svc.store.publication() == publication
    assert len([r for r in svc.store.input_records(clock[0]) if r['kind']=='issued_targets']) == before
    assert svc.get_scenario(scenario['scenario_id'])['job_id'] == job['id']


def test_failed_scenario_job_can_resume_after_restart(tmp_path):
    svc, clock = service(tmp_path)
    parent = svc.refresh('parent')
    ForecastWorker(svc).process_one()
    original = svc.builder
    def unavailable(*args, **kwargs):
        raise RuntimeError('temporary scenario compute failure')
    svc.builder = unavailable
    pending = svc.scenario(parent['run_id'], [])
    assert pending['status'] == 'queued'
    assert svc.store.get_job(pending['job_id'])['attempts']==1
    clock[0]='2026-10-28T03:00:06Z'
    svc.builder=original
    resumed = ForecastService(ForecastStore(svc.store.path), snapshot_factory=fixture_snapshot,builder=original,now=lambda:clock[0])
    ForecastWorker(resumed).process_one()
    assert resumed.get_scenario(pending['scenario_id'])['status']=='succeeded'


def test_interpretation_job_survives_failure_and_duplicate_ingestion(tmp_path, monkeypatch):
    from app.forecasting import evidence
    from app.forecasting.fixtures import build_northstar_snapshot, northstar_evidence
    clock=['2026-10-26T12:00:00Z']
    svc=ForecastService(ForecastStore(tmp_path/'interpret.db'),snapshot_factory=build_northstar_snapshot,now=lambda:clock[0])
    envelope=deepcopy(northstar_evidence()[0])
    original=evidence.extract_event
    # Native source validation is complete before the extractor runs.
    monkeypatch.setattr(evidence,'extract_event',lambda *args: (_ for _ in ()).throw(RuntimeError('interpreter unavailable')))
    pending=svc.ingest_evidence(envelope)
    assert pending['status']=='queued'
    job_id=pending['interpretation_job_id']
    assert svc.store.get_job(job_id)['job_type']=='interpretation'
    assert svc.evidence()['items'][0]['interpretation_job_id']==job_id
    assert svc.ingest_evidence(deepcopy(envelope))['interpretation_job_id']==job_id
    assert svc.store.input_records(clock[0])==[]
    monkeypatch.setattr(evidence,'extract_event',original)
    clock[0]='2026-10-26T12:00:06Z'
    resumed=ForecastService(ForecastStore(svc.store.path),snapshot_factory=build_northstar_snapshot,now=lambda:clock[0])
    ForecastWorker(resumed).process_one()
    assert resumed.store.get_job(job_id)['status']=='succeeded'
    receipt=resumed.ingest_evidence(deepcopy(envelope))
    assert receipt['drivers'] and receipt['interpretation_job_id']==job_id
    assert len(resumed.store.input_records(clock[0]))==1


def test_scenario_driver_shapes_rejected_before_enqueue(tmp_path):
    import pytest
    svc,_=service(tmp_path)
    parent=svc.refresh('parent');ForecastWorker(svc).process_one()
    for driver in [{'id':'x','kind':'workload','scope':None,'parameters':{}}, {'id':'x','kind':'workload','scope':{},'parameters':None}]:
        with pytest.raises(ValueError):
            svc.scenario(parent['run_id'],[driver])


def test_concurrent_source_revision_with_different_raw_payload_conflicts(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from app.forecasting.persistence import ImmutableConflict
    gate=Barrier(2)
    def simultaneous(*,now,tenant_id):
        gate.wait(timeout=5)
        return fixture_snapshot(now=now,tenant_id=tenant_id)
    svc=ForecastService(ForecastStore(tmp_path/'race.db'),snapshot_factory=simultaneous,builder=build,now=lambda:'2026-10-28T03:00:00Z')
    def ingest(text):
        try:
            return svc.ingest_evidence({'source':'slack','source_id':'same','revision':1,'available_at':'2026-10-28T03:00:00Z','text':text,'payload':{}})['status']
        except ImmutableConflict:
            return 'conflict'
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(ingest,['maybe move project','maybe pause project']))
    assert results.count('conflict')==1
    assert len(svc.store.list_jobs(job_type='interpretation'))==1


def test_error_receipts_append_corrections_withdrawals_without_changing_fit_inputs(tmp_path):
    from forecasting.learning import current_error_records
    svc, clock=service(tmp_path)
    svc.refresh('initialize-registry')
    baseline=svc.material_revision()
    target={'target_id':'issued-original','run_id':'historic-run','issued_at':'2026-10-12T00:00:00Z',
            'origin':'2026-10-12','start':'2026-10-12','end':'2026-10-19','lead_days':0,'duration_days':7,
            'aggregation':'weekly','scope_type':'company','scope_id':'northstar','unit':'USD','basis':'planning',
            'timezone':'UTC','procedure_id':'original-v1','history_delay_days':0,'prediction':100.,'is_synthetic':False}
    truth={'target_id':'issued-original','revision':1,'available_at':'2026-10-27T00:00:00Z',
           'mature_at':'2026-10-27T00:00:00Z','status':'mature','value':112.,'source_id':'ledger','is_synthetic':False}
    svc.store.append_input('issued_targets',target['target_id'],'1',target,available_at=target['issued_at'])
    svc.store.append_input('truth_revisions',target['target_id'],'1',truth,available_at=truth['available_at'])
    first=svc.refresh('score')
    frozen=svc.store.get_snapshot(first['snapshot_id'])
    assert frozen['forecast_errors'][0]['absolute_error']==12
    assert frozen['observations']==[{'quantity':3}]
    assert svc.material_revision()==baseline
    clock[0]='2026-10-28T04:00:00Z'
    pending={**truth,'revision':2,'status':'pending','value':999.,'available_at':clock[0],'mature_at':clock[0]}
    svc.store.append_input('truth_revisions',target['target_id'],'2',pending,available_at=clock[0])
    second=svc.refresh('withdraw')
    receipts=svc.store.get_snapshot(second['snapshot_id'])['forecast_errors']
    assert len(receipts)==2
    assert current_error_records(receipts,cutoff=clock[0])[target['target_id']]['state']=='withdrawn'
    assert receipts[0]['absolute_error']==12 and receipts[1]['actual'] is None
    assert svc.material_revision()==baseline
    clock[0]='2026-10-28T05:00:00Z'
    svc.refresh('again-no-new-truth')
    persisted=[r for r in svc.store.input_records(clock[0]) if r['kind']=='forecast_errors']
    assert len(persisted)==2
    assert svc.store.get_snapshot(first['snapshot_id'])['forecast_errors']==frozen['forecast_errors']


def test_worker_polling_recovers_after_transient_repository_reset(tmp_path):
    import asyncio
    svc,_=service(tmp_path)
    async def check():
        stop=asyncio.Event()
        calls=[]
        def schedule():
            calls.append(1)
            if len(calls)==1:
                raise RuntimeError('repository tables temporarily resetting')
            stop.set()
        svc.schedule_due=schedule
        await ForecastWorker(svc).run_forever(stop,poll_seconds=0.001)
        assert len(calls)==2
    asyncio.run(check())


def test_manual_freeze_uses_captured_archive_not_later_live_mutation(tmp_path):
    live={'quantity':3};archive={}
    def factory(*,now,tenant_id,as_of):
        snapshot=fixture_snapshot(now=now,tenant_id=tenant_id)
        snapshot['observations']=[deepcopy(archive if as_of else live)]
        return snapshot
    def capture(*,now,tenant_id):
        archive.update(live)
        # A concurrent import/mapping change can commit after this cutoff capture
        # and before the freeze reads. Its live state is not cutoff evidence.
        live['quantity']=99
    factory.supports_as_of=True
    factory.capture_inputs=capture
    svc=ForecastService(ForecastStore(tmp_path/'archive-race.db'),snapshot_factory=factory,builder=build,now=lambda:'2026-10-28T03:00:00Z')
    job=svc.refresh('freeze')
    assert svc.store.get_snapshot(job['snapshot_id'])['observations']==[{'quantity':3}]
    assert svc.current_actuals()['observations']==[{'quantity':99}]


def test_snapshot_freezes_explicit_numerical_adapter_dependencies(tmp_path, monkeypatch):
    import hashlib
    from pathlib import Path
    import app.forecasting.service as service_module
    svc,_=service(tmp_path)
    first=svc.refresh('dependency-before')
    before=svc.store.get_snapshot(first['snapshot_id'])
    dependencies=before['procedure_dependencies']
    package=Path(service_module.__file__).parent
    assert dependencies=={
        'evidence_extraction':{'version':'native-envelope-v1','sha256':hashlib.sha256((package/'evidence.py').read_bytes()).hexdigest()},
        'repository_adapter':{'version':'repository-snapshot-v1','sha256':hashlib.sha256((package/'repository.py').read_bytes()).hexdigest()},
        'native_evidence_adapter':{'version':'native-corpus-signals-v1','sha256':hashlib.sha256((package/'native_evidence.py').read_bytes()).hexdigest()},
        'outcome_ingestion':{'version':'observed-target-outcome-v1','sha256':hashlib.sha256((package/'outcomes.py').read_bytes()).hexdigest()},
        'repository_archive':{'version':'repository-row-archive-v2','sha256':hashlib.sha256((package/'archive.py').read_bytes()).hexdigest()}}
    changed=deepcopy(dependencies)
    changed['native_evidence_adapter']['sha256']='f'*64
    monkeypatch.setattr(service_module,'procedure_dependency_manifest',lambda:deepcopy(changed))
    second=svc.refresh('dependency-after')
    assert svc.store.get_snapshot(second['snapshot_id'])['procedure_dependencies']==changed
    assert svc.store.get_snapshot(first['snapshot_id'])['procedure_dependencies']==dependencies


def test_adapter_dependency_change_isolates_issued_procedure_identity(tmp_path, monkeypatch):
    import app.forecasting.service as service_module
    from app.forecasting.fixtures import build_northstar_snapshot
    svc=ForecastService(ForecastStore(tmp_path/'adapter-identity.db'),snapshot_factory=build_northstar_snapshot,now=lambda:'2026-10-26T00:00:00Z')
    first=svc.refresh('before');ForecastWorker(svc).process_one()
    before=svc.store.get_run(first['run_id'])['bundle']
    changed=deepcopy(svc.store.get_snapshot(first['snapshot_id'])['procedure_dependencies'])
    changed['evidence_extraction']['sha256']='f'*64
    monkeypatch.setattr(service_module,'procedure_dependency_manifest',lambda:deepcopy(changed))
    second=svc.refresh('after');ForecastWorker(svc).process_one()
    after=svc.store.get_run(second['run_id'])['bundle']
    assert before['effective_procedure_id']!=after['effective_procedure_id']
    assert after['model_registry']['decision']['promote'] is False
    records=[r['payload'] for r in svc.store.input_records(svc.now()) if r['kind']=='issued_targets']
    original=next(r for r in records if r['run_id']==first['run_id'])
    revised=next(r for r in records if r['run_id']==second['run_id'])
    assert original['implementation_sha256']!=revised['implementation_sha256']


def test_actuals_ignore_learning_receipts_and_returned_views_cannot_mutate_issuance(tmp_path):
    svc, clock = service(tmp_path)
    job = svc.refresh('initial')
    assert ForecastWorker(svc).process_one()
    before = svc.current_actuals()
    svc.store.append_input('issued_targets', 'unrelated', '1', {'unrelated': 'learning receipt'}, available_at=clock[0])
    assert svc.current_actuals() == before
    original = svc.views(include_current_actuals=False)
    altered = svc.views(include_current_actuals=False)
    altered['views'][0]['value'] = 999
    altered['calculations'].clear()
    assert svc.views(include_current_actuals=False) == original
    assert svc.store.get_run(job['run_id'])['bundle']['views'][0]['value'] == 3
    svc.store.append_input('observations', 'new-actuals', '1', [{'quantity': 7}], available_at=clock[0])
    after = svc.current_actuals()
    assert after['observations'] == [{'quantity': 7}]
    assert after['revision'] != before['revision']
