"""Real joint serving: shared paths, exact target support and inherited evidence."""
from dataclasses import replace, fields
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import io
import json

import pytest

from forecasting.contracts import ForecastRequest, Target, digest
from forecasting.service import ForecastService, ForecastApplication
from forecasting.snapshot import DailyValue, Snapshot
from forecasting.store import ArtifactStore, AccessDenied


def fixture(tmp_path, *, lag=0, output='remainder'):
    start = date(2026, 8, 1)
    history_end = start + timedelta(days=60)
    origin = datetime.combine(history_end + timedelta(days=lag), datetime.min.time(), timezone.utc)
    target = Target('tokens', 'tenant', 'metered_usage', 'tokens', None, ('usage',), ('variable',), support='nonnegative')
    daily = tuple(DailyValue(entity, start + timedelta(days=i), Decimal(value))
                  for entity, value in [('a', 2), ('b', 3)] for i in range(60))
    company = tuple(DailyValue('company', start + timedelta(days=i), Decimal(5)) for i in range(60))
    fields = dict(target=target, as_of=origin, history_start=start, history_end=history_end,
                  daily=daily, company_daily=company, ready=True, limitations=(),
                  source_manifest=(), attribution_digest='mapping', coverage_digest='covered')
    snap = Snapshot(digest(fields), **fields)
    req = ForecastRequest('joint', target, origin, origin.date(), origin.date()+timedelta(days=4), output=output)
    return ForecastService(ArtifactStore(tmp_path/'joint.sqlite')), snap, req


def axes():
    from forecasting.joint import SeriesAxis
    return tuple(SeriesAxis(entity, 'input', 'model', 'pool', 'tokens') for entity in ('a','b'))


def test_joint_public_service_exists():
    assert callable(getattr(ForecastService, 'run_joint', None)), 'public service must expose integrated joint route'


def test_joint_shared_paths_conserve_and_replay_under_current_acl(tmp_path):
    service, snap, req = fixture(tmp_path)
    result = service.run_joint(req, snap, axes=axes(), allowed_sources={'usage'}, n_paths=8, seed=7,
                               quantiles=(0.5,), threshold=Decimal(19))
    assert Decimal(result['result']['future']) == 20
    assert Decimal(result['entities']['a']['future']) == 8
    assert Decimal(result['entities']['b']['future']) == 12
    assert Decimal(result['usage']['quantiles']['0.5']) == 20
    assert result['usage']['exceedance_probability'] == 1
    assert result['capabilities']['safe_transfer'] is False
    assert result['manifest']['empirical_status'] == 'not_empirically_qualified'
    replay = service.run_joint(req, snap, axes=axes(), allowed_sources={'usage'}, n_paths=8, seed=7,
                               quantiles=(0.5,), threshold=Decimal(19))
    assert replay['artifact_id'] == result['artifact_id']
    saved = service.retrieve('tenant', result['artifact_id'], allowed_sources={'usage'}, now=req.as_of)
    assert saved['usage'] == result['usage']
    bundle = service.store.get('tenant', result['bundle_artifact_id'], allowed_sources={'usage'})
    assert len(bundle['payload']['values']) == 8
    with pytest.raises(AccessDenied):
        service.retrieve('tenant', result['artifact_id'], allowed_sources=set(), now=req.as_of)
    service.store.revoke('tenant', result['artifact_id'], reason='source revoked')
    with pytest.raises(AccessDenied):
        service.retrieve('tenant', result['artifact_id'], allowed_sources={'usage'}, now=req.as_of)


def test_joint_exact_future_support_and_lag_does_not_invent_gap_actuals(tmp_path):
    service, snap, req = fixture(tmp_path, lag=2)
    req = replace(req, period_start=req.period_start+timedelta(days=1))
    with pytest.raises(ValueError):
        service.run_joint(req, snap, axes=axes(), allowed_sources={'usage'})
    result = service.run_joint(req, snap, axes=axes(), allowed_sources={'usage'}, max_history_lag_days=2, n_paths=4)
    assert Decimal(result['result']['future']) == 15
    assert Decimal(result['result']['recorded']) == 0
    assert result['manifest']['history_lag_days'] == 2
    assert result['usage']['dates'] == ['2026-10-03','2026-10-04','2026-10-05']
    assert len(result['entities']['a']['daily']) == 3


def test_joint_unavailable_model_preserves_actual_usage(tmp_path):
    service, snap, req = fixture(tmp_path, output='full_period')
    req = replace(req, period_start=snap.history_start)
    changes = {f.name: getattr(snap, f.name) for f in fields(snap) if f.name not in {'snapshot_id','schema_version'}}
    changes.update(ready=False, limitations=('coverage_missing',))
    if changes.get('evidence_class') == 'unspecified': changes.pop('evidence_class')
    snap = Snapshot(digest(changes), **changes)
    result = service.run_joint(req, snap, axes=axes(), allowed_sources={'usage'})
    assert result['result']['future'] is None
    assert Decimal(result['result']['recorded']) == 300
    assert result['usage']['qualification']['status'] == 'unavailable'
    assert sum(Decimal(v['recorded']) for v in result['entities'].values()) == 300


def test_bound_provenance_cannot_be_upgraded_in_either_service(tmp_path):
    service, snap, req = fixture(tmp_path)
    # Unknown source receipts cannot become verified data by caller assertion.
    for method, options in [(service.run, {}), (service.run_joint, {'axes': axes()})]:
        with pytest.raises(ValueError, match='provenance|evidence'):
            method(req, snap, allowed_sources={'usage'}, evidence_class='backend_verified_snapshot', **options)


def test_joint_wsgi_route_uses_trusted_options_and_retrieves_result(tmp_path):
    service, snap, req = fixture(tmp_path)
    app = ForecastApplication(service, authenticate=lambda env: ('tenant', {'usage'}),
                              snapshot_resolver=lambda request, tenant, sources: snap,
                              run_options={'axes': axes(), 'n_paths': 4})
    body = json.dumps(req.to_dict()).encode()
    status = []
    result = json.loads(b''.join(app({'REQUEST_METHOD':'POST', 'PATH_INFO':'/v1/joint-forecast',
                                     'CONTENT_LENGTH':str(len(body)), 'wsgi.input':io.BytesIO(body)},
                                     lambda value, headers: status.append(value))))
    assert status == ['200 OK']
    assert Decimal(result['result']['future']) == 20
    assert service.retrieve('tenant', result['artifact_id'], allowed_sources={'usage'}, now=req.as_of)['usage'] == result['usage']


def commercial_options(req, *, complete=True):
    from forecasting.commercial import MeterKey, RateRevision, TariffCatalog, PeriodUsage
    from forecasting.pricing import PricingContract
    key = MeterKey('model','input','tokens','pool')
    # Twenty future tokens less one shared allowance of ten, plus fixed three.
    contract = PricingContract('fixture-contract','1','USD','tokens',req.period_start,req.period_end,
                               req.as_of,Decimal(10),Decimal(2),Decimal(3))
    rate = RateRevision('fixture-rate',key,Decimal(1),req.period_start,req.period_end,req.as_of,contract)
    def resolve(bundle):
        prefixes = tuple(PeriodUsage(path,'pool',req.period_start,req.period_end,req.period_start,
                                    (key,),(),(),(),complete) for path in bundle.path_ids)
        return {'catalog':TariffCatalog((rate,)), 'prefixes':prefixes}
    return resolve


def test_joint_commercial_exact_shared_pool_and_independent_unavailability(tmp_path):
    service, snap, req = fixture(tmp_path)
    result = service.run_joint(req,snap,axes=axes(),allowed_sources={'usage'},n_paths=4,
                               commercial_options=commercial_options(req),monetary_threshold=Decimal(22))
    assert Decimal(result['usage']['mean']) == 20
    assert Decimal(result['monetary']['mean']) == 23
    assert Decimal(result['monetary']['quantiles']['0.5']) == 23
    assert result['monetary']['exceedance_probability'] == 1
    priced = service.store.get('tenant',result['commercial_artifact_id'],allowed_sources={'usage'})['payload']
    assert len(priced['paths']) == 4
    for path in priced['paths']:
        period = path['periods'][0]
        assert Decimal(period['future_increment']) == 20
        assert sum(Decimal(a['future_increment'])+Decimal(a['fixed'])+Decimal(a['prefix_variable']) for a in period['allocations']) == 23
    unsupported = service.run_joint(req,snap,axes=axes(),allowed_sources={'usage'},n_paths=4,
                                    commercial_options=commercial_options(req,complete=False))
    assert Decimal(unsupported['result']['future']) == 20
    assert unsupported['monetary']['mean'] is None
    assert unsupported['monetary']['qualification']['status'] == 'unavailable'
    assert unsupported['capabilities']['mean'] is True


def test_workload_adjustment_retains_baseline_lineage_without_changing_actuals(tmp_path):
    from forecasting.context import NumericAssumption, WorkloadAdjustment
    service,snap,req = fixture(tmp_path,output='full_period')
    req = replace(req,period_start=snap.history_start)
    baseline = service.run_joint(req,snap,axes=axes(),allowed_sources={'usage'},n_paths=4)
    adjustment = WorkloadAdjustment('plan','assumption',NumericAssumption('user','Conditional double workload',Decimal(2)))
    result = service.run_joint(req,snap,axes=axes(),allowed_sources={'usage'},n_paths=4,workload_adjustments=(adjustment,))
    assert Decimal(result['result']['recorded']) == 300
    assert Decimal(result['result']['future']) == 40
    assert result['manifest']['scenario']['estimand'] == 'workload'
    bundle = service.store.get('tenant',result['bundle_artifact_id'],allowed_sources={'usage'})['payload']
    assert bundle['parent_ids'] == [baseline['manifest']['bundle_id']]
    with pytest.raises(ValueError,match='already applied'):
        service.run_joint(req,snap,axes=axes(),allowed_sources={'usage'},workload_adjustments=(adjustment,adjustment))


def test_structural_kernel_is_selected_without_aggregate_history_fit(tmp_path):
    from forecasting.state import ExposureSpell, ExecutionMark, HurdleParameters
    service,snap,req = fixture(tmp_path)
    exposure = ExposureSpell('access','person','cohort',req.period_start,req.period_end,req.as_of,True,prior_use=False)
    inputs = {'exposures':(exposure,), 'events':(),
              'parameters':(HurdleParameters('cohort',1,marks=(ExecutionMark(7),)),)}
    result = service.run_joint(req,snap,allowed_sources={'usage'},n_paths=4,state_inputs=inputs)
    assert Decimal(result['result']['future']) == 28
    assert result['state_artifact_id']
    state = service.store.get('tenant',result['state_artifact_id'],allowed_sources={'usage'})['payload']
    assert len(state['paths']) == 4
    assert result['manifest']['procedure']['procedure_id'] != 'joint_residual_blocks'


def test_structural_target_slice_advances_state_from_actual_origin(tmp_path):
    from forecasting.state import ExposureSpell, ExecutionMark, HurdleParameters
    service,snap,req = fixture(tmp_path)
    exposure = ExposureSpell('access','person','cohort',req.period_start,req.period_end,req.as_of,True,prior_use=False)
    req = replace(req,period_start=req.period_start+timedelta(days=2))
    result = service.run_joint(req,snap,allowed_sources={'usage'},n_paths=2,state_inputs={
        'exposures':(exposure,), 'events':(), 'parameters':(HurdleParameters('cohort',1,marks=(ExecutionMark(7),)),)})
    assert Decimal(result['result']['future']) == 14
    state = service.store.get('tenant',result['state_artifact_id'],allowed_sources={'usage'})['payload']
    assert len(state['paths'][0]['roots']) == 4
    assert len(result['usage']['dates']) == 2


@pytest.mark.parametrize('process',['state','aggregate'])
def test_cli_compound_demo_acquires_evidence_prices_resets_and_retrieves(tmp_path,capsys,process):
    from forecasting.cli import main
    assert main(['joint-demo','--output-dir',str(tmp_path/'demo'),'--process',process]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result['process'] == process
    assert result['evidence_class'] == 'synthetic_fixture'
    assert Decimal(result['usage_mean']) == 20
    assert Decimal(result['conditional_contract_mean']) == 26
    assert result['monetary_exceedance_probability'] == 1
    assert result['retrieved_artifact_id'] == result['artifact_id']
    assert (tmp_path/'demo'/'joint.sqlite').exists()


def test_views_are_independently_qualified_and_commercial_inputs_replayable(tmp_path):
    service,snap,req = fixture(tmp_path)
    result = service.run_joint(req,snap,axes=axes(),allowed_sources={'usage'},n_paths=4,
                               commercial_options=commercial_options(req))
    assert result['usage']['qualifications']['mean']['status'] == 'available_assumption_conditional'
    assert result['usage']['qualifications']['exceedance_probability']['status'] == 'unavailable'
    assert result['calibration']['status'] == 'unavailable'
    inputs = service.store.get('tenant',result['commercial_input_artifact_id'],allowed_sources={'usage'})['payload']
    assert inputs['bundle_id'] == result['manifest']['bundle_id']
    assert inputs['inputs']['catalog']['revisions'][0]['revision_id'] == 'fixture-rate'
    assert len(inputs['inputs']['prefixes']) == 4


def test_invalid_structural_law_is_rejected_instead_of_fabricating_unavailability(tmp_path):
    from forecasting.state import ExposureSpell, ExecutionMark, HurdleParameters
    service,snap,req = fixture(tmp_path)
    inputs = {'exposures':(ExposureSpell('access','person','c',req.period_start,req.period_end,req.as_of,True),),
              'events':(), 'parameters':(HurdleParameters('c',1,marks=(ExecutionMark(7),)),),'mode':'invalid'}
    with pytest.raises(ValueError,match='mode'):
        service.run_joint(req,snap,allowed_sources={'usage'},state_inputs=inputs)


def test_full_period_native_risk_targets_recorded_plus_future_when_complete(tmp_path):
    service,snap,req = fixture(tmp_path,output='full_period')
    req = replace(req,period_start=snap.history_start)
    result = service.run_joint(req,snap,axes=axes(),allowed_sources={'usage'},n_paths=4,threshold=Decimal(319))
    assert Decimal(result['usage']['mean']) == 320
    assert result['usage']['exceedance_probability'] == 1
    assert Decimal(result['variable_total']) == 320
    assert result['usage']['target_scope'] == 'exact_requested_target'


def midcontract_commercial(req, *, fixed=Decimal(0)):
    from forecasting.commercial import MeterKey, RateRevision, TariffCatalog, PeriodUsage, UsageAtom
    from forecasting.pricing import PricingContract
    key = MeterKey('model','input','tokens','pool')
    start = req.as_of.date()-timedelta(days=2)
    contract = PricingContract('midcontract','1','USD','tokens',start,req.period_end,req.as_of,
                               Decimal(0),Decimal(2),fixed)
    catalog = TariffCatalog((RateRevision('mid-rate',key,Decimal(1),start,req.period_end,req.as_of,contract),))
    def resolve(bundle):
        return {'catalog':catalog,'prefixes':tuple(PeriodUsage(path,'pool',start,req.period_end,req.as_of.date(),
            (key,),(UsageAtom('a',key,Decimal(100)),),(),(),True) for path in bundle.path_ids)}
    return resolve


def test_monetary_remainder_excludes_historical_prefix_and_uses_requested_event(tmp_path):
    service,snap,req = fixture(tmp_path)
    result = service.run_joint(req,snap,axes=axes(),allowed_sources={'usage'},n_paths=4,
        commercial_options=midcontract_commercial(req),monetary_threshold=Decimal(100))
    assert Decimal(result['monetary']['mean']) == 40
    assert result['monetary']['exceedance_probability'] == 0
    assert Decimal(result['monetary']['complete_contract']['mean']) == 240
    assert result['monetary']['target_scope'] == 'exact_requested_remainder_increment'


@pytest.mark.parametrize('output,fixed', [('full_period',Decimal(0)),('remainder',Decimal(3))])
def test_monetary_mismatched_start_or_untimed_fixed_keeps_distinct_contract_view(tmp_path,output,fixed):
    service,snap,req = fixture(tmp_path,output=output)
    result = service.run_joint(req,snap,axes=axes(),allowed_sources={'usage'},n_paths=4,
        commercial_options=midcontract_commercial(req,fixed=fixed),monetary_threshold=Decimal(100))
    assert result['monetary']['mean'] is None
    assert result['monetary']['exceedance_probability'] is None
    assert Decimal(result['monetary']['complete_contract']['mean']) == 240+fixed
    assert result['monetary']['complete_contract']['exceedance_probability'] is None
    assert result['monetary']['complete_contract']['periods'][0]['period_start'] == '2026-09-28'
    assert Decimal(result['result']['future']) == 20


def test_joint_dependencies_withdraw_snapshot_and_adjustment_parent_with_acl_unchanged(tmp_path):
    from forecasting.context import NumericAssumption, WorkloadAdjustment
    service,snap,req = fixture(tmp_path)
    independent = service.store.put('tenant','independent',{'value':'readable'},('usage',))
    baseline = service.run_joint(req,snap,axes=axes(),allowed_sources={'usage'},n_paths=4)
    adjustment = WorkloadAdjustment('a','assumption',NumericAssumption('user','scenario',Decimal(2)))
    changed = service.run_joint(req,snap,axes=axes(),allowed_sources={'usage'},n_paths=4,workload_adjustments=(adjustment,))
    parent = changed['parent_bundle_artifact_ids'][0]
    service.store.revoke('tenant',parent,reason='parent withdrawn')
    with pytest.raises(AccessDenied):
        service.retrieve('tenant',changed['artifact_id'],allowed_sources={'usage'},now=req.as_of)
    service.store.revoke('tenant',baseline['snapshot_artifact_id'],reason='snapshot withdrawn')
    with pytest.raises(AccessDenied):
        service.retrieve('tenant',baseline['artifact_id'],allowed_sources={'usage'},now=req.as_of)
    assert service.store.get('tenant',independent,allowed_sources={'usage'})['payload']['value'] == 'readable'


def test_store_dependency_closure_inherits_source_union_and_withdrawal(tmp_path):
    store = ArtifactStore(tmp_path/'deps.sqlite')
    source = store.put('tenant','evidence',{'value':1},('context',))
    parent = store.put('tenant','derived',{'value':2},('usage',),required_artifacts=(source,))
    child = store.put('tenant','derived',{'value':3},required_artifacts=(parent,))
    with pytest.raises(AccessDenied): store.get('tenant',child,allowed_sources={'usage'})
    assert store.get('tenant',child,allowed_sources={'usage','context'})['required_sources'] == ['context','usage']
    store.revoke('tenant',source,reason='context withdrawn')
    with pytest.raises(AccessDenied): store.get('tenant',child,allowed_sources={'usage','context'})


def test_structural_sensitivity_is_identity_bound_and_never_publishes_probabilities(tmp_path):
    from forecasting.state import ExposureSpell, ExecutionMark, HurdleParameters
    from forecasting.joint import ScenarioSpec
    from forecasting.context import NumericAssumption, WorkloadAdjustment
    service,snap,req = fixture(tmp_path)
    inputs = {'exposures':(ExposureSpell('access','person','c',req.period_start,req.period_end,req.as_of,True),),
              'events':(), 'parameters':(HurdleParameters('c',1,marks=(ExecutionMark(7),)),)}
    baseline = service.run_joint(req,snap,allowed_sources={'usage'},n_paths=4,state_inputs=inputs)
    scenario = ScenarioSpec('sensitivity-test',kind='sensitivity',estimand='stress')
    result = service.run_joint(req,snap,allowed_sources={'usage'},n_paths=4,state_inputs=inputs,scenario=scenario)
    assert result['artifact_id'] != baseline['artifact_id']
    assert result['manifest']['scenario']['kind'] == 'sensitivity'
    assert result['manifest']['scenario']['estimand'] == 'stress'
    assert result['usage']['quantiles'] == {} and result['usage']['exceedance_probability'] is None
    adjustment = WorkloadAdjustment('a','assumption',NumericAssumption('user','scenario',Decimal(2)))
    adjusted = service.run_joint(req,snap,allowed_sources={'usage'},n_paths=4,state_inputs=inputs,
                                 scenario=scenario,workload_adjustments=(adjustment,))
    assert adjusted['manifest']['scenario']['kind'] == 'sensitivity'
    assert adjusted['manifest']['scenario']['estimand'] == 'stress'
    assert adjusted['usage']['quantiles'] == {} and adjusted['usage']['mean'] is None


def test_joint_explicit_material_sources_are_required_at_issue_and_retrieval(tmp_path):
    service,snap,req = fixture(tmp_path)
    context = service.store.put('tenant','context',{'assumption':'authorized'},('context-source',))
    with pytest.raises(AccessDenied):
        service.run_joint(req,snap,axes=axes(),allowed_sources={'usage'},required_artifacts=(context,))
    result = service.run_joint(req,snap,axes=axes(),allowed_sources={'usage','context-source'},
                               required_artifacts=(context,),n_paths=4)
    with pytest.raises(AccessDenied):
        service.retrieve('tenant',result['artifact_id'],allowed_sources={'usage'},now=req.as_of)
    service.store.revoke('tenant',context,reason='assumption evidence withdrawn')
    with pytest.raises(AccessDenied):
        service.retrieve('tenant',result['artifact_id'],allowed_sources={'usage','context-source'},now=req.as_of)


def test_chained_structural_artifacts_inherit_each_direct_parent_withdrawal(tmp_path):
    from forecasting.state import ExposureSpell, ExecutionMark, HurdleParameters
    from forecasting.joint import ScenarioSpec
    from forecasting.context import NumericAssumption, WorkloadAdjustment
    service,snap,req = fixture(tmp_path)
    exposure = ExposureSpell('access','person','c',req.period_start,req.period_end,req.as_of,True)
    req = replace(req,period_start=req.period_start+timedelta(days=1))
    result = service.run_joint(req,snap,allowed_sources={'usage'},n_paths=4,
        state_inputs={'exposures':(exposure,), 'events':(),
                      'parameters':(HurdleParameters('c',1,marks=(ExecutionMark(7),)),)},
        scenario=ScenarioSpec('grid',kind='sensitivity',estimand='stress'),
        workload_adjustments=(WorkloadAdjustment('a','assumption',NumericAssumption('user','scenario',Decimal(2))),))
    original,declared,sliced = result['parent_bundle_artifact_ids']
    children = (declared,sliced,result['bundle_artifact_id'],result['artifact_id'])
    for child in children:
        assert service.store.get('tenant',child,allowed_sources={'usage'})
    service.store.revoke('tenant',original,reason='original structural parent withdrawn')
    for child in children:
        with pytest.raises(AccessDenied):
            service.store.get('tenant',child,allowed_sources={'usage'})
    with pytest.raises(AccessDenied):
        service.retrieve('tenant',result['artifact_id'],allowed_sources={'usage'},now=req.as_of)
    assert service.store.get('tenant',result['state_artifact_id'],allowed_sources={'usage'})
