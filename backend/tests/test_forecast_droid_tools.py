from app.agent.tools import TOOL_NAMES, TOOLS, render_manifest, MANIFEST_PATH
from app.agent.fake_runner import FakeDroidRunner
from app.agent.runner import AgentTask
from northstar_droid.sdk_tools import tool_functions

EXPECTED = {'explain_forecast','compare_forecasts','preview_forecast_scenario','request_forecast_refresh'}


def test_forecast_tool_manifest_sdk_and_inputs_match():
    assert EXPECTED <= set(TOOL_NAMES)
    assert MANIFEST_PATH.read_text() == render_manifest()
    wrappers = {name:fn for name,_,fn in tool_functions(object())}
    assert set(wrappers) == set(TOOL_NAMES)
    model = next(t.input_model for t in TOOLS if t.name=='explain_forecast')
    assert model.model_validate({'run_id':'run-1','scope_type':'person','scope_id':'maya','driver_id':'drv-1'}).driver_id=='drv-1'


def test_fake_runner_forecast_question_uses_frozen_exact_context_and_grounded_receipt():
    class Tools:
        calls = []
        def explain_forecast(self, **args):
            self.calls.append(args)
            return {'run_id':'run-1','scope':{'type':'person','id':'maya'},'driver_id':'drv-1',
                    'summary':'Published quarter base is 430 USD. Atlas moved five days.',
                    'citations':[{'source_id':'asana:atlas','quote':'Move Atlas'}],
                    'limitations':['Synthetic fixture; descriptive scenarios.']}
        def emit(self,*args): pass
    tools=Tools()
    output = FakeDroidRunner().run(AgentTask(type='answer_question',instruction='Why did this move?',
        params={'forecast_context':{'action':'explain','run_id':'run-1','scope_type':'person',
                                    'scope_id':'maya','driver_id':'drv-1'}}),tools)
    assert tools.calls == [{'run_id':'run-1','scope_type':'person','scope_id':'maya','driver_id':'drv-1'}]
    assert '430 USD' in output.summary and 'run-1' in output.summary
    assert output.findings[0]['receipt']['citations'][0]['source_id']=='asana:atlas'
    assert 'question_not_interpreted' not in {w['code'] for w in output.warnings}


def test_stored_agent_forecast_explanation_and_scenario_receipts_preserve_baseline(seeded, client):
    from app.forecasting.worker import ForecastWorker
    service=seeded.state.forecast_service
    from app.forecasting.fixtures import build_northstar_snapshot
    service.snapshot_factory=build_northstar_snapshot
    job=service.refresh('droid-test-publication')
    ForecastWorker(service).process_one()
    run=service.store.get_job(job['id'])['run_id']
    original=service.store.get_run(run)['bundle']
    company=next(v for v in original['views'] if v['scope']['type']=='company')
    driver=company['included_drivers'][0]['id']
    context={'action':'explain','run_id':run,'scope_type':'company','scope_id':'northstar','driver_id':driver}
    response=client.post('/api/agent/runs',headers={'X-Actor-Id':'analyst','X-Actor-Role':'finance_analyst'},
                         json={'task_type':'answer_question','instruction':'Explain this driver.',
                               'params':{'forecast_context':context}})
    assert response.status_code==201,response.text
    data=response.json()
    assert data['status']=='succeeded',data
    assert data['steps'][0]['tool']=='explain_forecast'
    assert data['steps'][0]['args']['run_id']==run
    assert data['output']['forecast_receipts'][0]['receipt']['run_id']==run
    assert driver in data['summary']
    scenario=service.scenario(run,drivers=[])
    assert scenario['scenario_id'] and scenario['parent_run_id']==run
    assert service.get_scenario(scenario['scenario_id'])==scenario
    assert service.store.get_run(run)['bundle']==original


def test_sdk_comparison_retains_exact_runs_sources_and_values_within_response_limit():
    import json
    from app.agent.toolbox import _compact_forecast_receipt
    from app.forecasting.fixtures import build_northstar_snapshot
    from forecasting.planning import build_forecast
    from northstar_droid.sdk_tools import _respond
    snapshot=build_northstar_snapshot()
    bundle=build_forecast(snapshot,run_id='published-1',generated_at=snapshot['generated_at'])
    bundle['views']=[v for v in bundle['views'] if v['scope']['type']=='company']
    bundle['snapshot']=snapshot
    other={**bundle,'run_id':'published-2'}
    explained=json.loads(_respond(lambda:_compact_forecast_receipt(bundle)))
    assert not explained.get('truncated')
    result=json.loads(_respond(lambda:_compact_forecast_receipt({'runs':[bundle,other]})))
    assert not result.get('truncated')
    assert [b['run_id'] for b in result['runs']]==['published-1','published-2']
    assert result['runs'][0]['views'][0]['quarter_outlook']['base']>0
    assert result['runs'][0]['views'][0]['included_drivers'][0]['citations']
