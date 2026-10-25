"""Availability-aware evaluation primitives and a bounded runnable demonstration.

No retrospective/current export is silently treated as an as-of archive. The
convenience runner without observation versions is explicitly idealized. Final
selection is locked on development scores; unsupported metrics remain None.
Every public target/split interval is half-open [target_start, target_end) in UTC.
"""
from __future__ import annotations
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
import hashlib
import json
import math
import random
from time import perf_counter
from typing import Optional

from .contracts import exact_sum


def _aware(value):
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError('timezone-aware timestamp required')


def _finite(values):
    if any(not math.isfinite(x) for x in values):
        raise ValueError('finite metric values required')


@dataclass(frozen=True)
class LabelVersion:
    example_id: str
    entity_id: str
    target_start: date
    target_end: date
    available_at: datetime
    mature_at: datetime
    value: float
    revision: int = 1
    status: str = 'mature'

    def __post_init__(self):
        _aware(self.available_at)
        _aware(self.mature_at)
        _finite((self.value,))
        if self.target_end <= self.target_start or self.available_at > self.mature_at or self.mature_at.astimezone(timezone.utc).date() < self.target_end:
            raise ValueError('invalid label period or maturity ordering')
        if self.revision < 1 or self.status not in ('mature','pending','disputed'):
            raise ValueError('invalid revision or label status')


class LabelQueue:
    """Immutable version inventory; each query returns its own scoring vintage."""
    def __init__(self, versions):
        unique = {}
        identity = {}
        for value in versions:
            key=(value.example_id,value.revision)
            if key in unique and unique[key] != value:
                raise ValueError('conflicting label revision')
            target=(value.entity_id,value.target_start,value.target_end)
            if value.example_id in identity and identity[value.example_id] != target:
                raise ValueError('label revision changed target identity')
            unique[key]=value
            identity[value.example_id]=target
        self.versions=tuple(sorted(unique.values(), key=lambda x:(x.example_id,x.revision)))

    def latest(self, cutoff):
        _aware(cutoff)
        out={}
        for v in self.versions:
            if v.available_at <= cutoff and (v.example_id not in out or v.revision > out[v.example_id].revision):
                out[v.example_id]=v
        return out

    def fit_labels(self, cutoff, purge_period=None):
        result=[]
        for v in self.latest(cutoff).values():
            if v.status != 'mature' or v.mature_at>cutoff or v.target_end>cutoff.astimezone(timezone.utc).date():
                continue
            if purge_period and v.target_start < purge_period[1] and v.target_end > purge_period[0]:
                continue
            result.append(v)
        return tuple(sorted(result,key=lambda x:x.example_id))

    def score_labels(self, as_of):
        return self.fit_labels(as_of)


@dataclass(frozen=True)
class SplitManifest:
    development: tuple
    calibration: tuple
    final: tuple
    attribution: str = 'origin_time'

    def __post_init__(self):
        periods=(self.development,self.calibration,self.final)
        if any(len(p)!=2 or p[0]>=p[1] for p in periods):
            raise ValueError('invalid split interval')
        if self.development[1] > self.calibration[0] or self.calibration[1] > self.final[0]:
            raise ValueError('D/C/F target windows must be disjoint and chronological')

    def phase(self, start, end):
        for name,period in (('D',self.development),('C',self.calibration),('F',self.final)):
            if period[0] <= start < end <= period[1]:
                return name
        raise ValueError('target straddles or falls outside split boundaries')


@dataclass(frozen=True)
class PopulationMember:
    entity_id: str
    split: str
    company_lineage: str
    derivative_ids: tuple = ()


def validate_population(members):
    """Unseen-population manifest: lineage and fitted derivatives stay grouped."""
    groups={}
    entities={}
    for member in members:
        if member.split not in ('D','C','F') or not member.company_lineage:
            raise ValueError('known population split and lineage required')
        if member.entity_id in entities and entities[member.entity_id]!=member.split:
            raise ValueError('entity crosses population holdout')
        entities[member.entity_id]=member.split
        for key in ('company:'+member.company_lineage,)+tuple('derivative:'+x for x in member.derivative_ids):
            if key in groups and groups[key]!=member.split:
                raise ValueError('lineage/derivative crosses population holdout')
            groups[key]=member.split
    return True


class LockedSelection:
    """One preaggregated development loss per registered complete procedure.

    Folds/seeds must be aggregated before recording. Distinct configurations
    require distinct candidate identities; a lucky retry cannot replace loss.
    """
    def __init__(self,candidates,search_budget,seed):
        if not candidates or len(set(candidates)) != len(candidates) or search_budget < 1:
            raise ValueError('unique candidate registry and positive search budget required')
        self.candidates=tuple(candidates)
        self.search_budget=search_budget
        self.seed=seed
        self.trials=[]
        self.selected=None
        self.final_started=False

    @property
    def total_cost(self):
        return sum(t['cost'] for t in self.trials)

    def record(self,candidate,loss,*,phase,cost=0,latency_seconds=0,failure=None):
        if phase!='D' or self.selected is not None or self.final_started:
            raise ValueError('selection may read development only, before freeze')
        if candidate not in self.candidates or len(self.trials)>=self.search_budget:
            raise ValueError('unregistered trial or exhausted search budget')
        if any(t['candidate']==candidate for t in self.trials):
            raise ValueError('duplicate candidate: aggregate development trials before recording')
        _finite((cost,latency_seconds))
        if cost<0 or latency_seconds<0 or (loss is not None and (not math.isfinite(loss) or loss<0)):
            raise ValueError('invalid loss or resource cost')
        self.trials.append(dict(candidate=candidate,loss=loss,cost=cost,latency_seconds=latency_seconds,failure=failure,seed=self.seed))

    def freeze(self):
        if self.selected is None:
            eligible=[t for t in self.trials if t['loss'] is not None and t['failure'] is None]
            if not eligible:
                raise ValueError('no eligible development candidate')
            self.selected=min(eligible,key=lambda x:(x['loss'],self.candidates.index(x['candidate'])))['candidate']
        return self.selected

    def begin_final(self):
        if self.selected is None or self.final_started:
            raise ValueError('final requires locked procedure and can run once')
        self.final_started=True
        return self.selected


def point_metrics(predictions,actuals):
    if len(predictions)!=len(actuals):
        raise ValueError('paired observations required')
    _finite(tuple(predictions)+tuple(actuals))
    n=len(actuals)
    errors=[p-y for p,y in zip(predictions,actuals)]
    scale=sum(abs(y) for y in actuals)
    return dict(n=n,mae=sum(abs(e) for e in errors)/n if n else None,
                rmse=math.sqrt(sum(e*e for e in errors)/n) if n else None,
                bias=sum(errors)/n if n else None,
                wape=sum(abs(e) for e in errors)/scale if scale else None)


def quantile_metrics(quantiles, actuals):
    levels=sorted(quantiles)
    _finite(actuals)
    if not levels or any(not 0<q<1 or len(quantiles[q])!=len(actuals) for q in levels):
        raise ValueError('common nonempty quantile grid and paired outcomes required')
    for q in levels:
        _finite(quantiles[q])
    if any(quantiles[a][i]>quantiles[b][i] for a,b in zip(levels,levels[1:]) for i in range(len(actuals))):
        raise ValueError('crossed quantiles')
    scores={q:(sum(max(q*(y-p),(q-1)*(y-p)) for p,y in zip(quantiles[q],actuals))/len(actuals) if actuals else None) for q in levels}
    return dict(n=len(actuals),pinball_by_quantile=scores,pinball_mean=sum(scores.values())/len(scores) if actuals else None)


def interval_metrics(lower,upper,actuals,alpha):
    if not 0<alpha<1 or len(lower)!=len(upper) or len(lower)!=len(actuals):
        raise ValueError('paired interval observations and valid alpha required')
    _finite(tuple(lower)+tuple(upper)+tuple(actuals))
    if any(a>b for a,b in zip(lower,upper)):
        raise ValueError('inverted interval')
    n=len(actuals)
    widths=[b-a for a,b in zip(lower,upper)]
    scores=[b-a+2/alpha*(a-y if y<a else y-b if y>b else 0) for a,b,y in zip(lower,upper,actuals)]
    return dict(n=n,coverage=sum(a<=y<=b for a,b,y in zip(lower,upper,actuals))/n if n else None,
                width=sum(widths)/n if n else None,interval_score=sum(scores)/n if n else None)


def weighted_interval_score(median, intervals, actuals):
    """WIS = (0.5|y-m| + sum(alpha/2 IS_alpha))/(K+0.5)."""
    if len(median)!=len(actuals) or not intervals:
        raise ValueError('median and at least one central interval required')
    base=point_metrics(median,actuals)['mae']
    if base is None:
        return None
    score=.5*base
    for alpha,(lower,upper) in intervals.items():
        if any(not lo<=m<=hi for lo,m,hi in zip(lower,median,upper)):
            raise ValueError('median outside central interval')
        score+=alpha/2*interval_metrics(lower,upper,actuals,alpha)['interval_score']
    return score/(len(intervals)+.5)


def event_metrics(probabilities,events,threshold=.5):
    if len(probabilities)!=len(events) or not 0<=threshold<=1:
        raise ValueError('paired events required')
    _finite(probabilities)
    if any(not 0<=p<=1 for p in probabilities) or any(type(y) is not bool for y in events):
        raise ValueError('valid probabilities and boolean event labels required')
    n=len(events)
    positives=sum(events)
    warnings=sum(p>=threshold for p in probabilities)
    tp=sum(p>=threshold and y for p,y in zip(probabilities,events))
    log_scores=[]
    for p,y in zip(probabilities,events):
        mass=p if y else 1-p
        log_scores.append(-math.log(mass) if mass else math.inf)
    log_loss=sum(log_scores)/n if n else None
    return dict(n=n,brier=sum((p-int(y))**2 for p,y in zip(probabilities,events))/n if n else None,
                log_loss=log_loss if log_loss is None or math.isfinite(log_loss) else None,
                log_loss_status='infinite' if log_loss is not None and not math.isfinite(log_loss) else 'finite' if n else 'unavailable',
                prevalence=positives/n if n else None,recall=tp/positives if positives else None,
                precision=tp/warnings if warnings else None,false_alarms_per_eligible=(warnings-tp)/n if n else None)


@dataclass(frozen=True)
class Opportunity:
    opportunity_id: str
    entity_id: str
    company_id: str
    target_start: date
    target_end: date
    output_status: str
    prediction: Optional[float]
    actual: Optional[float]
    label_status: str
    cohort: str = 'warm'
    latency_seconds: float = 0.
    origin_budget: Optional[float] = None
    label_revision: Optional[int] = None
    failure: Optional[str] = None
    statistic: str = 'mean'

    def __post_init__(self):
        if self.output_status not in ('on_time','late','stale','unavailable','failed','missing'):
            raise ValueError('unknown output state')
        if self.label_status not in ('mature','pending','disputed','missing'):
            raise ValueError('unknown label state')
        if self.actual is not None and self.label_status!='mature':
            raise ValueError('immature actual cannot be scored as settled')
        if self.target_end<=self.target_start:
            raise ValueError('invalid target period')
        _finite(tuple(x for x in (self.prediction,self.actual,self.latency_seconds,self.origin_budget) if x is not None))


def summarize_opportunities(opportunities, abstention_cost=None, _cohorts=True):
    rows=tuple(opportunities)
    if len({x.opportunity_id for x in rows})!=len(rows):
        raise ValueError('opportunity IDs must be unique')
    scored=[r for r in rows if r.prediction is not None and r.actual is not None and r.label_status=='mature']
    metrics=point_metrics(tuple(r.prediction for r in scored),tuple(r.actual for r in scored))
    timely_scored=[r for r in scored if r.output_status=='on_time']
    timely_metrics=point_metrics(tuple(r.prediction for r in timely_scored),tuple(r.actual for r in timely_scored))
    issued=sum(r.prediction is not None for r in rows)
    periods=sorted(set((r.target_start,r.target_end) for r in rows))
    blocks=0
    last=None
    for start,end in sorted(periods,key=lambda p:p[1]):
        if last is None or start>=last:
            blocks+=1
            last=end
    ontime=sum(r.output_status=='on_time' and r.prediction is not None for r in rows)
    # An explicit cost enables all-opportunity scoring only when every label is known.
    utility=None
    if abstention_cost is not None:
        if abstention_cost<0 or not math.isfinite(abstention_cost):
            raise ValueError('nonnegative abstention cost required')
        if rows and all(r.actual is not None and r.label_status=='mature' for r in rows):
            utility=sum(abs(r.prediction-r.actual) if r.output_status=='on_time' and r.prediction is not None else abstention_cost for r in rows)/len(rows)
    result=dict(scheduled=len(rows),scored=len(scored),issued=issued,unissued=len(rows)-issued,
                on_time_issued=ontime,mature=sum(r.actual is not None and r.label_status=='mature' for r in rows),
                output_states=dict(Counter(r.output_status for r in rows)),
                label_states=dict(Counter(r.label_status for r in rows)),availability=ontime/len(rows) if rows else None,
                maturity_coverage=sum(r.label_status=='mature' for r in rows)/len(rows) if rows else None,
                distinct_companies=len({r.company_id for r in rows}),distinct_teams=len({r.entity_id for r in rows}),
                distinct_target_periods=len(periods),nonoverlapping_blocks=blocks,point=metrics,
                all_issued_point=metrics,on_time_point=timely_metrics,
                point_population='all issued predictions with mature truth, including late/stale; point aliases all_issued_point',
                all_case_utility=utility,
                inference='descriptive only; dependent rows are not independent evidence',
                mean_latency_seconds=sum(r.latency_seconds for r in rows)/len(rows) if rows else None)
    if _cohorts:
        result['cohorts']={c:summarize_opportunities([r for r in rows if r.cohort==c],abstention_cost,False) for c in sorted({r.cohort for r in rows})}
        result['companies']={c:summarize_opportunities([r for r in rows if r.company_id==c],abstention_cost,False) for c in sorted({r.company_id for r in rows})}
        team_errors=defaultdict(list)
        for r in scored:
            team_errors[r.entity_id].append(abs(r.prediction-r.actual))
        result['team_macro_mae']=sum(sum(v)/len(v) for v in team_errors.values())/len(team_errors) if team_errors else None
        spend=sum(abs(r.actual) for r in scored)
        result['spend_weighted_mae']=sum(abs(r.actual)*abs(r.prediction-r.actual) for r in scored)/spend if spend else None
        result['statistic_counts']=dict(Counter(r.statistic for r in rows if r.prediction is not None))
    return result


def selected_donor_diagnostics(selected):
    """Rows (origin budget, withdrawal, matched mature outcome), already selected.

    Accounting exposure holds the outcome fixed; no causal/safety interpretation.
    """
    values=tuple(selected)
    for b,d,y in values:
        _finite((b,d,y))
        if b<0 or not 0<=d<=b:
            raise ValueError('withdrawal outside allocation')
    before=sum(max(0,y-b) for b,d,y in values)
    after=sum(max(0,y-(b-d)) for b,d,y in values)
    return dict(selected_n=len(values),original_exposure=before,retained_exposure=after,increased_exposure=after-before,
                validated_safe_transfer=False,causal_savings=None)


def promotion_decision(metrics,thresholds,*,synthetic=False,real_population_support=False,capability='point'):
    reasons=[]
    if synthetic:
        reasons.append('synthetic evidence')
    if not real_population_support:
        reasons.append('representative population support missing')
    required={'max_mae','max_abs_bias','min_availability','max_latency_seconds'}
    if capability=='interval':
        required|={'min_coverage','max_width','max_interval_score'}
    elif capability=='event_probability':
        required|={'max_brier','min_events','min_recall','max_false_alarms_per_eligible'}
    elif capability!='point':
        reasons.append('unsupported promotion capability')
    for key in sorted(required|set(thresholds)):
        if not key.startswith(('min_','max_')) or len(key)<=4:
            raise ValueError('threshold keys require min_ or max_ and a metric name')
        limit=thresholds.get(key)
        if limit is None:
            reasons.append('unset mandatory threshold: '+key)
            continue
        if not math.isfinite(limit):
            raise ValueError('finite thresholds required')
        metric=key[4:]
        value=metrics.get(metric)
        if value is None:
            reasons.append('unavailable metric: '+metric)
        elif not math.isfinite(value):
            reasons.append('nonfinite metric: '+metric)
        elif (key.startswith('max_') and value>limit) or (key.startswith('min_') and value<limit):
            reasons.append('failed threshold: '+key)
    return dict(promoted=not reasons,capability=capability,reasons=reasons)


def _midnight(d):
    return datetime.combine(d,time(),timezone.utc)


def evaluate_rolling(series_by_entity, origins, horizon, candidates, score_as_of, *, seed=0,
                     labels=None, observation_labels=None, cohorts=None, companies=None, configs=None,
                     scheduled_entities=None, history_ends=None, max_history_lag_days=0):
    """Replay one origin/entity opportunity per candidate, including failures.

    Origins are first forecast dates. Inputs end the preceding day. Explicit
    daily observation labels reconstruct availability/maturity; without them the
    series is an idealized next-midnight-ready archive, clearly labeled as such.
    Labels supplied by callers replace generated labels, never fill missing truth.
    Explicit scheduled_entities freezes the origin population independently of
    current source refreshes; a missing entity remains an unavailable opportunity.
    history_ends maps origins to explicit exclusive mature training watermarks.
    A delayed watermark requires the same 0..30-day lag policy as serving.
    Predict across the bridge, then score only exact future target dates.
    """
    from .models import Series, forecast, ModelUnavailable
    _aware(score_as_of)
    if horizon<1 or not candidates or not origins or len(set(candidates))!=len(candidates) or len(set(origins))!=len(origins):
        raise ValueError('positive horizon and unique nonempty origins/candidates required')
    if type(max_history_lag_days) is not int or not 0<=max_history_lag_days<=30:
        raise ValueError('history lag policy must be an integer from 0 to 30 days')
    history_ends={} if history_ends is None else dict(history_ends)
    if set(history_ends)-set(origins):
        raise ValueError('history watermark origin is not scheduled')
    for origin in origins:
        end=history_ends.get(origin,origin)
        if type(end) is not date or not 0<=(origin-end).days<=max_history_lag_days:
            raise ValueError('daily history watermark exceeds explicit lag policy')
    cohorts=cohorts or {}
    companies=companies or {}
    configs=configs or {}
    source={s.entity_id:s for s in series_by_entity}
    if len(source)!=len(series_by_entity):
        raise ValueError('duplicate source entity')
    entities=tuple(sorted(source)) if scheduled_entities is None else tuple(scheduled_entities)
    if not entities or len(set(entities))!=len(entities) or any(not isinstance(e,str) or not e for e in entities):
        raise ValueError('nonempty unique scheduled entities required')
    idealized=observation_labels is None
    if observation_labels is None:
        observation_labels=tuple(LabelVersion('daily:'+s.entity_id+':'+d.isoformat(),s.entity_id,d,d+timedelta(days=1),_midnight(d+timedelta(days=1)),_midnight(d+timedelta(days=1)),v) for s in source.values() for d,v in zip(s.dates,s.values))
    observed=LabelQueue(observation_labels)
    if any(v.target_end-v.target_start!=timedelta(days=1) for v in observed.versions):
        raise ValueError('observation labels must be daily')
    daily_identity={}
    for v in observed.versions:
        key=(v.entity_id,v.target_start)
        if key in daily_identity and daily_identity[key]!=v.example_id:
            raise ValueError('duplicate daily observation identities')
        daily_identity[key]=v.example_id
    if labels is None:
        if not idealized:
            raise ValueError('versioned replay requires explicit cumulative labels; current Series is not delivered truth')
        generated=[]
        for s in source.values():
            values=dict(zip(s.dates,s.values))
            for origin in origins:
                dates=tuple(origin+timedelta(days=i) for i in range(horizon))
                if all(d in values for d in dates):
                    end=origin+timedelta(days=horizon)
                    generated.append(LabelVersion(s.entity_id+':'+origin.isoformat(),s.entity_id,origin,end,_midnight(end),_midnight(end),sum(values[d] for d in dates)))
        labels=generated
    truths=LabelQueue(labels)
    expected={entity+':'+origin.isoformat():(entity,origin,origin+timedelta(days=horizon)) for entity in entities for origin in origins}
    for v in truths.versions:
        if v.example_id in expected and expected[v.example_id]!=(v.entity_id,v.target_start,v.target_end):
            raise ValueError('scoring label target identity does not match opportunity')
    latest=truths.latest(score_as_of)
    mature={v.example_id:v for v in truths.score_labels(score_as_of)}
    reports={name:[] for name in candidates}
    input_manifests=[]
    model_manifests=[]
    for origin in sorted(origins):
        cutoff=_midnight(origin)
        history_end=history_ends.get(origin,origin)
        lag=(origin-history_end).days
        panel=[]
        available=observed.fit_labels(cutoff, (origin,origin+timedelta(days=horizon)))
        for entity in sorted(entities):
            daily=sorted((v for v in available if v.entity_id==entity and v.target_end<=history_end),key=lambda x:x.target_start)
            if daily:
                # Keep maximal complete suffix through the declared mature
                # watermark; neither stale values nor gaps become new history.
                bydate={v.target_start:v for v in daily}
                tail=[]
                cursor=history_end-timedelta(days=1)
                while cursor in bydate:
                    tail.append(bydate[cursor])
                    cursor-=timedelta(days=1)
                if tail:
                    tail.reverse()
                    panel.append(Series(entity,tuple(v.target_start for v in tail),tuple(v.value for v in tail)))
        panel_by_id={s.entity_id:s for s in panel}
        input_payload=[(s.entity_id,[d.isoformat() for d in s.dates],s.values) for s in panel]
        digest=hashlib.sha256(json.dumps(input_payload,sort_keys=True).encode()).hexdigest()
        input_manifests.append(dict(origin=origin.isoformat(),history_end=history_end.isoformat(),
                                    history_lag_days=lag,max_history_lag_days=max_history_lag_days,
                                    input_sha256=digest,available_observation_versions=[(v.example_id,v.revision) for v in available]))
        dates=tuple(origin+timedelta(days=i) for i in range(horizon))
        all_dates=tuple(history_end+timedelta(days=i) for i in range(lag+horizon))
        for entity in sorted(entities):
            key=entity+':'+origin.isoformat()
            truth=mature.get(key)
            known=latest.get(key)
            status='mature' if truth else 'disputed' if known and known.status=='disputed' else 'pending' if known or any(v.example_id==key for v in truths.versions) else 'missing'
            for name in candidates:
                started=perf_counter()
                prediction=None
                statistic='mean'
                failure=None
                output='on_time'
                try:
                    if entity not in panel_by_id:
                        raise ModelUnavailable('no mature contiguous history through declared watermark')
                    config=dict(configs.get(name,{}))
                    if name in ('tabular_mean','tabular_direct_cumulative'):
                        config.setdefault('seed',seed)
                    pred=forecast(panel_by_id[entity],all_dates,name,config=config,panel=tuple(panel))
                    if pred.daily_values is None:
                        if lag:
                            raise ModelUnavailable('direct cumulative prediction cannot slice delayed history bridge')
                        prediction=pred.cumulative_value
                    else:
                        selected=tuple(v for d,v in zip(pred.dates,pred.daily_values) if d in dates)
                        if len(selected)!=horizon:
                            raise ModelUnavailable('prediction does not span exact target dates')
                        # Serving reduces the decimal rendering of each daily
                        # prediction exactly, rather than its binary float sum.
                        target_prediction=float(exact_sum(Decimal(str(v)) for v in selected))
                        if not math.isfinite(target_prediction):
                            raise ModelUnavailable('nonfinite cumulative target prediction')
                        prediction=target_prediction
                    statistic=pred.statistic
                    model_manifests.append(dict(opportunity_id=key,model_name=name,input_sha256=digest,
                                                history_end=history_end.isoformat(),history_lag_days=lag,
                                                prediction_dates=[d.isoformat() for d in dates],
                                                bridge_dates=[d.isoformat() for d in all_dates if d<origin],
                                                metadata=dict(pred.metadata),coherence=pred.coherence,
                                                statistic=pred.statistic,limitations=list(pred.limitations)))
                except ModelUnavailable as exc:
                    output='unavailable'
                    failure=str(exc)
                except Exception as exc:
                    output='failed'
                    failure=type(exc).__name__+': '+str(exc)
                reports[name].append(Opportunity(key,entity,companies.get(entity,entity),origin,origin+timedelta(days=horizon),output,prediction,truth.value if truth else None,status,cohorts.get(entity,'warm'),perf_counter()-started,label_revision=truth.revision if truth else None,failure=failure,statistic=statistic))
    return dict(seed=seed,horizon=horizon,score_as_of=score_as_of.isoformat(),scheduled_entities=entities,
                history_mode='idealized_next_midnight_availability' if idealized else 'versioned_as_of_observations',
                input_manifests=input_manifests,model_manifests=model_manifests,
                candidates={name:dict(summary=summarize_opportunities(rows),rows=[_json_row(r) for r in rows]) for name,rows in reports.items()})


def _json_row(row):
    value=asdict(row)
    value['target_start']=row.target_start.isoformat()
    value['target_end']=row.target_end.isoformat()
    return value


def synthetic_evaluation(seed=0):
    """A deterministic labeled fixture; model ranking is not enterprise evidence."""
    from .models import Series
    rng=random.Random(seed)
    dates=tuple(date(2025,1,1)+timedelta(days=i) for i in range(230))
    series=tuple(Series(entity,dates,tuple(base+.1*i+(4 if d.weekday()<5 else -3)+rng.uniform(-1,1) for i,d in enumerate(dates))) for entity,base in (('research',30),('product',20)))
    candidates=('last_observation','trailing_mean','weekday_mean','seasonal_naive','exponential_smoothing','calendar_regression','local_linear_trend','pooled_ridge','tabular_mean','tabular_direct_cumulative')
    split=SplitManifest((dates[70],dates[119]),(dates[126],dates[168]),(dates[175],dates[217]))
    origins={'D':tuple(dates[i] for i in range(70,113,7)),'C':tuple(dates[i] for i in range(126,162,7)),'F':tuple(dates[i] for i in range(175,211,7))}
    for phase,values in origins.items():
        for origin in values:
            assert split.phase(origin,origin+timedelta(days=7))==phase
    selector=LockedSelection(candidates,len(candidates),seed)
    dev=evaluate_rolling(series,origins['D'],7,candidates,_midnight(dates[125]),seed=seed,companies={'research':'synthetic-company','product':'synthetic-company'})
    for name,data in dev['candidates'].items():
        summary=data['summary']
        # A candidate must cover every development opportunity to be selectable;
        # conditional accuracy alone cannot beat a complete eligible baseline.
        loss=summary['point']['mae'] if summary['availability']==1 and summary['maturity_coverage']==1 else None
        selector.record(name,loss,phase='D',cost=len(data['rows']),latency_seconds=sum(r['latency_seconds'] for r in data['rows']),failure=None if loss is not None else 'incomplete development service')
    winner=selector.freeze()
    calibration=evaluate_rolling(series,origins['C'],7,(winner,),_midnight(dates[174]),seed=seed,companies={'research':'synthetic-company','product':'synthetic-company'})
    selector.begin_final()
    final=evaluate_rolling(series,origins['F'],7,(winner,),_midnight(dates[229]),seed=seed,companies={'research':'synthetic-company','product':'synthetic-company'})
    summary=final['candidates'][winner]['summary']
    company_series=Series('synthetic-company',dates,tuple(sum(s.values[i] for s in series) for i in range(len(dates))))
    company_final=evaluate_rolling((company_series,),origins['F'],7,(winner,),_midnight(dates[229]),seed=seed)
    def restore(row):
        fields=dict(row)
        fields['target_start']=date.fromisoformat(fields['target_start'])
        fields['target_end']=date.fromisoformat(fields['target_end'])
        return Opportunity(**fields)
    granularity=company_comparison(tuple(restore(r) for r in final['candidates'][winner]['rows']),
                                  tuple(restore(r) for r in company_final['candidates'][winner]['rows']),
                                  {'synthetic-company':('research','product')})
    return dict(evidence='synthetic_mechanism_demo',seed=seed,candidates=candidates,selected_model=winner,
                selection_rule='minimum development cumulative MAE among full-availability candidates; registry order breaks ties',
                procedure='expanding mature daily history; refit each origin; frozen model/configuration; no final selection',
                split_manifest={name:[d.isoformat() for d in p] for name,p in (('D',split.development),('C',split.calibration),('F',split.final))},
                trials=selector.trials,search_cost=dict(unit='model fit attempts',total=selector.total_cost,tokens=0,human_cost=None),
                development=dev,calibration=calibration,final=summary,final_rows=final['candidates'][winner]['rows'],company_comparison=granularity,
                uncertainty='not promoted: expanding refits require separate uncertainty qualification; point evaluation only',
                promotion=promotion_decision({'mae':summary['point']['mae'],'availability':summary['availability']},{},synthetic=True),
                limitations=['one synthetic company, no enterprise superiority','no cold-company claim','latency measured locally, not a service SLO','no cost/finance thresholds supplied'])


@dataclass(frozen=True)
class ManagerForecast:
    manager_id: str
    issued_at: datetime
    prediction: float
    purpose: str
    target: tuple

    def __post_init__(self):
        _aware(self.issued_at)
        _finite((self.prediction,))
        if len(self.target)!=5:
            raise ValueError('target requires unit, basis, start, end, statistic')


def score_manager_forecast(forecast, label, score_as_of, expected_target):
    """Only original predictive statements on exactly matching targets qualify."""
    _aware(score_as_of)
    if forecast.purpose!='prediction':
        raise ValueError('a budget request is not a predictive forecast')
    if forecast.target != expected_target or forecast.target[2:4] != (label.target_start,label.target_end):
        raise ValueError('manager predictive target/unit/statistic mismatch')
    if forecast.issued_at>_midnight(label.target_start):
        raise ValueError('retrospective manager forecast cannot score future prediction')
    if forecast.issued_at>score_as_of or label.available_at>score_as_of or label.mature_at>score_as_of or label.status!='mature':
        return dict(status='pending',metrics=None)
    return dict(status='mature',metrics=point_metrics((forecast.prediction,),(label.value,)),label_revision=label.revision)


@dataclass(frozen=True)
class WarningRecord:
    event_id: str
    origin_budget_version: str
    origin_budget: float
    issued_at: datetime
    target_end: date
    warned: bool
    actual: Optional[float]
    retracted: bool = False

    def __post_init__(self):
        _aware(self.issued_at)
        _finite(tuple(x for x in (self.origin_budget,self.actual) if x is not None))
        if not self.event_id or not self.origin_budget_version or type(self.warned) is not bool:
            raise ValueError('warning needs immutable event/budget identity')


def warning_diagnostics(warnings):
    """Scores fixed origin-threshold events; revised funding is a separate event.

    Event IDs group repeated predictions of the *same* target and origin budget.
    An outcome remains pending until a caller supplies its mature target value.
    """
    grouped=defaultdict(list)
    for w in warnings:
        grouped[w.event_id].append(w)
    events=[]
    predictions=[]
    pending=0
    pending_warned=0
    duplicates=0
    retracted=0
    lead={}
    for event_id,rows in grouped.items():
        target={(r.origin_budget_version,r.origin_budget,r.target_end) for r in rows}
        if len(target)!=1:
            raise ValueError('warning event origin budget or target changed')
        actuals={r.actual for r in rows if r.actual is not None}
        if len(actuals)>1:
            raise ValueError('score warning outcomes in a single revision vintage')
        issued=sorted((r for r in rows if r.warned),key=lambda r:r.issued_at)
        duplicates+=max(0,len(issued)-1)
        retracted+=sum(r.retracted for r in rows)
        timely=[r for r in issued if r.issued_at<_midnight(r.target_end)]
        if timely:
            lead[event_id]=(_midnight(timely[0].target_end)-timely[0].issued_at).total_seconds()/86400
        if not actuals:
            pending+=1
            pending_warned+=bool(timely)
            continue
        events.append(next(iter(actuals))>rows[0].origin_budget)
        predictions.append(1. if timely else 0.)
    scores=event_metrics(predictions,events)
    known_false_alarms=sum(bool(p) and not event for p,event in zip(predictions,events))
    eligible=len(grouped)
    false_alarm_bounds=(known_false_alarms/eligible,(known_false_alarms+pending_warned)/eligible) if eligible else None
    return dict(eligible_events=len(grouped),mature_events=len(events),pending_events=pending,
                recall=scores['recall'],recall_denominator_mature_breaches=sum(events),
                false_alarms_per_mature=scores['false_alarms_per_eligible'],
                false_alarm_mature_denominator=len(events),known_false_alarms=known_false_alarms,
                pending_warned_events=pending_warned,
                false_alarms_per_eligible=known_false_alarms/eligible if eligible and not pending else None,
                false_alarms_per_eligible_bounds=false_alarm_bounds,
                prevalence=scores['prevalence'],duplicate_warnings=duplicates,retracted_warnings=retracted,
                recall_and_prevalence_population='mature events only; pending outcomes are unknown',
                first_warning_lead_days=lead,review_effort=None,
                threshold_basis='frozen origin budget; no causal intervention claim')


def company_comparison(team_rows, direct_rows, company_members):
    """Compare company-target losses without mixing component errors into them.

    Membership is the frozen origin population supplied by the evaluation design.
    Missing component rows invalidate that aggregate, never imply zero spending.
    """
    grouped=defaultdict(list)
    for r in team_rows:
        grouped[(r.company_id,r.target_start,r.target_end)].append(r)
    for r in direct_rows:
        grouped.setdefault((r.company_id,r.target_start,r.target_end),[])
    bottom=[]
    for (company,start,end),rows in sorted(grouped.items()):
        if company not in company_members:
            raise ValueError('company population manifest missing')
        expected=set(company_members[company])
        observed=[r.entity_id for r in rows]
        if len(set(observed))!=len(observed) or not set(observed).issubset(expected):
            raise ValueError('duplicate/unregistered company component')
        complete=set(observed)==expected and bool(expected)
        predictions=complete and all(r.prediction is not None for r in rows)
        mature=complete and all(r.label_status=='mature' and r.actual is not None for r in rows)
        ontime=predictions and all(r.output_status=='on_time' for r in rows)
        bottom.append(Opportunity(company+':'+start.isoformat()+':'+end.isoformat(),company,company,start,end,
                                  'on_time' if ontime else 'late' if predictions else 'missing',
                                  sum(r.prediction for r in rows) if predictions else None,
                                  sum(r.actual for r in rows) if mature else None,'mature' if mature else 'pending',
                                  cohort='company',statistic='mean' if all(r.statistic=='mean' for r in rows) else 'point'))
    direct_by_period={(r.company_id,r.target_start,r.target_end):r for r in direct_rows}
    if len(direct_by_period)!=len(direct_rows):
        raise ValueError('duplicate direct company target')
    paired=[]
    for r in bottom:
        other=direct_by_period.get((r.company_id,r.target_start,r.target_end))
        if other and r.actual is not None and other.actual is not None and r.prediction is not None and other.prediction is not None:
            if not math.isclose(r.actual,other.actual,abs_tol=1e-8):
                raise ValueError('company actual differs across matched procedures')
            paired.append(abs(r.prediction-r.actual)-abs(other.prediction-other.actual))
    return dict(bottom_up_company=summarize_opportunities(bottom),direct_company=summarize_opportunities(direct_rows),
                paired_company=dict(n=len(paired),mean_absolute_loss_difference=sum(paired)/len(paired) if paired else None,
                                    confidence_interval=None,inference='descriptive paired loss; no iid-row confidence claim'))


def interval_cohort_metrics(rows, alpha):
    """Coverage/width/proper interval score for each predeclared selected slice.

    Rows are (cohort, lower, upper, actual); no aggregation hides a selected
    donor or changed-contract cohort's failure. Support is reported explicitly.
    """
    rows=tuple(rows)
    def score(values):
        return interval_metrics(tuple(r[1] for r in values),tuple(r[2] for r in values),tuple(r[3] for r in values),alpha)
    return dict(overall=score(rows),cohorts={cohort:score(tuple(r for r in rows if r[0]==cohort)) for cohort in sorted({r[0] for r in rows})},
                qualification='descriptive observed coverage; selected-population validation requires its own gate')
