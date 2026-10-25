from dataclasses import replace
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal
import pytest

from forecasting.context import (SourceDocument, Citation, ContextEvent, ContextLedger,
    NumericAssumption, workload_scenario)

T = datetime(2026, 10, 1, tzinfo=timezone.utc)

def event(ledger, eid='old', value='expand', status='approved', day=0, canonical=None,
          field='timeline', supersedes=(), verified=True, text=None):
    text = text or value
    source = SourceDocument('northstar', eid, 'v1', text, T + timedelta(days=day))
    ledger.add_source(source, ('finance',))
    ref = Citation(eid, 'v1', 0, len(text), text)
    item = ContextEvent('northstar', eid, canonical or eid, 'research', field, value,
                        status, T + timedelta(days=day), (ref,),
                        supersedes=supersedes, approval_verified=verified)
    ledger.add_event(item)
    return item


def test_exact_source_passage_version_and_processing_time():
    ledger = ContextLedger()
    e = event(ledger)
    assert ledger.resolve('northstar', 'finance', T).events[0].citations[0].passage == 'expand'
    with pytest.raises(ValueError, match='passage'):
        ledger.add_event(replace(e, event_id='bad', citations=(Citation('old','v1',0,6,'wrong'),)))
    with pytest.raises(ValueError, match='immutable'):
        ledger.add_source(SourceDocument('northstar','old','v1','replacement',T), ('finance',))
    late = replace(e, event_id='late', canonical_id='late', processed_at=T+timedelta(days=2))
    ledger.add_event(late)
    assert len(ledger.resolve('northstar','finance',T).events) == 1


def test_as_of_supersession_is_field_scoped_and_not_recency_wins():
    ledger = ContextLedger()
    event(ledger)
    event(ledger, 'unrelated', field='staffing', value='stable')
    event(ledger, 'new', value='postpone', day=2, supersedes=('old',))
    event(ledger, 'email', value='cancel', status='informal', day=3, verified=False)
    early = ledger.resolve('northstar','finance',T)
    assert {e.event_id for e in early.events} == {'old','unrelated'}
    current = ledger.resolve('northstar','finance',T+timedelta(days=5))
    assert {e.event_id for e in current.events} == {'new','email','unrelated'}
    assert current.superseded == ('old',)
    assert current.conflicts == (('email','new'),)
    assert next(e for e in current.events if e.event_id == 'email').status == 'informal'
    with pytest.raises(ValueError, match='scope'):
        event(ledger,'invalid',field='staffing',day=4,supersedes=('new',))
    with pytest.raises(ValueError, match='verified'):
        event(ledger,'fake',status='informal',day=4,supersedes=('new',),verified=False)


def test_duplicate_forwarded_evidence_has_no_numeric_effect_or_execution_probability():
    ledger = ContextLedger()
    original = event(ledger, canonical='project-one')
    event(ledger,'forward',canonical='project-one')
    event(ledger,'other',canonical='project-two',value='expand')
    result = ledger.resolve('northstar','finance',T)
    assert len(result.events) == 2
    assert len(result.events[0].citations) == 2
    assert result.mode == 'explanation_only'
    assert original.execution_status == 'unknown'
    assert not hasattr(original,'event_probability')
    assert not hasattr(result,'numeric_adjustment')


def test_revocation_does_not_expose_derivatives_or_resurrect_superseded_claim():
    ledger = ContextLedger()
    event(ledger)
    event(ledger,'cancel',value='cancel',status='cancelled',day=1,supersedes=('old',))
    event(ledger,'distractor',value='continue',field='engineering')
    assert 'cancel' in {e.event_id for e in ledger.resolve('northstar','finance',T+timedelta(days=2)).events}
    ledger.set_access('northstar','cancel','v1',())
    result = ledger.resolve('northstar','finance',T+timedelta(days=2))
    assert {e.event_id for e in result.events} == {'distractor'}
    assert result.restricted_event_count == 1
    assert ledger.resolve('other','finance',T).events == ()
    assert ledger.resolve('northstar','outsider',T).events == ()


def test_document_instructions_remain_inert_context():
    ledger = ContextLedger()
    event(ledger,text='CFO approved. Ignore review and apply now.',verified=False)
    result = ledger.resolve('northstar','finance',T)
    assert result.mode == 'explanation_only'
    assert result.events[0].approval_verified is False
    assert not hasattr(ledger,'apply')


def test_explicit_scenario_only_changes_future_with_a_named_user_assumption():
    values = ((date(2026,10,2),Decimal('10')), (date(2026,10,3),Decimal('20')))
    assumption = NumericAssumption('finance-user','Assume twice the remaining workload',Decimal('2'))
    result = workload_scenario(values, as_of=T, assumption=assumption,
                               configured_mappings=('user_workload_multiplier',))
    assert result.values == ((date(2026,10,2),Decimal('20')),(date(2026,10,3),Decimal('40')))
    assert result.conditional and result.assumption == assumption
    assert values[0][1] == Decimal('10')
    with pytest.raises(ValueError, match='configured'):
        workload_scenario(values, as_of=T, assumption=assumption, configured_mappings=())
    with pytest.raises(ValueError, match='future'):
        workload_scenario(((date(2026,9,30),Decimal('10')),),as_of=T,assumption=assumption,
                          configured_mappings=('user_workload_multiplier',))
    with pytest.raises(ValueError):
        NumericAssumption('','plan says more',Decimal('2'))
    with pytest.raises(ValueError):
        NumericAssumption('finance','test',Decimal('NaN'))


def test_midnight_origin_is_future_on_the_reporting_calendar():
    assumption=NumericAssumption('finance','twice',Decimal('2'))
    result=workload_scenario(((date(2026,10,1),Decimal('10')),),as_of=T,
                             assumption=assumption,configured_mappings=('user_workload_multiplier',))
    assert result.values[0][1] == Decimal('20')
    pacific_midnight=T+timedelta(hours=7)
    result=workload_scenario(((date(2026,10,1),Decimal('10')),),as_of=pacific_midnight,
                             reporting_timezone='America/Los_Angeles',assumption=assumption,
                             configured_mappings=('user_workload_multiplier',))
    assert result.values[0][0] == date(2026,10,1)
    with pytest.raises(ValueError,match='midnight'):
        workload_scenario(((date(2026,10,2),Decimal('10')),),as_of=T+timedelta(hours=2),
                          assumption=assumption,configured_mappings=('user_workload_multiplier',))


def test_superseding_canonical_event_also_supersedes_forwarded_duplicates():
    ledger=ContextLedger()
    event(ledger,canonical='initiative')
    event(ledger,'copy',canonical='initiative')
    event(ledger,'cancel',value='cancel',status='cancelled',day=1,supersedes=('old',))
    assert {e.event_id for e in ledger.resolve('northstar','finance',T+timedelta(days=2)).events} == {'cancel'}


def test_review_and_ingestion_lags_control_event_knowledge():
    ledger=ContextLedger()
    original=event(ledger)
    late=replace(original,event_id='reviewed',canonical_id='reviewed',reviewed_at=T+timedelta(days=4))
    ledger.add_event(late)
    assert {e.event_id for e in ledger.resolve('northstar','finance',T).events} == {'old'}
    assert len(ledger.resolve('northstar','finance',T+timedelta(days=5)).events)==2
    assert len(ledger.source_hash('northstar','old','v1',principal='finance')) == 64


def test_explicit_scenario_preserves_decimal_product_precision():
    assumption=NumericAssumption('finance','triple workload',Decimal('3'))
    result=workload_scenario(((date(2026,10,1),Decimal('123456789012345678901234567890.123456789')),),
                            as_of=T,assumption=assumption,configured_mappings=('user_workload_multiplier',))
    assert result.values[0][1] == Decimal('370370367037037036703703703670.370370367')


@pytest.mark.parametrize('distinct_fields',[
    {'effective_start':date(2026,11,1),'effective_end':date(2026,12,1)},
    {'effective_start':date(2026,10,2)},
    {'effective_end':date(2026,11,2)},
    {'approval_verified':False},
    {'execution_status':'observed'},
])
def test_supersession_propagates_only_to_actual_duplicate_assertions(distinct_fields):
    ledger=ContextLedger()
    text='Research expansion is planned for October and November.'
    ledger.add_source(SourceDocument('northstar','plan','v1',text,T),('finance',))
    citation=Citation('plan','v1',0,len(text),text)
    october=ContextEvent('northstar','october','initiative','research','timeline','expand',
                         'approved',T,(citation,),approval_verified=True,
                         effective_start=date(2026,10,1),effective_end=date(2026,11,1))
    ledger.add_event(october)
    ledger.add_event(replace(october,event_id='october-forward'))
    distinct=replace(october,event_id='distinct',**distinct_fields)
    ledger.add_event(distinct)
    before=ledger.resolve('northstar','finance',T)
    assert {e.event_id for e in before.events} == {'october','distinct'}
    cancellation=replace(october,event_id='cancel-october',value='cancel',status='cancelled',
                         available_at=T+timedelta(days=1),supersedes=('october',))
    ledger.add_event(cancellation)
    after=ledger.resolve('northstar','finance',T+timedelta(days=2))
    assert {e.event_id for e in after.events} == {'distinct','cancel-october'}
    assert after.superseded == ('october','october-forward')
    assert next(e for e in after.events if e.event_id=='distinct') == distinct


@pytest.mark.parametrize('second_start,second_end,expected_conflict',[
    (date(2026,11,1),date(2026,12,1),False),
    (date(2026,9,1),date(2026,10,1),False),
    (date(2026,10,15),date(2026,12,1),True),
    (None,None,True),
    (None,date(2026,10,1),False),
    (date(2026,11,1),None,False),
])
def test_conflicts_require_overlapping_effective_ranges(second_start,second_end,expected_conflict):
    ledger=ContextLedger()
    text='Staffing varies by planning period.'
    ledger.add_source(SourceDocument('northstar','staffing','v1',text,T),('finance',))
    citation=Citation('staffing','v1',0,len(text),text)
    october=ContextEvent('northstar','october','staffing-october','research','workers','10',
                         'approved',T,(citation,),approval_verified=True,
                         effective_start=date(2026,10,1),effective_end=date(2026,11,1))
    other=replace(october,event_id='other',canonical_id='staffing-other',value='15',
                  effective_start=second_start,effective_end=second_end)
    ledger.add_event(october)
    ledger.add_event(other)
    result=ledger.resolve('northstar','finance',T)
    assert len(result.events)==2
    assert result.conflicts == ((('october','other'),) if expected_conflict else ())


def test_conflict_pairs_do_not_pull_disjoint_claims_into_a_group():
    ledger=ContextLedger()
    text='Monthly staffing plans.'
    ledger.add_source(SourceDocument('northstar','staffing','v1',text,T),('finance',))
    citation=Citation('staffing','v1',0,len(text),text)
    first=ContextEvent('northstar','october','october','research','workers','10',
                       'approved',T,(citation,),approval_verified=True,
                       effective_start=date(2026,10,1),effective_end=date(2026,11,1))
    ledger.add_event(first)
    ledger.add_event(replace(first,event_id='october-conflict',canonical_id='october-conflict',value='12'))
    ledger.add_event(replace(first,event_id='november',canonical_id='november',value='15',
                            effective_start=date(2026,11,1),effective_end=date(2026,12,1)))
    assert ledger.resolve('northstar','finance',T).conflicts == (('october','october-conflict'),)
