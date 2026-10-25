"""Numerical integration regressions; all fixtures are synthetic."""
from datetime import date, timedelta
import importlib.util
import json
import pytest


def snapshot():
    start = date(2026, 10, 19)
    rows, coverage = [], []
    for offset in range(-56, 0):
        day = start + timedelta(days=offset)
        coverage.append({'date': str(day), 'source_id': 'meter', 'complete': True})
        for person, team, quantity, exposure in [('p1', 't1', 10, 1), ('p2', 't2', 40, 2), (None, None, 5, 1)]:
            rows.append(dict(date=str(day), person_id=person, team_id=team, project_id='project', configuration_id='c1', meter='tokens', billing_pool='pool', quantity=quantity, exposure=exposure, source_id='meter', available_at=str(day)+'T23:00:00Z', mature=True, complete=True))
    return dict(id='snapshot', tenant_id='tenant', target=dict(unit='USD', quantity='spend', basis='planning', timezone='UTC'), information_cutoff='2026-10-19T00:00:00Z', history_complete_through='2026-10-18', forecast_start=str(start), period_start='2026-10-01', period_end='2027-01-01', people=[dict(id='p1', name='One'),dict(id='p2', name='Two')], required_sources=['meter'], observations=rows, coverage=coverage, drivers=[], pricing=[dict(id='tariff',version='1',billing_pool='pool',unit='tokens',currency='USD',period_start='2026-10-01',period_end='2027-01-01',rate=.1,mode='linear',complete_pool=True,known_at='2026-01-01T00:00:00Z')])


def build(s, **kwargs):
    assert importlib.util.find_spec('forecasting.planning') is not None, 'canonical planner must exist'
    from forecasting.planning import build_forecast
    return build_forecast(s, run_id='run', generated_at='2026-10-19T00:01:00Z', **kwargs)


def company(result):
    return next(v for v in result['views'] if v['scope']['type']=='company')


def test_daily_weekly_quarter_and_scope_rollups_share_paths():
    result = build(snapshot())
    view = company(result)
    assert len(view['daily']) == 7 and len(view['weekly']) == 4
    assert view['daily'][0]['base'] == pytest.approx(5.5)
    assert view['weekly'][0]['base'] == pytest.approx(38.5)
    assert view['quarter_outlook']['base'] == pytest.approx(92*5.5)
    for branch in ['base','low','high']:
        assert view['quarter_outlook'][branch] == pytest.approx(sum(v['quarter_outlook'][branch] for v in result['views'] if v['scope']['type'] in ['person','shared']))
    assert result == build(snapshot())
    json.dumps(result, allow_nan=False)


def test_workload_uses_observed_rate_and_paired_omission():
    s = snapshot()
    s['drivers'] = [dict(id='work',kind='workload',scope={'person_id':'p2'},effective_from='2026-10-19',effective_to='2027-01-01',parameters={'exposure':3,'unit':'work_units'},status='eligible',citations=[{'source_id':'plan'}])]
    result = build(s)
    assert company(result)['daily'][0]['base'] == pytest.approx(7.5)
    effect = result['driver_effects'][0]
    assert effect['driver_id']=='work' and effect['base_delta']==pytest.approx(74*2)


def test_missing_prefix_coverage_makes_full_quarter_unavailable():
    s=snapshot();s['coverage']=[r for r in s['coverage'] if r['date']!='2026-10-10']
    view=company(build(s))
    assert view['quarter_outlook']['base'] is None
    assert not view['quarter_outlook']['complete']
    assert any('coverage' in x.lower() for x in view['limitations'])


def test_missing_exposure_retains_aggregate_and_excludes_workload():
    s=snapshot()
    for row in s['observations']:row['exposure']=None
    s['drivers']=[dict(id='work',kind='workload',scope={},effective_from='2026-10-19',parameters={'exposure':10,'unit':'work_units'},status='eligible')]
    result=build(s);view=company(result)
    assert view['daily'][0]['base']==pytest.approx(5.5)
    assert not view['included_drivers']
    assert any('exposure' in x.lower() for x in view['limitations'])


def test_incomplete_tariff_never_treats_spend_as_zero():
    s=snapshot();s['pricing'][0]['complete_pool']=False
    view=company(build(s))
    assert view['daily'][0]['base'] is None
    assert any('pool' in x.lower() for x in view['limitations'])


def test_graduated_price_is_computed_on_full_pool_before_allocation():
    s=snapshot();p=s['pricing'][0];p.update(mode='graduated',tiers=[{'up_to':1000,'rate':.1},{'up_to':None,'rate':.05}])
    result=build(s);view=company(result)
    assert view['quarter_outlook']['base']==pytest.approx(100+(92*55-1000)*.05)
    assert view['quarter_outlook']['base']==pytest.approx(sum(v['quarter_outlook']['base'] for v in result['views'] if v['scope']['type'] in ['team','shared']))
    assert any('allocation' in x.lower() for x in view['limitations'])


def test_partial_calendar_week_excludes_recorded_days():
    s=snapshot();s['forecast_start']='2026-10-21';s['information_cutoff']='2026-10-21T00:00:00Z'
    # The intervening days have explicit zero coverage; they are recorded zero.
    s['coverage'] += [dict(date=d,source_id='meter',complete=True) for d in ['2026-10-19','2026-10-20']]
    s['history_complete_through']='2026-10-20'
    view=company(build(s))
    assert view['weekly'][0]['start']=='2026-10-21'
    assert view['weekly'][0]['calendar_start']=='2026-10-19'
    assert view['weekly'][0]['partial'] is True
    assert view['weekly'][0]['base']==pytest.approx(sum(p['base'] for p in view['daily'][:5]))
    assert view['weekly'][0]['recorded']==0


def test_insufficient_history_omits_descriptive_bounds():
    s=snapshot();s['observations']=s['observations'][-9:];s['coverage']=s['coverage'][-3:]
    view=company(build(s))
    assert view['daily'][0]['low'] is None and view['daily'][0]['high'] is None
    assert view['scenario_range']['available'] is False


def test_late_available_evidence_not_included_in_frozen_run():
    s=snapshot();s['drivers']=[dict(id='future',kind='workload',scope={},effective_from='2026-10-19',available_at='2026-10-20T00:00:00Z',parameters={'exposure':100,'unit':'work_units'},status='eligible')]
    view=company(build(s))
    assert view['daily'][0]['base']==pytest.approx(5.5)
    assert [d['id'] for d in view['queued_changes']]==['future']


def test_membership_reallocates_future_team_without_changing_company():
    s=snapshot();s['drivers']=[dict(id='move',kind='membership',scope={'person_id':'p1'},effective_from='2026-10-19',parameters={'team_id':'t2'},status='eligible')]
    result=build(s)
    team=next(v for v in result['views'] if v['scope']=={'type':'team','id':'t1','name':'t1'})
    assert team['daily'][0]['base']==0
    assert company(result)['daily'][0]['base']==pytest.approx(5.5)


def test_project_absolute_exposure_is_distributed_not_repeated_per_person():
    s=snapshot();s['drivers']=[dict(id='work',kind='workload',scope={'project_id':'project'},effective_from='2026-10-19',parameters={'exposure':8,'unit':'work_units'},status='eligible')]
    view=company(build(s))
    # Baseline exposure is 4 across project, so each component doubles.
    assert view['daily'][0]['base']==pytest.approx(11)


def test_unassigned_component_partition_reconciles_people_and_teams():
    s=snapshot()
    for row in s['observations']:
        if row['person_id'] is None:row['team_id']='t1'
    result=build(s);view=company(result)
    for partition,kind in [('people','person'),('teams','team')]:
        ids=view['reconciliation'][partition]['scope_ids']
        assert view['daily'][0]['base']==pytest.approx(sum(v['daily'][0]['base'] for v in result['views'] if v['id'] in ids))


def test_no_observations_is_unavailable_not_zero():
    s=snapshot();s['observations']=[]
    view=company(build(s))
    assert view['daily'][0]['base'] is None


def test_invalid_and_unapplied_pricing_driver_is_excluded():
    s=snapshot();s['pricing'][0].update(mode='volume',tiers=[{'up_to':None,'rate':.1}])
    s['drivers']=[dict(id='price',kind='pricing',scope={'billing_pool':'pool'},effective_from='2026-10-19',parameters={'rate':.2,'currency':'USD','unit':'tokens'},status='eligible')]
    view=company(build(s))
    assert not view['included_drivers']
    assert 'linear' in view['queued_changes'][0]['publication_reason'].lower()


def test_corrected_observation_revision_replaces_original_quantity():
    s=snapshot();original=s['observations'][-3]
    correction=dict(original,quantity=20,available_at='2026-10-18T23:30:00Z',source_revision=2)
    s['observations'].append(correction)
    result=build(s)
    assert company(result)['components']['recorded']==pytest.approx(18*5.5+1)


def test_selected_procedure_changes_fitted_history_and_identity():
    s=snapshot()
    for row in s['observations']:
        if row['date']<'2026-09-21':row['quantity']*=3
    default=company(build(s))
    s['procedure']={'id':'candidate-28','kind':'driver_rate','window_days':28}
    candidate=company(build(s))
    assert candidate['procedure_id']=='candidate-28'
    assert candidate['daily'][0]['base']==pytest.approx(5.5)
    assert default['daily'][0]['base']>candidate['daily'][0]['base']
    s['procedure']={'id':'reference','kind':'seasonal_naive','window_days':56}
    assert company(build(s))['daily'][0]['base']==pytest.approx(5.5)


def test_forecast_does_not_report_zero_beyond_quarter_tariff_end():
    s=snapshot();s.update(forecast_start='2026-12-30',information_cutoff='2026-12-30T00:00:00Z')
    view=company(build(s))
    assert view['daily'][2]['base'] is None


def test_team_workload_uses_effective_membership_exposure_partition():
    s=snapshot();s['drivers']=[
        dict(id='move',kind='membership',scope={'person_id':'p1'},effective_from='2026-10-19',parameters={'team_id':'t2'},status='eligible'),
        dict(id='load',kind='workload',scope={'team_id':'t2'},effective_from='2026-10-19',parameters={'exposure':6,'unit':'work_units'},status='eligible')]
    assert company(build(s))['daily'][0]['base']==pytest.approx(10.5)


def test_unsupported_scope_key_does_not_become_global_effect():
    s=snapshot();s['drivers']=[dict(id='bad',kind='workload',scope={'unknown_team':'t1'},effective_from='2026-10-19',parameters={'exposure':100,'unit':'work_units'},status='eligible')]
    view=company(build(s))
    assert view['daily'][0]['base']==pytest.approx(5.5)
    assert not view['included_drivers']


def test_forecast_json_roundtrip_preserves_contract_exactly():
    result=build(snapshot())
    assert json.loads(json.dumps(result,allow_nan=False))==result


def test_pool_tariff_cannot_be_replaced_for_only_one_person():
    s=snapshot();s['drivers']=[dict(id='price',kind='pricing',scope={'person_id':'p1'},effective_from='2026-10-19',parameters={'rate':.001,'currency':'USD','unit':'tokens'},status='eligible')]
    view=company(build(s))
    assert not view['included_drivers']
    assert view['daily'][0]['base']==pytest.approx(5.5)


def test_branch_values_reconcile_before_envelope_summarization():
    s=snapshot();s['drivers']=[dict(id='w',kind='workload',scope={'person_id':'p2'},effective_from='2026-10-19',parameters={'exposure':2,'exposure_low':1,'exposure_high':4,'unit':'work_units'},status='eligible')]
    r=build(s);v=company(r)
    for branch in ['low','base','high']:
        assert v['quarter_outlook']['configuration_values'][branch]==pytest.approx(sum(x['quarter_outlook']['configuration_values'][branch] for x in r['views'] if x['id'] in v['reconciliation']['people']['scope_ids']))


def test_project_shift_preserves_work_and_changes_only_identified_dates():
    s=snapshot();s['target'].update(unit='tokens',quantity='usage')
    before=company(build(s))
    s['drivers']=[dict(id='shift',kind='project_schedule',scope={'project_id':'project'},effective_from='2026-10-19',parameters={'from_start':'2026-10-19','from_end':'2026-10-24','to_start':'2026-10-26'},status='eligible')]
    after=company(build(s))
    assert after['daily'][0]['base']==0
    assert after['weekly'][1]['base']==pytest.approx(before['weekly'][1]['base']+5*55)
    assert after['quarter_outlook']['base']==pytest.approx(before['quarter_outlook']['base'])


def test_adoption_conserves_quantity_without_benchmark_reduction():
    s=snapshot();s['drivers']=[dict(id='adopt',kind='adoption',scope={'project_id':'project'},effective_from='2026-10-19',parameters={'configuration_id':'new','share':.6},status='eligible')]
    result=build(s)
    assert company(result)['daily'][0]['base']==pytest.approx(5.5)
    assert result['driver_effects'][0]['base_delta']==pytest.approx(0)


def test_known_recorded_amount_survives_missing_coverage_without_training():
    s=snapshot();s['coverage']=[]
    for row in s['observations']:row.update(complete=False,mature=False,exposure=None)
    v=company(build(s))
    assert v['components']['recorded']==pytest.approx(99)
    assert v['components']['late'] is None
    assert v['daily'][0]['base'] is None
    assert v['quarter_outlook']['base'] is None


def test_driver_omission_effects_are_scoped_to_requested_person():
    s=snapshot();s['drivers']=[dict(id='w',kind='workload',scope={'person_id':'p2'},effective_from='2026-10-19',parameters={'exposure':3,'unit':'work_units'},status='eligible')]
    r=build(s);p1=next(v for v in r['views'] if v['scope']['type']=='person' and v['scope']['id']=='p1')
    assert r['driver_effects'][0]['scope']=={'type':'company','id':'tenant'}
    assert p1['driver_effects'][0]['scope']=={'type':'person','id':'p1'}
    assert p1['driver_effects'][0]['base_delta']==pytest.approx(0)


def test_explicit_recorded_money_survives_unavailable_usage_pricing():
    s=snapshot();s['pricing']=[];s['coverage']=[]
    for row in s['observations']:row.update(complete=False,mature=False,exposure=None,meter='usd',recorded_amount=row['quantity']*.1,recorded_currency='USD')
    v=company(build(s))
    assert v['components']['recorded']==pytest.approx(99)
    assert v['daily'][0]['base'] is None
    assert v['quarter_outlook']['base'] is None


def test_superseded_immature_revision_does_not_poison_complete_day():
    s=snapshot();s['observations'].append(dict(s['observations'][-3],complete=False,mature=False,available_at='2026-10-18T22:00:00Z'))
    assert company(build(s))['quarter_outlook']['base']==pytest.approx(506)


def test_schedule_is_inactive_before_its_effective_date():
    s=snapshot();s['drivers']=[dict(id='shift',kind='project_schedule',scope={'project_id':'project'},effective_from='2026-11-19',parameters={'from_start':'2026-10-19','from_end':'2026-10-24','to_start':'2026-10-26'},status='eligible')]
    assert company(build(s))['daily'][0]['base']==pytest.approx(5.5)


def test_workload_can_target_new_effective_membership_team():
    s=snapshot();s['drivers']=[dict(id='move',kind='membership',scope={'person_id':'p1'},effective_from='2026-10-19',parameters={'team_id':'NEW'},status='eligible'),dict(id='load',kind='workload',scope={'team_id':'NEW'},effective_from='2026-10-19',parameters={'exposure':2,'unit':'work_units'},status='eligible')]
    assert company(build(s))['daily'][0]['base']==pytest.approx(6.5)


def cohort_snapshot():
    s=snapshot()
    s['components']=[dict(person_id='new',team_id='t1',project_id='project',configuration_id='c1',meter='tokens',billing_pool='pool',exposure_unit='work_units',exposure_by_weekday={str(i):2 for i in range(7)})]
    s['authorized_cohorts']={'new-person':dict(authorized=True,recipient_scope={'person_id':'new'},donor_scope={'person_id':'p1'},configuration_id='c1',meter='tokens',billing_pool='pool',exposure_unit='work_units')}
    return s


def test_explicit_authorized_compatible_cohort_supplies_missing_rate():
    s=cohort_snapshot();r=build(s)
    person=next(v for v in r['views'] if v['scope']['type']=='person' and v['scope']['id']=='new')
    assert person['daily'][0]['base']==pytest.approx(2)
    assert company(r)['daily'][0]['base']==pytest.approx(7.5)
    assert any(c.get('cohort_id')=='new-person' for c in r['calculations'][0]['components'])


@pytest.mark.parametrize('change',[{'authorized':False},{'meter':'requests'},{'configuration_id':'other'},{'exposure_unit':'hours'}])
def test_cohort_requires_explicit_authorization_and_compatible_units(change):
    s=cohort_snapshot();s['authorized_cohorts']['new-person'].update(change)
    assert company(build(s))['daily'][0]['base'] is None


def test_cohort_cannot_invent_recipient_exposure():
    s=cohort_snapshot();del s['components'][0]['exposure_by_weekday']
    assert company(build(s))['daily'][0]['base'] is None


def test_fixed_only_pool_obligation_is_priced_without_usage():
    s=snapshot();s['pricing'].append(dict(s['pricing'][0],id='subscription',billing_pool='empty',rate=0,fixed=1000))
    v=company(build(s))
    assert v['quarter_outlook']['base']==pytest.approx(1506)
    assert v['components']['fixed']==pytest.approx(1000)


def test_history_window_uses_latest_56_complete_days_not_calendar_span():
    s=snapshot();missing='2026-10-10';s['coverage']=[r for r in s['coverage'] if r['date']!=missing]
    extra='2026-08-23';s['coverage'].append(dict(date=extra,source_id='meter',complete=True))
    s['observations'].extend([dict(r,date=extra,available_at=extra+'T23:00:00Z') for r in s['observations'][:3]])
    r=build(s)
    assert all(c['complete_days']==56 for c in r['calculations'][0]['components'])


def test_explicit_source_bounds_survive_sparse_bootstrap_with_qualification():
    s=snapshot();s['observations']=s['observations'][-9:];s['coverage']=s['coverage'][-3:]
    s['drivers']=[dict(id='w',kind='workload',scope={'person_id':'p2'},effective_from='2026-10-19',parameters={'exposure':2,'exposure_low':1,'exposure_high':3,'unit':'work_units'},status='eligible')]
    v=company(build(s))
    assert v['daily'][0]['low'] < v['daily'][0]['base'] < v['daily'][0]['high']
    assert v['scenario_range']['available'] is True
    assert v['scenario_range']['complete'] is False
    assert v['scenario_range']['conditional_on_base_rates'] is True


def test_overlapping_absolute_scopes_do_not_depend_on_input_order():
    s=snapshot();a=dict(id='a',kind='workload',scope={},effective_from='2026-10-19',parameters={'exposure':2,'unit':'work_units'},status='eligible');b=dict(a,id='b',scope={'person_id':'p1'})
    s['drivers']=[a,b];one=company(build(s));s['drivers']=[b,a];two=company(build(s))
    assert one['daily'][0]['base']==two['daily'][0]['base']==pytest.approx(5.5)
    assert not one['included_drivers']


def test_future_exposure_declaration_does_not_turn_aggregate_rate_into_unit_rate():
    s=snapshot()
    for row in s['observations']:row['exposure']=None
    s['components']=[dict(s['observations'][0],exposure_unit='work_units',exposure_by_weekday={str(i):100 for i in range(7)})]
    assert company(build(s))['daily'][0]['base']==pytest.approx(5.5)


def test_cohort_donor_exposure_units_must_match_authorization():
    s=cohort_snapshot()
    for row in s['observations']:
        if row['person_id']=='p1':row['exposure_unit']='hours'
    assert company(build(s))['daily'][0]['base'] is None


@pytest.mark.parametrize('invalid',[2,-.1,'not a number'])
def test_adoption_bounds_cannot_create_negative_component_quantities(invalid):
    s=snapshot();s['drivers']=[dict(id='adopt',kind='adoption',scope={},effective_from='2026-10-19',parameters={'configuration_id':'new','share':.5,'share_low':.2,'share_high':invalid},status='eligible')]
    v=company(build(s))
    assert not v['included_drivers']
    assert v['daily'][0]['base']==pytest.approx(5.5)
