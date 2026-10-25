"""Bitemporal daily snapshot with explicit coverage and attribution conservation."""
from __future__ import annotations
from dataclasses import dataclass, fields
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Tuple, Optional
from zoneinfo import ZoneInfo
from .contracts import Target, ContractError, Serializable, aware, interval, decimal, digest, strict, timestamp, day, exact_sum, exact_product

@dataclass(frozen=True)
class Coverage(Serializable):
    source_id: str
    start: date
    end: date
    state: str
    maturity: str
    known_at: datetime
    version: str = '1'
    generation_id: Optional[str] = None

    def __post_init__(self):
        interval(self.start,self.end); aware(self.known_at)
        if self.state not in {'complete','partial','pending','missing','suppressed','unknown','not_applicable'}:raise ContractError('unknown coverage state')
        if self.maturity not in {'provisional','finalized','unknown'}: raise ContractError('unknown maturity state')
        if not self.source_id: raise ContractError('coverage source required')

@dataclass(frozen=True)
class Assignment(Serializable):
    source_entity: str
    target_entity: str
    effective_start: date
    effective_end: date
    known_at: datetime
    weight: Decimal
    version: str = '1'
    evidence_ref: str = ''
    policy: str = 'approved_partition'

    def __post_init__(self):
        interval(self.effective_start,self.effective_end); aware(self.known_at)
        decimal(self.weight)
        if not isinstance(self.weight,Decimal) or not 0<=self.weight<=1: raise ContractError('assignment weight must be Decimal in [0,1]')
        if not self.source_entity or not self.target_entity:raise ContractError('namespaced native identity required')
        if self.policy!='approved_partition': raise ContractError('membership/role labels are not allocation weights')


@dataclass(frozen=True)
class AllocationPolicy(Serializable):
    """Declared global policy version, distinct from individual row revisions."""
    version: str
    assignments: Tuple[Assignment, ...]
    policy: str = 'approved_partition'

    def __post_init__(self):
        if not isinstance(self.version,str) or not self.version:raise ContractError('allocation policy version required')
        if self.policy!='approved_partition':raise ContractError('unsupported allocation policy')
        if not isinstance(self.assignments,tuple) or any(not isinstance(a,Assignment) for a in self.assignments):
            raise ContractError('immutable allocation policy assignments required')


def _snapshot_identity(content, *, legacy_receipts=False):
    content=dict(content)
    # Omitted optional provenance retains the old scalar snapshot identity.
    if content.get('evidence_class','unspecified')=='unspecified':content.pop('evidence_class',None)
    if legacy_receipts:
        content['source_manifest']=tuple({k:v for k,v in r.to_dict().items() if k!='evidence_class'} for r in content['source_manifest'])
    return digest(content)

@dataclass(frozen=True)
class DailyValue(Serializable):
    entity_id: str
    date: date
    value: Decimal

@dataclass(frozen=True)
class Snapshot(Serializable):
    snapshot_id: str
    target: Target
    as_of: datetime
    history_start: date
    history_end: date
    daily: Tuple[DailyValue,...]
    company_daily: Tuple[DailyValue,...]
    ready: bool
    limitations: Tuple[str,...]
    source_manifest: Tuple[object,...]
    attribution_digest: str
    coverage_digest: str
    schema_version: str = '1.0'
    evidence_class: str = 'unspecified'

    def __post_init__(self):
        from .ingestion import evidence_class_from_receipts
        if self.schema_version!='1.0': raise ContractError('unsupported snapshot version')
        if any(not isinstance(x,tuple) for x in (self.daily,self.company_daily,self.limitations,self.source_manifest)):raise ContractError('immutable snapshot tuples required')
        if type(self.ready) is not bool:raise ContractError('typed snapshot readiness required')
        if len({x.date for x in self.company_daily})!=len(self.company_daily):raise ContractError('duplicate company date')
        aware(self.as_of);interval(self.history_start,self.history_end)
        if self.ready and self.limitations: raise ContractError('ready snapshot has limitations')
        for x in self.daily+self.company_daily:
            if not self.history_start<=x.date<self.history_end: raise ContractError('daily value outside history')
            if not isinstance(x.value,Decimal):raise ContractError('Decimal snapshot value required')
        if len({(x.entity_id,x.date) for x in self.daily})!=len(self.daily): raise ContractError('duplicate entity/date')
        totals={}
        for x in self.daily: totals[x.date]=exact_sum((totals.get(x.date,Decimal(0)),x.value))
        for x in self.company_daily:
            if totals.get(x.date,Decimal(0))!=x.value: raise ContractError('company/entity conservation failed')
        if set(totals)-{x.date for x in self.company_daily}:raise ContractError('entity day missing company total')
        if self.evidence_class!=evidence_class_from_receipts(self.source_manifest):raise ContractError('snapshot evidence provenance differs from acquisition receipts')
        content={f.name:getattr(self,f.name) for f in fields(self) if f.name not in {'snapshot_id','schema_version'}}
        expected=_snapshot_identity(content)
        legacy=self.evidence_class=='unspecified' and all(r.evidence_class=='unspecified' for r in self.source_manifest)
        valid_ids={expected,digest(content)}
        if legacy:valid_ids.add(_snapshot_identity(content,legacy_receipts=True))
        if self.snapshot_id not in valid_ids:raise ContractError('snapshot digest mismatch')

    @classmethod
    def from_dict(cls,value):
        from .ingestion import ExtractionReceipt
        d=strict(cls,value)
        try:
            d['target']=Target.from_dict(d['target']); d['as_of']=timestamp(d['as_of'])
            for k in ('history_start','history_end'):d[k]=day(d[k])
            for k in ('daily','company_daily'):
                d[k]=tuple(DailyValue(x['entity_id'],day(x['date']),decimal(x['value'])) for x in d[k])
            manifest=[]
            for raw in d['source_manifest']:
                r=strict(ExtractionReceipt,raw)
                r['fetched_at']=timestamp(r['fetched_at']);r['control_total']=decimal(r['control_total']);r['raw_hashes']=tuple(r['raw_hashes']);r['archive_refs']=tuple(r.get('archive_refs',()))
                manifest.append(ExtractionReceipt(**r))
            d['source_manifest']=tuple(manifest);d['limitations']=tuple(d['limitations'])
            return cls(**d)
        except (KeyError,TypeError) as exc:raise ContractError(str(exc)) from exc

    def recorded(self,start,end):
        interval(start,end)
        return exact_sum(x.value for x in self.company_daily if start<=x.date<end)

    def recorded_by_entity(self,start,end):
        interval(start,end)
        result={}
        for x in self.daily:
            if start<=x.date<end:result[x.entity_id]=exact_sum((result.get(x.entity_id,Decimal(0)),x.value))
        return result


def build_snapshot(target,ledger,as_of,history_start,history_end,*,coverage=(),assignments=(),allowed_sources=None,allocation_policy=None):
    aware(as_of); interval(history_start,history_end)
    if history_end>as_of.astimezone(ZoneInfo(target.reporting_timezone)).date():raise ContractError('future service dates cannot enter origin history')
    if len(target.sources)>1 and not target.source_partition_policy:raise ContractError('multiple sources require an explicit disjoint partition policy')
    if ledger.tenant_id!=target.tenant_id: raise PermissionError('cross-tenant snapshot')
    if allowed_sources is not None and not set(target.sources)<=set(allowed_sources): raise PermissionError('current source access denied; historical availability cannot override revocation')
    if target.period_basis!='incurred':raise ContractError('daily source adapter supports incurred service-date targets only; invoice/cash bridge unsupported')
    if not target.additive: raise ContractError('nonadditive target requires full-state pricing scenario')
    if allocation_policy is None:
        if target.attribution_version!='1':raise ContractError('declared allocation policy version requires matching evidence')
        allocation_policy=AllocationPolicy('1',tuple(assignments))
        legacy_policy=True
    else:
        if not isinstance(allocation_policy,AllocationPolicy):raise ContractError('typed allocation policy evidence required')
        if assignments:raise ContractError('allocation policy and legacy assignments cannot both be supplied')
        if allocation_policy.version!=target.attribution_version:raise ContractError('allocation policy version differs from target')
        legacy_policy=False
    assignments=allocation_policy.assignments
    basis_fields=('gross_net','tax_treatment','reporting_timezone')
    latest_receipts={}
    for index,receipt in enumerate(ledger.receipts):
        if receipt.source_id in target.sources and receipt.fetched_at<=as_of:
            key=(receipt.fetched_at,index)
            if receipt.source_id not in latest_receipts or key>latest_receipts[receipt.source_id][0]:latest_receipts[receipt.source_id]=(key,receipt)
    for _,receipt in latest_receipts.values():
        if any(getattr(receipt,k)!=getattr(target,k) for k in basis_fields):raise ContractError('source financial basis/reporting timezone requires an explicit supported reconciliation bridge')
    active_generations=ledger.active_generation_ids(as_of)
    evidence=ledger.select_evidence(as_of)
    rows=tuple(r for r in evidence.records if r.source_id in target.sources and history_start<=r.service_date<history_end)
    limits=set();values={};companies={};dates=[]
    d=history_start
    while d<history_end:dates.append(d);d+=timedelta(days=1)
    complete_days=set(dates)
    eligible_sources={r.source_id for r in ledger.receipts if r.fetched_at<=as_of}
    for d in dates:
        for source in target.sources:
            if source not in eligible_sources:
                limits.add(f'source_receipt_unavailable:{source}');complete_days.discard(d);continue
            cs=[c for c in coverage if c.source_id==source and c.start<=d<c.end and c.known_at<=as_of and (c.generation_id is None or c.generation_id in active_generations.get(source,()))]
            if not cs:
                limits.add(f'coverage_unknown:{source}:{d}');complete_days.discard(d);continue
            latest_time=max(c.known_at for c in cs)
            latest=[c for c in cs if c.known_at==latest_time]
            if len({(c.state,c.maturity) for c in latest})>1:raise ContractError('conflicting coverage evidence')
            c=latest[0]
            if c.state not in {'complete','not_applicable'}:
                limits.add(f'coverage_{c.state}:{source}:{d}');complete_days.discard(d)
            if c.maturity!='finalized':limits.add(f'maturity_{c.maturity}:{source}:{d}')
    for pending in evidence.pending:
        if pending.source_id in target.sources and history_start<=pending.service_date<history_end:
            limits.add(f'processing_pending:{pending.source_id}:{pending.record_id}')
            complete_days.discard(pending.service_date)
    economics={};selected_mappings={}
    for r in rows:
        if any(getattr(r,k)!=getattr(target,k) for k in basis_fields):raise ContractError('observation financial basis/reporting timezone differs from target')
        if r.economic_id:
            key=(r.economic_id,r.service_date)
            if key in economics and economics[key]!=r.source_id:raise ContractError('overlapping economic observation across sources')
            economics[key]=r.source_id
        if r.measure!=target.measure:raise ContractError('observation measure differs from target financial basis')
        if r.category not in target.categories: raise ContractError('source includes category outside target; partition input explicitly')
        if r.unit!=target.unit or r.currency!=target.currency:raise ContractError('unit/currency mismatch; no implicit conversion or alternative billing-view sum')
        if r.available_at>as_of:
            limits.add(f'processing_pending:{r.source_id}:{r.record_id}');complete_days.discard(r.service_date);continue
        if r.status!='observed':
            limits.add(f'observation_{r.status}:{r.source_id}:{r.record_id}');complete_days.discard(r.service_date)
        if r.value is None:continue
        if target.support=='nonnegative' and r.value<0:raise ContractError('negative physical demand unsupported')
        candidates=[a for a in assignments if a.source_entity==r.entity_id and a.effective_start<=r.service_date<a.effective_end and a.known_at<=as_of]
        if candidates:
            known=max(a.known_at for a in candidates)
            chosen=[a for a in candidates if a.known_at==known]
            if legacy_policy and len({a.version for a in chosen})!=1:raise ContractError('conflicting attribution versions at same known time')
            if len({a.target_entity for a in chosen})!=len(chosen):raise ContractError('overlapping allocation rows')
            weight=exact_sum(a.weight for a in chosen)
            if weight>1:raise ContractError('allocation weights exceed one')
            allocations=[(a.target_entity,a.weight) for a in chosen]
            if weight<1:allocations.append(('unattributed',exact_sum((Decimal(1),weight.copy_negate()))))
        else:
            entity=r.entity_id if r.entity_id.startswith('team:') or r.entity_id in {'shared','central','unattributed'} else 'unattributed'
            allocations=[(entity,Decimal(1))]
            chosen=[]
        selected_mappings[(r.entity_id,r.service_date)]=(tuple(sorted(chosen,key=lambda a:a.target_entity)),tuple(allocations))
        allocated=Decimal(0)
        for i,(entity,weight) in enumerate(allocations):
            # Preserve exact parent even where Decimal division/weights have finite precision.
            value=exact_sum((r.value,allocated.copy_negate())) if i==len(allocations)-1 else exact_product(r.value,weight)
            allocated=exact_sum((allocated,value))
            values[(entity,r.service_date)]=exact_sum((values.get((entity,r.service_date),Decimal(0)),value))
        companies[r.service_date]=exact_sum((companies.get(r.service_date,Decimal(0)),r.value))
    entities={entity for entity,_ in values}
    for d in complete_days:
        companies.setdefault(d,Decimal(0))
        for entity in entities: values.setdefault((entity,d),Decimal(0))
    daily=tuple(DailyValue(e,d,v) for (e,d),v in sorted(values.items()))
    company_daily=tuple(DailyValue('company',d,v) for d,v in sorted(companies.items()))
    manifest=tuple(r for r in ledger.receipts if r.fetched_at<=as_of and r.source_id in target.sources)
    ad=digest({'policy':allocation_policy.policy,'version':allocation_policy.version,
               'selected_mapping':tuple((entity,service_date,*mapping) for (entity,service_date),mapping in sorted(selected_mappings.items()))})
    cd=digest(tuple(c for c in coverage if c.known_at<=as_of))
    from .ingestion import evidence_class_from_receipts
    fields=dict(target=target,as_of=as_of,history_start=history_start,history_end=history_end,daily=daily,company_daily=company_daily,ready=not limits,limitations=tuple(sorted(limits)),source_manifest=manifest,attribution_digest=ad,coverage_digest=cd,evidence_class=evidence_class_from_receipts(manifest))
    return Snapshot(snapshot_id=_snapshot_identity(fields),**fields)
