"""Enrichment must scale with archive size without changing calibration evidence."""
from collections import Counter
from copy import deepcopy
from datetime import date, timedelta

import pytest

from forecasting import learning


def _view(scope='acme', *, cutoff='2025-10-06T00:00:00Z', origin='2025-10-06'):
    start = date.fromisoformat(origin)
    points = lambda days: [dict(start=str(start + timedelta(days=offset)),
                               end=str(start + timedelta(days=offset + days)),
                               base=100. + offset, complete=True) for offset in (0, 7)]
    return dict(run_id=f'new:{scope}:{origin}', scope={'type': 'company', 'id': scope},
                target={'unit': 'USD', 'basis': 'planning'}, timezone='UTC',
                procedure_id='v1', publication={'generated_at': cutoff,
                'information_cutoff': cutoff, 'forecast_start': origin,
                'history_complete_through': origin}, daily=points(1),
                weekly=points(7), cumulative=points(14))


def _case(*, two_cutoffs=False):
    views = [_view()]
    if two_cutoffs:
        views.append(_view('later', cutoff='2025-10-13T00:00:00Z', origin='2025-10-13'))
    bundle = {'views': views}
    snapshot = {'id': 'test-snapshot', 'is_synthetic': False}
    templates = learning.archive_issued_targets(bundle, snapshot)
    issued, truths = [], []
    for j, template in enumerate(templates):
        for i in range(20):
            row = deepcopy(template)
            offset = timedelta(weeks=22-i)
            for key in ('start', 'end', 'origin'):
                row[key] = str(date.fromisoformat(row[key]) - offset)
            row.update(target_id=f'h:{j}:{i}', run_id=f'old:{j}:{i}',
                       issued_at=row['origin']+'T00:00:00Z', prediction=100.,
                       intervals={'80': {'lower': 90., 'upper': 110.},
                                  '95': {'lower': 80., 'upper': 120.}})
            issued.append(row)
            truths.append(dict(target_id=row['target_id'], revision=1, value=101.+i,
                               available_at=row['end']+'T00:00:00Z',
                               mature_at=row['end']+'T00:00:00Z', status='mature',
                               is_synthetic=False))
    snapshot.update(issued_targets=issued, truth_revisions=truths)
    return bundle, snapshot


def _assert_reference(bundle, snapshot):
    before = deepcopy((bundle, snapshot))
    expected_targets = learning.archive_issued_targets(bundle, snapshot)
    expected = {r['target_id']: {str(int(c*100)): learning.historical_error_interval(
        r, snapshot['issued_targets'], snapshot['truth_revisions'],
        cutoff=next(v['publication']['information_cutoff'] for v in bundle['views']
                    if v['run_id'] == r['run_id']), coverage=c) for c in (.8, .95)}
        for r in expected_targets}
    actual = learning.enrich_intervals(bundle, snapshot)
    archived = learning.archive_issued_targets(actual, snapshot)
    assert {r['target_id']: r['intervals'] for r in archived} == expected
    assert (bundle, snapshot) == before
    return actual


def test_enrichment_validates_archived_targets_once(monkeypatch):
    bundle, snapshot = _case(two_cutoffs=True)
    seen = Counter()
    validate = learning._validate_target

    def counted(row):
        if row['target_id'].startswith('h:'):
            seen[row['target_id']] += 1
        return validate(row)

    monkeypatch.setattr(learning, '_validate_target', counted)
    actual = learning.enrich_intervals(bundle, snapshot)
    assert len(actual['views']) == 2
    assert len(seen) == len(snapshot['issued_targets'])
    assert set(seen.values()) == {1}


def test_enrichment_matches_reference_for_overlap_duplicates_and_cutoff_corrections():
    bundle, snapshot = _case(two_cutoffs=True)
    issued, truths = snapshot['issued_targets'], snapshot['truth_revisions']
    # Identical retries deduplicate; a separate overlapping publication loses the
    # original ordering tie, even though the two timestamp strings denote UTC.
    issued.append(deepcopy(issued[0])); truths.append(deepcopy(truths[0]))
    overlap = dict(issued[0], target_id='overlap', issued_at=issued[0]['origin']+'T01:00:00+01:00')
    issued.append(overlap); truths.append(dict(truths[0], target_id='overlap', value=900.))
    truths.append(dict(truths[1], revision=2, value=150.,
                       available_at='2025-10-10T00:00:00Z', mature_at='2025-10-10T00:00:00Z'))
    # Newer unavailable/pending/immature/incompatible revisions do not revive a
    # previous revision; all revisions are validated before these exclusions.
    truths.extend([dict(truths[2], revision=2, status='pending'),
                   dict(truths[3], revision=2, status='disputed'),
                   dict(truths[4], revision=2, mature_at='2025-12-01T00:00:00Z'),
                   dict(truths[5], revision=2, is_synthetic=True)])
    issued.reverse(); truths.reverse()
    actual = _assert_reference(bundle, snapshot)
    interval = actual['views'][0]['daily'][0]['historical_error_interval']['80']
    assert interval['excluded_overlap'] == 1
    assert interval['n'] == 16
    assert 'h:0:2' not in interval['target_ids']
    assert interval['empirical']['wis_count'] == 16


def test_enrichment_keeps_target_start_and_utc_cutoff_boundaries():
    bundle, snapshot = _case()
    first = snapshot['issued_targets'][0]
    # At the cutoff boundary the truth is visible and the old interval ends at
    # the target start. A later target can additionally use a later interval.
    first.update(start='2025-10-05', end='2025-10-06', origin='2025-10-05',
                 issued_at='2025-10-06T01:00:00+01:00')
    snapshot['truth_revisions'][0].update(available_at='2025-10-06T01:00:00+01:00',
                                         mature_at='2025-10-06T01:00:00+01:00')
    bundle['views'][0]['publication']['information_cutoff'] = '2025-10-13T00:00:00Z'
    later = dict(first, target_id='after-first-start', start='2025-10-06', end='2025-10-07',
                 origin='2025-10-06')
    snapshot['issued_targets'].append(later)
    snapshot['truth_revisions'].append(dict(snapshot['truth_revisions'][0],
        target_id=later['target_id'], available_at='2025-10-07T00:00:00Z', mature_at='2025-10-07T00:00:00Z'))
    actual = _assert_reference(bundle, snapshot)
    interval = actual['views'][0]['daily'][0]['historical_error_interval']['80']
    assert first['target_id'] in interval['target_ids']
    assert later['target_id'] not in interval['target_ids']


@pytest.mark.parametrize('defect, message', [
    ('issued_prediction', 'finite numerical'),
    ('issued_conflict', 'issued target identity changed'),
    ('truth_conflict', 'conflicting truth revision'),
    ('truth_status', 'invalid truth revision/status'),
    ('truth_before_available', 'maturity precedes availability'),
    ('truth_before_end', 'matures before target end'),
])
def test_unrelated_invalid_history_still_raises(defect, message):
    bundle, snapshot = _case()
    row = dict(snapshot['issued_targets'][0], target_id='unrelated', scope_id='other')
    truth = dict(snapshot['truth_revisions'][0], target_id='unrelated')
    snapshot['issued_targets'].append(row)
    snapshot['truth_revisions'].append(truth)
    if defect == 'issued_prediction': row['prediction'] = float('inf')
    elif defect == 'issued_conflict': snapshot['issued_targets'].append(dict(row, prediction=999.))
    elif defect == 'truth_conflict': snapshot['truth_revisions'].append(dict(truth, value=999.))
    elif defect == 'truth_status': truth.update(target_id='orphan', status='invalid')
    elif defect == 'truth_before_available': truth['available_at'] = '2030-01-01T00:00:00Z'
    elif defect == 'truth_before_end': truth.update(available_at='2020-01-01T00:00:00Z', mature_at='2020-01-01T00:00:00Z')
    with pytest.raises(ValueError, match=message):
        learning.enrich_intervals(bundle, snapshot)
    target = learning.archive_issued_targets(bundle, snapshot)[0]
    with pytest.raises(ValueError, match=message):
        learning.historical_error_interval(target, snapshot['issued_targets'],
                                          snapshot['truth_revisions'], cutoff='2025-10-06T00:00:00Z')


def test_unhashable_unrelated_stratum_and_absent_implementation_remain_ignorable():
    bundle, snapshot = _case()
    row = dict(snapshot['issued_targets'][0], target_id='unrelated', scope_id=['other'])
    row.pop('implementation_sha256')
    snapshot['issued_targets'].append(row)
    snapshot['truth_revisions'].append(dict(snapshot['truth_revisions'][0], target_id='unrelated'))
    _assert_reference(bundle, snapshot)


def test_unavailable_points_do_not_newly_validate_history():
    bundle, snapshot = _case()
    for view in bundle['views']:
        for aggregation in ('daily', 'weekly', 'cumulative'):
            for point in view[aggregation]: point['base'] = None
    snapshot['issued_targets'] = [{'malformed': True}]
    snapshot['truth_revisions'] = [{'malformed': True}]
    actual = learning.enrich_intervals(bundle, snapshot)
    assert actual['views'][0]['historical_error_interval'] is None


def test_same_stratum_views_resolve_corrections_at_their_own_cutoff():
    bundle, snapshot = _case()
    bundle['views'].append(_view(cutoff='2025-10-13T00:00:00Z', origin='2025-10-13'))
    correction = dict(snapshot['truth_revisions'][0], revision=2, value=150.,
                      available_at='2025-10-10T00:00:00Z', mature_at='2025-10-10T00:00:00Z')
    snapshot['truth_revisions'].append(correction)
    actual = _assert_reference(bundle, snapshot)
    earlier, later = [v['daily'][0]['historical_error_interval']['80'] for v in actual['views']]
    assert (earlier['n'], earlier['lower'], earlier['upper']) == (20, 83., 117.)
    assert (later['n'], later['lower'], later['upper']) == (20, 82., 118.)
    assert earlier['truth_revisions'][0]['revision'] == 1
    assert later['truth_revisions'][0]['revision'] == 2


def test_same_stratum_views_do_not_share_target_start_eligibility():
    bundle, snapshot = _case()
    bundle['views'][0]['publication']['information_cutoff'] = '2025-10-13T00:00:00Z'
    bundle['views'].append(_view(cutoff='2025-10-13T00:00:00Z', origin='2025-10-13'))
    row = dict(snapshot['issued_targets'][0], target_id='between-targets',
               start='2025-10-06', end='2025-10-07', origin='2025-10-06',
               issued_at='2025-10-06T00:00:00Z')
    snapshot['issued_targets'].append(row)
    snapshot['truth_revisions'].append(dict(snapshot['truth_revisions'][0], target_id=row['target_id'],
        available_at='2025-10-07T00:00:00Z', mature_at='2025-10-07T00:00:00Z'))
    actual = _assert_reference(bundle, snapshot)
    earlier, later = [v['daily'][0]['historical_error_interval']['80'] for v in actual['views']]
    assert earlier['n'] == 20
    assert later['n'] == 21
    assert row['target_id'] not in earlier['target_ids']
    assert row['target_id'] in later['target_ids']
