from datetime import date, datetime, timezone
from decimal import Decimal
import pytest
from forecasting.contracts import Target, ForecastRequest, ForecastResult, ContractError, canonical_json


def target(**kwargs):
    return Target(target_id='cost', tenant_id='org', measure='provider_reported_cost', unit='USD', currency='USD', sources=('billing',), categories=('usage','adjustment'), **kwargs)


def test_decimal_strings_versions_and_unknown_fields():
    t = target()
    assert Target.from_dict(t.to_dict()) == t
    assert canonical_json({'tiny': Decimal('0.000001')}) == '{"tiny":"0.000001"}'
    with pytest.raises(ContractError): Target.from_dict({**t.to_dict(), 'version':'2.0'})
    with pytest.raises(ContractError): Target.from_dict({**t.to_dict(), 'mystery':1})
    with pytest.raises(ContractError): target(reporting_timezone='Nonesuch')
    with pytest.raises(ContractError): Target.from_dict({**t.to_dict(), 'measure':'x'})


def test_request_half_open_timezone_and_partial_day_rejection():
    t = target()
    args = dict(request_id='r',target=t,as_of=datetime(2026,10,10,tzinfo=timezone.utc),period_start=date(2026,10,1),period_end=date(2026,11,1))
    req = ForecastRequest(**args)
    assert ForecastRequest.from_dict(req.to_dict()) == req
    with pytest.raises(ContractError): ForecastRequest(**{**args,'as_of':datetime(2026,10,10)})
    with pytest.raises(ContractError): ForecastRequest(**{**args,'period_end':date(2026,10,1)})
    with pytest.raises(ContractError): ForecastRequest(**{**args,'as_of':datetime(2026,10,10,12,tzinfo=timezone.utc)})


def test_result_missing_late_is_not_zero_and_negative_adjustment_survives():
    r = ForecastResult(result_id='r', request_id='q', target=target(), snapshot_id='s', as_of=datetime(2026,10,10,tzinfo=timezone.utc), period_start=date(2026,10,1),period_end=date(2026,11,1), recorded=Decimal('-0.0001'), late=None, future=Decimal('2'), fixed=None, status='limited', model='naive', statistic='point', limitations=('late_unknown',))
    assert r.variable_total is None
    assert r.to_dict()['recorded'] == '-0.0001'
    assert ForecastResult.from_dict(r.to_dict()) == r
    with pytest.raises(ContractError): ForecastResult.from_dict({**r.to_dict(), 'status':'ready'})


def test_request_default_matches_registry_baseline():
    r=ForecastRequest('r',target(),datetime(2026,10,10,tzinfo=timezone.utc),date(2026,10,1),date(2026,11,1))
    assert r.model=='trailing_mean'


def test_unconstrained_demand_and_unknown_fx_are_not_inferred():
    with pytest.raises(ContractError):Target.from_dict({**target().to_dict(),'measure':'unconstrained_demand'})
    with pytest.raises(ContractError):Target.from_dict({**target().to_dict(),'conversion_policy':'infer_fx'})


def test_authoritative_arithmetic_preserves_precision_beyond_global_context():
    from forecasting.contracts import exact_sum, exact_product
    from decimal import getcontext
    a=Decimal('123456789012345678901234567890.000000001')
    tiny=Decimal('0.000000009')
    assert exact_sum((a,tiny))==Decimal('123456789012345678901234567890.000000010')
    assert exact_sum((a,a.copy_negate(),tiny))==tiny
    assert exact_product(a,Decimal('.5'))==Decimal('61728394506172839450617283945.0000000005')
    assert getcontext().prec==28
