"""Prospective vintages and observed revisions, never retrospective forecasts."""
from datetime import date
from decimal import Decimal
from test_forecast_outcomes import issued_outcome
from types import SimpleNamespace
import pytest
from app.forecasting.weekly_history import weekly_history

START=date(2026,10,19); END=date(2026,10,26)
NOW='2026-10-26T12:00:00Z'
DIMS=dict(quantity='spend',unit='USD',basis='planning',timezone='UTC',scope_type='company',scope_id='northstar',start=str(START),end=str(END))

def target(id='t1',run='r1',issued='2026-10-19T00:00:00Z',**changes):
    return dict(DIMS,target_id=id,run_id=run,issued_at=issued,information_cutoff=issued,aggregation='weekly',duration_days=7,prediction=100,is_synthetic=True,**changes)

def truth(t,revision=1,status='mature',value=110,**changes):
    return dict(DIMS,target_id=t['target_id'],revision=revision,status=status,value=value,available_at=NOW,mature_at=NOW,complete=status=='mature',is_synthetic=True,provenance={'kind':'observed','reference':'source-week'},source_id='actual-source',**changes)

class Store:
    def __init__(self,targets,truths,published=None,sequences=None):
        self.targets=targets;self.truths=truths;self.published=published or {};self.sequences=sequences or {}
    def input_records(self,cutoff,tenant_id='northstar',**kwargs):
        return [dict(kind='issued_targets',payload=t) for t in self.targets]+[dict(kind='truth_revisions',payload=t) for t in self.truths]
    def get_run(self,id):
        if ':' in id: raise KeyError(id)
        t=next(t for t in self.targets if t['run_id']==id)
        return {'job_id':id,'bundle':{'views':[{'scope':{'type':'company','id':'northstar'},'target':{'unit':'USD','quantity':'spend','basis':'planning','timezone':'UTC'},'publication':{'published_at':self.published.get(id,t['issued_at'])}}]}}

    def get_job(self,id):
        return {'sequence':self.sequences.get(id,0)}

def result(targets,truths=(),published=None,ledger=None,now=NOW,views=None,sequences=None):
    svc=SimpleNamespace(now=lambda:now,store=Store(targets,truths,published,sequences),views=lambda **kw:{'views':views or []})
    ledger=ledger or {'buckets':[],'dataset_revision':'ledger-r1','synthetic':True}
    return weekly_history(svc,ledger,scope_type='company',scope_id='northstar',start_date=START,end_date_exclusive=END)['weeks'][0]

def test_exact_observed_truth_supplies_same_actual_bar_and_positive_overrun():
    t=target();row=result([t],[truth(t)])
    assert row['prior_forecast']['amount']=='100'
    assert row['actual']['amount']=='110' and row['actual']['status']=='mature'
    assert row['variance']['amount']=='10' and row['variance']['status']=='available'

def test_latest_published_preweek_vintage_excludes_shadow_late_and_fence_loser():
    targets=[target('a','early','2026-10-18T00:00:00Z'),target('b','latest'),target('c','late','2026-10-20T00:00:00Z'),target('d','latest:shadow'),target('e','lost')]
    row=result(targets,published={'lost':None})
    assert row['prior_forecast']['target_id']=='b'

def test_historical_cutoff_cannot_backdate_real_issuance():
    t=target(issued='2026-10-26T00:00:00Z');t['information_cutoff']='2026-10-19T00:00:00Z'
    assert result([t])['prior_forecast'] is None

@pytest.mark.parametrize('status',['pending','disputed'])
def test_newer_unsettled_revision_withdraws_old_actual_and_variance(status):
    t=target();row=result([t],[truth(t),truth(t,revision=2,status=status)])
    assert row['actual']['amount'] is None and row['actual']['status']==status
    assert row['variance']['amount'] is None and row['actual']['corrected']

def test_future_maturity_and_dimension_mismatch_never_score():
    t=target();future=truth(t);future['mature_at']='2026-10-27T00:00:00Z'
    assert result([t],[future])['variance']['amount'] is None
    incompatible=truth(t);incompatible['unit']='TOKENS'
    assert result([t],[incompatible])['variance']['amount'] is None

def test_partial_first_forecast_week_never_compares_to_calendar_week():
    t=target();t.update(start='2026-10-25',duration_days=1)
    assert result([t])['prior_forecast'] is None

def test_ledger_subtotal_is_partial_and_cannot_become_forecast_error():
    ledger={'buckets':[{'date':'2026-10-19','recorded_spend':'12.34','source_refs':['batch1']}],'dataset_revision':'r2','synthetic':False}
    row=result([target()],ledger=ledger)
    assert row['actual']['amount']=='12.34' and row['actual']['status']=='partial'
    assert row['actual']['dataset_id']=='repository-ledger'
    assert row['variance']['amount'] is None

def test_current_week_never_claims_final_error_and_known_zero_remains_zero():
    t=target();z=truth(t,value=0);row=result([t],[z],now='2026-10-22T12:00:00Z')
    assert row['state']=='current' and row['variance']['amount'] is None
    row=result([t],[z]);assert row['actual']['amount']=='0' and row['variance']['amount']=='-100'


def test_weekly_history_http_native_and_compat_agree_and_validate_boundaries(client):
    query='?start_date=2026-10-19&end_date_exclusive=2026-11-02&scope_type=company&scope_id=northstar'
    native=client.get('/api/forecast-weekly-history'+query)
    compat=client.get('/compat/api/forecast-weekly-history'+query)
    assert native.status_code == 200, native.text
    assert native.json() == compat.json()
    assert len(native.json()['weeks']) == 2
    assert all(row['variance']['amount'] is None for row in native.json()['weeks'])
    assert client.get('/api/forecast-weekly-history?start_date=2026-10-20&end_date_exclusive=2026-11-02').status_code == 422


def test_real_archived_outcome_comparison_changes_without_refreshing_forecast(issued_outcome):
    client,service,worker,clock,t,job,bundle=issued_outcome
    from test_forecast_outcomes import _envelope
    query=f"?start_date={t['start']}&end_date_exclusive={t['end']}&scope_type=company&scope_id={t['scope_id']}"
    assert client.post('/api/forecast-outcomes',json=_envelope(t,clock)).status_code == 201
    row=client.get('/api/forecast-weekly-history'+query).json()['weeks'][0]
    assert row['prior_forecast']['run_id'] == job['run_id']
    assert Decimal(row['variance']['amount']) == Decimal('12')
    assert client.post('/api/forecast-outcomes',json=_envelope(t,clock,revision=2,status='disputed',complete=False)).status_code == 201
    row=client.get('/api/forecast-weekly-history'+query).json()['weeks'][0]
    assert row['actual']['amount'] is None and row['actual']['status']=='disputed'
    assert row['variance']['amount'] is None
    assert service.store.get_run(job['run_id'])['bundle'] == bundle


@pytest.mark.parametrize('change', [{'quantity':'tokens'}, {'timezone':'America/Los_Angeles'}])
def test_current_outlook_requires_same_financial_target(change):
    view={'scope':{'type':'company','id':'northstar'}, 'run_id':'current',
          'target':dict(unit='USD',basis='planning',quantity='spend',timezone='UTC',**{}),
          'publication':{'issued_at':'2026-10-20T00:00:00Z'},
          'weekly':[{'start':'2026-10-20','end':'2026-10-26','base':80,'complete':True}]}
    view['target'].update(change)
    row=result([],now='2026-10-22T12:00:00Z',views=[view])
    assert row['outlook'] is None


def test_partial_outlook_retains_supplied_span_and_explicit_incomplete_is_withheld():
    view={'scope':{'type':'company','id':'northstar'}, 'run_id':'current',
          'target':{'unit':'USD','basis':'planning','quantity':'spend','timezone':'UTC'},
          'publication':{'issued_at':'2026-10-20T00:00:00Z'},
          'weekly':[{'start':'2026-10-20','end':'2026-10-26','base':80,'complete':True}]}
    row=result([],now='2026-10-22T12:00:00Z',views=[view])
    assert row['outlook']['amount']=='80' and row['outlook']['partial']
    assert row['outlook']['start']=='2026-10-20' and row['variance']['amount'] is None
    view['weekly'][0]['complete']=False
    assert result([],now='2026-10-22T12:00:00Z',views=[view])['outlook'] is None


def test_company_scope_cannot_relabel_another_companys_ledger(client):
    response=client.get('/api/forecast-weekly-history?start_date=2026-10-19&end_date_exclusive=2026-10-26&scope_type=company&scope_id=another-company')
    assert response.status_code == 422


def test_late_publication_is_not_a_preweek_vintage_even_if_issued_timestamp_is_early():
    assert result([target()],published={'r1':'2026-10-20T00:00:00Z'})['prior_forecast'] is None


def test_numeric_truth_revision_order_and_correction_keep_frozen_prediction():
    t=target()
    row=result([t],[truth(t,revision=10,value=112),truth(t,revision=2,value=115)])
    assert row['prior_forecast']['amount']=='100'
    assert row['actual']['revision']=='10' and row['actual']['corrected']
    assert row['actual']['amount']=='112' and row['variance']['amount']=='12'


def test_equal_issue_timestamps_choose_latest_persisted_publication_sequence():
    older=target('z-older','old');newer=target('a-newer','new')
    row=result([older,newer],sequences={'old':1,'new':2})
    assert row['prior_forecast']['target_id']=='a-newer'
