"""Hand-checked execution identities and finite recurrent-law fixtures."""
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
import importlib
import math

import pytest

from forecasting.contracts import Target

UTC = timezone.utc
ORIGIN = datetime(2024, 1, 4, tzinfo=UTC)
DATES = (date(2024, 1, 4), date(2024, 1, 5), date(2024, 1, 6))
TARGET = Target('tokens', 'org', 'metered_usage', 'tokens', None, ('trace',), ('all',), support='nonnegative')


def api():
    # Missing implementation is an explicit failing behavior, not collection failure.
    assert importlib.util.find_spec('forecasting.state') is not None, 'recurrent execution kernel missing'
    return importlib.import_module('forecasting.state')


def spell(person='a', **kwargs):
    return api().ExposureSpell('spell-'+person, person, 'team', date(2024,1,1), date(2024,1,8), datetime(2023,12,1,tzinfo=UTC), **kwargs)


def event(eid, kind, root='r', person='a', day=2, **kwargs):
    stamp = datetime(2024,1,day,tzinfo=UTC)
    return api().ExecutionEvent(eid, root, person, stamp, stamp, kind, **kwargs)


def generate(exposures=None, events=(), parameters=None, **kwargs):
    s = api()
    return s.generate_recurrent_scenarios(
        exposures or (spell(access=True, prior_use=False),), events,
        parameters or (s.HurdleParameters('team', 1., (1,), (s.ExecutionMark(10),)),),
        as_of=ORIGIN, dates=DATES, path_count=kwargs.pop('path_count', 3), seed=7,
        target=TARGET, snapshot_id='authorized-snapshot', **kwargs)


def test_first_trial_comes_once_from_roots_while_recurrent_use_continues():
    result = generate()
    p = result.paths[0]
    assert len(p.roots) == 3
    assert p.first_trials == (('a', DATES[0]),)
    assert p.ever_used == (('a', True),)
    assert p.last_use == (('a', DATES[-1]),)
    assert result.bundle.totals() == (30., 30., 30.)


def test_unknown_prior_use_is_not_a_confirmed_first_trial():
    p = generate((spell(access=True, prior_use=None),)).paths[0]
    assert p.first_trials == ()
    assert p.first_observed_use == (('a', DATES[0]),)
    assert p.ever_used == (('a', True),)


def test_access_loss_does_not_remove_origin_ongoing_work():
    s = api()
    result = generate((spell(access=False, prior_use=True),), (event('start', 'root_start'),),
                      continuation_marks=(s.ExecutionMark(5),))
    assert result.paths[0].roots == ()
    assert result.paths[0].ongoing_roots == ('r',)
    assert result.bundle.totals() == (15.,15.,15.)


def test_delivered_bypasses_admission_proposal_calls_it_once_and_derives_adoption():
    calls = []
    def deny(root, when, mark, person):
        calls.append(root)
        return False
    delivered = generate(mode='delivered', admission=deny)
    assert calls == [] and len(delivered.paths[0].roots) == 3
    proposed = generate(mode='proposal', admission=deny, admission_id='deny-v1')
    assert len(calls) == 9 and len(set(calls)) == 9
    assert proposed.paths[0].first_trials == ()
    assert proposed.paths[0].ever_used == (('a', False),)
    assert proposed.bundle.totals() == (0.,0.,0.)


def test_zero_occurrence_and_returning_users_reactivation_are_real_state_branches():
    s = api()
    par = (s.HurdleParameters('team', 0., marks=(s.ExecutionMark(4),), p_returning=1.),)
    assert generate(parameters=par).bundle.totals() == (0.,0.,0.)
    result = generate((spell(access=True, prior_use=True),), parameters=par)
    assert result.bundle.totals() == (12.,12.,12.)
    assert result.paths[0].first_trials == ()


def test_common_shock_keeps_people_dependent_and_hurdle_count_support_bounded():
    s = api()
    result = generate((spell('a',access=True),spell('b',access=True)), path_count=1000,
                      parameters=(s.HurdleParameters('team',1.,(1,3),(s.ExecutionMark(2),)),),
                      shocks=(s.CommonShock(0,1),s.CommonShock(1,1)))
    values = result.bundle.values
    assert all((p[0][0] == 0) == (p[1][0] == 0) for p in values)
    assert all(x in (0.,2.,6.) for p in values for row in p for x in row)
    assert sum(p[0][0] for p in values)/1000 == pytest.approx(2., abs=.2)


def test_meter_leaves_preserve_retry_fallback_losers_and_wrappers_do_not_add():
    s = api()
    events = (
        event('start','root_start'),
        event('a1','attempt',attempt_id='physical-1',logical_id='op'),
        event('a2','attempt',attempt_id='physical-2',logical_id='op',parent_attempt_id='physical-1',relationship='retry'),
        event('a3','attempt',attempt_id='physical-3',logical_id='op',parent_attempt_id='physical-2',relationship='fallback'),
        event('m1','meter',attempt_id='physical-1',logical_id='op',meter_id='leaf1',tokens=7),
        event('m2','meter',attempt_id='physical-2',logical_id='op',meter_id='leaf2',tokens=11),
        event('m3','meter',attempt_id='physical-3',logical_id='op',meter_id='leaf3',tokens=13),
        event('wrapper','wrapper',tokens=31,leaf_meter_ids=('leaf1','leaf2','leaf3')),
    )
    replay = s.replay_execution((spell(access=True),), events + (events[4],), as_of=ORIGIN)
    assert replay.total_tokens == 31
    assert len(replay.meters) == 3 and len(replay.starts) == 1
    assert replay.ongoing_roots == ('r',)
    with pytest.raises(ValueError, match='meter'):
        s.replay_execution((),events+(replace(events[4],event_id='conflict',tokens=8),),as_of=ORIGIN)
    with pytest.raises(ValueError, match='relationship'):
        event('bad','meter',attempt_id='physical-1',meter_id='bad',tokens=1,meter_relationship='unknown')


def test_lineage_cycles_and_unresolved_parent_are_rejected():
    s = api()
    with pytest.raises(ValueError,match='lineage'):
        s.replay_execution((),(event('start','root_start'),event('a','attempt',attempt_id='a',logical_id='op',parent_attempt_id='b',relationship='retry')),as_of=ORIGIN)
    with pytest.raises(ValueError,match='lineage'):
        s.replay_execution((),(event('start','root_start'),event('a','attempt',attempt_id='a',logical_id='op',parent_attempt_id='b',relationship='retry'),event('b','attempt',attempt_id='b',logical_id='op',parent_attempt_id='a',relationship='retry')),as_of=ORIGIN)


def test_origin_replay_and_fit_ignore_late_events_and_missing_observation_days():
    s = api()
    exposures=(replace(spell(access=True),end=date(2024,1,3)),replace(spell(access=True),spell_id='gap',start=date(2024,1,3),observed=False))
    events=(event('start','root_start'),event('a','attempt',attempt_id='a',logical_id='op'),event('m','meter',attempt_id='a',logical_id='op',meter_id='m',tokens=8))
    late=replace(event('late','root_start',root='late',day=1),known_at=datetime(2024,1,6,tzinfo=UTC))
    fit=s.fit_recurrent_hurdle(exposures,events+(late,),as_of=ORIGIN)
    assert fit[0].p_any == .5
    assert fit[0].positive_counts == (1,)
    assert fit[0].marks[0].tokens == 8
    assert s.replay_execution(exposures,events,as_of=ORIGIN).evidence_id == s.replay_execution(exposures,events+(late,),as_of=ORIGIN).evidence_id


def test_catalog_feasibility_and_capability_uncertainty_are_shared_per_path():
    s=api()
    config=s.ConsumedConfiguration('small',datetime(2023,12,1,tzinfo=UTC),date(2024,1,1),date(2025,1,1),100,(.2,.8))
    mark=s.ExecutionMark(5,'request','small','bill',context_tokens=50)
    result=generate((spell('a',access=True),spell('b',access=True)),parameters=(s.HurdleParameters('team',1.,marks=(mark,)),),catalog=(config,),path_count=100)
    assert {p.capability_draws[0][1] for p in result.paths} == {.2,.8}
    assert all({r.capability for r in p.roots} == {p.capability_draws[0][1]} for p in result.paths)
    assert result.paths[0].roots[0].mark.billed_configuration == 'bill'
    impossible=replace(mark,context_tokens=101)
    with pytest.raises(ValueError,match='feasible'):
        generate(parameters=(s.HurdleParameters('team',1.,marks=(impossible,)),),catalog=(config,))


def test_unknown_capability_mass_and_zero_exposure_are_explicit():
    result=generate()
    assert result.diagnostics.unknown_capability_token_share == 1.
    assert result.diagnostics.zero_exposure_path_share == 0.
    s=api()
    zero=generate(parameters=(s.HurdleParameters('team',0.),))
    assert zero.diagnostics.unknown_capability_token_share is None
    assert zero.diagnostics.zero_exposure_path_share == 1.


def test_replay_determinism_and_all_material_scenario_inputs_bind_identity():
    a,b=generate(),generate()
    assert a.bundle.bundle_id == b.bundle.bundle_id
    s=api()
    different=generate(shocks=(s.CommonShock(.5,1),))
    assert different.bundle.bundle_id != a.bundle.bundle_id
    with pytest.raises(ValueError):
        s.ExecutionMark(float('inf'))
    with pytest.raises(ValueError):
        s.HurdleParameters('team',1.,(0,))


def test_rehire_retains_known_ever_use_when_new_spell_prior_is_unknown():
    old = replace(spell(access=True,prior_use=True),end=date(2024,1,3))
    rehire = replace(spell(access=True,prior_use=None),spell_id='rehire',start=date(2024,1,4))
    result = generate((old,rehire))
    assert result.paths[0].first_observed_use == ()
    assert result.diagnostics.unknown_prior_use_people == ()


def test_unknown_access_requires_assumption_and_preserves_unknown_diagnostic():
    with pytest.raises(ValueError,match='unknown access'):
        generate((spell(access=None),))
    result = generate((spell(access=None),),unknown_access=False)
    assert result.bundle.totals() == (0.,0.,0.)
    assert result.diagnostics.unknown_access_people == ('a',)


def test_zero_token_execution_outcomes_are_bound_in_bundle_identity():
    s=api()
    par=(s.HurdleParameters('team',1.,marks=(s.ExecutionMark(0),)),)
    yes=generate(parameters=par,mode='proposal',admission=lambda *args:True,admission_id='policy')
    no=generate(parameters=par,mode='proposal',admission=lambda *args:False,admission_id='policy')
    assert yes.bundle.totals() == no.bundle.totals() == (0.,0.,0.)
    assert yes.bundle.bundle_id != no.bundle.bundle_id


def test_stateful_admission_capacity_restarts_for_each_path():
    class OneRootPerPath:
        def for_path(self, path_id):
            admitted=[]
            def decide(root, when, mark, person):
                if admitted:
                    return False
                admitted.append(root)
                return True
            return decide
    result=generate(mode='proposal',admission=OneRootPerPath(),admission_id='one-root')
    assert result.bundle.totals() == (10.,10.,10.)
    assert all(len(p.first_trials)==1 and len(p.blocked_proposals)==2 for p in result.paths)


def test_invalid_unknown_probability_and_numeric_boolean_exposure_are_rejected():
    s=api()
    with pytest.raises(ValueError):
        s.HurdleParameters('team',None)
    with pytest.raises(ValueError):
        spell(access=1)


def test_nonqualifying_execution_never_creates_first_trial():
    s=api()
    result=generate(parameters=(s.HurdleParameters('team',1.,marks=(s.ExecutionMark(2,qualifying=False),)),))
    assert result.bundle.totals() == (6.,6.,6.)
    assert result.paths[0].first_trials == ()
    assert result.paths[0].ever_used == (('a',False),)


def test_derived_path_overflow_is_rejected():
    s=api()
    with pytest.raises(ValueError,match='finite'):
        generate(parameters=(s.HurdleParameters('team',1.,marks=(s.ExecutionMark(1e308),)),))


def test_pricing_axes_use_billed_identity_while_roots_retain_served_identity():
    s=api()
    config=s.ConsumedConfiguration('served',datetime(2023,12,1,tzinfo=UTC),date(2024,1,1),date(2025,1,1),100)
    mark=s.ExecutionMark(4,'requested','served','billed')
    result=generate(parameters=(s.HurdleParameters('team',1.,marks=(mark,)),),catalog=(config,))
    assert result.bundle.axes[0].configuration == 'billed'
    assert result.paths[0].roots[0].mark.served_configuration == 'served'


def test_late_catalog_evidence_cannot_make_origin_route_feasible():
    s=api()
    config=s.ConsumedConfiguration('future',datetime(2024,1,5,tzinfo=UTC),date(2024,1,1),date(2025,1,1),100)
    with pytest.raises(ValueError,match='feasible'):
        generate(parameters=(s.HurdleParameters('team',1.,marks=(s.ExecutionMark(4,served_configuration='future'),)),),catalog=(config,))


def test_overlapping_exposure_never_doubles_person_risk_set():
    s=api()
    with pytest.raises(ValueError,match='overlapping'):
        s.replay_execution((spell(access=True),replace(spell(access=True),spell_id='overlap')),(),as_of=ORIGIN)


def test_ongoing_roots_require_explicit_continuation_law_in_total_forecast():
    with pytest.raises(ValueError,match='continuation'):
        generate(events=(event('start','root_start'),))


def test_forecast_origin_cannot_skip_recurrent_transitions_in_an_unmodeled_gap():
    s=api()
    with pytest.raises(ValueError,match='origin'):
        s.generate_recurrent_scenarios((spell(access=True),),(),(s.HurdleParameters('team',1.),),
            as_of=ORIGIN,dates=(date(2024,1,6),),path_count=1,seed=1,target=TARGET,snapshot_id='snap')


def test_parameters_fitted_after_forecast_origin_cannot_leak_future_marks():
    s = api()
    exposures = (spell(access=True),)
    events = (
        event('future-start', 'root_start', day=5),
        event('future-attempt', 'attempt', day=5, attempt_id='future-attempt', logical_id='op'),
        event('future-meter', 'meter', day=5, attempt_id='future-attempt', logical_id='op',
              meter_id='future-meter', tokens=123456),
        event('future-end', 'root_end', day=5),
    )
    fitted = s.fit_recurrent_hurdle(exposures, events, as_of=datetime(2024,1,7,tzinfo=UTC))
    with pytest.raises(ValueError, match='fitted.*origin'):
        generate(exposures, events, parameters=fitted, path_count=100)


def test_actual_fit_cutoff_cannot_be_removed_or_relabelled_as_supplied():
    s = api()
    fitted = s.fit_recurrent_hurdle((spell(access=True),), (), as_of=ORIGIN)[0]
    assert fitted.parameter_source == 'fitted'
    assert fitted.fit_as_of == ORIGIN
    assert fitted.fit_evidence_id
    with pytest.raises(ValueError, match='fitted'):
        replace(fitted, fit_as_of=None)
    with pytest.raises(ValueError, match='supplied'):
        replace(fitted, parameter_source='supplied')
    with pytest.raises(ValueError, match='supplied'):
        replace(fitted, parameter_source='supplied', fit_as_of=None, fit_evidence_id='')
    # An explicitly supplied hypothesis remains supported independently of fitting.
    supplied = s.HurdleParameters('team', 1., marks=(s.ExecutionMark(123456),))
    assert generate(parameters=(supplied,)).bundle.totals() == (370368.,370368.,370368.)
    assert generate(parameters=(fitted,)).bundle.totals() == (0.,0.,0.)


@pytest.mark.parametrize('prior_use,p_any,p_returning,first_trials', [
    (False, 1., None, (('a',date(2024,1,5)),)),
    (True, 0., 1., ()),
])
def test_future_exposure_prior_use_applies_at_effective_entry(prior_use,p_any,p_returning,first_trials):
    s = api()
    future_spell = replace(spell(access=True,prior_use=prior_use),start=date(2024,1,5))
    parameters = (s.HurdleParameters('team',p_any,marks=(s.ExecutionMark(10),),p_returning=p_returning),)
    result = s.generate_recurrent_scenarios((future_spell,),(),parameters,as_of=ORIGIN,
        dates=DATES[:2],path_count=1,seed=7,target=TARGET,snapshot_id='snapshot')
    assert result.bundle.totals() == (10.,)
    assert result.paths[0].first_trials == first_trials
    assert result.paths[0].first_observed_use == ()
    assert result.paths[0].ever_used == (('a',True),)


def test_future_known_never_spell_does_not_reset_already_emitted_first_trial():
    first_spell = replace(spell(access=True,prior_use=False),end=date(2024,1,5))
    next_spell = replace(spell(access=True,prior_use=False),spell_id='rehire',start=date(2024,1,5))
    result = generate((first_spell,next_spell))
    assert result.paths[0].first_trials == (('a',DATES[0]),)
    assert result.paths[0].first_observed_use == ()


def test_historical_recency_uses_utc_service_date_for_offset_events():
    s = api()
    offset_stamp = datetime(2024,1,2,23,30,tzinfo=timezone(timedelta(hours=-8)))
    events = (
        s.ExecutionEvent('offset-start','root','a',offset_stamp,offset_stamp,'root_start'),
        s.ExecutionEvent('offset-end','root','a',offset_stamp,offset_stamp,'root_end'),
    )
    result = generate(events=events,parameters=(s.HurdleParameters('team',0.),))
    assert result.paths[0].last_use == (('a',date(2024,1,3)),)
    assert result.bundle.totals() == (0.,0.,0.)
