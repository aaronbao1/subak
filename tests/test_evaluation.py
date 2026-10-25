from datetime import date, datetime, timedelta, timezone
import pytest
from forecasting.evaluation import (LabelVersion, LabelQueue, SplitManifest, LockedSelection,
    PopulationMember, validate_population, point_metrics, quantile_metrics, interval_metrics,
    event_metrics, Opportunity, summarize_opportunities, selected_donor_diagnostics,
    promotion_decision, synthetic_evaluation)

UTC = timezone.utc
def dt(day): return datetime(2025, 1, day, tzinfo=UTC)
def label(revision=1, value=10, available=3, mature=4, status='mature'):
    return LabelVersion('a', 'team', date(2025,1,1), date(2025,1,3), dt(available), dt(mature), value, revision, status)

def test_label_queue_maturity_revisions_and_purge():
    q = LabelQueue((label(), label(2, 99, 8, 9)))
    assert q.fit_labels(dt(3)) == ()
    assert q.fit_labels(dt(4))[0].value == 10
    assert q.fit_labels(dt(10))[0].value == 99
    assert q.fit_labels(dt(10), (date(2025,1,2), date(2025,1,5))) == ()
    assert q.score_labels(dt(4))[0].revision == 1
    assert q.score_labels(dt(10))[0].revision == 2
    assert LabelQueue((label(), label())).fit_labels(dt(5)) == (label(),)

def test_pending_revision_does_not_fall_back_to_old_mature_truth():
    q = LabelQueue((label(), label(2, 99, 5, 9, 'disputed')))
    assert q.fit_labels(dt(10)) == ()

def test_chronological_overlap_and_final_selection_guards():
    with pytest.raises(ValueError):
        SplitManifest((date(2025,1,1),date(2025,1,10)), (date(2025,1,8),date(2025,1,20)), (date(2025,2,1),date(2025,2,10)))
    lock = LockedSelection(('a','b'), search_budget=2, seed=7)
    with pytest.raises(ValueError): lock.record('a', 1, phase='F')
    lock.record('a', 3, phase='D', cost=2)
    lock.record('b', None, phase='D', cost=5)
    assert lock.freeze() == 'a'
    assert lock.total_cost == 7
    with pytest.raises(ValueError): lock.record('b', 0, phase='D')
    lock.begin_final()
    with pytest.raises(ValueError): lock.begin_final()

def test_population_lineage_and_derivatives_never_cross_holdout():
    with pytest.raises(ValueError):
        validate_population((PopulationMember('x','D','company',('export1',)), PopulationMember('y','F','other',('export1',))))
    with pytest.raises(ValueError):
        validate_population((PopulationMember('x','D','company'), PopulationMember('y','F','company')))

def test_metric_semantics_and_undefined_denominators():
    assert point_metrics((1,3),(0,1)) == {'n':2,'mae':1.5,'rmse':pytest.approx(2.5**.5),'bias':1.5,'wape':3.0}
    assert point_metrics((1,), (0,))['wape'] is None
    assert point_metrics((), ())['mae'] is None
    assert quantile_metrics({.5:(2,)},(4,))['pinball_mean'] == 1
    assert interval_metrics((0,), (2,), (4,), .2)['interval_score'] == 22
    assert event_metrics((.2,.8),(False,True))['brier'] == pytest.approx(.04)
    assert event_metrics((.1,), (False,))['recall'] is None
    with pytest.raises(ValueError): quantile_metrics({.1:(3,),.9:(2,)},(2,))

def test_all_opportunities_preserve_missing_failed_pending_and_historical_cohorts():
    ops = (Opportunity('1','old-team','company',date(2025,1,1),date(2025,1,8),'on_time',10,11,'mature','dissolved'),
           Opportunity('2','old-team','company',date(2025,1,2),date(2025,1,9),'missing',None,None,'pending','dissolved'),
           Opportunity('3','new-team','company',date(2025,1,3),date(2025,1,10),'failed',None,100,'mature','cold'))
    report = summarize_opportunities(ops)
    assert report['scheduled'] == 3 and report['scored'] == 1
    assert report['label_states']['pending'] == 1
    assert report['availability'] == pytest.approx(1/3)
    assert report['distinct_companies'] == 1
    assert report['nonoverlapping_blocks'] == 1
    assert report['all_case_utility'] is None
    assert report['cohorts']['dissolved']['scheduled'] == 2

def test_selected_donor_diagnostic_and_gates_are_not_safety_claims():
    assert selected_donor_diagnostics(((100,30,90),))['increased_exposure'] == 20
    report = promotion_decision({'mae':1,'availability':1}, {'max_mae':None,'min_availability':.99}, synthetic=True)
    assert not report['promoted']
    assert 'synthetic evidence' in report['reasons']

def test_runnable_synthetic_registry_evaluation_is_locked_and_honest():
    r = synthetic_evaluation(seed=4)
    assert r['evidence'] == 'synthetic_mechanism_demo'
    assert r['selected_model'] in r['candidates']
    assert r['final']['scheduled'] > 0
    assert r['trials'] and all('latency_seconds' in t for t in r['trials'])
    assert not r['promotion']['promoted']
    assert r['seed'] == 4
    assert r['company_comparison']['paired_company']['n'] > 0
    assert all(t['loss'] is not None for t in r['trials'])
    manifests=r['development']['model_manifests']
    assert manifests and all('config' in m['metadata'] for m in manifests)
    assert {m['model_name'] for m in manifests}==set(r['candidates'])

def test_rolling_replay_does_not_use_late_revision_and_score_vintages_change():
    from forecasting.models import Series
    from forecasting.evaluation import evaluate_rolling
    ds=tuple(date(2025,1,d) for d in range(1,8))
    series=(Series('t',ds,(1.,)*7),)
    daily=tuple(LabelVersion('d'+str(i),'t',d,d+timedelta(days=1),dt(i+2),dt(i+2),1.) for i,d in enumerate(ds))
    corrected=LabelVersion('d0','t',ds[0],ds[0]+timedelta(days=1),dt(9),dt(9),100.,2)
    truth=LabelVersion('t:2025-01-05','t',ds[4],ds[6],dt(7),dt(7),2.)
    revised=LabelVersion('t:2025-01-05','t',ds[4],ds[6],dt(9),dt(9),99.,2)
    a=evaluate_rolling(series,(ds[4],),2,('last_observation',),dt(8),labels=(truth,revised),observation_labels=daily)
    b=evaluate_rolling(series,(ds[4],),2,('last_observation',),dt(10),labels=(truth,revised),observation_labels=daily+(corrected,))
    assert a['input_manifests']==b['input_manifests']
    ar=a['candidates']['last_observation']['rows'][0]
    br=b['candidates']['last_observation']['rows'][0]
    assert ar['prediction']==br['prediction']==2
    assert ar['actual']==2 and br['actual']==99

def test_score_target_identity_cannot_be_overridden_by_label_key():
    from forecasting.models import Series
    from forecasting.evaluation import evaluate_rolling
    series=(Series('t',(date(2025,1,1),date(2025,1,2)),(1.,1.)),)
    bad=LabelVersion('t:2025-01-03','other',date(2025,1,3),date(2025,1,4),dt(4),dt(4),99.)
    with pytest.raises(ValueError,match='target identity'):
        evaluate_rolling(series,(date(2025,1,3),),1,('last_observation',),dt(5),labels=(bad,))

def test_duplicate_daily_observations_cannot_silently_overwrite():
    from forecasting.models import Series
    from forecasting.evaluation import evaluate_rolling
    s=Series('t',(date(2025,1,1),),(1.,))
    observations=tuple(LabelVersion(key,'t',date(2025,1,1),date(2025,1,2),dt(2),dt(2),value) for key,value in (('a',1.),('b',100.)))
    with pytest.raises(ValueError,match='duplicate daily'):
        evaluate_rolling((s,),(date(2025,1,2),),1,('last_observation',),dt(5),observation_labels=observations)

def test_abstention_cost_and_duplicate_target_support():
    a=Opportunity('1','t','c',date(2025,1,1),date(2025,1,8),'on_time',0,100,'mature')
    b=Opportunity('2','t','c',date(2025,1,1),date(2025,1,8),'missing',None,100,'mature')
    assert summarize_opportunities((a,),100)['all_case_utility']==100
    assert summarize_opportunities((b,),100)['all_case_utility']==100
    assert summarize_opportunities((a,b))['distinct_target_periods']==1
    assert summarize_opportunities((a,b))['nonoverlapping_blocks']==1

def test_manager_budget_request_and_target_mismatch_rejected():
    from forecasting.evaluation import ManagerForecast, score_manager_forecast
    target=('USD','net_incurred',date(2025,1,1),date(2025,1,3),'mean')
    forecast=ManagerForecast('manager',dt(1),10,'budget_request',target)
    with pytest.raises(ValueError,match='predictive'):
        score_manager_forecast(forecast,label(),dt(5),target)
    forecast=ManagerForecast('manager',dt(1),10,'prediction',('credits',)+target[1:])
    with pytest.raises(ValueError,match='target'):
        score_manager_forecast(forecast,label(),dt(5),target)

def test_warning_uses_frozen_origin_budget_and_pending_is_not_negative():
    from forecasting.evaluation import WarningRecord, warning_diagnostics
    warning=WarningRecord('event','budget-v1',100,dt(1),date(2025,1,11),True,120)
    duplicate=WarningRecord('event','budget-v1',100,dt(2),date(2025,1,11),True,120)
    pending=WarningRecord('pending','budget-v1',100,dt(2),date(2025,1,11),False,None)
    result=warning_diagnostics((warning,duplicate,pending))
    assert result['mature_events']==1 and result['pending_events']==1
    assert result['recall']==1 and result['duplicate_warnings']==1
    assert result['first_warning_lead_days']=={'event':10}
    from dataclasses import FrozenInstanceError
    with pytest.raises(FrozenInstanceError): warning.origin_budget=200

def test_final_label_mutation_cannot_change_development_selection():
    from forecasting.evaluation import LockedSelection
    def selected(final_loss):
        state=LockedSelection(('a','b'),2,1)
        state.record('a',3,phase='D'); state.record('b',4,phase='D')
        state.freeze(); state.begin_final()
        with pytest.raises(ValueError): state.record('b',final_loss,phase='F')
        return state.selected
    assert selected(0)==selected(1000)=='a'

def test_wis_and_certain_wrong_event_have_honest_boundary():
    from forecasting.evaluation import weighted_interval_score
    assert weighted_interval_score((1,),{.2:((0,),(2,))},(4,))==pytest.approx((1.5+2.2)/1.5)
    r=event_metrics((0.,),(True,))
    assert r['log_loss'] is None and r['log_loss_status']=='infinite'

def test_runner_does_not_inject_unsupported_seed_into_baselines():
    from forecasting.models import Series
    from forecasting.evaluation import evaluate_rolling
    ds=tuple(date(2025,1,d) for d in range(1,8))
    report=evaluate_rolling((Series('t',ds,(1.,)*7),),(date(2025,1,8),),2,('last_observation','trailing_mean'),dt(10))
    assert all(c['summary']['availability']==1 for c in report['candidates'].values())

def test_company_comparison_preserves_population_and_separate_granularity():
    from forecasting.evaluation import company_comparison
    a=Opportunity('a','a','c',date(2025,1,1),date(2025,1,8),'on_time',10,12,'mature')
    b=Opportunity('b','b','c',date(2025,1,1),date(2025,1,8),'on_time',20,23,'mature')
    direct=Opportunity('c','c','c',date(2025,1,1),date(2025,1,8),'on_time',34,35,'mature')
    r=company_comparison((a,b),(direct,),{'c':('a','b')})
    assert r['bottom_up_company']['point']['mae']==5
    assert r['direct_company']['point']['mae']==1
    assert r['paired_company']['mean_absolute_loss_difference']==4
    incomplete=company_comparison((a,),(direct,),{'c':('a','b')})
    assert incomplete['bottom_up_company']['scored']==0
    assert incomplete['paired_company']['n']==0

def test_macro_and_spend_weighted_views_keep_denominators_explicit():
    rows=(Opportunity('1','a','c',date(2025,1,1),date(2025,1,8),'on_time',5,10,'mature'),Opportunity('2','b','c',date(2025,1,1),date(2025,1,8),'on_time',100,100,'mature'))
    score=summarize_opportunities(rows)
    assert score['team_macro_mae']==2.5
    assert score['spend_weighted_mae']==pytest.approx(50/110)
    assert score['companies']['c']['scheduled']==2

def test_pooled_90_percent_coverage_does_not_hide_migration_donor_failure():
    from forecasting.evaluation import interval_cohort_metrics
    rows=tuple(('stable',0,10,5) for _ in range(90))+tuple(('migration_donor',0,10,50) for _ in range(10))
    r=interval_cohort_metrics(rows,.1)
    assert r['overall']['coverage']==.9
    assert r['cohorts']['migration_donor']['coverage']==0
    gate=promotion_decision({'mae':0,'abs_bias':0,'availability':1,'latency_seconds':0,'coverage':.9,'width':10,'interval_score':1,'migration_donor_coverage':0},
        {'max_mae':10,'max_abs_bias':10,'min_availability':1,'max_latency_seconds':1,'min_coverage':.9,'max_width':20,'max_interval_score':10,'min_migration_donor_coverage':.8},real_population_support=True,capability='interval')
    assert not gate['promoted'] and 'failed threshold: min_migration_donor_coverage' in gate['reasons']

def test_promotion_nonfinite_metric_cannot_pass_comparisons():
    metrics={'mae':float('nan'),'abs_bias':0,'availability':1,'latency_seconds':0}
    thresholds={'max_mae':1,'max_abs_bias':1,'min_availability':.9,'max_latency_seconds':1}
    assert not promotion_decision(metrics,thresholds,real_population_support=True)['promoted']
    with pytest.raises(ValueError,match='threshold'):
        promotion_decision(metrics,dict(thresholds,mae=1),real_population_support=True)

def test_versioned_replay_requires_explicit_truth_not_current_series():
    from forecasting.models import Series
    from forecasting.evaluation import evaluate_rolling
    s=Series('t',(date(2025,1,1),date(2025,1,2)),(1.,999.))
    obs=(LabelVersion('d','t',date(2025,1,1),date(2025,1,2),dt(2),dt(2),1.),)
    with pytest.raises(ValueError,match='explicit cumulative'):
        evaluate_rolling((s,),(date(2025,1,2),),1,('last_observation',),dt(5),observation_labels=obs)

def test_manager_same_day_hindsight_after_origin_rejected():
    from forecasting.evaluation import ManagerForecast, score_manager_forecast
    target=('USD','net_incurred',date(2025,1,1),date(2025,1,3),'mean')
    forecast=ManagerForecast('manager',dt(1)+timedelta(hours=23),10,'prediction',target)
    with pytest.raises(ValueError,match='retrospective'):
        score_manager_forecast(forecast,label(),dt(5),target)

def test_utc_daily_maturity_boundary_cannot_be_bypassed_with_offset():
    offset=timezone(timedelta(hours=14))
    early=datetime(2025,1,3,tzinfo=offset)
    with pytest.raises(ValueError,match='maturity'):
        LabelVersion('early','t',date(2025,1,2),date(2025,1,3),early,early,9.)

def test_frozen_schedule_retains_entity_after_source_deletion():
    from forecasting.models import Series
    from forecasting.evaluation import evaluate_rolling
    s=Series('active',(date(2025,1,1),date(2025,1,2)),(1.,1.))
    result=evaluate_rolling((s,),(date(2025,1,2),),1,('last_observation',),dt(5),scheduled_entities=('active','dissolved'))
    data=result['candidates']['last_observation']
    assert data['summary']['scheduled']==2 and data['summary']['availability']==.5
    dissolved=next(r for r in data['rows'] if r['entity_id']=='dissolved')
    assert dissolved['output_status']=='unavailable' and dissolved['actual'] is None
    assert result['scheduled_entities']==('active','dissolved')

def test_late_warning_cannot_count_as_actionable_success():
    from forecasting.evaluation import WarningRecord, warning_diagnostics
    late=WarningRecord('event','budget-v1',100,dt(12),date(2025,1,11),True,120)
    result=warning_diagnostics((late,))
    assert result['mature_events']==1 and result['recall']==0
    assert result['first_warning_lead_days']=={}

def test_half_open_seven_day_label_matures_at_exclusive_end_and_adjacent_purge_keeps_it():
    record=LabelVersion('week','t',date(2025,1,1),date(2025,1,8),dt(8),dt(8),7.)
    queue=LabelQueue((record,))
    assert queue.fit_labels(dt(8))==(record,)
    assert queue.fit_labels(dt(8)-timedelta(microseconds=1))==()
    assert queue.fit_labels(dt(9),(date(2025,1,8),date(2025,1,15)))==(record,)
    assert queue.fit_labels(dt(9),(date(2025,1,7),date(2025,1,15)))==()

def test_half_open_adjacent_split_boundaries_are_disjoint():
    split=SplitManifest((date(2025,1,1),date(2025,1,8)),(date(2025,1,8),date(2025,1,15)),(date(2025,1,15),date(2025,1,22)))
    assert split.phase(date(2025,1,1),date(2025,1,8))=='D'
    assert split.phase(date(2025,1,8),date(2025,1,15))=='C'
    with pytest.raises(ValueError):split.phase(date(2025,1,7),date(2025,1,9))
    with pytest.raises(ValueError):split.phase(date(2025,1,8),date(2025,1,8))

def test_runner_half_open_week_and_month_remainder_exact_totals():
    from forecasting.models import Series
    from forecasting.evaluation import evaluate_rolling
    dates=tuple(date(2025,1,1)+timedelta(days=i) for i in range(32))
    source=(Series('t',dates,(1.,)*31+(1000.,)),)
    for origin,horizon,end in ((date(2025,1,8),7,date(2025,1,15)),(date(2025,1,24),8,date(2025,2,1))):
        score_at=datetime.combine(end,datetime.min.time(),UTC)
        result=evaluate_rolling(source,(origin,),horizon,('last_observation',),score_at)
        row=result['candidates']['last_observation']['rows'][0]
        assert row['target_end']==end.isoformat()
        assert row['prediction']==row['actual']==horizon
        assert row['label_status']=='mature'

def test_half_open_midnight_maturity_uses_utc_instant_across_offset():
    end=date(2025,1,8)
    same_instant=datetime(2025,1,7,16,tzinfo=timezone(timedelta(hours=-8)))
    record=LabelVersion('week','t',date(2025,1,1),end,same_instant,same_instant,7.)
    assert LabelQueue((record,)).score_labels(dt(8))==(record,)
    with pytest.raises(ValueError,match='maturity'):
        LabelVersion('early','t',date(2025,1,1),end,same_instant-timedelta(microseconds=1),same_instant-timedelta(microseconds=1),7.)

def test_warning_at_exclusive_end_is_too_late_in_any_offset():
    from forecasting.evaluation import WarningRecord, warning_diagnostics
    issued=datetime(2025,1,7,16,tzinfo=timezone(timedelta(hours=-8)))
    late=WarningRecord('event','b',100,issued,date(2025,1,8),True,120)
    result=warning_diagnostics((late,))
    assert result['recall']==0 and result['first_warning_lead_days']=={}

def test_warning_pending_outcomes_leave_all_eligible_false_alarm_rate_unknown():
    from forecasting.evaluation import WarningRecord, warning_diagnostics
    settled=WarningRecord('settled','v1',100,dt(1),date(2025,1,8),True,90)
    pending=WarningRecord('pending','v1',100,dt(1),date(2025,1,8),True,None)
    result=warning_diagnostics((settled,pending))
    assert (result['eligible_events'],result['mature_events'],result['pending_events'])==(2,1,1)
    assert result['false_alarms_per_eligible'] is None
    assert result['false_alarms_per_mature']==1
    assert result['false_alarm_mature_denominator']==1
    assert result['known_false_alarms']==1
    assert result['false_alarms_per_eligible_bounds']==(.5,1.)
    unissued=WarningRecord('pending','v1',100,dt(1),date(2025,1,8),False,None)
    assert warning_diagnostics((settled,unissued))['false_alarms_per_eligible_bounds']==(.5,.5)
    matured=WarningRecord('pending','v1',100,dt(1),date(2025,1,8),True,110)
    final=warning_diagnostics((settled,matured))
    assert final['false_alarms_per_eligible']==.5
    assert final['false_alarms_per_eligible_bounds']==(.5,.5)
    empty=warning_diagnostics(())
    assert empty['false_alarms_per_eligible'] is None and empty['false_alarms_per_eligible_bounds'] is None

def test_company_comparison_same_origin_distinct_horizons_have_distinct_ids():
    from forecasting.evaluation import company_comparison
    start=date(2025,1,1)
    teams=tuple(Opportunity('team-'+str(days),'t','c',start,start+timedelta(days=days),'on_time',float(days),float(days),'mature') for days in (7,14))
    direct=tuple(Opportunity('company-'+str(days),'c','c',start,start+timedelta(days=days),'on_time',float(days),float(days),'mature') for days in (7,14))
    result=company_comparison(teams,direct,{'c':('t',)})
    assert result['bottom_up_company']['scheduled']==2
    assert result['bottom_up_company']['distinct_target_periods']==2
    assert result['paired_company']['n']==2
    assert result['paired_company']['mean_absolute_loss_difference']==0
