"""Small, explicit numerical registry for complete, daily, as-of histories.

This boundary accepts already authorized/as-of snapshots. It cannot recover
coverage or label availability from floats: callers must enforce those gates.
Direct horizon squared-error regression estimates original-scale conditional
means; no nonlinear recursive point path is relabeled as a mean.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from importlib import metadata as package_metadata
from math import fsum as _math_fsum, isfinite, sqrt
from types import MappingProxyType
from typing import Any, Mapping, Optional, Sequence, Tuple


class ModelUnavailable(ValueError):
    """A candidate cannot produce a valid forecast for this request."""
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


def fsum(values):
    try:
        return _math_fsum(values)
    except (ValueError, ArithmeticError) as exc:
        raise ModelUnavailable('numerical sum failed: ' + str(exc)) from exc


@dataclass(frozen=True)
class Series:
    entity_id: str
    dates: Tuple[date, ...]
    values: Tuple[float, ...]

    def __post_init__(self):
        if not isinstance(self.entity_id, str) or not self.entity_id:
            raise ValueError('entity_id must be nonempty')
        dates = tuple(self.dates)
        try:
            values = tuple(float(v) for v in self.values)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError('values must be finite numbers; missing is not zero') from exc
        if not dates or len(dates) != len(values):
            raise ValueError('nonempty aligned dates and values required')
        if any(type(d) is not date for d in dates):
            raise ValueError('dates must be date-only financial calendar dates')
        if any(b - a != timedelta(days=1) for a,b in zip(dates, dates[1:])):
            raise ValueError('daily history must be consecutive; gaps are not zeros')
        if not all(isfinite(v) for v in values):
            raise ValueError('history must be finite; missing is not zero')
        object.__setattr__(self, 'dates', dates)
        object.__setattr__(self, 'values', values)


@dataclass(frozen=True)
class ModelSpec:
    name: str
    min_history: int
    scope: str = 'local'
    dependencies: Tuple[str, ...] = ()
    supported: bool = True
    unavailable_reason: Optional[str] = None
    statistic: str = 'mean'
    horizon_strategy: str = 'daily_path'
    target_types: Tuple[str, ...] = ('additive_signed', 'additive_nonnegative')
    covariates: Tuple[str, ...] = ('calendar',)
    max_horizon: int = 366
    license: str = 'project code'


@dataclass(frozen=True)
class Eligibility:
    eligible: bool
    required_history: int
    reasons: Tuple[str, ...] = ()


@dataclass(frozen=True)
class Prediction:
    model_name: str
    dates: Tuple[date, ...]
    daily_values: Optional[Tuple[float, ...]]
    cumulative_value: float
    statistic: str
    coherence: str
    limitations: Tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.statistic not in ('mean', 'point'):
            raise ValueError('prediction statistic must identify mean or point')
        if not isfinite(self.cumulative_value):
            raise ModelUnavailable('nonfinite cumulative prediction')
        if self.daily_values is not None:
            if len(self.daily_values) != len(self.dates) or not all(isfinite(v) for v in self.daily_values):
                raise ModelUnavailable('daily prediction is not finite/aligned')
            if self.coherence != 'daily_sum':
                raise ValueError('daily prediction must declare daily_sum coherence')
            if abs(fsum(self.daily_values) - self.cumulative_value) > 1e-9 * max(1., abs(self.cumulative_value)):
                raise ValueError('cumulative prediction does not sum daily path')
        elif self.coherence != 'direct_cumulative_only':
            raise ValueError('direct cumulative prediction has no daily allocation')
        object.__setattr__(self, 'metadata', MappingProxyType(dict(self.metadata)))


_NUMERIC = ('numpy==1.26.4', 'scikit-learn==1.6.1')
MODEL_REGISTRY = MappingProxyType({s.name:s for s in (
    ModelSpec('last_observation', 1),
    ModelSpec('trailing_mean', 7),
    ModelSpec('weekday_mean', 14),
    ModelSpec('seasonal_naive', 7),
    ModelSpec('exponential_smoothing', 2),
    ModelSpec('local_linear_trend', 3),
    ModelSpec('calendar_regression', 14, dependencies=_NUMERIC, license='NumPy BSD-3-Clause; scikit-learn BSD-3-Clause'),
    ModelSpec('pooled_ridge', 35, 'pooled', _NUMERIC, horizon_strategy='direct', max_horizon=90, license='NumPy BSD-3-Clause; scikit-learn BSD-3-Clause'),
    ModelSpec('tabular_mean', 42, 'pooled', _NUMERIC, horizon_strategy='direct', max_horizon=90, license='NumPy BSD-3-Clause; scikit-learn BSD-3-Clause'),
    ModelSpec('tabular_direct_cumulative', 42, 'pooled', _NUMERIC, horizon_strategy='direct_cumulative', max_horizon=90, license='NumPy BSD-3-Clause; scikit-learn BSD-3-Clause'),
    *(ModelSpec(name, 1, supported=False, unavailable_reason=reason) for name,reason in (
        ('neural', 'no pinned trained neural artifact, tested covariate interface, or empirical qualification'),
        ('foundation', 'no pinned checkpoint/runtime, weight license, supported output statistic, or access qualification'),
        ('session', 'no censor-aware session observation and continuation adapter'),
        ('llm', 'text-only numerical forecasts are unsupported; use source-backed context scenarios'),
        ('lognormal', 'no qualified original-scale mean derivation or observation distribution'),
        ('croston', 'intermittent likelihood and coverage mask adapter not implemented'),
        ('tsb', 'verified exposure and missing-mask occurrence state adapter not implemented'),
        ('compound_arrival_severity', 'joint arrival/severity dependence and censoring adapter not implemented'),
        ('multivariate_var', 'stable attribution and rank-qualified multivariate panel adapter not implemented'),
        ('gaussian_process', 'kernel fitting and observation-noise predictive distribution adapter not implemented'),
        ('reconciliation_mint', 'aligned residual covariance and constrained reconciliation adapter not implemented'),
        ('online_change_detector', 'delayed-label updates and fleet false-alarm qualification not implemented'),
        ('quantile_sum', 'marginal quantiles cannot be summed into a calibrated cumulative quantile'),
    )),
)})

_DEFAULTS = {
    'last_observation': {},
    'trailing_mean': {'window':7},
    'weekday_mean': {'window':28},
    'seasonal_naive': {'season_length':7},
    'exponential_smoothing': {'alpha':.3},
    'local_linear_trend': {'alpha':.3, 'beta':.1, 'damping':.95},
    'calendar_regression': {'ridge_alpha':1.},
    'pooled_ridge': {'ridge_alpha':1., 'lags':7, 'min_training_rows':20},
    'tabular_mean': {'lags':7, 'min_training_rows':28, 'n_estimators':80, 'max_depth':2, 'learning_rate':.08, 'seed':0},
    'tabular_direct_cumulative': {'lags':7, 'min_training_rows':28, 'n_estimators':80, 'max_depth':2, 'learning_rate':.08, 'seed':0},
}


def _dependency_versions():
    versions = {}
    for name in ('numpy', 'scikit-learn'):
        try:
            versions[name] = package_metadata.version(name)
        except package_metadata.PackageNotFoundError:
            pass
    return versions


def _config(name, config):
    config = {} if config is None else dict(config)
    defaults = dict(_DEFAULTS.get(name, {}), nonnegative=False)
    unknown = set(config) - set(defaults)
    if unknown:
        raise ModelUnavailable('unsupported config fields: ' + ', '.join(sorted(unknown)))
    defaults.update(config)
    for key,value in defaults.items():
        if key == 'nonnegative':
            if type(value) is not bool:
                raise ModelUnavailable('nonnegative config must be bool')
        elif key in ('window','season_length','lags','min_training_rows','n_estimators','max_depth','seed'):
            if type(value) is not int or value < (0 if key == 'seed' else 1):
                raise ModelUnavailable(key + ' config must be a positive integer')
        elif not isinstance(value, (float,int)) or isinstance(value,bool) or not isfinite(value) or value <= 0:
            raise ModelUnavailable(key + ' config must be finite and positive')
    for key in ('alpha', 'beta', 'damping', 'learning_rate'):
        if defaults.get(key, 1) > 1:
            raise ModelUnavailable(key + ' config must be at most 1')
    if name == 'weekday_mean' and defaults['window'] < 7:
        raise ModelUnavailable('weekday window requires at least seven complete days')
    if defaults.get('n_estimators',1) > 500 or defaults.get('max_depth',1) > 6 or defaults.get('lags',1) > 56:
        raise ModelUnavailable('config exceeds bounded model resource budget')
    return defaults


def eligibility(series: Series, model_name: str, config=None) -> Eligibility:
    spec = MODEL_REGISTRY.get(model_name)
    if spec is None:
        return Eligibility(False, 0, ('unknown model: ' + str(model_name),))
    if not spec.supported:
        return Eligibility(False, spec.min_history, (spec.unavailable_reason,))
    try:
        cfg = _config(model_name, config)
    except ModelUnavailable as exc:
        return Eligibility(False, spec.min_history, (str(exc),))
    required = spec.min_history
    if model_name in ('trailing_mean', 'weekday_mean'):
        required = cfg['window']
        if model_name == 'weekday_mean':
            required = max(7, required)
    if model_name == 'seasonal_naive':
        required = cfg['season_length']
    reasons = []
    if len(series.values) < required:
        reasons.append('insufficient history: requires %d complete consecutive days' % required)
    if cfg['nonnegative'] and any(v < 0 for v in series.values):
        reasons.append('nonnegative target has signed history; do not clip refunds')
    installed = _dependency_versions() if spec.dependencies else {}
    for pinned in spec.dependencies:
        name,version = pinned.split('==')
        if installed.get(name) != version:
            reasons.append('dependency requires %s (installed %s)' % (pinned, installed.get(name,'unavailable')))
    return Eligibility(not reasons, required, tuple(reasons))


def _validate_dates(series, dates, max_horizon):
    dates = tuple(dates)
    if len(dates) > max_horizon:
        raise ModelUnavailable('horizon exceeds declared resource budget')
    for i,d in enumerate(dates):
        if type(d) is not date or d != series.dates[-1] + timedelta(days=i+1):
            raise ModelUnavailable('future dates must be consecutive calendar days immediately after origin')
    return dates


def _finish(name, dates, daily, total, cfg, metadata, limitations):
    projection_count = 0
    if cfg['nonnegative']:
        if daily is not None:
            projection_count = sum(v < 0 for v in daily)
            daily = tuple(max(0., v) for v in daily)
            total = fsum(daily)
        elif total < 0:
            projection_count = 1
            total = 0.
    statistic = 'point' if projection_count else 'mean'
    if projection_count:
        limitations.append('Nonnegative projection changed a fitted mean; projected values are point forecasts, not identified conditional means.')
    metadata = dict(metadata, projection_count=projection_count, config=dict(cfg))
    return Prediction(name, dates, daily, float(total), statistic,
                      'daily_sum' if daily is not None else 'direct_cumulative_only',
                      tuple(limitations), metadata)


def _calendar_features(dates, start, scale):
    return [[(d-start).days/scale] + [float(d.weekday()==k) for k in range(6)] for d in dates]


def _panel(series, panel, cfg):
    records = {}
    for item in tuple(panel or ()):
        if item.entity_id in records:
            raise ModelUnavailable('duplicate panel entity_id')
        if item.dates[-1] > series.dates[-1]:
            raise ModelUnavailable('future panel observations exceed origin')
        if cfg['nonnegative'] and any(v < 0 for v in item.values):
            raise ModelUnavailable('nonnegative panel target has signed history')
        records[item.entity_id] = item
    if series.entity_id in records and records[series.entity_id] != series:
        raise ModelUnavailable('target entity panel history differs from supplied series')
    records[series.entity_id] = series
    return tuple(records[k] for k in sorted(records))


def _features(item, end, h, scale, lags):
    """Only information at/before end plus deterministic target calendar."""
    observed = item.values[max(0,end-27):end+1]
    recent = observed[-7:]
    mu = fsum(recent)/len(recent)
    variance = fsum((v-mu)**2 for v in recent)/len(recent)
    d = item.dates[end] + timedelta(days=h)
    return ([v/scale for v in item.values[end-lags+1:end+1]] +
            [mu/scale, fsum(observed)/len(observed)/scale, sqrt(variance)/scale,
             (recent[-1]-recent[0])/max(1,len(recent)-1)/scale,
             float(h)] + [float(d.weekday()==k) for k in range(7)])


def _learned(series, dates, name, cfg, panel):
    try:
        import numpy as np
        from sklearn.linear_model import Ridge
        from sklearn.ensemble import GradientBoostingRegressor
    except (ImportError, OSError) as exc:
        raise ModelUnavailable('dependency import failed: ' + str(exc)) from exc
    metadata = {'dependency_versions': _dependency_versions()}
    limitations = ['Model mean is conditional on fitted parameters and historical regime; no uncertainty capability is implied.']
    if name == 'calendar_regression':
        x = np.array(_calendar_features(series.dates, series.dates[0], len(series.values)))
        future_x = np.array(_calendar_features(dates, series.dates[0], len(series.values)))
        fit = Ridge(alpha=cfg['ridge_alpha']).fit(x, series.values)
        daily = tuple(float(v) for v in fit.predict(future_x))
        metadata.update(training_rows=len(x), regularization=cfg['ridge_alpha'],
                        design_rank=int(np.linalg.matrix_rank(x)), horizon_strategy='calendar_direct',
                        training_entities=(series.entity_id,))
        return daily, fsum(daily), metadata, limitations
    items = _panel(series, panel, cfg)
    scales = {s.entity_id:max(fsum(abs(v) for v in s.values)/len(s.values), 1e-12) for s in items}
    horizons = (len(dates),) if name == 'tabular_direct_cumulative' else range(1, len(dates)+1)
    predictions = []
    row_counts = []
    lags = cfg['lags']
    for h in horizons:
        x,y = [],[]
        for item in items:
            scale = scales[item.entity_id]
            for end in range(lags-1, len(item.values)-h):
                x.append(_features(item, end, h, scale, lags))
                target = fsum(item.values[end+1:end+h+1]) if name == 'tabular_direct_cumulative' else item.values[end+h]
                y.append(target/scale)
        if len(y) < cfg['min_training_rows']:
            raise ModelUnavailable('insufficient mature training rows for horizon %d: %d < %d' % (h,len(y),cfg['min_training_rows']))
        if name == 'pooled_ridge':
            estimator = Ridge(alpha=cfg['ridge_alpha'])
        else:
            estimator = GradientBoostingRegressor(loss='squared_error', n_estimators=cfg['n_estimators'],
                max_depth=cfg['max_depth'], learning_rate=cfg['learning_rate'], random_state=cfg['seed'])
        estimator.fit(np.asarray(x), np.asarray(y))
        test_x = [_features(series,len(series.values)-1,h,scales[series.entity_id],lags)]
        predictions.append(float(estimator.predict(test_x)[0])*scales[series.entity_id])
        row_counts.append(len(y))
    metadata.update(training_rows=min(row_counts), training_rows_by_horizon=tuple(row_counts),
                    training_entities=tuple(s.entity_id for s in items),
                    horizon_strategy='direct_cumulative' if name == 'tabular_direct_cumulative' else 'direct',
                    objective='squared_error', normalization='per_entity_mean_absolute_history',
                    regularization=cfg.get('ridge_alpha'), seed=cfg.get('seed'))
    if name == 'tabular_direct_cumulative':
        limitations.append('Direct cumulative output has no daily allocation or guaranteed nested-period coherence; compare each period separately.')
        return None,predictions[0],metadata,limitations
    return tuple(predictions),fsum(predictions),metadata,limitations


def forecast(series: Series, future_dates: Sequence[date], model_name: str,
             config: Optional[Mapping[str, Any]]=None,
             panel: Optional[Sequence[Series]]=None) -> Prediction:
    """Forecast exact contiguous calendar dates using complete as-of history.

    `panel` is an explicit authorized, semantically comparable learning group.
    It is ignored by local models. No hidden inference batch changes groups.
    All model/history minima are engineering defaults, not empirical guarantees.
    """
    gate = eligibility(series, model_name, config)
    if not gate.eligible:
        raise ModelUnavailable('; '.join(gate.reasons))
    spec = MODEL_REGISTRY[model_name]
    cfg = _config(model_name, config)
    dates = _validate_dates(series, future_dates, spec.max_horizon)
    metadata = {'required_history':gate.required_history, 'horizon_strategy':spec.horizon_strategy,
                'training_entities':(series.entity_id,), 'origin':series.dates[-1].isoformat()}
    limitations = ['As-of coverage and target comparability must be established by the snapshot caller.',
                   'Conditional mean under the declared continuation model; accuracy and uncertainty are not empirically qualified.']
    if not dates:
        return _finish(model_name, dates, () if spec.horizon_strategy != 'direct_cumulative' else None,
                       0.,cfg,metadata,limitations)
    values = series.values
    if model_name == 'last_observation':
        daily = (values[-1],)*len(dates)
    elif model_name == 'trailing_mean':
        daily = (fsum(values[-cfg['window']:])/cfg['window'],)*len(dates)
    elif model_name == 'weekday_mean':
        grouped = {k:[] for k in range(7)}
        for d,v in zip(series.dates[-cfg['window']:],values[-cfg['window']:]):
            grouped[d.weekday()].append(v)
        daily = tuple(fsum(grouped[d.weekday()])/len(grouped[d.weekday()]) for d in dates)
    elif model_name == 'seasonal_naive':
        season = values[-cfg['season_length']:]
        daily = tuple(season[i % len(season)] for i in range(len(dates)))
    elif model_name == 'exponential_smoothing':
        level = values[0]
        for v in values[1:]:
            level = cfg['alpha']*v+(1-cfg['alpha'])*level
        metadata['state_level'] = level
        daily = (level,)*len(dates)
    elif model_name == 'local_linear_trend':
        level,slope = values[0],values[1]-values[0]
        alpha,beta,phi = cfg['alpha'],cfg['beta'],cfg['damping']
        for v in values[1:]:
            old = level
            level = alpha*v+(1-alpha)*(level+phi*slope)
            slope = beta*(level-old)+(1-beta)*phi*slope
        daily = tuple(level+slope*fsum(phi**j for j in range(1,h+1)) for h in range(1,len(dates)+1))
        metadata.update(state_level=level,state_slope=slope)
    else:
        try:
            daily,total,learned_meta,learned_limits = _learned(series,dates,model_name,cfg,panel)
            metadata.update(learned_meta)
            limitations.extend(learned_limits)
            return _finish(model_name,dates,daily,total,cfg,metadata,limitations)
        except ModelUnavailable:
            raise
        except (ValueError, ArithmeticError, RuntimeError) as exc:
            raise ModelUnavailable('numerical fit failed: ' + str(exc)) from exc
    return _finish(model_name,dates,daily,fsum(daily),cfg,metadata,limitations)
