from dataclasses import replace
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal
import pytest

from forecasting.source_store import SourceStore
from forecasting.snapshot import Coverage
from test_ingestion import obs,ext,T


def test_durable_receipt_replay_and_synthetic_isolation(tmp_path):
    store=SourceStore(tmp_path/'sources.sqlite')
    extraction=ext([obs()])
    c=Coverage('billing',date(2026,9,1),date(2026,9,2),'complete','finalized',T)
    store.acquire(extraction,(c,),evidence_class='authorized_local_file',adapter='normalized')
    later=replace(extraction,receipt=replace(extraction.receipt,fetched_at=T+timedelta(days=1)))
    store.acquire(later,(c,),evidence_class='authorized_local_file',adapter='normalized')
    ledger,coverage=SourceStore(tmp_path/'sources.sqlite').load('org','billing',evidence_class='authorized_local_file',adapter='normalized')
    assert len(ledger.receipts)==1 and ledger.receipts[0].fetched_at==T
    assert ledger.records_as_of(T)[0].value==100
    assert coverage[0].generation_id==extraction.receipt.generation_id
    with pytest.raises(PermissionError):store.load('org','billing',evidence_class='synthetic_fixture',adapter='normalized')
    with pytest.raises(PermissionError):store.load('other','billing',evidence_class='authorized_local_file',adapter='normalized')


def test_finality_upgrade_uses_new_actual_receipt_not_original_bytes(tmp_path):
    store=SourceStore(tmp_path/'sources.sqlite')
    c=Coverage('billing',date(2026,9,1),date(2026,9,2),'complete','provisional',T)
    first=ext([obs()]);store.acquire(first,(c,),evidence_class='authorized_local_file',adapter='normalized')
    later=T+timedelta(days=1)
    second=replace(first,receipt=replace(first.receipt,fetched_at=later))
    store.acquire(second,(replace(c,maturity='finalized'),),evidence_class='authorized_local_file',adapter='normalized')
    ledger,coverage=store.load('org','billing',evidence_class='authorized_local_file',adapter='normalized')
    assert len(ledger.receipts)==1
    final=[x for x in coverage if x.maturity=='finalized'][0]
    assert final.known_at==later
    assert all(x.maturity=='provisional' for x in coverage if x.known_at<=T)


def test_changed_adapter_and_conflicting_generation_coverage_rejected(tmp_path):
    store=SourceStore(tmp_path/'sources.sqlite')
    c=Coverage('billing',date(2026,9,1),date(2026,9,2),'complete','finalized',T,generation_id='wrong')
    with pytest.raises(ValueError):store.acquire(ext([obs()]),(c,),evidence_class='authorized_local_file',adapter='normalized')
    store.acquire(ext([obs()]),(),evidence_class='authorized_local_file',adapter='normalized')
    with pytest.raises(ValueError):store.acquire(ext([obs()]),(),evidence_class='authorized_local_file',adapter='anthropic_cost_report')


def test_coverage_state_can_return_after_intervening_revision(tmp_path):
    store=SourceStore(tmp_path/'sources.sqlite')
    original=ext([obs()])
    c=Coverage('billing',date(2026,9,1),date(2026,9,2),'complete','finalized',T)
    for offset,state in [(0,'finalized'),(1,'provisional'),(2,'finalized')]:
        delivery=replace(original,receipt=replace(original.receipt,fetched_at=T+timedelta(days=offset)))
        store.acquire(delivery,(replace(c,maturity=state),),evidence_class='authorized_local_file',adapter='normalized')
    _,coverage=store.load('org','billing',evidence_class='authorized_local_file',adapter='normalized')
    assert [(x.maturity,x.known_at) for x in coverage]==[
        ('finalized',T),('provisional',T+timedelta(days=1)),('finalized',T+timedelta(days=2))]
