from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import json
from types import SimpleNamespace

import pytest

from forecasting.contracts import ForecastRequest, Target
from forecasting.service import ForecastService, ForecastApplication
from forecasting.store import ArtifactStore, AccessDenied


T = datetime(2026, 10, 1, tzinfo=timezone.utc)


def snapshot():
    target = Target('cost', 'northstar', 'provider_reported_cost', 'USD', 'USD', ('billing',), ('variable',))
    daily = tuple(SimpleNamespace(entity_id=entity, date=date(2026,9,1)+timedelta(days=i), value=Decimal(value))
                  for entity,value in [('research','10'),('product','5')] for i in range(30))
    return SimpleNamespace(target=target, as_of=T, history_start=date(2026,9,1), history_end=date(2026,10,1),
                           snapshot_id='snapshot-1',daily=daily,ready=True,limitations=(),
                           to_dict=lambda: {'snapshot_id':'snapshot-1','data':'fixture'},
                           recorded=lambda s,e: sum((d.value for d in daily if s<=d.date<e),Decimal(0)),
                           recorded_by_entity=lambda s,e: {entity:sum((d.value for d in daily if d.entity_id==entity and s<=d.date<e),Decimal(0)) for entity in ['research','product']})


def request(s, **kw):
    return ForecastRequest('r1',s.target,T,date(2026,9,1),date(2026,10,8),model=kw.pop('model','trailing_mean'),**kw)


def test_full_remainder_and_company_conserve_with_unknown_late(tmp_path):
    s=snapshot(); service=ForecastService(ArtifactStore(tmp_path/'results.sqlite'))
    full=service.run(request(s),s,allowed_sources={'billing'})
    assert full['result']['recorded']=='450'
    assert Decimal(full['result']['future']) == 105
    assert full['variable_total'] is None and full['result']['status']=='limited'
    assert sum(Decimal(v['future']) for v in full['entities'].values()) == Decimal(full['result']['future'])
    assert full['capabilities']['event_probability'] is False
    remainder=service.run(request(s,output='remainder'),s,allowed_sources={'billing'},late_estimate=Decimal(0))
    assert Decimal(remainder['result']['recorded']) == 0
    assert Decimal(remainder['variable_total']) == 105
    restored=service.retrieve('northstar',full['artifact_id'],allowed_sources={'billing'},now=T+timedelta(days=10))
    assert restored['read_status']=='stale' and restored['result']==full['result']


def test_fallback_unavailable_and_current_permission(tmp_path):
    s=snapshot(); service=ForecastService(ArtifactStore(tmp_path/'results.sqlite'))
    result=service.run(request(s,model='foundation'),s,allowed_sources={'billing'},fallback='trailing_mean')
    assert result['result']['status']=='fallback'
    assert result['fallback']['requested']=='foundation'
    s.ready=False;s.limitations=('coverage_missing:billing',)
    result=service.run(request(s),s,allowed_sources={'billing'})
    assert result['result']['status']=='unavailable' and result['result']['future'] is None
    assert result['result']['recorded']=='450'
    with pytest.raises(AccessDenied): service.run(request(s),s,allowed_sources=set())


def test_fault_after_storage_leaves_retrievable_result_and_control_usable(tmp_path):
    s=snapshot(); service=ForecastService(ArtifactStore(tmp_path/'results.sqlite'))
    first=service.run(request(s),s,allowed_sources={'billing'})
    for stage in ['before_forecast','after_forecast','before_store','after_store']:
        def fault(current, wanted=stage):
            if current==wanted: raise RuntimeError('injected '+wanted)
        with pytest.raises(RuntimeError): service.run(request(s),s,allowed_sources={'billing'},fault=fault)
        assert service.retrieve('northstar',first['artifact_id'],allowed_sources={'billing'},now=T)['result']==first['result']
        assert service.run(request(s),s,allowed_sources={'billing'})['artifact_id']==first['artifact_id']


def test_service_guards_snapshot_mismatch_and_request_bounds(tmp_path):
    s=snapshot(); service=ForecastService(ArtifactStore(tmp_path/'results.sqlite'))
    s.as_of=T-timedelta(days=1)
    with pytest.raises(ValueError): service.run(request(s),s,allowed_sources={'billing'})
    s.as_of=T
    long=ForecastRequest('r2',s.target,T,date(2026,10,1),date(2028,1,1))
    with pytest.raises(ValueError): service.run(long,s,allowed_sources={'billing'})


def test_wsgi_retrieval_uses_server_auth_and_rejects_unknown_route(tmp_path):
    import io
    s=snapshot(); service=ForecastService(ArtifactStore(tmp_path/'results.sqlite'))
    saved=service.run(request(s),s,allowed_sources={'billing'})
    app=ForecastApplication(service,authenticate=lambda env: ('northstar',{'billing'}))
    status=[]
    response=b''.join(app({'REQUEST_METHOD':'GET','PATH_INFO':'/v1/results/'+saved['artifact_id'], 'wsgi.input':io.BytesIO()},lambda value,headers:status.append(value)))
    assert status==['200 OK'] and json.loads(response)['artifact_id']==saved['artifact_id']
    denied=ForecastApplication(service,authenticate=lambda env: ('other',{'billing'}))
    status=[]
    b''.join(denied({'REQUEST_METHOD':'GET','PATH_INFO':'/v1/results/'+saved['artifact_id']},lambda value,headers:status.append(value)))
    assert status==['403 Forbidden']


def test_concurrent_identical_requests_share_one_inflight_computation(tmp_path,monkeypatch):
    from concurrent.futures import ThreadPoolExecutor, Future as RealFuture
    from threading import Event
    import forecasting.service as module
    follower=Event(); started=Event(); release=Event(); calls=[]
    class ObservedFuture(RealFuture):
        def result(self,*args,**kwargs):
            follower.set()
            return super().result(*args,**kwargs)
    original=module.forecast
    def counted(*args,**kwargs):
        calls.append(args[0].entity_id)
        started.set()
        assert release.wait(5)
        return original(*args,**kwargs)
    monkeypatch.setattr(module,'Future',ObservedFuture,raising=False)
    monkeypatch.setattr(module,'forecast',counted)
    s=snapshot();service=ForecastService(ArtifactStore(tmp_path/'results.sqlite'))
    with ThreadPoolExecutor(max_workers=2) as pool:
        one=pool.submit(service.run,request(s),s,allowed_sources={'billing'})
        assert started.wait(5)
        two=pool.submit(service.run,request(s),s,allowed_sources={'billing'})
        shared=follower.wait(.2)
        release.set()
        a,b=one.result(),two.result()
    assert shared, 'concurrent follower did not join in-flight request'
    assert len(calls)==2  # one actual model calculation for each entity, not two runs
    assert a['artifact_id']==b['artifact_id']
    a['result']['status']='corrupted caller copy'
    assert b['result']['status']=='limited'
