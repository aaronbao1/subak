from copy import deepcopy
from datetime import date, timedelta
import pytest
from forecasting import learning


def target(i=0, **changes):
    start = date(2025, 1, 6) + timedelta(days=7*i)
    result = dict(target_id=f't{i}', run_id=f'r{i}', issued_at=start.isoformat()+'T00:00:00+00:00',
                  origin=start.isoformat(), start=start.isoformat(), end=(start+timedelta(days=7)).isoformat(),
                  lead_days=0,duration_days=7,aggregation='weekly',scope_type='company',scope_id='acme',
                  unit='USD',basis='planning',timezone='UTC',procedure_id='v1',history_delay_days=0,
                  prediction=100.,is_synthetic=False)
    result.update(changes)
    return result


def truth(t, error, revision=1, **changes):
    out=dict(target_id=t['target_id'], revision=revision, available_at=t['end']+'T00:00:00+00:00',
             mature_at=t['end']+'T00:00:00+00:00',status='mature',value=100.+error,source_id='ledger',is_synthetic=False)
    out.update(changes)
    return out


def test_rank_exact_matching_and_corrected_truth_are_as_of():
    issued=[target(i) for i in range(4)]
    truths=[truth(t,i+1) for i,t in enumerate(issued)]
    future=target(40)
    r=learning.historical_error_interval(future,issued,truths,cutoff=future['issued_at'])
    assert (r['lower'],r['upper'],r['n'],r['rank']) == (96.,104.,4,4)
    assert r['coverage']==.8 and r['qualification']
    assert learning.historical_error_interval(future,issued,truths,cutoff=future['issued_at'],coverage=.95)['lower'] is None
    wrong=target(4,lead_days=1,origin='2025-02-02')
    assert learning.historical_error_interval(future,issued+[wrong],truths+[truth(wrong,999)],cutoff=future['issued_at'])['n']==4
    correction=truth(issued[-1],20,2,available_at='2025-08-01T00:00:00+00:00',mature_at='2025-08-01T00:00:00+00:00')
    assert learning.historical_error_interval(future,issued,truths+[correction],cutoff='2025-07-01T00:00:00+00:00')['upper']==104.
    assert learning.historical_error_interval(future,issued,truths+[correction],cutoff=future['issued_at'])['upper']==120.


def test_latest_pending_revision_withdraws_old_truth_and_overlap_is_deterministic():
    issued=[target(i) for i in range(5)]
    truths=[truth(t,1) for t in issued]
    duplicate=target(0,target_id='duplicate',run_id='later',issued_at='2025-01-06T01:00:00+00:00')
    r=learning.historical_error_interval(target(40),list(reversed(issued+[duplicate])),truths+[truth(duplicate,999)],cutoff='2025-10-20T00:00:00+00:00')
    assert r['n']==5 and r['upper']==101 and r['excluded_overlap']==1
    withdrawn=truth(issued[0],99,2,status='pending')
    assert learning.historical_error_interval(target(40),issued,truths+[withdrawn],cutoff='2025-10-20T00:00:00+00:00')['n']==4


def test_archive_uses_final_priced_bases_and_does_not_mix_aggregations():
    snapshot=dict(is_synthetic=True,forecast_start='2025-01-06',history_complete_through='2025-01-06')
    row=dict(start='2025-01-06',end='2025-01-13',base=123,low=70,high=200,complete=True)
    view=dict(run_id='r',scope={'type':'company','id':'acme'},target={'unit':'USD','basis':'planning'},timezone='UTC',procedure_version='v1',publication={'generated_at':'2025-01-06T00:00:00+00:00','forecast_start':'2025-01-06','history_complete_through':'2025-01-06'},daily=[],weekly=[row],cumulative=[row])
    rows=learning.archive_issued_targets({'views':[view]},snapshot)
    assert len(rows)==2 and {x['prediction'] for x in rows}=={123}
    assert len({x['target_id'] for x in rows})==2 and all(x['is_synthetic'] for x in rows)
    assert rows==learning.archive_issued_targets({'views':[view]},snapshot)


def test_invalid_conflicting_truth_and_nonfinite_derived_values_rejected():
    t=target()
    with pytest.raises(ValueError):
        learning.historical_error_interval(target(40),[t],[truth(t,1),truth(t,2)],cutoff='2025-10-20T00:00:00+00:00')
    with pytest.raises(ValueError):
        learning.historical_error_interval(target(40),[target(prediction=float('inf'))],[],cutoff='2025-10-20T00:00:00+00:00')


def policy_rows(synthetic=False):
    rows=[]
    for i in range(32):
        for name,error in [('serving',3),('shadow',1),('seasonal_naive',5)]:
            rows.append(dict(week=(date(2024,1,1)+timedelta(days=7*i)).isoformat(),procedure_id=name,phase='calibration' if i<20 else 'prospective',weekly_company_mae=error,daily_mae=error,interval_score_80=error,interval_score_95=error,wis=error,misses_80=0,misses_95=0,availability=1,invariant_failures=0,is_synthetic=synthetic,reconstructible=True,input_manifest='sha256:abc',mature=True))
    for row in rows:
        row['policy_id']=policy()['policy_id']
        row['issued_at']=row['week']+'T00:00:00+00:00'
        row['information_cutoff']=row['issued_at']
    return rows


def policy():
    return learning.freeze_policy('serving','shadow',{'model':'weekday'},frozen_at='2023-12-01T00:00:00+00:00',calibration_start='2024-01-01',prospective_start='2024-05-20',prospective_end='2024-08-12')


def test_gate_requires_frozen_20_plus_12_genuine_weeks_and_all_metrics():
    p=policy()
    assert learning.promotion_decision(p,policy_rows())['promote'] is True
    assert learning.promotion_decision(p,policy_rows(True))['promote'] is False
    assert learning.promotion_decision(p,policy_rows()[:-1])['promote'] is False
    bad=policy_rows(); bad[-2]['daily_mae']=999
    assert learning.promotion_decision(p,bad)['promote'] is False
    tied=policy_rows()
    for r in tied:
        if r['procedure_id']=='shadow': r['weekly_company_mae']=3
    assert learning.promotion_decision(p,tied)['promote'] is False
    mutated=deepcopy(p); mutated['candidate_config']['model']='changed'
    with pytest.raises(ValueError): learning.promotion_decision(mutated,policy_rows())


def test_enrichment_archives_actual_bounds_and_scores_without_refitting():
    issued=[target(i) for i in range(4)]
    truths=[truth(t, i+1) for i,t in enumerate(issued)]
    t=target(40)
    t['intervals']={'80':{'lower':96,'upper':104},'95':{'lower':90,'upper':110}}
    scores=learning.score_issued_intervals([t],[truth(t,8)],cutoff='2026-01-01T00:00:00+00:00')
    assert scores['weekly']['intervals']['80']['coverage']==0
    assert scores['weekly']['intervals']['80']['interval_score']==48
    assert scores['weekly']['intervals']['95']['coverage']==1
    assert scores['weekly']['wis']==pytest.approx(3.72)


def test_daily_cumulative_negative_lead_scores_same_issued_truth():
    t=target(4,aggregation='cumulative',origin='2025-02-04',lead_days=-1)
    t['intervals']={'80':{'lower':96,'upper':104},'95':{'lower':90,'upper':110}}
    assert learning.score_issued_intervals([t],[truth(t,2)],cutoff='2026-01-01T00:00:00+00:00')['cumulative']['scored']==1


def test_synthetic_errors_cannot_calibrate_real_company_targets():
    issued=[target(i,is_synthetic=True) for i in range(20)]
    truths=[truth(t,1,is_synthetic=True) for t in issued]
    r=learning.historical_error_interval(target(40),issued,truths,cutoff='2026-01-01T00:00:00+00:00')
    assert r['n']==0 and r['lower'] is None


def test_gate_rejects_retrospective_or_different_policy_evidence():
    p=policy(); rows=policy_rows()
    for row in rows:
        row['policy_id']=p['policy_id']
        row['issued_at']=row['week']+'T00:00:00+00:00'
    rows[-2]['issued_at']='2025-01-01T00:00:00+00:00'
    assert learning.promotion_decision(p,rows)['promote'] is False
    rows[-2]['issued_at']=rows[-2]['week']+'T00:00:00+00:00'
    rows[-2]['policy_id']='other experiment'
    assert learning.promotion_decision(p,rows)['promote'] is False


def test_registry_freezes_candidate_and_retains_without_genuine_mature_evidence():
    snapshot={'is_synthetic':True,'issued_targets':[],'truth_revisions':[]}
    registry=learning.update_model_registry(snapshot,generated_at='2026-10-26T00:00:00+00:00')
    assert registry['serving']['window_days']==56 and registry['shadow']['window_days']==28
    assert registry['reference']['kind']=='seasonal_naive'
    assert registry['decision']['decision']=='retain_incumbent'
    assert registry['policy']['minimum_calibration_weeks']==20
    second=learning.update_model_registry(dict(snapshot,model_registry=registry),generated_at='2026-11-02T00:00:00+00:00')
    assert second['version']==registry['version'] and second==registry
    assert registry['decision']['reasons']


def test_build_learning_bundle_archives_serving_shadow_and_reference_without_publishing_shadow():
    from forecasting.planning import build_forecast
    # Empty verified coverage leads to unavailable forecasts, but preserves the
    # executed independent procedures and retention diagnostics.
    snapshot={'id':'empty','tenant_id':'acme','information_cutoff':'2026-10-26T00:00:00+00:00','forecast_start':'2026-10-26','history_complete_through':'2026-10-25','period_start':'2026-10-01','period_end':'2027-01-01','target':{'unit':'USD','quantity':'spend','basis':'planning','timezone':'UTC'},'observations':[],'required_sources':['ledger'],'coverage':[],'people':[],'memberships':[],'projects':[],'configurations':[],'pricing':[],'is_synthetic':True}
    snapshot['model_registry']=learning.update_model_registry(snapshot,generated_at=snapshot['information_cutoff'])
    result=learning.build_learning_bundle(snapshot,run_id='test',generated_at=snapshot['information_cutoff'],builder=build_forecast)
    assert len(result['learning_runs'])==3
    assert {x['role'] for x in result['learning_runs']}=={'serving','shadow','reference'}
    assert result['run_id']=='test'
    assert all(v['procedure_id']==snapshot['model_registry']['serving']['id'] for v in result['views'])


def genuine_archive(snapshot,registry):
    issued=[]; truths=[]
    start=date.fromisoformat(registry['policy']['calibration_start'])
    for i in range(32):
        week=start+timedelta(weeks=i)
        for role,error in [('serving',3.),('shadow',1.),('reference',5.)]:
            procedure=registry[role]['id']; run=f'{i}:{role}'
            for offset in [-1,0,1,2,3,4,5,6]:
                weekly=offset==-1; begin=week if weekly else week+timedelta(days=offset)
                end=begin+timedelta(days=7 if weekly else 1)
                prediction=100+error if weekly else (100+error)/7
                value=100 if weekly else 100/7
                row=target(i,target_id=f'{run}:{offset}',run_id=run,issued_at=week.isoformat()+'T00:00:00+00:00',origin=str(week),start=str(begin),end=str(end),lead_days=0 if weekly else offset,duration_days=7 if weekly else 1,aggregation='weekly' if weekly else 'daily',procedure_id=procedure,prediction=prediction,snapshot_id=f'snapshot:{i}',input_manifest=f'sha256:{i}',policy_id=registry['policy']['policy_id'],implementation_sha256=registry['policy']['implementation_sha256'])
                if i>=20: row['intervals']={'80':{'lower':prediction-10,'upper':prediction+10},'95':{'lower':prediction-20,'upper':prediction+20}}
                issued.append(row); truths.append(truth(row,0,value=value))
    return dict(snapshot,model_registry=registry,issued_targets=issued,truth_revisions=truths)


def test_registry_promotes_only_from_reconstructed_prospective_archive():
    snapshot={'is_synthetic':False,'issued_targets':[],'truth_revisions':[]}
    registry=learning.update_model_registry(snapshot,generated_at='2024-01-01T00:00:00+00:00')
    observed=genuine_archive(snapshot,registry)
    updated=learning.update_model_registry(observed,generated_at='2025-01-01T00:00:00+00:00')
    assert updated['decision']['promote'] is True
    assert updated['serving']==registry['shadow'] and updated['version']==2
    observed['truth_revisions'][-1]['status']='disputed'
    updated=learning.update_model_registry(observed,generated_at='2025-01-01T00:00:00+00:00')
    assert updated['decision']['promote'] is False and updated['serving']==registry['serving']


def test_registry_cannot_promote_incoherent_weekly_and_daily_targets():
    snapshot={'is_synthetic':False,'issued_targets':[],'truth_revisions':[]}
    registry=learning.update_model_registry(snapshot,generated_at='2024-01-01T00:00:00+00:00')
    observed=genuine_archive(snapshot,registry)
    row=next(r for r in observed['issued_targets'] if r['procedure_id']==registry['shadow']['id'] and r['aggregation']=='daily' and r['origin']>=registry['policy']['prospective_start'])
    row['prediction']=0
    assert learning.update_model_registry(observed,generated_at='2025-01-01T00:00:00+00:00')['decision']['promote'] is False


def test_interval_scoring_does_not_pool_units_or_target_strata():
    a=target(0); b=target(1,unit='tokens')
    for row in (a,b): row['intervals']={'80':{'lower':90,'upper':110},'95':{'lower':80,'upper':120}}
    result=learning.score_issued_intervals([a,b],[truth(a,1),truth(b,2)],cutoff='2026-01-01T00:00:00+00:00')['weekly']
    assert result['wis'] is None and len(result['strata'])==2
    assert {group['stratum']['unit'] for group in result['strata']}=={'USD','tokens'}


def test_historical_interval_reports_only_previously_issued_interval_scores():
    issued=[target(i) for i in range(4)]
    for row in issued: row['intervals']={'80':{'lower':90,'upper':110},'95':{'lower':80,'upper':120}}
    result=learning.historical_error_interval(target(40),issued,[truth(t,i+1) for i,t in enumerate(issued)],cutoff='2026-01-01T00:00:00+00:00')
    assert result['empirical']['coverage']==1
    assert result['empirical']['interval_score']==20
    assert result['empirical']['wis']==pytest.approx(1.7)
    assert result['empirical']['wis_count']==4


def test_frozen_publication_grace_accepts_compute_latency_but_not_future_information():
    rows=policy_rows(); p=policy()
    for row in rows:
        row['issued_at']=row['week']+'T00:04:59+00:00'
        row['information_cutoff']=row['week']+'T00:00:00+00:00'
    assert learning.promotion_decision(p,rows)['promote'] is True
    rows[-2]['information_cutoff']=rows[-2]['week']+'T00:00:01+00:00'
    assert learning.promotion_decision(p,rows)['promote'] is False
    rows[-2]['information_cutoff']=rows[-2]['week']+'T00:00:00+00:00'
    rows[-2]['issued_at']=rows[-2]['week']+'T00:05:01+00:00'
    assert learning.promotion_decision(p,rows)['promote'] is False


def test_code_artifact_change_requires_new_frozen_experiment():
    p=policy(); rows=policy_rows()
    # Simulate a different immutable source artifact while preserving a valid
    # policy digest, as an older deployed experiment would have.
    p['implementation_sha256']='prior-code-artifact'
    p['policy_id']=learning._digest({k:v for k,v in p.items() if k!='policy_id'})
    for row in rows: row['policy_id']=p['policy_id']
    result=learning.promotion_decision(p,rows)
    assert result['promote'] is False
    assert any('implementation' in reason for reason in result['reasons'])


def test_error_receipts_append_correction_and_withdrawal_without_erasing_history():
    t=target(); first=truth(t,3)
    snapshot={'issued_targets':[t],'truth_revisions':[first]}
    receipts=learning.score_error_receipts(snapshot,cutoff='2025-01-13T00:00:00+00:00')
    assert len(receipts)==1 and receipts[0]['absolute_error']==3
    assert receipts[0]['state']=='scored' and receipts[0]['truth_revision']==1
    original=deepcopy(receipts[0])
    pending=truth(t,99,2,status='pending',available_at='2025-01-14T00:00:00+00:00',mature_at='2025-01-20T00:00:00+00:00')
    snapshot.update(forecast_errors=receipts,truth_revisions=[first,pending])
    withdrawal=learning.score_error_receipts(snapshot,cutoff='2025-01-15T00:00:00+00:00')
    assert len(withdrawal)==1 and withdrawal[0]['state']=='withdrawn'
    assert withdrawal[0]['absolute_error'] is None
    assert receipts[0]==original
    history=receipts+withdrawal
    current=learning.current_error_records(history,cutoff='2025-01-15T00:00:00+00:00')
    assert current[t['target_id']]['state']=='withdrawn'
    assert learning.current_error_records(history,cutoff='2025-01-13T00:00:00+00:00')[t['target_id']]['absolute_error']==3
    correction=truth(t,7,3,available_at='2025-01-16T00:00:00+00:00',mature_at='2025-01-22T00:00:00+00:00')
    snapshot.update(forecast_errors=history,truth_revisions=[first,pending,correction])
    awaiting=learning.score_error_receipts(snapshot,cutoff='2025-01-17T00:00:00+00:00')
    assert len(awaiting)==1 and awaiting[0]['state']=='awaiting_maturity'
    history+=awaiting; snapshot['forecast_errors']=history
    corrected=learning.score_error_receipts(snapshot,cutoff='2025-01-22T00:00:00+00:00')
    assert len(corrected)==1 and corrected[0]['absolute_error']==7
    history+=corrected; snapshot['forecast_errors']=history
    assert learning.current_error_records(history,cutoff='2025-01-22T00:00:00+00:00')[t['target_id']]['truth_revision']==3
    assert learning.score_error_receipts(snapshot,cutoff='2025-02-01T00:00:00+00:00')==[]
    assert history[0]==original


def test_error_receipts_reject_conflicting_revisions_and_do_not_cross_evidence_populations():
    t=target()
    with pytest.raises(ValueError,match='conflicting truth'):
        learning.score_error_receipts({'issued_targets':[t],'truth_revisions':[truth(t,1),truth(t,2)]},cutoff='2026-01-01T00:00:00+00:00')
    receipts=learning.score_error_receipts({'issued_targets':[t],'truth_revisions':[truth(t,2,is_synthetic=True)]},cutoff='2026-01-01T00:00:00+00:00')
    assert receipts[0]['state']=='incompatible_evidence' and receipts[0]['absolute_error'] is None


def test_current_error_projection_rejects_conflicting_receipt_identity():
    t=target()
    receipt=learning.score_error_receipts({'issued_targets':[t],'truth_revisions':[truth(t,1)]},cutoff='2026-01-01T00:00:00+00:00')[0]
    conflicting=dict(receipt,receipt_id='different-delivery-id',absolute_error=2)
    with pytest.raises(ValueError,match='conflicting'):
        learning.current_error_records([receipt,conflicting],cutoff='2026-01-01T00:00:00+00:00')


def test_extraction_dependencies_change_issued_identity_and_separate_calibration():
    old_dependencies={'evidence_extraction':{'version':'native-envelope-v1','sha256':'old-parser'}}
    new_dependencies={'evidence_extraction':{'version':'native-envelope-v1','sha256':'new-parser'}}
    snapshot=dict(is_synthetic=False,forecast_start='2025-01-06',history_complete_through='2025-01-06',procedure_dependencies=old_dependencies)
    view=dict(run_id='r',scope={'type':'company','id':'acme'},target={'unit':'USD','basis':'planning'},timezone='UTC',procedure_version='v1',publication={'generated_at':'2025-01-06T00:00:00+00:00','forecast_start':'2025-01-06','history_complete_through':'2025-01-06'},daily=[],weekly=[dict(start='2025-01-06',end='2025-01-13',base=100,complete=True)],cumulative=[])
    before=learning.archive_issued_targets({'views':[view]},snapshot)[0]
    after=learning.archive_issued_targets({'views':[view]},dict(snapshot,procedure_dependencies=new_dependencies))[0]
    assert before['implementation_sha256']!=after['implementation_sha256']
    assert before['effective_procedure_id']!=after['effective_procedure_id']
    assert before['procedure_dependencies']==old_dependencies
    issued=[target(i,implementation_sha256=before['implementation_sha256']) for i in range(4)]
    truths=[truth(t,2) for t in issued]
    future=target(40,implementation_sha256=before['implementation_sha256'])
    assert learning.historical_error_interval(future,issued,truths,cutoff='2026-01-01T00:00:00Z')['n']==4
    future['implementation_sha256']=after['implementation_sha256']
    changed=learning.historical_error_interval(future,issued,truths,cutoff='2026-01-01T00:00:00Z')
    assert changed['n']==0 and changed['lower'] is None
    enriched=learning.enrich_intervals({'views':[view]},dict(snapshot,procedure_dependencies=new_dependencies))
    assert enriched['views'][0]['effective_procedure_id']==after['effective_procedure_id']


def test_extraction_dependency_change_invalidates_frozen_promotion():
    dependencies={'evidence_extraction':{'version':'native-envelope-v1','sha256':'old-parser'}}
    snapshot={'is_synthetic':False,'issued_targets':[],'truth_revisions':[],'procedure_dependencies':dependencies}
    registry=learning.update_model_registry(snapshot,generated_at='2024-01-01T00:00:00+00:00')
    assert registry['policy']['procedure_dependencies']==dependencies
    observed=genuine_archive(snapshot,registry)
    assert learning.update_model_registry(observed,generated_at='2025-01-01T00:00:00+00:00')['decision']['promote'] is True
    observed['procedure_dependencies']={'evidence_extraction':{'version':'native-envelope-v1','sha256':'new-parser'}}
    changed=learning.update_model_registry(observed,generated_at='2025-01-01T00:00:00+00:00')
    assert changed['decision']['promote'] is False
    assert changed['serving']==registry['serving']
    assert any('implementation' in reason for reason in changed['decision']['reasons'])
    assert changed['policy']==registry['policy']
