"""Immutable aligned path laws and an honest rolling historical block baseline.

Series are already authorized, availability-qualified snapshot projections. This
module cannot reconstruct observation receipt timestamps from a numeric Series.
Empirical support is conditional on block exchangeability, never calibration.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date, datetime, time, timedelta
from decimal import Decimal
import math
import random
from types import MappingProxyType
from typing import Mapping, Tuple
from zoneinfo import ZoneInfo

from .contracts import ContractError, Serializable, Target, aware, digest, exact_sum
from .models import ModelUnavailable, Series, eligibility, forecast
from .uncertainty import weighted_quantile


def _freeze(value):
    if isinstance(value, Mapping):
        if any(not isinstance(k, str) for k in value):
            raise ContractError('configuration keys must be strings')
        return MappingProxyType({k: _freeze(v) for k, v in value.items()})
    if isinstance(value, (tuple, list)):
        return tuple(_freeze(v) for v in value)
    if isinstance(value, Decimal) and not value.is_finite():
        raise ContractError('configuration must contain finite values')
    if value is None or isinstance(value, (str, bool, int, date, datetime, Decimal)):
        return value
    if isinstance(value, float) and math.isfinite(value):
        return value
    raise ContractError('configuration must contain finite serializable values')


def _typed_config(value):
    """Identity-only encoding; external Decimal/date wire values stay strings."""
    if isinstance(value, Mapping):
        return ('mapping', tuple((key, _typed_config(value[key])) for key in sorted(value)))
    if isinstance(value, tuple):
        return ('sequence', tuple(_typed_config(item) for item in value))
    if isinstance(value, datetime):
        return ('datetime', value.isoformat(), str(value.tzinfo), value.fold)
    if isinstance(value, date):
        return ('date', value.isoformat())
    if isinstance(value, Decimal):
        return ('decimal', str(value))
    # _freeze has already restricted values to the supported scalar types.
    return (type(value).__name__, value)


class DerivedNumericalUnavailable(ContractError):
    """Validated numerical inputs cannot produce a finite derived law."""


def _sum(values):
    values = tuple(values)
    if all(isinstance(v, Decimal) for v in values):
        result = exact_sum(values)
        if not result.is_finite():
            raise DerivedNumericalUnavailable('nonfinite derived total')
        return result
    try:
        result = math.fsum(values)
    except (ArithmeticError, ValueError) as exc:
        raise DerivedNumericalUnavailable('nonfinite derived total') from exc
    if not math.isfinite(result):
        raise DerivedNumericalUnavailable('nonfinite derived total')
    return result


def _strings(values, label):
    values = tuple(values)
    if any(not isinstance(v, str) or not v for v in values):
        raise ContractError(label + ' must be nonempty strings')
    return values


@dataclass(frozen=True)
class ProcedureSpec(Serializable):
    procedure_id: str
    version: str = '1'
    config: Mapping = field(default_factory=dict)

    def __post_init__(self):
        _strings((self.procedure_id, self.version), 'procedure identity')
        if not isinstance(self.config, Mapping):
            raise ContractError('configuration mapping required')
        object.__setattr__(self, 'config', _freeze(self.config))
        digest(self)

    @property
    def identity(self):
        return digest({'procedure_id': self.procedure_id, 'version': self.version,
                       'typed_config': _typed_config(self.config)})


@dataclass(frozen=True)
class ScenarioSpec(Serializable):
    scenario_id: str = 'baseline'
    kind: str = 'probability_law'
    assumptions: tuple = ()
    estimand: str = 'baseline'

    def __post_init__(self):
        _strings((self.scenario_id,), 'scenario identity')
        if self.kind not in {'probability_law', 'sensitivity'}:
            raise ContractError('unknown scenario law kind')
        if self.estimand not in {'baseline', 'frozen_usage_repricing', 'workload', 'stress'}:
            raise ContractError('unknown scenario estimand')
        object.__setattr__(self, 'assumptions', _strings(self.assumptions, 'assumptions'))


@dataclass(frozen=True)
class SeriesAxis(Serializable):
    entity_id: str
    meter: str
    configuration: str
    pool: str
    unit: str

    def __post_init__(self):
        _strings((self.entity_id, self.meter, self.configuration, self.pool, self.unit), 'axis dimensions')

    @property
    def axis_id(self):
        return digest(self)


@dataclass(frozen=True)
class OutputQualification(Serializable):
    output: str
    status: str
    reasons: tuple = ()
    evidence_scope: str = 'unassessed'
    evidence_ids: tuple = ()

    def __post_init__(self):
        _strings((self.output,), 'output')
        if self.status not in {'available_assumption_conditional', 'unavailable', 'empirically_qualified'}:
            raise ContractError('unknown qualification status')
        object.__setattr__(self, 'reasons', _strings(self.reasons, 'qualification reasons'))
        object.__setattr__(self, 'evidence_ids', _strings(self.evidence_ids, 'qualification evidence'))
        if self.evidence_scope not in {'unassessed', 'public_trace', 'enterprise'}:
            raise ContractError('unknown empirical evidence scope')
        if self.status == 'empirically_qualified' and (self.evidence_scope == 'unassessed' or not self.evidence_ids):
            raise ContractError('empirical qualification requires scoped evaluation evidence')


@dataclass(frozen=True)
class ScenarioBundle(Serializable):
    target: Target
    snapshot_id: str
    as_of: datetime
    dates: tuple
    axes: tuple
    path_ids: tuple
    values: tuple
    weights: tuple
    procedure: ProcedureSpec
    scenario: ScenarioSpec = ScenarioSpec()
    evidence_class: str = 'unspecified'
    parent_ids: tuple = ()
    support_transform: str = 'none'
    assumptions: tuple = ()
    qualifications: tuple = ()

    def __post_init__(self):
        if not isinstance(self.target, Target) or not isinstance(self.procedure, ProcedureSpec) or not isinstance(self.scenario, ScenarioSpec):
            raise ContractError('typed target, procedure and scenario required')
        _strings((self.snapshot_id, self.support_transform), 'snapshot and support transform')
        aware(self.as_of)
        for name in ('dates', 'axes', 'path_ids', 'weights', 'parent_ids', 'assumptions', 'qualifications'):
            object.__setattr__(self, name, tuple(getattr(self, name)))
        object.__setattr__(self, 'values', tuple(tuple(tuple(a) for a in p) for p in self.values))
        if self.evidence_class not in {'unspecified', 'synthetic_fixture', 'authorized_local_file', 'backend_verified_snapshot', 'public_trace', 'mixed'}:
            raise ContractError('unknown evidence class')
        if not self.dates or any(type(d) is not date for d in self.dates) or any(b-a != timedelta(days=1) for a,b in zip(self.dates, self.dates[1:])):
            raise ContractError('exact consecutive target dates required')
        local = self.as_of.astimezone(ZoneInfo(self.target.reporting_timezone))
        if local.timetz().replace(tzinfo=None) != time() or local.date() > self.dates[0]:
            raise ContractError('reporting-midnight origin must precede target dates')
        if not self.axes or any(not isinstance(a, SeriesAxis) for a in self.axes) or len(set(self.axes)) != len(self.axes):
            raise ContractError('unique typed axes required')
        if any(a.unit != self.target.unit for a in self.axes):
            raise ContractError('implicit cross-unit aggregation forbidden')
        _strings(self.path_ids, 'path IDs')
        _strings(self.parent_ids, 'parent IDs')
        _strings(self.assumptions, 'assumptions')
        if not self.path_ids or len(set(self.path_ids)) != len(self.path_ids):
            raise ContractError('unique nonempty path IDs required')
        if len(self.values) != len(self.path_ids) or any(len(p) != len(self.axes) or any(len(a) != len(self.dates) for a in p) for p in self.values):
            raise ContractError('rectangular path/axis/date shape required')
        money = self.target.measure != 'metered_usage'
        for p in self.values:
            for a in p:
                for v in a:
                    if money and not isinstance(v, Decimal):
                        raise ContractError('money paths require exact Decimal values')
                    if isinstance(v, bool) or not isinstance(v, (int, float, Decimal)):
                        raise ContractError('numeric path value required')
                    if not (v.is_finite() if isinstance(v, Decimal) else math.isfinite(v)):
                        raise ContractError('finite path value required')
                    if self.target.support == 'nonnegative' and v < 0:
                        raise ContractError('nonnegative target has negative paths')
        if self.scenario.kind == 'sensitivity':
            if self.weights:
                raise ContractError('sensitivity grid has no probability weights')
        elif len(self.weights) != len(self.path_ids) or any(isinstance(w, bool) or not isinstance(w, (int, float)) or not math.isfinite(w) or not 0 <= w <= 1 for w in self.weights) or not math.isclose(_sum(self.weights), 1., rel_tol=0., abs_tol=1e-12):
            raise ContractError('normalized finite probability weights required')
        if any(not isinstance(q, OutputQualification) for q in self.qualifications) or len({q.output for q in self.qualifications}) != len(self.qualifications):
            raise ContractError('unique typed output qualifications required')
        if self.evidence_class in {'mixed', 'unspecified', 'synthetic_fixture'} and any(q.status == 'empirically_qualified' for q in self.qualifications):
            raise ContractError('unqualified evidence cannot be empirically promoted')
        if self.evidence_class == 'public_trace' and any(q.status == 'empirically_qualified' and q.evidence_scope != 'public_trace' for q in self.qualifications):
            raise ContractError('public trace evidence cannot establish enterprise qualification')
        self.totals()  # Finite cells do not imply finite cumulative sums.

    @property
    def bundle_id(self):
        return digest({'bundle': self, 'procedure_identity': self.procedure.identity})

    def totals(self, entity_ids=None):
        if not self.target.additive:
            raise ContractError('target does not permit implicit additive totals')
        selected = tuple(dict.fromkeys(a.entity_id for a in self.axes)) if entity_ids is None else tuple(entity_ids)
        if not selected or len(set(selected)) != len(selected) or not set(selected).issubset(a.entity_id for a in self.axes):
            raise ContractError('unknown, empty or repeated entity selection')
        indices = tuple(i for i,a in enumerate(self.axes) if a.entity_id in selected)
        return tuple(_sum(v for i in indices for v in path[i]) for path in self.values)

    def quantile(self, q, entity_ids=None):
        if self.scenario.kind != 'probability_law':
            raise ContractError('sensitivity grid is not a probability law')
        if not isinstance(q, (int, float)) or not math.isfinite(q) or not 0 <= q <= 1:
            raise ContractError('quantile must be in [0,1]')
        return weighted_quantile(self.totals(entity_ids), self.weights, q)

    def aggregate_entities(self):
        entities = tuple(dict.fromkeys(a.entity_id for a in self.axes))
        indices = tuple(tuple(i for i,a in enumerate(self.axes) if a.entity_id == e) for e in entities)
        values = tuple(tuple(tuple(_sum(p[i][d] for i in group) for d in range(len(self.dates))) for group in indices) for p in self.values)
        axes = tuple(SeriesAxis(e, 'aggregate', 'aggregate', 'aggregate', self.target.unit) for e in entities)
        return replace(self, axes=axes, values=values, parent_ids=(self.bundle_id,),
                       procedure=ProcedureSpec('aggregate_entities', config={'parent_procedure': self.procedure.identity}))


    def aggregate_company(self, entity_id='company'):
        values = tuple((tuple(_sum(a[d] for a in p) for d in range(len(self.dates))),) for p in self.values)
        return replace(self, axes=(SeriesAxis(entity_id, 'aggregate', 'aggregate', 'aggregate', self.target.unit),),
                       values=values, parent_ids=(self.bundle_id,),
                       procedure=ProcedureSpec('aggregate_company', config={'parent_procedure': self.procedure.identity}))


@dataclass(frozen=True)
class JointUnavailable(Serializable):
    reason: str
    procedure: ProcedureSpec
    status: str = field(default='unavailable', init=False)


def fit_joint_blocks(series, *, target, snapshot_id, as_of, dates, axes,
                     n_paths=200, seed=0, baseline='trailing_mean', baseline_config=None,
                     min_blocks=3, allow_direct_fallback=True, evidence_class='unspecified',
                     scenario=ScenarioSpec(), history_end=None, max_history_lag_days=0):
    """Fit complete nonoverlapping rolling residual blocks shared across axes.

    Each historical prefix is forecast independently; neither its held-out block
    nor later observations enter that fit. One sampled block selects *every*
    axis and day in a path. Direct fallback samples observed complete blocks.
    """
    series, dates, axes = tuple(series), tuple(dates), tuple(axes)
    aware(as_of)
    if target.measure != 'metered_usage':
        raise ContractError('native usage generator cannot fit exact money from float Series')
    if not series:
        return JointUnavailable('cold start: no complete historical Series',
                                ProcedureSpec('joint_residual_blocks', config={
                                    'baseline': baseline, 'baseline_config': baseline_config or {},
                                    'seed': seed, 'n_paths': n_paths, 'min_blocks': min_blocks}))
    if len(series) != len(axes) or any(not isinstance(s, Series) for s in series):
        raise ContractError('one complete Series per axis required')
    if len(set(axes)) != len(axes) or any(a.unit != target.unit for a in axes):
        raise ContractError('unique compatible axes required')
    for s,a in zip(series, axes):
        if s.entity_id != a.axis_id and (s.entity_id != a.entity_id or sum(x.entity_id == a.entity_id for x in axes) != 1):
            raise ContractError('history identity must unambiguously match its axis')
    if any(s.dates != series[0].dates for s in series):
        raise ContractError('all historical axes must have identical dates')
    local = as_of.astimezone(ZoneInfo(target.reporting_timezone))
    if local.timetz().replace(tzinfo=None) != time():
        raise ContractError('reporting-midnight origin required')
    if type(max_history_lag_days) is not int or not 0 <= max_history_lag_days <= 30:
        raise ContractError('history lag policy must be between zero and thirty days')
    history_end = local.date() if history_end is None else history_end
    if type(history_end) is not date or not 0 <= (local.date()-history_end).days <= max_history_lag_days:
        raise ContractError('history end exceeds declared lag policy')
    if series[0].dates[-1] != history_end - timedelta(days=1):
        raise ContractError('history must end immediately before history_end; later observations forbidden')
    if not dates or any(type(d) is not date for d in dates) or dates[0] < local.date() or any(d != dates[0] + timedelta(days=i) for i,d in enumerate(dates)):
        raise ContractError('future target dates must be consecutive and no earlier than as-of')
    modeled_dates = tuple(history_end + timedelta(days=i) for i in range((dates[-1]-history_end).days+1))
    output_offset = (dates[0]-history_end).days
    if any(v < 0 for s in series for v in s.values):
        raise ContractError('native usage histories must be nonnegative')
    if type(n_paths) is not int or not 1 <= n_paths <= 10000 or type(seed) is not int or type(min_blocks) is not int or min_blocks < 2:
        raise ContractError('bounded positive path count, integer seed and at least two blocks required')
    if len(modeled_dates) > 366 or n_paths * len(axes) * len(modeled_dates) > 2000000:
        raise ContractError('joint generator exceeds resource budget')
    cfg = {} if baseline_config is None else dict(baseline_config)
    cfg['nonnegative'] = False  # Projection occurs once, after residual sampling.
    config = {'baseline': baseline, 'baseline_config': cfg, 'seed': seed,
              'n_paths': n_paths, 'min_blocks': min_blocks,
              'allow_direct_fallback': allow_direct_fallback,
              'history_digest': digest(series), 'history_start': series[0].dates[0],
              'history_end': history_end, 'horizon': len(modeled_dates),
              'modeled_dates': modeled_dates, 'output_dates': dates,
              'max_history_lag_days': max_history_lag_days}
    procedure = ProcedureSpec('joint_residual_blocks', config=config)
    horizon, n = len(modeled_dates), len(series[0].dates)
    blocks, starts = [], []
    eligibility_result = eligibility(series[0], baseline, cfg)
    predictions = None
    try:
        predictions = tuple(forecast(s, modeled_dates, baseline, cfg).daily_values for s in series)
        if any(p is None for p in predictions):
            return JointUnavailable('baseline has no daily path', procedure)
        required = max(eligibility(s, baseline, cfg).required_history for s in series)
        for start in range(required, n-horizon+1, horizon):
            block_dates = series[0].dates[start:start+horizon]
            block = []
            for s in series:
                prefix = Series(s.entity_id, s.dates[:start], s.values[:start])
                predicted = forecast(prefix, block_dates, baseline, cfg).daily_values
                if predicted is None:
                    raise ModelUnavailable('baseline has no daily path')
                residual = tuple(_sum((s.values[start+j], -predicted[j])) for j in range(horizon))
                block.append(residual)
            blocks.append(tuple(block))
            starts.append(start)
    except ModelUnavailable as exc:
        # Unsupported/invalid model choices are not silently reinterpreted.
        if eligibility_result.required_history == 0 or not str(exc).startswith('insufficient history'):
            return JointUnavailable(str(exc), procedure)
    direct = len(blocks) < min_blocks
    if direct:
        if not allow_direct_fallback:
            return JointUnavailable('insufficient complete historical residual blocks', procedure)
        starts = list(range(0, n-horizon+1, horizon))
        blocks = [tuple(s.values[start:start+horizon] for s in series) for start in starts]
        if len(blocks) < min_blocks:
            return JointUnavailable('insufficient complete historical blocks', procedure)
    rng = random.Random(seed)
    sampled = tuple(rng.randrange(len(blocks)) for _ in range(n_paths))
    paths, projection_count = [], 0
    for selected in sampled:
        path = []
        for i, residual in enumerate(blocks[selected]):
            values = []
            for j, value in enumerate(residual):
                value = value if direct else _sum((predictions[i][j], value))
                projection_count += int(value < 0)
                values.append(max(0., value))
            path.append(tuple(values[output_offset:output_offset+len(dates)]))
        paths.append(tuple(path))
    config.update(block_count=len(blocks), block_starts=tuple(series[0].dates[s] for s in starts),
                  sampled_block_indices=sampled, projection_count=projection_count)
    procedure = ProcedureSpec('joint_direct_blocks' if direct else 'joint_residual_blocks', config=config)
    assumptions = ('Historical blocks are exchangeable with the forecast horizon.',
                   'Finite empirical support does not establish calibrated future tail probabilities.',
                   'Snapshot must enforce source permission, completeness and observation availability as of origin.')
    qualification = OutputQualification('native_usage', 'available_assumption_conditional',
                                        ('Empirical block law; no enterprise calibration established.',))
    law_id = digest({'target': target, 'snapshot_id': snapshot_id, 'as_of': as_of,
                     'dates': dates, 'axes': axes, 'procedure_identity': procedure.identity,
                     'scenario': scenario, 'evidence_class': evidence_class})
    return ScenarioBundle(target, snapshot_id, as_of, dates, axes,
                          tuple(law_id + ':path-%d' % i for i in range(n_paths)), tuple(paths),
                          tuple(1./n_paths for _ in range(n_paths)) if scenario.kind == 'probability_law' else (),
                          procedure, scenario, evidence_class,
                          support_transform='none' if direct else 'clip_nonnegative',
                          assumptions=assumptions, qualifications=(qualification,))
