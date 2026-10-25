"""Regression checks for receipt availability, allocation identity and provenance."""
from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal

import pytest

from forecasting.contracts import ContractError, digest
from forecasting.ingestion import SourceLedger
from forecasting.snapshot import Assignment, Coverage, Snapshot, build_snapshot
from forecasting.source_store import SourceStore
from test_contracts import target
from test_ingestion import T, ext, obs

START = date(2026, 9, 1)
END = date(2026, 9, 3)
LATER = T + timedelta(days=1)


def snapshot(ledger, at=T, **options):
    options.setdefault('coverage', (Coverage('billing', START, END, 'complete', 'finalized', T),))
    return build_snapshot(target(), ledger, at, START, END, **options)


@pytest.mark.parametrize('mode', ['replacement', 'delta', 'revision', 'counter'])
def test_known_receipt_with_unprocessed_row_never_certifies_zero(mode):
    ledger = SourceLedger('org')
    row = replace(obs(counter_epoch='epoch' if mode == 'counter' else None), processed_at=LATER)
    ledger.activate(ext([row]), mode)
    pending = snapshot(ledger)
    assert not pending.ready
    assert 'processing_pending:billing:a' in pending.limitations
    assert all(x.date != START for x in pending.company_daily)
    assert not ledger.records_as_of(T)
    assert snapshot(ledger, LATER).recorded(START, END) == Decimal('100')
    restored = SourceLedger.from_dict(ledger.to_dict())
    assert snapshot(restored).snapshot_id == pending.snapshot_id


@pytest.mark.parametrize('mode', ['revision', 'counter'])
def test_pending_correction_keeps_known_amount_but_never_claims_finality(mode):
    ledger = SourceLedger('org')
    epoch = 'epoch' if mode == 'counter' else None
    ledger.activate(ext([obs(counter_epoch=epoch)]), mode)
    correction = replace(obs('150', revision=2, counter_epoch=epoch), processed_at=LATER)
    ledger.activate(ext([correction], 'correction'), mode)
    pending = snapshot(ledger)
    assert pending.recorded(START, END) == Decimal('100')
    assert not pending.ready
    assert 'processing_pending:billing:a' in pending.limitations
    assert snapshot(ledger, LATER).recorded(START, END) == Decimal('150')


def test_out_of_order_pending_older_revision_does_not_hide_usable_newer_revision():
    ledger = SourceLedger('org')
    ledger.activate(ext([obs('150', revision=2)], 'new'), 'revision')
    ledger.activate(ext([replace(obs(revision=1), processed_at=LATER)], 'old'), 'revision')
    current = snapshot(ledger)
    assert current.ready and current.recorded(START, END) == Decimal('150')


def test_pending_replacement_does_not_resurrect_previous_generation():
    ledger = SourceLedger('org')
    ledger.activate(ext([obs()]))
    next_time = T + timedelta(hours=1)
    replacement = replace(obs('80'), processed_at=LATER)
    ledger.activate(ext([replacement], 'new', at=next_time))
    assert snapshot(ledger).recorded(START, END) == Decimal('100')
    current = snapshot(ledger, next_time)
    assert not current.ready and all(x.date != START for x in current.company_daily)
    assert snapshot(ledger, LATER).recorded(START, END) == Decimal('80')
    assert snapshot(SourceLedger.from_dict(ledger.to_dict())).recorded(START, END) == Decimal('100')


def test_declared_nondefault_allocation_version_requires_matching_policy_evidence():
    ledger = SourceLedger('org'); ledger.activate(ext([obs()]))
    with pytest.raises(ContractError, match='allocation policy'):
        build_snapshot(replace(target(), attribution_version='finance-2'), ledger, T, START, END)


def test_acquired_synthetic_provenance_survives_snapshot_replay_and_cannot_promote(tmp_path):
    store = SourceStore(tmp_path / 'sources.sqlite')
    store.acquire(ext([obs()]), (), evidence_class='synthetic_fixture', adapter='normalized')
    ledger, _ = store.load('org', 'billing', evidence_class='synthetic_fixture', adapter='normalized')
    result = snapshot(ledger)
    assert getattr(result, 'evidence_class', None) == 'synthetic_fixture'
    assert Snapshot.from_dict(result.to_dict()) == result
    assert snapshot(SourceLedger.from_dict(ledger.to_dict())).evidence_class == 'synthetic_fixture'
    with pytest.raises(ContractError, match='provenance|evidence'):
        store.acquire(ledger._deliveries[0][1], (), evidence_class='authorized_local_file', adapter='normalized')


def test_unknown_receipt_provenance_stays_unspecified():
    ledger = SourceLedger('org'); ledger.activate(ext([obs()]))
    assert getattr(snapshot(ledger), 'evidence_class', None) == 'unspecified'


def test_global_policy_allows_individual_revisions_and_binds_effective_mapping():
    import forecasting.snapshot as module
    policy_type = getattr(module, 'AllocationPolicy', None)
    assert policy_type is not None, 'global allocation policy evidence is missing'
    ledger = SourceLedger('org')
    ledger.activate(ext([obs(), obs('60', 'b', service_date=date(2026, 9, 2))]))
    first = Assignment('person:1', 'team:a', START, date(2026, 9, 2), T, Decimal('.25'), version='row-8')
    second = Assignment('person:1', 'team:b', date(2026, 9, 2), END, T, Decimal('1'), version='row-15')
    policy = policy_type('finance-2', (first, second))
    custom = replace(target(), attribution_version='finance-2')
    result = build_snapshot(custom, ledger, T, START, END, allocation_policy=policy)
    assert result.recorded_by_entity(START, END) == {'team:a': Decimal('25'), 'team:b': Decimal('60'), 'unattributed': Decimal('75')}
    assert result.recorded(START, END) == Decimal('160')
    with pytest.raises(ContractError, match='allocation policy'):
        build_snapshot(target(), ledger, T, START, END, allocation_policy=policy)
    changed = replace(policy, assignments=(replace(first, weight=Decimal('.5')), second))
    restated = build_snapshot(custom, ledger, T, START, END, allocation_policy=changed)
    assert restated.attribution_digest != result.attribution_digest
    assert restated.recorded(START, END) == Decimal('160')


def test_unknown_provenance_legacy_snapshot_id_remains_readable():
    ledger = SourceLedger('org'); ledger.activate(ext([obs()]))
    payload = snapshot(ledger).to_dict()
    payload.pop('evidence_class', None)
    for receipt in payload['source_manifest']:
        receipt.pop('evidence_class', None)
    payload['snapshot_id'] = digest({k: v for k, v in payload.items() if k not in {'snapshot_id', 'schema_version'}})
    restored = Snapshot.from_dict(payload)
    assert getattr(restored, 'evidence_class', None) == 'unspecified'
    assert restored.recorded(START, END) == Decimal('100')


def test_mixed_synthetic_and_real_receipts_never_classify_as_real(tmp_path):
    from forecasting.ingestion import Extraction
    store = SourceStore(tmp_path / 'sources.sqlite')
    store.acquire(ext([obs()]), (), evidence_class='synthetic_fixture', adapter='normalized')
    ledger, _ = store.load('org', 'billing', evidence_class='synthetic_fixture', adapter='normalized')
    other = obs('50', source_id='other')
    receipt = replace(ext([obs('50')], 'other').receipt, source_id='other')
    store.acquire(Extraction((other,), receipt), (), evidence_class='public_trace', adapter='normalized')
    real, _ = store.load('org', 'other', evidence_class='public_trace', adapter='normalized')
    for mode, extraction in real._deliveries:
        ledger.activate(extraction, mode)
    multi = replace(target(), sources=('billing', 'other'), source_partition_policy='disjoint-accounts')
    result = build_snapshot(multi, ledger, T, START, END)
    assert getattr(result, 'evidence_class', None) == 'mixed'


def test_unspecified_snapshot_supports_full_asdict_content_addressing():
    from dataclasses import asdict
    ledger = SourceLedger('org'); ledger.activate(ext([obs()]))
    result = snapshot(ledger)
    fields = asdict(result)
    fields.pop('snapshot_id'); fields.pop('schema_version')
    fields.update(target=result.target, daily=result.daily, company_daily=result.company_daily,
                  source_manifest=result.source_manifest, as_of=LATER)
    reconstructed = Snapshot(digest(fields), **fields)
    assert reconstructed.as_of == LATER
    assert reconstructed.evidence_class == 'unspecified'


def test_unbound_redelivery_of_known_synthetic_bytes_cannot_change_namespace(tmp_path):
    store = SourceStore(tmp_path / 'sources.sqlite')
    original = ext([obs()])
    store.acquire(original, (), evidence_class='synthetic_fixture', adapter='normalized')
    # The original caller still holds the unclassified extraction. Merely
    # switching namespace or source alias must not launder already-known bytes.
    with pytest.raises(ContractError, match='synthetic|provenance'):
        store.acquire(original, (), evidence_class='authorized_local_file', adapter='normalized')
    from forecasting.ingestion import Extraction
    alias = Extraction((replace(original.records[0], source_id='alias'),),
                       replace(original.receipt, source_id='alias'))
    with pytest.raises(ContractError, match='synthetic|provenance'):
        store.acquire(alias, (), evidence_class='public_trace', adapter='normalized')


def test_pending_revision_date_move_invalidates_the_old_date_as_well():
    ledger = SourceLedger('org')
    ledger.activate(ext([obs()]), 'revision')
    moved = replace(obs('150', revision=2), service_date=date(2026, 9, 2), processed_at=LATER)
    ledger.activate(ext([moved], 'moved'), 'revision')
    old_day = build_snapshot(target(), ledger, T, START, date(2026, 9, 2),
                             coverage=(Coverage('billing', START, END, 'complete', 'finalized', T),))
    assert old_day.recorded(START, END) == Decimal('100')
    assert not old_day.ready, 'known pending removal must invalidate the previously recorded date'
    current = snapshot(ledger, LATER)
    assert current.ready
    assert {x.date:x.value for x in current.company_daily} == {START: Decimal('0'), date(2026, 9, 2): Decimal('150')}
