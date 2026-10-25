"""Architecture audit: synthetic cross-boundary path counterexamples."""
from datetime import date, timedelta

import pytest

from forecasting.planning import build_forecast


def snapshot(start=date(2026, 10, 19)):
    coverage, observations = [], []
    for offset in range(-100, 0):
        day = start + timedelta(days=offset)
        coverage.append(dict(date=str(day), source_id='meter', complete=True,
                             available_at=str(day)+'T23:00:00Z', revision=1))
        for person, team, quantity, exposure in [('p1', 't1', 10, 1), ('p2', 't2', 40, 2), (None, None, 5, 1)]:
            observations.append(dict(date=str(day), person_id=person, team_id=team,
                project_id='project', configuration_id='c1', meter='tokens', billing_pool='pool',
                quantity=quantity, exposure=exposure, source_id='meter',
                available_at=str(day)+'T23:00:00Z', complete=True, mature=True))
    return dict(id='snapshot', tenant_id='tenant', is_synthetic=True, information_cutoff=str(start)+'T00:00:00Z',
        forecast_start=str(start), history_complete_through=str(start-timedelta(days=1)),
        period_start='2026-10-01', period_end='2027-01-01',
        target=dict(unit='USD', quantity='spend', basis='planning', timezone='UTC'),
        required_sources=['meter'], observations=observations, coverage=coverage, drivers=[],
        pricing=[dict(id='tariff', version=1, billing_pool='pool', unit='tokens', currency='USD',
            period_start='2026-10-01', period_end='2027-01-01', rate=.1, mode='linear',
            complete_pool=True, known_at='2026-01-01T00:00:00Z')])


def build(s):
    return build_forecast(s, run_id='audit', generated_at=s['information_cutoff'])


def company(result):
    return next(v for v in result['views'] if v['scope']['type'] == 'company')


@pytest.mark.parametrize('weekday', range(7))
@pytest.mark.parametrize('quantity_target', [False, True])
def test_all_calendar_offsets_preserve_paths_and_rollup_partitions(weekday, quantity_target):
    s = snapshot(date(2026, 10, 19)+timedelta(days=weekday))
    if quantity_target:
        s['target'].update(unit='tokens', quantity='usage')
    result = build(s)
    v = company(result)
    by_id = {view['id']: view for view in result['views']}
    for partition in ['people', 'teams']:
        children = [by_id[i] for i in v['reconciliation'][partition]['scope_ids']]
        for bucket in ['daily', 'weekly', 'cumulative']:
            for i, point in enumerate(v[bucket]):
                for branch in ['low', 'base', 'high']:
                    assert point['configuration_values'][branch] == pytest.approx(sum(
                        child[bucket][i]['configuration_values'][branch] for child in children))
        assert v['quarter_outlook']['base'] == pytest.approx(sum(
            child['quarter_outlook']['base'] for child in children))
    for branch in ['low', 'base', 'high']:
        cumulative = {p['date']: p['configuration_values'][branch] for p in v['cumulative']}
        for point in v['daily'][1:]:
            prior = str(date.fromisoformat(point['date'])-timedelta(days=1))
            assert point['configuration_values'][branch] == pytest.approx(
                cumulative[point['date']]-cumulative[prior])
        assert v['weekly'][0]['configuration_values'][branch] == pytest.approx(sum(
            p['configuration_values'][branch] for p in v['daily'] if p['date'] < v['weekly'][0]['end']))
    assert v['quarter_outlook']['assumptions']
    assert v['scenario_range']['coverage_probability'] is None


def test_workload_conflicts_after_membership_change_are_excluded():
    s = snapshot()
    move = dict(id='move', kind='membership', scope={'person_id':'p1'}, status='eligible',
                effective_from=s['forecast_start'], parameters={'team_id':'t2'})
    person = dict(id='personal-load', kind='workload', scope={'person_id':'p1'}, status='eligible',
                  effective_from=s['forecast_start'], parameters={'exposure':2, 'unit':'work_units'})
    team = dict(id='team-load', kind='workload', scope={'team_id':'t2'}, status='eligible',
                effective_from=s['forecast_start'], parameters={'exposure':6, 'unit':'work_units'})
    s['drivers'] = [move, person, team]
    forward = company(build(s))
    s['drivers'] = [move, team, person]
    reverse = company(build(s))
    assert forward['daily'][0]['base'] == reverse['daily'][0]['base'] == pytest.approx(5.5)
    assert {d['id'] for d in forward['included_drivers']} == {'move'}


def test_workload_conflicts_use_snapshot_membership_and_actual_overlap_dates():
    s = snapshot()
    s['memberships'] = [dict(person_id='p1', team_id='t2', effective_from='2026-11-01')]
    person = dict(id='personal-load', kind='workload', scope={'person_id':'p1'}, status='eligible',
                  effective_from=s['forecast_start'], effective_to='2026-10-26',
                  parameters={'exposure':2, 'unit':'work_units'})
    team = dict(person, id='team-load', scope={'team_id':'t2'},
                parameters={'exposure':6, 'unit':'work_units'})
    s['drivers'] = [person, team]
    assert company(build(s))['daily'][0]['base'] == pytest.approx(14.5)
    s['memberships'][0]['effective_from'] = s['forecast_start']
    view = company(build(s))
    assert view['daily'][0]['base'] == pytest.approx(5.5)
    assert not view['included_drivers']


def test_known_next_quarter_fixed_charge_is_included_in_cross_quarter_daily_path():
    s = snapshot(date(2026, 12, 30))
    s['pricing'].append(dict(s['pricing'][0], id='next', period_start='2027-01-01',
                             period_end='2027-04-01', fixed=100))
    v = company(build(s))
    january = next(p for p in v['daily'] if p['date'] == '2027-01-01')
    assert january['base'] == pytest.approx(105.5)
    assert v['quarter_outlook']['base'] == pytest.approx(92*5.5)
    assert v['components']['fixed'] == 0
    assert v['weekly'][0]['base'] == pytest.approx(5*5.5+100)
    assert v['weekly'][1]['base'] == pytest.approx(7*5.5)


def test_newer_incomplete_coverage_revision_revokes_quarter_completeness():
    s = snapshot()
    old = next(row for row in s['coverage'] if row['date'] == '2026-10-10')
    s['coverage'].append(dict(old, complete=False, revision=2,
                             available_at='2026-10-18T23:30:00Z'))
    v = company(build(s))
    assert v['quarter_outlook']['base'] is None
    assert v['components']['late'] is None


@pytest.mark.parametrize('reverse', [False, True])
def test_coverage_revision_precedence_is_numeric_at_same_receipt_time(reverse):
    s = snapshot()
    old = next(row for row in s['coverage'] if row['date'] == '2026-10-10')
    old.update(revision=2, complete=True)
    s['coverage'].append(dict(old, revision=10, complete=False))
    if reverse:
        s['coverage'].reverse()
    assert company(build(s))['quarter_outlook']['base'] is None


def test_future_coverage_correction_cannot_revoke_frozen_coverage():
    s = snapshot()
    old = next(row for row in s['coverage'] if row['date'] == '2026-10-10')
    s['coverage'].append(dict(old, complete=False, revision=2,
                             available_at='2026-10-19T00:00:01Z'))
    assert company(build(s))['quarter_outlook']['base'] == pytest.approx(506)


def test_coverage_receipts_compare_instants_not_timestamp_strings():
    s = snapshot()
    old = next(row for row in s['coverage'] if row['date'] == '2026-10-10')
    old['available_at'] = '2026-10-18T23:00:00+02:00'
    s['coverage'].append(dict(old, complete=False, revision=2,
                             available_at='2026-10-18T22:00:00Z'))
    assert company(build(s))['quarter_outlook']['base'] is None


@pytest.mark.parametrize('kind,parameters,expected', [
    ('workload', {'exposure':2, 'unit':'work_units'}, [6.5]*5+[5.5]*2),
    ('adoption', {'configuration_id':'c2', 'share':.5}, [6.0]*5+[5.5]*2),
    ('project_schedule', {'from_start':'2026-10-19', 'from_end':'2026-10-26',
                          'to_start':'2026-10-20'}, [4.5, 5.5, 5.5, 5.5, 5.5, 6.5, 5.5]),
])
def test_identical_absolute_states_apply_once_over_union_of_effective_dates(kind, parameters, expected):
    s = snapshot()
    s['pricing'][0]['configuration_id'] = 'c1'
    s['pricing'].append(dict(s['pricing'][0], id='new-price', configuration_id='c2', rate=.2))
    first = dict(id='first', kind=kind, scope={'person_id':'p1','project_id':'project'},
                 status='eligible', effective_from='2026-10-19', effective_to='2026-10-22',
                 parameters=parameters)
    second = dict(first, id='second', effective_from='2026-10-20', effective_to='2026-10-24')
    s['drivers'] = [first, second]
    view = company(build(s))
    assert [p['base'] for p in view['daily']] == pytest.approx(expected)
    assert {d['id'] for d in view['included_drivers']} == {'first','second'}
    s['drivers'].reverse()
    assert [p['base'] for p in company(build(s))['daily']] == pytest.approx(expected)


def test_different_overlapping_absolute_states_remain_visible_and_excluded():
    s = snapshot()
    first = dict(id='first', kind='workload', scope={'person_id':'p1'}, status='eligible',
                 effective_from='2026-10-19', effective_to='2026-10-22',
                 parameters={'exposure':2, 'unit':'work_units'})
    second = dict(first, id='second', effective_from='2026-10-20', effective_to='2026-10-24',
                  parameters={'exposure':3, 'unit':'work_units'})
    s['drivers'] = [first, second]
    view = company(build(s))
    assert [p['base'] for p in view['daily']] == pytest.approx([5.5]*7)
    assert not view['included_drivers']
    assert {d['id'] for d in view['queued_changes']} == {'first','second'}
    assert all('Conflicting' in d['publication_reason'] for d in view['queued_changes'])


def test_repeated_absolute_state_does_not_fill_inactive_date_gaps():
    s = snapshot()
    first = dict(id='first', kind='workload', scope={'person_id':'p1'}, status='eligible',
                 effective_from='2026-10-19', effective_to='2026-10-20',
                 parameters={'exposure':2, 'unit':'work_units'})
    second = dict(first, id='second', effective_from='2026-10-21', effective_to='2026-10-22',
                  parameters={'exposure':2.0, 'unit':'work_units'})
    s['drivers'] = [first, second]
    assert [p['base'] for p in company(build(s))['daily']] == pytest.approx(
        [6.5, 5.5, 6.5, 5.5, 5.5, 5.5, 5.5])
