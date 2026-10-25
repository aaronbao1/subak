"""Exact-target calibration and explicitly supplied joint laws.

Split-conformal rank arithmetic is exact; coverage relies on exchangeability of
calibration and future scores for the fixed procedure. Time series do not imply
that assumption. No interval-to-event probability conversion is provided.
All target intervals are half-open [target_start, target_end) in UTC.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date, datetime, timezone
from fractions import Fraction
import math
from typing import Optional


class NumericalFailure(ValueError):
    """Finite inputs produced arithmetic outside the supported finite domain."""


def _checked(value):
    if not math.isfinite(value):
        raise NumericalFailure('numerical failure: nonfinite derived risk value')
    return value


def _finite_sum(values):
    try:
        return _checked(math.fsum(values))
    except OverflowError as exc:
        raise NumericalFailure('numerical failure: risk sum overflow') from exc


def _aware(value):
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError('timezone-aware timestamp required')


@dataclass(frozen=True)
class CalibrationPoint:
    example_id: str
    target_start: date
    target_end: date
    prediction: float
    actual: float
    mature_at: datetime
    procedure_id: str
    scope: str
    revision: int = 1
    available_at: Optional[datetime] = None
    status: str = 'mature'

    def __post_init__(self):
        _aware(self.mature_at)
        if self.available_at is not None:
            _aware(self.available_at)
            if self.available_at > self.mature_at:
                raise ValueError('maturity precedes availability')
        if self.target_end <= self.target_start or self.revision < 1:
            raise ValueError('invalid calibration period/revision')
        if not all(math.isfinite(x) for x in (self.prediction, self.actual)):
            raise ValueError('finite calibration values required')
        if self.mature_at.astimezone(timezone.utc).date() < self.target_end:
            raise ValueError('maturity must be at or after the exclusive target end')
        if self.status not in ('mature','pending','disputed'):
            raise ValueError('invalid calibration status')


@dataclass(frozen=True)
class CumulativeInterval:
    lower: Optional[float]
    upper: Optional[float]
    alpha: float
    n: int
    rank: int
    status: str
    horizon: int
    procedure_id: str
    scope: str
    capabilities: tuple = ('cumulative_interval',)
    event_probability: None = None
    assumptions: tuple = ('fixed procedure', 'exchangeable exact-target residuals',
                          'nonoverlapping mature calibration periods',
                          'time-series coverage is not established by construction')


def cumulative_interval(point, records, *, cutoff, horizon, procedure_id, scope, alpha=.05):
    """Symmetric split conformal of cumulative absolute errors, never daily widths.

    Revisions replace a score by identity, independent of delivery/retry order.
    Overlapping periods are rejected rather than counted as independent support.
    None bounds with insufficient_evidence represent the unbounded rank case.
    """
    _aware(cutoff)
    if not 0 < alpha < 1 or horizon < 1 or not math.isfinite(point):
        raise ValueError('invalid alpha, horizon or point')
    latest = {}
    versions = {}
    identities = {}
    for r in records:
        identity=(r.target_start,r.target_end,r.prediction,r.procedure_id,r.scope)
        if r.example_id in identities and identities[r.example_id]!=identity:
            raise ValueError('calibration revision changed target/prediction identity')
        identities[r.example_id]=identity
        key = (r.example_id, r.revision)
        if key in versions and versions[key] != r:
            raise ValueError('conflicting calibration revision')
        versions[key] = r
        if r.procedure_id != procedure_id or r.scope != scope:
            continue
        if (r.target_end-r.target_start).days != horizon:
            continue
        if (r.available_at or r.mature_at) > cutoff:
            continue
        if r.example_id not in latest or latest[r.example_id].revision < r.revision:
            latest[r.example_id] = r
    eligible = sorted((r for r in latest.values() if r.status == 'mature' and r.mature_at <= cutoff), key=lambda r:r.target_start)
    for a,b in zip(eligible,eligible[1:]):
        if b.target_start < a.target_end:
            raise ValueError('overlapping calibration target periods')
    n=len(eligible)
    rank = math.ceil((n+1)*(1-alpha))
    try:
        scores = sorted(abs(_checked(r.actual-r.prediction)) for r in eligible)
        if rank > n:
            return CumulativeInterval(None,None,alpha,n,rank,'insufficient_evidence',horizon,procedure_id,scope)
        q=scores[rank-1]
        lower,upper=_checked(point-q),_checked(point+q)
    except NumericalFailure:
        return CumulativeInterval(None,None,alpha,n,rank,'numerical_failure',horizon,procedure_id,scope,capabilities=())
    return CumulativeInterval(lower,upper,alpha,n,rank,'available_assumption_conditional',horizon,procedure_id,scope)


def weighted_quantile(values, weights, q):
    """Left-inverse quantile using exact, normalized decimal-rendered masses.

    Callers validate the finite numerical support of the comparable values.
    Values are returned unchanged, including Decimal support beyond float range.
    Weights need not total one: the rank threshold uses their exact total.
    Decimal rendering of probabilities avoids shifting an atom boundary through
    repeated binary additions (for example eight equal tenths at q=.8).
    """
    if len(values)!=len(weights) or not values:
        raise ValueError('nonempty aligned weighted quantile inputs required')
    masses=tuple(Fraction(int(w)) if isinstance(w,bool) else Fraction(str(w)) for w in weights)
    probability=Fraction(int(q)) if isinstance(q,bool) else Fraction(str(q))
    total=sum(masses)
    if not 0<=probability<=1 or total<=0 or any(w<0 for w in masses):
        raise ValueError('nonnegative positive-total weights and quantile in [0, 1] required')
    threshold=probability*total
    cumulative=Fraction(0)
    for value,mass in sorted((v,w) for v,w in zip(values,masses) if w>0):
        cumulative+=mass
        if cumulative>=threshold:
            return value
    raise NumericalFailure('numerical failure: weighted quantile rank not reached')


def empirical_quantile(values, weights, q):
    if not 0 <= q <= 1 or len(values) != len(weights) or not values:
        raise ValueError('invalid quantile inputs')
    if any(not math.isfinite(x) for x in values) or any(not math.isfinite(w) or w < 0 for w in weights) or not math.isclose(_finite_sum(weights),1.,abs_tol=1e-9):
        raise ValueError('finite values and probability weights summing to one required')
    return weighted_quantile(values,weights,q)


@dataclass(frozen=True)
class JointPaths:
    """User-supplied empirical/assumed joint law, not fitted enterprise risk.

    Shape is [path][entity][day]. Path identity is preserved when summing;
    same-index entities and dates must be jointly sampled by the producer.
    """
    path_ids: tuple
    entities: tuple
    values: tuple
    weights: tuple
    provenance: str = 'explicit_assumed_joint_law; unvalidated_for_enterprise'

    def __post_init__(self):
        object.__setattr__(self,'path_ids',tuple(self.path_ids))
        object.__setattr__(self,'entities',tuple(self.entities))
        object.__setattr__(self,'values',tuple(tuple(tuple(days) for days in path) for path in self.values))
        object.__setattr__(self,'weights',tuple(self.weights))
        if not self.path_ids or len(set(self.path_ids)) != len(self.path_ids) or len(set(self.entities)) != len(self.entities) or not self.entities:
            raise ValueError('unique nonempty path and entity IDs required')
        if len(self.values)!=len(self.path_ids) or len(self.weights)!=len(self.path_ids):
            raise ValueError('path shape mismatch')
        horizon = len(self.values[0][0]) if self.values[0] else 0
        if not horizon or any(len(p)!=len(self.entities) or any(len(e)!=horizon for e in p) for p in self.values):
            raise ValueError('rectangular paths required')
        empirical_quantile(tuple(x for p in self.values for e in p for x in e), tuple(1/(len(self.values)*len(self.entities)*horizon) for p in self.values for e in p for x in e),.5)
        empirical_quantile(self.totals(),self.weights,.5)

    def totals(self, entities=None):
        selected = self.entities if entities is None else tuple(entities)
        if not selected or not set(selected).issubset(self.entities) or len(set(selected))!=len(selected):
            raise ValueError('unknown or repeated entity')
        indices = tuple(self.entities.index(e) for e in selected)
        return tuple(_finite_sum(x for i in indices for x in p[i]) for p in self.values)

    def quantile(self, q, entities=None):
        return empirical_quantile(self.totals(entities), self.weights, q)

    def exceedance(self, threshold, entities=None):
        if not math.isfinite(threshold):
            raise ValueError('finite threshold required')
        return _finite_sum(w for total,w in zip(self.totals(entities),self.weights) if total>threshold)

    def expected_excess(self, threshold, entities=None):
        if not math.isfinite(threshold):
            raise ValueError('finite threshold required')
        return _finite_sum(_checked(w*_checked(total-threshold))
                           for total,w in zip(self.totals(entities),self.weights) if w>0 and total>threshold)

    def expected_shortfall(self, alpha, entities=None):
        """Mean of the worst ``1-alpha`` probability mass, alpha in [0, 1).

        Uses fractional mass at the threshold atom, not a conditional mean of
        only losses strictly above VaR. Signed target values remain signed.
        This describes the supplied law and makes no calibration claim.
        """
        if not math.isfinite(alpha) or not 0<=alpha<1:
            raise ValueError('finite expected shortfall alpha in [0, 1) required')
        tail=1-alpha
        remaining=tail
        terms=[]
        for total,weight in sorted(zip(self.totals(entities),self.weights),reverse=True):
            if weight<=0:
                continue
            mass=min(weight,remaining)
            # Normalize before multiplying: even a constant 1e308 law has
            # finite shortfall when alpha is close to one.
            terms.append(_checked((mass/tail)*total))
            remaining-=mass
            if remaining<=0:
                break
        return _finite_sum(terms)
