from decimal import Decimal
import json
import subprocess
import sys
import os

from forecasting.integration import write_demo_inputs, forecast_from_config, run_demo


def test_authorized_source_to_snapshot_forecast_scenario_and_independent_receipts(tmp_path):
    report=run_demo(tmp_path)
    assert report['evidence']=='synthetic_fixture'
    assert Decimal(report['forecast']['result']['recorded'])==95000
    assert report['forecast']['result']['future'] is not None
    assert report['forecast']['variable_total'] is None
    assert report['context']['mode']=='explanation_only'
    assert 'old-research' in report['context']['superseded']
    assert report['scenario']['conditional'] is True
    assert report['scenario']['assumption']['multiplier']=='1.20'
    assert Decimal(report['decisions']['redistribution']['after']['envelope'])==200000
    assert Decimal(report['decisions']['addition']['after']['envelope'])==250000
    assert report['decisions']['addition']['after']['allocations']=={'research':'95000','product':'80000','engineering':'75000'}
    assert report['live_factory']=='not_executed: credentials/runtime not supplied'
    assert (tmp_path/'demo-report.json').exists()


def test_cli_roundtrip_and_invalid_source_never_becomes_zero(tmp_path):
    config=write_demo_inputs(tmp_path)
    env=dict(os.environ,PYTHONPATH='src')
    command=[sys.executable,'-m','forecasting','forecast',str(config),'--store',str(tmp_path/'results.sqlite')]
    run=subprocess.run(command,capture_output=True,text=True,env=env)
    assert run.returncode==0,run.stderr
    value=json.loads(run.stdout)
    shown=subprocess.run([sys.executable,'-m','forecasting','show',value['artifact_id'],'--store',str(tmp_path/'results.sqlite'),'--tenant','northstar','--source','billing'],capture_output=True,text=True,env=env)
    assert shown.returncode==0 and json.loads(shown.stdout)['result']==value['result']
    obj=json.loads(config.read_text());obj['coverage'][0]['state']='missing';config.write_text(json.dumps(obj))
    with pytest.raises(ValueError,match='conflicting coverage'):
        forecast_from_config(config,tmp_path/'results.sqlite')
    unavailable=forecast_from_config(config,tmp_path/'missing.sqlite')
    assert unavailable['result']['status']=='unavailable'
    assert unavailable['result']['future'] is None
    assert Decimal(unavailable['result']['recorded'])==95000


import pytest

@pytest.mark.parametrize('stage', ['before_source','after_source','before_snapshot','after_snapshot',
    'before_forecast','after_forecast','before_store','after_store','before_context','after_context',
    'before_review','after_review','before_apply','after_apply'])
def test_fault_injection_each_handoff_preserves_unaffected_journey(tmp_path,stage):
    def inject(current):
        if current==stage: raise RuntimeError('injected '+stage)
    broken=tmp_path/'broken'
    with pytest.raises(RuntimeError,match=stage): run_demo(broken,fault=inject)
    assert not (broken/'demo-report.json').exists()
    if stage=='after_apply':
        from forecasting.consumers import FinanceStore
        backend=FinanceStore(broken/'redistribution.sqlite','northstar')
        receipt=backend.receipt('redistribution',actor='demo-finance')
        assert receipt is not None and receipt.after.envelope==200000
        assert backend.decision_count()==1
    control=run_demo(tmp_path/'control')
    assert Decimal(control['forecast']['result']['recorded'])==95000
    assert control['decisions']['addition']['after']['envelope']=='250000'


def test_wsgi_post_real_snapshot_scoped_body_and_current_auth(tmp_path):
    import io
    from forecasting.integration import load_snapshot
    from forecasting.service import ForecastService, ForecastApplication
    config=write_demo_inputs(tmp_path)
    request,snapshot,store,_=load_snapshot(config,tmp_path/'results.sqlite')
    app=ForecastApplication(ForecastService(store),authenticate=lambda env:('northstar',{'billing'}),
                            snapshot_resolver=lambda request,tenant,sources:snapshot)
    body=json.dumps(request.to_dict()).encode()
    statuses=[]
    result=json.loads(b''.join(app({'REQUEST_METHOD':'POST','PATH_INFO':'/v1/forecast',
        'CONTENT_LENGTH':str(len(body)),'wsgi.input':io.BytesIO(body)},lambda s,h:statuses.append(s))))
    assert statuses==['200 OK'] and Decimal(result['result']['recorded'])==95000
    value=request.to_dict();value['target']['tenant_id']='different-tenant'
    body=json.dumps(value).encode();statuses=[]
    b''.join(app({'REQUEST_METHOD':'POST','PATH_INFO':'/v1/forecast','CONTENT_LENGTH':str(len(body)),
                 'wsgi.input':io.BytesIO(body)},lambda s,h:statuses.append(s)))
    assert statuses==['403 Forbidden']
    value=request.to_dict();value['admin_file_path']='/etc/passwd'
    body=json.dumps(value).encode();statuses=[]
    b''.join(app({'REQUEST_METHOD':'POST','PATH_INFO':'/v1/forecast','CONTENT_LENGTH':str(len(body)),
                 'wsgi.input':io.BytesIO(body)},lambda s,h:statuses.append(s)))
    assert statuses==['400 Bad Request']


def test_native_anthropic_cost_report_to_stored_forecast(tmp_path):
    from datetime import date,timedelta
    page={'data':[],'has_more':False,'next_page':None}
    for i in range(7):
        start=date(2026,1,1)+timedelta(days=i);end=start+timedelta(days=1)
        page['data'].append({'starting_at':str(start)+'T00:00:00Z','ending_at':str(end)+'T00:00:00Z',
            'results':[{'amount':'125.25','currency':'USD','workspace_id':None,'description':'Usage - Input Tokens'}]})
    (tmp_path/'native.json').write_text(json.dumps(page))
    config={'schema_version':'1.0','adapter':'anthropic_cost_report','exports':['native.json'],
        'source_id':'anthropic:console:fixture','history_start':'2026-01-01','evidence_class':'synthetic_fixture',
        'query':{'starting_at':'2026-01-01T00:00:00Z','ending_at':'2026-01-08T00:00:00Z','bucket_width':'1d'},
        'request_pages':[None],'maturity':'finalized','maturity_policy':'synthetic-fixture-only',
        'request':{'request_id':'native-demo','target':{'target_id':'native','tenant_id':'org','measure':'provider_reported_cost',
            'unit':'USD','currency':'USD','sources':['anthropic:console:fixture'],'categories':['variable']},
            'as_of':'2026-01-08T00:00:00Z','period_start':'2026-01-01','period_end':'2026-01-15','model':'trailing_mean'}}
    p=tmp_path/'config.json';p.write_text(json.dumps(config))
    result=forecast_from_config(p,tmp_path/'store.sqlite')
    assert Decimal(result['result']['recorded'])==Decimal('8.7675')
    assert Decimal(result['result']['future'])==Decimal('8.7675')
    assert 'unattributed' in result['entities']
    assert 'priority_tier_costs' in result['manifest']['source_exclusions']
    assert result['manifest']['evidence_class']=='synthetic_fixture'
    config['maturity']='provisional';config['maturity_policy']='';p.write_text(json.dumps(config))
    pending=forecast_from_config(p,tmp_path/'pending.sqlite')
    assert pending['result']['status']=='unavailable' and pending['result']['future'] is None


def test_saved_context_requires_current_document_access_not_only_billing(tmp_path):
    from forecasting.store import ArtifactStore, AccessDenied
    report=run_demo(tmp_path)
    store=ArtifactStore(tmp_path/'forecasts.sqlite')
    with pytest.raises(AccessDenied):
        store.get('northstar',report['context_artifact_id'],allowed_sources={'billing'})
    permitted={'billing'}|{'context:'+event+':1' for event in ('old-research','research-plan','product-plan','engineering-note')}
    saved=store.get('northstar',report['context_artifact_id'],allowed_sources=permitted)
    assert saved['payload']['events']
    permitted.remove('context:research-plan:1')
    with pytest.raises(AccessDenied):
        store.get('northstar',report['context_artifact_id'],allowed_sources=permitted)


def test_real_delayed_daily_acquisition_replays_nonfuture_origin_and_retains_partial_charges(tmp_path,monkeypatch):
    from datetime import datetime,timezone
    import forecasting.ingestion as ingestion
    from forecasting.integration import ingest_from_config
    from forecasting.source_store import SourceStore
    class Clock(datetime):
        current=datetime(2026,9,16,12,tzinfo=timezone.utc)
        @classmethod
        def now(cls,tz=None):return cls.current.astimezone(tz or timezone.utc)
    monkeypatch.setattr(ingestion,'datetime',Clock)
    p=write_demo_inputs(tmp_path)
    config=json.loads(p.read_text());config['evidence_class']='authorized_local_file'
    config['request']['as_of']='2026-09-17T00:00:00+00:00'
    config['history_end']='2026-09-16';config['max_history_lag_days']=1
    config['coverage'].append(dict(source_id='billing',start='2026-09-16',end='2026-09-17',
        state='partial',maturity='provisional',known_at='2026-09-16T12:00:00+00:00'))
    source=tmp_path/config['export'];rows=json.loads(source.read_text())
    partial=dict(rows['records'][0]);partial.update(record_id='partial',service_date='2026-09-16',value='5',status='partial',
        known_at='2026-09-16T12:00:00+00:00',ingested_at='2026-09-16T12:00:00+00:00',processed_at='2026-09-16T12:00:00+00:00')
    rows['records'].append(partial);source.write_text(json.dumps(rows));p.write_text(json.dumps(config))
    acquired=ingest_from_config(p,tmp_path/'real.sqlite')
    assert acquired['receipt']['fetched_at']=='2026-09-16T12:00:00+00:00'
    Clock.current=datetime(2026,9,17,12,tzinfo=timezone.utc)
    result=forecast_from_config(p,tmp_path/'real.sqlite')
    assert datetime.fromisoformat(result['result']['as_of'])<=Clock.current
    assert Decimal(result['result']['recorded'])==95005
    assert result['result']['future'] is not None and result['result']['late'] is None
    assert result['manifest']['history_lag_days']==1
    assert min(result['entities']['team:research']['daily'])=='2026-09-17'
    assert result['recorded_supplement_artifact_id']
    ledger,_=SourceStore(tmp_path/'real-sources.sqlite').load('northstar','billing',evidence_class='authorized_local_file',adapter='normalized')
    assert len(ledger.receipts)==1 and ledger.receipts[0].fetched_at==datetime(2026,9,16,12,tzinfo=timezone.utc)
    fresh=forecast_from_config(p,tmp_path/'fresh.sqlite')
    assert fresh['result']['status']=='unavailable' and fresh['result']['future'] is None
    config['max_history_lag_days']=0;p.write_text(json.dumps(config))
    with pytest.raises(ValueError,match='lag policy'):forecast_from_config(p,tmp_path/'real.sqlite')


def test_acquisition_source_cannot_borrow_unrelated_target_permissions(tmp_path):
    from forecasting.integration import ingest_from_config
    config=write_demo_inputs(tmp_path)
    data=json.loads(config.read_text());data['request']['target']['sources']=['other-source'];config.write_text(json.dumps(data))
    with pytest.raises(ValueError,match='source'):
        ingest_from_config(config,tmp_path/'store.sqlite')
