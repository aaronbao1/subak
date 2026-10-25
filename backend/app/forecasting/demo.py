"""Executable Northstar acceptance journey using the real product API and worker.

Run from the repository root with PYTHONPATH=src:backend:agent. The clock,
observed history and connector messages are synthetic; no API keys are needed.
"""
from __future__ import annotations
import argparse
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import json
from pathlib import Path

from fastapi.testclient import TestClient
from app.config import Settings
from app.core.clock import FrozenClock, SequentialIdFactory
from app.main import create_app
from app.seed.northstar import seed
from app.services.imports import run_import
from forecasting.learning import score_issued_intervals
from .fixtures import build_northstar_snapshot, northstar_evidence, northstar_spending_records


def _write(directory, name, value):
    (directory/name).write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False)+'\n')


def observed_inputs(*, now, tenant_id='northstar'):
    """History is observed independently; messages enter only through ingestion."""
    snapshot=build_northstar_snapshot(now=now,tenant_id=tenant_id)
    snapshot['drivers']=[]
    snapshot['evidence']=[]
    return snapshot


def create_demo_app(directory, clock, *, worker=False):
    app=create_app(Settings(db_path=Path(directory)/'app.db',forecast_provider='engine',forecast_demo=True,
                            forecast_worker=worker),clock=clock)
    app.state.forecast_service.snapshot_factory=observed_inputs
    return app


def import_observed_actuals(app, snapshot, clock):
    """Keep the finance ledger on the same observed days, with explicit cent rounding."""
    records=[]
    for row in northstar_spending_records(snapshot):
        records.append({'record_id':row['id'],'occurred_at':row['date']+'T00:00:00Z',
            'source_account':'ws-'+row['teamId'],'cost_category':'direct_api','value_kind':'simulated',
            'amount':str(Decimal(str(row['amount'])).quantize(Decimal('.01'))),'unit':'USD',
            'provider':'Northstar synthetic fixture','model':'classic'})
    with app.state.session_factory() as session:
        result=run_import(session,source_kind='northstar_billing',raw=json.dumps(records).encode(),filename='fixture-actuals.json',
                          actor_id='fixture',clock=clock,ids=app.state.id_factory,value_kind_default='simulated')
        if result.batch.status not in {'imported','duplicate'}:
            raise RuntimeError(result.batch.error_details)
        session.commit()
    return sum((Decimal(row['amount']) for row in records),Decimal(0))


def run_demo(output_dir):
    directory=Path(output_dir)
    directory.mkdir(parents=True,exist_ok=True)
    if (directory/'app.db').exists():
        raise ValueError('Use a fresh output directory; the demo never replaces an existing database.')
    clock=FrozenClock(datetime(2026,10,26,tzinfo=timezone.utc))
    app=create_demo_app(directory,clock)
    app.state.id_factory=SequentialIdFactory()
    service=app.state.forecast_service
    # The connector messages are delivered explicitly below. Input history never
    # auto-includes a message merely because its upstream timestamp is earlier.
    history=observed_inputs(now=clock.now().isoformat())
    _write(directory,'northstar-history.json',history)
    _write(directory,'connector-events.json',northstar_evidence())
    # Populate the legacy actual-charge ledger from the same observed fixture.
    # MoneyType stores cents; fine-grained native estimates retain their original precision.
    with app.state.session_factory() as session:
        seed(session,clock=clock,ids=app.state.id_factory,include_spend=False)
    import_observed_actuals(app,history,clock)
    checks={}
    with TestClient(app) as client:
        first=client.post('/api/forecast-refreshes',headers={'Idempotency-Key':'demo-initial'}).json()
        assert app.state.forecast_worker.process_one(job_id=first['id'])
        initial=service.store.get_run(first['run_id'])['bundle']
        _write(directory,'initial-forecast.json',initial)
        company=next(v for v in initial['views'] if v['scope']['type']=='company')
        by_id={view['id']:view for view in initial['views']}
        partitions=company.get('reconciliation',{})
        checks['coherent_company_team_person_shared']=(set(partitions)=={'people','teams'} and all(
            abs(sum(by_id[scope]['quarter_outlook']['base'] for scope in part['scope_ids'])
                -company['quarter_outlook']['base'])<1e-7 for part in partitions.values()))
        checks['seven_daily_four_weekly']=len(company['daily'])==7 and len(company['weekly'])==4
        for envelope in northstar_evidence():
            response=client.post('/api/forecast-evidence',json=envelope)
            assert response.status_code==201,response.text
        evidence=client.get('/api/forecast-evidence').json()
        checks['automatic_extraction_queued']=any(d.get('queue_status')=='queued' for item in evidence['items'] for d in item.get('drivers',[]))
        checks['release_and_ambiguity_context_only']=sum(d.get('status')=='context_only' for item in evidence['items'] for d in item.get('drivers',[]))>=2
        checks['published_curve_unchanged_while_queued']=service.store.get_run(first['run_id'])['bundle']==initial and service.store.publication()['run_id']==first['run_id']
        refresh=client.post('/api/forecast-refreshes',headers={'Idempotency-Key':'demo-after-evidence'}).json()
        assert app.state.forecast_worker.process_one(job_id=refresh['id'])
        published=service.store.get_run(refresh['run_id'])['bundle']
        company2=next(v for v in published['views'] if v['scope']['type']=='company')
        checks['new_immutable_run_changes_supported_work']=first['run_id']!=refresh['run_id'] and company2['quarter_outlook']['base']!=company['quarter_outlook']['base'] and service.store.get_run(first['run_id'])['bundle']==initial
        # The release has no numerical effect; the schedule, adoption and tariff
        # explanations cite both their stored passage and deterministic calculation.
        driver=next(d for d in company2['included_drivers'] if d['kind']=='project_schedule')
        explanation=client.get('/api/forecast-runs/'+refresh['run_id']+'/explanation',params={'driver_id':driver['id']}).json()
        context={'action':'explain','run_id':refresh['run_id'],'scope_type':'company','scope_id':'northstar','driver_id':driver['id']}
        answer=client.post('/compat/api/threads/acceptance/messages',json={'content':'Why did this forecast change?', 'forecast_context':context}).json()[-1]
        calculation=next(c for c in explanation['calculations'] if c.get('driver_id')==driver['id'])
        citation=driver['citations'][0]
        checks['droid_matches_calculation_and_source']=(driver['id'] in answer['content']
            and refresh['run_id'] in answer['content']
            and str(calculation['base_delta']) in answer['content']
            and citation['quote'] in answer['content']
            and f"Source {citation['source_id']} revision {citation['source_revision']}" in answer['content'])
        preview=client.post('/api/forecast-runs/'+refresh['run_id']+'/scenarios',json={'drivers':[d for d in company2['included_drivers'] if d['id']!=driver['id']]}).json()
        checks['isolated_scenario']=preview['parent_run_id']==refresh['run_id'] and service.store.publication()['run_id']==refresh['run_id'] and service.store.get_run(refresh['run_id'])['bundle']==published
        _write(directory,'published-forecast.json',published)
        _write(directory,'explanation.json',explanation)
        _write(directory,'droid-answer.json',answer)
        _write(directory,'scenario.json',preview)
        # Independent synthetic observations mature one week later. No forecast
        # values or inferred driver assumptions become the observed outcome.
        clock.advance(days=7)
        observed=observed_inputs(now=clock.now().isoformat())
        expected_ledger=import_observed_actuals(app,observed,clock)
        checks['current_ledger_matches_observed_days']=Decimal(client.get('/api/spend/summary').json()['company_total'])==expected_ledger
        realized=sum(Decimal(str(r['quantity']))*Decimal('0.000018') for r in observed['observations']
                     if '2026-10-26'<=r['date']<'2026-11-02')
        issued=[r['payload'] for r in service.store.input_records(clock.now().isoformat()) if r['kind']=='issued_targets']
        matching=[r for r in issued if r['run_id'].startswith(refresh['run_id']) and r['scope_type']=='company' and r['aggregation']=='weekly' and r['start']=='2026-10-26' and r['end']=='2026-11-02']
        truth=[]
        for target in matching:
            outcome=dict(target_id=target['target_id'],revision=1,available_at=clock.now().isoformat(),mature_at=clock.now().isoformat(),status='mature',value=float(realized),source_id='northstar-observed-week-2026-10-26',is_synthetic=True,complete=True,
                         provenance={'kind':'observed','reference':'northstar-independent-observed-usage-week-2026-10-26'},
                         **{key:target[key] for key in ('quantity','unit','basis','timezone','scope_type','scope_id','start','end')})
            receipt=client.post('/api/forecast-outcomes',json=outcome)
            if receipt.status_code!=201:
                raise RuntimeError('Observed outcome ingestion failed: '+receipt.text)
            truth.append(receipt.json()['outcome'])
        scores=score_issued_intervals(issued,truth,cutoff=clock.now().isoformat())
        next_job=service.refresh('demo-next-week')
        assert app.state.forecast_worker.process_one(job_id=next_job['id'])
        next_bundle=service.store.get_run(next_job['run_id'])['bundle']
        def monday_rate(bundle):
            rates=next(c for c in bundle['calculations'] if c['id']=='calculation:rates')
            return next(c for c in rates['components'] if c['component']['person_id']=='maya')['rates']['0']['base']
        training_start=(clock.now().date()-timedelta(days=56)).isoformat()
        mondays=[r for r in observed['observations'] if r['person_id']=='maya'
                 and r['date']>=training_start and date.fromisoformat(r['date']).weekday()==0]
        expected_rate=sum(r['quantity'] for r in mondays)/sum(r['exposure'] for r in mondays)
        checks['mature_outcomes_score_and_refit']=(scores['weekly']['scored']>=1
            and abs(monday_rate(next_bundle)-expected_rate)<1e-8
            and monday_rate(next_bundle)!=monday_rate(published))
        errors=[r['payload'] for r in service.store.input_records(clock.now().isoformat()) if r['kind']=='forecast_errors']
        checks['immutable_error_receipts_persisted']=any(r['state']=='scored' for r in errors)
        checks['synthetic_cannot_promote']=not next_bundle['model_registry']['decision']['promote']
        checks['current_actuals_separate_from_issued']=service.views(run_id=refresh['run_id'])['current_actuals']['history_complete_through']>'2026-10-25' and service.store.get_run(refresh['run_id'])['bundle']==published
        _write(directory,'observed-truth.json',truth)
        _write(directory,'learning-scores.json',scores)
        _write(directory,'error-receipts.json',errors)
        _write(directory,'next-week-forecast.json',next_bundle)
    report=dict(passed=all(checks.values()),checks=checks,initial_run_id=first['run_id'],published_run_id=refresh['run_id'],next_run_id=next_job['run_id'],scenario_id=preview['scenario_id'],
                initial_quarter=company['quarter_outlook']['base'],published_quarter=company2['quarter_outlook']['base'],
                truth_source='independent synthetic observed usage, not forecast output',is_synthetic=True,
                limitations=['Connector-shaped fixtures; no live authenticated connector or live Droid request.',
                             'Synthetic replay demonstrates mechanics and cannot establish enterprise accuracy.',
                             'All receipts use UTC; a frozen midnight clock keeps the demo complete and deterministic.'])
    _write(directory,'report.json',report)
    if not report['passed']: raise AssertionError(report['checks'])
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',default='artifacts/forecast-integration')
    parser.add_argument('--serve',action='store_true',help='After the acceptance journey, serve its database at a frozen November 2 clock.')
    parser.add_argument('--port',type=int,default=8787)
    args=parser.parse_args()
    print(json.dumps(run_demo(args.output_dir),indent=2))
    if args.serve:
        import uvicorn
        clock=FrozenClock(datetime(2026,11,2,tzinfo=timezone.utc))
        uvicorn.run(create_demo_app(args.output_dir,clock,worker=True),host='127.0.0.1',port=args.port)


if __name__=='__main__': main()
