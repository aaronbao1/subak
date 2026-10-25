from datetime import date, datetime, timezone
from decimal import Decimal as D, localcontext
import pytest
from forecasting.contracts import ContractError
from forecasting.pricing import PricingContract
from forecasting.commercial import (MeterKey, RateRevision, TariffCatalog, UsageAtom,
    PeriodUsage, price_usage_paths)

START=date(2026,10,1); ORIGIN=date(2026,10,15); END=date(2026,11,1)
NOW=datetime(2026,10,15,tzinfo=timezone.utc)
KEY=MeterKey('config-v1','input','tokens','pool')
def rate(version='v1', known=NOW, allowance=D(100), denominator=D(1)):
    c=PricingContract('synthetic',version,'USD','tokens',START,END,known,allowance,D(1),D(3))
    return RateRevision('rate-'+version,KEY,denominator,START,END,known,c)
def usage(path='p',future=(('a','80'),('b','80')),complete=True):
    return PeriodUsage(path,'pool',START,END,ORIGIN,(KEY,),(),(),
        tuple(UsageAtom(name,KEY,D(q)) for name,q in future),complete)

def test_shared_pool_price_once_and_exact_conserved_roles():
    out=price_usage_paths('bundle',NOW,(('p',D(1)),),TariffCatalog((rate(),)),(usage(),),'proportional-v1')
    assert out.status=='available'
    p=out.paths[0]; line=p.periods[0]
    assert (p.path_id,p.weight,p.total)==('p',D(1),D(63))
    assert line.future_increment==D(60) and line.fixed==D(3)
    assert sum((a.total for a in line.allocations),D(0))==p.total
    assert line.contract_version=='v1' and line.allocation_version=='proportional-v1'
    assert line.allocations[0].total==D('31.5')

def test_catalog_gates_future_knowledge_ambiguity_and_dimensions():
    future=datetime(2026,10,20,tzinfo=timezone.utc)
    assert TariffCatalog((rate('v2',future),)).resolve(KEY,START,END,NOW) is None
    with pytest.raises(ContractError,match='ambiguous'):
        TariffCatalog((rate(),rate('v2'))).resolve(KEY,START,END,NOW)
    wrong=MeterKey('config-v1','output','tokens','pool')
    assert TariffCatalog((rate(),)).resolve(wrong,START,END,NOW) is None
    with pytest.raises(ContractError): rate(denominator=D(0))

def test_missing_prefix_or_mismatched_meter_preserves_native_parent():
    for item in (usage(complete=False),PeriodUsage('p','pool',START,END,ORIGIN,(KEY,),(),(),(UsageAtom('a',MeterKey('c','input','requests','pool'),D(2)),),True)):
        out=price_usage_paths('native-stays',NOW,(('p',D(1)),),TariffCatalog((rate(),)),(item,),'proportional-v1')
        assert out.status=='unavailable' and out.bundle_id=='native-stays' and out.reason
        assert out.paths==()

def test_duplicate_meter_and_omitted_reset_period_rejected():
    with pytest.raises(ContractError,match='duplicate'):
        PeriodUsage('p','pool',START,END,ORIGIN,(KEY,KEY),(),(),(),True)
    item=usage()
    out=price_usage_paths('bundle',NOW,(('p',D(1)),('q',D(0))),TariffCatalog((rate(),)),(item,),'proportional-v1')
    assert out.status=='unavailable' and 'complete' in out.reason

def test_late_prefix_and_signed_volume_delta_conserve_under_low_precision():
    from forecasting.pricing import Tier
    c=PricingContract('volume','v','USD','tokens',START,END,NOW,D(0),D(0),D(0),'volume',(Tier(D(100),D(10)),Tier(None,D(8))))
    catalog=TariffCatalog((RateRevision('r',KEY,D(1),START,END,NOW,c),))
    item=PeriodUsage('p','pool',START,END,ORIGIN,(KEY,),(UsageAtom('a',KEY,D(90)),),(UsageAtom('a',KEY,D(10)),),(UsageAtom('b',KEY,D(1)),),True)
    with localcontext() as ctx:
        ctx.prec=3
        out=price_usage_paths('bundle',NOW,(('p',D(1)),),catalog,(item,),'proportional-v1')
    line=out.paths[0].periods[0]
    assert (line.prefix_variable,line.future_increment,line.total)==(D(1000),D(-192),D(808))
    assert sum((a.total for a in line.allocations),D(0))==line.total

def test_bundle_adapter_requires_complete_future_span_and_retains_original_weights():
    from datetime import timedelta
    from forecasting.joint import ScenarioBundle, SeriesAxis, ProcedureSpec
    from forecasting.contracts import Target
    from forecasting.commercial import price_bundle
    dates=tuple(ORIGIN+timedelta(days=i) for i in range((END-ORIGIN).days))
    bundle=ScenarioBundle(Target('u','tenant','metered_usage','tokens',None,('s',),('input',),support='nonnegative'),
        'snapshot',NOW,dates,(SeriesAxis('a','input','config-v1','pool','tokens'),),
        ('p','q','r'),tuple(((1,)*len(dates),) for _ in range(3)),(1/3,1/3,1/3),ProcedureSpec('fixture'))
    prefixes=tuple(PeriodUsage(p,'pool',START,END,ORIGIN,(KEY,),(),(),(),True) for p in bundle.path_ids)
    out=price_bundle(bundle,TariffCatalog((rate(allowance=D(0)),)),prefixes)
    assert out.status=='available' and tuple(p.weight for p in out.paths)==bundle.weights
    assert all(p.total==D(20) for p in out.paths)
    from dataclasses import replace
    incomplete=replace(bundle,dates=dates[:-1],values=tuple(((1,)*(len(dates)-1),) for _ in range(3)))
    rejected=price_bundle(incomplete,TariffCatalog((rate(),)),prefixes)
    assert rejected.status=='unavailable' and 'future' in rejected.reason

def test_prefix_boundary_cannot_omit_past_or_include_future():
    from dataclasses import replace
    bad=replace(usage(),through=date(2026,10,16))
    out=price_usage_paths('bundle',NOW,(('p',D(1)),),TariffCatalog((rate(),)),(bad,),'proportional-v1')
    assert out.status=='unavailable' and 'origin' in out.reason

def test_two_explicit_reset_periods_each_apply_shared_allowance_and_fixed_once():
    from dataclasses import replace
    second_end=date(2026,12,1)
    first=usage()
    second=PeriodUsage('p','pool',END,second_end,END,(KEY,),(),(),first.future,True)
    c=replace(rate().contract,period_start=END,period_end=second_end)
    second_rate=RateRevision('nov',KEY,D(1),END,second_end,NOW,c)
    out=price_usage_paths('b',NOW,(('p',D(1)),),TariffCatalog((rate(),second_rate)),(first,second),'proportional-v1')
    assert out.status=='available' and out.paths[0].total==D(126)
    assert tuple(p.total for p in out.paths[0].periods)==(D(63),D(63))

def test_denominator_scales_quantities_before_shared_allowance_without_rounding():
    out=price_usage_paths('b',NOW,(('p',D(1)),),TariffCatalog((rate(allowance=D(0),denominator=D(1000)),)),(usage(),),'proportional-v1')
    assert out.paths[0].total==D('3.160')
    no_rounding=price_usage_paths('b',NOW,(('p',D(1)),),TariffCatalog((rate(denominator=D(3)),)),(usage(),),'proportional-v1')
    assert no_rounding.status=='unavailable' and 'nonterminating' in no_rounding.reason

def test_nonfinite_derived_weight_mass_is_unavailable():
    out=price_usage_paths('b',NOW,(('p',1e308),('q',1e308)),TariffCatalog((rate(),)),(usage(),),'proportional-v1')
    assert out.status=='unavailable' and 'weight' in out.reason

@pytest.mark.parametrize('role',['known_prefix','late_prefix'])
def test_nonzero_prefix_in_empty_interval_is_unavailable(role):
    from dataclasses import replace
    c=replace(rate().contract,period_start=END,period_end=date(2026,12,1),allowance=D(0),fixed=D(0))
    catalog=TariffCatalog((RateRevision('nov',KEY,D(1),END,c.period_end,NOW,c),))
    atoms=(UsageAtom('a',KEY,D(100)),)
    item=PeriodUsage('p','pool',END,c.period_end,END,(KEY,),atoms if role=='known_prefix' else (),atoms if role=='late_prefix' else (),(),True)
    out=price_usage_paths('b',NOW,(('p',D(1)),),catalog,(item,),'proportional-v1')
    assert out.status=='unavailable' and 'empty prefix' in out.reason

def test_nonzero_future_in_empty_interval_is_unavailable():
    from dataclasses import replace
    old_start=date(2026,9,1)
    c=replace(rate().contract,period_start=old_start,period_end=START)
    catalog=TariffCatalog((RateRevision('sept',KEY,D(1),old_start,START,NOW,c),))
    item=PeriodUsage('p','pool',old_start,START,START,(KEY,),(),(),(UsageAtom('a',KEY,D(1)),),True)
    out=price_usage_paths('b',NOW,(('p',D(1)),),catalog,(item,),'proportional-v1')
    assert out.status=='unavailable' and 'empty future' in out.reason

@pytest.mark.parametrize('role',['known_prefix','late_prefix'])
def test_bundle_adapter_refuses_nonzero_prefix_for_future_contract(role):
    from dataclasses import replace
    from datetime import timedelta
    from forecasting.joint import ScenarioBundle,SeriesAxis,ProcedureSpec
    from forecasting.contracts import Target
    from forecasting.commercial import price_bundle
    end=date(2026,12,1)
    dates=tuple(END+timedelta(days=i) for i in range((end-END).days))
    bundle=ScenarioBundle(Target('u','tenant','metered_usage','tokens',None,('s',),('input',),support='nonnegative'),
        'snapshot',NOW,dates,(SeriesAxis('a','input','config-v1','pool','tokens'),),('p',),
        (((1,)*len(dates),),),(1.,),ProcedureSpec('fixture'))
    c=replace(rate().contract,period_start=END,period_end=end,allowance=D(0),fixed=D(0))
    catalog=TariffCatalog((RateRevision('nov',KEY,D(1),END,end,NOW,c),))
    atoms=(UsageAtom('a',KEY,D(100)),)
    prefix=PeriodUsage('p','pool',END,end,END,(KEY,),atoms if role=='known_prefix' else (),atoms if role=='late_prefix' else (),(),True)
    rejected=price_bundle(bundle,catalog,(prefix,))
    assert rejected.status=='unavailable' and 'empty prefix' in rejected.reason
    zero=replace(prefix,known_prefix=(UsageAtom('a',KEY,D(0)),),late_prefix=())
    accepted=price_bundle(bundle,catalog,(zero,))
    assert accepted.status=='available' and accepted.paths[0].total==D(30)
