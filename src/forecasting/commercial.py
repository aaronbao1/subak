"""Exact conditional contract estimates over complete, aligned scenario paths.

Synthetic or supplied contracts only. Native bundles remain readable when this
independent monetary view is unavailable; these outputs are never invoices.
"""
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from fractions import Fraction
import math
from typing import Optional, Tuple
from .contracts import ContractError, Serializable, aware, decimal, interval, exact_sum, digest
from .pricing import PricingContract, price_period, allocate


def _quantity(value):
    if not isinstance(value, Decimal) or decimal(value) < 0:
        raise ContractError('nonnegative finite Decimal quantity required')


@dataclass(frozen=True)
class MeterKey(Serializable):
    configuration: str
    meter: str
    unit: str
    pool: str

    def __post_init__(self):
        if any(not isinstance(x,str) or not x for x in (self.configuration,self.meter,self.unit,self.pool)):
            raise ContractError('complete meter identity required')


@dataclass(frozen=True)
class RateRevision(Serializable):
    revision_id: str
    key: MeterKey
    denominator: Decimal
    valid_start: date
    valid_end: date
    known_at: datetime
    contract: PricingContract

    def __post_init__(self):
        interval(self.valid_start,self.valid_end); aware(self.known_at)
        _quantity(self.denominator)
        if not self.revision_id or self.denominator == 0:
            raise ContractError('revision identity and positive denominator required')
        if self.key.unit != self.contract.unit:
            raise ContractError('incompatible meter and contract units')
        if self.known_at < self.contract.known_at:
            raise ContractError('catalog cannot predate contract knowledge')


@dataclass(frozen=True)
class TariffCatalog(Serializable):
    revisions: Tuple[RateRevision,...]

    def __post_init__(self):
        if type(self.revisions) is not tuple or any(type(x) is not RateRevision for x in self.revisions):
            raise ContractError('immutable rate revisions required')
        if len({r.revision_id for r in self.revisions}) != len(self.revisions):
            raise ContractError('duplicate revision identity')

    def resolve(self,key,start,end,as_of):
        aware(as_of); interval(start,end)
        matches=tuple(r for r in self.revisions if r.key==key and r.known_at<=as_of
                      and r.valid_start<=start and end<=r.valid_end
                      and r.contract.period_start==start and r.contract.period_end==end)
        if len(matches)>1: raise ContractError('ambiguous eligible tariff revisions')
        return matches[0] if matches else None


@dataclass(frozen=True)
class UsageAtom(Serializable):
    entity_id: str
    key: MeterKey
    quantity: Decimal

    def __post_init__(self):
        if not self.entity_id or type(self.key) is not MeterKey: raise ContractError('typed entity meter required')
        _quantity(self.quantity)


@dataclass(frozen=True)
class PeriodUsage(Serializable):
    path_id: str
    pool: str
    period_start: date
    period_end: date
    through: date
    meters: Tuple[MeterKey,...]
    known_prefix: Tuple[UsageAtom,...]
    late_prefix: Tuple[UsageAtom,...]
    future: Tuple[UsageAtom,...]
    complete: bool

    def __post_init__(self):
        if type(self.complete) is not bool:
            raise ContractError('period completeness must be bool')
        interval(self.period_start,self.period_end)
        if not self.path_id or not self.pool or not self.period_start<=self.through<=self.period_end:
            raise ContractError('path/pool and in-period coverage boundary required')
        if type(self.meters) is not tuple or len(set(self.meters))!=len(self.meters):
            raise ContractError('immutable nonduplicate meter manifest required')
        if not self.meters or any(type(m) is not MeterKey or m.pool!=self.pool for m in self.meters):
            raise ContractError('complete pool meter manifest required')
        for atoms in (self.known_prefix,self.late_prefix,self.future):
            if type(atoms) is not tuple or any(type(a) is not UsageAtom for a in atoms):
                raise ContractError('immutable usage atoms required')
            if len({(a.entity_id,a.key) for a in atoms})!=len(atoms):
                raise ContractError('duplicate entity meter within usage component')


@dataclass(frozen=True)
class AllocationLine(Serializable):
    entity_id: str
    prefix_variable: Decimal
    future_increment: Decimal
    fixed: Decimal

    @property
    def total(self): return exact_sum((self.prefix_variable,self.future_increment,self.fixed))


@dataclass(frozen=True)
class PricedPeriod(Serializable):
    pool: str
    period_start: date
    period_end: date
    contract_id: str
    contract_version: str
    allocation_version: str
    rate_revision_ids: Tuple[str,...]
    currency: str
    prefix_variable: Decimal
    future_increment: Decimal
    fixed: Decimal
    allocations: Tuple[AllocationLine,...]

    @property
    def total(self): return exact_sum((self.prefix_variable,self.future_increment,self.fixed))


@dataclass(frozen=True)
class PricedPath(Serializable):
    path_id: str
    weight: object
    periods: Tuple[PricedPeriod,...]

    @property
    def total(self): return exact_sum(p.total for p in self.periods)


@dataclass(frozen=True)
class CommercialResult(Serializable):
    bundle_id: str
    status: str
    paths: Tuple[PricedPath,...]
    reason: Optional[str]
    input_id: str
    basis: str = 'conditional_contract_estimate'


def _scaled(q,denominator):
    # Refuse nonterminating conversions rather than silently rounding rates.
    value=Fraction(q)/Fraction(denominator)
    den=value.denominator; twos=fives=0
    while den%2==0: den//=2; twos+=1
    while den%5==0: den//=5; fives+=1
    if den!=1: raise ContractError('quantity denominator requires nonterminating Decimal conversion')
    scale=max(twos,fives)
    coefficient=value.numerator * (2**(scale-twos)) * (5**(scale-fives))
    return Decimal((int(coefficient<0),tuple(int(c) for c in str(abs(coefficient))),-scale))


def _price_one(item,catalog,as_of,allocation_version):
    if type(item.complete) is not bool or not item.complete: raise ContractError('complete known and optional late prefix plus future coverage required')
    if item.through!=max(item.period_start,min(as_of.date(),item.period_end)):
        raise ContractError('prefix boundary must equal origin or contract period boundary')
    if item.through==item.period_start and any(a.quantity!=0 for a in item.known_prefix+item.late_prefix):
        raise ContractError('nonzero quantity in empty prefix interval')
    if item.through==item.period_end and any(a.quantity!=0 for a in item.future):
        raise ContractError('nonzero quantity in empty future interval')
    rates={key:catalog.resolve(key,item.period_start,item.period_end,as_of) for key in item.meters}
    if any(r is None for r in rates.values()): raise ContractError('missing compatible origin-known full-period tariff')
    contracts={digest(r.contract) for r in rates.values()}
    if len(contracts)!=1: raise ContractError('pool meters require one compatible shared contract')
    contract=next(iter(rates.values())).contract
    def quantities(atoms):
        result={}
        for atom in atoms:
            if atom.key not in rates: raise ContractError('usage meter absent from complete pool manifest')
            value=_scaled(atom.quantity,rates[atom.key].denominator)
            result[atom.entity_id]=exact_sum((result.get(atom.entity_id,Decimal(0)),value))
        return result
    prefix=quantities(item.known_prefix+item.late_prefix); future=quantities(item.future)
    p=price_period(contract,prefix,future,as_of=as_of,period_start=item.period_start,period_end=item.period_end)
    weights={e:exact_sum((prefix.get(e,Decimal(0)),future.get(e,Decimal(0)))) for e in set(prefix)|set(future)}
    before=allocate(p.prefix_variable,weights); after=allocate(p.future_increment,weights); fixed=allocate(p.fixed,weights)
    allocations=tuple(AllocationLine(e,before[e],after[e],fixed[e]) for e in sorted(before))
    if exact_sum(x.total for x in allocations)!=p.total: raise ContractError('allocation conservation failure')
    return PricedPeriod(item.pool,item.period_start,item.period_end,contract.contract_id,contract.version,
                        allocation_version,tuple(sorted(r.revision_id for r in rates.values())),contract.currency,
                        p.prefix_variable,p.future_increment,p.fixed,allocations)


def price_usage_paths(bundle_id,as_of,path_weights,catalog,periods,allocation_version):
    """Price each path/period exactly once; caller attests complete meter coverage.

    PeriodUsage manifests must form the same complete, nonoverlapping period set
    on every path. Prefix completeness is evidence supplied by the caller, never
    inferred from missing rows. Known and late prefix amounts are disjoint.
    """
    aware(as_of)
    input_id=digest((bundle_id,as_of,path_weights,catalog,periods,allocation_version))
    try:
        if allocation_version!='proportional-v1': raise ContractError('unsupported allocation policy')
        if not bundle_id or not path_weights or len({p for p,w in path_weights})!=len(path_weights):
            raise ContractError('unique aligned weighted paths required')
        for path,w in path_weights:
            if not path: raise ContractError('path identity required')
            if isinstance(w,Decimal): _quantity(w)
            elif isinstance(w,bool) or not isinstance(w,(int,float)) or not math.isfinite(w) or w<0:
                raise ContractError('finite nonnegative path weight required')
        ws=tuple(w for _,w in path_weights)
        if all(isinstance(w,Decimal) for w in ws):
            if exact_sum(ws)!=1: raise ContractError('weights must sum exactly to one')
        else:
            try: mass=math.fsum(ws)
            except (OverflowError,ValueError): raise ContractError('nonfinite derived weight mass')
            if not math.isfinite(mass) or not math.isclose(mass,1.,rel_tol=0.,abs_tol=1e-12):
                raise ContractError('normalized path weights required')
        grouped={p:[] for p,_ in path_weights}
        for item in periods:
            if item.path_id not in grouped: raise ContractError('unknown path identity')
            grouped[item.path_id].append(item)
        expected=None; result=[]; currencies=set()
        for path,w in path_weights:
            items=sorted(grouped[path],key=lambda x:(x.pool,x.period_start))
            keys={(x.pool,x.period_start,x.period_end) for x in items}
            if not keys or len(keys)!=len(items): raise ContractError('duplicate or missing complete periods')
            if expected is not None and keys!=expected: raise ContractError('complete periods must align across every path')
            expected=keys
            last={}
            for x in items:
                if x.pool in last and x.period_start!=last[x.pool]: raise ContractError('omitted or overlapping reset periods')
                last[x.pool]=x.period_end
            priced=tuple(_price_one(x,catalog,as_of,allocation_version) for x in items)
            currencies.update(x.currency for x in priced)
            result.append(PricedPath(path,w,priced))
        if len(currencies)!=1: raise ContractError('mixed currencies require an explicit FX transform')
        return CommercialResult(bundle_id,'available',tuple(result),None,input_id)
    except ContractError as exc:
        return CommercialResult(bundle_id,'unavailable',(),str(exc),input_id)


def price_bundle(bundle,catalog,prefixes,allocation_version='proportional-v1'):
    """Adapt one native ScenarioBundle without independently zipping draws.

    ``prefixes`` are complete PeriodUsage declarations, one per path/pool/reset,
    with empty future atoms. Every remaining service date of each declared
    contract period must be present in the native bundle. Weight values and path
    identities are retained unchanged. Numeric usage cells are converted using
    Decimal(str(cell)); this is an explicit valuation of the supplied path,
    not a claim that floating model output is a measured exact token count.
    """
    from dataclasses import replace
    from datetime import timedelta
    from zoneinfo import ZoneInfo
    input_id=digest((bundle.bundle_id,catalog,prefixes,allocation_version))
    try:
        if bundle.target.measure!='metered_usage' or bundle.scenario.kind!='probability_law':
            raise ContractError('native usage probability bundle required')
        origin=bundle.as_of.astimezone(ZoneInfo(bundle.target.reporting_timezone)).date()
        paths={p:i for i,p in enumerate(bundle.path_ids)}
        axes_by_pool={}
        for i,axis in enumerate(bundle.axes): axes_by_pool.setdefault(axis.pool,[]).append((i,axis))
        periods=[]; covered=set()
        for item in prefixes:
            if item.future: raise ContractError('prefix declarations cannot contain future usage')
            if item.path_id not in paths or item.pool not in axes_by_pool:
                raise ContractError('prefix has no matching native path/pool')
            if item.through!=max(item.period_start,min(origin,item.period_end)):
                raise ContractError('prefix coverage does not end at origin or period boundary')
            indices=tuple(i for i,d in enumerate(bundle.dates) if item.through<=d<item.period_end)
            expected=(item.period_end-item.through).days
            if len(indices)!=expected: raise ContractError('complete future contract-period dates required')
            pairs=axes_by_pool[item.pool]
            meters={MeterKey(a.configuration,a.meter,a.unit,a.pool) for _,a in pairs}
            if meters!=set(item.meters): raise ContractError('complete native meter manifest mismatch')
            atoms=[]
            for ai,axis in pairs:
                key=MeterKey(axis.configuration,axis.meter,axis.unit,axis.pool)
                q=exact_sum(Decimal(str(bundle.values[paths[item.path_id]][ai][di])) for di in indices)
                atoms.append(UsageAtom(axis.entity_id,key,q))
            for di in indices:
                cell=(item.path_id,item.pool,di)
                if cell in covered: raise ContractError('duplicate native contract-period coverage')
                covered.add(cell)
            periods.append(replace(item,future=tuple(atoms)))
        required={(p,pool,di) for p in bundle.path_ids for pool in axes_by_pool for di in range(len(bundle.dates))}
        if covered!=required: raise ContractError('complete future pool/date/path coverage required')
        return price_usage_paths(bundle.bundle_id,bundle.as_of.astimezone(ZoneInfo(bundle.target.reporting_timezone)),tuple(zip(bundle.path_ids,bundle.weights)),catalog,
                                 tuple(periods),allocation_version)
    except ContractError as exc:
        return CommercialResult(bundle.bundle_id,'unavailable',(),str(exc),input_id)
