from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
import pytest
from forecasting.contracts import ContractError
from forecasting.controls import (ControlPolicy, ControlEvent, Attempt, ControlState, simulate_controls)

T=datetime(2026,10,15,tzinfo=timezone.utc)
def policy(mode='hard',limit='10',concurrency=2): return ControlPolicy('p','pool','tokens',D(limit),concurrency,mode)
def ev(i,kind,attempt='',amount='0',seconds=0,entity='a',policy_value=None):
    return ControlEvent(i,T+timedelta(seconds=seconds),kind,attempt,entity,D(amount),policy_value)

def test_concurrent_reservation_race_is_shared_across_entities():
    out=simulate_controls(policy(),(ev('1','proposal','a','7'),ev('2','proposal','b','7',entity='b')))
    assert [d.admitted for d in out.decisions]==[True,False]
    assert out.state.available==D(3) and len(out.state.attempts)==1

def test_cancel_ack_releases_concurrency_but_keeps_liability_until_settlement():
    out=simulate_controls(policy(concurrency=1),(ev('1','proposal','a','7'),ev('2','start','a'),ev('3','cancel_ack','a'),ev('4','proposal','b','4')))
    assert out.state.available==D(3) and not out.decisions[-1].admitted
    done=simulate_controls(policy(concurrency=1),(ev('5','settle','a','5'),ev('6','proposal','b','4')),opening=out.state)
    assert done.state.available==D(1) and done.decisions[-1].admitted

def test_estimate_mode_exposes_overshoot_while_hard_mode_checks_bound():
    events=(ev('1','proposal','a','7'),ev('2','start','a'),ev('3','end','a'),ev('4','settle','a','12'))
    out=simulate_controls(policy('estimate'),events)
    assert out.state.available==D(-2) and out.overshoot==D(2) and not out.hard_assurance
    with pytest.raises(ContractError,match='bound'): simulate_controls(policy(),events)

def test_reset_reconfiguration_preserves_opening_inflight_liability():
    p=policy(); opening=ControlState(p,D(2),(Attempt('a','team',D(7),True,False,False),),())
    out=simulate_controls(p,(ev('r','reset'),ev('c','reconfigure',policy_value=policy(limit='8')),ev('1','proposal','b','2')),opening)
    assert out.state.available==D(1) and not out.decisions[-1].admitted

def test_delivered_bypass_and_budget_only_invariance():
    out=simulate_controls(policy(limit='0'),(ev('1','delivered','a','8'),ev('2','budget',amount='999')))
    assert out.decisions[0].admitted and not out.hard_assurance and out.state.available==D(-8)
    base=simulate_controls(policy(),(ev('1','proposal','a','2'),))
    changed=simulate_controls(policy(),(ev('1','proposal','a','2'),ev('2','budget',amount='999')))
    assert (base.state.policy,base.state.settled_debit,base.state.attempts,base.state.available)==(changed.state.policy,changed.state.settled_debit,changed.state.attempts,changed.state.available)
    assert changed.state.event_ids==base.state.event_ids+('2',)

def test_chronology_duplicate_settlement_and_concurrency_rejected():
    with pytest.raises(ContractError,match='chronological'):
        simulate_controls(policy(),(ev('1','budget',seconds=2),ev('2','budget',seconds=1)))
    out=simulate_controls(policy(concurrency=1),(ev('1','proposal','a','2'),ev('2','proposal','b','2')))
    assert not out.decisions[-1].admitted
    with pytest.raises(ContractError,match='settled'):
        simulate_controls(policy(),(ev('1','proposal','a','2'),ev('cancel','cancel_ack','a'),ev('2','settle','a','2'),ev('3','settle','a','2')))

def test_proposal_callback_adapter_reserves_once_and_supports_explicit_lifecycle():
    from forecasting.controls import ControlAdmission
    adapter=ControlAdmission(policy(concurrency=1),lambda mark:D(str(mark)))
    assert adapter('root-1',T,7,'a')
    assert not adapter('root-2',T,7,'b')
    adapter.apply((ev('end','end','root-1'),ev('settle','settle','root-1','3')))
    assert adapter('root-3',T,7,'b')
    assert adapter.state.available==D(0)

def test_admission_adapter_forks_independent_path_ledgers():
    from forecasting.controls import ControlAdmission
    adapter=ControlAdmission(policy(concurrency=1),lambda mark:D(str(mark)))
    a=adapter.for_path('path-a'); b=adapter.for_path('path-b')
    assert a('a',T,7,'entity') and b('b',T,7,'entity')
    assert a.state.available==b.state.available==D(3)
    assert adapter.state.available==D(10)

def test_estimated_open_liability_does_not_become_bounded_after_policy_change():
    out=simulate_controls(policy('estimate'),(ev('1','reserve','a','2'),ev('2','reconfigure',policy_value=policy())))
    assert not out.hard_assurance
    settled=simulate_controls(out.state.policy,(ev('cancel','cancel_ack','a'),ev('3','settle','a','12')),out.state)
    assert settled.overshoot==D(2)

def test_simulation_identity_binds_rejected_liability_and_internal_budget_inputs():
    a=simulate_controls(policy(limit='0'),(ev('1','proposal','a','1'),))
    b=simulate_controls(policy(limit='0'),(ev('1','proposal','a','2'),))
    assert a.state==b.state and a.input_id!=b.input_id

@pytest.mark.parametrize('started',[False,True])
def test_settlement_cannot_release_liability_before_terminal_execution(started):
    events=[ev('reserve','reserve','a','7')]
    if started: events.append(ev('start','start','a'))
    events.append(ev('settle','settle','a','0'))
    with pytest.raises(ContractError,match='end|terminal'):
        simulate_controls(policy(),events)

@pytest.mark.parametrize('started',[False,True])
def test_opening_settled_attempt_cannot_remain_startable_or_live(started):
    with pytest.raises(ContractError,match='end|terminal'):
        ControlState(policy(),attempts=(Attempt('a','entity',D(0),started,False,True),))

def test_prestart_cancel_ack_and_settlement_are_terminal():
    result=simulate_controls(policy(),(ev('r','reserve','a','7'),ev('c','cancel_ack','a'),ev('s','settle','a','0')))
    assert result.state.available==D(10)
    with pytest.raises(ContractError,match='start|end'):
        simulate_controls(policy(),(ev('start','start','a'),),result.state)

def test_reset_retains_realized_overshoot_and_whole_trajectory_qualification():
    events=(ev('r','reserve','a','7'),ev('s','start','a'),ev('e','end','a'),ev('paid','settle','a','12'),
            ev('reset','reset'),ev('hard','reconfigure',policy_value=policy()))
    result=simulate_controls(policy('estimate'),events)
    assert result.overshoot==D(2) and result.state.available==D(10)
    assert result.final_deficit==D(0) and not result.hard_assurance

def test_chunked_adapter_preserves_breach_and_assurance_after_reset():
    from forecasting.controls import ControlAdmission
    adapter=ControlAdmission(policy('estimate'),lambda mark:D(str(mark)))
    assert adapter('a',T,7,'entity')
    breach=adapter.apply((ev('end','end','a'),ev('settle','settle','a','12')))
    assert breach.overshoot==D(2)
    reset=adapter.apply((ev('reset','reset'),ev('hard','reconfigure',policy_value=policy())))
    resumed=adapter.apply(())
    assert reset.overshoot==resumed.overshoot==D(2)
    assert reset.final_deficit==resumed.final_deficit==D(0)
    assert not reset.hard_assurance and not resumed.hard_assurance

def test_budget_only_chunk_persists_chronology_and_replay_without_physical_change():
    original=ControlState(policy())
    out=simulate_controls(policy(),(ev('budget','budget',seconds=10),),original)
    assert out.state.last_at==T+timedelta(seconds=10) and out.state.event_ids==('budget',)
    assert (out.state.policy,out.state.attempts,out.state.settled_debit,out.state.available)==(original.policy,original.attempts,original.settled_debit,original.available)
    with pytest.raises(ContractError,match='duplicate'):
        simulate_controls(policy(),(ev('budget','budget',seconds=10),),out.state)
    with pytest.raises(ContractError,match='chronological'):
        simulate_controls(policy(),(ev('physical','proposal','a','1'),),out.state)
    with pytest.raises(ContractError,match='chronological'):
        simulate_controls(policy(),(ev('budget-earlier','budget'),),out.state)

def test_opening_deficit_remains_historical_after_reset():
    opening=ControlState(policy(),settled_debit=D(12))
    result=simulate_controls(policy(),(ev('reset','reset'),),opening)
    assert result.overshoot==D(2) and result.final_deficit==D(0)
    assert not result.hard_assurance

def test_chunked_budget_callback_rejects_earlier_and_replayed_events():
    from forecasting.controls import ControlAdmission
    adapter=ControlAdmission(policy(),lambda mark:D(str(mark)))
    adapter.apply((ev('budget','budget',seconds=10),))
    with pytest.raises(ContractError,match='chronological'):
        adapter('a',T,1,'entity')
    with pytest.raises(ContractError,match='duplicate'):
        adapter.apply((ev('budget','budget',seconds=10),))
