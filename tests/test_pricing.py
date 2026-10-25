from datetime import date, datetime, timezone
from decimal import Decimal as D
import pytest
from forecasting.pricing import PricingContract, Tier, price_period, price_paths, allocate
from forecasting.contracts import ContractError


def contract(**kw):
    return PricingContract(contract_id='c',version='1',currency='USD',unit='credits',period_start=date(2026,10,1),period_end=date(2026,11,1),known_at=datetime(2026,9,1,tzinfo=timezone.utc),**kw)

def test_shared_pool_full_state_and_negative_repricing_increment():
    c=contract(allowance=D(10),rate=D(1),fixed=D(100))
    p=price_period(c,{'a':D(8)},{'b':D(8)})
    assert p.variable_total == 6 and p.future_increment == 6 and p.fixed == 100
    assert sum(allocate(p.variable_total,{'a':D('.5'),'b':D('.5')}).values()) == 6
    v=contract(mode='volume',tiers=(Tier(D(100),D(10)),Tier(None,D(8))))
    p=price_period(v,{'a':D(100)},{'a':D(1)})
    assert p.prefix_variable == 1000 and p.variable_total == 808 and p.future_increment == -192


def test_expected_tariff_uses_paths_not_mean_and_graduated():
    c=contract(allowance=D(10),rate=D(10),fixed=D(100))
    r=price_paths(c,{},[({'a':D(0)},D('.5')),({'a':D(20)},D('.5'))])
    assert r == 150
    assert price_period(c,{}, {'a':D(10)}).total == 100
    graduated=contract(mode='graduated',tiers=(Tier(D(10),D(2)),Tier(None,D(1))))
    assert price_period(graduated,{}, {'a':D(15)}).total == 25


def test_unsupported_terms_and_zero_allocation():
    assert allocate(D(100),{'a':D(0),'b':D(0)}) == {'central':D(100)}
    with pytest.raises(ContractError): contract(mode='credits_expiry')
    with pytest.raises(ContractError): price_paths(contract(),{},[({},D('.8'))])
    with pytest.raises(ContractError): price_period(contract(),{}, {'a':D(-1)})


@pytest.mark.parametrize('mode',['credits_expiry','annual_commitment','seat_changes','tax','fx','invoice_reconciliation'])
def test_complex_financial_branches_explicitly_rejected(mode):
    with pytest.raises(ContractError,match='unsupported tariff'):contract(mode=mode)


def test_unknown_origin_and_cross_reset_rejected():
    with pytest.raises(ContractError):price_period(contract(),{}, {},as_of=datetime(2026,8,1,tzinfo=timezone.utc))
    with pytest.raises(ContractError):price_period(contract(),{}, {},period_end=date(2026,12,1))


def test_allocation_exact_residual_and_no_savings_from_weights():
    a=allocate(D('1.50'),{'a':D(1),'b':D(2),'c':D(3)})
    b=allocate(D('1.50'),{'a':D(3),'b':D(2),'c':D(1)})
    assert sum(a.values())==sum(b.values())==D('1.50')
    assert a!=b


def test_price_only_scenario_freezes_usage_and_higher_usage_can_outweigh_cut():
    from dataclasses import replace, FrozenInstanceError
    old=contract(rate=D(10))
    revised=replace(old,version='2',rate=D(8))
    baseline={'a':D(100)}
    assert price_period(old,{},baseline).total==1000
    assert price_period(revised,{},baseline).total==800
    assert baseline=={'a':D(100)}
    assert price_period(revised,{}, {'a':D(150)}).total==1200
    assert price_period(old,{},baseline).contract_version=='1'
    with pytest.raises(FrozenInstanceError):old.rate=D(8)
    unknown_then=replace(revised,known_at=datetime(2026,10,20,tzinfo=timezone.utc))
    with pytest.raises(ContractError):price_period(unknown_then,{},baseline,as_of=datetime(2026,10,1,tzinfo=timezone.utc))


def test_pricing_large_microcost_conserves_full_precision():
    c=contract(rate=D('0.000000001'))
    p=price_period(c,{'a':D('123456789012345678901234567890')},{'a':D(1)})
    assert p.variable_total==D('123456789012345678901.234567891')
    assert p.future_increment==D('.000000001')


@pytest.mark.parametrize('amount,weights',[
    (D('123456789012345678901234567890.000000001'),{'a':D(1),'z':D(0)}),
    (D(10),{'a':D(1),'b':D(1),'c':D(1),'z':D(0)}),
    (D('.000000000000000000000000000001'),{'a':D(1),'b':D(1),'z':D(0)}),
])
def test_allocation_never_gives_rounding_residual_to_zero_weight(amount,weights):
    from forecasting.contracts import exact_sum
    result=allocate(amount,weights)
    assert result['z']==0
    assert all(v>=0 for v in result.values())
    assert exact_sum(result.values())==amount
    if len(weights)==2:assert result['a']==amount


def test_tariff_requires_immutable_typed_decimal_terms():
    with pytest.raises(ContractError):contract(mode='volume',tiers=[Tier(None,D(1))])
    with pytest.raises(ContractError):contract(mode='volume',tiers=({'up_to':None,'rate':D(1)},))
    for value in ('1',1,1.0):
        with pytest.raises(ContractError):contract(rate=value)
        with pytest.raises(ContractError):Tier(None,value)
        with pytest.raises(ContractError):Tier(value,D(1))
