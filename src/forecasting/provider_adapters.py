"""Read-only adapters for authorized files containing native provider responses.

Anthropic Console Cost Report shape verified against primary documentation on
2026-10-24. This is file parsing, not authenticated acquisition or invoice close.
Docs: https://platform.claude.com/docs/en/manage-claude/usage-cost-api
Schema: https://platform.claude.com/docs/en/api/beta/organization/cost_report/retrieve
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
import hashlib
import json
import os
import tempfile
from typing import Tuple
from .contracts import ContractError, Serializable, aware, canonical_json, decimal, digest, exact_product, exact_sum, timestamp
from .ingestion import Observation, Extraction, ExtractionReceipt
from .snapshot import Coverage

DOCS='https://platform.claude.com/docs/en/manage-claude/usage-cost-api'
EXCLUSIONS=('priority_tier_costs','claude_enterprise_analytics','third_party_cloud_billing','invoice_tax_and_settlement')

@dataclass(frozen=True)
class ProviderImport(Serializable):
    extraction: Extraction
    coverage: Tuple[Coverage,...]
    exclusions: Tuple[str,...]
    query: str
    documentation_url: str = DOCS
    adapter_version: str = 'anthropic-console-cost-report/1.0'
    provider_api_version: str = 'unknown'
    maturity_policy: str = ''


def _utc_day(value):
    t=timestamp(value)
    if t.utcoffset()!=timedelta(0) or any((t.hour,t.minute,t.second,t.microsecond)):
        raise ContractError('native cost bucket must use UTC-midnight daily boundaries')
    return t


def _archive(raw,raw_hash,directory):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    path=directory/(raw_hash+'.raw')
    if path.exists():
        if hashlib.sha256(path.read_bytes()).hexdigest()!=raw_hash:raise ContractError('archive content hash mismatch')
    else:
        fd,tmp=tempfile.mkstemp(prefix='.provider-',dir=directory)
        try:
            with os.fdopen(fd,'wb') as f:
                f.write(raw);f.flush();os.fsync(f.fileno())
            os.replace(tmp,path)
        finally:
            if os.path.exists(tmp):os.unlink(tmp)
    return str(path.resolve())


class AnthropicCostReportAdapter:
    """Parse complete or staged ordered pages from GET /organizations/cost_report.

    A source_id denotes ONE entire replacement query partition. Do not reuse it
    for a different time range/grouping/filter. Every row is a provider-reported
    monetary cost; token quantities and list prices are never added to it.
    """
    def read(self,paths,*,source_id,tenant_id,query,request_pages=None,authorized=True,
             fetched_at=None,archive_dir=None,maturity='provisional',maturity_policy=None,provider_api_version=None):
        if not authorized:raise PermissionError('native source file access denied')
        paths=tuple(Path(p) for p in paths)
        if not paths:raise ContractError('at least one captured response page required')
        allowed_query={'starting_at','ending_at','bucket_width','group_by','limit'}
        if not isinstance(query,dict) or set(query)-allowed_query or not {'starting_at','ending_at'}<=set(query):raise ContractError('exact supported native query required')
        start=_utc_day(query['starting_at']);end=_utc_day(query['ending_at'])
        if start>=end or query.get('bucket_width','1d')!='1d':raise ContractError('nonempty daily native query required')
        groups=query.get('group_by',[])
        if not isinstance(groups,(list,tuple)) or set(groups)-{'workspace_id','description'} or len(set(groups))!=len(groups):raise ContractError('unsupported native grouping')
        if 'limit' in query and (type(query['limit']) is not int or not 1<=query['limit']<=31):raise ContractError('native page limit must be 1..31')
        if maturity not in {'provisional','finalized'} or (maturity=='finalized' and not maturity_policy):raise ContractError('finalized native labels require explicit maturity policy; endpoint does not certify close')
        fetched_at=aware(fetched_at or datetime.now(timezone.utc))
        if request_pages is None:
            if len(paths)>1:raise ContractError('pagination request cursor manifest required')
            request_pages=(None,)
        request_pages=tuple(request_pages)
        if len(request_pages)!=len(paths) or request_pages[0] is not None:raise ContractError('page manifest must start with the initial query')
        records=[];hashes=[];raw_objects=[];days=[];seen=set();cursor=None;complete=False
        result_fields={'amount','currency','workspace_id','description','cost_type','context_window','model','service_tier','token_type','inference_geo','speed'}
        for page_index,(path,requested_cursor) in enumerate(zip(paths,request_pages)):
            if requested_cursor!=cursor or (page_index and complete):raise ContractError('pagination cursor chain mismatch or trailing page')
            raw=path.read_bytes();raw_hash=hashlib.sha256(raw).hexdigest()
            if raw_hash in hashes:raise ContractError('duplicate native page')
            try:payload=json.loads(raw)
            except (json.JSONDecodeError,UnicodeDecodeError) as exc:raise ContractError('invalid native JSON page') from exc
            if not isinstance(payload,dict) or set(payload)!={'data','has_more','next_page'} or not isinstance(payload['data'],list) or type(payload['has_more']) is not bool:raise ContractError('unsupported native page schema')
            more=payload['has_more'];cursor=payload['next_page']
            if more and (not isinstance(cursor,str) or not cursor):raise ContractError('partial native page requires next_page cursor')
            if not more and cursor is not None:raise ContractError('final native page must end cursor chain')
            complete=not more
            hashes.append(raw_hash);raw_objects.append(raw)
            for bucket_index,bucket in enumerate(payload['data']):
                if not isinstance(bucket,dict) or set(bucket)!={'starting_at','ending_at','results'} or not isinstance(bucket['results'],list):raise ContractError('unsupported native bucket schema')
                bucket_start=_utc_day(bucket['starting_at']);bucket_end=_utc_day(bucket['ending_at'])
                if bucket_end-bucket_start!=timedelta(days=1) or not start<=bucket_start<bucket_end<=end:raise ContractError('native daily bucket outside query or spanning dates')
                if bucket_start in seen:raise ContractError('overlapping native buckets across pages')
                seen.add(bucket_start);days.append(bucket_start.date())
                for row_index,row in enumerate(bucket['results']):
                    if not isinstance(row,dict) or set(row)-result_fields or not {'amount','currency'}<=set(row):raise ContractError('unsupported native cost item schema')
                    if not isinstance(row['amount'],str):raise ContractError('native cost amount must be exact decimal cents string')
                    if row['currency']!='USD':raise ContractError('native adapter supports documented USD cents only')
                    if row.get('service_tier')=='priority':raise ContractError('Priority Tier is excluded from this native cost endpoint')
                    for key,value in row.items():
                        if key not in {'amount','currency'} and value is not None and not isinstance(value,str):raise ContractError('native dimensions must be strings or null')
                    workspace=row.get('workspace_id')
                    if 'workspace_id' not in groups:
                        if workspace is not None:raise ContractError('workspace dimension present without workspace grouping')
                        entity='anthropic:organization:aggregate'
                    else:entity='anthropic:workspace:'+workspace if workspace is not None else 'anthropic:workspace:default'
                    logical=digest({'query':query,'date':bucket_start.date(),'dimensions':{k:v for k,v in row.items() if k!='amount'},'occurrence':row_index})
                    records.append(Observation(record_id=logical,source_id=source_id,entity_id=entity,service_date=bucket_start.date(),
                                               value=exact_product(decimal(row['amount']),Decimal('.01')),unit='USD',currency='USD',category='variable',
                                               known_at=fetched_at,ingested_at=fetched_at,processed_at=fetched_at,
                                               raw_ref=f'sha256:{raw_hash}#data/{bucket_index}/results/{row_index}',measure='provider_reported_cost'))
        archive_refs=tuple(_archive(raw,h,archive_dir) for raw,h in zip(raw_objects,hashes)) if archive_dir is not None else ()
        manifest={'endpoint':'GET /v1/organizations/cost_report','query':query,'request_pages':request_pages,
                  'files':tuple(str(p.resolve()) for p in paths),'api_version':provider_api_version or 'unknown','adapter_version':'1.0',
                  'exclusions':EXCLUSIONS,'maturity_policy':maturity_policy,'maturity':maturity}
        # For an incomplete chain, expected_parts is only the minimum known next
        # page count; complete=False prevents any activation or coverage claim.
        receipt=ExtractionReceipt(generation_id=digest({'query':query,'raw_hashes':hashes}),source_id=source_id,tenant_id=tenant_id,
                                  fetched_at=fetched_at,parser_version='1.0',raw_hashes=tuple(hashes),row_count=len(records),
                                  control_total=exact_sum(r.value for r in records),complete=complete,
                                  expected_parts=len(paths)+(0 if complete else 1),received_parts=len(paths),
                                  query=canonical_json(manifest),archive_refs=archive_refs,partition_id=digest(query))
        requested_days=tuple((start+timedelta(days=i)).date() for i in range((end-start).days))
        coverage=tuple(Coverage(source_id,d,d+timedelta(days=1),('complete' if complete else 'partial') if d in days else 'unknown',maturity,fetched_at,generation_id=receipt.generation_id) for d in requested_days)
        return ProviderImport(Extraction(tuple(records),receipt),coverage,EXCLUSIONS,canonical_json(query),maturity_policy=maturity_policy or '',provider_api_version=provider_api_version or 'unknown')
