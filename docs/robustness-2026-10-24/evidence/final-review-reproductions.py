"""Bounded review probes. Run with PYTHONPATH=src:tests; never allocates huge laws."""
from dataclasses import fields, replace
from datetime import timedelta
from decimal import Decimal, localcontext, ROUND_DOWN, ROUND_UP
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from forecasting.contracts import digest
from forecasting.joint import SeriesAxis
from forecasting.joint_service import _summaries
from forecasting.snapshot import Snapshot
from forecasting.state import ExposureSpell, HurdleParameters, ExecutionMark, generate_recurrent_scenarios
from test_joint_service import fixture, axes, commercial_options
from test_state import ORIGIN, DATES, TARGET, spell


def snapshot_with(snapshot, **changes):
    body = {f.name: getattr(snapshot, f.name) for f in fields(snapshot)
            if f.name not in {'snapshot_id', 'schema_version'}}
    body.update(changes)
    return Snapshot(digest(body), **body)


report = {}
with TemporaryDirectory() as tmp:
    service, snapshot, request = fixture(Path(tmp), output='full_period')
    dimensions = (SeriesAxis('team:a', 'input', 'model', 'pool', 'tokens'),
                  SeriesAxis('team:a', 'output', 'model', 'pool', 'tokens'))
    mapping = {'a': dimensions[0].axis_id, 'b': dimensions[1].axis_id}
    snapshot = snapshot_with(snapshot, daily=tuple(replace(row, entity_id=mapping[row.entity_id])
                                                   for row in snapshot.daily))
    request = replace(request, period_start=snapshot.history_start)
    result = service.run_joint(request, snapshot, allowed_sources={'usage'}, axes=dimensions, n_paths=2)
    report['multi_axis_actuals'] = {'expected_team_recorded': '300',
                                   'actual_entities': result['entities'],
                                   'company_mean': result['usage']['mean']}

with TemporaryDirectory() as tmp:
    service, snapshot, request = fixture(Path(tmp))
    options = dict(axes=axes(), allowed_sources={'usage'}, n_paths=2, threshold=Decimal('19.99'),
                   commercial_options=commercial_options(request), monetary_threshold=Decimal('22.99'))
    normal = service.run_joint(request, snapshot, **options)
    with localcontext() as context:
        context.prec = 3
        low = service.run_joint(request, snapshot, **options)
    report['ambient_decimal'] = {
        name: {view: {key: result[view][key] for key in
                      ('mean', 'threshold', 'exceedance_probability', 'expected_excess')}
               for view in ('usage', 'monetary')}
        for name, result in [('default', normal), ('precision_3', low)]}
    modes = {}
    for mode in (ROUND_DOWN, ROUND_UP):
        with localcontext() as context:
            context.rounding = mode
            modes[mode] = _summaries((0, 1, 1), (1/3,)*3, (.5,), None, .95)['mean']
    report['ambient_rounding'] = modes

with TemporaryDirectory() as tmp:
    service, snapshot, request = fixture(Path(tmp))
    service.max_entities = 2
    exposures = tuple(ExposureSpell('access-'+p, p, 'c', request.period_start, request.period_end,
                                    request.as_of, True) for p in ('x', 'y', 'z'))
    result = service.run_joint(request, snapshot, allowed_sources={'usage'}, n_paths=1,
        state_inputs={'exposures': exposures, 'events': (),
                      'parameters': (HurdleParameters('c', 1, marks=(ExecutionMark(1),)),)})
    report['structural_entity_bound'] = {'configured_max_entities': service.max_entities,
        'generated_entities': [key for key, value in result['entities'].items() if value['future'] is not None]}

class AllocationReached(Exception):
    pass

with patch('forecasting.state.random.Random', side_effect=AllocationReached):
    try:
        generate_recurrent_scenarios((spell(access=True),), (),
            (HurdleParameters('team', 1, (10000,), (ExecutionMark(1),)),), as_of=ORIGIN,
            dates=DATES, path_count=10**9, seed=0, target=TARGET, snapshot_id='s')
    except AllocationReached:
        report['structural_work_bound'] = 'Accepted through all pre-generation checks: 1e9 paths * 3 days * 10000 roots. Sentinel stopped before allocation.'

with TemporaryDirectory() as tmp:
    service, snapshot, request = fixture(Path(tmp), output='full_period')
    snapshot = snapshot_with(snapshot,
        daily=tuple(replace(row, value=Decimal('1e308')) for row in snapshot.daily),
        company_daily=tuple(replace(row, value=Decimal('2e308')) for row in snapshot.company_daily))
    request = replace(request, period_start=snapshot.history_start,
                      period_end=request.period_start+timedelta(days=1), model='last_observation')
    try:
        result = service.run_joint(request, snapshot, allowed_sources={'usage'}, axes=axes(), n_paths=1)
        report['derived_overflow_isolation'] = {'recorded': result['result']['recorded'],
                                                'future': result['result']['future']}
    except Exception as error:
        report['derived_overflow_isolation'] = {'raised': type(error).__name__, 'message': str(error),
                                                'actuals_response_returned': False}

print(json.dumps(report, indent=2))
