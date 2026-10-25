"""Benchmark regressions: leakage, native bins, common opportunity denominators."""
import importlib.util
from pathlib import Path

import pytest


def harness():
    path = Path(__file__).resolve().parents[1] / 'benchmarks/robustness/run.py'
    assert path.exists(), 'the reproducible benchmark harness is missing'
    spec = importlib.util.spec_from_file_location('robustness_benchmark', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_final_origins_are_chronological_nonoverlapping_and_preserve_horizon():
    b = harness()
    assert b.origins(100, horizon=4, context=16, final_fraction=.2) == (80, 84, 88, 92, 96)
    assert b.origins(100, horizon=1, context=16, final_fraction=.2) == tuple(range(80, 100))
    with pytest.raises(ValueError):
        b.origins(10, horizon=4, context=16)


def test_candidates_see_prefix_only_and_failure_keeps_opportunity_denominator():
    b = harness()
    seen = []
    def latest(prefix, horizon):
        seen.append(tuple(prefix))
        return [prefix[-1]] * horizon
    def unavailable(prefix, horizon):
        raise ValueError('checkpoint unavailable')
    rows = b.evaluate(tuple(range(1, 21)), (16, 18), 2, 4,
                      {'latest': latest, 'unavailable': unavailable})
    assert seen == [(13, 14, 15, 16), (15, 16, 17, 18)]
    summary = b.summarize(rows)
    assert summary['latest']['opportunities'] == 2
    assert summary['latest']['mae_tokens'] == 3
    assert summary['latest']['bias_tokens'] == -3
    assert summary['unavailable']['opportunities'] == 2
    assert summary['unavailable']['successes'] == 0
    assert summary['unavailable']['mae_tokens'] is None
    assert summary['unavailable']['failure_reasons'] == {'ValueError: checkpoint unavailable': 2}


def test_csv_requires_contiguous_native_bins_and_never_fills_unknown_gaps(tmp_path):
    b = harness()
    path = tmp_path / 'trace.csv'
    path.write_text('bin_start_seconds,total_tokens\n0,2\n60,3\n180,4\n')
    with pytest.raises(ValueError, match='contiguous'):
        b.load_series(path, 60)
    path.write_text('bin_start_seconds,total_tokens\n0,2\n60,3\n120,4\n')
    assert b.load_series(path, 60) == (2., 3., 4.)


def test_nonfinite_negative_or_misaligned_predictions_fail_instead_of_score():
    b = harness()
    candidates = {'nan': lambda p, h: [float('nan')],
                  'negative': lambda p, h: [-1],
                  'wrong_horizon': lambda p, h: [1, 2]}
    summary = b.summarize(b.evaluate((0.,) * 20, (16,), 1, 16, candidates))
    assert all(v['successes'] == 0 for v in summary.values())
    assert all(v['wape'] is None for v in summary.values())


def test_zero_truth_wape_is_undefined_and_slices_use_only_prefix_thresholds():
    b = harness()
    rows = b.evaluate((0.,) * 20, (16, 18), 2, 16, {'zero': lambda p, h: [0.] * h})
    assert b.summarize(rows)['zero']['wape'] is None
    assert all(row['slice_zero_target'] for row in rows)
    assert not any(row['slice_high_load_target'] for row in rows)


def test_pairwise_comparison_does_not_drop_successes_due_to_unrelated_candidate_failure():
    b = harness()
    rows = b.evaluate(tuple(range(1, 21)), (16, 18), 2, 4,
                      {'last_observation': lambda p,h: [p[-1]]*h,
                       'foundation': lambda p,h: [p[-1]+1]*h,
                       'unavailable': lambda p,h: (_ for _ in ()).throw(ValueError('no season'))})
    pair = b.paired_comparisons(rows)['foundation']
    assert pair['matched_opportunities'] == 2
    assert pair['mean_absolute_loss_difference_vs_last_tokens'] == -2
    assert pair['wins'] == 2
    assert pair['losses'] == 0


def test_procedure_identity_binds_checkpoint_source_context_and_origin_manifest():
    b = harness()
    base = dict(series_sha256='s', provenance_sha256='p', harness_sha256='h',
                foundation={'revision':'r1', 'weights_sha256':'w'}, context=64,
                origins={'1':[80,81], '4':[80,84]}, seasonal_period=None)
    first = b.procedure_identity(base)
    assert first == b.procedure_identity(dict(reversed(list(base.items()))))
    for key, replacement in [('context',32), ('series_sha256','other'),
                             ('foundation',{'revision':'r2', 'weights_sha256':'w'}),
                             ('origins',{'1':[80], '4':[80]})]:
        assert b.procedure_identity(dict(base, **{key:replacement})) != first


def test_cli_refuses_input_mutation_during_adapter_load(tmp_path):
    b = harness()
    source = tmp_path / 'trace.csv'
    source.write_text('bin_start_seconds,total_tokens\n'+''.join(f'{i},1\n' for i in range(100)))
    provenance = tmp_path / 'provenance.json'
    provenance.write_text('{}')
    adapter = tmp_path / 'adapter.py'
    adapter.write_text('from pathlib import Path\ndef load():\n'
                       f'    Path({str(source)!r}).write_text("changed")\n'
                       '    return None, {}\n')
    with pytest.raises(ValueError, match='input changed'):
        b.main(['--series',str(source),'--bin-seconds','1','--context','16',
                '--provenance',str(provenance),'--foundation-adapter',str(adapter),
                '--output',str(tmp_path/'results.json')])


def test_fixed_mean16_cannot_silently_run_on_less_than16_context_bins():
    b = harness()
    with pytest.raises(ValueError, match='at least 16'):
        b.run(tuple(range(100)), bin_seconds=3600, context=8)


def test_target_meter_cannot_relabel_provenance(tmp_path):
    b = harness()
    source = tmp_path / 'trace.csv'
    source.write_text('bin_start_seconds,total_tokens\n'+''.join(f'{i},1\n' for i in range(100)))
    provenance = tmp_path / 'provenance.json'
    provenance.write_text('{"target_meter":"input_tokens"}')
    with pytest.raises(ValueError, match='target meter'):
        b.main(['--series',str(source),'--bin-seconds','1','--provenance',str(provenance),
                '--target-meter','output_tokens','--output',str(tmp_path/'results.json')])


@pytest.mark.parametrize('metadata_expression', ['None', "{'invalid': object()}",
                                                "{'invalid': float('nan')}"])
def test_metadata_load_failure_cannot_leave_scored_foundation_callable(tmp_path, metadata_expression):
    b = harness()
    source = tmp_path / 'trace.csv'
    source.write_text('bin_start_seconds,total_tokens\n'+''.join(f'{i},1\n' for i in range(100)))
    provenance = tmp_path / 'provenance.json'
    provenance.write_text('{}')
    adapter = tmp_path / 'adapter.py'
    if metadata_expression != 'None':
        metadata_expression = ("dict(checkpoint='unit-test-only', revision='test-revision', "
                               "weights_sha256='a'*64, dependencies={'test-runtime':'1.0'}, "
                               "point_statistic='point', projection='none', device='unit-test-only', "
                               "**"+metadata_expression+")")
    adapter.write_text('def load():\n'
                       f'    return lambda prefix,horizon: [1.0]*horizon, {metadata_expression}\n')
    output = tmp_path / 'results.json'
    b.main(['--series',str(source),'--bin-seconds','1','--provenance',str(provenance),
            '--foundation-adapter',str(adapter),'--max-origins','2','--output',str(output)])
    import json
    result = json.loads(output.read_text())
    assert result['foundation']['load_failure']
    assert result['horizons']['1']['origin_indices'] == [80,99]
    assert result['horizons']['4']['origin_indices'] == [80,96]
    for horizon in result['horizons'].values():
        scored = horizon['summaries']['foundation']
        assert scored['opportunities'] == 2
        assert scored['successes'] == 0
        assert scored['failures'] == 2
        assert scored['availability'] == 0
        assert scored['mae_tokens'] is None
        assert sum(scored['failure_reasons'].values()) == 2
        assert all(r['prediction_tokens'] is None for r in horizon['records']
                   if r['candidate'] == 'foundation')


@pytest.mark.parametrize('missing', ['checkpoint','revision','weights_sha256','dependencies',
                                     'point_statistic','projection','device'])
def test_genuine_foundation_requires_complete_checkpoint_runtime_manifest(tmp_path, missing):
    b = harness()
    metadata = dict(checkpoint='unit-test-only', revision='immutable-test-revision',
                    weights_sha256='a'*64, dependencies={'test-runtime':'1.0'},
                    point_statistic='point', projection='none', device='unit-test-only')
    del metadata[missing]
    source = tmp_path / 'trace.csv'
    source.write_text('bin_start_seconds,total_tokens\n'+''.join(f'{i},1\n' for i in range(100)))
    provenance = tmp_path / 'provenance.json'
    provenance.write_text('{}')
    adapter = tmp_path / 'adapter.py'
    adapter.write_text(f'def load():\n    return lambda p,h: [1.0]*h, {metadata!r}\n')
    output = tmp_path / 'results.json'
    b.main(['--series',str(source),'--bin-seconds','1','--provenance',str(provenance),
            '--foundation-adapter',str(adapter),'--max-origins','2','--output',str(output)])
    import json
    result = json.loads(output.read_text())
    assert missing in result['foundation']['load_failure']
    for horizon in result['horizons'].values():
        assert horizon['summaries']['foundation']['opportunities'] == 2
        assert horizon['summaries']['foundation']['successes'] == 0


def test_foundation_identity_ignores_runtime_observations_but_binds_model_behavior():
    b = harness()
    metadata = dict(checkpoint='official-model', revision='fixed-revision',
                    weights_sha256='a'*64, dependencies={'torch':'2.2.2'},
                    point_statistic='marginal median', projection='clip_nonnegative',
                    device='cpu', dtype='float32', cpu_threads=2, seed=0,
                    config_sha256='b'*64, adapter_sha256='c'*64,
                    acquisition_seconds=1., model_load_seconds=2., cold_load_seconds=3.,
                    runtime_observations={'warmup_seconds':4., 'cache_hit':False})
    first = b.procedure_identity({'foundation':b.foundation_procedure_metadata(metadata)})
    different_time = dict(metadata, acquisition_seconds=10., model_load_seconds=20.,
                          cold_load_seconds=30., runtime_observations={'warmup_seconds':40.,'cache_hit':True})
    assert b.procedure_identity({'foundation':b.foundation_procedure_metadata(different_time)}) == first
    for key,value in [('checkpoint','different-model'),('dependencies',{'torch':'2.3.0'}),
                      ('projection','none'),('config_sha256','d'*64),('dtype','float64'),
                      ('cpu_threads',4),('adapter_sha256','e'*64)]:
        assert b.procedure_identity({'foundation':b.foundation_procedure_metadata(dict(metadata, **{key:value}))}) != first
    # Explicit classification prevents new semantic parameters being silently
    # dropped from a stable allowlist.
    with pytest.raises(ValueError, match='classif'):
        b.foundation_procedure_metadata(dict(metadata, undeclared_model_parameter='changed'))


def test_cli_procedure_id_is_stable_across_observed_load_timings(tmp_path):
    import json
    b = harness()
    source = tmp_path / 'trace.csv'
    source.write_text('bin_start_seconds,total_tokens\n'+''.join(f'{i},1\n' for i in range(100)))
    provenance = tmp_path / 'provenance.json'
    provenance.write_text('{}')
    metadata_path = tmp_path / 'metadata.json'
    metadata = dict(checkpoint='unit-test-only', revision='fixed-test-revision',
                    weights_sha256='a'*64, dependencies={'test-runtime':'1.0'},
                    point_statistic='point', projection='none', device='unit-test-only',
                    acquisition_seconds=1., model_load_seconds=2.)
    adapter = tmp_path / 'adapter.py'
    adapter.write_text('import json\nfrom pathlib import Path\ndef load():\n'
                       f'    return lambda p,h: [1.0]*h, json.loads(Path({str(metadata_path)!r}).read_text())\n')
    output = tmp_path / 'results.json'
    args = ['--series',str(source),'--bin-seconds','1','--provenance',str(provenance),
            '--foundation-adapter',str(adapter),'--max-origins','2','--output',str(output)]
    metadata_path.write_text(json.dumps(metadata))
    b.main(args)
    first = json.loads(output.read_text())
    metadata.update(acquisition_seconds=10.,model_load_seconds=20.)
    metadata_path.write_text(json.dumps(metadata))
    b.main(args)
    second = json.loads(output.read_text())
    assert first['procedure_identity'] == second['procedure_identity']
    assert first['foundation']['model_load_seconds'] == 2.
    assert second['foundation']['model_load_seconds'] == 20.
    assert 'model_load_seconds' not in second['procedure_manifest']['foundation']
    assert 'acquisition_seconds' not in second['procedure_manifest']['foundation']
    metadata['checkpoint'] = 'different-unit-test-model'
    metadata_path.write_text(json.dumps(metadata))
    b.main(args)
    third = json.loads(output.read_text())
    assert third['procedure_identity'] != second['procedure_identity']
