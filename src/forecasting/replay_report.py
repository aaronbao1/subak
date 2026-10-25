"""Deterministic extraction → context → pricing replay with explicit denominators.

Run from repository root: PYTHONPATH=src:backend python -m forecasting.replay_report.
The bundled Northstar evaluation is synthetic mechanism evidence only.
"""
from __future__ import annotations
from copy import deepcopy
from datetime import timedelta
import argparse
import json
import math
from pathlib import Path

from .learning import _digest, _finite, _time, _day


def _facts(drivers):
    def normalize(value):
        if isinstance(value,dict): return {k:normalize(v) for k,v in value.items()}
        if isinstance(value,list): return [normalize(v) for v in value]
        if isinstance(value,(int,float)) and not isinstance(value,bool): return float(value)
        return value
    facts=[]
    for driver in drivers:
        if driver.get('status')!='eligible': continue
        fact={key:deepcopy(driver.get(key)) for key in ('kind','scope','effective_from','effective_to','parameters')}
        fact['parameters'].setdefault('mode','absolute')
        facts.append(_digest(normalize(fact)))
    return sorted(facts)


def _key(row):
    return tuple(row[k] for k in ('scope_type','scope_id','aggregation','start','end'))


def direct_weekly_challenger(snapshot,targets,*,method='weekly_mean'):
    """Fit complete observed weekly company spend; never invent a daily allocation.

    Evaluation-only challengers: trailing eight complete weekly-total mean and
    last complete weekly total. Conversion supports attested complete linear
    pools with no allowance/fixed charge. Nonlinear/incomplete pricing is
    unavailable; it is never approximated by multiplying usage by a unit rate.
    """
    if method not in ('weekly_mean','weekly_last'): raise ValueError('unknown weekly challenger')
    cutoff=_time(snapshot['information_cutoff']); origin=_day(snapshot['forecast_start'])
    watermark=min(_day(snapshot['history_complete_through']),origin-timedelta(days=1),cutoff.date()-timedelta(days=1))
    if snapshot['target'].get('unit')!='USD' or snapshot['target'].get('timezone','UTC')!='UTC':
        raise ValueError('weekly challenger requires USD UTC observed spend')
    required=set(snapshot.get('required_sources',[]))
    if not required: raise ValueError('required source coverage needed')
    coverage={}; coverage_versions={}
    for row in snapshot.get('coverage',[]):
        if row.get('available_at') and _time(row['available_at'])>cutoff: continue
        key=(row['date'],row['source_id']); revision=int(row.get('source_revision',row.get('revision',1)))
        if key in coverage_versions and revision==coverage_versions[key][0] and row!=coverage_versions[key][1]:
            raise ValueError('conflicting source coverage revision')
        if key not in coverage_versions or revision>coverage_versions[key][0]: coverage_versions[key]=(revision,row)
    for (_,source),(_,row) in coverage_versions.items():
        if row.get('complete'): coverage.setdefault(row['date'],set()).add(source)
    observations={}
    dimensions=('source_id','person_id','team_id','project_id','configuration_id','meter','billing_pool')
    for row in snapshot.get('observations',[]):
        if not row.get('available_at') or _time(row['available_at'])>cutoff: continue
        key=(row['date'],)+tuple(row.get(k) for k in dimensions)
        revision=int(row.get('source_revision',row.get('revision',1)))
        if key in observations and observations[key][0]==revision and observations[key][1]!=row:
            raise ValueError('conflicting observed usage revision')
        if key not in observations or revision>observations[key][0]: observations[key]=(revision,row)
    by_day={}
    for _,row in observations.values(): by_day.setdefault(row['date'],[]).append(row)
    tariffs={}
    for tariff in snapshot.get('pricing',[]):
        if not tariff.get('known_at') or _time(tariff['known_at'])>cutoff: continue
        key=tariff['id']; revision=int(tariff.get('version',1))
        if key not in tariffs or revision>int(tariffs[key].get('version',1)): tariffs[key]=tariff
    weeks=[]
    last_monday=watermark-timedelta(days=watermark.weekday())
    if last_monday+timedelta(days=6)>watermark: last_monday-=timedelta(days=7)
    for delta in reversed(range(8)):
        monday=last_monday-timedelta(weeks=delta); total=[]; valid=True
        for offset in range(7):
            day=monday+timedelta(days=offset); key=str(day)
            if not required.issubset(coverage.get(key,set())): valid=False; break
            available=[t for t in tariffs.values() if _day(t.get('effective_from',t['period_start']))<=day<_day(t.get('effective_to') or t['period_end'])]
            if not available or any(t.get('mode')!='linear' or not t.get('complete_pool') or t.get('allowance',0)!=0 or t.get('fixed',0)!=0 or t.get('currency')!='USD' for t in available):
                valid=False; break
            for row in by_day.get(key,[]):
                if not row.get('complete') or not row.get('mature') or row.get('source_id') not in required:
                    valid=False; break
                matching=[t for t in available if t.get('billing_pool')==row.get('billing_pool') and (not t.get('configuration_id') or t['configuration_id']==row.get('configuration_id')) and (not t.get('meter') or t['meter']==row.get('meter')) and t.get('unit')==row.get('meter')]
                if len(matching)!=1: valid=False; break
                quantity=_finite(row['quantity']); rate=_finite(matching[0]['rate'])
                if quantity<0 or rate<0: raise ValueError('nonnegative observed quantities/tariffs required')
                total.append(_finite(quantity*rate))
            if not valid: break
        if valid: weeks.append(dict(start=str(monday),end=str(monday+timedelta(days=7)),value=_finite(math.fsum(total))))
    minimum=2 if method=='weekly_mean' else 1
    if len(weeks)<minimum: raise ValueError('insufficient complete observed weeks with supported linear full-pool pricing')
    prediction=_finite(math.fsum(r['value']/len(weeks) for r in weeks)) if method=='weekly_mean' else weeks[-1]['value']
    points=[]
    for target in targets:
        start,end=_day(target['start']),_day(target['end'])
        if target['aggregation']!='weekly' or target['scope_type']!='company' or target['scope_id']!=snapshot['tenant_id'] or start<origin or start.weekday()!=0 or (end-start).days!=7: continue
        points.append(dict(start=str(start),end=str(end),base=prediction,complete=True))
    return dict(views=[dict(scope={'type':'company','id':snapshot['tenant_id']},weekly=points,daily=[],cumulative=[])],
                method=dict(name=method,training_weeks=len(weeks),training_targets=weeks,information_cutoff=snapshot['information_cutoff'],
                            qualification='Evaluation-only direct weekly total; no context, no daily allocation, no automatic serving promotion. USD observed totals require complete source coverage and complete linear pricing; nonlinear, fixed and allowance pools unavailable.'))


def replay_cases(cases, *, build_forecast, extract_event):
    """All scheduled cases and held-out targets remain in every arm's denominator.

    Missing extraction is a service failure for the extracted arm; no-context and
    oracle controls still run. Conditional MAE is never an unconditional success
    claim. Inputs, oracle facts and held-out truths are included for reconstruction.
    """
    cases=deepcopy(list(cases)); ids=[c['id'] for c in cases]
    if len(ids)!=len(set(ids)): raise ValueError('unique replay case IDs required')
    names=('extracted_context','no_context','oracle_context','direct_weekly_mean','direct_weekly_last')
    rows={name:[] for name in names}; extraction=[]
    for case in cases:
        truths=case.get('actuals',[])
        keys=[_key(row) for row in truths]
        if len(keys)!=len(set(keys)): raise ValueError('duplicate held-out target')
        for truth in truths: _finite(truth['value'])
        snapshot=case['snapshot']
        generated_at=snapshot.get('generated_at',snapshot['information_cutoff'])
        extracted=[]; extraction_error=None
        try:
            for envelope in case.get('envelopes',[]): extracted.extend(extract_event(envelope,deepcopy(snapshot)))
        except Exception as exc:
            extraction_error=type(exc).__name__+': '+str(exc)
        exact=extraction_error is None and _facts(extracted)==_facts(case.get('oracle_drivers',[]))
        extraction.append(dict(case_id=case['id'],success=extraction_error is None,exact_match=exact,error=extraction_error,
                               extracted_drivers=extracted,oracle_drivers=case.get('oracle_drivers',[])))
        for name,drivers in [('extracted_context',extracted),('no_context',[]),('oracle_context',case.get('oracle_drivers',[])),('direct_weekly_mean',[]),('direct_weekly_last',[])]:
            failure=extraction_error if name=='extracted_context' else None
            predictions={}; method_manifest=None
            if failure is None:
                try:
                    if name.startswith('direct_'):
                        output=direct_weekly_challenger(deepcopy(snapshot),truths,method=name.removeprefix('direct_'))
                        method_manifest=output['method']
                    else:
                        output=build_forecast(deepcopy(snapshot),run_id='replay:'+_digest([case['id'],name])[:20],generated_at=generated_at,drivers=deepcopy(drivers))
                    for view in output.get('views',[output]):
                        for aggregation in ('daily','weekly','cumulative'):
                            for point in view.get(aggregation,[]):
                                key=(view['scope']['type'],view['scope']['id'],aggregation,point.get('start',point.get('date')),point['end'])
                                if key in predictions: raise ValueError('duplicate forecast target')
                                if point.get('complete',True) and point.get('base') is not None:
                                    predictions[key]=_finite(point['base'])
                except Exception as exc:
                    failure=type(exc).__name__+': '+str(exc); predictions={}
            scored=[]
            for truth in truths:
                prediction=predictions.get(_key(truth))
                scored.append(dict(target={k:truth[k] for k in ('scope_type','scope_id','aggregation','start','end')},
                                   actual=truth['value'],prediction=prediction,
                                   absolute_error=_finite(abs(prediction-truth['value'])) if prediction is not None else None))
            rows[name].append(dict(case_id=case['id'],failure=failure,method=method_manifest,expected_targets=len(truths),served_targets=sum(r['prediction'] is not None for r in scored),targets=scored,
                                   snapshot_sha256=_digest(snapshot),evidence_sha256=_digest(case.get('envelopes',[]))))
    summaries={}
    for name in names:
        expected=sum(r['expected_targets'] for r in rows[name]); served=sum(r['served_targets'] for r in rows[name])
        errors=[t['absolute_error'] for r in rows[name] for t in r['targets'] if t['absolute_error'] is not None]
        summaries[name]=dict(scheduled_cases=len(cases),failed_cases=sum(r['failure'] is not None for r in rows[name]),
                             expected_targets=expected,served_targets=served,missing_targets=expected-served,
                             availability=served/expected if expected else None,
                             conditional_mae=math.fsum(e/len(errors) for e in errors) if errors else None,rows=rows[name])
    synthetic=any(c.get('is_synthetic',False) for c in cases)
    return dict(schema_version=1,evidence='synthetic_mechanism_demo' if synthetic else 'replay_only',is_synthetic=synthetic,
                promotion_eligible=False,comparisons=summaries,
                extraction=dict(scheduled_cases=len(cases),successful_cases=sum(x['success'] for x in extraction),
                                exact_matches=sum(x['exact_match'] for x in extraction),exact_match_rate=sum(x['exact_match'] for x in extraction)/len(cases) if cases else None,rows=extraction),
                reconstruction=dict(input_sha256=_digest(cases),cases=cases),
                qualification='Synthetic fixtures are not enterprise accuracy evidence. MAE is conditional on available outputs; every extraction failure remains in the denominator. Oracle structured facts measure the extraction gap, not attainable production knowledge. A replay cannot promote a shadow procedure; prospective policy evidence is separate.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    from app.forecasting.evidence import extract_event
    from app.forecasting.fixtures import northstar_replay_cases
    from .planning import build_forecast
    report=replay_cases(northstar_replay_cases(),build_forecast=build_forecast,extract_event=extract_event)
    rendered=json.dumps(report,indent=2,sort_keys=True,allow_nan=False)+'\n'
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True); args.output.write_text(rendered)
    else: print(rendered,end='')


if __name__=='__main__': main()
