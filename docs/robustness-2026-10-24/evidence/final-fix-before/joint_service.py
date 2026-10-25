"""Evidence-bound joint orchestration; source acquisition remains backend-owned."""
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal, localcontext
from fractions import Fraction
from zoneinfo import ZoneInfo
import json

from .contracts import ForecastResult, decimal, exact_sum, exact_product, digest, primitive
from .models import Series, ModelUnavailable
from .store import AccessDenied, canonical_json


EVIDENCE_CLASSES = {'unspecified', 'synthetic_fixture', 'authorized_local_file',
                    'backend_verified_snapshot', 'public_trace', 'mixed'}


def bound_evidence(snapshot, requested='unspecified'):
    """A caller may suppress provenance, but cannot supply a stronger receipt."""
    bound = getattr(snapshot, 'evidence_class', 'unspecified')
    if requested not in EVIDENCE_CLASSES or bound not in EVIDENCE_CLASSES:
        raise ValueError('unknown evidence class')
    if requested != 'unspecified' and requested != bound:
        raise ValueError('caller evidence class cannot upgrade or relabel bound provenance')
    return bound if requested == 'unspecified' else requested


def _number(value):
    result = Decimal(str(value)) if not isinstance(value, Decimal) else value
    if not result.is_finite():
        raise ValueError('nonfinite derived summary')
    return result


def _ratio(value):
    # Pricing totals remain exact Decimal. Statistical expectations can be
    # rational; publish their explicitly declared 50-digit decimal projection.
    with localcontext() as context:
        context.prec = 50
        result = Decimal(value.numerator) / Decimal(value.denominator)
    if not result.is_finite():
        raise ValueError('nonfinite derived expectation')
    return result


def _weights(weights):
    values = tuple(Fraction(_number(w)) for w in weights)
    total = sum(values, Fraction(0))
    if total <= 0 or any(w < 0 for w in values):
        raise ValueError('positive probability mass required')
    return tuple(w / total for w in values)


def _mean(values, weights):
    return _ratio(sum((Fraction(_number(v))*w for v,w in zip(values,weights)), Fraction(0)))


def _summaries(values, weights, quantiles, threshold, tail_alpha):
    weights = _weights(weights)
    values = tuple(_number(v) for v in values)
    pairs = sorted((v,w) for v,w in zip(values,weights) if w > 0)
    quantile_values = {}
    for q in quantiles:
        mass = Fraction(0)
        for value, weight in pairs:
            mass += weight
            if mass >= Fraction(str(q)):
                break
        quantile_values[str(q)] = str(value)
    remaining = tail = 1-Fraction(str(tail_alpha))
    terms = Fraction(0)
    for value, weight in reversed(pairs):
        take = min(weight, remaining)
        terms += Fraction(value)*take
        remaining -= take
        if remaining <= 0:
            break
    exceedance = excess = None
    if threshold is not None:
        threshold = _number(threshold)
        exceedance = float(sum((w for v,w in pairs if v > threshold), Fraction(0)))
        excess = str(_ratio(sum((Fraction(max(Decimal(0),exact_sum((v,-threshold))))*w
                                for v,w in pairs), Fraction(0))))
    return {'mean': str(_mean(values,weights)), 'quantiles': quantile_values,
            'threshold': str(threshold) if threshold is not None else None,
            'exceedance_probability': exceedance, 'expected_excess': excess,
            'expected_shortfall': str(_ratio(terms/tail)), 'tail_alpha': tail_alpha,
            'qualification': {'status':'available_assumption_conditional',
                              'reasons':['Summaries describe the supplied joint law; empirical calibration is not established.']}}


def _qualify(summary):
    summary['qualifications'] = {}
    for output in ('mean','quantiles','exceedance_probability','expected_excess','expected_shortfall'):
        present = bool(summary[output]) if output == 'quantiles' else summary[output] is not None
        summary['qualifications'][output] = (dict(summary['qualification']) if present else
            {'status':'unavailable','reasons':summary['qualification']['reasons'] if summary['qualification']['status'] == 'unavailable' else ['Output was not requested.']})
    return summary


def _unavailable(reason):
    return {'mean':None, 'quantiles':{}, 'exceedance_probability':None,
            'expected_excess':None, 'expected_shortfall':None,
            'qualification':{'status':'unavailable','reasons':[reason]}}


def _monetary_summaries(priced, request, origin, quantiles, threshold, tail_alpha):
    """Keep complete-contract valuation distinct from exact requested amounts."""
    weights = tuple(path.weight for path in priced.paths)
    complete = _summaries(tuple(path.total for path in priced.paths),weights,quantiles,None,tail_alpha)
    periods = priced.paths[0].periods
    complete.update(target_scope='complete_contract_periods', basis=priced.basis,
        periods=[{'pool':period.pool,'period_start':period.period_start.isoformat(),
                  'period_end':period.period_end.isoformat()} for period in periods])
    _qualify(complete)
    start = max(origin,request.period_start) if request.output == 'remainder' else request.period_start
    reason = None
    by_pool = {}
    for period in periods:
        if request.output == 'full_period' or period.period_end > start:
            by_pool.setdefault(period.pool,[]).append(period)
    if not by_pool:
        reason = 'No complete commercial support for the requested interval.'
    for pool_periods in by_pool.values():
        ordered = sorted(pool_periods,key=lambda period:period.period_start)
        left = ordered[0].period_start
        if request.output == 'remainder': left = max(left,origin)
        if left != start or ordered[-1].period_end != request.period_end:
            reason = 'Requested monetary interval differs from complete supplied contract coverage.'
        if request.output == 'remainder' and any(period.period_start < start and period.fixed != 0 for period in ordered):
            reason = 'Fixed charge temporal basis is unavailable for a partial contract period.'
    if reason:
        result = _unavailable(reason)
    else:
        totals = []
        for path in priced.paths:
            if request.output == 'full_period':
                totals.append(path.total)
            else:
                totals.append(exact_sum(exact_sum((period.future_increment,period.fixed if period.period_start >= start else Decimal(0)))
                                        for period in path.periods if period.period_end > start))
        result = _summaries(tuple(totals),weights,quantiles,threshold,tail_alpha)
    result.update(target_scope='exact_requested_remainder_increment' if request.output == 'remainder' else 'exact_requested_full_period',
        target_start=start.isoformat(),target_end=request.period_end.isoformat(),
        basis=priced.basis,commercial_input_id=priced.input_id,currency=periods[0].currency,
        complete_contract=complete)
    return result


def run_joint(service, request, snapshot, *, allowed_sources, axes=(), n_paths=200,
              seed=0, model_config=None, min_blocks=3, allow_direct_fallback=True,
              evidence_class='unspecified', max_history_lag_days=0,
              recorded_supplement=None, quantiles=(.5,.9,.95), threshold=None,
              tail_alpha=.95, state_inputs=None, commercial_options=None, monetary_threshold=None,
              scenario=None, workload_adjustments=(), required_artifacts=()):
    """One aligned generator per panel; numerical views qualify independently.

    ``state_inputs`` and ``commercial_options`` are trusted backend inputs, never
    paths or permissions granted by an HTTP request. Full-period money needs the
    commercial adapter's explicit complete billing-period coverage evidence.
    """
    from .joint import fit_joint_blocks, ScenarioSpec, ProcedureSpec, JointUnavailable
    sources = frozenset(allowed_sources)
    if not set(request.target.sources).issubset(sources):
        raise AccessDenied('current source permissions required')
    if snapshot.target != request.target or snapshot.as_of != request.as_of:
        raise ValueError('snapshot target and cutoff must exactly match request')
    required_artifacts = tuple(required_artifacts)
    for artifact in required_artifacts:
        service.store.get(request.target.tenant_id,artifact,allowed_sources=sources)
    evidence = bound_evidence(snapshot,evidence_class)
    if request.target.measure != 'metered_usage' or not request.target.additive:
        raise ValueError('joint native route requires additive metered usage')
    origin = request.as_of.astimezone(ZoneInfo(request.target.reporting_timezone)).date()
    lag = (origin-snapshot.history_end).days
    if type(max_history_lag_days) is not int or not 0 <= max_history_lag_days <= 30 or not 0 <= lag <= max_history_lag_days:
        raise ValueError('daily history watermark exceeds explicit lag policy')
    if request.period_start < snapshot.history_start:
        raise ValueError('snapshot does not cover recorded portion of requested period')
    if (request.period_end-snapshot.history_end).days > service.max_horizon:
        raise ValueError('requested horizon exceeds configured workload bound')
    if any(isinstance(q,bool) or not isinstance(q,(float,int)) or not 0 <= q <= 1 for q in quantiles):
        raise ValueError('quantiles must be finite probabilities')
    if isinstance(tail_alpha,bool) or not isinstance(tail_alpha,(float,int)) or not 0 <= tail_alpha < 1:
        raise ValueError('tail alpha must be in [0,1)')
    if threshold is not None: threshold = _number(threshold)
    scenario = scenario or ScenarioSpec()
    if not isinstance(scenario,ScenarioSpec): raise ValueError('typed scenario specification required')
    dates = tuple(origin+timedelta(days=i) for i in range(max(0,(request.period_end-origin).days))
                  if origin+timedelta(days=i) >= request.period_start)
    observations = {}
    for row in snapshot.daily:
        observations.setdefault(row.entity_id,[]).append(row)
    if len(observations) > service.max_entities:
        raise ValueError('entity workload bound exceeded')
    recorded_by = snapshot.recorded_by_entity(request.period_start,min(origin,request.period_end)) if request.period_start < min(origin,request.period_end) else {}
    limitations = list(snapshot.limitations)
    if recorded_supplement is not None:
        if (recorded_supplement.target != request.target or recorded_supplement.as_of != request.as_of
            or recorded_supplement.history_start != snapshot.history_end or recorded_supplement.history_end != origin
            or recorded_supplement.source_manifest != snapshot.source_manifest):
            raise ValueError('incurred supplement must share exact source generations, target, cutoff and gap')
        if request.period_start < min(origin,request.period_end):
            start,end = max(request.period_start,snapshot.history_end),min(origin,request.period_end)
            if start < end:
                for entity,value in recorded_supplement.recorded_by_entity(start,end).items():
                    recorded_by[entity] = exact_sum((recorded_by.get(entity,Decimal(0)),value))
        if {r.entity_id for r in recorded_supplement.daily}-set(observations):
            limitations.append('new incurred entity lacks training history')
    elif lag and request.output == 'full_period' and request.period_start < min(origin,request.period_end):
        raise ValueError('delayed full-period request requires same-source incurred supplement')
    if lag: limitations.append('history_lag_days:%d; bridge forecasts are not recorded usage' % lag)
    recorded = exact_sum(recorded_by.values()) if request.output == 'full_period' else Decimal(0)
    snapshot_artifact = service.store.put(request.target.tenant_id,'snapshot',snapshot.to_dict(),request.target.sources)
    supplement_artifact = service.store.put(request.target.tenant_id,'snapshot',recorded_supplement.to_dict(),request.target.sources) if recorded_supplement is not None else None
    material_dependencies = required_artifacts+(snapshot_artifact,)+((supplement_artifact,) if supplement_artifact else ())
    bundle = None
    state_artifact = None
    state_evidence = None
    parent_artifacts = []
    unavailable = None
    try:
        if not snapshot.ready or 'new incurred entity lacks training history' in limitations:
            raise ModelUnavailable('snapshot coverage or training support unavailable')
        if not dates:
            raise ModelUnavailable('joint law requires a nonempty future target')
        if state_inputs is not None:
            from .state import generate_recurrent_scenarios, replay_execution
            inputs = dict(state_inputs)
            forbidden = {'target','snapshot_id','as_of','dates','path_count','seed','evidence_class'} & set(inputs)
            if forbidden: raise ValueError('state inputs cannot override evidence-bound fields')
            generated = generate_recurrent_scenarios(target=request.target, snapshot_id=snapshot.snapshot_id,
                as_of=request.as_of, dates=tuple(origin+timedelta(days=i) for i in range((request.period_end-origin).days)),
                path_count=n_paths, seed=seed, evidence_class=evidence, **inputs)
            bundle = generated.bundle
            state_evidence = primitive(generated)
            state_evidence['replay'] = primitive(replay_execution(inputs['exposures'],inputs['events'],as_of=request.as_of))
            state_artifact = service.store.put(request.target.tenant_id,'state_evidence',state_evidence,request.target.sources,required_artifacts=material_dependencies)
            material_dependencies += (state_artifact,)
            if bundle.scenario != scenario:
                parent_artifacts.append(service.store.put(request.target.tenant_id,'joint_bundle',bundle.to_dict(),request.target.sources,required_artifacts=material_dependencies))
                material_dependencies += (parent_artifacts[-1],)
                bundle = replace(bundle,scenario=scenario,weights=() if scenario.kind == 'sensitivity' else bundle.weights,
                    parent_ids=(bundle.bundle_id,))
            if bundle.dates != dates:
                parent_artifacts.append(service.store.put(request.target.tenant_id,'joint_bundle',bundle.to_dict(),request.target.sources,required_artifacts=material_dependencies))
                material_dependencies += (parent_artifacts[-1],)
                selected = tuple(bundle.dates.index(d) for d in dates)
                bundle = replace(bundle,dates=dates,values=tuple(tuple(tuple(a[i] for i in selected) for a in path) for path in bundle.values),
                    parent_ids=(bundle.bundle_id,),procedure=ProcedureSpec('exact_target_slice',config={'parent_procedure':bundle.procedure.identity,'output_dates':dates}))
        else:
            axes = tuple(axes)
            if not axes: raise ValueError('explicit native series axes required')
            panel = []
            for axis in axes:
                identity = axis.axis_id if axis.axis_id in observations else axis.entity_id
                rows = sorted(observations.get(identity,()),key=lambda row:row.date)
                if not rows: raise ModelUnavailable('no covered history for axis '+axis.entity_id)
                try:
                    panel.append(Series(identity,tuple(r.date for r in rows),tuple(float(r.value) for r in rows)))
                except ValueError as exc:
                    raise ModelUnavailable(str(exc)) from exc
            mapped = {s.entity_id for s in panel}
            if mapped != set(observations):
                raise ValueError('axes must cover every source series exactly')
            generated = fit_joint_blocks(tuple(panel), target=request.target, snapshot_id=snapshot.snapshot_id,
                as_of=request.as_of, dates=dates, axes=axes, n_paths=n_paths, seed=seed,
                baseline=request.model, baseline_config=model_config, min_blocks=min_blocks,
                allow_direct_fallback=allow_direct_fallback, evidence_class=evidence,
                scenario=scenario, history_end=snapshot.history_end,max_history_lag_days=max_history_lag_days)
            if isinstance(generated,JointUnavailable): raise ModelUnavailable(generated.reason)
            bundle = generated
    except (ModelUnavailable,OverflowError) as exc:
        unavailable = str(exc)
        limitations.append('joint_unavailable: '+unavailable)
    if bundle is not None and workload_adjustments:
        from .context import WorkloadAdjustment
        if any(not isinstance(a,WorkloadAdjustment) for a in workload_adjustments):
            raise ValueError('explicit bound workload adjustments required')
        if len({a.adjustment_id for a in workload_adjustments}) != len(workload_adjustments) or len({a.assumption_id for a in workload_adjustments}) != len(workload_adjustments):
            raise ValueError('workload adjustment or assumption already applied')
        baseline_id = bundle.bundle_id
        parent_artifacts.append(service.store.put(request.target.tenant_id,'joint_bundle',bundle.to_dict(),request.target.sources,required_artifacts=material_dependencies))
        material_dependencies += (parent_artifacts[-1],)
        values = bundle.values
        for adjustment in workload_adjustments:
            values = tuple(tuple(tuple(exact_product(_number(v),adjustment.assumption.multiplier) for v in axis)
                                 for axis in path) for path in values)
        bundle = replace(bundle,values=values,parent_ids=(baseline_id,),
            scenario=ScenarioSpec('workload-'+digest((bundle.scenario,workload_adjustments)),kind=bundle.scenario.kind,
                                  estimand='workload' if bundle.scenario.estimand == 'baseline' else bundle.scenario.estimand,
                                  assumptions=bundle.scenario.assumptions+tuple(a.assumption.rationale for a in workload_adjustments)),
            procedure=ProcedureSpec('user_workload_multiplier',config={'baseline_id':baseline_id,'adjustments':primitive(workload_adjustments)}))
    entities = {entity:{'recorded':str(recorded_by.get(entity,Decimal(0)) if request.output == 'full_period' else Decimal(0)),
                        'future':None,'daily':None} for entity in sorted(set(observations)|set(recorded_by))}
    usage = _unavailable(unavailable or 'probability law unavailable')
    future = None
    if bundle is not None and bundle.scenario.kind == 'probability_law':
        weights = _weights(bundle.weights)
        for entity in sorted({a.entity_id for a in bundle.axes}):
            indices = tuple(i for i,a in enumerate(bundle.axes) if a.entity_id == entity)
            daily = {day.isoformat():str(_mean(tuple(exact_sum(_number(path[i][d]) for i in indices) for path in bundle.values),weights))
                     for d,day in enumerate(bundle.dates)}
            entities[entity] = {'recorded':str(recorded_by.get(entity,Decimal(0)) if request.output == 'full_period' else Decimal(0)),
                                'future':str(exact_sum(Decimal(v) for v in daily.values())), 'daily':daily}
        future = exact_sum(Decimal(v['future']) for v in entities.values() if v['future'] is not None)
        totals = tuple(exact_sum((_number(v),recorded)) for v in bundle.totals())
        usage = _summaries(totals,bundle.weights,quantiles,threshold,tail_alpha)
        usage['mean'] = str(exact_sum((recorded,future)))
    elif bundle is not None:
        limitations.append('sensitivity grid has no probability law')
    complete_target = (request.output == 'remainder' or request.period_start >= origin or
        (snapshot.ready and (not lag or (recorded_supplement is not None and recorded_supplement.ready))))
    if not complete_target and usage['mean'] is not None:
        known_plus_future_mean = usage['mean']
        usage = _unavailable('Incomplete incurred gap prevents exact full-period risk; known recorded plus future is a partial view.')
        usage['known_plus_future_mean'] = known_plus_future_mean
    usage['target_scope'] = 'exact_requested_target' if complete_target else 'incomplete_requested_target'
    usage['dates'] = [d.isoformat() for d in dates]
    bundle_artifact = service.store.put(request.target.tenant_id,'joint_bundle',bundle.to_dict(),request.target.sources,required_artifacts=material_dependencies) if bundle else None
    monetary = _unavailable('no complete commercial view supplied')
    commercial_artifact = None
    commercial_input_artifact = None
    if bundle is not None and commercial_options is not None:
        from .commercial import price_bundle
        resolved_commercial = commercial_options(bundle) if callable(commercial_options) else commercial_options
        commercial_input_artifact = service.store.put(request.target.tenant_id,'commercial_inputs',
            {'bundle_id':bundle.bundle_id,'inputs':primitive(resolved_commercial)},request.target.sources,
            required_artifacts=material_dependencies+(bundle_artifact,))
        priced = price_bundle(bundle,**resolved_commercial)
        commercial_artifact = service.store.put(request.target.tenant_id,'commercial',primitive(priced),request.target.sources,required_artifacts=(commercial_input_artifact,))
        if priced.status == 'available':
            monetary = _monetary_summaries(priced,request,origin,quantiles,monetary_threshold,tail_alpha)
        else: monetary = _unavailable(priced.reason)
    _qualify(usage)
    _qualify(monetary)
    if future is None: limitations.append('affected forecast unavailable; measured usage remains readable')
    limitations.append('conditional joint law; no empirical calibration or safe transferable headroom established')
    manifest = {'schema_version':'1.0','request':request.to_dict(),'snapshot_id':snapshot.snapshot_id,
                'evidence_class':evidence,'history_end':snapshot.history_end,'history_lag_days':lag,
                'max_history_lag_days':max_history_lag_days,'recorded_supplement_id':recorded_supplement.snapshot_id if recorded_supplement else None,
                'required_artifacts':required_artifacts,'bundle_id':bundle.bundle_id if bundle else None,'procedure':primitive(bundle.procedure) if bundle else None,
                'scenario':primitive(bundle.scenario) if bundle else primitive(scenario),
                'empirical_status':'not_empirically_qualified','process_mode':'structural_recurrent' if state_inputs is not None else 'aggregate_delivered','summary_arithmetic':'exact rational weights; 50 significant decimal digits for expectations',
                'quantiles':quantiles,'threshold':threshold,'monetary_threshold':monetary_threshold,'tail_alpha':tail_alpha,
                'output_digest':digest({'entities':entities,'usage':usage,'monetary':monetary,'limitations':limitations})}
    result = ForecastResult(digest(manifest),request.request_id,request.target,snapshot.snapshot_id,
        request.as_of,request.period_start,request.period_end,recorded,Decimal(0) if complete_target else None,
        future,None,'limited' if future is not None else 'unavailable',bundle.procedure.procedure_id if bundle else 'unavailable','mean',tuple(dict.fromkeys(limitations)))
    payload = {'schema_version':'1.0','result':result.to_dict(),'manifest':manifest,'entities':entities,
        'usage':usage,'monetary':monetary,'bundle_artifact_id':bundle_artifact,'snapshot_artifact_id':snapshot_artifact,
        'recorded_supplement_artifact_id':supplement_artifact,
        'state_artifact_id':state_artifact,'commercial_artifact_id':commercial_artifact,
        'commercial_input_artifact_id':commercial_input_artifact,'parent_bundle_artifact_ids':parent_artifacts,
        'calibration':{'status':'unavailable','reasons':['No exact-target empirical calibration evidence supplied.']},
        'coherence':'shared_path_daily_sum' if bundle else None,
        'known_plus_future':str(exact_sum((recorded,future))) if future is not None else None,
        'variable_total':str(result.variable_total) if result.variable_total is not None else None,
        'capabilities':{'mean':future is not None,'joint_paths':bundle is not None,'quantiles':bool(usage['quantiles']),
            'event_probability':usage['exceedance_probability'] is not None,'interval':False,'safe_transfer':False},
        'all_in_total':None}
    dependencies = material_dependencies+tuple(ref for ref in (bundle_artifact,commercial_input_artifact,commercial_artifact) if ref)
    payload['material_artifact_ids'] = tuple(sorted(set(dependencies)))
    artifact_id = service.store.put(request.target.tenant_id,'joint_forecast',payload,request.target.sources,required_artifacts=dependencies)
    stored = service.store.get(request.target.tenant_id,artifact_id,allowed_sources=sources)
    return json.loads(canonical_json(dict(payload,artifact_id=artifact_id,stored_at=stored['stored_at'])))


def run_joint_demo(directory, *, process='state'):
    """Local synthetic compound fixture with two complete tariff reset periods."""
    from pathlib import Path
    from datetime import date, datetime, timezone
    from .contracts import Target, ForecastRequest
    from .integration import load_snapshot
    from .service import ForecastService
    from .joint import SeriesAxis
    from .commercial import MeterKey, RateRevision, TariffCatalog, PeriodUsage
    from .pricing import PricingContract
    from .state import ExposureSpell, ExecutionMark, HurdleParameters
    if process not in {'state','aggregate'}: raise ValueError('unknown joint process')
    directory = Path(directory)
    if directory.exists() and any(directory.iterdir()):
        raise ValueError('joint demo requires a fresh output directory')
    directory.mkdir(parents=True,exist_ok=True)
    start,origin = date(2026,8,1),datetime(2026,9,30,tzinfo=timezone.utc)
    end = origin.date()+timedelta(days=4)
    target = Target('synthetic-tokens','joint-demo','metered_usage','tokens',None,('usage',),('variable',),support='nonnegative')
    request = ForecastRequest('compound-demo',target,origin,origin.date(),end,output='remainder')
    records = []
    for entity,value in (('a',2),('b',3)):
        for i in range((origin.date()-start).days):
            day = start+timedelta(days=i)
            records.append({'record_id':entity+':'+day.isoformat(),'source_id':'usage','entity_id':entity,
                'service_date':day.isoformat(),'value':str(value),'unit':'tokens','currency':None,'category':'variable',
                'known_at':origin.isoformat(),'ingested_at':origin.isoformat(),'processed_at':origin.isoformat(),
                'measure':'metered_usage'})
    (directory/'usage.json').write_text(json.dumps({'schema_version':'1.0','records':records})+'\n')
    config = {'schema_version':'1.0','request':request.to_dict(),'source_id':'usage','history_start':start.isoformat(),
        'export':'usage.json','evidence_class':'synthetic_fixture','coverage':[{'source_id':'usage','start':start.isoformat(),
        'end':origin.date().isoformat(),'state':'complete','maturity':'finalized','known_at':origin.isoformat()}]}
    config_path = directory/'joint-config.json'
    config_path.write_text(json.dumps(config,indent=2)+'\n')
    request,snapshot,store,policy = load_snapshot(config_path,directory/'joint.sqlite')
    options = {'axes':tuple(SeriesAxis(e,'input','model','pool','tokens') for e in sorted({r.entity_id for r in snapshot.daily}))}
    if process == 'state':
        options = {'state_inputs':{'exposures':tuple(ExposureSpell('access-'+e,e,e,start,end,origin,True,prior_use=True) for e in ('a','b')),
            'events':(), 'parameters':tuple(HurdleParameters(e,1,marks=(ExecutionMark(v),)) for e,v in (('a',2),('b',3)))}}
    def commercial(bundle):
        pools = tuple(sorted({a.pool for a in bundle.axes}))
        revisions,prefixes = [],[]
        for pool in pools:
            keys = tuple(sorted({MeterKey(a.configuration,a.meter,a.unit,a.pool) for a in bundle.axes if a.pool == pool},
                                key=lambda k:(k.configuration,k.meter,k.unit,k.pool)))
            for i in range(2):
                left,right = origin.date()+timedelta(days=i*2),origin.date()+timedelta(days=(i+1)*2)
                contract = PricingContract('synthetic-reset-%d' % i,'1','USD','tokens',left,right,origin,
                                           Decimal(5),Decimal(2),Decimal(3))
                for j,key in enumerate(keys):
                    revisions.append(RateRevision('rate-%s-%d-%d' % (pool,i,j),key,Decimal(1),left,right,origin,contract))
                prefixes.extend(PeriodUsage(path,pool,left,right,left,keys,(),(),(),True) for path in bundle.path_ids)
        return {'catalog':TariffCatalog(tuple(revisions)), 'prefixes':tuple(prefixes)}
    service = ForecastService(store)
    result = service.run_joint(request,snapshot,allowed_sources={'usage'},n_paths=8,seed=7,
        commercial_options=commercial,monetary_threshold=Decimal(25),threshold=Decimal(19),**options,**policy)
    retrieved = service.retrieve(target.tenant_id,result['artifact_id'],allowed_sources={'usage'},now=origin)
    report = {'process':process,'evidence_class':result['manifest']['evidence_class'],
        'artifact_id':result['artifact_id'],'retrieved_artifact_id':retrieved['artifact_id'],
        'bundle_artifact_id':result['bundle_artifact_id'],'commercial_artifact_id':result['commercial_artifact_id'],
        'state_artifact_id':result['state_artifact_id'],'snapshot_artifact_id':result['snapshot_artifact_id'],
        'usage_mean':result['usage']['mean'],'conditional_contract_mean':result['monetary']['mean'],
        'monetary_exceedance_probability':result['monetary']['exceedance_probability'],
        'monetary_expected_shortfall':result['monetary']['expected_shortfall'],
        'safe_transfer':False,'qualification':'synthetic fixture; conditional law, no empirical enterprise qualification'}
    (directory/'joint-demo.json').write_text(json.dumps(report,indent=2)+'\n')
    return report
