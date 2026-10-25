"""Executable reference handoffs. Northstar inputs and reviews here are synthetic."""
from __future__ import annotations
from dataclasses import asdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from .contracts import ForecastRequest, day, timestamp
from .ingestion import LocalFileAdapter, SourceLedger
from .snapshot import Coverage, build_snapshot
from .store import ArtifactStore, canonical_json
from .service import ForecastService
from .source_store import SourceStore


def _acquire_source(config_path, store_path, *, fault=None):
    """Authorized-local-file CLI boundary, not a remote arbitrary-file endpoint.

    Synthetic examples explicitly replay their fixture cutoff. Real files use
    actual receipt time; historical archive replay belongs to the backend ledger.
    """
    notify=fault or (lambda stage: None)
    notify('before_source')
    path=Path(config_path)
    config=json.loads(path.read_text())
    adapter=config.get('adapter','normalized')
    common={'schema_version','request','source_id','history_start','evidence_class'}
    if adapter=='normalized':
        required=common|{'export','coverage'}
        optional={'adapter','history_end','max_history_lag_days'}
    elif adapter=='anthropic_cost_report':
        required=common|{'adapter','exports','query','request_pages','maturity','maturity_policy'}
        optional={'provider_api_version','history_end','max_history_lag_days'}
    else:
        raise ValueError('unsupported source adapter')
    if not required<=set(config) or set(config)-(required|optional) or config['schema_version']!='1.0':
        raise ValueError('unknown or missing forecast config fields/version')
    if config['evidence_class'] not in {'synthetic_fixture','authorized_local_file'}:
        raise ValueError('unknown evidence class')
    request=ForecastRequest.from_dict(config['request'])
    if config['source_id'] not in request.target.sources:
        raise ValueError('acquired source must belong to the requested target scope')
    store_path=Path(store_path)
    fetched_at=request.as_of if config['evidence_class']=='synthetic_fixture' else None
    provider=None
    if adapter=='normalized':
        extraction=LocalFileAdapter().read(path.parent/config['export'],source_id=config['source_id'],tenant_id=request.target.tenant_id,
                                          authorized=True,fetched_at=fetched_at,archive_dir=store_path.parent/'raw')
        coverage=[]
        for row in config['coverage']:
            if set(row)!={'source_id','start','end','state','maturity','known_at'}: raise ValueError('invalid coverage fields')
            coverage.append(Coverage(row['source_id'],day(row['start']),day(row['end']),row['state'],row['maturity'],timestamp(row['known_at'])))
    else:
        from .provider_adapters import AnthropicCostReportAdapter
        provider=AnthropicCostReportAdapter().read(tuple(path.parent/p for p in config['exports']),
                    source_id=config['source_id'],tenant_id=request.target.tenant_id,query=config['query'],
                    request_pages=tuple(config['request_pages']),fetched_at=fetched_at,archive_dir=store_path.parent/'raw',
                    maturity=config['maturity'],maturity_policy=config['maturity_policy'],
                    provider_api_version=config.get('provider_api_version'))
        extraction=provider.extraction;coverage=provider.coverage
    source_store=SourceStore(store_path.with_name(store_path.stem+'-sources.sqlite'))
    retained=source_store.acquire(extraction,coverage,evidence_class=config['evidence_class'],adapter=adapter)
    ledger,coverage=source_store.load(request.target.tenant_id,config['source_id'],evidence_class=config['evidence_class'],adapter=adapter)
    notify('after_source')
    store=ArtifactStore(store_path)
    store.put(request.target.tenant_id,'extraction',extraction.to_dict(),(extraction.receipt.source_id,))
    if provider is not None: store.put(request.target.tenant_id,'provider_import',provider.to_dict(),(extraction.receipt.source_id,))
    return request,ledger,coverage,store,config,retained


def ingest_from_config(config_path,store_path):
    request,ledger,coverage,store,config,receipt=_acquire_source(config_path,store_path)
    return {'schema_version':'1.0','status':'acquired','tenant_id':request.target.tenant_id,
            'source_id':config['source_id'],'evidence_class':config['evidence_class'],
            'receipt':receipt.to_dict(),'delivery_count':len(ledger.receipts),
            'meaning':'Original acquisition is retained; this does not certify forecast maturity or coverage.'}


def load_snapshot(config_path, store_path, *, fault=None):
    request,ledger,coverage,store,config,receipt=_acquire_source(config_path,store_path,fault=fault)
    notify=fault or (lambda stage: None)
    notify('before_snapshot')
    origin=request.as_of.astimezone(ZoneInfo(request.target.reporting_timezone)).date()
    history_end=day(config['history_end']) if 'history_end' in config else origin
    lag=config.get('max_history_lag_days',0)
    if type(lag) is not int or not 0<=lag<=30 or not 0<=(origin-history_end).days<=lag:
        raise ValueError('explicit history watermark exceeds bounded lag policy')
    snapshot=build_snapshot(request.target,ledger,request.as_of,day(config['history_start']),history_end,
                            coverage=tuple(coverage),allowed_sources=set(request.target.sources))
    supplement=build_snapshot(request.target,ledger,request.as_of,history_end,origin,
                              coverage=tuple(coverage),allowed_sources=set(request.target.sources)) if history_end<origin else None
    notify('after_snapshot')
    policy={'evidence_class':snapshot.evidence_class,'max_history_lag_days':lag,'recorded_supplement':supplement}
    return request,snapshot,store,policy


def forecast_from_config(config_path, store_path, *, fault=None):
    request,snapshot,store,policy=load_snapshot(config_path,store_path,fault=fault)
    return ForecastService(store).run(request,snapshot,allowed_sources=set(request.target.sources),fault=fault,**policy)


def write_demo_inputs(directory):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    origin=datetime(2026,9,16,tzinfo=timezone.utc)
    start=date(2026,8,1);last=date(2026,9,16)
    amounts={'research':Decimal('45000'),'product':Decimal('20000'),'engineering':Decimal('30000')}
    rows=[]
    for name,total in amounts.items():
        unit=(total/15).quantize(Decimal('0.01'))
        for i in range((last-start).days):
            d=start+timedelta(days=i)
            value=total-unit*14 if d==date(2026,9,15) else unit
            known=datetime.combine(d+timedelta(days=1),datetime.min.time(),timezone.utc).isoformat()
            rows.append(dict(record_id=name+':'+d.isoformat(),source_id='billing',entity_id='team:'+name,
                             service_date=d.isoformat(),value=str(value),unit='USD',currency='USD',category='variable',
                             known_at=known,ingested_at=known,processed_at=known,revision=1,status='observed'))
    export=directory/'northstar-observations.json'
    export.write_text(json.dumps({'schema_version':'1.0','records':rows},indent=2)+'\n')
    target=dict(target_id='northstar-covered-variable',tenant_id='northstar',measure='provider_reported_cost',unit='USD',
                currency='USD',sources=['billing'],categories=['variable'])
    config=dict(schema_version='1.0',request=dict(request_id='northstar-demo-v1',target=target,as_of=origin.isoformat(),
                period_start='2026-09-01',period_end='2026-10-01',model='trailing_mean'),export=export.name,source_id='billing',
                history_start=start.isoformat(),coverage=[dict(source_id='billing',start=start.isoformat(),end=last.isoformat(),
                state='complete',maturity='finalized',known_at=origin.isoformat())],evidence_class='synthetic_fixture')
    config_path=directory/'northstar-config.json';config_path.write_text(json.dumps(config,indent=2)+'\n')
    return config_path


def run_demo(directory, *, fault=None):
    from .context import ContextLedger, SourceDocument, Citation, ContextEvent, NumericAssumption, workload_scenario
    from .consumers import BudgetState, FinanceStore
    notify=fault or (lambda stage: None)
    directory=Path(directory)
    if (directory/'redistribution.sqlite').exists() or (directory/'addition.sqlite').exists():
        raise ValueError('demo requires a fresh output directory to preserve independent original-budget alternatives')
    config=write_demo_inputs(directory)
    payload=forecast_from_config(config,directory/'forecasts.sqlite',fault=fault)
    notify('before_context')
    now=timestamp(payload['result']['as_of'])
    ledger=ContextLedger()
    facts=[('old-research','Research evaluation starts in October.',(),False,'informal'),
           ('research-plan','Approved research plan expands model-evaluation work in September.',('old-research',),True,'approved'),
           ('product-plan','Product launch moves into October, reducing planned near-term work.',(),True,'approved'),
           ('engineering-note','Engineering migration work continues through September.',(),False,'observed')]
    for event_id,text,supersedes,approved,status in facts:
        source=SourceDocument('northstar',event_id,'1',text,now-timedelta(days=1))
        ledger.add_source(source,('finance','factory'))
        event=ContextEvent('northstar',event_id,event_id,('research' if event_id=='old-research' else event_id.split('-')[0]),'plan',text,status,source.available_at,
                           (Citation(event_id,'1',0,len(text),text),),supersedes,approved)
        ledger.add_event(event)
    resolution=ledger.resolve('northstar','factory',now)
    dates=payload['entities']['team:research']['daily']
    scenario=workload_scenario(tuple((day(d),Decimal(v)) for d,v in dates.items()),as_of=now,
                              assumption=NumericAssumption('demo-finance','Explicit hypothetical 20% workload increase; not inferred from plans.',Decimal('1.20')),
                              configured_mappings=('user_workload_multiplier',))
    artifacts=ArtifactStore(directory/'forecasts.sqlite')
    context_scopes=('billing',)+tuple('context:'+event_id+':1' for event_id,_,_,_,_ in facts)
    context_id=artifacts.put('northstar','context_resolution',asdict(resolution),context_scopes)
    scenario_id=artifacts.put('northstar','scenario',{'base_forecast':payload['artifact_id'],**asdict(scenario)},('billing',))
    notify('after_context')
    decisions={}
    for kind,amounts,addition in [('redistribution',('85000','50000','65000'),'0'),('addition',('95000','80000','75000'),'50000')]:
        finance=FinanceStore(directory/(kind+'.sqlite'),'northstar')
        base=BudgetState('northstar',1,date(2026,9,1),date(2026,10,1),'USD',('variable','fixed'),
                         tuple(zip(('research','product','engineering'),map(Decimal,('60000','80000','60000')))))
        finance.initialize(base,recorded_spend=tuple(zip(('research','product','engineering'),map(Decimal,('45000','20000','30000')))))
        finance.grant_authority('demo-finance',policy_version='synthetic-policy-v1')
        finance.set_dependency('forecast',payload['artifact_id']);finance.set_dependency('plans',context_id)
        proposal=finance.prepare_proposal(after=tuple(zip(('research','product','engineering'),map(Decimal,amounts))),addition=Decimal(addition),
                                          business_requester='demo-finance',requester_kind='finance_instruction',assistant_proposer='demo-factory-adapter',
                                          rationale='Independent master-plan illustration; manual reviewed allocation under incomplete forecast coverage, no safe-transfer claim.',
                                          dependency_keys=('forecast','plans'),forecast_result_id=payload['artifact_id'])
        notify('before_review')
        review=finance.review(proposal.proposal_id,actor='demo-finance',now=now)
        notify('after_review')
        notify('before_apply')
        receipt=finance.apply(review.review_id,actor='demo-finance',idempotency_key=kind,now=now)
        notify('after_apply')
        decisions[kind]={'receipt_id':receipt.receipt_id,'operation':proposal.operation,
                         'after':{'envelope':str(receipt.after.envelope),'allocations':dict((k,str(v)) for k,v in receipt.after.allocations)},
                         'business_requester':receipt.business_requester,'assistant_proposer':receipt.assistant_proposer,'finance_approver':receipt.finance_approver}
    report={'schema_version':'1.0','evidence':'synthetic_fixture','forecast':payload,'context':asdict(resolution),
            'context_artifact_id':context_id,'scenario':asdict(scenario),'scenario_artifact_id':scenario_id,'decisions':decisions,
            'live_factory':'not_executed: credentials/runtime not supplied',
            'limitations':['Numerical projections are computed and differ from the master-plan illustrative placeholders.',
                           'Variable coverage and unknown late charges do not establish all-in headroom.',
                           'Reference review actors are fixtures, not authenticated production users.']}
    report=json.loads(canonical_json(report))
    (directory/'demo-report.json').write_text(json.dumps(report,indent=2)+'\n')
    return report
