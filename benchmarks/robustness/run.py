#!/usr/bin/env python3
"""Reproducible native-bin token-load benchmark; optional genuine model adapter.

No benchmark dependency enters the standard-library product package. Run with
PYTHONPATH=src python benchmarks/robustness/run.py --help.
"""
from __future__ import annotations

import argparse
from collections.abc import Mapping
import csv
from datetime import date, datetime, timedelta, timezone
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import statistics
import time


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def procedure_identity(manifest):
    return hashlib.sha256(json.dumps(manifest, sort_keys=True, separators=(',', ':'),
                                     allow_nan=False).encode()).hexdigest()


FOUNDATION_PROCEDURE_FIELDS = frozenset((
    'checkpoint','revision','weights_sha256','dependencies','point_statistic',
    'projection','device','adapter_sha256','config_sha256','dtype','cpu_threads',
    'seed','license','weight_bytes','source_url','calibration',
    'pretraining_contamination','configuration','preprocessing','output_transform',
    'fit_policy','inference_config'))
FOUNDATION_OBSERVATION_FIELDS = frozenset((
    'cold_load_seconds','acquisition_seconds','model_load_seconds',
    'runtime_observations','load_failure'))


def foundation_procedure_metadata(metadata):
    """Bind declared model behavior; preserve runtime observations only in report.

    New fields require an explicit classification so adding an adapter parameter
    cannot silently omit it from the procedure identity. Arbitrary new runtime
    measurements belong inside ``runtime_observations``.
    """
    metadata = metadata or {}
    unclassified = set(metadata)-FOUNDATION_PROCEDURE_FIELDS-FOUNDATION_OBSERVATION_FIELDS
    if unclassified:
        raise ValueError('foundation metadata fields require classification: '+', '.join(sorted(unclassified)))
    return {key:metadata[key] for key in FOUNDATION_PROCEDURE_FIELDS if key in metadata}


def load_series(path, bin_seconds):
    """Consume complete, contiguous native bins; missing bins remain unknown."""
    if not math.isfinite(bin_seconds) or bin_seconds <= 0:
        raise ValueError('positive native bin duration required')
    with Path(path).open(newline='') as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise ValueError('empty series')
    values, starts = [], []
    for row in rows:
        start = float(row['bin_start_seconds'])
        value = float(row['total_tokens'])
        if not math.isfinite(start) or not math.isfinite(value) or value < 0:
            raise ValueError('native token counts and timestamps must be finite/nonnegative')
        starts.append(start)
        values.append(value)
    if any(not math.isclose(b-a, bin_seconds, rel_tol=0, abs_tol=1e-6)
           for a, b in zip(starts, starts[1:])):
        raise ValueError('complete contiguous native bins required; unknown gaps cannot become zero')
    return tuple(values)


def origins(n, horizon, context=64, final_fraction=.2):
    if horizon < 1 or context < 1 or not 0 < final_fraction < 1:
        raise ValueError('invalid heldout origin protocol')
    start = max(context, math.ceil(n * (1-final_fraction)))
    result = tuple(range(start, n-horizon+1, horizon))
    if not result:
        raise ValueError('insufficient observations for final heldout targets')
    return result


def evaluate(values, origin_indices, horizon, context, candidates):
    """Every procedure receives the same prefix and every failure remains a row."""
    rows = []
    for origin in origin_indices:
        if origin < context or origin + horizon > len(values):
            raise ValueError('origin outside common eligible range')
        prefix = tuple(values[origin-context:origin])
        truth = math.fsum(values[origin:origin+horizon])
        # Slices are fixed rules with thresholds computed only from prefix.
        level = statistics.mean(prefix)
        spread = statistics.pstdev(prefix)
        high = truth > horizon*(level+2*spread)
        burst = max(values[origin:origin+horizon]) > level+3*spread
        for name, predict in candidates.items():
            row = dict(candidate=name, origin_index=origin, target_end_exclusive=origin+horizon,
                       horizon_bins=horizon, truth_tokens=truth, prediction_tokens=None,
                       failure=None, latency_seconds=None,
                       slice_zero_target=truth == 0, slice_high_load_target=high,
                       slice_burst_target=burst)
            started = time.perf_counter()
            try:
                path = tuple(float(x) for x in predict(prefix, horizon))
                if len(path) != horizon or any(not math.isfinite(x) or x < 0 for x in path):
                    raise ValueError('prediction must be aligned finite nonnegative native tokens')
                total = math.fsum(path)
                if not math.isfinite(total):
                    raise ValueError('nonfinite cumulative forecast')
                row['prediction_tokens'] = total
                row['prediction_path_tokens'] = path
                row['error_tokens'] = total-truth
            except Exception as exc:
                row['failure'] = type(exc).__name__ + ': ' + str(exc)
            row['latency_seconds'] = time.perf_counter()-started
            rows.append(row)
    return rows


def summarize(rows):
    output = {}
    for name in sorted({r['candidate'] for r in rows}):
        all_rows = [r for r in rows if r['candidate'] == name]
        valid = [r for r in all_rows if r['failure'] is None]
        errors = [r['error_tokens'] for r in valid]
        denom = math.fsum(abs(r['truth_tokens']) for r in valid)
        reasons = {}
        for r in all_rows:
            if r['failure']:
                reasons[r['failure']] = reasons.get(r['failure'], 0)+1
        output[name] = dict(opportunities=len(all_rows), successes=len(valid),
            failures=len(all_rows)-len(valid), availability=len(valid)/len(all_rows),
            mae_tokens=statistics.mean(map(abs, errors)) if errors else None,
            rmse_tokens=math.sqrt(statistics.mean(e*e for e in errors)) if errors else None,
            bias_tokens=statistics.mean(errors) if errors else None,
            wape=math.fsum(map(abs, errors))/denom if denom else None,
            worst_absolute_loss_tokens=max(map(abs, errors)) if errors else None,
            latency_seconds_total=math.fsum(r['latency_seconds'] for r in all_rows),
            latency_seconds_median=statistics.median(r['latency_seconds'] for r in all_rows),
            failure_reasons=reasons)
    return output


def paired_comparisons(rows):
    """Descriptive matched-origin differences; unrelated failures cannot select cases."""
    baseline = {r['origin_index']:r for r in rows
                if r['candidate'] == 'last_observation' and r['failure'] is None}
    output = {}
    for name in sorted({r['candidate'] for r in rows}):
        matched = [r for r in rows if r['candidate'] == name and r['failure'] is None
                   and r['origin_index'] in baseline]
        differences = [abs(r['error_tokens'])-abs(baseline[r['origin_index']]['error_tokens'])
                       for r in matched]
        output[name] = dict(matched_opportunities=len(matched),
            mean_absolute_loss_difference_vs_last_tokens=statistics.mean(differences) if differences else None,
            wins=sum(d < 0 for d in differences), ties=sum(d == 0 for d in differences),
            losses=sum(d > 0 for d in differences))
    return output


def joint(prefix, horizon):
    """Use production joint law with arbitrary consecutive *index* dates only.

These dates have no relation to trace time and imply no day/month evidence.
"""
    from forecasting.contracts import Target
    from forecasting.joint import JointUnavailable, SeriesAxis, fit_joint_blocks
    from forecasting.models import Series
    base = date(2000, 1, 1)
    axis = SeriesAxis('public-trace', 'total_tokens', 'observed', 'public-trace', 'tokens')
    dates = tuple(base+timedelta(days=i) for i in range(len(prefix)))
    origin = base+timedelta(days=len(prefix))
    bundle = fit_joint_blocks((Series('public-trace', dates, prefix),),
        target=Target('native-token-load', 'public-trace', 'metered_usage', 'tokens', None,
                      ('public-trace',), ('usage',), support='nonnegative'),
        snapshot_id=hashlib.sha256(json.dumps(prefix).encode()).hexdigest(),
        as_of=datetime.combine(origin, datetime.min.time(), timezone.utc),
        dates=tuple(origin+timedelta(days=i) for i in range(horizon)), axes=(axis,),
        n_paths=200, seed=0, baseline='trailing_mean', baseline_config={'window':16},
        evidence_class='public_trace')
    if isinstance(bundle, JointUnavailable):
        raise ValueError(bundle.reason)
    return tuple(math.fsum(float(p[0][i])*w for p,w in zip(bundle.values,bundle.weights))
                 for i in range(horizon))


def run(values, *, bin_seconds, context=64, foundation=None, foundation_metadata=None,
        seasonal_period=None, max_origins=None):
    if context < 16:
        raise ValueError('at least 16 context bins required by fixed mean16 procedure')
    candidates = {'last_observation': lambda p,h: [p[-1]]*h,
                  'trailing_mean_16': lambda p,h: [statistics.mean(p[-16:])]*h,
                  'zero_diagnostic': lambda p,h: [0.]*h, 'joint_block_mean': joint}
    if seasonal_period:
        if seasonal_period > context or seasonal_period < 1:
            raise ValueError('seasonal period must fit common context')
        candidates['seasonal_naive'] = lambda p,h: [p[-seasonal_period+i%seasonal_period] for i in range(h)]
    else:
        def seasonal_unavailable(p,h):
            raise ValueError('no externally supported repeated seasonal period declared')
        candidates['seasonal_naive'] = seasonal_unavailable
    if foundation is not None:
        candidates['foundation'] = foundation
    else:
        def foundation_unavailable(p,h):
            raise ValueError('genuine pretrained checkpoint/runtime not supplied')
        candidates['foundation'] = foundation_unavailable
    report = dict(schema='native-token-benchmark-v1', unit='tokens', bin_seconds=bin_seconds,
                  observations=len(values), total_tokens=math.fsum(values), context_bins=context,
                  protocol='fixed zero-shot procedures; no D/C selection or fitted calibration; final 20% chronological',
                  final_fraction=.2, seed=0, foundation=foundation_metadata,
                  internal_joint_dates='arbitrary integer-bin index mapped to consecutive date API; not calendar-day evidence',
                  forecast_statistics={'foundation':'native adapter point; see model metadata',
                                       'joint_block_mean':'empirical joint-path mean, uncalibrated',
                                       'last_observation':'point', 'trailing_mean_16':'point',
                                       'seasonal_naive':'point'},
                  limitations=['one public serving trace, not companies or enterprise invoices',
                               'pretraining contamination unknown',
                               'no monthly/daily financial validation or empirical probability calibration',
                               'native bins assumed fully observed only per accompanying acquisition provenance',
                               'success-conditional loss must be read alongside all-opportunity availability'])
    report['horizons'] = {}
    for horizon in (1,4):
        selected = origins(len(values), horizon, context)
        # Explicit deterministic cap permits a practical feasibility run without
        # selecting origins on outcomes or model successes. Keep endpoint coverage.
        if max_origins and len(selected) > max_origins:
            if max_origins < 2:
                raise ValueError('max_origins must be at least two')
            selected = tuple(selected[round(i*(len(selected)-1)/(max_origins-1))]
                             for i in range(max_origins))
        records = evaluate(values, selected, horizon, context, candidates)
        common = tuple(o for o in selected if all(r['failure'] is None for r in records
                       if r['origin_index'] == o))
        report['horizons'][str(horizon)] = dict(horizon_seconds=horizon*bin_seconds,
            origin_indices=selected, nonoverlapping_target_blocks=len(selected),
            origin_manifest_sha256=hashlib.sha256(json.dumps(selected).encode()).hexdigest(),
            summaries=summarize(records),
            paired_vs_last_observation=paired_comparisons(records),
            matched_success_origins=common,
            matched_success_summaries=summarize([r for r in records if r['origin_index'] in common]),
            slices={name:summarize([r for r in records if r[name]]) for name in
                    ('slice_zero_target','slice_high_load_target','slice_burst_target')},
            records=records)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--series', type=Path, required=True)
    parser.add_argument('--bin-seconds', type=float, required=True)
    parser.add_argument('--provenance', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--context', type=int, default=64)
    parser.add_argument('--target-meter', choices=('total_tokens','input_tokens','output_tokens'),
                        default='total_tokens')
    parser.add_argument('--max-origins', type=int)
    parser.add_argument('--seasonal-period', type=int)
    parser.add_argument('--foundation-adapter', type=Path,
                        help='module exporting load() -> (predict(prefix,horizon), metadata)')
    args = parser.parse_args(argv)
    input_hashes = {'series_sha256':sha256(args.series),
                    'provenance_sha256':sha256(args.provenance)}
    provenance = json.loads(args.provenance.read_text())
    if provenance.get('target_meter', args.target_meter) != args.target_meter:
        raise ValueError('target meter conflicts with acquired source provenance')
    if provenance.get('canonical_sha256', input_hashes['series_sha256']) != input_hashes['series_sha256']:
        raise ValueError('source hash conflicts with acquired source provenance')
    values = load_series(args.series, args.bin_seconds)
    foundation, metadata = None, None
    if args.foundation_adapter:
        started = time.perf_counter()
        adapter_identity = {}
        try:
            adapter_identity['adapter_sha256'] = sha256(args.foundation_adapter)
            spec = importlib.util.spec_from_file_location('genuine_foundation_adapter', args.foundation_adapter)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            candidate_predict, candidate_metadata = module.load()
            if not callable(candidate_predict):
                raise ValueError('foundation adapter must return a prediction callable')
            if not isinstance(candidate_metadata, Mapping):
                raise ValueError('foundation adapter metadata must be a mapping')
            for field in ('checkpoint','revision','point_statistic','projection','device'):
                if not isinstance(candidate_metadata.get(field), str) or not candidate_metadata[field].strip():
                    raise ValueError('foundation adapter metadata requires nonempty '+field)
            dependencies = candidate_metadata.get('dependencies')
            if (not isinstance(dependencies, Mapping) or not dependencies or
                    any(not isinstance(k,str) or not k.strip() or
                        not isinstance(v,str) or not v.strip() for k,v in dependencies.items())):
                raise ValueError('foundation adapter metadata requires nonempty dependencies name/version mapping')
            hashes = candidate_metadata.get('weights_sha256')
            if isinstance(hashes, str):
                hashes = {'weights':hashes}
            if (not isinstance(hashes, Mapping) or not hashes or
                    any(not isinstance(k,str) or not k.strip() or
                        not isinstance(v,str) or len(v) != 64 or
                        any(c not in '0123456789abcdef' for c in v) for k,v in hashes.items())):
                raise ValueError('foundation adapter metadata requires weights_sha256 lowercase SHA256 identity')
            candidate_metadata = dict(candidate_metadata,
                cold_load_seconds=time.perf_counter()-started,
                **adapter_identity)
            # Validate and detach the complete manifest before admitting any
            # callable: invalid provenance must never produce scored forecasts.
            metadata = json.loads(json.dumps(candidate_metadata, allow_nan=False))
            foundation_procedure_metadata(metadata)
            foundation = candidate_predict
        except Exception as exc:
            foundation = None
            metadata = dict(adapter_identity, load_failure=type(exc).__name__+': '+str(exc),
                            cold_load_seconds=time.perf_counter()-started)
    report = run(values, bin_seconds=args.bin_seconds, context=args.context,
                 foundation=foundation, foundation_metadata=metadata,
                 seasonal_period=args.seasonal_period, max_origins=args.max_origins)
    if (sha256(args.series) != input_hashes['series_sha256'] or
            sha256(args.provenance) != input_hashes['provenance_sha256']):
        raise ValueError('input changed during benchmark execution')
    report['target_meter'] = args.target_meter
    report['inputs'] = dict(input_hashes, **{'series_path':str(args.series),
                        'provenance_path':str(args.provenance),
                        'provenance':provenance,
                        'harness_sha256':sha256(__file__)})
    # Freeze the complete procedure rather than only a display candidate name.
    # Latencies are observations, not procedure parameters.
    model_identity = foundation_procedure_metadata(metadata)
    report['procedure_manifest'] = {
        'series_sha256':report['inputs']['series_sha256'],
        'provenance_sha256':report['inputs']['provenance_sha256'],
        'harness_sha256':report['inputs']['harness_sha256'],
        'joint_implementation_sha256':sha256(Path(__file__).resolve().parents[2]/'src/forecasting/joint.py'),
        'model_implementation_sha256':sha256(Path(__file__).resolve().parents[2]/'src/forecasting/models.py'),
        'foundation':model_identity, 'context':args.context,
        'origins':{h:v['origin_indices'] for h,v in report['horizons'].items()},
        'seasonal_period':args.seasonal_period, 'seed':0, 'target_meter':args.target_meter,
        'mean_window':16, 'joint_paths':200, 'joint_baseline':'trailing_mean',
        'joint_projection':'clip_nonnegative', 'baseline_projection':'none',
        'fit_policy':'zero-shot pretrained, joint residual fit per origin on prefix only',
        'calibration':'none', 'pricing':'none', 'fallback':'record failure, no substitution'}
    report['procedure_identity'] = procedure_identity(report['procedure_manifest'])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    print(json.dumps({'output':str(args.output), 'horizons':{h:v['summaries'] for h,v in report['horizons'].items()}}, indent=2))


if __name__ == '__main__':
    main()
