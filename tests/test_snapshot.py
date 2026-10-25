from datetime import date, datetime, timezone
from decimal import Decimal
import pytest
from forecasting.snapshot import Assignment, Coverage, build_snapshot
from forecasting.ingestion import SourceLedger
from forecasting.contracts import ContractError
from test_ingestion import obs, ext, T
from test_contracts import target


def coverage(state='complete',maturity='finalized'):
    return Coverage('billing',date(2026,9,1),date(2026,9,3),state,maturity,T)

def build(ledger, at=T, **kw):
    return build_snapshot(target(),ledger,at,date(2026,9,1),date(2026,9,3),**kw)


def test_unknown_is_not_zero_and_permission_is_current():
    ledger=SourceLedger('org');ledger.activate(ext([obs()]))
    s=build(ledger)
    assert not s.ready and 'coverage_unknown:billing:2026-09-02' in s.limitations
    assert len(s.daily) == 1
    s=build(ledger,coverage=(coverage(),))
    assert s.ready
    assert s.recorded(date(2026,9,1),date(2026,9,3)) == Decimal(100)
    assert s.company_daily[-1].value == 0
    with pytest.raises(PermissionError): build(ledger,allowed_sources=set())
    assert not build(ledger,coverage=(coverage('suppressed'),)).ready


def test_bitemporal_transfer_conservation_and_processed_time():
    ledger=SourceLedger('org'); ledger.activate(ext([obs()]))
    later=datetime(2026,10,10,tzinfo=timezone.utc)
    a=Assignment('person:1','team:a',date(2026,1,1),date(2027,1,1),T,Decimal('1'),version='1')
    b=Assignment('person:1','team:b',date(2026,1,1),date(2027,1,1),later,Decimal('1'),version='2')
    old=build(ledger,assignments=(a,b),coverage=(coverage(),))
    new=build(ledger,later,assignments=(a,b),coverage=(coverage(),))
    assert old.daily[0].entity_id == 'team:a' and new.daily[0].entity_id == 'team:b'
    assert old.recorded(date(2026,9,1),date(2026,9,3)) == new.recorded(date(2026,9,1),date(2026,9,3)) == 100
    assert old.snapshot_id != new.snapshot_id
    hidden=obs('20','hidden'); object.__setattr__(hidden,'processed_at',later)
    ledger.activate(ext([hidden],'g2'),'replacement')
    assert not build(ledger,coverage=(coverage(),)).ready


def test_partial_weights_retained_unattributed_and_overlap_rejected():
    ledger=SourceLedger('org');ledger.activate(ext([obs('0.000003')]))
    a=Assignment('person:1','team:a',date(2026,1,1),date(2027,1,1),T,Decimal('.25'))
    s=build(ledger,assignments=(a,),coverage=(coverage(),))
    assert {x.entity_id:x.value for x in s.daily if x.date==date(2026,9,1)} == {'team:a':Decimal('.00000075'),'unattributed':Decimal('.00000225')}
    b=Assignment('person:1','team:b',date(2026,1,1),date(2027,1,1),T,Decimal('1'))
    with pytest.raises(ContractError): build(ledger,assignments=(a,b))


def test_snapshot_roundtrip_version_and_manifest_permissions():
    from forecasting.snapshot import Snapshot
    ledger=SourceLedger('org');ledger.activate(ext([obs()]))
    s=build(ledger,coverage=(coverage(),))
    assert Snapshot.from_dict(s.to_dict())==s
    with pytest.raises(ContractError):Snapshot.from_dict({**s.to_dict(),'schema_version':'2.0'})
    with pytest.raises(ContractError):Snapshot.from_dict({**s.to_dict(),'unknown':True})
    with pytest.raises(ContractError):Snapshot.from_dict({**s.to_dict(),'snapshot_id':'forged'})


def test_source_maturity_currency_and_late_service_date():
    from dataclasses import replace
    ledger=SourceLedger('org');ledger.activate(ext([obs('100'),replace(obs('-20','credit'),category='adjustment')]))
    s=build(ledger,coverage=(coverage(),))
    assert s.recorded(date(2026,9,1),date(2026,9,2))==80
    assert s.recorded(date(2026,10,1),date(2026,10,2))==0
    assert not build(ledger,coverage=(coverage(maturity='provisional'),)).ready
    with pytest.raises(ContractError):build_snapshot(replace(target(),currency='EUR',unit='EUR'),ledger,T,date(2026,9,1),date(2026,9,3))
    with pytest.raises(ContractError):build_snapshot(replace(target(),period_basis='cash'),ledger,T,date(2026,9,1),date(2026,9,3))
    with pytest.raises(ContractError):build_snapshot(replace(target(),categories=('usage',)),ledger,T,date(2026,9,1),date(2026,9,3))


def test_unmapped_person_is_unattributed_and_explicit_team_preserved():
    from dataclasses import replace
    ledger=SourceLedger('org'); ledger.activate(ext([obs(),replace(obs('50','b'),entity_id='team:product')]))
    s=build(ledger,coverage=(coverage(),))
    assert s.recorded_by_entity(date(2026,9,1),date(2026,9,3))=={'unattributed':Decimal(100),'team:product':Decimal(50)}


def test_alternative_financial_view_and_multisource_overlap_rejected():
    from dataclasses import replace
    from forecasting.ingestion import Extraction
    ledger=SourceLedger('org');ledger.activate(ext([replace(obs(),measure='list_price_equivalent')]))
    with pytest.raises(ContractError,match='measure'):build(ledger)
    a=replace(obs(),economic_id='economic-1')
    ledger=SourceLedger('org');ledger.activate(ext([a]))
    b=replace(a,source_id='other')
    extraction=ext([a],'g2');other=Extraction((b,),replace(extraction.receipt,source_id='other'))
    ledger.activate(other)
    t=replace(target(),sources=('billing','other'))
    with pytest.raises(ContractError,match='partition'):build_snapshot(t,ledger,T,date(2026,9,1),date(2026,9,3))
    t=replace(t,source_partition_policy='finance-approved-disjoint-v1')
    with pytest.raises(ContractError,match='overlap'):build_snapshot(t,ledger,T,date(2026,9,1),date(2026,9,3))


def test_future_service_dates_cannot_enter_origin_history():
    ledger=SourceLedger('org');ledger.activate(ext([obs()]))
    with pytest.raises(ContractError,match='future'):build_snapshot(target(),ledger,T,date(2026,9,1),date(2026,10,2))


def test_coverage_cannot_create_zero_before_source_receipt_arrives():
    from dataclasses import replace
    ledger=SourceLedger('org')
    empty=build(ledger,coverage=(coverage(),))
    assert not empty.ready and not empty.company_daily
    later=datetime(2026,10,2,tzinfo=timezone.utc)
    e=ext([obs()]);ledger.activate(replace(e,receipt=replace(e.receipt,fetched_at=later)))
    old=build(ledger,coverage=(coverage(),))
    assert not old.ready and not old.company_daily
    assert build(ledger,later,coverage=(coverage(),)).ready


def test_snapshot_direct_mutation_and_duplicate_company_rejected():
    from dataclasses import replace
    ledger=SourceLedger('org');ledger.activate(ext([obs()]))
    s=build(ledger,coverage=(coverage(),))
    with pytest.raises(ContractError):replace(s,daily=list(s.daily))
    with pytest.raises(ContractError):replace(s,company_daily=s.company_daily+s.company_daily)
    with pytest.raises(ContractError):replace(s,snapshot_id='forged')


def test_old_generation_bound_coverage_cannot_certify_replacement_zeros():
    from dataclasses import replace
    ledger=SourceLedger('org');original=ext([obs()]);ledger.activate(original)
    c=replace(coverage(),generation_id=original.receipt.generation_id)
    assert build(ledger,coverage=(c,)).ready
    later=datetime(2026,10,2,tzinfo=timezone.utc)
    ledger.activate(ext([],name='new-empty',at=later))
    current=build(ledger,later,coverage=(c,))
    assert not current.ready and not current.company_daily
    assert build(ledger,coverage=(c,)).ready
