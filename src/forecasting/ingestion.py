"""Authorized local normalized exports and atomic, replayable source generations.

Provider acquisition is deliberately outside this adapter. Files assert normalized
source semantics; receipt completion alone never certifies date coverage or finality.
"""
from __future__ import annotations
from dataclasses import dataclass, replace
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
import csv
import hashlib
import json
import os
import tempfile
from threading import RLock
from typing import Optional, Tuple
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from .contracts import ContractError, Serializable, aware, day, decimal, digest, strict, timestamp, exact_sum

EVIDENCE_CLASSES = frozenset({'unspecified', 'synthetic_fixture', 'authorized_local_file',
                              'public_trace', 'backend_verified_snapshot', 'mixed'})


def evidence_class_from_receipts(receipts):
    """Conservative provenance closure; heterogeneous dependencies stay mixed."""
    classes = {r.evidence_class for r in receipts}
    return next(iter(classes)) if len(classes) == 1 else ('mixed' if classes else 'unspecified')


def _validate_basis(record):
    if record.gross_net not in {'gross','net'} or record.tax_treatment not in {'included','excluded','unknown'}:raise ContractError('unsupported source financial basis')
    try:ZoneInfo(record.reporting_timezone)
    except (ZoneInfoNotFoundError,TypeError) as exc:raise ContractError('invalid source reporting timezone') from exc


def _basis(record):
    return (record.gross_net,record.tax_treatment,record.reporting_timezone)


def _economic_content(record):
    # Availability and each raw receipt remain in history; neither is the source
    # economic identity used for overlapping-delivery idempotence.
    return {k:v for k,v in record.to_dict().items() if k not in {'raw_ref','known_at','ingested_at','processed_at'}}

@dataclass(frozen=True)
class Observation(Serializable):
    record_id: str
    source_id: str
    entity_id: str
    service_date: date
    value: Optional[Decimal]
    unit: str
    currency: Optional[str]
    category: str
    known_at: datetime
    ingested_at: datetime
    processed_at: datetime
    revision: int = 1
    status: str = 'observed'
    raw_ref: str = ''
    counter_epoch: Optional[str] = None
    schema_version: str = '1.0'
    measure: str = 'provider_reported_cost'
    economic_id: Optional[str] = None
    gross_net: str = 'net'
    tax_treatment: str = 'excluded'
    reporting_timezone: str = 'UTC'

    def __post_init__(self):
        _validate_basis(self)
        if self.measure not in {'metered_usage','list_price_equivalent','contract_priced_estimate','provider_reported_cost','invoice_amount','fixed_obligation','internal_allocation'}: raise ContractError('unknown observation measure')
        if self.schema_version != '1.0': raise ContractError('unsupported observation version')
        if not all((self.record_id,self.source_id,self.entity_id,self.unit,self.category)): raise ContractError('native record/source/entity/unit/category required')
        if type(self.service_date) is not date: raise ContractError('daily service date required')
        for t in (self.known_at,self.ingested_at,self.processed_at): aware(t)
        if self.processed_at < self.ingested_at: raise ContractError('processing predates ingestion')
        if type(self.revision) is not int or self.revision<1: raise ContractError('positive integer revision required')
        if self.status not in {'observed','partial','pending','missing','suppressed','unknown','not_applicable'}: raise ContractError('unknown observation status')
        if self.status=='observed' and self.value is None: raise ContractError('observed requires a value, including explicit zero')
        if self.value is not None:
            if not isinstance(self.value,Decimal): raise ContractError('Decimal value required')
            decimal(self.value)
            if self.status not in {'observed','partial'}: raise ContractError('unobserved value must be null')
        if self.currency is not None and (len(self.currency)!=3 or not self.currency.isupper()): raise ContractError('invalid currency')

    @property
    def available_at(self): return max(self.known_at,self.ingested_at,self.processed_at)

    @classmethod
    def from_dict(cls,value):
        d=strict(cls,value)
        try:
            d['service_date']=day(d['service_date'])
            for k in ('known_at','ingested_at','processed_at'): d[k]=timestamp(d[k])
            d['value']=None if d['value'] in (None,'') else decimal(d['value'])
            if 'revision' in d:
                if isinstance(d['revision'],str) and d['revision'].isdigit():d['revision']=int(d['revision'])
                elif type(d['revision']) is not int:raise ContractError('revision must be an integer')
            if d.get('currency')=='':d['currency']=None
            if d.get('counter_epoch')=='':d['counter_epoch']=None
            return cls(**d)
        except (KeyError,TypeError,ValueError) as exc: raise ContractError(str(exc)) from exc

@dataclass(frozen=True)
class ExtractionReceipt(Serializable):
    generation_id: str
    source_id: str
    tenant_id: str
    fetched_at: datetime
    parser_version: str
    raw_hashes: Tuple[str,...]
    row_count: int
    control_total: Decimal
    complete: bool
    expected_parts: int = 1
    received_parts: int = 1
    query: str = ''
    schema_version: str = '1.0'
    archive_refs: Tuple[str,...] = ()
    partition_id: Optional[str] = None
    gross_net: str = 'net'
    tax_treatment: str = 'excluded'
    reporting_timezone: str = 'UTC'
    evidence_class: str = 'unspecified'

    def __post_init__(self):
        _validate_basis(self)
        if self.evidence_class not in EVIDENCE_CLASSES:raise ContractError('unknown acquisition evidence class')
        aware(self.fetched_at); decimal(self.control_total)
        if type(self.complete) is not bool or any(type(x) is not int for x in (self.row_count,self.expected_parts,self.received_parts)):raise ContractError('typed receipt completion and integer counts required')
        if not isinstance(self.raw_hashes,tuple) or not isinstance(self.archive_refs,tuple):raise ContractError('immutable receipt lineage required')
        if not isinstance(self.control_total,Decimal):raise ContractError('Decimal control total required')
        if self.schema_version!='1.0' or self.parser_version!='1.0': raise ContractError('unsupported receipt/parser version')
        if not self.generation_id or not self.source_id or not self.tenant_id or not self.raw_hashes: raise ContractError('receipt lineage required')
        if self.row_count<0 or self.expected_parts<1 or not 0<=self.received_parts<=self.expected_parts: raise ContractError('invalid part manifest')
        if self.complete and self.expected_parts!=self.received_parts: raise ContractError('complete receipt missing parts')

@dataclass(frozen=True)
class Extraction(Serializable):
    records: Tuple[Observation,...]
    receipt: ExtractionReceipt

    def __post_init__(self):
        if not isinstance(self.records,tuple):raise ContractError('immutable extraction records required')
        if any(_basis(r)!=_basis(self.receipt) for r in self.records):raise ContractError('observation financial basis/timezone differs from extraction receipt')
        if len(self.records)!=self.receipt.row_count: raise ContractError('receipt row count mismatch')
        if any(r.source_id!=self.receipt.source_id for r in self.records): raise ContractError('source mismatch')
        if len({(r.record_id,r.counter_epoch) for r in self.records})!=len(self.records): raise ContractError('duplicate native record IDs within generation')
        if exact_sum(r.value or Decimal(0) for r in self.records) != self.receipt.control_total: raise ContractError('control total mismatch')
        if len({(r.unit,r.currency) for r in self.records if r.value is not None})>1: raise ContractError('mixed units/currency require separate extractions and control totals')


@dataclass(frozen=True)
class PendingObservation(Serializable):
    """Receipt-visible availability metadata, deliberately without a numerical value."""
    source_id: str
    record_id: str
    service_date: date
    available_at: datetime
    revision: int


@dataclass(frozen=True)
class SelectedEvidence:
    records: Tuple[Observation, ...]
    pending: Tuple[PendingObservation, ...]

class LocalFileAdapter:
    """Read only an explicitly authorized normalized JSON/CSV file, no network."""
    def read(self,path,*,source_id,tenant_id,authorized=True,fetched_at=None,archive_dir=None):
        if not authorized: raise PermissionError('source not authorized')
        p=Path(path)
        if p.suffix.lower() not in {'.json','.csv'}: raise ContractError('only normalized JSON/CSV supported; native provider/telemetry schemas require their own verified adapter')
        raw=p.read_bytes(); raw_hash=hashlib.sha256(raw).hexdigest()
        try:
            if p.suffix.lower()=='.json':
                payload=json.loads(raw)
                if not isinstance(payload,dict) or set(payload)!={'schema_version','records'} or payload['schema_version']!='1.0': raise ContractError('normalized export envelope schema 1.0 required')
                rows=payload['records']
            else:
                rows=list(csv.DictReader(raw.decode('utf8').splitlines()))
            records=tuple(replace(Observation.from_dict(r),raw_ref=f'sha256:{raw_hash}#row={i+1}') for i,r in enumerate(rows))
        except (json.JSONDecodeError,UnicodeDecodeError,TypeError) as exc: raise ContractError('invalid normalized export') from exc
        archive_refs=()
        if archive_dir is not None:
            directory=Path(archive_dir); directory.mkdir(parents=True,exist_ok=True)
            archived=directory/(raw_hash+'.raw')
            if archived.exists():
                if hashlib.sha256(archived.read_bytes()).hexdigest()!=raw_hash:raise ContractError('archive content hash mismatch')
            else:
                fd,tmp=tempfile.mkstemp(prefix='.staged-',dir=directory)
                try:
                    with os.fdopen(fd,'wb') as f:
                        f.write(raw);f.flush();os.fsync(f.fileno())
                    os.replace(tmp,archived)
                finally:
                    if os.path.exists(tmp):os.unlink(tmp)
            archive_refs=(str(archived.resolve()),)
        fetched_at=fetched_at or datetime.now(timezone.utc)
        receipt=ExtractionReceipt(raw_hash,source_id,tenant_id,fetched_at,'1.0',(raw_hash,),len(records),exact_sum(r.value or Decimal(0) for r in records),True,query=str(p.resolve()),archive_refs=archive_refs,**({k:getattr(records[0],k) for k in ('gross_net','tax_treatment','reporting_timezone')} if records else {}))
        return Extraction(records,receipt)

class SourceLedger:
    """In-memory transactional reference ledger; retain complete immutable deliveries.

Replacement generations replace the entire named source partition. Use a distinct
source_id for each independently replaced account/product/period partition.
"""
    def __init__(self,tenant_id):
        self.tenant_id=tenant_id
        self._deliveries=()
        self._lock=RLock()

    @property
    def receipts(self): return tuple(e.receipt for _,e in self._deliveries)

    def activate(self,extraction,semantics='replacement',*,fault=None):
        if semantics not in {'replacement','delta','revision','counter'}: raise ContractError('unsupported update semantics')
        r=extraction.receipt
        if r.tenant_id!=self.tenant_id: raise PermissionError('cross-tenant extraction')
        if not r.complete or r.expected_parts!=r.received_parts: raise ContractError('incomplete generation cannot activate')
        with self._lock:
            matching=[]
            eligible=[]
            for index,(mode,existing) in enumerate(self._deliveries):
                er=existing.receipt
                if er.source_id!=r.source_id:continue
                if mode!=semantics: raise ContractError('source update semantics cannot change')
                if er.partition_id!=r.partition_id:raise ContractError('source replacement partition changed; use a distinct source_id')
                if er.fetched_at<=r.fetched_at:eligible.append((er.fetched_at,index,er))
                if er.generation_id==r.generation_id:
                    # Fetch timestamps may change on a harmless retry; economic payload must not.
                    if tuple(map(_economic_content,existing.records))!=tuple(map(_economic_content,extraction.records)) or er.raw_hashes!=r.raw_hashes: raise ContractError('generation identity reused with changed contents')
                    if er.evidence_class!=r.evidence_class:raise ContractError('generation acquisition provenance cannot change')
                    matching.append(er)
            if matching:
                if semantics!='replacement':return matching[0]
                # Raw generation identity is distinct from an activation event:
                # A->B->A is a real later revision, whereas a retry of the active
                # A retains its first availability. Compare at the delivery's
                # own fetched time so delayed retries cannot undo newer data.
                active=max(eligible,key=lambda item:(item[0],item[1]))[2] if eligible else None
                if active is not None and active.generation_id==r.generation_id:return active
            if semantics in {'delta','revision','counter'}:

                prior=[x for mode,e in self._deliveries if e.receipt.source_id==r.source_id for x in e.records]
                for row in extraction.records:
                    same=[x for x in prior if (x.record_id,x.counter_epoch)==(row.record_id,row.counter_epoch)]
                    if semantics=='counter' and (not row.counter_epoch or row.value is None or row.value<0): raise ContractError('counter requires known epoch and nonnegative complete value; spanning/reset ambiguity unsupported')
                    for old in same:
                        if semantics=='delta' and _economic_content(old)!=_economic_content(row): raise ContractError('delta native ID reused with changed contents')
                        if old.revision==row.revision and _economic_content(old)!=_economic_content(row): raise ContractError('revision identity conflict')
                    if semantics=='counter':
                        for old in same:
                            if old.service_date!=row.service_date:raise ContractError('spanning counter epoch dates require a separate verified interval adapter')
                            if (row.revision>old.revision and row.value<old.value) or (row.revision<old.revision and row.value>old.value): raise ContractError('counter reset or downward correction requires explicit new epoch/revision adapter')
            if fault: fault('before_activation')
            self._deliveries=self._deliveries+((semantics,extraction),)
            if fault: fault('after_activation')
            return r

    def select_evidence(self,as_of):
        """Keep numerical availability separate from known pending corrections.

        A revision/counter may retain its last usable value while a newer known
        correction is pending, but cannot certify that date as finalized. A
        replacement never revives values from a superseded generation.
        """
        aware(as_of)
        deliveries=tuple(self._deliveries)
        eligible=[(m,e) for m,e in deliveries if e.receipt.fetched_at<=as_of]
        sources={e.receipt.source_id for _,e in eligible}
        result=[];pending=[]
        for source in sorted(sources):
            ds=[(m,e) for m,e in eligible if e.receipt.source_id==source]
            mode=ds[0][0]
            if mode=='replacement':
                _,e=max(enumerate(ds),key=lambda pair:(pair[1][1].receipt.fetched_at,pair[0]))[1]
                selected=e.records
            else:
                rows={};latest={}
                for _,e in ds:
                    for row in e.records:
                        key=(row.record_id,row.counter_epoch)
                        if (key not in latest or row.revision>latest[key].revision or
                            (row.revision==latest[key].revision and row.available_at<latest[key].available_at)):
                            latest[key]=row
                        if row.available_at<=as_of and (key not in rows or row.revision>rows[key].revision):rows[key]=row
                result.extend(rows.values())
                selected=latest.values()
            for row in selected:
                if row.available_at>as_of:
                    pending.append(PendingObservation(row.source_id,row.record_id,row.service_date,row.available_at,row.revision))
                    if mode!='replacement':
                        previous=rows.get((row.record_id,row.counter_epoch))
                        if previous is not None and previous.service_date!=row.service_date:
                            pending.append(PendingObservation(row.source_id,row.record_id,previous.service_date,row.available_at,row.revision))
                elif mode=='replacement':result.append(row)
        order=lambda r:(r.source_id,r.service_date,r.record_id)
        return SelectedEvidence(tuple(sorted(result,key=order)),tuple(sorted(pending,key=order)))

    def selected_records(self,as_of):
        return self.select_evidence(as_of).records

    def active_generation_ids(self,as_of):
        aware(as_of)
        result={}
        for index,(mode,extraction) in enumerate(self._deliveries):
            r=extraction.receipt
            if r.fetched_at>as_of:continue
            result.setdefault(r.source_id,[]).append((mode,r.fetched_at,index,r.generation_id))
        return {source:(max(rows,key=lambda x:(x[1],x[2]))[3],) if rows[0][0]=='replacement' else tuple(row[3] for row in rows) for source,rows in result.items()}

    def records_as_of(self,as_of):
        return tuple(r for r in self.selected_records(as_of) if r.available_at<=as_of)

    def to_dict(self):
        from .contracts import primitive
        content={'schema_version':'1.0','tenant_id':self.tenant_id,'deliveries':[{'semantics':mode,'extraction':primitive(extraction)} for mode,extraction in self._deliveries]}
        return {**content,'ledger_id':digest(content)}

    @classmethod
    def from_dict(cls,payload):
        if not isinstance(payload,dict) or set(payload)!={'schema_version','tenant_id','deliveries','ledger_id'} or payload['schema_version']!='1.0':raise ContractError('unsupported ledger envelope')
        content={k:v for k,v in payload.items() if k!='ledger_id'}
        if digest(content)!=payload['ledger_id']:raise ContractError('ledger digest mismatch')
        ledger=cls(payload['tenant_id'])
        try:
            for delivery in payload['deliveries']:
                if set(delivery)!={'semantics','extraction'} or set(delivery['extraction'])!={'records','receipt'}:raise ContractError('unknown delivery fields')
                data=delivery['extraction'];r=strict(ExtractionReceipt,data['receipt'])
                r['fetched_at']=timestamp(r['fetched_at']);r['control_total']=decimal(r['control_total'])
                r['raw_hashes']=tuple(r['raw_hashes']);r['archive_refs']=tuple(r.get('archive_refs',()))
                receipt=ExtractionReceipt(**r)
                extraction=Extraction(tuple(Observation.from_dict(x) for x in data['records']),receipt)
                ledger.activate(extraction,delivery['semantics'])
            return ledger
        except (KeyError,TypeError) as exc:raise ContractError(str(exc)) from exc

    def manifest_as_of(self,as_of):
        return tuple(r.to_dict() for r in self.receipts if r.fetched_at<=as_of)
