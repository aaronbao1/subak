import pytest
from forecasting.replay_report import replay_cases


def builder(snapshot, *, run_id, generated_at, drivers):
    # A tiny deterministic serving procedure supplied through the public runner API.
    base=10+sum(d['parameters']['increment'] for d in drivers)
    return {'views':[{'scope':{'type':'company','id':'acme'},'daily':[{'start':'2025-01-06','end':'2025-01-07','base':base,'complete':True}]}]}


def extractor(envelope,snapshot):
    if envelope['text']=='malformed': raise ValueError('invalid source envelope')
    return envelope['drivers']


def cases():
    driver={'kind':'workload','scope':{},'effective_from':'2025-01-06','effective_to':None,'parameters':{'increment':2},'status':'eligible'}
    return [dict(id=str(i),snapshot={'information_cutoff':'2025-01-06T00:00:00+00:00'},
                 envelopes=[{'text':'malformed' if i==1 else 'valid','drivers':[driver]}],oracle_drivers=[driver],
                 actuals=[{'scope_type':'company','scope_id':'acme','aggregation':'daily','start':'2025-01-06','end':'2025-01-07','value':13}],
                 is_synthetic=True) for i in range(2)]


def test_replay_keeps_extraction_failure_in_opportunity_denominator():
    report=replay_cases(cases(),build_forecast=builder,extract_event=extractor)
    extracted=report['comparisons']['extracted_context']
    assert extracted['scheduled_cases']==2 and extracted['expected_targets']==2
    assert extracted['served_targets']==1 and extracted['availability']==.5 and extracted['conditional_mae']==1
    assert report['comparisons']['no_context']['conditional_mae']==3
    assert report['comparisons']['oracle_context']['conditional_mae']==1
    assert report['extraction']['exact_match_rate']==.5
    assert report['promotion_eligible'] is False
    assert report==replay_cases(cases(),build_forecast=builder,extract_event=extractor)


def test_missing_outcomes_cannot_turn_into_accuracy_evidence():
    inputs=cases()[:1]; inputs[0]['actuals']=[]
    report=replay_cases(inputs,build_forecast=builder,extract_event=extractor)
    assert report['comparisons']['extracted_context']['conditional_mae'] is None
    assert report['comparisons']['extracted_context']['expected_targets']==0
    assert report['comparisons']['extracted_context']['availability'] is None


def test_direct_weekly_challengers_fit_observed_totals_without_daily_allocation():
    from datetime import date,timedelta
    from forecasting.replay_report import direct_weekly_challenger
    first=date(2025,1,6)
    snapshot={'tenant_id':'acme','information_cutoff':'2025-01-20T00:00:00Z','forecast_start':'2025-01-20','history_complete_through':'2025-01-19','target':{'unit':'USD','timezone':'UTC'},'required_sources':['ledger'],'coverage':[],'observations':[],
              'pricing':[{'id':'rate','version':1,'billing_pool':'pool','unit':'tokens','currency':'USD','mode':'linear','rate':2,'allowance':0,'fixed':0,'complete_pool':True,'period_start':'2025-01-01','period_end':'2025-02-01','known_at':'2025-01-01T00:00:00Z'}]}
    for i in range(14):
        day=first+timedelta(days=i)
        snapshot['coverage'].append({'date':str(day),'source_id':'ledger','complete':True})
        snapshot['observations'].append({'date':str(day),'source_id':'ledger','source_revision':1,'billing_pool':'pool','configuration_id':'model','meter':'tokens','quantity':10 if i<7 else 20,'complete':True,'mature':True,'available_at':str(day+timedelta(days=1))+'T00:00:00Z'})
    targets=[{'scope_type':'company','scope_id':'acme','aggregation':'weekly','start':'2025-01-20','end':'2025-01-27','value':250}]
    mean=direct_weekly_challenger(snapshot,targets,method='weekly_mean')
    last=direct_weekly_challenger(snapshot,targets,method='weekly_last')
    assert mean['views'][0]['weekly'][0]['base']==210
    assert last['views'][0]['weekly'][0]['base']==280
    assert mean['views'][0].get('daily',[])==[]
    assert mean['method']['training_weeks']==2
    snapshot['observations'].append(dict(snapshot['observations'][0],source_revision=2,quantity=999,available_at='2025-02-01T00:00:00Z'))
    assert direct_weekly_challenger(snapshot,targets,method='weekly_mean')['views'][0]['weekly'][0]['base']==210
    snapshot['coverage'].append({'date':'2025-01-06','source_id':'ledger','revision':2,'complete':False,'available_at':'2025-01-20T00:00:00Z'})
    with pytest.raises(ValueError,match='insufficient complete'):
        direct_weekly_challenger(snapshot,targets,method='weekly_mean')
    snapshot['coverage'].pop()
    snapshot['pricing'][0]['mode']='volume'
    with pytest.raises(ValueError,match='complete.*linear|linear.*complete'):
        direct_weekly_challenger(snapshot,targets,method='weekly_mean')
