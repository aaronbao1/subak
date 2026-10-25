"""Pure chronological quota/concurrency scenario simulation; no enforcement I/O."""
from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal
from typing import Optional, Tuple
from .contracts import ContractError, Serializable, aware, decimal, exact_sum, digest


def _nonnegative(value):
    if not isinstance(value,Decimal) or decimal(value)<0:
        raise ContractError('nonnegative finite Decimal control amount required')


@dataclass(frozen=True)
class ControlPolicy(Serializable):
    version: str
    pool: str
    unit: str
    limit: Decimal
    concurrency: int
    mode: str = 'hard'

    def __post_init__(self):
        _nonnegative(self.limit)
        if not self.version or not self.pool or not self.unit or self.mode not in {'hard','estimate'}:
            raise ContractError('explicit versioned control scope and mode required')
        if type(self.concurrency) is not int or self.concurrency<1:
            raise ContractError('positive integer concurrency required')


@dataclass(frozen=True)
class Attempt(Serializable):
    attempt_id: str
    entity_id: str
    reservation: Decimal
    started: bool = False
    ended: bool = False
    settled: bool = False
    bounded: bool = True

    def __post_init__(self):
        _nonnegative(self.reservation)
        if not self.attempt_id or not self.entity_id: raise ContractError('physical attempt identity required')
        if any(type(x) is not bool for x in (self.started,self.ended,self.settled,self.bounded)):
            raise ContractError('Boolean attempt lifecycle flags required')
        if self.settled and self.reservation!=0: raise ContractError('settled attempt cannot retain reservation')
        if self.settled and not self.ended: raise ContractError('settled attempt requires terminal execution end or cancellation acknowledgement')


@dataclass(frozen=True)
class ControlState(Serializable):
    policy: ControlPolicy
    settled_debit: Decimal = Decimal(0)
    attempts: Tuple[Attempt,...] = ()
    event_ids: Tuple[str,...] = ()
    last_at: Optional[datetime] = None
    bypassed: bool = False
    peak_overshoot: Decimal = Decimal(0)
    hard_assurance_lost: bool = False

    def __post_init__(self):
        _nonnegative(self.settled_debit); _nonnegative(self.peak_overshoot)
        if type(self.bypassed) is not bool or type(self.hard_assurance_lost) is not bool:
            raise ContractError('Boolean qualification flags required')
        if type(self.attempts) is not tuple or any(type(a) is not Attempt for a in self.attempts):
            raise ContractError('immutable attempts required')
        if len({a.attempt_id for a in self.attempts})!=len(self.attempts): raise ContractError('duplicate attempt')
        if type(self.event_ids) is not tuple or len(set(self.event_ids))!=len(self.event_ids):
            raise ContractError('unique immutable event IDs required')
        if self.last_at is not None: aware(self.last_at)
        object.__setattr__(self,'peak_overshoot',max(self.peak_overshoot,Decimal(0),self.available.copy_negate()))
        lost=self.hard_assurance_lost or self.bypassed or self.policy.mode!='hard' or self.peak_overshoot>0 or any(not a.bounded for a in self.attempts)
        object.__setattr__(self,'hard_assurance_lost',lost)

    @property
    def available(self):
        return exact_sum((self.policy.limit,self.settled_debit.copy_negate(),
                          exact_sum(a.reservation for a in self.attempts).copy_negate()))


@dataclass(frozen=True)
class ControlEvent(Serializable):
    event_id: str
    occurred_at: datetime
    kind: str
    attempt_id: str = ''
    entity_id: str = ''
    amount: Decimal = Decimal(0)
    policy: Optional[ControlPolicy] = None

    def __post_init__(self):
        aware(self.occurred_at); _nonnegative(self.amount)
        if not self.event_id or self.kind not in {'proposal','reserve','start','end','cancel_ack','settle','reset','reconfigure','budget','delivered'}:
            raise ContractError('identified supported scenario event required')


@dataclass(frozen=True)
class Decision(Serializable):
    event_id: str
    attempt_id: str
    admitted: bool
    reason: str


@dataclass(frozen=True)
class ControlResult(Serializable):
    state: ControlState
    decisions: Tuple[Decision,...]
    overshoot: Decimal
    hard_assurance: bool
    input_id: str
    final_deficit: Decimal
    boundary: str = 'scenario_simulation_only'


def simulate_controls(policy,events,opening=None):
    """Input order is deterministic tie order; reject time travel and replay.

    Proposal/reserve atomically reserves quota and an execution slot across all
    entities in this scope. Execution end/cancel acknowledgement releases only
    the slot. Settlement releases liability independently. Reset clears settled
    period debit while retaining all unsettled opening liability. Delivered
    starts bypass admission and explicitly invalidate hard-bound assurance.
    """
    events=tuple(events)
    input_id=digest((policy,events,opening))
    state=opening if opening is not None else ControlState(policy)
    if state.policy!=policy: raise ContractError('opening policy mismatch; reconfigure explicitly')
    decisions=[]
    cursor=state.last_at
    seen=set(state.event_ids)
    for event in events:
        if cursor is not None and event.occurred_at<cursor:
            raise ContractError('chronological event order required')
        if event.event_id in seen: raise ContractError('duplicate control event')
        cursor=event.occurred_at; seen.add(event.event_id)
        if event.kind=='budget':
            # Audit metadata advances; allocations have no physical effect.
            state=replace(state,event_ids=state.event_ids+(event.event_id,),last_at=event.occurred_at)
            continue
        if event.event_id in state.event_ids: raise ContractError('duplicate control event')
        if state.last_at is not None and event.occurred_at<state.last_at:
            raise ContractError('chronological event order required')
        attempts={a.attempt_id:a for a in state.attempts}; debit=state.settled_debit; p=state.policy
        bypassed=state.bypassed
        if event.kind in {'proposal','reserve','delivered'}:
            if not event.attempt_id or not event.entity_id: raise ContractError('physical attempt/entity required')
            if event.attempt_id in attempts: raise ContractError('attempt already admitted')
            slots=sum(not a.ended for a in attempts.values())
            admitted=event.kind=='delivered' or (event.amount<=state.available and slots<p.concurrency)
            reason='delivered bypass' if event.kind=='delivered' else ('reserved' if admitted else 'quota or concurrency')
            if admitted:
                attempts[event.attempt_id]=Attempt(event.attempt_id,event.entity_id,event.amount,event.kind=='delivered',bounded=p.mode=='hard' and event.kind!='delivered')
            if event.kind=='delivered': bypassed=True
            decisions.append(Decision(event.event_id,event.attempt_id,admitted,reason))
        elif event.kind in {'start','end','cancel_ack','settle'}:
            if event.attempt_id not in attempts: raise ContractError('unknown physical attempt')
            a=attempts[event.attempt_id]
            if event.kind=='start':
                if a.started or a.ended or a.settled: raise ContractError('attempt cannot start twice or after terminal end')
                a=replace(a,started=True)
            elif event.kind in {'end','cancel_ack'}:
                if a.ended: raise ContractError('execution already ended')
                if event.kind=='end' and not a.started: raise ContractError('execution end requires a start')
                a=replace(a,ended=True)
            else:
                if a.settled: raise ContractError('attempt already settled')
                if not a.ended: raise ContractError('settlement requires terminal execution end or cancellation acknowledgement')
                if a.bounded and event.amount>a.reservation:
                    raise ContractError('settlement exceeds reserved hard liability bound')
                debit=exact_sum((debit,event.amount)); a=replace(a,reservation=Decimal(0),settled=True)
            attempts[event.attempt_id]=a
        elif event.kind=='reset':
            debit=Decimal(0)
        elif event.kind=='reconfigure':
            if event.policy is None or (event.policy.pool,event.policy.unit)!=(p.pool,p.unit):
                raise ContractError('reconfiguration must preserve liability scope and unit')
            p=event.policy
        state=ControlState(p,debit,tuple(attempts.values()),state.event_ids+(event.event_id,),event.occurred_at,bypassed,state.peak_overshoot,state.hard_assurance_lost)
    final_deficit=max(Decimal(0),state.available.copy_negate())
    return ControlResult(state,tuple(decisions),state.peak_overshoot,not state.hard_assurance_lost,input_id,final_deficit)


class ControlAdmission:
    """Narrow scenario-only callback adapter for the physical state generator.

    Create one adapter per path. ``liability(mark)`` must return a Decimal in the
    policy unit, bounded in hard mode. The adapter reserves and starts admitted
    proposals once. The caller must apply explicit end/cancel/settlement events;
    absent acknowledgement, concurrency and liability remain outstanding.
    """
    def __init__(self,policy,liability,opening=None):
        self.state=opening if opening is not None else ControlState(policy)
        if self.state.policy!=policy: raise ContractError('opening policy mismatch')
        self.liability=liability
        self.opening=self.state

    def for_path(self,path_id):
        if not isinstance(path_id,str) or not path_id: raise ContractError('path identity required')
        return ControlAdmission(self.opening.policy,self.liability,self.opening)

    def apply(self,events):
        result=simulate_controls(self.state.policy,events,self.state)
        self.state=result.state
        return result

    def __call__(self,root_id,occurred_at,mark,person_id):
        amount=self.liability(mark)
        result=self.apply((ControlEvent(root_id+':admit',occurred_at,'proposal',root_id,person_id,amount),))
        admitted=result.decisions[0].admitted
        if admitted:
            self.apply((ControlEvent(root_id+':start',occurred_at,'start',root_id,person_id),))
        return admitted
