from datetime import datetime, date, timezone
from decimal import Decimal
from dataclasses import replace
import json
import pytest
from forecasting.contracts import ContractError, Target
from forecasting.ingestion import SourceLedger
from forecasting.snapshot import build_snapshot
from forecasting.provider_adapters import AnthropicCostReportAdapter

T=datetime(2026,10,3,tzinfo=timezone.utc)
QUERY={'starting_at':'2026-10-01T00:00:00Z','ending_at':'2026-10-03T00:00:00Z','bucket_width':'1d','group_by':['workspace_id','description']}

def page(day=1,amount='123.78912',workspace=None,more=False,next_page=None):
    return {'data':[{'starting_at':f'2026-10-{day:02}T00:00:00Z','ending_at':f'2026-10-{day+1:02}T00:00:00Z','results':[{'amount':amount,'currency':'USD','workspace_id':workspace,'description':'Usage - Input Tokens','cost_type':'tokens','model':'model-v1','service_tier':'standard','token_type':'uncached_input_tokens','context_window':'0-200k','inference_geo':'global','speed':'standard'}]}], 'has_more':more,'next_page':next_page}

def write(tmp_path,name,payload):
    p=tmp_path/name;p.write_text(json.dumps(payload));return p

def read(paths,**kw):
    return AnthropicCostReportAdapter().read(paths,source_id='anthropic:org:oct',tenant_id='org',query=QUERY,fetched_at=T,**kw)

def test_native_cents_precision_null_workspace_exclusions_and_archive(tmp_path):
    p=write(tmp_path,'one.json',page())
    result=read([p],archive_dir=tmp_path/'raw')
    assert result.extraction.records[0].value==Decimal('1.2378912')
    assert result.extraction.records[0].entity_id=='anthropic:workspace:default'
    assert result.extraction.records[0].known_at==T
    assert result.extraction.receipt.archive_refs
    assert 'priority_tier_costs' in result.exclusions
    assert result.coverage[0].maturity=='provisional'
    assert len(result.coverage)==2 and result.coverage[1].state=='unknown'  # explicit omission invalidates any old completeness
    ledger=SourceLedger('org');ledger.activate(result.extraction)
    target=Target('anthropic','org','provider_reported_cost','USD','USD',('anthropic:org:oct',),('variable',))
    snapshot=build_snapshot(target,ledger,T,date(2026,10,1),date(2026,10,3),coverage=result.coverage)
    assert not snapshot.ready
    assert snapshot.daily[0].entity_id=='unattributed'
    assert snapshot.recorded(date(2026,10,1),date(2026,10,3))==Decimal('1.2378912')


def test_native_paginated_generation_atomic_and_retry(tmp_path):
    a=write(tmp_path,'one.json',page(more=True,next_page='cursor2'))
    b=write(tmp_path,'two.json',page(day=2,amount='-20',workspace='wrkspc_a'))
    partial=read([a]);ledger=SourceLedger('org')
    assert not partial.extraction.receipt.complete
    with pytest.raises(ContractError):ledger.activate(partial.extraction)
    complete=read([a,b],request_pages=(None,'cursor2'),maturity='finalized',maturity_policy='synthetic-fixture-mature')
    ledger.activate(complete.extraction);ledger.activate(complete.extraction)
    assert len(ledger.receipts)==1
    assert len(ledger.records_as_of(T))==2
    assert complete.extraction.receipt.control_total==Decimal('1.0378912')
    assert len(complete.coverage)==2
    assert complete.extraction.receipt.expected_parts==2
    with pytest.raises(ContractError):read([a,b],request_pages=(None,'wrong'))


def test_native_revised_report_replaces_and_historical_availability_retained(tmp_path):
    p=write(tmp_path,'old.json',page(amount='10000'))
    old=read([p]);ledger=SourceLedger('org');ledger.activate(old.extraction)
    p=write(tmp_path,'new.json',page(amount='8000'))
    later=datetime(2026,10,4,tzinfo=timezone.utc)
    new=AnthropicCostReportAdapter().read([p],source_id='anthropic:org:oct',tenant_id='org',query=QUERY,fetched_at=later)
    ledger.activate(new.extraction)
    assert sum(r.value for r in ledger.records_as_of(T))==100
    assert sum(r.value for r in ledger.records_as_of(later))==80
    assert ledger.records_as_of(later)[0].service_date==date(2026,10,1)


@pytest.mark.parametrize('change',[
    lambda p:p['data'][0]['results'][0].update(amount=123.45),
    lambda p:p['data'][0]['results'][0].update(currency='EUR'),
    lambda p:p['data'][0]['results'][0].update(service_tier='priority'),
    lambda p:p['data'][0].update(starting_at='2026-10-01T01:00:00Z'),
    lambda p:p['data'][0].update(starting_at='2026-10-01T00:00:00'),
    lambda p:p.update(has_more=True,next_page=None),
    lambda p:p.update(unexpected='schema-drift'),
])
def test_native_ambiguous_or_unknown_schema_rejected(tmp_path,change):
    data=page();change(data)
    with pytest.raises(ContractError):read([write(tmp_path,'bad.json',data)])


def test_native_unauthorized_duplicate_bucket_and_unjustified_finality_rejected(tmp_path):
    p=write(tmp_path,'one.json',page())
    with pytest.raises(PermissionError):read([p],authorized=False)
    with pytest.raises(ContractError):read([p,p],request_pages=(None,None))
    with pytest.raises(ContractError):read([p],maturity='finalized')
    with pytest.raises(ContractError):AnthropicCostReportAdapter().read([p],source_id='s',tenant_id='org',query={**QUERY,'bucket_width':'1h'},fetched_at=T)


def test_native_retry_later_fetch_and_changed_query_partition(tmp_path):
    p=write(tmp_path,'one.json',page())
    old=read([p]);ledger=SourceLedger('org');ledger.activate(old.extraction)
    later=AnthropicCostReportAdapter().read([p],source_id='anthropic:org:oct',tenant_id='org',query=QUERY,fetched_at=datetime(2026,10,4,tzinfo=timezone.utc))
    ledger.activate(later.extraction)
    assert len(ledger.receipts)==1
    assert ledger.records_as_of(T)[0].known_at==T
    different=AnthropicCostReportAdapter().read([p],source_id='anthropic:org:oct',tenant_id='org',query={**QUERY,'ending_at':'2026-10-04T00:00:00Z'},fetched_at=T)
    with pytest.raises(ContractError,match='partition'):ledger.activate(different.extraction)


def test_file_does_not_invent_response_api_version(tmp_path):
    p=write(tmp_path,'one.json',page())
    assert read([p]).provider_api_version=='unknown'
    assert read([p],provider_api_version='2023-06-01').provider_api_version=='2023-06-01'


@pytest.mark.parametrize('override',[{'tax_treatment':'included'},{'gross_net':'gross'},{'reporting_timezone':'America/Los_Angeles'}])
@pytest.mark.parametrize('empty',[False,True])
def test_native_basis_cannot_be_relabelled_even_for_empty_bucket(tmp_path,override,empty):
    data=page()
    if empty:data['data'][0]['results']=[]
    p=write(tmp_path,'one.json',data)
    imported=read([p],maturity='finalized',maturity_policy='synthetic-controlled-test')
    ledger=SourceLedger('org');ledger.activate(imported.extraction)
    target=Target('cost','org','provider_reported_cost','USD','USD',('anthropic:org:oct',),('variable',),**override)
    with pytest.raises(ContractError,match='basis|timezone'):
        build_snapshot(target,ledger,datetime(2026,10,3,7,tzinfo=timezone.utc),date(2026,10,1),date(2026,10,2),coverage=imported.coverage)


def test_replacement_omission_supersedes_old_complete_coverage(tmp_path):
    data=page();data['data']+=page(day=2)['data']
    old=read([write(tmp_path,'old.json',data)],maturity='finalized',maturity_policy='synthetic')
    later=datetime(2026,10,4,tzinfo=timezone.utc)
    p=write(tmp_path,'new.json',page(amount='100'))
    new=AnthropicCostReportAdapter().read([p],source_id='anthropic:org:oct',tenant_id='org',query=QUERY,fetched_at=later,maturity='finalized',maturity_policy='synthetic')
    ledger=SourceLedger('org');ledger.activate(old.extraction);ledger.activate(new.extraction)
    target=Target('cost','org','provider_reported_cost','USD','USD',('anthropic:org:oct',),('variable',))
    snapshot=build_snapshot(target,ledger,later,date(2026,10,1),date(2026,10,3),coverage=old.coverage+new.coverage)
    assert not snapshot.ready
    assert not any(x.date==date(2026,10,2) for x in snapshot.company_daily)
    assert 'coverage_unknown:anthropic:org:oct:2026-10-02' in snapshot.limitations


def test_ungrouped_native_total_is_not_the_default_workspace(tmp_path):
    from forecasting.snapshot import Assignment
    p=write(tmp_path,'one.json',page())
    imported=AnthropicCostReportAdapter().read([p],source_id='anthropic:org:oct',tenant_id='org',query={**QUERY,'group_by':['description']},fetched_at=T,maturity='finalized',maturity_policy='synthetic')
    assert imported.extraction.records[0].entity_id!='anthropic:workspace:default'
    ledger=SourceLedger('org');ledger.activate(imported.extraction)
    target=Target('cost','org','provider_reported_cost','USD','USD',('anthropic:org:oct',),('variable',))
    a=Assignment('anthropic:workspace:default','team:default-only',date(2026,1,1),date(2027,1,1),T,Decimal(1))
    snapshot=build_snapshot(target,ledger,T,date(2026,10,1),date(2026,10,2),coverage=imported.coverage,assignments=(a,))
    assert snapshot.recorded_by_entity(date(2026,10,1),date(2026,10,2))=={'unattributed':Decimal('1.2378912')}
