"""Architecture edges: real SDK runner with deterministic transport and real persisted tools.

No Factory request is made. The stub stands in for CLI/model transport only.
"""
from __future__ import annotations

import json

import pytest

import fake_droid_sdk
from app.forecasting.fixtures import build_northstar_snapshot
from app.forecasting.worker import ForecastWorker
from northstar_droid.sdk_tools import NORTHSTAR_TOOL_IDS
from test_sdk_runner import ANALYST, fake_sdk, sdk_client  # noqa: F401
from app.config import Settings
from app.main import create_app
from northstar_droid.sdk_runner import SdkDroidRunner


@pytest.fixture
def sdk_app(tmp_path, clock, id_factory):
    app = create_app(Settings(db_path=tmp_path / "sdk-forecast.db", droid_runner="sdk", forecast_worker=False),
                     clock=clock, id_factory=id_factory,
                     droid_runner=SdkDroidRunner(executable="/nonexistent/droid", timeout_s=5))
    from app.seed.northstar import seed
    with app.state.session_factory() as session:
        seed(session, clock=clock, ids=id_factory)
    yield app
    app.state.engine.dispose()


@pytest.fixture
def published_pair(sdk_app):
    service = sdk_app.state.forecast_service
    service.snapshot_factory = build_northstar_snapshot
    jobs = [service.refresh(key) for key in ('architecture-first', 'architecture-second')]
    for job in jobs:
        assert ForecastWorker(service).process_one(job_id=job['id'])
    return service, [service.store.get_job(job['id'])['run_id'] for job in jobs]


def sdk_forecast_request(fake_sdk, client, context, tool, args):
    observed = []
    fake_sdk.SCENARIO = [fake_droid_sdk.Step(
        'text(await tools.northstar.' + tool + '(' + json.dumps(args) + '));',
        lambda call: observed.append(call(tool, **args)),
    )]
    response = client.post('/api/agent/runs', headers=ANALYST, json={
        'task_type': 'answer_question', 'instruction': 'Use the selected forecast context.',
        'params': {'forecast_context': context},
    })
    assert response.status_code == 201, response.text
    return response.json(), observed


@pytest.mark.parametrize('action,tool', [
    ('explain', 'explain_forecast'), ('compare', 'compare_forecasts'),
    ('preview', 'preview_forecast_scenario'), ('refresh', 'request_forecast_refresh'),
])
def test_sdk_forecast_action_reaches_real_persisted_tool(fake_sdk, sdk_client, published_pair, action, tool):
    service, (old, newest) = published_pair
    original = service.store.get_run(old)['bundle']
    driver = next(view for view in original['views'] if view['scope']['type'] == 'company')['included_drivers'][0]['id']
    context = {'action': action, 'run_id': old, 'scope_type': 'company', 'scope_id': 'northstar'}
    args = {'run_id': old, 'scope_type': 'company', 'scope_id': 'northstar'}
    if action == 'explain':
        context['driver_id'] = args['driver_id'] = driver
    elif action == 'compare':
        context['compare_run_id'] = newest
        args = {'run_ids': [old, newest], 'scope_type': 'company', 'scope_id': 'northstar'}
    elif action == 'preview':
        context['drivers'] = args['drivers'] = []
    else:
        context['idempotency_key'] = 'sdk-architecture-refresh'
        args = {'idempotency_key': context['idempotency_key']}
    output, observed = sdk_forecast_request(fake_sdk, sdk_client, context, tool, args)
    assert output['status'] == 'succeeded', output
    assert len(NORTHSTAR_TOOL_IDS) == 16
    assert [step['tool'] for step in output['steps']] == ['list_budget_requests', tool]
    assert output['steps'][1]['args'] == args
    assert observed and not observed[0].get('error') and not observed[0].get('truncated')
    receipt = output['output']['forecast_receipts'][0]
    assert receipt == {'tool': tool, 'args': args, 'receipt': observed[0]}
    prompt = fake_droid_sdk.STATE['prompt']
    assert old in prompt and 'never substitute the newest run' in prompt
    if action == 'explain':
        explained = receipt['receipt']
        assert explained['run_id'] == old
        assert explained['views'][0]['scope']['type'] == 'company'
        assert explained['views'][0]['scope']['id'] == 'northstar'
        assert {effect['driver_id'] for effect in explained['driver_effects']} == {driver}
        assert explained['calculations']
        assert explained['views'][0]['included_drivers'][0]['citations']
    elif action == 'compare':
        assert [run['run_id'] for run in receipt['receipt']['runs']] == [old, newest]
    elif action == 'preview':
        assert receipt['receipt']['parent_run_id'] == old
        assert receipt['receipt']['status'] == 'succeeded'
        assert service.get_scenario(receipt['receipt']['scenario_id'])['parent_run_id'] == old
    else:
        assert receipt['receipt']['status'] == 'queued'
        assert service.store.find_job('northstar', context['idempotency_key'])['id'] == receipt['receipt']['id']
    assert service.store.publication()['run_id'] == newest
    assert service.store.get_run(old)['bundle'] == original


def test_sdk_cannot_substitute_newest_run_for_exact_context(fake_sdk, sdk_client, published_pair):
    _, (old, newest) = published_pair
    context = {'action': 'explain', 'run_id': old, 'scope_type': 'company', 'scope_id': 'northstar'}
    output, observed = sdk_forecast_request(fake_sdk, sdk_client, context, 'explain_forecast',
                                           {'run_id': newest, 'scope_type': 'company', 'scope_id': 'northstar'})
    assert observed[0].get('error'), 'Exact-run task accepted an SDK substitution of the newest run'
    assert not output['output'].get('forecast_receipts')


def test_sdk_cannot_refresh_while_explaining_frozen_run(fake_sdk, sdk_client, published_pair):
    service, (old, _) = published_pair
    context = {'action': 'explain', 'run_id': old, 'scope_type': 'company', 'scope_id': 'northstar'}
    _, observed = sdk_forecast_request(fake_sdk, sdk_client, context, 'request_forecast_refresh',
                                      {'idempotency_key': 'unrequested-sdk-refresh'})
    assert observed[0].get('error'), 'Explain-only task accepted a model-initiated forecast refresh'
    assert service.store.find_job('northstar', 'unrequested-sdk-refresh') is None


@pytest.mark.parametrize('change', [
    {'scope_type': 'team', 'scope_id': 'research'},
    {'driver_id': 'not-the-requested-driver'},
])
def test_sdk_cannot_change_exact_scope_or_driver(fake_sdk, sdk_client, published_pair, change):
    _, (old, _) = published_pair
    context = {'action': 'explain', 'run_id': old, 'scope_type': 'company', 'scope_id': 'northstar'}
    _, observed = sdk_forecast_request(fake_sdk, sdk_client, context, 'explain_forecast',
                                      {'run_id': old, 'scope_type': 'company', 'scope_id': 'northstar', **change})
    assert observed[0]['error']['code'] == 'forecast_context_mismatch'


def test_sdk_cannot_replace_pinned_forecast_with_current_provider(fake_sdk, sdk_client, published_pair):
    _, (old, _) = published_pair
    context = {'action': 'explain', 'run_id': old, 'scope_type': 'company', 'scope_id': 'northstar'}
    _, observed = sdk_forecast_request(fake_sdk, sdk_client, context, 'get_forecast', {})
    assert observed[0]['error']['code'] == 'forecast_context_mismatch'


def test_sdk_generic_user_refresh_request_retains_tool_access(fake_sdk, sdk_client, published_pair):
    service, _ = published_pair
    observed = []
    fake_sdk.SCENARIO = [fake_droid_sdk.Step(
        'text(await tools.northstar.request_forecast_refresh({idempotency_key: "explicit-refresh"}));',
        lambda call: observed.append(call('request_forecast_refresh', idempotency_key='explicit-refresh')),
    )]
    response = sdk_client.post('/api/agent/runs', headers=ANALYST, json={
        'task_type': 'answer_question', 'instruction': 'Please refresh the forecast now using explicit-refresh.',
    })
    assert response.json()['status'] == 'succeeded'
    assert not observed[0].get('error')
    assert service.store.find_job('northstar', 'explicit-refresh')['id'] == observed[0]['id']


def test_fake_scenario_answer_names_pending_status_and_failure(sdk_app, sdk_client, published_pair):
    from app.agent.fake_runner import FakeDroidRunner
    service, (old, _) = published_pair
    def unavailable_builder(*args, **kwargs):
        raise RuntimeError('temporary calculation outage')
    service.builder = unavailable_builder
    sdk_app.state.droid_runner = FakeDroidRunner()
    response = sdk_client.post('/api/agent/runs', headers=ANALYST, json={
        'task_type': 'answer_question', 'instruction': 'Preview this scenario.',
        'params': {'forecast_context': {'action': 'preview', 'run_id': old,
                   'scope_type': 'company', 'scope_id': 'northstar', 'drivers': []}},
    })
    output = response.json()
    assert output['status'] == 'succeeded'
    receipt = output['output']['forecast_receipts'][0]['receipt']
    assert receipt['status'] == 'queued'
    assert 'status queued' in output['summary']
    assert 'temporary calculation outage' in output['summary']
    assert receipt['job_id'] in output['summary']


def test_sdk_cannot_attach_latest_forecast_chart_to_pinned_run(fake_sdk, sdk_client, published_pair):
    _, (old, _) = published_pair
    context = {'action': 'explain', 'run_id': old, 'scope_type': 'company', 'scope_id': 'northstar'}
    output, observed = sdk_forecast_request(fake_sdk, sdk_client, context, 'build_chart_spec',
                                          {'kind': 'projection_vs_allocation'})
    assert observed[0].get('error', {}).get('code') == 'forecast_context_mismatch'
    assert not output['output'].get('charts')


def test_sdk_full_company_explanation_is_readable_after_native_capture(fake_sdk, sdk_client, published_pair):
    service, (old, _) = published_pair
    context = {'action': 'explain', 'run_id': old, 'scope_type': 'company', 'scope_id': 'northstar'}
    snapshot = service.store.get_snapshot(service.store.get_run(old)['snapshot_id'])
    from app.forecasting.archive import resolve_material
    from app.agent.toolbox import _compact_forecast_receipt
    from northstar_droid.sdk_tools import _respond
    with service.store.transaction() as connection:
        material = resolve_material(connection, snapshot['repository_state'][0], tenant_id='northstar')
    assert len(json.dumps(material)) > 60000
    # Previously issued runs may contain the full immutable v1 capture, while
    # current captures reference the same archived material compactly.
    legacy = service.explain(old, 'company', 'northstar')
    legacy['snapshot']['repository_state'] = [
        {'repository_capture_version': 1, 'repository_material': material},
    ]
    assert not json.loads(_respond(lambda: _compact_forecast_receipt(legacy))).get('truncated')
    _, observed = sdk_forecast_request(fake_sdk, sdk_client, context, 'explain_forecast',
                                      {'run_id': old, 'scope_type': 'company', 'scope_id': 'northstar'})
    assert not observed[0].get('truncated')
    assert observed[0]['run_id'] == old
    assert observed[0]['calculations']
    assert observed[0]['views'][0]['included_drivers'][0]['citations']
    assert 'repository_state' not in observed[0]['snapshot']


@pytest.mark.parametrize('scope_type,scope_id', [('company', 'northstar'), ('shared', 'shared')])
def test_sdk_native_repository_explanation_is_not_truncated(fake_sdk, sdk_app, sdk_client, scope_type, scope_id):
    service = sdk_app.state.forecast_service
    job = service.refresh('native-sdk-explanation')
    assert ForecastWorker(service).process_one(job_id=job['id'])
    context = {'action': 'explain', 'run_id': job['run_id'], 'scope_type': scope_type, 'scope_id': scope_id}
    _, observed = sdk_forecast_request(fake_sdk, sdk_client, context, 'explain_forecast',
                                      {'run_id': job['run_id'], 'scope_type': scope_type, 'scope_id': scope_id})
    assert not observed[0].get('truncated')
    assert observed[0]['calculations'][0]['components']
    assert observed[0]['snapshot']['repository_exclusion_summary']['count'] > 0


def test_exact_driver_compaction_preserves_zero_quarter_nonzero_weekly_effect():
    from app.agent.toolbox import _compact_forecast_receipt
    from forecasting.planning import build_forecast
    snapshot = build_northstar_snapshot()
    snapshot['drivers'] = [driver for driver in snapshot['drivers'] if driver['kind'] == 'project_schedule']
    bundle = build_forecast(snapshot, run_id='timing-only', generated_at=snapshot['generated_at'])
    effect = bundle['driver_effects'][0]
    assert effect['base_delta'] == 0
    assert any(point['base_delta'] for point in effect['weekly'])
    compact = _compact_forecast_receipt(bundle)
    assert compact['driver_effects'][0]['daily'] == effect['daily']
    assert compact['driver_effects'][0]['weekly'] == effect['weekly']


def test_sdk_comparison_allows_detail_for_its_pinned_run(fake_sdk, sdk_client, published_pair):
    _, (old, newest) = published_pair
    context = {'action': 'compare', 'run_id': old, 'compare_run_id': newest,
               'scope_type': 'company', 'scope_id': 'northstar'}
    _, observed = sdk_forecast_request(fake_sdk, sdk_client, context, 'explain_forecast',
                                      {'run_id': old, 'scope_type': 'company', 'scope_id': 'northstar'})
    assert not observed[0].get('error') and not observed[0].get('truncated')
    assert observed[0]['run_id'] == old
