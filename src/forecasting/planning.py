"""Frozen, JSON-native planning forecasts from versioned observations and evidence.

Scenario envelopes describe three common, jointly propagated configurations.
They are not prediction intervals. All amounts are planning allocations; unknown
coverage and unsupported tariffs remain explicit rather than becoming zero.
"""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import json
import math
import random

from .pricing import PricingContract, Tier, price_period

PROCEDURE_VERSION = 'driver-rate-weekblock-v1'
DIMENSIONS = ('person_id', 'team_id', 'project_id', 'configuration_id', 'meter', 'billing_pool')
BRANCHES = ('low', 'base', 'high')


def _day(value):
    return date.fromisoformat(str(value)[:10])


def _instant(value):
    parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed


def _days(start, end):
    return [start + timedelta(days=i) for i in range(max(0, (end-start).days))]


def _number(value):
    if isinstance(value, bool):
        raise ValueError('boolean is not a quantity')
    result = float(value)
    if not math.isfinite(result) or result < 0:
        raise ValueError('quantities and exposures must be finite and nonnegative')
    return result


def _key(row):
    return tuple(row.get(k) for k in DIMENSIONS)


def _matches(driver, component):
    return all(component.get(k) == v for k, v in driver.get('scope', {}).items() if k in DIMENSIONS)


def _active(driver, day):
    return _day(driver.get('effective_from', '0001-01-01')) <= day < _day(driver.get('effective_to') or '9999-12-31')


def _quantile(values, fraction):
    ordered = sorted(values)
    position = (len(ordered)-1)*fraction
    lower = int(position)
    upper = min(lower+1,len(ordered)-1)
    return ordered[lower]*(upper-position)+ordered[upper]*(position-lower) if upper!=lower else ordered[lower]


def _fit(snapshot, start, cutoff, limitations):
    """Fit weighted rates only on complete, available, mature observed days."""
    required = set(snapshot.get('required_sources', []))
    coverage = defaultdict(set)
    for row in snapshot.get('coverage', []):
        if row.get('complete') is True and (not row.get('available_at') or _instant(row['available_at']) <= cutoff):
            coverage[_day(row['date'])].add(row.get('source_id'))
    complete_through = _day(snapshot.get('history_complete_through', start-timedelta(days=1)))
    complete = {d for d, sources in coverage.items() if required and required <= sources and d <= complete_through}
    rows = []
    latest = {}
    for index, original in enumerate(snapshot.get('observations', [])):
        row = deepcopy(original)
        d = _day(row['date'])
        if d >= start or (row.get('available_at') and _instant(row['available_at']) > cutoff):
            continue
        row['quantity'] = _number(row['quantity'])
        exposure = row.get('exposure', row.get('work_units'))
        row['exposure'] = None if exposure is None else _number(exposure)
        if row['exposure'] == 0 and row['quantity'] > 0:
            row['exposure'] = None
        # An explicit observation identity supports append-only corrections.
        identity = row.get('observation_id', row.get('id', (row['date'],row.get('source_id'),_key(row))))
        stamp = (row.get('available_at',''),str(row.get('revision',row.get('source_revision',''))))
        if identity not in latest or stamp > latest[identity][0]:
            latest[identity] = (stamp,row)
    rows = [row for _,row in latest.values()]
    for row in rows:
        if row.get('complete') is not True or row.get('mature') is not True:
            complete.discard(_day(row['date']))
    grouped = defaultdict(list)
    for row in rows:
        grouped[_key(row)].append(row)
    declared={_key(c):c for c in snapshot.get('components',[])}
    for key in declared:grouped.setdefault(key,[])
    procedure=snapshot.get('procedure',{})
    train_days = sorted(d for d in complete if d < start)[-procedure.get('window_days',56):]
    # One resampling sequence is shared across every component and weekday.
    weeks = defaultdict(list)
    for d in train_days:
        weeks[d-timedelta(days=d.weekday())].append(d)
    full_weeks = sorted(w for w, ds in weeks.items() if len(ds)==7)
    seed = int(hashlib.sha256((str(snapshot.get('tenant_id',''))+'|'+str(start)+'|'+PROCEDURE_VERSION).encode()).hexdigest()[:16],16)
    rng = random.Random(seed)
    draws = [[rng.choice(full_weeks) for _ in full_weeks] for _ in range(200)] if len(full_weeks)>=4 else []
    fits = {}
    for key, component_rows in grouped.items():
        by_day = defaultdict(list)
        for row in component_rows:
            if _day(row['date']) in train_days:
                by_day[_day(row['date'])].append(row)
        has_exposure = bool(by_day) and all(r['exposure'] is not None and r.get('exposure_unit',snapshot.get('work_unit','work_units'))=='work_units' for rr in by_day.values() for r in rr)
        series = {}
        for d in train_days:
            rr = by_day[d]
            series[d] = (sum(r['quantity'] for r in rr), sum(r['exposure'] for r in rr) if has_exposure else 1.)
        def estimate(ds):
            quantity = sum(series[d][0] for d in ds)
            exposure = sum(series[d][1] for d in ds)
            return quantity/exposure if exposure else None
        overall = estimate(train_days)
        rates, exposures = {}, {}
        for weekday in range(7):
            ds = [d for d in train_days if d.weekday()==weekday]
            rate = estimate(ds)
            if rate is None:
                rate=overall
            exposure = (sum(series[d][1] for d in ds)/len(ds)) if ds and has_exposure else 1.
            if procedure.get('kind')=='seasonal_naive' and ds:
                latest_day=max(ds)
                quantity,last_exposure=series[latest_day]
                rate=quantity/last_exposure if last_exposure else 0.
                exposure=last_exposure
            reps=[]
            for draw in draws:
                sample=[w+timedelta(days=weekday) for w in draw]
                value=estimate(sample)
                if value is None:value=estimate([w+timedelta(days=i) for w in draw for i in range(7)])
                if value is not None:
                    reps.append(value)
            if procedure.get('kind')=='seasonal_naive':reps=[]
            if not component_rows:rate=None;reps=[]
            rates[weekday]={'base':rate,'low':_quantile(reps,.1) if reps else None,'high':_quantile(reps,.9) if reps else None}
            exposures[weekday]=exposure
        fits[key]={'component':dict(zip(DIMENSIONS,key)),'rates':rates,'exposures':exposures,'has_exposure':has_exposure,'complete_days':len(train_days),'bootstrap_replicates':200 if draws and procedure.get('kind')!='seasonal_naive' else 0,'full_weeks':len(full_weeks)}
        explicit=declared.get(key,{})
        if (has_exposure or not component_rows) and explicit.get('exposure_unit')=='work_units' and all(str(i) in explicit.get('exposure_by_weekday',{}) for i in range(7)):
            fits[key]['exposures']={i:_number(explicit['exposure_by_weekday'][str(i)]) for i in range(7)}
            fits[key]['has_exposure']=True
    # A declared new component never silently becomes zero. Borrow only when
    # recipient exposure is known and a compatible entity or explicit cohort
    # authorization supplies actual observed donor rates.
    authorizations=snapshot.get('authorized_cohorts',{})
    if not isinstance(authorizations,dict):
        raise ValueError('authorized_cohorts must be an explicit id-to-authorization mapping')
    for key,fit in fits.items():
        if all(rate['base'] is not None for rate in fit['rates'].values()):continue
        component=fit['component']
        if not fit['has_exposure']:
            limitations.add('Missing recipient exposure: compatible cohort rates cannot supply a workload assumption.')
            continue
        def compatible(other):
            return all(other.get(dim)==component.get(dim) for dim in ('configuration_id','meter','billing_pool'))
        donors=[k for k,f in fits.items() if k!=key and component.get('person_id') is not None and f['component'].get('person_id')==component.get('person_id') and compatible(f['component']) and f['has_exposure'] and grouped[k]]
        cohort_id='entity_overall' if donors else None
        if not donors:
            matches=[]
            for identifier,auth in authorizations.items():
                if auth.get('authorized') is not True or auth.get('exposure_unit')!='work_units':continue
                if not all(auth.get(dim)==component.get(dim) for dim in ('configuration_id','meter','billing_pool')):continue
                recipient=auth.get('recipient_scope');donor_scope=auth.get('donor_scope')
                if not isinstance(recipient,dict) or not recipient or not isinstance(donor_scope,dict) or not donor_scope:continue
                if any(dim not in DIMENSIONS for dim in list(recipient)+list(donor_scope)):continue
                if not _matches({'scope':recipient},component):continue
                candidates=[k for k,f in fits.items() if k!=key and compatible(f['component']) and f['has_exposure'] and grouped[k] and _matches({'scope':donor_scope},f['component'])]
                if candidates:matches.append((identifier,candidates))
            if len(matches)==1:cohort_id,donors=matches[0]
        if not donors:
            limitations.add('No unambiguous authorized compatible cohort for a declared component without an entity rate.')
            continue
        pooled={d:[0.,0.] for d in train_days}
        for donor in donors:
            for row in grouped[donor]:
                d=_day(row['date'])
                if d in pooled and row['exposure'] is not None:
                    pooled[d][0]+=row['quantity'];pooled[d][1]+=row['exposure']
        def pooled_rate(ds):
            exposure=math.fsum(pooled[d][1] for d in ds)
            return math.fsum(pooled[d][0] for d in ds)/exposure if exposure else None
        for weekday in range(7):
            if fit['rates'][weekday]['base'] is not None:continue
            ds=[d for d in train_days if d.weekday()==weekday]
            rate=pooled_rate(ds)
            if rate is None:rate=pooled_rate(train_days)
            reps=[]
            for draw in draws:
                value=pooled_rate([w+timedelta(days=weekday) for w in draw])
                if value is None:value=pooled_rate([w+timedelta(days=i) for w in draw for i in range(7)])
                reps.append(value)
            reps=[r for r in reps if r is not None]
            if procedure.get('kind')=='seasonal_naive':
                rate=pooled_rate([max(ds)]) if ds else None;reps=[]
            fit['rates'][weekday]={'base':rate,'low':_quantile(reps,.1) if reps else None,'high':_quantile(reps,.9) if reps else None}
        fit['cohort_id']=cohort_id
        fit['cohort_donors']=[dict(zip(DIMENSIONS,k)) for k in donors]
    if not draws:
        limitations.add('Fewer than four complete history weeks: descriptive scenario bounds unavailable.')
    if not required:
        limitations.add('No required source manifest: history coverage cannot be established.')
    if any(not f['has_exposure'] for f in fits.values()):
        limitations.add('Missing exposure: aggregate weekday continuation is used; workload, adoption and schedule effects are unavailable for affected components.')
    return fits, rows, complete


def _select_drivers(snapshot, drivers, fits, cutoff, limitations):
    candidates, queued = [], []
    superseded={d.get('supersedes') for d in drivers if d.get('supersedes') and (not d.get('available_at') or _instant(d['available_at'])<=cutoff)}
    for original in drivers:
        d=deepcopy(original)
        reason=None
        if d.get('id') in superseded:
            reason='Superseded by an available explicit replacement.'
        elif d.get('available_at') and _instant(d['available_at'])>cutoff:
            reason='Available after this publication information cutoff.'
        elif d.get('status')!='eligible':
            reason=d.get('reason') or 'Context only; no supported numerical effect.'
        elif d.get('kind') not in {'workload','membership','project_schedule','adoption','pricing'}:
            reason='Unsupported driver kind.'
        elif any(key not in DIMENSIONS for key in d.get('scope',{})):
            reason='Unsupported scope dimension; evidence cannot become a global effect.'
        else:
            p=d.get('parameters',{})
            def could_match(fit):
                if _matches(d,fit['component']):return True
                memberships=[m for m in snapshot.get('memberships',[]) if m.get('person_id')==fit['component'].get('person_id')]
                for other in drivers:
                    if other.get('kind')=='membership' and other.get('status')=='eligible' and _matches(other,fit['component']) and (not other.get('available_at') or _instant(other['available_at'])<=cutoff):
                        memberships.append(dict(other.get('parameters',{}),effective_from=other.get('effective_from'),effective_to=other.get('effective_to')))
                for member in memberships:
                    if member.get('team_id') is not None and _matches(d,dict(fit['component'],team_id=member['team_id'])):
                        return True
                return False
            affected=[f for f in fits.values() if could_match(f)]
            if not affected:
                reason='No compatible observed component; an authorized cohort is required.'
            elif d['kind'] in {'workload','adoption','project_schedule'} and any(not f['has_exposure'] for f in affected):
                reason='Missing exposure; context cannot change aggregate quantities.'
            elif d['kind']=='workload' and (p.get('unit')!='work_units' or 'exposure' not in p):
                reason='Workload needs absolute exposure in compatible work_units.'
            elif d['kind']=='membership' and 'team_id' not in p:
                reason='Membership needs an explicit destination team.'
            elif d['kind']=='adoption' and (not p.get('configuration_id') or 'share' not in p):
                reason='Adoption needs an absolute supported configuration share.'
            elif d['kind']=='project_schedule' and (not d.get('scope',{}).get('project_id') or not all(k in p for k in ('from_start','from_end','to_start'))):
                reason='Schedule needs identified project and source/destination dates.'
            elif d['kind']=='pricing' and not all(k in p for k in ('rate','currency','unit')):
                reason='Pricing needs complete supported absolute rate and units.'
            elif d['kind']=='pricing':
                tariffs=[t for t in snapshot.get('pricing',[]) if any(t.get('billing_pool')==f['component']['billing_pool'] for f in affected)]
                if any(key in d.get('scope',{}) for key in ('person_id','team_id','project_id')):
                    reason='A pool tariff cannot be replaced for a partial person/team/project subset.'
                elif not tariffs or any(t.get('mode','linear')!='linear' or t.get('allowance',0) or t.get('currency')!=p['currency'] or t.get('unit')!=p['unit'] for t in tariffs):
                    reason='Pricing replacement needs compatible supported linear pool tariffs.'
            if reason is None:
                try:
                    for name in ('exposure','exposure_low','exposure_high','rate','rate_low','rate_high','share','share_low','share_high'):
                        if name in p:_number(p[name])
                    for name in ('exposure','rate','share'):
                        if name in p and not _number(p.get(name+'_low',p[name]))<=_number(p[name])<=_number(p.get(name+'_high',p[name])):
                            raise ValueError('source bounds must surround the absolute base parameter')
                    if any(_number(p[name])>1 for name in ('share','share_low','share_high') if name in p):
                        raise ValueError('configuration shares must be in [0,1]')
                except (TypeError,ValueError):
                    reason='Nonfinite or unsupported magnitude.'
        if reason:
            d['publication_status']='excluded';d['publication_reason']=reason;queued.append(d)
            if 'exposure' in reason.lower():limitations.add(reason)
        else:candidates.append(d)
    conflicts=set()
    for i,a in enumerate(candidates):
        for b in candidates[i+1:]:
            if a['kind']!=b['kind']:
                continue
            overlap=max(_day(a.get('effective_from','0001-01-01')),_day(b.get('effective_from','0001-01-01'))) < min(_day(a.get('effective_to') or '9999-12-31'),_day(b.get('effective_to') or '9999-12-31'))
            scopes=any(_matches(a,f['component']) and _matches(b,f['component']) for f in fits.values())
            if overlap and scopes and (a.get('parameters')!=b.get('parameters') or a.get('scope')!=b.get('scope')):
                conflicts.update((a['id'],b['id']))
    accepted=[]
    seen=set()
    for d in candidates:
        if d['id'] in conflicts:
            d['publication_status']='excluded';d['publication_reason']='Conflicting overlapping absolute states need explicit supersession.';queued.append(d)
        else:
            token=(d['kind'],repr(sorted(d.get('scope',{}).items())),d.get('effective_from'),d.get('effective_to'),repr(sorted(d.get('parameters',{}).items())))
            if token in seen:
                d['publication_status']='excluded';d['publication_reason']='Duplicate absolute state.';queued.append(d)
            else:
                seen.add(token);d['publication_status']='included';accepted.append(d)
    return accepted,queued


def _parameter(parameters, name, branch):
    return _number(parameters.get(name+'_'+branch, parameters[name]))


def _quantity_paths(snapshot, fits, observed, complete, drivers, branch, start, period_start, end):
    entries=[]
    def state_at(fit,d):
        component=dict(fit['component'])
        exposure=fit['exposures'][d.weekday()]
        for membership in snapshot.get('memberships',[]):
            if membership.get('person_id') is not None and membership.get('person_id')==component['person_id'] and _active(membership,d):
                component['team_id']=membership.get('team_id')
                if 'exposure' in membership and fit['has_exposure']:
                    exposure=fit['exposures'][d.weekday()]*_number(membership['exposure'])
        for driver in drivers:
            if driver['kind']=='membership' and _matches(driver,fit['component']) and _active(driver,d):
                p=driver['parameters'];component['team_id']=p['team_id']
                if 'exposure' in p and fit['has_exposure']:
                    exposure=fit['exposures'][d.weekday()]*_parameter(p,'exposure',branch)
        return component,exposure
    for row in observed:
        d=_day(row['date'])
        if period_start<=d<start:
            entries.append(dict(date=d,component=dict(zip(DIMENSIONS,_key(row))),quantity=row['quantity'],recorded=True,fixed=False,recorded_amount=row.get('recorded_amount'),recorded_currency=row.get('recorded_currency')))
    for key,fit in fits.items():
        original=fit['component']
        daily={}
        for d in _days(start,end):
            rate=fit['rates'][d.weekday()][branch]
            if rate is None:rate=fit['rates'][d.weekday()]['base']
            component,exposure=state_at(fit,d)
            for driver in drivers:
                if not _matches(driver,component) or not _active(driver,d):continue
                p=driver['parameters']
                if driver['kind']=='workload':
                    affected=[state_at(f,d) for f in fits.values() if _matches(driver,state_at(f,d)[0])]
                    total=math.fsum(e for _,e in affected)
                    weight=exposure/total if total else 1/len(affected)
                    exposure=_parameter(p,'exposure',branch)*weight
            daily[d]={'date':d,'component':component,'quantity':0. if exposure==0 else None if rate is None else rate*exposure,'recorded':False,'fixed':False}
        # Move existing future workload one-to-one; no arbitrary count multiplier.
        for driver in drivers:
            if driver['kind']!='project_schedule' or not _matches(driver,original):continue
            p=driver['parameters'];a,b,c=_day(p['from_start']),_day(p['from_end']),_day(p['to_start'])
            moved=[]
            for d in _days(a,b):
                if d in daily and _active(driver,d):
                    destination=c+(d-a)
                    moved.append((destination,daily[d]['quantity']))
                    daily[d]['quantity']=0.
            for destination,quantity in moved:
                if destination in daily:
                    daily[destination]['quantity']=None if quantity is None or daily[destination]['quantity'] is None else daily[destination]['quantity']+quantity
        for d,row in daily.items():
            remaining=row['quantity'];adopted=[]
            for driver in drivers:
                if driver['kind']!='adoption' or not _matches(driver,row['component']) or not _active(driver,d):continue
                p=driver['parameters'];share=_parameter(p,'share',branch)
                component=dict(row['component']);component['configuration_id']=p['configuration_id']
                if p.get('billing_pool'):component['billing_pool']=p['billing_pool']
                adopted.append(dict(row,component=component,quantity=None if remaining is None else remaining*share))
                remaining=None if remaining is None else remaining*(1-share)
            entries.append(dict(row,quantity=remaining));entries.extend(adopted)
    return entries


def _price(snapshot, entries, complete, drivers, branch, start, period_start, end, cutoff, limitations):
    currency=snapshot.get('target',{}).get('unit','USD')
    quantity_target=snapshot.get('target',{}).get('quantity') in ('usage','quantity','tokens')
    output=[]
    missing_prefix=set(_days(period_start,min(start,end)))-complete
    if missing_prefix:
        limitations.add('Missing required source/day coverage in recorded quarter prefix; late usage is unknown and quarter total is incomplete.')
    if quantity_target:
        return [dict(row,amount=row['quantity']) for row in entries], missing_prefix
    tariffs=snapshot.get('pricing',[])
    groups=defaultdict(list)
    for row in entries:
        component=row['component'];d=row['date']
        if row['recorded'] and row.get('recorded_amount') is not None and row.get('recorded_currency')==currency and str(component.get('meter','')).lower()==currency.lower():
            output.append(dict(row,amount=_number(row['recorded_amount'])))
            continue
        matching=[]
        for tariff in tariffs:
            if tariff.get('billing_pool')!=component.get('billing_pool'):continue
            if tariff.get('configuration_id') not in (None,component.get('configuration_id')):continue
            if tariff.get('meter') not in (None,component.get('meter')):continue
            if not (_day(tariff.get('effective_from',tariff.get('period_start',period_start)))<=d<_day(tariff.get('effective_to') or tariff.get('period_end',end))):continue
            if tariff.get('known_at') and _instant(tariff['known_at'])>cutoff:continue
            matching.append(tariff)
        if len(matching)!=1:
            limitations.add('Missing or ambiguous supported pricing for a complete billing pool.')
            output.append(dict(row,amount=None));continue
        tariff=matching[0]
        if tariff.get('complete_pool') is not True or tariff.get('currency')!=currency or tariff.get('unit')!=component.get('meter'):
            limitations.add('Incomplete billing pool or incompatible pricing currency/unit: spend unavailable.')
            output.append(dict(row,amount=None));continue
        identity=(tariff.get('id'),tariff.get('version'),tariffs.index(tariff))
        groups[identity].append((row,tariff))
    for grouped in groups.values():
        tariff=grouped[0][1];pool=[row for row,_ in grouped]
        mode=tariff.get('mode','linear')
        nonlinear=mode!='linear' or bool(tariff.get('allowance',0))
        if mode not in ('linear','graduated','volume'):
            limitations.add('Unsupported tariff terms: spend unavailable.')
            output.extend(dict(row,amount=None) for row in pool);continue
        if nonlinear:
            limitations.add('Nonlinear full-pool pricing uses proportional quantity allocation; near-term amounts depend on conditional quarter tail.')
            exact_period=_day(tariff.get('period_start',period_start))==period_start and _day(tariff.get('period_end',end))==end
            if missing_prefix or not exact_period or any(row['quantity'] is None for row in pool):
                limitations.add('Nonlinear tariff needs complete matching billing-period prefix and tail.')
                output.extend(dict(row,amount=None) for row in pool);continue
            try:
                contract=PricingContract(str(tariff.get('id','tariff')),str(tariff.get('version','1')),currency,tariff['unit'],period_start,end,cutoff,allowance=Decimal(str(tariff.get('allowance',0))),rate=Decimal(str(tariff.get('rate',0))),fixed=Decimal(0),mode=mode,tiers=tuple(Tier(None if t.get('up_to') is None else Decimal(str(t['up_to'])),Decimal(str(t['rate']))) for t in tariff.get('tiers',[])))
                total=sum(row['quantity'] for row in pool)
                amount=float(price_period(contract,{}, {'pool':Decimal(str(total))}).variable_total)
                factor=amount/total if total else 0.
                output.extend(dict(row,amount=row['quantity']*factor) for row in pool)
            except (ValueError,TypeError,ArithmeticError):
                limitations.add('Invalid supported tariff: spend unavailable.')
                output.extend(dict(row,amount=None) for row in pool)
        else:
            for row in pool:
                rate=_number(tariff.get('rate',0))
                for driver in drivers:
                    if driver['kind']=='pricing' and not row['recorded'] and _matches(driver,row['component']) and _active(driver,row['date']):
                        p=driver['parameters']
                        if p['currency']==currency and p['unit']==tariff['unit']:rate=_parameter(p,'rate',branch)
                        else:
                            rate=None;limitations.add('Pricing evidence has incompatible units or currency.')
                output.append(dict(row,amount=None if row['quantity'] is None or rate is None else row['quantity']*rate))
    # Fixed contractual obligations exist independently of metered usage.
    fixed_contracts=defaultdict(list)
    for tariff in tariffs:
        fixed_date=_day(tariff.get('period_start',period_start))
        if not period_start<=fixed_date<end:continue
        if tariff.get('known_at') and _instant(tariff['known_at'])>cutoff:continue
        if tariff.get('fixed',0)==0 and tariff.get('fixed_known',True):continue
        identity=(tariff.get('billing_pool'),tariff.get('configuration_id'),tariff.get('meter'),str(fixed_date),tariff.get('period_end'))
        fixed_contracts[identity].append(tariff)
    for identity,contracts in fixed_contracts.items():
        tariff=contracts[0];fixed_date=_day(identity[3])
        supported=len(contracts)==1 and tariff.get('currency')==currency and tariff.get('mode','linear') in ('linear','graduated','volume') and tariff.get('fixed_known',True) and tariff.get('fixed') is not None
        fixed=_number(tariff['fixed']) if supported else None
        if not supported:limitations.add('Unknown, ambiguous or unsupported fixed obligation: all-in quarter total incomplete.')
        output.append({'date':fixed_date,'component':dict(zip(DIMENSIONS,(None,None,None,None,None,tariff.get('billing_pool')))),'quantity':0.,'amount':fixed,'recorded':fixed_date<start,'fixed':True})
    if snapshot.get('fixed_obligations_unknown'):
        limitations.add('Fixed obligations are unknown: all-in quarter total incomplete.')
        output.append({'date':period_start,'component':dict.fromkeys(DIMENSIONS),'quantity':0.,'amount':None,'recorded':period_start<start,'fixed':True})
    return output,missing_prefix


def _scope_matches(row, kind, scope_id):
    c=row['component']
    if kind=='company':return True
    if kind=='person':return c['person_id']==scope_id
    if kind=='team':return c['team_id']==scope_id
    if scope_id=='people_unallocated':return c['person_id'] is None and c['team_id'] is not None
    if scope_id=='teams_unallocated':return c['team_id'] is None and c['person_id'] is not None
    return c['person_id'] is None and c['team_id'] is None


def _sum(rows):
    return None if any(row['amount'] is None for row in rows) else math.fsum(row['amount'] for row in rows)


def _view(snapshot, priced, missing_prefix, fits, drivers, queued, limitations, run_id, generated_at, scope, start, period_start, end):
    kind,scope_id,name=scope
    selected={branch:[row for row in priced[branch] if _scope_matches(row,kind,scope_id)] for branch in BRANCHES}
    rate_bounds=bool(fits) and all(fit['bootstrap_replicates']==200 and all(rate['low'] is not None and rate['high'] is not None for rate in fit['rates'].values()) for fit in fits.values())
    source_bounds=[{'driver_id':d['id'],'parameter':name} for d in drivers for name in ('exposure','rate','share') if name+'_low' in d.get('parameters',{}) and name+'_high' in d.get('parameters',{})]
    bounds=rate_bounds or bool(source_bounds)
    if source_bounds and not rate_bounds:
        limitations.add('Source-stated driver bounds are conditional on point observed rates; rate bounds unavailable, so the scenario envelope is incomplete.')
    def point(a,b, **extras):
        rows={branch:[r for r in selected[branch] if a<=r['date']<b] for branch in BRANCHES}
        totals={branch:_sum(rr) for branch,rr in rows.items()}
        if not fits or any(a<=d<b for d in missing_prefix):totals={branch:None for branch in BRANCHES}
        base=totals['base'];available=bounds and all(x is not None for x in totals.values())
        return dict(start=str(a),end=str(b),base=base,low=min(totals.values()) if available else None,high=max(totals.values()) if available else None,configuration_values={branch:totals[branch] if branch=='base' or available else None for branch in BRANCHES},complete=base is not None,recorded=_sum([r for r in rows['base'] if r['recorded']]),future=_sum([r for r in rows['base'] if not r['recorded']]),**extras)
    monday=start-timedelta(days=start.weekday())
    daily=[point(d,d+timedelta(days=1),date=str(d)) for d in _days(start,start+timedelta(days=7))]
    weekly=[point(max(start,monday+timedelta(days=7*i)),monday+timedelta(days=7*(i+1)),label='Week '+str(i+1),calendar_start=str(monday+timedelta(days=7*i)),partial=i==0 and start!=monday) for i in range(4)]
    cumulative=[point(period_start,d+timedelta(days=1),date=str(d)) for d in _days(start,min(end,monday+timedelta(days=28)))]
    quarter=point(period_start,end,label='Conditional quarter continuation',assumptions=['Near-term paths are preserved; weekday rates and exposure continue to quarter end.','Only supported effective-dated schedule, membership, workload, adoption and pricing evidence changes continuation.'])
    recorded=_sum([r for r in selected['base'] if r['recorded'] and not r['fixed'] and r['date']<end])
    future=_sum([r for r in selected['base'] if not r['recorded'] and not r['fixed'] and r['date']<end])
    fixed=_sum([r for r in selected['base'] if r['fixed'] and r['date']<end])
    applicable=[deepcopy(d) for d in drivers if kind=='company' or any(_matches(d,row['component']) for row in selected['base'])]
    return dict(id=run_id+':'+kind+':'+str(scope_id),run_id=run_id,snapshot_id=snapshot.get('id'),scope={'type':kind,'id':scope_id,'name':name},target=deepcopy(snapshot.get('target',{'unit':'USD','quantity':'spend','basis':'planning','timezone':'UTC'})),timezone='UTC',procedure_version=PROCEDURE_VERSION,procedure_id=PROCEDURE_VERSION,history_delay_days=(start-_day(snapshot.get('history_complete_through',start-timedelta(days=1)))).days-1,publication={'generated_at':generated_at,'information_cutoff':snapshot['information_cutoff'],'history_complete_through':snapshot.get('history_complete_through'),'forecast_start':str(start)},components={'recorded':recorded,'late':None if missing_prefix else 0.,'future':future,'fixed':fixed},daily=daily,weekly=weekly,cumulative=cumulative,quarter_outlook=quarter,included_drivers=applicable,queued_changes=deepcopy(queued),limitations=sorted(limitations),explanation_refs=['calculation:rates','calculation:pricing']+['driver:'+d['id'] for d in applicable],scenario_range={'type':'descriptive_scenario_envelope','available':bounds,'complete':rate_bounds,'conditional_on_base_rates':bool(source_bounds) and not rate_bounds,'source_parameter_bounds':source_bounds,'rate_bounds_available':rate_bounds,'label':'Low / base / high planning configurations; not a confidence interval','bootstrap_replicates':200 if rate_bounds else 0,'rate_parameters':'week-block P10 / exposure-weighted mean / P90','coverage_probability':None},historical_error_interval=None)


def build_forecast(snapshot: dict, *, run_id: str, generated_at: str, drivers=None) -> dict:
    """Create immutable company/team/person/shared views from one frozen snapshot.

    Caller persists the returned JSON and never rebases it on subsequently arriving
    actuals. ``drivers`` is an isolated complete scenario replacement, not mutation.
    """
    snapshot=deepcopy(snapshot)
    procedure=snapshot.get('procedure',{})
    if procedure.get('kind','driver_rate') not in ('driver_rate','seasonal_naive') or procedure.get('window_days',56) not in (28,56):
        raise ValueError('Unsupported forecasting procedure configuration')
    procedure_id=procedure.get('id',PROCEDURE_VERSION)
    if snapshot.get('target',{}).get('timezone','UTC')!='UTC':
        raise ValueError('Only UTC daily targets are supported')
    start=_day(snapshot['forecast_start']);period_start=_day(snapshot['period_start']);end=_day(snapshot['period_end'])
    if not period_start<=start<end:raise ValueError('Forecast start must be within the quarter')
    cutoff=_instant(snapshot['information_cutoff'])
    limitations=set(snapshot.get('limitations',[]))
    fits,observed,complete=_fit(snapshot,start,cutoff,limitations)
    selected,queued=_select_drivers(snapshot,list(snapshot.get('drivers',[]) if drivers is None else drivers),fits,cutoff,limitations)
    if snapshot.get('is_synthetic'):
        limitations.add('Synthetic fixture; forecast behavior is demonstrable, enterprise accuracy is unvalidated.')
    if not fits:limitations.add('No compatible complete observed history; forecast unavailable.')
    def run(active):
        paths={};missing=set()
        horizon_end=max(end,start-timedelta(days=start.weekday())+timedelta(days=28),start+timedelta(days=7))
        for branch in BRANCHES:
            entries=_quantity_paths(snapshot,fits,observed,complete,active,branch,start,period_start,horizon_end)
            paths[branch],missing=_price(snapshot,entries,complete,active,branch,start,period_start,end,cutoff,limitations)
        return paths,missing
    priced,missing=run(selected)
    people={row.get('id'):row.get('name',row.get('id')) for row in snapshot.get('people',[])}
    person_ids={r['component']['person_id'] for r in priced['base'] if r['component']['person_id'] is not None}|set(people)
    team_ids={r['component']['team_id'] for r in priced['base'] if r['component']['team_id'] is not None}
    team_names={row.get('id'):row.get('name',row.get('id')) for row in snapshot.get('teams',[])}
    scopes=[('company',snapshot.get('tenant_id','company'),snapshot.get('name',snapshot.get('tenant_id','Company')))]+[('team',x,team_names.get(x,x)) for x in sorted(team_ids)]+[('person',x,people.get(x,x)) for x in sorted(person_ids)]+[('shared','shared','Shared / unallocated')]
    if any(r['component']['person_id'] is None and r['component']['team_id'] is not None for r in priced['base']):
        scopes.append(('shared','people_unallocated','Team usage without person attribution'))
    if any(r['component']['team_id'] is None and r['component']['person_id'] is not None for r in priced['base']):
        scopes.append(('shared','teams_unallocated','Person usage without team attribution'))
    views=[_view(snapshot,priced,missing,fits,selected,queued,limitations,run_id,generated_at,scope,start,period_start,end) for scope in scopes]
    for view in views:
        view['procedure_id']=procedure_id
        view['procedure_version']=procedure_id
        view['procedure']=dict(kind=procedure.get('kind','driver_rate'),window_days=procedure.get('window_days',56),id=procedure_id)
        view['is_synthetic']=bool(snapshot.get('is_synthetic',False))
        kind=view['scope']['type'];identity=view['scope']['id']
        view['rollup_partitions']=(['people','teams'] if identity=='shared' else ['people'] if identity=='people_unallocated' else ['teams']) if kind=='shared' else ['people'] if kind=='person' else ['teams'] if kind=='team' else []
    views[0]['reconciliation']={partition:{'scope_ids':[v['id'] for v in views if partition in v['rollup_partitions']]} for partition in ('people','teams')}
    effects=[]
    for view in views:view['driver_effects']=[]
    with_base=views[0]['quarter_outlook']['base']
    for driver in selected:
        omitted,_=run([d for d in selected if d['id']!=driver['id']])
        for view in views:
            scope=view['scope'];with_base=view['quarter_outlook']['base']
            without_base=None if missing else _sum([r for r in omitted['base'] if r['date']<end and _scope_matches(r,scope['type'],scope['id'])])
            available=with_base is not None and without_base is not None
            effect={'driver_id':driver['id'],'scope':{'type':scope['type'],'id':scope['id']},'with_base':with_base,'without_base':without_base,'base_delta':with_base-without_base if available else None,'available':available,'qualification':'Paired omission with identical history and bootstrap draws; interacting effects need not add.'}
            for bucket in ('daily','weekly'):
                effect[bucket]=[]
                for point in view[bucket]:
                    a,b=_day(point['start']),_day(point['end'])
                    counterfactual=None if any(a<=d<b for d in missing) else _sum([r for r in omitted['base'] if a<=r['date']<b and _scope_matches(r,scope['type'],scope['id'])])
                    effect[bucket].append({'start':point['start'],'end':point['end'],'with_base':point['base'],'without_base':counterfactual,'base_delta':point['base']-counterfactual if point['base'] is not None and counterfactual is not None else None})
            view['driver_effects'].append(effect)
            if scope['type']=='company':effects.append(effect)
    calculations=[{'id':'calculation:rates','method':'Trailing 56 complete UTC days; exposure-weighted weekday rates, entity overall fallback; aggregate continuation when exposure absent.','bootstrap':{'replicates':200,'block':'complete Monday–Sunday week','seed_identity':str(snapshot.get('tenant_id'))+'|'+str(start)+'|'+PROCEDURE_VERSION},'components':[dict(component=f['component'],complete_days=f['complete_days'],full_weeks=f['full_weeks'],has_exposure=f['has_exposure'],rates=f['rates'],exposures=f['exposures'],cohort_id=f.get('cohort_id'),cohort_donors=f.get('cohort_donors',[])) for f in fits.values()]},{'id':'calculation:pricing','method':'Supported complete pool tariffs applied before scope aggregation; nonlinear quantity-proportional allocation discloses conditional tail dependency.'}]+[dict(effect,id='driver:'+effect['driver_id']) for effect in effects]
    calculations[0]['procedure']=dict(id=procedure_id,kind=procedure.get('kind','driver_rate'),window_days=procedure.get('window_days',56))
    calculations[0]['method']='Latest '+str(procedure.get('window_days',56))+' complete UTC days; '+('last complete matching weekday observation' if procedure.get('kind')=='seasonal_naive' else 'exposure-weighted weekday rate, entity overall then explicitly authorized compatible cohort fallback')+'. Aggregate continuation when compatible exposure is absent.'
    calculations[0]['bootstrap']['replicates']=max((f['bootstrap_replicates'] for f in fits.values()),default=0)
    calculations[0]['source_revisions']=deepcopy(snapshot.get('source_revisions',{}))
    calculations[0]['snapshot_id']=snapshot.get('id')
    calculations[0]['information_cutoff']=snapshot['information_cutoff']
    result={'schema_version':1,'run_id':run_id,'snapshot_id':snapshot.get('id'),'procedure_version':procedure_id,'views':views,'calculations':calculations,'driver_effects':effects}
    return json.loads(json.dumps(result,allow_nan=False))
