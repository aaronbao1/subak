"""Deterministic Northstar connector demo, explicitly synthetic throughout.

Daily usage is input evidence, never inferred from a forecast. All required source/day
coverage is explicit, including weekends and shared usage. These examples demonstrate
mechanics and cannot establish enterprise accuracy or promote a learning candidate.
"""
from __future__ import annotations

import hashlib
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone

from .evidence import extract_event


def northstar_evidence() -> list[dict]:
    def event(source, identifier, text, payload, *, available='2026-10-23T15:00:00Z', revision=1):
        return {'source':source,'source_id':identifier,'revision':revision,
                'occurred_at':available,'available_at':available,'text':text,
                'payload':payload,'is_synthetic':True}
    return [
        event('asana','asana:task:atlas-launch',
              'Move Atlas from 2026-10-26 through 2026-10-30 to 2026-11-02. The same five days of evaluation work remain.',
              {'resource_type':'task','gid':'120348001','project_id':'atlas','name':'Atlas launch evaluation',
               'custom_fields':[{'gid':'cf-101','name':'from_start','resource_subtype':'text','text_value':'2026-10-26'},
                                {'gid':'cf-102','name':'from_end','resource_subtype':'text','text_value':'2026-10-31'},
                                {'gid':'cf-103','name':'to_start','resource_subtype':'text','text_value':'2026-11-02'}],
               'events':[{'action':'changed','resource':{'gid':'120348001','resource_type':'task'},
                          'change':{'field':'due_on','action':'changed','new_value':'2026-11-06'}}],
               'permalink':'https://app.asana.com/0/120348001/120348001'}),
        event('slack','slack:C-people:1792767600.000100',
              'Maya Chen moves to product team from 2026-10-27 at 1 exposure.',
              {'type':'message','channel':'C-people','ts':'1792767600.000100','user':'U-MAYA',
               'person_id':'maya','permalink':'https://northstar.example/slack/C-people/p1792767600000100'}),
        event('monday','monday:item:982331',
              'Beacon workload is 2.4 work_units per day from 2026-10-26 through 2026-11-15.',
              {'boardId':7811,'itemId':982331,'project_id':'beacon','column_values':[{'id':'status','text':'Approved','value':'{"index":1}'},
               {'id':'workload','text':'2.4','value':'2.4'}],
               'permalink':'https://northstar.example/monday/boards/7811/pulses/982331'}),
        event('slack','slack:C-models:1792767700.000100',
              'Atlas will use nova for 60% of requests from 2026-10-28 through 2026-11-20.',
              {'type':'message','channel':'C-models','ts':'1792767700.000100','user':'U-PRIYA',
               'project_id':'atlas','permalink':'https://northstar.example/slack/C-models/p1792767700000100'}),
        event('slack','slack:C-finance:1792767800.000100',
              'pool-main rate is USD 0.000012 per tokens from 2026-11-01.',
              {'type':'message','channel':'C-finance','ts':'1792767800.000100','user':'U-FINANCE',
               'permalink':'https://northstar.example/slack/C-finance/p1792767800000100'}),
        event('model_release','models:nova:release:2026-10-22',
              'Nova is now available. The vendor reports a 30% benchmark speed improvement; deployment is optional.',
              {'model':'nova','release_date':'2026-10-22','vendor':'Example Models','benchmark':{'latency_improvement':0.3},
               'url':'https://models.example/nova/releases/2026-10-22'}),
        event('slack','slack:C-plans:1792767900.000100',
              'Maybe double Atlas workload soon if approved.',
              {'type':'message','channel':'C-plans','ts':'1792767900.000100','user':'U-PLAN'}),
    ]


def build_northstar_snapshot(*, now: str | None = None, tenant_id: str = 'northstar') -> dict:
    now = now or '2026-10-26T00:00:00Z'
    instant = datetime.fromisoformat(now.replace('Z','+00:00'))
    if instant.tzinfo is None:
        raise ValueError('fixture cutoff must be timezone-aware')
    instant = instant.astimezone(timezone.utc)
    start = instant.date()
    complete_through = start - timedelta(days=1)
    stamp = instant.isoformat().replace('+00:00','Z')
    teams = [{'id':'research','name':'Research'},{'id':'product','name':'Product'},
             {'id':'engineering','name':'Engineering'}]
    people = [{'id':'maya','name':'Maya Chen'},{'id':'priya','name':'Priya Rao'},
              {'id':'owen','name':'Owen Park'},{'id':'liam','name':'Liam Brooks'},
              {'id':'zoe','name':'Zoe Kim'},{'id':'noah','name':'Noah Patel'}]
    memberships = [{'person_id':p['id'],'team_id':t,'effective_from':'2026-01-01','effective_to':None,'exposure':1}
                   for p,t in zip(people,['research','research','product','product','engineering','engineering'])]
    projects = [{'id':'atlas','name':'Atlas','start_date':'2026-07-01','end_date':'2026-12-31'},
                {'id':'beacon','name':'Beacon','start_date':'2026-07-01','end_date':'2026-12-31'},
                {'id':'platform','name':'Platform','start_date':'2026-07-01','end_date':'2026-12-31'}]
    sources = ['usage:vendor-main','usage:shared']
    observations, coverage = [], []
    # At least 84 complete daily observations, and enough prefix to price all quarter
    # usage when replaying an early or late quarter publication.
    history_start = min(start-timedelta(days=84), date(2026,10,1))
    day = history_start
    while day <= complete_through:
        available = (day+timedelta(days=1)).isoformat()+'T00:00:00Z'
        for source in sources:
            coverage.append({'date':day.isoformat(),'source_id':source,'complete':True,
                             'available_at':available,'revision':1})
        weekday = day.weekday()
        for index, membership in enumerate(memberships):
            # Eight observed weekday repeats with a deterministic week effect,
            # zero weekend usage is explicit rather than a missing record.
            exposure = 1.0 if weekday < 5 else 0.0
            project = ['atlas','atlas','beacon','beacon','platform','platform'][index]
            week_effect = 1+(((day-date(2026,1,5)).days//7)%5-2)*0.025
            quantity = round((210000+index*25000)*(1+weekday*0.04)*week_effect*exposure, 3)
            observations.append({'date':day.isoformat(), 'person_id':membership['person_id'],
                                 'team_id':membership['team_id'],'project_id':project,
                                 'configuration_id':'classic','meter':'tokens','billing_pool':'pool-main',
                                 'quantity':quantity,'exposure':exposure,'work_units':exposure,
                                 'source_id':sources[0],'source_revision':1,'available_at':available,
                                 'complete':True,'mature':True,'is_synthetic':True})
        observations.append({'date':day.isoformat(),'person_id':None,'team_id':None,'project_id':None,
                             'configuration_id':'classic','meter':'tokens','billing_pool':'pool-main',
                             'quantity':50000.0 if weekday<5 else 10000.0,'exposure':1.0,
                             'work_units':1.0,'source_id':sources[1],'source_revision':1,
                             'available_at':available,'complete':True,'mature':True,'is_synthetic':True})
        day += timedelta(days=1)
    snapshot = {'schema_version':1,'id':'snap_fixture_'+hashlib.sha256((tenant_id+stamp).encode()).hexdigest()[:16],
                'tenant_id':tenant_id,'information_cutoff':stamp,'generated_at':stamp,
                'history_complete_through':complete_through.isoformat(),'forecast_start':start.isoformat(),
                'period_start':'2026-10-01','period_end':'2027-01-01',
                'target':{'unit':'USD','quantity':'spend','basis':'planning','timezone':'UTC'},
                'people':people,'teams':teams,'memberships':memberships,'projects':projects,
                'configurations':[{'id':'classic','name':'Classic'},{'id':'nova','name':'Nova'}],
                'work_unit':'work_units','required_sources':sources,'coverage':coverage,'observations':observations,
                'pricing':[{'id':'tariff-main','version':1,'billing_pool':'pool-main','unit':'tokens',
                            'currency':'USD','period_start':'2026-10-01','period_end':'2027-01-01',
                            'mode':'linear','rate':0.000018,'allowance':0,'fixed':0,'complete_pool':True,
                            'known_at':'2026-07-01T00:00:00Z'}],
                'source_revisions':{source:1 for source in sources},'is_synthetic':True,
                'limitations':['Deterministic synthetic Northstar fixture; no enterprise accuracy claim.']}
    snapshot['evidence'] = [event for event in northstar_evidence() if event['available_at'] <= stamp]
    snapshot['drivers'] = [d for event in snapshot['evidence'] for d in extract_event(event,snapshot)]
    return snapshot


def northstar_replay_cases() -> list[dict]:
    """Reconstructible synthetic task cases; held-out truth is input usage, not outputs."""
    snapshot = build_northstar_snapshot()
    cases = []
    for event in northstar_evidence():
        extracted = extract_event(event, snapshot)
        # Independent expected oracle encoded from fixture facts, not obtained by
        # running a forecast. Ambiguous/release evidence intentionally has none.
        oracle = []
        facts = {
            'asana:task:atlas-launch': ('project_schedule', {'project_id':'atlas'}, '2026-10-26',
                {'from_start':'2026-10-26','from_end':'2026-10-31','to_start':'2026-11-02'}),
            'slack:C-people:1792767600.000100': ('membership', {'person_id':'maya'}, '2026-10-27', {'team_id':'product','exposure':1}),
            'monday:item:982331': ('workload', {'project_id':'beacon'}, '2026-10-26', {'exposure':2.4,'unit':'work_units'}),
            'slack:C-models:1792767700.000100': ('adoption', {'project_id':'atlas'}, '2026-10-28', {'configuration_id':'nova','share':0.6}),
            'slack:C-finance:1792767800.000100': ('pricing', {'billing_pool':'pool-main'}, '2026-11-01', {'rate':0.000012,'unit':'tokens','currency':'USD'}),
        }
        if event['source_id'] in facts:
            kind,scope,begin,params = facts[event['source_id']]
            end = {'workload':'2026-11-16','adoption':'2026-11-21'}.get(kind)
            oracle = [{'id':'oracle:'+event['source_id'],'kind':kind,'scope':scope,'effective_from':begin,
                       'effective_to':end,'parameters':params,'status':'eligible','citations':[]}]
        cases.append({'id':event['source_id'],'snapshot':deepcopy(snapshot),'envelopes':[deepcopy(event)],
                      'oracle_drivers':oracle,'actuals':_future_actuals(event['source_id']), 'is_synthetic':True,
                      'expected_extraction':{'eligible_count':len(oracle)},
                      'qualification':'Synthetic extraction/mechanics replay using independently prescribed future usage; not enterprise accuracy.'})
    return cases


def _future_actuals(source_id: str) -> list[dict]:
    """Independent prescribed observations for a controlled synthetic replay.

    No forecasting function is called here. The explicit generator that supplied
    historical usage supplies future observations, with the one case's actual
    plan change realized. Financial truth uses the case's prescribed tariff.
    """
    begin = date(2026,10,26)
    totals = []
    for offset in range(28):
        day = begin+timedelta(days=offset)
        weekday = day.weekday()
        week_effect = 1+(((day-date(2026,1,5)).days//7)%5-2)*0.025
        quantity = 50000.0 if weekday<5 else 10000.0
        for index in range(6):
            exposure = 1.0 if weekday<5 else 0.0
            if source_id == 'monday:item:982331' and index in (2,3) and day<date(2026,11,16):
                exposure = 1.2
            if source_id == 'asana:task:atlas-launch' and index in (0,1):
                if date(2026,10,26)<=day<date(2026,10,31):
                    exposure=0.0
                elif date(2026,11,2)<=day<date(2026,11,7):
                    exposure=2.0
            # Weekend work has the prescribed mean weekday token/work rate.
            rate_weekday = weekday if weekday<5 else 2
            quantity += round((210000+index*25000)*(1+rate_weekday*0.04)*week_effect*exposure,3)
        tariff = 0.000012 if source_id=='slack:C-finance:1792767800.000100' and day>=date(2026,11,1) else 0.000018
        totals.append(quantity*tariff)
    return [{'scope_type':'company','scope_id':'northstar','aggregation':'weekly',
             'start':(begin+timedelta(days=week*7)).isoformat(),
             'end':(begin+timedelta(days=(week+1)*7)).isoformat(),
             'value':round(sum(totals[week*7:(week+1)*7]),8),'unit':'USD','timezone':'UTC',
             'is_synthetic':True,'complete':True,'mature':True,
             'truth_source':'northstar-independent-prescribed-usage-v1'} for week in range(4)]


def northstar_spending_records(snapshot: dict) -> list[dict]:
    """Frontend actual-usage estimates from the *same* synthetic publication inputs.

    This fixture adapter prices recorded quantities only, at the supported fixture
    tariff. It never uses forecast paths, inferred future drivers, current team
    membership or the legacy seed ledger. The frontend amount field cannot express
    unknown spend, so unsupported/ambiguous pricing raises ValueError.
    """
    import json
    import math
    from decimal import Decimal, InvalidOperation

    def instant(value):
        result = datetime.fromisoformat(str(value).replace('Z','+00:00'))
        if result.tzinfo is None:
            raise ValueError('fixture spending timestamps must be timezone-aware')
        return result.astimezone(timezone.utc)

    def day(value):
        return date.fromisoformat(str(value)[:10])

    if snapshot.get('is_synthetic') is not True or snapshot.get('target',{}).get('unit') != 'USD':
        raise ValueError('northstar spending adapter requires an explicitly synthetic USD usage fixture')
    cutoff=instant(snapshot['information_cutoff'])
    period_start=day(snapshot['period_start'])
    prefix_end=min(day(snapshot['forecast_start']),day(snapshot['period_end']))
    complete_through=day(snapshot['history_complete_through'])
    required=set(snapshot.get('required_sources',[]))
    coverage={}
    for row in snapshot.get('coverage',[]):
        if row.get('complete') is True and (not row.get('available_at') or instant(row['available_at'])<=cutoff):
            coverage.setdefault(day(row['date']),set()).add(row.get('source_id'))
    dimensions=('person_id','team_id','project_id','configuration_id','meter','billing_pool')
    latest={}
    for row in snapshot.get('observations',[]):
        observed_day=day(row['date'])
        if not period_start<=observed_day<prefix_end or (row.get('available_at') and instant(row['available_at'])>cutoff):
            continue
        identity=row.get('observation_id',row.get('id',(row['date'],row.get('source_id'),tuple(row.get(k) for k in dimensions))))
        stamp=(row.get('available_at',''),str(row.get('revision',row.get('source_revision',''))))
        if identity not in latest or stamp>latest[identity][0]:
            latest[identity]=(stamp,row)
    # A partial observation makes that day partial even when a source-level
    # coverage row was incorrectly left marked complete.
    partial_days={day(row['date']) for _,row in latest.values() if row.get('complete') is not True or row.get('mature') is not True}
    records=[]
    for _,row in latest.values():
        observed_day=day(row['date'])
        matching=[tariff for tariff in snapshot.get('pricing',[]) if
                  tariff.get('billing_pool')==row.get('billing_pool') and
                  tariff.get('configuration_id') in (None,row.get('configuration_id')) and
                  tariff.get('meter') in (None,row.get('meter')) and
                  day(tariff.get('effective_from',tariff.get('period_start',snapshot['period_start'])))<=observed_day<
                  day(tariff.get('effective_to') or tariff.get('period_end',snapshot['period_end'])) and
                  (not tariff.get('known_at') or instant(tariff['known_at'])<=cutoff)]
        if len(matching)!=1:
            raise ValueError('fixture recorded usage has missing or ambiguous supported pricing')
        tariff=matching[0]
        try:
            rate=Decimal(str(tariff['rate']))
            quantity=Decimal(str(row['quantity']))
            valid_numbers=rate.is_finite() and quantity.is_finite() and rate==Decimal('0.000018') and quantity>=0
        except (KeyError,ValueError,TypeError,InvalidOperation) as exc:
            raise ValueError('fixture recorded usage has unknown quantity or tariff') from exc
        if (not valid_numbers or isinstance(row.get('quantity'),bool) or tariff.get('mode')!='linear' or
            tariff.get('complete_pool') is not True or tariff.get('currency')!='USD' or
            tariff.get('unit')!=row.get('meter') or row.get('meter')!='tokens' or
            tariff.get('allowance',0)!=0 or tariff.get('fixed',0)!=0 or tariff.get('tiers')):
            raise ValueError('fixture spending supports only complete linear USD/token tariff 0.000018 without allowances or fixed fees')
        amount=float(quantity*rate)
        if not math.isfinite(amount):
            raise ValueError('fixture recorded cost is nonfinite')
        identity=[row['date'],row.get('source_id'),row.get('source_revision',row.get('revision')),
                  *[row.get(k) for k in dimensions]]
        source_id=str(row.get('source_id','unknown'))
        record={'id':'fixture-spend-'+hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()[:20],
                'teamId':row.get('team_id') or 'unattributed','date':row['date'],'component':'api',
                'provider':'northstar-fixture','amount':amount,'unit':'usd','provenance':'estimate',
                'source':f"Synthetic Northstar observed usage {source_id} revision {row.get('source_revision',row.get('revision',1))}; "
                         f"estimate at supported tariff USD 0.000018/token; snapshot {snapshot.get('id')}",
                'complete':bool(required) and required<=coverage.get(observed_day,set()) and
                           observed_day<=complete_through and observed_day not in partial_days}
        if row.get('person_id') is not None:
            record['personId']=row['person_id']
        records.append(record)
    return sorted(records,key=lambda r:(r['date'],r['teamId'],r.get('personId',''),r['id']))
