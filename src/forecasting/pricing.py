"""Explicit synthetic contract primitives, computed once over the complete pool.

Not a provider tariff engine: seat/credit/commitment/tax/FX terms require separate
verified adapters. Values are planning estimates, never posted charges.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from fractions import Fraction
from typing import Optional, Tuple
from .contracts import ContractError, Serializable, aware, decimal, interval, exact_sum, exact_product

@dataclass(frozen=True)
class Tier(Serializable):
    up_to: Optional[Decimal]
    rate: Decimal
    def __post_init__(self):
        if not isinstance(self.rate,Decimal):raise ContractError('Decimal tier rate required')
        decimal(self.rate)
        if self.rate<0:raise ContractError('negative tier rate')
        if self.up_to is not None:
            if not isinstance(self.up_to,Decimal):raise ContractError('Decimal tier boundary required')
            decimal(self.up_to)
            if self.up_to<=0:raise ContractError('positive tier boundary required')

@dataclass(frozen=True)
class PricingContract(Serializable):
    contract_id: str
    version: str
    currency: str
    unit: str
    period_start: date
    period_end: date
    known_at: datetime
    allowance: Decimal = Decimal(0)
    rate: Decimal = Decimal(0)
    fixed: Decimal = Decimal(0)
    mode: str = 'linear'
    tiers: Tuple[Tier,...] = ()

    def __post_init__(self):
        interval(self.period_start,self.period_end);aware(self.known_at)
        if type(self.tiers) is not tuple or any(type(t) is not Tier for t in self.tiers):raise ContractError('immutable tuple of validated Tier objects required')
        for x in (self.allowance,self.rate,self.fixed):
            if not isinstance(x,Decimal):raise ContractError('Decimal pricing terms required')
            decimal(x)
            if x<0:raise ContractError('nonnegative tariff terms required')
        if self.mode not in {'linear','graduated','volume'}:raise ContractError('unsupported tariff; credits, seat transitions, commitments, tax and FX need verified adapters')
        if not self.contract_id or not self.version or not self.unit or len(self.currency)!=3:raise ContractError('complete versioned pricing identity required')
        if self.mode=='linear' and self.tiers:raise ContractError('linear tariff cannot carry tiers')
        if self.mode!='linear':
            if not self.tiers or self.tiers[-1].up_to is not None or any(t.up_to is None for t in self.tiers[:-1]):raise ContractError('tiers must end with one unlimited band')
            bounds=[t.up_to for t in self.tiers[:-1]]
            if bounds!=sorted(set(bounds)):raise ContractError('tier boundaries must increase')

@dataclass(frozen=True)
class PriceResult(Serializable):
    contract_id: str
    contract_version: str
    currency: str
    prefix_variable: Decimal
    future_increment: Decimal
    variable_total: Decimal
    fixed: Decimal
    statistic: str = 'point'
    @property
    def total(self):return exact_sum((self.variable_total,self.fixed))


def _quantity(by_entity):
    total=Decimal(0)
    for q in by_entity.values():
        decimal(q)
        if not isinstance(q,Decimal) or q<0:raise ContractError('usage path requires nonnegative Decimal quantities')
        total=exact_sum((total,q))
    return total


def _variable(c,usage):
    billable=max(Decimal(0),exact_sum((usage,c.allowance.copy_negate())))
    if c.mode=='linear':return exact_product(billable,c.rate)
    if c.mode=='volume':
        for tier in c.tiers:
            if tier.up_to is None or billable<=tier.up_to:return exact_product(billable,tier.rate)
    total=Decimal(0);lower=Decimal(0)
    for tier in c.tiers:
        upper=billable if tier.up_to is None else min(billable,tier.up_to)
        total=exact_sum((total,exact_product(max(Decimal(0),exact_sum((upper,lower.copy_negate()))),tier.rate)))
        if upper==billable:break
        lower=tier.up_to
    return total


def price_period(contract,prefix_usage,future_usage,*,as_of=None,period_start=None,period_end=None):
    """Caller supplies all pool usage for this one contract period, across all teams."""
    if as_of is not None and aware(as_of)<contract.known_at:raise ContractError('pricing version unknown at origin')
    if period_start is not None and period_start!=contract.period_start:raise ContractError('full contract period required')
    if period_end is not None and period_end!=contract.period_end:raise ContractError('cross-reset/multi-period pricing unsupported; split complete periods')
    before=_quantity(prefix_usage);future=_quantity(future_usage)
    prefix=_variable(contract,before);full=_variable(contract,exact_sum((before,future)))
    return PriceResult(contract.contract_id,contract.version,contract.currency,prefix,exact_sum((full,prefix.copy_negate())),full,contract.fixed)


def price_paths(contract,prefix_usage,paths,**kwargs):
    """Expected total charge of explicit weighted joint usage paths, including fixed."""
    if not paths:raise ContractError('joint paths required')
    mass=Decimal(0);expected=Decimal(0)
    for future,probability in paths:
        decimal(probability)
        if probability<0:raise ContractError('negative path probability')
        mass=exact_sum((mass,probability));expected=exact_sum((expected,exact_product(probability,price_period(contract,prefix_usage,future,**kwargs).total)))
    if mass!=1:raise ContractError('path probabilities must sum exactly to one')
    return expected


def allocate(amount,weights,*,fractional_places=28):
    """Approved proportional allocation with deterministic residual policy.

    Compute exact rational proportions. Round each nonfinal positive recipient
    toward zero at max(fractional_places, input amount scale) decimal places;
    the last positive key in sorted order receives the exact residual. Zero
    weights always receive zero. Signed credits preserve their sign. This is a
    planning allocation policy, not currency settlement rounding.
    """
    if not isinstance(amount,Decimal):raise ContractError('Decimal allocation amount required')
    decimal(amount)
    if type(fractional_places) is not int or not 0<=fractional_places<=1000:raise ContractError('allocation fractional_places must be an integer in [0,1000]')
    for key,w in weights.items():
        if not isinstance(key,str) or not key or not isinstance(w,Decimal):raise ContractError('named Decimal allocation weights required')
        decimal(w)
        if w<0:raise ContractError('negative allocation weight')
    total=exact_sum(weights.values())
    if total==0:return {'central':amount}
    result={key:Decimal(0) for key in weights}
    items=sorted((key,w) for key,w in weights.items() if w>0)
    scale=min(amount.as_tuple().exponent,-fractional_places)
    quantum=Fraction(Decimal((0,(1,),scale)))
    used=Decimal(0)
    for i,(key,weight) in enumerate(items):
        if i==len(items)-1:
            value=exact_sum((amount,used.copy_negate()))
        else:
            units=int(Fraction(amount)*Fraction(weight)/Fraction(total)/quantum)
            value=Decimal((int(units<0),tuple(int(c) for c in str(abs(units))),scale))
        result[key]=value;used=exact_sum((used,value))
    return result
