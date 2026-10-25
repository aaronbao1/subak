"""Supported connector evidence must become cited drivers, never arbitrary multipliers."""
from copy import deepcopy
from app.forecasting.evidence import extract_event
from app.forecasting.fixtures import build_northstar_snapshot, northstar_evidence


def test_fixture_native_evidence_extracts_cited_drivers_and_release_is_context():
    snapshot = build_northstar_snapshot()
    events = northstar_evidence()
    drivers = [d for event in events for d in extract_event(event, snapshot)]
    eligible = [d for d in drivers if d['status'] == 'eligible']
    assert {'project_schedule', 'membership', 'workload', 'adoption', 'pricing'} <= {d['kind'] for d in eligible}
    for event in events:
        for d in extract_event(event, snapshot):
            assert d['citations'][0]['quote'] in event['text']
            assert d['source_revision'] == event['revision']
    release = next(e for e in events if e['source'] == 'model_release')
    assert all(d['status'] == 'context_only' for d in extract_event(release, snapshot))


def test_ambiguous_names_incompatible_units_and_claimed_benchmark_savings_stay_context():
    s = build_northstar_snapshot()
    base = {'source':'slack','source_id':'test','revision':1,'occurred_at':'2026-10-23T09:00:00Z',
            'available_at':'2026-10-23T09:00:00Z','is_synthetic':True, 'payload':{}}
    for text in ('Maybe double Atlas workload soon.', 'Atlas workload is 50 bananas from 2026-10-26.',
                 'The new model benchmark is 40% faster so tokens will fall 40%.'):
        result = extract_event({**base, 'text':text}, s)
        assert result and all(d['status'] == 'context_only' for d in result)


def test_prose_adoption_is_absolute_cited_and_repeated_extraction_idempotent():
    s = build_northstar_snapshot()
    e = {'source':'slack','source_id':'rollout','revision':2,'occurred_at':'2026-10-23T09:00:00Z',
         'available_at':'2026-10-23T09:00:00Z','is_synthetic':True,
         'text':'Atlas will use nova for 60% of requests from 2026-10-28 through 2026-11-20.', 'payload':{}}
    first = extract_event(e, s)
    assert first == extract_event(e, s)
    assert first[0]['status'] == 'eligible'
    assert first[0]['kind'] == 'adoption'
    assert first[0]['parameters']['share'] == 0.6
    assert first[0]['parameters']['mode'] == 'absolute'


def test_history_has_84_complete_days_explicit_source_coverage_and_shared_rows():
    s = build_northstar_snapshot()
    assert len({r['date'] for r in s['observations']}) >= 84
    assert s['period_start'] == '2026-10-01' and s['period_end'] == '2027-01-01'
    assert any(r['person_id'] is None and r['team_id'] is None for r in s['observations'])
    for day in {r['date'] for r in s['observations']}:
        assert set(s['required_sources']) <= {c['source_id'] for c in s['coverage'] if c['date'] == day and c['complete']}


def test_conflict_is_context_and_explicit_revision_supersedes_absolute_state():
    s = build_northstar_snapshot()
    e = deepcopy(next(e for e in northstar_evidence() if e['source'] == 'asana'))
    e['payload']['conflicting'] = True
    assert all(d['status']=='context_only' for d in extract_event(e,s))
    e['payload'].pop('conflicting')
    e['payload']['supersedes'] = 'old-driver'
    driver = extract_event(e,s)[0]
    assert driver['supersedes'] == 'old-driver'
    assert driver['parameters']['mode'] == 'absolute'


def test_invalid_native_payload_and_prose_payload_disagreement_remain_context():
    s=build_northstar_snapshot()
    event=deepcopy(next(e for e in northstar_evidence() if e['source']=='asana'))
    event['payload']['custom_fields'][2]['text_value']=42
    assert extract_event(event,s)[0]['status']=='context_only'
    event['payload']['custom_fields'][2]['text_value']='2026-11-20'
    assert extract_event(event,s)[0]['status']=='context_only'


def test_replay_cases_include_independently_generated_future_outcomes():
    from app.forecasting.fixtures import northstar_replay_cases
    cases=northstar_replay_cases()
    assert len(cases)==7
    assert all(len(case['actuals'])==4 for case in cases)
    assert all(row['is_synthetic'] for case in cases for row in case['actuals'])


def test_native_extraction_flows_through_pricing_and_paired_explanation():
    from forecasting.planning import build_forecast
    s=build_northstar_snapshot()
    s['drivers']=[d for e in northstar_evidence() for d in extract_event(e,s)]
    bundle=build_forecast(s,run_id='extracted',generated_at=s['generated_at'])
    company=next(v for v in bundle['views'] if v['scope']['type']=='company')
    assert company['quarter_outlook']['complete']
    assert len(company['included_drivers'])==5
    effects={e['driver_id']:e for e in bundle['driver_effects']}
    pricing=next(d for d in s['drivers'] if d['kind']=='pricing')
    adoption=next(d for d in s['drivers'] if d['kind']=='adoption' and d['status']=='eligible')
    assert effects[pricing['id']]['base_delta']<0
    # Merely choosing a new model gives no invented usage/cost reduction when
    # the observed rate and same complete-pool tariff remain unchanged.
    assert effects[adoption['id']]['base_delta']==0
    assert pricing['citations'][0]['quote'].startswith('pool-main rate')


def test_negated_and_proposed_actions_never_change_the_baseline():
    s=build_northstar_snapshot()
    event=deepcopy(next(e for e in northstar_evidence() if e['source']=='slack' and 'will use' in e['text']))
    for prefix in ('Do not: ', 'Proposed: ', 'We could consider: ', 'Unconfirmed: '):
        event['text']=prefix+'Atlas will use nova for 60% of requests from 2026-10-28.'
        assert extract_event(event,s)[0]['status']=='context_only'


def test_connector_revision_replaces_prior_source_state_without_compounding():
    from forecasting.planning import build_forecast
    s=build_northstar_snapshot()
    event=deepcopy(next(e for e in northstar_evidence() if e['source']=='monday'))
    old=extract_event(event,s)[0]
    event.update(revision=2,text='Beacon workload is 3 work_units per day from 2026-10-26 through 2026-11-15.')
    replacement=extract_event(event,s)[0]
    assert replacement['supersedes']==old['id']
    combined=build_forecast(s,run_id='combined',generated_at=s['generated_at'],drivers=[old,replacement])
    one=build_forecast(s,run_id='one',generated_at=s['generated_at'],drivers=[replacement])
    def amount(bundle):
        return next(v for v in bundle['views'] if v['scope']['type']=='company')['quarter_outlook']['base']
    assert amount(combined)==amount(one)


def test_native_entity_id_disagreeing_with_prose_is_context():
    s=build_northstar_snapshot()
    event=deepcopy(next(e for e in northstar_evidence() if e['source']=='monday'))
    event['payload']['project_id']='atlas'
    assert extract_event(event,s)[0]['status']=='context_only'


def test_same_envelope_conflicts_and_reversed_effective_range_remain_context():
    s=build_northstar_snapshot()
    event=deepcopy(next(e for e in northstar_evidence() if e['source']=='monday'))
    for text in ('Beacon workload is 2 work_units per day from 2026-10-26. Beacon workload is 5 work_units per day from 2026-10-26.',
                 'Beacon workload is 2 work_units per day from 2026-11-20 through 2026-10-26.'):
        event['text']=text
        assert extract_event(event,s)[0]['status']=='context_only'


def test_native_schedule_cites_source_field_values_when_text_has_no_dates():
    s=build_northstar_snapshot()
    event=deepcopy(next(e for e in northstar_evidence() if e['source']=='asana'))
    event['text']='Atlas schedule updated.'
    driver=extract_event(event,s)[0]
    assert driver['status']=='eligible'
    structured=next(c for c in driver['citations'] if c.get('field_path')=='payload.custom_fields')
    assert structured['value']==event['payload']['custom_fields']
    assert '2026-11-02' in structured['quote']


def test_fixture_spending_adapter_reconciles_recorded_person_team_and_shared_amounts():
    import math
    from app.forecasting.fixtures import northstar_spending_records
    from forecasting.planning import build_forecast
    from app.compat.schemas import SpendingRecord
    snapshot=build_northstar_snapshot()
    records=northstar_spending_records(snapshot)
    bundle=build_forecast(snapshot,run_id='spending-reconciliation',generated_at=snapshot['generated_at'])
    company=next(v for v in bundle['views'] if v['scope']['type']=='company')
    assert math.isclose(math.fsum(r['amount'] for r in records),company['components']['recorded'],abs_tol=1e-10)
    assert all(r['provenance']=='estimate' and r['complete'] for r in records)
    assert all('synthetic' in r['source'].lower() for r in records)
    assert all(snapshot['period_start']<=r['date']<snapshot['forecast_start'] for r in records)
    for r in records:
        SpendingRecord.model_validate(r)
    assert any(r['teamId']=='unattributed' and not r.get('personId') for r in records)
    for view in bundle['views']:
        scope=view['scope']
        if scope['type']=='person':
            amount=math.fsum(r['amount'] for r in records if r.get('personId')==scope['id'])
            assert math.isclose(amount,view['components']['recorded'],abs_tol=1e-10)
        elif scope['type']=='team':
            amount=math.fsum(r['amount'] for r in records if r['teamId']==scope['id'])
            assert math.isclose(amount,view['components']['recorded'],abs_tol=1e-10)


def test_fixture_spending_adapter_rejects_unknown_tariffs_and_marks_partial_coverage():
    import pytest
    from app.forecasting.fixtures import northstar_spending_records
    snapshot=build_northstar_snapshot()
    for change in ({'mode':'volume'}, {'complete_pool':False}, {'rate':None}, {'currency':'EUR'}, {'allowance':100}):
        unsupported=deepcopy(snapshot)
        unsupported['pricing'][0].update(change)
        with pytest.raises(ValueError):
            northstar_spending_records(unsupported)
    partial=deepcopy(snapshot)
    day=partial['period_start']
    partial['coverage']=[c for c in partial['coverage'] if not(c['date']==day and c['source_id']==partial['required_sources'][0])]
    assert all(not r['complete'] for r in northstar_spending_records(partial) if r['date']==day)
    assert any(r['complete'] for r in northstar_spending_records(partial) if r['date']!=day)
