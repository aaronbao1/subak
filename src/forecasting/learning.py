"""Versioned issued-target learning; only observed, mature truth creates errors.

JSON records are immutable values. Persistence owns append-only storage. Intervals
are historical-error rank intervals, with exchangeability explicitly unproven.
"""
from __future__ import annotations
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
from types import MappingProxyType

from .evaluation import interval_metrics, weighted_interval_score

STRATUM = ('lead_days','duration_days','aggregation','scope_type','scope_id','unit',
           'basis','timezone','procedure_id','history_delay_days','implementation_sha256')
QUALIFICATION = ('Historical error interval conditional on a frozen procedure and exchangeable '
                 'matching mature errors; time-series coverage is not guaranteed. Synthetic '
                 'fixtures demonstrate mechanics only, never enterprise accuracy.')


def _time(value):
    value = datetime.fromisoformat(value.replace('Z','+00:00')) if isinstance(value,str) else value
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError('timezone-aware timestamp required')
    return value.astimezone(timezone.utc)


def _day(value):
    return date.fromisoformat(value[:10]) if isinstance(value,str) else value


def _finite(value):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
        raise ValueError('finite numerical value required')
    return value


def _procedure_dependencies(value=None):
    if value is None: return {}
    if not isinstance(value,dict) or any(not isinstance(key,str) or not key for key in value):
        raise ValueError('procedure dependency manifest must be a string-keyed mapping')
    # Canonical JSON is an explicit backend-independent version contract.
    return json.loads(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False))


def _implementation_digest(procedure_dependencies=None):
    root=Path(__file__).parent
    names=('planning.py','learning.py','pricing.py','evaluation.py','commercial.py','contracts.py')
    digest=hashlib.sha256()
    for name in names:
        digest.update(name.encode()); digest.update((root/name).read_bytes())
    manifest=_procedure_dependencies(procedure_dependencies)
    digest.update(b'procedure_dependencies:')
    digest.update(json.dumps(manifest,sort_keys=True,separators=(',',':'),allow_nan=False).encode())
    return digest.hexdigest()


def _digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def _validate_target(row):
    for key in STRATUM + ('target_id','run_id','issued_at','origin','start','end','prediction'):
        if key not in row and key!='implementation_sha256':
            raise ValueError('target missing '+key)
    _finite(row['prediction'])
    start,end,origin = (_day(row[k]) for k in ('start','end','origin'))
    if end<=start or (end-start).days!=row['duration_days'] or (start-origin).days!=row['lead_days']:
        raise ValueError('target dates do not match duration/lead')
    if row['timezone']!='UTC' or row['history_delay_days']<0:
        raise ValueError('UTC targets and nonnegative history delay required')
    _time(row['issued_at'])


def archive_issued_targets(bundle, snapshot):
    """Archive exactly final priced bases; unavailable points are not predictions."""
    result=[]
    manifest=snapshot.get('id') or _digest(snapshot)
    policy=snapshot.get('model_registry',{}).get('policy',{})
    dependencies=_procedure_dependencies(snapshot.get('procedure_dependencies'))
    implementation=_implementation_digest(dependencies)
    for view in bundle.get('views',[bundle]):
        publication=view['publication']
        origin=publication['forecast_start']
        delay=(_day(origin)-_day(publication['history_complete_through'])).days
        for aggregation in ('daily','weekly','cumulative'):
            for point in view.get(aggregation,[]):
                if point.get('base') is None or not point.get('complete',True):
                    continue
                start=point.get('start',point.get('date'))
                end=point.get('end',(_day(start)+timedelta(days=1)).isoformat())
                identity=[view['run_id'],view['scope']['type'],view['scope']['id'],aggregation,start,end]
                row=dict(target_id=_digest(identity),run_id=view['run_id'],issued_at=publication['generated_at'],
                         origin=origin,start=start,end=end,lead_days=(_day(start)-_day(origin)).days,
                         duration_days=(_day(end)-_day(start)).days,aggregation=aggregation,
                         scope_type=view['scope']['type'],scope_id=view['scope']['id'],
                         unit=view['target']['unit'],quantity=view['target'].get('quantity'),basis=view['target'].get('basis','planning'),
                         timezone=view.get('timezone','UTC'),procedure_id=view.get('procedure_id',view.get('procedure_version')),
                         history_delay_days=view.get('history_delay_days',delay),prediction=point['base'],
                         is_synthetic=bool(snapshot.get('is_synthetic',False)))
                row.update(implementation_sha256=implementation,procedure_dependencies=deepcopy(dependencies),effective_procedure_id=str(row['procedure_id'])+'@'+implementation,snapshot_id=snapshot.get('id'),input_manifest=manifest,policy_id=policy.get('policy_id'),information_cutoff=publication.get('information_cutoff',snapshot.get('information_cutoff')))
                if point.get('historical_error_interval'):
                    row['intervals']=deepcopy(point['historical_error_interval'])
                _validate_target(row)
                result.append(row)
    return result


def _matched(target,issued,truth_revisions,cutoff, *, before_target=True):
    cutoff=_time(cutoff)
    _validate_target(target)
    inventory={}
    for row in issued:
        _validate_target(row)
        identity=row['target_id']
        if identity in inventory and inventory[identity]!=row:
            raise ValueError('issued target identity changed')
        inventory[identity]=row
    versions={}; latest={}
    for row in truth_revisions:
        if not isinstance(row['revision'],int) or row['revision']<1 or row['status'] not in ('mature','pending','disputed'):
            raise ValueError('invalid truth revision/status')
        _finite(row['value'])
        available,mature=_time(row['available_at']),_time(row['mature_at'])
        if available>mature:
            raise ValueError('truth maturity precedes availability')
        original=inventory.get(row['target_id'])
        if original and mature.date()<_day(original['end']):
            raise ValueError('truth matures before target end')
        key=(row['target_id'],row['revision'])
        if key in versions and versions[key]!=row:
            raise ValueError('conflicting truth revision')
        versions[key]=row
        if available<=cutoff and (row['target_id'] not in latest or row['revision']>latest[row['target_id']]['revision']):
            latest[row['target_id']]=row
    eligible=[]
    for identity,row in inventory.items():
        truth=latest.get(identity)
        if any(row.get(k)!=target.get(k) for k in STRATUM) or _time(row['issued_at'])>cutoff:
            continue
        if bool(row.get('is_synthetic',False)) != bool(target.get('is_synthetic',False)):
            continue
        if truth and bool(truth.get('is_synthetic',False)) != bool(target.get('is_synthetic',False)):
            continue
        if not truth or truth['status']!='mature' or _time(truth['mature_at'])>cutoff:
            continue
        if _day(row['end'])>cutoff.date() or (before_target and _day(row['end'])>_day(target['start'])):
            continue
        eligible.append((row,truth))
    # Earliest finishing interval, with earliest publication then stable ID ties.
    # Deterministic maximal nonoverlapping subset; input/retry order is irrelevant.
    eligible.sort(key=lambda pair:(pair[0]['end'],pair[0]['start'],pair[0]['issued_at'],pair[0]['target_id']))
    selected=[]; end=None
    for pair in eligible:
        if end is None or pair[0]['start']>=end:
            selected.append(pair); end=pair[0]['end']
    return selected,len(eligible)-len(selected)


def historical_error_interval(target, issued, truth_revisions, *, cutoff, coverage=.8):
    if coverage not in (.8,.95):
        raise ValueError('supported coverage levels are 0.8 and 0.95')
    rows,excluded=_matched(target,issued,truth_revisions,cutoff)
    return _interval_from_matches(target,rows,excluded,coverage)


def _interval_from_matches(target,rows,excluded,coverage):
    n=len(rows)
    rank=math.ceil((n+1)*Fraction(str(coverage)))
    errors=sorted(abs(_finite(t['value']-r['prediction'])) for r,t in rows)
    available=rank<=n
    width=errors[rank-1] if available else None
    lower=_finite(target['prediction']-width) if available else None
    upper=_finite(target['prediction']+width) if available else None
    scored=[]
    for issued_row,truth in rows:
        intervals=issued_row.get('intervals',{})
        level=intervals.get(str(int(coverage*100)),{})
        if level.get('lower') is not None and level.get('upper') is not None:
            scored.append((level['lower'],level['upper'],truth['value']))
    metrics=interval_metrics([x[0] for x in scored],[x[1] for x in scored],[x[2] for x in scored],float(1-Fraction(str(coverage))))
    paired=[(r,t) for r,t in rows if all(r.get('intervals',{}).get(level,{}).get(bound) is not None for level in ('80','95') for bound in ('lower','upper'))]
    metrics['wis']=weighted_interval_score([r['prediction'] for r,_ in paired],{alpha:([r['intervals'][level]['lower'] for r,_ in paired],[r['intervals'][level]['upper'] for r,_ in paired]) for level,alpha in [('80',.2),('95',.05)]},[t['value'] for _,t in paired]) if paired else None
    metrics['wis_count']=len(paired)
    return dict(kind='historical_error_interval',status='available_assumption_conditional' if available else 'insufficient_evidence',
                lower=lower,upper=upper,coverage=coverage,n=n,rank=rank,excluded_overlap=excluded,
                calibration_start=min((r['start'] for r,_ in rows),default=None),calibration_end=max((r['end'] for r,_ in rows),default=None),
                target_ids=[r['target_id'] for r,_ in rows],truth_revisions=[{'target_id':r['target_id'],'revision':t['revision']} for r,t in rows],
                stratum={key:target.get(key) for key in STRATUM},empirical=metrics,
                is_synthetic=any(r.get('is_synthetic') or t.get('is_synthetic') for r,t in rows) or target.get('is_synthetic',False),
                qualification=QUALIFICATION)


def _validated_interval_history(issued,truth_revisions):
    """Validate the entire archive once; retain read-only per-call lookup data.

    Keep the validation order and duplicate rules of ``_matched`` even for
    unrelated or future evidence. Records are immutable JSON values owned by
    the snapshot; neither this index nor its consumers modify those records.
    """
    inventory={}
    for row in issued:
        _validate_target(row)
        identity=row['target_id']
        if identity in inventory and inventory[identity]!=row:
            raise ValueError('issued target identity changed')
        inventory[identity]=row
    versions={}; truths=[]
    for row in truth_revisions:
        if not isinstance(row['revision'],int) or row['revision']<1 or row['status'] not in ('mature','pending','disputed'):
            raise ValueError('invalid truth revision/status')
        _finite(row['value'])
        available,mature=_time(row['available_at']),_time(row['mature_at'])
        if available>mature:
            raise ValueError('truth maturity precedes availability')
        original=inventory.get(row['target_id'])
        if original and mature.date()<_day(original['end']):
            raise ValueError('truth matures before target end')
        key=(row['target_id'],row['revision'])
        if key in versions and versions[key]!=row:
            raise ValueError('conflicting truth revision')
        versions[key]=row
        truths.append((row,available,mature))
    return (tuple((row,_time(row['issued_at']),_day(row['end'])) for row in inventory.values()),
            tuple(truths))


def _interval_stratum_key(target):
    key=tuple(target.get(k) for k in STRATUM)+(bool(target.get('is_synthetic',False)),)
    try:
        hash(key)
    except TypeError:
        # Legacy validation permits unhashable stratum values. Keep these in a
        # fallback bucket, still comparing with the original equality rules.
        return None
    return key


def _interval_history_at(history,cutoff):
    """Index eligible latest truth by exact stratum at one publication cutoff."""
    inventory,truths=history
    latest={}
    for truth,available,mature in truths:
        identity=truth['target_id']
        if available<=cutoff and (identity not in latest or truth['revision']>latest[identity][0]['revision']):
            latest[identity]=(truth,mature)
    groups={}
    for row,issued_at,end in inventory:
        version=latest.get(row['target_id'])
        if issued_at>cutoff or end>cutoff.date() or version is None:
            continue
        truth,mature=version
        if truth['status']!='mature' or mature>cutoff:
            continue
        if bool(truth.get('is_synthetic',False))!=bool(row.get('is_synthetic',False)):
            continue
        groups.setdefault(_interval_stratum_key(row),[]).append((row,truth,end))
    return MappingProxyType({key:tuple(sorted(rows,key=lambda item:(item[0]['end'],item[0]['start'],item[0]['issued_at'],item[0]['target_id'])))
                             for key,rows in groups.items()})


def _matched_interval_history(target,groups):
    key=_interval_stratum_key(target)
    candidates=(tuple(item for rows in groups.values() for item in rows) if key is None
                else groups.get(key,())+groups.get(None,()))
    start=_day(target['start'])
    eligible=[(row,truth) for row,truth,end in candidates if end<=start
              and not any(row.get(k)!=target.get(k) for k in STRATUM)
              and bool(row.get('is_synthetic',False))==bool(target.get('is_synthetic',False))]
    # Normal buckets are already sorted. A fallback bucket may interleave rows.
    if key is None or None in groups:
        eligible.sort(key=lambda pair:(pair[0]['end'],pair[0]['start'],pair[0]['issued_at'],pair[0]['target_id']))
    selected=[]; end=None
    for pair in eligible:
        if end is None or pair[0]['start']>=end:
            selected.append(pair); end=pair[0]['end']
    return selected,len(eligible)-len(selected)


def enrich_intervals(bundle,snapshot):
    """Add per-target 80/95 intervals before publication, without changing bases."""
    result=deepcopy(bundle)
    dependencies=_procedure_dependencies(snapshot.get('procedure_dependencies'))
    implementation=_implementation_digest(dependencies)
    result['implementation_sha256']=implementation
    result['procedure_dependencies']=deepcopy(dependencies)
    base_procedure=result.get('procedure_id',result.get('procedure_version'))
    if base_procedure is not None: result['effective_procedure_id']=str(base_procedure)+'@'+implementation
    targets=archive_issued_targets(result,snapshot)
    indexed={(r['run_id'],r['scope_type'],r['scope_id'],r['aggregation'],r['start'],r['end']):r for r in targets}
    history=None; history_by_cutoff={}
    for view in result.get('views',[result]):
        view['implementation_sha256']=implementation
        view['procedure_dependencies']=deepcopy(dependencies)
        view['effective_procedure_id']=str(view.get('procedure_id',view.get('procedure_version')))+'@'+implementation
        for aggregation in ('daily','weekly','cumulative'):
            for point in view.get(aggregation,[]):
                key=(view['run_id'],view['scope']['type'],view['scope']['id'],aggregation,point.get('start',point.get('date')),point.get('end'))
                target=indexed.get(key)
                if target:
                    cutoff=_time(view['publication'].get('information_cutoff',view['publication']['generated_at']))
                    if history is None:
                        history=_validated_interval_history(snapshot.get('issued_targets',[]),snapshot.get('truth_revisions',[]))
                    if cutoff not in history_by_cutoff:
                        history_by_cutoff[cutoff]=_interval_history_at(history,cutoff)
                    rows,excluded=_matched_interval_history(target,history_by_cutoff[cutoff])
                    point['historical_error_interval']={str(int(c*100)):_interval_from_matches(target,rows,excluded,c) for c in (.8,.95)}
        view['historical_error_interval']=deepcopy(view.get('cumulative',[])[-1].get('historical_error_interval')) if view.get('cumulative') else None
    return result


def score_issued_intervals(issued,truth_revisions,*,cutoff):
    """Score actual issued bounds per exact stratum, never pool unlike targets."""
    by_truth={}
    for truth in truth_revisions: by_truth.setdefault(truth['target_id'],[]).append(truth)
    result={}
    for aggregation in ('daily','weekly','cumulative'):
        rows=[r for r in issued if r['aggregation']==aggregation]
        groups={}
        for row in rows: groups.setdefault(tuple(row.get(k) for k in STRATUM),[]).append(row)
        strata=[]
        for key,group in sorted(groups.items()):
            scores=[]
            for row in group:
                matched,_=_matched(row,[row],by_truth.get(row['target_id'],[]),cutoff,before_target=False)
                if matched: scores.append((row,matched[0][1],row.get('intervals',{})))
            levels={}
            for level,alpha in [('80',.2),('95',.05)]:
                available=[(r,t,b) for r,t,b in scores if b.get(level,{}).get('lower') is not None and b.get(level,{}).get('upper') is not None]
                levels[level]=interval_metrics([b[level]['lower'] for _,_,b in available],[b[level]['upper'] for _,_,b in available],[t['value'] for _,t,_ in available],alpha)
                levels[level]['availability']=len(available)/len(group) if group else None
            paired=[(r,t,b) for r,t,b in scores if all(b.get(level,{}).get('lower') is not None and b.get(level,{}).get('upper') is not None for level in ('80','95'))]
            wis=weighted_interval_score([r['prediction'] for r,_,_ in paired],{alpha:([b[level]['lower'] for _,_,b in paired],[b[level]['upper'] for _,_,b in paired]) for level,alpha in [('80',.2),('95',.05)]},[t['value'] for _,t,_ in paired]) if paired else None
            strata.append(dict(stratum=dict(zip(STRATUM,key)),issued=len(group),scored=len(scores),intervals=levels,wis=wis,wis_count=len(paired)))
        summary={k:v for k,v in strata[0].items() if k!='stratum'} if len(strata)==1 else dict(issued=len(rows),scored=sum(g['scored'] for g in strata),intervals=None,wis=None,wis_count=0)
        result[aggregation]=dict(summary,strata=strata,qualification='Descriptive scoring of archived bounds, separately by exact target stratum; base is central point, not an asserted conditional median. No pooled metrics across unlike strata.')
    return result


def freeze_policy(serving,shadow,candidate_config,*,frozen_at,calibration_start,prospective_start,prospective_end,reference='seasonal_naive',publication_grace_seconds=300,procedure_dependencies=None):
    if not isinstance(publication_grace_seconds,int) or not 0<=publication_grace_seconds<=300:
        raise ValueError('frozen publication grace must be between zero and 300 seconds')
    if len({serving,shadow,reference})!=3 or reference!='seasonal_naive':
        raise ValueError('distinct serving/shadow/seasonal-naive procedures required')
    start,prospective,end=map(_day,(calibration_start,prospective_start,prospective_end))
    if _time(frozen_at).date()>start or (prospective-start).days<140 or (end-prospective).days<84:
        raise ValueError('freeze before 20 calibration and 12 prospective weeks')
    if any(d.weekday()!=0 for d in (start,prospective,end)):
        raise ValueError('policy windows begin on Monday')
    dependencies=_procedure_dependencies(procedure_dependencies)
    policy=dict(version=3,procedure_dependencies=dependencies,implementation_sha256=_implementation_digest(dependencies),publication_grace_seconds=publication_grace_seconds,serving=serving,shadow=shadow,reference=reference,candidate_config=deepcopy(candidate_config),
                frozen_at=frozen_at,calibration_start=calibration_start,prospective_start=prospective_start,prospective_end=prospective_end,
                minimum_calibration_weeks=20,minimum_prospective_weeks=12)
    policy['policy_id']=_digest(policy)
    return policy


def promotion_decision(policy,rows,*,procedure_dependencies=None):
    payload={k:v for k,v in policy.items() if k!='policy_id'}
    if _digest(payload)!=policy['policy_id']:
        raise ValueError('frozen policy changed; register new shadow experiment')
    reasons=[]; selected={}; metrics={}
    if policy.get('implementation_sha256')!=_implementation_digest(procedure_dependencies):
        reasons.append('implementation artifact changed; register a new frozen experiment')
    names=[policy[k] for k in ('serving','shadow','reference')]
    low=['weekly_company_mae','daily_mae','interval_score_80','interval_score_95','wis','misses_80','misses_95','invariant_failures']
    optional=['daily_interval_score_80','daily_interval_score_95','daily_misses_80','daily_misses_95']
    if any(any(k in row for k in optional) for row in rows): low+=optional
    required=low+['availability']
    for row in rows:
        if row['procedure_id'] not in names: continue
        week=_day(row['week'])
        if not _day(policy['calibration_start'])<=week<_day(policy['prospective_end']): continue
        key=(row['procedure_id'],row['week'])
        if key in selected and selected[key]!=row: reasons.append('conflicting weekly records')
        selected[key]=row
    for phase,start,end,minimum in [('calibration',policy['calibration_start'],policy['prospective_start'],20),('prospective',policy['prospective_start'],policy['prospective_end'],12)]:
        weeks=[]; cursor=_day(start)
        while cursor<_day(end): weeks.append(cursor.isoformat()); cursor+=timedelta(days=7)
        if len(weeks)<minimum: reasons.append('insufficient '+phase+' weeks')
        for name in names:
            values=[selected.get((name,w)) for w in weeks]
            if any(v is None for v in values): reasons.append('missing '+phase+' opportunities for '+name); continue
            for row in values:
                if row.get('policy_id') != policy['policy_id']:
                    reasons.append('record does not identify frozen policy')
                try:
                    origin=_time(row['week']+'T00:00:00+00:00')
                    if _time(row['issued_at']) > origin+timedelta(seconds=policy.get('publication_grace_seconds',0)) or _time(row['issued_at']) < _time(policy['frozen_at']):
                        reasons.append('late or pre-freeze prediction')
                    if _time(row['information_cutoff'])>origin:
                        reasons.append('post-origin information cannot score prospectively')
                except (KeyError,ValueError,TypeError):
                    reasons.append('missing valid original issuance time')
                if row.get('phase')!=phase or not row.get('mature') or row.get('is_synthetic') or not row.get('reconstructible') or not row.get('input_manifest'):
                    reasons.append('genuine mature reconstructible '+phase+' evidence required')
                phase_required=required if phase=='prospective' else ['weekly_company_mae','daily_mae','availability','invariant_failures']
                if any(k not in row or row[k] is None or isinstance(row[k],bool) or not isinstance(row[k],(int,float)) or not math.isfinite(row[k]) or row[k]<0 for k in phase_required):
                    reasons.append('missing or invalid metrics'); break
                # Calibration outcomes are part of the frozen eligibility window,
                # even though comparative performance uses prospective metrics.
                if name==policy['shadow'] and row['invariant_failures']!=0:
                    reasons.append('candidate invariant failure')
            else:
                if phase=='prospective': metrics[name]={k:math.fsum(row[k]/len(values) for row in values) for k in required}
    if len(metrics)==3:
        candidate=metrics[policy['shadow']]
        if candidate['invariant_failures']!=0: reasons.append('candidate invariant failure')
        for name in (policy['serving'],policy['reference']):
            other=metrics[name]
            if candidate['weekly_company_mae']>=other['weekly_company_mae']: reasons.append('weekly company MAE must strictly improve '+name)
            if any(candidate[k]>other[k] for k in low[1:]): reasons.append('regressed secondary metrics versus '+name)
            if candidate['availability']<other['availability'] or candidate['availability']>1: reasons.append('availability regression')
    else: reasons.append('incomplete prospective metrics')
    return dict(policy_id=policy['policy_id'],promote=not reasons,serving=policy['shadow'] if not reasons else policy['serving'],
                decision='promote' if not reasons else 'retain_incumbent',reasons=sorted(set(reasons)),prospective_metrics=metrics,
                qualification='Evidence provenance must be attested by the company archive; synthetic fixtures cannot authorize promotion.')


def _evaluation_rows(snapshot,registry,cutoff):
    """Reconstruct weekly policy metrics from issued bases and observed outcomes."""
    policy=registry['policy']; by_truth={}
    for truth in snapshot.get('truth_revisions',[]):
        by_truth.setdefault(truth['target_id'],[]).append(truth)
    grouped={}
    for target in snapshot.get('issued_targets',[]):
        if target.get('implementation_sha256')!=policy.get('implementation_sha256'): continue
        if target.get('policy_id')!=policy['policy_id'] or target.get('scope_type')!='company': continue
        if target.get('aggregation') not in ('daily','weekly'): continue
        origin=target['origin']
        if not policy['calibration_start']<=origin<policy['prospective_end'] or _day(origin).weekday()!=0: continue
        grouped.setdefault((target['procedure_id'],origin),[]).append(target)
    result=[]
    for (procedure,week),targets in sorted(grouped.items()):
        # Earliest issued run is frozen for a scheduled opportunity. Later manual
        # retries cannot retroactively choose a better result.
        run=min(targets,key=lambda r:(r['issued_at'],r['run_id']))['run_id']
        targets=[r for r in targets if r['run_id']==run]
        wanted=[r for r in targets if (r['aggregation']=='weekly' and r['lead_days']==0 and r['duration_days']==7) or (r['aggregation']=='daily' and 0<=r['lead_days']<7 and r['duration_days']==1)]
        mature=[]
        for row in wanted:
            matched,_=_matched(row,[row],by_truth.get(row['target_id'],[]),cutoff,before_target=False)
            if matched: mature.append(matched[0])
        weekly=[pair for pair in mature if pair[0]['aggregation']=='weekly']
        daily=[pair for pair in mature if pair[0]['aggregation']=='daily']
        complete=len(weekly)==1 and len(daily)==7 and len({r['lead_days'] for r,_ in daily})==7
        phase='calibration' if week<policy['prospective_start'] else 'prospective'
        record=dict(week=week,procedure_id=procedure,policy_id=policy['policy_id'],phase=phase,
                    issued_at=min(r['issued_at'] for r in targets),information_cutoff=max((r.get('information_cutoff') or r['issued_at']) for r in targets),is_synthetic=any(r.get('is_synthetic') or t.get('is_synthetic') for r,t in mature),
                    reconstructible=bool(targets) and all(r.get('input_manifest') and r.get('snapshot_id') for r in targets),
                    input_manifest=sorted({r.get('input_manifest','') for r in targets}),mature=complete,
                    weekly_company_mae=abs(weekly[0][0]['prediction']-weekly[0][1]['value']) if len(weekly)==1 else None,
                    daily_mae=math.fsum(abs(r['prediction']-t['value'])/7 for r,t in daily) if len(daily)==7 else None,
                    availability=len(wanted)/8,invariant_failures=sum(r.get('invariant_failures',0) for r in wanted))
        origin_time=_time(week+'T00:00:00+00:00')
        record['publication_on_time']=_time(record['issued_at'])<=origin_time+timedelta(seconds=policy.get('publication_grace_seconds',0)) and _time(record['information_cutoff'])<=origin_time
        if not record['publication_on_time']: record['availability']=0
        if complete:
            if not math.isclose(math.fsum(r['prediction'] for r,_ in daily),weekly[0][0]['prediction'],rel_tol=1e-9,abs_tol=1e-8):
                record['invariant_failures']+=1
            if not math.isclose(math.fsum(t['value'] for _,t in daily),weekly[0][1]['value'],rel_tol=1e-9,abs_tol=1e-8):
                record['invariant_failures']+=1
        for coverage,alpha in [('80',.2),('95',.05)]:
            for label,pairs in [('',weekly),('daily_',daily)]:
                expected=1 if not label else 7
                usable=[(r,t,r.get('intervals',{}).get(coverage,{})) for r,t in pairs]
                usable=[(r,t,b) for r,t,b in usable if b.get('lower') is not None and b.get('upper') is not None]
                metric=interval_metrics([b['lower'] for _,_,b in usable],[b['upper'] for _,_,b in usable],[t['value'] for _,t,_ in usable],alpha) if len(usable)==expected else None
                record[label+'interval_score_'+coverage]=metric['interval_score'] if metric else None
                record[label+'misses_'+coverage]=sum(not b['lower']<=t['value']<=b['upper'] for _,t,b in usable) if metric else None
        if weekly and all(weekly[0][0].get('intervals',{}).get(level,{}).get('lower') is not None for level in ('80','95')):
            r,t=weekly[0]
            record['wis']=weighted_interval_score([r['prediction']],{alpha:([r['intervals'][level]['lower']],[r['intervals'][level]['upper']]) for level,alpha in [('80',.2),('95',.05)]},[t['value']])
        else: record['wis']=None
        result.append(record)
    return result


def update_model_registry(snapshot,*,generated_at):
    """Deterministic appendable registry revision, evaluated before every refresh.

    Automatic replacement is based exclusively on this policy's archived issued
    targets plus mature truth, never on caller-supplied summary claims. Once a
    candidate is promoted, a distinct future experiment must be registered to
    replace it again. Empty or synthetic evidence always retains serving.
    """
    registry=deepcopy(snapshot.get('model_registry'))
    if not registry:
        now=_time(generated_at)
        beginning=now.date()+timedelta(days=(-now.weekday())%7)
        if datetime.combine(beginning,datetime.min.time(),tzinfo=timezone.utc)<now:
            beginning+=timedelta(days=7)
        serving=dict(id='driver-rate-weekblock-v1',kind='driver_rate',window_days=56)
        shadow=dict(id='driver-rate-weekblock-28-v1',kind='driver_rate',window_days=28)
        reference=dict(id='seasonal_naive',kind='seasonal_naive',window_days=56)
        policy=freeze_policy(serving['id'],shadow['id'],shadow,frozen_at=generated_at,calibration_start=str(beginning),
                             prospective_start=str(beginning+timedelta(weeks=20)),prospective_end=str(beginning+timedelta(weeks=32)),procedure_dependencies=snapshot.get('procedure_dependencies'))
        registry=dict(version=0,serving=serving,shadow=shadow,reference=reference,policy=policy,status='shadow_evaluation')
    if registry['shadow']!=registry['policy']['candidate_config']:
        raise ValueError('shadow configuration differs from frozen candidate')
    rows=_evaluation_rows(snapshot,registry,generated_at)
    material=dict(rows=rows,is_synthetic=bool(snapshot.get('is_synthetic',False)),implementation_sha256=_implementation_digest(snapshot.get('procedure_dependencies')))
    digest=_digest(material)
    if registry.get('evaluation_digest')==digest:
        return registry
    decision=promotion_decision(registry['policy'],rows,procedure_dependencies=snapshot.get('procedure_dependencies'))
    if snapshot.get('is_synthetic'):
        decision.update(promote=False,serving=registry['serving']['id'],decision='retain_incumbent')
        decision['reasons']=sorted(set(decision['reasons']+['synthetic fixture evidence cannot promote']))
    if registry.get('status')=='promoted':
        decision.update(promote=False,serving=registry['serving']['id'],decision='retain_incumbent')
        decision['reasons']=sorted(set(decision['reasons']+['experiment already promoted; register a new frozen candidate']))
    elif decision['promote']:
        registry['previous_serving']=deepcopy(registry['serving'])
        registry['serving']=deepcopy(registry['shadow'])
        registry['status']='promoted'
    registry.update(version=registry['version']+1,evaluated_at=generated_at,evaluation_digest=digest,
                    decision=decision,evaluation_rows=rows)
    registry['registry_id']=_digest({k:v for k,v in registry.items() if k!='registry_id'})
    return registry


def build_learning_bundle(snapshot,*,run_id,generated_at,builder):
    """Run serving plus frozen shadow/reference; only serving views are published."""
    registry=snapshot.get('model_registry') or update_model_registry(snapshot,generated_at=generated_at)
    targets=[]; runs=[]; serving=None
    for role in ('serving','shadow','reference'):
        procedure=registry[role]
        # After promotion serving equals shadow; preserve one issued identity.
        if any(r['procedure_id']==procedure['id'] for r in runs):
            continue
        local=deepcopy(snapshot); local['model_registry']=registry; local['procedure']=deepcopy(procedure)
        local_run=run_id if role=='serving' else run_id+':'+role
        try:
            bundle=builder(local,run_id=local_run,generated_at=generated_at)
            bundle=enrich_intervals(bundle,local)
            archived=archive_issued_targets(bundle,local)
            targets.extend(archived)
            runs.append(dict(role=role,run_id=local_run,procedure_id=procedure['id'],status='available',issued_targets=len(archived)))
            if role=='serving': serving=bundle
        except Exception as exc:
            if role=='serving': raise
            runs.append(dict(role=role,run_id=local_run,procedure_id=procedure['id'],status='failed',issued_targets=0,error=type(exc).__name__+': '+str(exc)))
    serving['learning_targets']=targets
    serving['learning_runs']=runs
    serving['model_registry']=deepcopy(registry)
    return serving


def score_error_receipts(snapshot,*,cutoff):
    """Return new immutable error/withdrawal receipts; never observed fit inputs.

    Payload timestamps describe when a revision can affect scoring. Persistence
    separately records when this receipt was computed/received. A pending or
    disputed revision immediately withdraws its predecessor; a mature-status
    revision with a future maturity first appends awaiting_maturity and later
    appends scored. The original scored receipt remains unchanged forever.
    """
    cutoff_time=_time(cutoff)
    inventory={}
    for target in snapshot.get('issued_targets',[]):
        _validate_target(target)
        key=target['target_id']
        if key in inventory and inventory[key]!=target:
            raise ValueError('issued target identity changed')
        inventory[key]=target
    versions={}; by_target={}
    for truth in snapshot.get('truth_revisions',[]):
        key=(truth['target_id'],truth['revision'])
        if key in versions and versions[key]!=truth:
            raise ValueError('conflicting truth revision')
        versions[key]=truth
    for truth in versions.values(): by_target.setdefault(truth['target_id'],[]).append(truth)
    existing={}
    for receipt in snapshot.get('forecast_errors',[]):
        key=(receipt['target_id'],receipt['truth_revision'],receipt['state'])
        if key in existing and existing[key]!=receipt:
            raise ValueError('conflicting immutable error receipt')
        existing[key]=receipt
    additions=[]
    for target_id,target in sorted(inventory.items()):
        truths=by_target.get(target_id,[])
        # Reuse the numerical, revision and maturity validation of calibration.
        _matched(target,[target],truths,cutoff,before_target=False)
        for truth in sorted(truths,key=lambda row:row['revision']):
            available,mature=_time(truth['available_at']),_time(truth['mature_at'])
            known=max(available,_time(target['issued_at']))
            if known>cutoff_time: continue
            if bool(truth.get('is_synthetic',False))!=bool(target.get('is_synthetic',False)):
                events=[('incompatible_evidence',known)]
            elif truth['status']!='mature':
                events=[('withdrawn',known)]
            else:
                events=[]
                if mature>known: events.append(('awaiting_maturity',known))
                if max(mature,known)<=cutoff_time: events.append(('scored',max(mature,known)))
            for state,effective in events:
                scored=state=='scored'
                residual=_finite(truth['value']-target['prediction']) if scored else None
                receipt=dict(kind='forecast_error_receipt',target_id=target_id,run_id=target['run_id'],
                             truth_revision=truth['revision'],truth_source_id=truth.get('source_id'),
                             truth_status=truth['status'],state=state,
                             available_at=truth['available_at'],mature_at=truth['mature_at'],effective_at=effective.isoformat(),
                             issued_at=target['issued_at'],origin=target['origin'],start=target['start'],end=target['end'],
                             stratum={key:target.get(key) for key in STRATUM},prediction=target['prediction'],
                             actual=truth['value'] if scored else None,residual=residual,
                             absolute_error=abs(residual) if scored else None,
                             is_synthetic=bool(target.get('is_synthetic',False) or truth.get('is_synthetic',False)),
                             supersedes_through_revision=truth['revision']-1,
                             qualification='Immutable scoring audit only; never an observed model-fitting input. Apply the latest available truth revision before selecting a score.')
                receipt['receipt_id']=_digest(receipt)
                key=(target_id,truth['revision'],state)
                if key in existing:
                    if existing[key]!=receipt: raise ValueError('conflicting immutable error receipt')
                else: additions.append(receipt)
    return sorted(additions,key=lambda row:(row['effective_at'],row['target_id'],row['truth_revision'],row['state']))


def current_error_records(receipts,*,cutoff):
    """Project append-only error receipts to their as-of active revision/state."""
    cutoff_time=_time(cutoff); result={}; identities={}; states={}
    priorities={'awaiting_maturity':0,'withdrawn':1,'incompatible_evidence':1,'scored':2}
    for receipt in receipts:
        if receipt['state'] not in priorities: raise ValueError('unknown error receipt state')
        if receipt['receipt_id'] in identities and identities[receipt['receipt_id']]!=receipt:
            raise ValueError('conflicting immutable error receipt')
        identities[receipt['receipt_id']]=receipt
        state_key=(receipt['target_id'],receipt['truth_revision'],receipt['state'])
        if state_key in states and states[state_key]!=receipt:
            raise ValueError('conflicting immutable error receipt')
        states[state_key]=receipt
        if _time(receipt['effective_at'])>cutoff_time: continue
        target_id=receipt['target_id']
        order=(receipt['truth_revision'],priorities[receipt['state']])
        old=result.get(target_id)
        if old is None or order>(old['truth_revision'],priorities[old['state']]):
            result[target_id]=deepcopy(receipt)
    return result
