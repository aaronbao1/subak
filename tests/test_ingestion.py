from datetime import date, datetime, timezone
from decimal import Decimal
import json
import pytest
from forecasting.ingestion import Observation, Extraction, ExtractionReceipt, SourceLedger, LocalFileAdapter
from forecasting.contracts import ContractError

T = datetime(2026,10,1,tzinfo=timezone.utc)

def obs(value='100', record_id='a', revision=1, at=T, **kw):
    return Observation(**{**dict(record_id=record_id,source_id='billing',entity_id='person:1',service_date=date(2026,9,1),value=Decimal(value),unit='USD',currency='USD',category='usage',known_at=at,ingested_at=at,processed_at=at,revision=revision),**kw})

def ext(rows, name='g1', at=T, complete=True, expected_parts=1, received_parts=1):
    receipt = ExtractionReceipt(generation_id=name,source_id='billing',tenant_id='org',fetched_at=at,parser_version='1.0',raw_hashes=(name,),row_count=len(rows),control_total=sum((r.value or Decimal(0) for r in rows),Decimal(0)),complete=complete,expected_parts=expected_parts,received_parts=received_parts,query='authorized-fixture')
    return Extraction(tuple(rows),receipt)

def test_atomic_replacement_retry_and_multiplicity():
    ledger=SourceLedger('org')
    old=ext([obs(),obs(record_id='b')])
    ledger.activate(old)
    assert sum(r.value for r in ledger.records_as_of(T)) == 200
    ledger.activate(old)
    with pytest.raises(ContractError): ledger.activate(ext([obs('80')], 'g2', complete=False))
    assert sum(r.value for r in ledger.records_as_of(T)) == 200
    later=datetime(2026,10,2,tzinfo=timezone.utc)
    ledger.activate(ext([obs('80',at=later)],'g3',at=later))
    assert sum(r.value for r in ledger.records_as_of(T)) == 200
    assert sum(r.value for r in ledger.records_as_of(later)) == 80


def test_delta_reversal_revision_and_conflicting_id():
    ledger=SourceLedger('org')
    ledger.activate(ext([obs()]),'delta')
    ledger.activate(ext([obs('-100','reverse'),obs('80','replace')],'g2'),'delta')
    assert sum(r.value for r in ledger.records_as_of(T)) == 80
    ledger.activate(ext([obs('-20','newadjust')],'g3'),'delta')
    assert sum(r.value for r in ledger.records_as_of(T)) == 60
    with pytest.raises(ContractError): ledger.activate(ext([obs('999')],'g4'),'delta')
    revisions=SourceLedger('org')
    revisions.activate(ext([obs()]),'revision')
    revisions.activate(ext([obs('80',revision=2)],'g2'),'revision')
    assert sum(r.value for r in revisions.records_as_of(T)) == 80


def test_adapter_precision_raw_provenance_missing_and_strict_schema(tmp_path):
    row=obs('0.0000001').to_dict()
    p=tmp_path/'records.json'; p.write_text(json.dumps({'schema_version':'1.0','records':[row]}))
    extraction=LocalFileAdapter().read(p,source_id='billing',tenant_id='org',fetched_at=T)
    assert extraction.records[0].value == Decimal('0.0000001')
    assert extraction.receipt.raw_hashes
    assert extraction.records[0].raw_ref
    with pytest.raises(PermissionError): LocalFileAdapter().read(p,source_id='billing',tenant_id='org',authorized=False)
    row['value']=None; row['status']='suppressed'
    p.write_text(json.dumps({'schema_version':'1.0','records':[row]}))
    assert LocalFileAdapter().read(p,source_id='billing',tenant_id='org',fetched_at=T).records[0].value is None
    row['surprise']='bad';p.write_text(json.dumps({'schema_version':'1.0','records':[row]}))
    with pytest.raises(ContractError): LocalFileAdapter().read(p,source_id='billing',tenant_id='org',fetched_at=T)


def test_counters_require_epochs_and_select_revision_not_delivery_order():
    ledger=SourceLedger('org')
    with pytest.raises(ContractError): ledger.activate(ext([obs()]),'counter')
    ledger.activate(ext([obs('900',counter_epoch='e1',revision=1)],'g1'),'counter')
    ledger.activate(ext([obs('20',record_id='b',counter_epoch='e2',revision=1)],'g2'),'counter')
    ledger.activate(ext([obs('950',counter_epoch='e1',revision=2)],'g3'),'counter')
    assert sum(r.value for r in ledger.records_as_of(T)) == 970
    with pytest.raises(ContractError): ledger.activate(ext([obs('940',counter_epoch='e1',revision=3)],'g4'),'counter')


def test_fault_before_after_activation_preserves_single_generation():
    ledger=SourceLedger('org'); ledger.activate(ext([obs()]))
    replacement=ext([obs('80')],'g2')
    def before(stage):
        if stage=='before_activation': raise RuntimeError('process lost before publication')
    with pytest.raises(RuntimeError):ledger.activate(replacement,fault=before)
    assert sum(r.value for r in ledger.records_as_of(T))==100
    def after(stage):
        if stage=='after_activation':raise RuntimeError('response lost after publication')
    with pytest.raises(RuntimeError):ledger.activate(replacement,fault=after)
    assert sum(r.value for r in ledger.records_as_of(T))==80
    ledger.activate(replacement)
    assert len(ledger.receipts)==2


def test_native_provider_and_mixed_currency_rejected(tmp_path):
    for fields in ({'ActualCost':'100','AmortizedCost':'90'}, {'usage':{'output_tokens':30}}, {'invoice_total':None}, {'cost': '0.01', 'is_included': True}, {'error':{'code':400,'message':'unsupported grouping'}}, {'personal_copilot_usage':[],'unit':'premium_requests','scope':'personal'}, {'console_analytics':[],'auth_route':'enterprise_subscription'}):
        p=tmp_path/'native.json';p.write_text(json.dumps(fields))
        with pytest.raises(ContractError):LocalFileAdapter().read(p,source_id='billing',tenant_id='org')
    with pytest.raises(ContractError):ext([obs(),obs('90','euro',currency='EUR')])


def test_csv_and_duplicate_line_identity(tmp_path):
    import csv
    p=tmp_path/'rows.csv'
    rows=[obs('0.000001').to_dict(),obs('0.000001','b').to_dict()]
    with p.open('w') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    extracted=LocalFileAdapter().read(p,source_id='billing',tenant_id='org',fetched_at=T)
    assert extracted.receipt.control_total==Decimal('.000002')
    assert len(extracted.records)==2


@pytest.mark.parametrize('record',[
    {'parent_run':'run1','attempts':[{'tokens':100},{'tokens':80}]},
    {'input':1000,'cache_read':700,'cache_write':100,'output':200,'reasoning':120},
    {'attempt':'failed','status':'partial','usage':None,'fallback':'success'},
    {'start':'2026-11-01T01:30:00','end':'2026-11-01T01:45:00','counter':950},
    {'employee_email':'recycled@example.test','new_hire':True},
    {'leave_id':'leave1','status':'cancelled','permission':'revoked'},
    {'recurring_id':'meeting','occurrence':'2026-11-01','cancelled':True},
])
def test_native_context_telemetry_normalization_is_explicitly_unavailable(tmp_path,record):
    p=tmp_path/'record.json';p.write_text(json.dumps({'schema_version':'1.0','records':[record]}))
    with pytest.raises(ContractError):LocalFileAdapter().read(p,source_id='billing',tenant_id='org')


def test_durable_raw_archive_and_ledger_replay(tmp_path):
    p=tmp_path/'records.json';p.write_text(json.dumps({'schema_version':'1.0','records':[obs('0.000001').to_dict()]}))
    raw=p.read_bytes()
    extraction=LocalFileAdapter().read(p,source_id='billing',tenant_id='org',fetched_at=T,archive_dir=tmp_path/'archive')
    archive=__import__('pathlib').Path(extraction.receipt.archive_refs[0])
    assert archive.read_bytes()==raw
    p.write_text('source replaced')
    ledger=SourceLedger('org');ledger.activate(extraction)
    saved=ledger.to_dict()
    restored=SourceLedger.from_dict(saved)
    assert restored.records_as_of(T)==ledger.records_as_of(T)
    assert archive.read_bytes()==raw
    saved['deliveries'][0]['extraction']['records'][0]['value']='999'
    with pytest.raises(ContractError):SourceLedger.from_dict(saved)


def test_estimate_replaced_by_reported_charge_not_added():
    from dataclasses import replace
    ledger=SourceLedger('org')
    first=ext([replace(obs('8000'),measure='contract_priced_estimate')])
    ledger.activate(first)
    later=datetime(2026,10,2,tzinfo=timezone.utc)
    report=ext([obs('9000',at=later),replace(obs('-100','credit',at=later),category='adjustment')],'g2',at=later)
    ledger.activate(report);ledger.activate(report)
    assert sum(r.value for r in ledger.records_as_of(T))==8000
    assert sum(r.value for r in ledger.records_as_of(later))==8900
    assert {r.measure for r in ledger.records_as_of(later)}=={'provider_reported_cost'}


def test_mutable_or_untyped_receipts_cannot_activate():
    from dataclasses import replace
    e=ext([obs()])
    with pytest.raises(ContractError):replace(e,records=list(e.records))
    with pytest.raises(ContractError):replace(e.receipt,complete='false')
    with pytest.raises(ContractError):replace(e.receipt,raw_hashes=list(e.receipt.raw_hashes))
    with pytest.raises(ContractError):replace(e.receipt,row_count=True)
    with pytest.raises(ContractError):Observation.from_dict({**obs().to_dict(),'revision':1.5})


@pytest.mark.parametrize('semantics',['delta','revision'])
def test_overlapping_delivery_raw_provenance_does_not_conflict_with_economic_identity(tmp_path,semantics):
    p=tmp_path/'first.json';q=tmp_path/'second.json'
    a=obs().to_dict();b=obs('20','b').to_dict()
    p.write_text(json.dumps({'schema_version':'1.0','records':[a]}))
    q.write_text(json.dumps({'schema_version':'1.0','records':[a,b]}))
    adapter=LocalFileAdapter();ledger=SourceLedger('org')
    first=adapter.read(p,source_id='billing',tenant_id='org',fetched_at=T)
    second=adapter.read(q,source_id='billing',tenant_id='org',fetched_at=T)
    assert first.records[0].raw_ref!=second.records[0].raw_ref
    ledger.activate(first,semantics);ledger.activate(second,semantics)
    assert sum(r.value for r in ledger.records_as_of(T))==120
    assert len(ledger.receipts)==2
    a['value']='999';q.write_text(json.dumps({'schema_version':'1.0','records':[a,b]}))
    with pytest.raises(ContractError):ledger.activate(adapter.read(q,source_id='billing',tenant_id='org',fetched_at=T),semantics)


def test_counter_cannot_move_epoch_total_to_another_service_date():
    from dataclasses import replace
    ledger=SourceLedger('org');ledger.activate(ext([obs(counter_epoch='epoch')]),'counter')
    moved=replace(obs('150',revision=2,counter_epoch='epoch'),service_date=date(2026,9,2))
    with pytest.raises(ContractError,match='spanning'):ledger.activate(ext([moved],'g2'),'counter')


def test_replacement_content_can_reactivate_after_intervening_revision_and_replay():
    from dataclasses import replace
    ledger=SourceLedger('org')
    first=ext([obs('100')],name='content-100')
    second_time=datetime(2026,10,2,tzinfo=timezone.utc)
    third_time=datetime(2026,10,3,tzinfo=timezone.utc)
    second=ext([obs('80',at=second_time)],name='content-80',at=second_time)
    third=ext([obs('100',at=third_time)],name='content-100',at=third_time)
    ledger.activate(first);ledger.activate(second)
    ledger.activate(first)  # delayed original delivery must not undo newer data
    assert sum(r.value for r in ledger.records_as_of(third_time))==80
    ledger.activate(third)
    assert sum(r.value for r in ledger.records_as_of(third_time))==100
    assert sum(r.value for r in ledger.records_as_of(second_time))==80
    assert sum(r.value for r in ledger.records_as_of(T))==100
    ledger.activate(replace(third,receipt=replace(third.receipt,fetched_at=datetime(2026,10,4,tzinfo=timezone.utc))))
    assert len(ledger.receipts)==3  # same-current retry adds no activation
    restored=SourceLedger.from_dict(ledger.to_dict())
    assert restored.to_dict()==ledger.to_dict()
    assert sum(r.value for r in restored.records_as_of(third_time))==100
    assert restored.records_as_of(third_time)[0].known_at==third_time
