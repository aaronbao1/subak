"""Strict, versioned financial boundaries; Decimal values never serialize as floats."""
from __future__ import annotations
from dataclasses import dataclass, fields, is_dataclass
from datetime import date, datetime, time
from decimal import Decimal, Context, Inexact, InvalidOperation, Overflow, ROUND_HALF_EVEN, MAX_EMAX, MIN_EMIN, localcontext
from hashlib import sha256
import json
from typing import Any, Mapping, Optional, Tuple
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

SCHEMA_VERSION = '1.0'

class ContractError(ValueError):
    pass


def decimal(value: Any) -> Decimal:
    if not isinstance(value, (str, Decimal)):
        raise ContractError('financial values must be decimal strings or Decimal')
    try:
        result = Decimal(value)
    except InvalidOperation as exc:
        raise ContractError('invalid decimal') from exc
    if not result.is_finite():
        raise ContractError('nonfinite decimal')
    return result


def exact_sum(values) -> Decimal:
    """Sum finite Decimals with enough local precision for every input digit."""
    values=tuple(values)
    if not values:return Decimal(0)
    for value in values:
        if not isinstance(value,Decimal):raise ContractError('exact arithmetic requires Decimal')
        decimal(value)
    low=min(v.as_tuple().exponent for v in values)
    high=max(v.adjusted() for v in values)
    with localcontext(Context(prec=max(28,high-low+len(str(len(values)))+3),
                              rounding=ROUND_HALF_EVEN, Emin=MIN_EMIN, Emax=MAX_EMAX,
                              capitals=1, clamp=0, flags=[], traps=[Inexact,InvalidOperation,Overflow])):
        return decimal(sum(values,Decimal(0)))


def exact_product(left: Decimal, right: Decimal) -> Decimal:
    """Multiply finite decimals without global context rounding."""
    if not isinstance(left,Decimal) or not isinstance(right,Decimal):raise ContractError('exact arithmetic requires Decimal')
    decimal(left);decimal(right)
    with localcontext(Context(prec=max(28,len(left.as_tuple().digits)+len(right.as_tuple().digits)+2),
                              rounding=ROUND_HALF_EVEN, Emin=MIN_EMIN, Emax=MAX_EMAX,
                              capitals=1, clamp=0, flags=[], traps=[Inexact,InvalidOperation,Overflow])):
        return decimal(left*right)


def aware(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ContractError('timezone-aware timestamp required')
    return value


def timestamp(value: str) -> datetime:
    try:
        return aware(datetime.fromisoformat(value.replace('Z', '+00:00')))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ContractError('invalid aware timestamp') from exc


def day(value: str) -> date:
    try:
        result = date.fromisoformat(value)
    except (ValueError, TypeError) as exc:
        raise ContractError('invalid ISO service date') from exc
    return result


def interval(start: date, end: date) -> None:
    if type(start) is not date or type(end) is not date or start >= end:
        raise ContractError('nonempty half-open date interval required')


def primitive(value: Any) -> Any:
    if is_dataclass(value): return {f.name: primitive(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, Decimal): return str(value)
    if isinstance(value, (date, datetime)): return value.isoformat()
    if isinstance(value, Mapping): return {str(k):primitive(v) for k,v in value.items()}
    if isinstance(value, (tuple,list)): return [primitive(v) for v in value]
    return value


def canonical_json(value: Any) -> str:
    return json.dumps(primitive(value),sort_keys=True,separators=(',', ':'),allow_nan=False)


def digest(value: Any) -> str:
    return sha256(canonical_json(value).encode()).hexdigest()


def strict(cls, value: Mapping) -> dict:
    if not isinstance(value, Mapping): raise ContractError('object required')
    names = {f.name for f in fields(cls)}
    if set(value)-names: raise ContractError('unknown fields: '+','.join(sorted(set(value)-names)))
    return dict(value)

class Serializable:
    def to_dict(self): return primitive(self)

@dataclass(frozen=True)
class Target(Serializable):
    target_id: str
    tenant_id: str
    measure: str
    unit: str
    currency: Optional[str]
    sources: Tuple[str, ...]
    categories: Tuple[str, ...]
    period_basis: str = 'incurred'
    gross_net: str = 'net'
    tax_treatment: str = 'excluded'
    attribution_version: str = '1'
    reporting_timezone: str = 'UTC'
    support: str = 'signed'
    additive: bool = True
    version: str = SCHEMA_VERSION
    conversion_policy: str = 'native_only'
    source_partition_policy: Optional[str] = None

    def __post_init__(self):
        for name in ('target_id','tenant_id','measure','unit','period_basis','gross_net',
                     'tax_treatment','attribution_version','reporting_timezone','support',
                     'version','conversion_policy'):
            value = getattr(self,name)
            if not isinstance(value,str) or not value.strip():
                raise ContractError(name+' must be a nonempty string')
        if type(self.additive) is not bool:
            raise ContractError('additive must be a Boolean')
        for name in ('currency','source_partition_policy'):
            value = getattr(self,name)
            if value is not None and (not isinstance(value,str) or not value.strip()):
                raise ContractError(name+' must be a nonempty string or null')
        for name in ('sources','categories'):
            values = getattr(self,name)
            if not isinstance(values,tuple):
                raise ContractError('immutable source/category tuples required')
            if (not values or any(not isinstance(v,str) or not v.strip() for v in values)
                    or len(set(values)) != len(values)):
                raise ContractError('nonempty disjoint source/category identities required')
        if self.version != SCHEMA_VERSION: raise ContractError('unsupported target version')
        if not self.target_id or not self.tenant_id or not self.unit: raise ContractError('target identity and unit required')
        if self.measure not in {'metered_usage','list_price_equivalent','contract_priced_estimate','provider_reported_cost','invoice_amount','fixed_obligation','internal_allocation'}: raise ContractError('unknown target measure')
        if self.period_basis not in {'incurred','billed','cash'}: raise ContractError('unknown period basis')
        if self.gross_net not in {'gross','net'} or self.tax_treatment not in {'included','excluded','unknown'}: raise ContractError('unknown financial basis')
        if self.support not in {'signed','nonnegative'}: raise ContractError('unknown support')
        if self.measure == 'metered_usage' and (self.currency is not None or self.support != 'nonnegative'): raise ContractError('usage requires nonnegative physical units')
        if self.measure == 'metered_usage' and self.period_basis != 'incurred': raise ContractError('usage requires incurred physical flow')
        if self.measure != 'metered_usage' and (not self.currency or len(self.currency)!=3 or not self.currency.isascii() or not self.currency.isalpha() or not self.currency.isupper()): raise ContractError('monetary target requires explicit three-letter currency')
        if self.conversion_policy != 'native_only': raise ContractError('FX conversion requires an explicit supported bridge')
        try: ZoneInfo(self.reporting_timezone)
        except (ZoneInfoNotFoundError,ValueError) as exc: raise ContractError('unknown reporting timezone') from exc

    @classmethod
    def from_dict(cls, value):
        d=strict(cls,value)
        for k in ('sources','categories'):
            if k in d:
                if not isinstance(d[k],(list,tuple)):
                    raise ContractError(k+' must be an array of identities')
                d[k]=tuple(d[k])
        try: return cls(**d)
        except TypeError as exc: raise ContractError(str(exc)) from exc

@dataclass(frozen=True)
class ForecastRequest(Serializable):
    request_id: str
    target: Target
    as_of: datetime
    period_start: date
    period_end: date
    output: str = 'full_period'
    model: str = 'trailing_mean'
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self):
        if self.schema_version != SCHEMA_VERSION: raise ContractError('unsupported request version')
        aware(self.as_of); interval(self.period_start,self.period_end)
        if not self.request_id or not isinstance(self.target,Target): raise ContractError('request and target required')
        if self.output not in {'full_period','remainder'}: raise ContractError('unknown output scope')
        local=self.as_of.astimezone(ZoneInfo(self.target.reporting_timezone))
        if local.timetz().replace(tzinfo=None) != time(): raise ContractError('daily core requires reporting-calendar midnight origin; subdaily remainder unsupported')

    @classmethod
    def from_dict(cls,value):
        d=strict(cls,value)
        try:
            d['target']=Target.from_dict(d['target']); d['as_of']=timestamp(d['as_of'])
            d['period_start']=day(d['period_start']); d['period_end']=day(d['period_end'])
            return cls(**d)
        except (KeyError,TypeError) as exc: raise ContractError(str(exc)) from exc

@dataclass(frozen=True)
class ForecastResult(Serializable):
    result_id: str
    request_id: str
    target: Target
    snapshot_id: str
    as_of: datetime
    period_start: date
    period_end: date
    recorded: Optional[Decimal]
    late: Optional[Decimal]
    future: Optional[Decimal]
    fixed: Optional[Decimal]
    status: str
    model: str
    statistic: str
    limitations: Tuple[str,...] = ()
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self):
        if self.schema_version != SCHEMA_VERSION: raise ContractError('unsupported result version')
        if not isinstance(self.target,Target): raise ContractError('typed target required')
        if self.target.measure == 'metered_usage' and self.fixed is not None:
            raise ContractError('fixed monetary obligations cannot be physical usage')
        aware(self.as_of); interval(self.period_start,self.period_end)
        if self.status not in {'ready','limited','unavailable','stale','fallback'}: raise ContractError('unknown result status')
        if self.statistic not in {'point','mean','median'}: raise ContractError('unsupported statistic')
        for name in ('recorded','late','future','fixed'):
            value=getattr(self,name)
            if value is not None:
                decimal(value)
                if self.target.support=='nonnegative' and value<0: raise ContractError('negative value outside target support')
        if self.status == 'ready' and self.variable_total is None: raise ContractError('ready result requires all variable components')
        if self.status in {'limited','stale','fallback','unavailable'} and not self.limitations: raise ContractError('degraded results require limitations')

    @property
    def variable_total(self):
        if any(v is None for v in (self.recorded,self.late,self.future)): return None
        return exact_sum((self.recorded,self.late,self.future))

    @classmethod
    def from_dict(cls,value):
        d=strict(cls,value)
        try:
            d['target']=Target.from_dict(d['target']);d['as_of']=timestamp(d['as_of'])
            for k in ('period_start','period_end'): d[k]=day(d[k])
            for k in ('recorded','late','future','fixed'):
                if d.get(k) is not None: d[k]=decimal(d[k])
            d['limitations']=tuple(d.get('limitations',()))
            return cls(**d)
        except (KeyError,TypeError) as exc: raise ContractError(str(exc)) from exc
