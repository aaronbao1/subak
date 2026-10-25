"""Forecast estimand and content identity checks at the serving boundary."""
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from forecasting.contracts import ForecastRequest, Target, digest
from forecasting.models import Series
from forecasting.snapshot import DailyValue, Snapshot
from forecasting.service import ForecastService
from forecasting.store import ArtifactStore


def fixture(tmp_path, values, *, support='signed'):
    start=date(2024,1,1)
    end=start+timedelta(days=len(values))
    origin=datetime.combine(end,datetime.min.time(),timezone.utc)
    target=Target('target','tenant','provider_reported_cost','USD','USD',('billing',),('variable',),support=support)
    daily=tuple(DailyValue('team',start+timedelta(days=i),Decimal(str(v))) for i,v in enumerate(values))
    company=tuple(DailyValue('company',r.date,r.value) for r in daily)
    fields=dict(target=target,as_of=origin,history_start=start,history_end=end,
                daily=daily,company_daily=company,ready=True,limitations=(),
                source_manifest=(),attribution_digest='mapping',coverage_digest='coverage')
    snap=Snapshot(digest(fields),**fields)
    req=ForecastRequest('request',target,origin,end,end+timedelta(days=7),output='remainder',model='last_observation')
    return ForecastService(ArtifactStore(tmp_path/'store.sqlite')),snap,req


def test_runtime_capability_change_cannot_reuse_immutable_result_identity(tmp_path,monkeypatch):
    import forecasting.models as models
    service,snapshot,req=fixture(tmp_path,range(56))
    req=replace(req,model='calendar_regression')
    available=service.run(req,snapshot,allowed_sources={'billing'},fallback='last_observation')
    monkeypatch.setattr(models,'_dependency_versions',lambda:{})
    fallback=service.run(req,snapshot,allowed_sources={'billing'},fallback='last_observation')
    assert available['result']['model']=='calendar_regression'
    assert fallback['result']['model']=='last_observation'
    assert available['result']['result_id'] != fallback['result']['result_id']
    # Without fallback the model_requested/model_used manifest values are equal,
    # but different actual availability still requires different result identity.
    unavailable=service.run(req,snapshot,allowed_sources={'billing'})
    monkeypatch.undo()
    real=service.run(req,snapshot,allowed_sources={'billing'})
    assert unavailable['result']['result_id'] != real['result']['result_id']
    assert real['manifest']['resolved_predictions']['team']['model_metadata']['dependency_versions']['numpy']=='1.26.4'


def test_service_projection_disables_mean_capability(tmp_path):
    service,snapshot,req=fixture(tmp_path,[30-i for i in range(30)],support='nonnegative')
    result=service.run(replace(req,model='local_linear_trend'),snapshot,allowed_sources={'billing'},model_config={'damping':1.})
    assert result['result']['statistic']=='point'
    assert result['capabilities']['mean'] is False
    assert result['capabilities']['point'] is True
    assert all(Decimal(v)>=0 for v in result['entities']['team']['daily'].values())


def test_service_slices_daily_calendar_path_but_never_direct_total(tmp_path):
    service,snapshot,req=fixture(tmp_path,[5.]*100)
    req=replace(req,period_start=req.period_start+timedelta(days=3))
    daily=service.run(req,snapshot,allowed_sources={'billing'})
    assert Decimal(daily['result']['future'])==20
    assert len(daily['entities']['team']['daily'])==4
    direct=service.run(replace(req,model='tabular_direct_cumulative'),snapshot,allowed_sources={'billing'})
    assert direct['result']['status']=='unavailable'
    assert direct['result']['future'] is None
    assert direct['capabilities']['mean'] is False


def test_service_direct_total_has_no_daily_coherence_claim(tmp_path):
    service,snapshot,req=fixture(tmp_path,[5.]*100)
    direct=service.run(replace(req,model='tabular_direct_cumulative'),snapshot,allowed_sources={'billing'})
    assert Decimal(direct['result']['future'])==35
    assert direct['entities']['team']['daily'] is None
    assert direct['coherence']=='direct_cumulative_only'


def test_explicit_delayed_history_bridges_gap_without_inventing_incurred_or_future(tmp_path):
    service,snap,req=fixture(tmp_path,[5.]*100)
    new_origin=req.as_of+timedelta(days=2)
    from dataclasses import asdict
    fields=asdict(snap);fields.pop('snapshot_id');fields.pop('schema_version');fields['as_of']=new_origin
    # asdict deep-converts contracts; retain original frozen values.
    fields.update(target=snap.target,daily=snap.daily,company_daily=snap.company_daily,source_manifest=snap.source_manifest)
    delayed=Snapshot(digest(fields),**fields)
    supplement_fields=dict(target=delayed.target,as_of=new_origin,history_start=snap.history_end,
        history_end=new_origin.date(),daily=(DailyValue('team',snap.history_end,Decimal('5')),),
        company_daily=(DailyValue('company',snap.history_end,Decimal('5')),),ready=False,
        limitations=('coverage_partial:billing',),source_manifest=delayed.source_manifest,
        attribution_digest='mapping',coverage_digest='gap')
    supplement=Snapshot(digest(supplement_fields),**supplement_fields)
    request=replace(req,as_of=new_origin,period_start=snap.history_start,period_end=new_origin.date()+timedelta(days=7),output='full_period')
    with pytest.raises(ValueError):service.run(request,delayed,allowed_sources={'billing'},recorded_supplement=supplement)
    result=service.run(request,delayed,allowed_sources={'billing'},max_history_lag_days=2,recorded_supplement=supplement)
    assert Decimal(result['result']['recorded'])==505
    assert Decimal(result['result']['future'])==35
    assert result['result']['late'] is None and result['variable_total'] is None
    assert result['manifest']['history_lag_days']==2
    assert min(result['entities']['team']['daily'])==new_origin.date().isoformat()
    direct=service.run(replace(request,model='tabular_direct_cumulative'),delayed,allowed_sources={'billing'},max_history_lag_days=2,recorded_supplement=supplement)
    assert direct['result']['status']=='unavailable'
    assert direct['result']['future'] is None


@pytest.mark.parametrize('new_values', [(0,0),(10,-10),(5,0)])
def test_new_gap_entity_requires_cold_start_even_at_zero_net_spend(tmp_path,new_values):
    service,snap,req=fixture(tmp_path,[5.]*100)
    origin=req.as_of+timedelta(days=2)
    fields=dict(target=snap.target,as_of=origin,history_start=snap.history_start,history_end=snap.history_end,
        daily=snap.daily,company_daily=snap.company_daily,ready=True,limitations=(),source_manifest=snap.source_manifest,
        attribution_digest=snap.attribution_digest,coverage_digest=snap.coverage_digest)
    delayed=Snapshot(digest(fields),**fields)
    daily=tuple(DailyValue('new-team',snap.history_end+timedelta(days=i),Decimal(v)) for i,v in enumerate(new_values))
    gap=dict(target=snap.target,as_of=origin,history_start=snap.history_end,history_end=origin.date(),daily=daily,
        company_daily=tuple(DailyValue('company',x.date,x.value) for x in daily),ready=False,limitations=('partial',),
        source_manifest=snap.source_manifest,attribution_digest='mapping',coverage_digest='gap')
    supplement=Snapshot(digest(gap),**gap)
    request=replace(req,as_of=origin,period_start=snap.history_start,period_end=origin.date()+timedelta(days=7),output='full_period')
    result=service.run(request,delayed,allowed_sources={'billing'},max_history_lag_days=2,recorded_supplement=supplement)
    assert result['result']['status']=='unavailable' and result['result']['future'] is None
    assert 'new-team' in result['entities']
    assert sum(Decimal(x['recorded']) for x in result['entities'].values())==Decimal(result['result']['recorded'])
    assert Decimal(result['entities']['new-team']['recorded'])==sum(map(Decimal,new_values))


@pytest.mark.parametrize('output',['remainder','full_period'])
def test_future_only_request_still_gates_new_entity_in_incurred_supplement(tmp_path,output):
    service,snap,req=fixture(tmp_path,[5.]*100)
    origin=req.as_of+timedelta(days=1)
    fields=dict(target=snap.target,as_of=origin,history_start=snap.history_start,history_end=snap.history_end,
        daily=snap.daily,company_daily=snap.company_daily,ready=True,limitations=(),source_manifest=snap.source_manifest,
        attribution_digest=snap.attribution_digest,coverage_digest=snap.coverage_digest)
    delayed=Snapshot(digest(fields),**fields)
    gap=dict(target=snap.target,as_of=origin,history_start=snap.history_end,history_end=origin.date(),
        daily=(DailyValue('new-team',snap.history_end,Decimal(10)),),
        company_daily=(DailyValue('company',snap.history_end,Decimal(10)),),ready=False,limitations=('partial',),
        source_manifest=snap.source_manifest,attribution_digest='mapping',coverage_digest='gap')
    request=replace(req,as_of=origin,period_start=origin.date(),period_end=origin.date()+timedelta(days=7),output=output)
    result=service.run(request,delayed,allowed_sources={'billing'},max_history_lag_days=1,recorded_supplement=Snapshot(digest(gap),**gap))
    assert result['result']['status']=='unavailable' and result['result']['future'] is None
    assert 'new-team' in result['entities']
    assert Decimal(result['result']['recorded'])==0
