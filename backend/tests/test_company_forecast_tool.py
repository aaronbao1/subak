"""The SDK receives the issued company total, never an inferred sum of teams."""
from copy import deepcopy
from datetime import date
from types import SimpleNamespace

import pytest

from app.agent.toolbox import BackendToolbox
from app.db.models import AgentRun, PlanningPeriod
from app.db.session import transaction
from app.providers.engine import EngineForecastProvider
from app.schemas.forecasts import ForecastResult
from budget_helpers import seed_budget


def _inputs():
    result = ForecastResult(provider='engine', availability='available', target_period='2026-P1',
        method_label='issued', forecast_run_id='run_issued', input_snapshot_id='snapshot_issued',
        tenant_id='northstar', information_cutoff='2026-10-25T00:00:00Z')
    view = {'run_id': 'run_issued', 'snapshot_id': 'snapshot_issued',
            'scope': {'type': 'company', 'id': 'northstar'},
            'target': {'unit': 'USD', 'basis': 'planning', 'quantity': 'spend', 'timezone': 'UTC'},
            'publication': {'published_at': '2026-10-25T00:00:00Z'},
            'quarter_outlook': {'start': '2026-10-01', 'end': '2027-01-01',
                                'complete': True, 'base': 464485.19875}}
    run = {'id': 'run_issued', 'snapshot_id': 'snapshot_issued',
           'bundle': {'run_id': 'run_issued', 'views': [view]}}
    snapshot = {'tenant_id': 'northstar'}
    period = PlanningPeriod(id='2026-P1', starts_on=date(2026, 10, 1), ends_on=date(2026, 12, 31))
    return result, period, run, snapshot


def _summary(result, period, run, snapshot):
    from app.agent.toolbox import _company_projection
    from contextlib import nullcontext
    def read(run_id):
        assert run_id == 'run_issued', 'Read the receipt run, not a newer publication'
        return deepcopy(run), deepcopy(snapshot)
    store = SimpleNamespace(operation=nullcontext, get_issued_quarter_inputs=read)
    return _company_projection(result, period, SimpleNamespace(store=store)).model_dump(mode='json')


def test_exact_company_receipt_preserves_fractional_dollars_and_zero():
    result, period, run, snapshot = _inputs()
    summary = _summary(result, period, run, snapshot)
    assert summary['amount'] == '464485.19875'
    assert summary['availability'] == 'available'
    assert summary['scope'] == {'type': 'company', 'id': 'northstar'}
    assert summary['run_id'] == 'run_issued' and summary['input_snapshot_id'] == 'snapshot_issued'
    assert summary['period_start'] == '2026-10-01' and summary['period_end_exclusive'] == '2027-01-01'
    run['bundle']['views'][0]['quarter_outlook']['base'] = 0
    assert _summary(result, period, run, snapshot)['amount'] == '0'


@pytest.mark.parametrize('path,value', [
    ('scope.type', 'team'), ('scope.id', 'other'), ('target.unit', 'tokens'),
    ('target.quantity', 'tokens'), ('target.basis', 'billed'), ('target.timezone', 'US/Pacific'),
    ('quarter_outlook.start', '2026-10-02'), ('quarter_outlook.end', '2026-12-31'),
    ('quarter_outlook.complete', False), ('quarter_outlook.partial', True),
    ('quarter_outlook.base', None), ('quarter_outlook.base', -1), ('quarter_outlook.base', float('nan')),
    ('run_id', 'other'), ('snapshot_id', 'other'), ('publication.published_at', None),
])
def test_incompatible_company_value_is_unavailable_without_team_fallback(path, value):
    args = _inputs()
    view = args[2]['bundle']['views'][0]
    keys = path.split('.')
    target = view if len(keys) == 1 else view[keys[0]]
    target[keys[-1]] = value
    summary = _summary(*args)
    assert summary['availability'] == 'unavailable' and summary['amount'] is None
    assert summary['reason']


def test_missing_or_ambiguous_company_and_wrong_snapshot_are_unavailable():
    args = _inputs()
    args[2]['bundle']['views'] *= 2
    assert _summary(*args)['amount'] is None
    args[2]['bundle']['views'] = []
    assert _summary(*args)['amount'] is None
    args = _inputs()
    args[2]['snapshot_id'] = 'wrong'
    assert _summary(*args)['amount'] is None


def test_real_tool_exposes_same_run_company_without_changing_native_snapshot(app):
    seed_budget(app)
    store = app.state.forecast_service.store
    result, _, _, _ = _inputs()
    now = app.state.clock.now().isoformat()
    snapshot = {'id': 'snapshot_issued', 'tenant_id': 'northstar', 'information_cutoff': now,
                'observations': [], 'memberships': [], 'source_revisions': [], 'is_synthetic': True}
    store.save_snapshot(snapshot)
    job = store.enqueue('northstar', 'company-tool', snapshot['id'], now)
    claim = store.claim('test', now)
    view = _inputs()[2]['bundle']['views'][0]
    view['run_id'] = job['run_id']
    team = {**deepcopy(view), 'scope': {'type': 'team', 'id': 'research'},
            'quarter_outlook': {**view['quarter_outlook'], 'base': 10}}
    assert store.complete(job['id'], claim['lease_token'], {'run_id': job['run_id'],
        'procedure_version': 'test', 'views': [view, team]}, now)
    provider = EngineForecastProvider(app.state.forecast_service, app.state.session_factory)
    with transaction(app.state.session_factory) as session:
        session.add(AgentRun(id='agent_company', task_type='answer_question', input={},
                            runner_kind='fake', status='running', started_at=app.state.clock.now()))
    tools = BackendToolbox(session_factory=app.state.session_factory, run_id='agent_company',
        source='fake_runner', runner_kind='fake', clock=app.state.clock, ids=app.state.id_factory,
        forecast_provider=provider, forecast_service=app.state.forecast_service)
    out = tools.get_forecast()
    summary = out['forecast']['company_projection']
    assert summary['amount'] == '464485.19875', 'Includes shared spend; never sum the 10-dollar team'
    assert summary['run_id'] == out['forecast']['forecast_run_id'] == job['run_id']
    assert out['forecast']['projections'][0]['amount'] == '10.00'
    from app.services import forecasts
    with app.state.session_factory() as session:
        stored = forecasts.snapshot_out(forecasts.get_snapshot(session, out['id']))['forecast']
    assert 'company_projection' not in stored.model_dump()
