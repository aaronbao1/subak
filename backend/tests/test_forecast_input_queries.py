"""Input queries select usable revisions before decoding append-only history."""
from unittest.mock import patch

import pytest

from app.forecasting.persistence import ForecastStore
from app.forecasting.service import ForecastService


CUTOFF = '2026-10-25T12:00:00Z'


@pytest.fixture
def store(tmp_path):
    return ForecastStore(tmp_path / 'forecast.sqlite')


def append(store, kind, source, revision, *, available='2026-10-20T00:00:00Z',
           received=None, tenant='northstar'):
    return store.append_input(kind, source, revision, {'revision': revision},
                              available_at=available, received_at=received, tenant_id=tenant)


def test_latest_query_decodes_only_latest_eligible_payloads(store):
    for revision in range(20):
        append(store, 'repository_state', 'repository', str(revision))
    append(store, 'pricing', 'rates', 'current')
    with patch.object(store, '_input', wraps=store._input) as decode:
        rows = store.input_records(CUTOFF, latest=True)
    assert [(r['kind'], r['revision']) for r in rows] == [
        ('repository_state', '19'), ('pricing', 'current')]
    assert decode.call_count == 2


def test_latest_retains_cutoff_ties_tenant_and_first_group_order(store):
    # Later insertion may have an earlier effective time; group ordering follows
    # the earliest eligible row, not insertion order or latest row timestamp.
    append(store, 'pricing', 'second', 'base', available='2026-10-21T00:00:00Z')
    append(store, 'observations', 'first', 'base')
    append(store, 'pricing', 'second', 'latest', available='2026-10-24T00:00:00Z')
    append(store, 'pricing', 'second', 'late-old', received='2026-10-25T00:00:00Z')
    append(store, 'observations', 'first', 'tied-one', available='2026-10-23T00:00:00Z')
    append(store, 'observations', 'first', 'tied-two', available='2026-10-23T00:00:00Z')
    append(store, 'observations', 'first', 'not-received', available='2026-10-24T00:00:00Z',
           received='2026-10-26T00:00:00Z')
    append(store, 'pricing', 'second', 'not-available', available='2026-10-26T00:00:00Z',
           received='2026-10-22T00:00:00Z')
    append(store, 'pricing', 'second', 'other-tenant', tenant='other')
    rows = store.input_records(CUTOFF, latest=True)
    assert [(r['source_id'], r['revision']) for r in rows] == [
        ('first', 'tied-two'), ('second', 'latest')]
    assert set(rows[0]) == {'id', 'tenant_id', 'kind', 'source_id', 'revision',
                            'available_at', 'received_at', 'payload'}


def test_kind_and_source_filters_preserve_history_without_decoding_other_payloads(store):
    append(store, 'repository_state', 'repository', 'archive')
    append(store, 'truth_revisions', 'a', '1')
    append(store, 'truth_revisions', 'a', '2')
    append(store, 'truth_revisions', 'b', '1')
    append(store, 'issued_targets', 'a', '1')
    with patch.object(store, '_input', wraps=store._input) as decode:
        rows = store.input_records(CUTOFF, kinds=('truth_revisions', 'issued_targets'), source_id='a')
    assert [(r['kind'], r['revision']) for r in rows] == [
        ('truth_revisions', '1'), ('truth_revisions', '2'), ('issued_targets', '1')]
    assert decode.call_count == 3
    assert [(r['kind'], r['revision']) for r in store.input_records(
        CUTOFF, latest=True, kinds=('truth_revisions',), source_id='a')] == [('truth_revisions', '2')]
    assert store.input_records(CUTOFF, kinds=()) == []


def test_snapshot_only_decodes_current_inputs_and_complete_calibration_history(store):
    for revision in range(15):
        append(store, 'repository_state', 'repository', str(revision))
    for kind in ('issued_targets', 'truth_revisions', 'forecast_errors'):
        for revision in ('1', '2'):
            append(store, kind, 'calibration', revision)
    service = ForecastService(store, now=lambda: CUTOFF)
    with patch.object(store, '_input', wraps=store._input) as decode:
        snapshot = service.current_snapshot()
    for kind in ('issued_targets', 'truth_revisions', 'forecast_errors'):
        assert [r['revision'] for r in snapshot[kind]] == ['1', '2']
    assert decode.call_count == 10  # Four latest sources plus six calibration rows.
