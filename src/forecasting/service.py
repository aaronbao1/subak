"""Versioned forecasting orchestration and a small authenticated WSGI boundary."""
from __future__ import annotations

from dataclasses import asdict
from concurrent.futures import Future
from threading import Lock
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import json
from typing import Callable, Iterable, Optional
from zoneinfo import ZoneInfo

from . import __version__
from .contracts import ForecastRequest, ForecastResult, decimal, exact_sum
from .models import MODEL_REGISTRY, ModelUnavailable, Series, forecast
from .store import ArtifactStore, AccessDenied, canonical_json, digest


def _days(start: date, end: date):
    return tuple(start + timedelta(days=i) for i in range(max(0, (end-start).days)))


class ForecastService:
    """No retries, no external calls, and bounded horizons in the local core.

    Current source permissions come from the backend's authenticated authorization
    context. The result never certifies all-in transferable budget headroom.
    """
    def __init__(self, store: ArtifactStore, *, max_horizon=366, max_entities=1000):
        if max_horizon <= 0 or max_entities <= 0:
            raise ValueError('positive workload bounds required')
        self.store = store
        self.max_horizon = max_horizon
        self.max_entities = max_entities
        self._inflight = {}
        self._inflight_lock = Lock()

    def run(self, request: ForecastRequest, snapshot, *, allowed_sources: Iterable[str], **options) -> dict:
        sources=frozenset(allowed_sources)
        if not set(request.target.sources).issubset(sources):
            raise AccessDenied('current source permissions required')
        # Fault injection is an explicit trusted test harness; never cache its outcomes.
        if options.get('fault') is not None:
            return self._run(request,snapshot,allowed_sources=sources,**options)
        options=deepcopy(options)
        key=digest({'request':request.to_dict(),'snapshot_id':snapshot.snapshot_id,'options':options})
        with self._inflight_lock:
            leader=key not in self._inflight
            if leader: self._inflight[key]=Future()
            future=self._inflight[key]
        if not leader:
            return deepcopy(future.result())
        try:
            result=self._run(request,snapshot,allowed_sources=sources,**options)
            future.set_result(deepcopy(result))
            return result
        except BaseException as exc:
            future.set_exception(exc)
            raise
        finally:
            with self._inflight_lock:
                self._inflight.pop(key,None)

    def _run(self, request: ForecastRequest, snapshot, *, allowed_sources: Iterable[str],
            model_config=None, fallback: Optional[str] = None, evidence_class: str = 'unspecified',
            max_history_lag_days: int = 0, recorded_supplement=None,
            late_estimate: Optional[Decimal] = None, fixed_obligations: Optional[Decimal] = None,
            fault: Optional[Callable[[str], None]] = None) -> dict:
        from .joint_service import bound_evidence
        evidence_class = bound_evidence(snapshot, evidence_class)
        if not set(request.target.sources).issubset(set(allowed_sources)):
            raise AccessDenied('current source permissions required')
        if snapshot.target != request.target or snapshot.as_of != request.as_of:
            raise ValueError('snapshot target and cutoff must exactly match request')
        origin = request.as_of.astimezone(ZoneInfo(request.target.reporting_timezone)).date()
        if type(max_history_lag_days) is not int or not 0<=max_history_lag_days<=30:
            raise ValueError('history lag policy must be an integer from 0 to 30 days')
        lag=(origin-snapshot.history_end).days
        if lag<0 or lag>max_history_lag_days:
            raise ValueError('daily history watermark exceeds explicit lag policy')
        if recorded_supplement is not None:
            if (recorded_supplement.target!=request.target or recorded_supplement.as_of!=request.as_of
                or recorded_supplement.history_start!=snapshot.history_end or recorded_supplement.history_end!=origin
                or recorded_supplement.source_manifest!=snapshot.source_manifest):
                raise ValueError('incurred supplement must share target, cutoff, source generations and exact gap')
        elif lag and request.output=='full_period' and request.period_start<min(origin,request.period_end):
            raise ValueError('delayed full-period request requires a same-source incurred supplement')
        if request.period_start < snapshot.history_start:
            raise ValueError('snapshot does not cover recorded portion of requested period')
        if max(0,(request.period_end-snapshot.history_end).days) > self.max_horizon:
            raise ValueError('requested horizon exceeds configured workload bound')
        if not request.target.additive:
            raise ValueError('nonadditive targets require full-contract pricing adapter')
        if request.target.measure in {'fixed_obligation', 'internal_allocation'}:
            raise ValueError('budgets and fixed obligations are not stochastic variable demand')
        if late_estimate is not None: late_estimate=decimal(late_estimate)
        if fixed_obligations is not None: fixed_obligations=decimal(fixed_obligations)
        notify = fault or (lambda stage: None)
        notify('before_forecast')
        all_dates = _days(snapshot.history_end, request.period_end)
        selected_dates = tuple(d for d in all_dates if d >= max(origin,request.period_start))
        observations = {}
        for row in snapshot.daily:
            observations.setdefault(row.entity_id, []).append(row)
        if len(observations)>self.max_entities:
            raise ValueError('entity workload bound exceeded')
        source_exclusions=set()
        for receipt in getattr(snapshot,'source_manifest',()):
            query=receipt.query if hasattr(receipt,'query') else receipt.get('query','')
            try:
                metadata=json.loads(query)
                if isinstance(metadata,dict):
                    source_exclusions.update(x for x in metadata.get('exclusions',()) if isinstance(x,str))
            except (ValueError,TypeError):
                pass
        limitations = list(snapshot.limitations)
        if source_exclusions: limitations.append('source coverage excludes: '+', '.join(sorted(source_exclusions)))
        if lag: limitations.append(f'history_lag_days:{lag}; bridge predictions are not recorded charges or future continuation')
        entities = {}
        fallback_record = None
        model_used = request.model
        statistic = 'mean'
        coherent = 'daily_sum'
        future_total = Decimal(0)
        available = bool(snapshot.ready)
        panel=[]
        try:
            for entity, rows in sorted(observations.items()):
                rows=sorted(rows,key=lambda r:r.date)
                series=Series(entity,tuple(r.date for r in rows),tuple(float(r.value) for r in rows))
                if series.dates[-1] != snapshot.history_end-timedelta(days=1):
                    raise ModelUnavailable('entity history does not reach training watermark: '+entity)
                panel.append(series)
            if selected_dates and not panel:
                raise ModelUnavailable('no covered entity history')
        except (ModelUnavailable,ValueError,OverflowError) as exc:
            available=False;limitations.append(str(exc))
        recorded_by = snapshot.recorded_by_entity(request.period_start,min(origin,request.period_end)) if request.period_start<min(origin,request.period_end) else {}
        supplement_entities=set()
        if recorded_supplement is not None:
            supplement_entities={row.entity_id for row in recorded_supplement.daily}
            if selected_dates:
                for entity in sorted(supplement_entities-set(observations)):
                    available=False;limitations.append('new incurred entity lacks training history: '+entity)
            supplement_start=max(request.period_start,recorded_supplement.history_start)
            supplement_end=min(request.period_end,origin)
            if supplement_start<supplement_end:
                for entity,amount in recorded_supplement.recorded_by_entity(supplement_start,supplement_end).items():
                    recorded_by[entity]=exact_sum((recorded_by.get(entity,Decimal(0)),amount))
            limitations.extend('incurred_gap:'+v for v in recorded_supplement.limitations)
        recorded = exact_sum(recorded_by.values()) if request.output=='full_period' else Decimal(0)
        incurred_complete = (request.output=='remainder' or request.period_start>=min(origin,request.period_end)
            or (snapshot.ready and (not lag or (recorded_supplement is not None and recorded_supplement.ready))))
        # Remainder means future service only. Past unreported charges are a separate full-period component.
        late = late_estimate if request.output=='full_period' and request.period_start<origin else Decimal(0)
        if available:
            try:
                for series in panel:
                    pred=None
                    if selected_dates:
                        config=dict(model_config or {})
                        if 'nonnegative' in config and config['nonnegative'] != (request.target.support=='nonnegative'):
                            raise ModelUnavailable('model support conflicts with target contract')
                        config['nonnegative']=request.target.support=='nonnegative'
                        try:
                            pred=forecast(series,all_dates,request.model,config=config,panel=tuple(panel))
                        except ModelUnavailable as exc:
                            if fallback is None: raise
                            pred=forecast(series,all_dates,fallback,config={'nonnegative':request.target.support=='nonnegative'},panel=tuple(panel))
                            fallback_record={'requested':request.model,'used':fallback,'reason':str(exc)}
                            model_used=fallback
                        limitations.extend(pred.limitations)
                        if pred.statistic=='point': statistic='point'
                        if pred.daily_values is None:
                            if selected_dates != all_dates:
                                raise ModelUnavailable('direct cumulative prediction cannot be sliced or assigned to daily values')
                            entity_future=Decimal(str(pred.cumulative_value))
                            daily=None;coherent=pred.coherence
                        else:
                            daily={d.isoformat():str(Decimal(str(v))) for d,v in zip(pred.dates,pred.daily_values) if d in selected_dates}
                            entity_future=exact_sum(Decimal(v) for v in daily.values())
                    else:
                        entity_future=Decimal(0);daily={}
                    future_total=exact_sum((future_total,entity_future))
                    entities[series.entity_id]={'recorded':str(recorded_by.get(series.entity_id,Decimal(0)) if request.output=='full_period' else Decimal(0)),
                                               'future':str(entity_future),'daily':daily,
                                               'model':pred.model_name if pred else 'closed_period',
                                               'model_metadata':dict(pred.metadata) if pred else {}}
            except (ModelUnavailable,ValueError,OverflowError) as exc:
                available=False;limitations.append('model_unavailable: '+str(exc));entities={}
        if late is None:
            limitations.append('late_incurred_estimate_unavailable: known-plus-future is not complete variable total')
        if not available:
            entities={entity:{'recorded':str(recorded_by.get(entity,Decimal(0)) if request.output=='full_period' else Decimal(0)),
                              'future':None,'daily':None,'model':'unavailable','model_metadata':{}}
                      for entity in sorted(set(observations)|set(recorded_by)|supplement_entities)}
            limitations.append('affected forecast unavailable; measured spending remains readable')
        if fallback_record:
            limitations.append('explicit fallback: '+fallback_record['reason'])
        limitations=tuple(dict.fromkeys(limitations))
        status='unavailable' if not available else ('fallback' if fallback_record else ('limited' if limitations or late is None else 'ready'))
        manifest={'schema_version':'1.0','request':request.to_dict(),'snapshot_id':snapshot.snapshot_id,
                  'history_end':snapshot.history_end,'history_lag_days':lag,'max_history_lag_days':max_history_lag_days,
                  'recorded_supplement_id':recorded_supplement.snapshot_id if recorded_supplement is not None else None,
                  'source_exclusions':sorted(source_exclusions),'package_version':__version__,'model_requested':request.model,'model_used':model_used,
                  'model_config':model_config or {},'fallback_policy':fallback,'late_estimate':late,
                  'fixed_obligations':fixed_obligations,'incurred_complete':incurred_complete,
                  'seed':(model_config or {}).get('seed',0),
                  'resolved_predictions':{entity:{'model':value['model'],'model_metadata':value['model_metadata']}
                                          for entity,value in entities.items()},
                  # Identity includes resolved behavior, not only requested inputs.
                  # Dependency failure, projection, or a changed daily path must not
                  # reuse an immutable result identity from a different outcome.
                  'output_digest':digest({'recorded':recorded,'late_incurred':late,
                                          'future':future_total if available else None,
                                          'fixed_obligations':fixed_obligations,
                                          'entities':entities,'status':status,
                                          'statistic':statistic,'limitations':limitations,
                                          'coherence':coherent if available else None}),
                  'evidence_class':evidence_class,'empirical_status':'promotion_pending'}
        result=ForecastResult(digest(manifest),request.request_id,request.target,snapshot.snapshot_id,request.as_of,
                              request.period_start,request.period_end,recorded,late,
                              future_total if available else None,fixed_obligations,status,model_used,statistic,limitations)
        notify('after_forecast')
        snapshot_artifact=self.store.put(request.target.tenant_id,'snapshot',snapshot.to_dict(),request.target.sources)
        supplement_artifact=self.store.put(request.target.tenant_id,'snapshot',recorded_supplement.to_dict(),request.target.sources) if recorded_supplement is not None else None
        payload={'schema_version':'1.0','result':result.to_dict(),'variable_total':str(result.variable_total) if result.variable_total is not None else None,
                 'known_plus_future':str(exact_sum((recorded,future_total))) if available else None,
                 'entities':entities,'coherence':coherent if available else None,'incurred_complete':incurred_complete,
                 'capabilities':{'point':available,'mean':available and statistic=='mean','quantiles':False,'interval':False,
                                 'event_probability':False,'joint_paths':False,'safe_transfer':False},
                 'manifest':manifest,'recorded_supplement_artifact_id':supplement_artifact,'snapshot_artifact_id':snapshot_artifact,'fallback':fallback_record,
                 'all_in_total':None,'all_in_limitation':'fixed/variable budget coverage and late-charge obligations require explicit reconciliation'}
        notify('before_store')
        artifact_id=self.store.put(request.target.tenant_id,'forecast',payload,request.target.sources,
                                   required_artifacts=tuple(ref for ref in (snapshot_artifact,supplement_artifact) if ref))
        notify('after_store')
        stored_at=self.store.get(request.target.tenant_id,artifact_id,allowed_sources=allowed_sources)['stored_at']
        return json.loads(canonical_json(dict(payload,artifact_id=artifact_id,stored_at=stored_at)))

    def run_joint(self, request, snapshot, *, allowed_sources, **options):
        from .joint_service import run_joint
        return run_joint(self, request, snapshot, allowed_sources=allowed_sources, **options)

    def retrieve(self, tenant_id: str, artifact_id: str, *, allowed_sources: Iterable[str],
                 now: Optional[datetime]=None, max_age: timedelta=timedelta(days=2)) -> dict:
        if max_age.total_seconds()<0: raise ValueError('max_age must be nonnegative')
        artifact=self.store.get(tenant_id,artifact_id,allowed_sources=allowed_sources)
        if artifact['kind'] not in {'forecast','joint_forecast'}: raise ValueError('artifact is not a forecast')
        payload=artifact['payload']
        now=now or datetime.now(timezone.utc)
        if now.tzinfo is None: raise ValueError('aware read time required')
        origin=datetime.fromisoformat(payload['result']['as_of'])
        if now<origin: raise ValueError('read time precedes forecast origin')
        return dict(payload,artifact_id=artifact_id,stored_at=artifact['stored_at'],
                    read_status='stale' if now-origin>max_age else payload['result']['status'],
                    age_seconds=(now-origin).total_seconds())


class ForecastApplication:
    """WSGI adapter. An embedding backend supplies authenticated tenant/source ACLs.

    POST /v1/forecast delegates source loading to a trusted resolver; neither
    authentication nor file-system paths are accepted from the JSON body.
    """
    def __init__(self, service: ForecastService, *, authenticate: Callable, snapshot_resolver: Optional[Callable]=None,
                 max_body_bytes=1048576, run_options=None):
        self.service=service;self.authenticate=authenticate
        self.snapshot_resolver=snapshot_resolver;self.max_body_bytes=max_body_bytes
        self.run_options=deepcopy(run_options or {})

    def __call__(self,environ,start_response):
        try:
            tenant,sources=self.authenticate(environ)
            if not tenant: raise AccessDenied('authentication required')
            method=environ.get('REQUEST_METHOD','GET');path=environ.get('PATH_INFO','')
            if method=='GET' and path=='/v1/models':
                value={'schema_version':'1.0','models':{k:asdict(v) for k,v in MODEL_REGISTRY.items()}}
            elif method=='GET' and path.startswith('/v1/results/'):
                value=self.service.retrieve(tenant,path.removeprefix('/v1/results/'),allowed_sources=sources)
            elif method=='POST' and path in {'/v1/forecast','/v1/joint-forecast'} and self.snapshot_resolver is not None:
                length=int(environ.get('CONTENT_LENGTH','0'))
                if length<=0 or length>self.max_body_bytes: raise ValueError('invalid request size')
                request=ForecastRequest.from_dict(json.loads(environ['wsgi.input'].read(length)))
                if request.target.tenant_id!=tenant: raise AccessDenied('tenant mismatch')
                snapshot=self.snapshot_resolver(request,tenant,sources)
                runner=self.service.run_joint if path=='/v1/joint-forecast' else self.service.run
                value=runner(request,snapshot,allowed_sources=sources,**self.run_options)
            else:
                start_response('404 Not Found',[('Content-Type','application/json')]);return [b'{"error":"route unavailable"}']
            status='200 OK'
        except PermissionError as exc: status='403 Forbidden';value={'error':str(exc)}
        except (ValueError,TypeError,KeyError) as exc: status='400 Bad Request';value={'error':str(exc)}
        except Exception:
            status='500 Internal Server Error';value={'error':'request failed; no success receipt issued'}
        body=canonical_json(value).encode()
        start_response(status,[('Content-Type','application/json'),('Content-Length',str(len(body)))])
        return [body]
