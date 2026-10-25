"""As-of execution evidence and a bounded, assumption-conditional recurrent law.

This is a pooled predictive process, not a model of latent demand or causal
adoption. Finite empirical/supplied supports give finite moments. Native token
marks belong to the start day; continuation is a separately supplied scenario.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime, time, timedelta, timezone
import math
import random
from typing import Optional

from .contracts import aware, digest, interval, primitive


def _finite(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError(name + ' must be finite and nonnegative')


def _unique(records, key, label):
    result = {}
    for record in records:
        identity = key(record)
        if identity in result and result[identity] != record:
            raise ValueError('conflicting ' + label + ' identity')
        result[identity] = record
    return result


@dataclass(frozen=True)
class ExposureSpell:
    spell_id: str
    person_id: str
    cohort: str
    start: date
    end: date
    known_at: datetime
    access: Optional[bool]
    observed: bool = True
    prior_use: Optional[bool] = None

    def __post_init__(self):
        interval(self.start, self.end)
        aware(self.known_at)
        if not all((self.spell_id, self.person_id, self.cohort)):
            raise ValueError('exposure identities required')
        if any(value is not None and type(value) is not bool for value in (self.access, self.prior_use)):
            raise ValueError('access and prior use require known boolean or unknown')
        if type(self.observed) is not bool:
            raise ValueError('observation status must be boolean')


@dataclass(frozen=True)
class ExecutionEvent:
    event_id: str
    root_id: str
    person_id: str
    occurred_at: datetime
    known_at: datetime
    kind: str
    logical_id: str = ''
    attempt_id: str = ''
    meter_id: str = ''
    tokens: float = 0.
    parent_attempt_id: str = ''
    relationship: str = 'root'
    meter_relationship: str = 'exclusive'
    leaf_meter_ids: tuple = ()
    qualifying: bool = True
    requested_configuration: str = ''
    served_configuration: str = ''
    billed_configuration: str = ''

    def __post_init__(self):
        aware(self.occurred_at)
        aware(self.known_at)
        object.__setattr__(self, 'leaf_meter_ids', tuple(self.leaf_meter_ids))
        _finite(self.tokens, 'tokens')
        if self.known_at < self.occurred_at:
            raise ValueError('execution cannot be known before occurrence')
        if not all((self.event_id, self.root_id, self.person_id)):
            raise ValueError('execution identities required')
        if self.kind not in ('root_start', 'root_end', 'attempt', 'meter', 'wrapper'):
            raise ValueError('unknown execution kind')
        if self.relationship not in ('root', 'child', 'retry', 'fallback', 'resume', 'shared'):
            raise ValueError('unknown lineage relationship')
        if self.kind == 'attempt' and (not self.attempt_id or not self.logical_id):
            raise ValueError('physical and logical attempt identities required')
        if self.kind == 'meter' and (not self.attempt_id or not self.meter_id):
            raise ValueError('physical meter identities required')
        if self.meter_relationship not in ('exclusive', 'subset'):
            raise ValueError('unknown meter relationship')
        if self.kind == 'meter' and self.meter_relationship != 'exclusive':
            raise ValueError('subset meter relationship requires wrapper with explicit leaves')
        if self.kind == 'wrapper' and (not self.leaf_meter_ids or len(set(self.leaf_meter_ids)) != len(self.leaf_meter_ids)):
            raise ValueError('wrapper requires unique authoritative meter leaves')


@dataclass(frozen=True)
class ExecutionReplay:
    exposures: tuple
    events: tuple
    starts: tuple
    ongoing_roots: tuple
    meters: tuple
    total_tokens: float
    evidence_id: str


def replay_execution(exposures, events, *, as_of):
    """Replay only available occurred records; later evidence cannot alter identity."""
    aware(as_of)
    spells = tuple(sorted(_unique((s for s in exposures if s.known_at <= as_of),
                                  lambda s: s.spell_id, 'exposure').values(),
                          key=lambda s: (s.person_id, s.start, s.spell_id)))
    for a, b in zip(spells, spells[1:]):
        if a.person_id == b.person_id and b.start < a.end:
            raise ValueError('overlapping person exposure spells')
    records = tuple(sorted(_unique((e for e in events if e.known_at <= as_of and e.occurred_at < as_of),
                                   lambda e: e.event_id, 'event').values(),
                           key=lambda e: (e.occurred_at, e.event_id)))
    starts = _unique((e for e in records if e.kind == 'root_start'), lambda e: e.root_id, 'root')
    ends = _unique((e for e in records if e.kind == 'root_end'), lambda e: e.root_id, 'root end')
    attempts = _unique((e for e in records if e.kind == 'attempt'), lambda e: e.attempt_id, 'attempt')
    for e in records:
        start = starts.get(e.root_id)
        if start is None or e.person_id != start.person_id or e.occurred_at < start.occurred_at:
            raise ValueError('execution root lineage is missing or conflicting')
        if e.kind == 'attempt' and e.relationship != 'root' and not e.parent_attempt_id:
            raise ValueError('attempt lineage requires parent')
        if e.kind in ('attempt', 'meter') and e.root_id in ends and e.occurred_at > ends[e.root_id].occurred_at:
            raise ValueError('execution after acknowledged root end')
    for attempt in attempts.values():
        seen = {attempt.attempt_id}
        current = attempt
        while current.parent_attempt_id:
            parent = attempts.get(current.parent_attempt_id)
            if (parent is None or parent.attempt_id in seen or parent.root_id != attempt.root_id
                    or parent.occurred_at > current.occurred_at):
                raise ValueError('invalid attempt lineage')
            seen.add(parent.attempt_id)
            current = parent
    meters = {}
    for e in records:
        if e.kind != 'meter':
            continue
        attempt = attempts.get(e.attempt_id)
        if (attempt is None or attempt.root_id != e.root_id or attempt.person_id != e.person_id
                or e.occurred_at < attempt.occurred_at or (e.logical_id and e.logical_id != attempt.logical_id)):
            raise ValueError('meter attempt lineage mismatch')
        # Delivery event IDs may differ; authoritative physical leaf identity may not.
        signature = (e.root_id, e.person_id, e.attempt_id, e.logical_id, e.occurred_at,
                     e.tokens, e.requested_configuration, e.served_configuration, e.billed_configuration)
        if e.meter_id in meters:
            prior, prior_signature = meters[e.meter_id]
            if prior_signature != signature:
                raise ValueError('conflicting meter identity')
        else:
            meters[e.meter_id] = (e, signature)
    for e in records:
        if e.kind == 'wrapper':
            if any(leaf not in meters or meters[leaf][0].root_id != e.root_id for leaf in e.leaf_meter_ids):
                raise ValueError('wrapper has unresolved meter leaves')
            leaf_total = math.fsum(meters[leaf][0].tokens for leaf in e.leaf_meter_ids)
            if not math.isclose(leaf_total, e.tokens, rel_tol=1e-12, abs_tol=1e-12):
                raise ValueError('wrapper does not reconcile to meter leaves')
    leaves = tuple(pair[0] for _, pair in sorted(meters.items()))
    try:
        total = math.fsum(e.tokens for e in leaves)
    except OverflowError as exc:
        raise ValueError('meter total overflow') from exc
    _finite(total, 'meter total')
    return ExecutionReplay(spells, records, tuple(starts.values()), tuple(sorted(set(starts)-set(ends))),
                           leaves, total, digest((as_of, spells, records)))


@dataclass(frozen=True)
class ExecutionMark:
    tokens: float
    requested_configuration: str = ''
    served_configuration: str = ''
    billed_configuration: str = ''
    qualifying: bool = True
    context_tokens: int = 0

    def __post_init__(self):
        _finite(self.tokens, 'mark tokens')
        if type(self.context_tokens) is not int or self.context_tokens < 0:
            raise ValueError('nonnegative context size required')
        if type(self.qualifying) is not bool:
            raise ValueError('qualifying marker must be boolean')


@dataclass(frozen=True)
class HurdleParameters:
    cohort: str
    p_any: float
    positive_counts: tuple = (1,)
    marks: tuple = (ExecutionMark(1.),)
    p_returning: Optional[float] = None
    fit_id: str = 'supplied-finite-law'
    parameter_source: str = 'supplied'
    fit_as_of: Optional[datetime] = None
    fit_evidence_id: str = ''

    def __post_init__(self):
        object.__setattr__(self, 'positive_counts', tuple(self.positive_counts))
        object.__setattr__(self, 'marks', tuple(self.marks))
        if not self.cohort or not self.fit_id:
            raise ValueError('cohort and parameter provenance required')
        if self.parameter_source == 'fitted':
            if self.fit_as_of is None or not self.fit_evidence_id:
                raise ValueError('fitted parameters require origin and evidence provenance')
            aware(self.fit_as_of)
        elif self.parameter_source == 'supplied':
            if self.fit_as_of is not None or self.fit_evidence_id or self.fit_id.startswith('fitted:'):
                raise ValueError('supplied parameters cannot relabel actual fitted provenance')
        else:
            raise ValueError('parameter source must be supplied or fitted')
        if self.p_any is None:
            raise ValueError('occurrence probability cannot be unknown')
        for p in (self.p_any, self.p_returning):
            if p is not None and (not math.isfinite(p) or not 0 <= p <= 1):
                raise ValueError('hurdle probability must be in [0,1]')
        if not self.positive_counts or any(type(n) is not int or not 1 <= n <= 10000 for n in self.positive_counts):
            raise ValueError('positive count support must be bounded integers in [1,10000]')
        if not self.marks or any(not isinstance(mark, ExecutionMark) for mark in self.marks):
            raise ValueError('nonempty finite mark support required')


@dataclass(frozen=True)
class CommonShock:
    occurrence_multiplier: float = 1.
    mark_multiplier: float = 1.

    def __post_init__(self):
        _finite(self.occurrence_multiplier, 'occurrence multiplier')
        _finite(self.mark_multiplier, 'mark multiplier')


@dataclass(frozen=True)
class ConsumedConfiguration:
    configuration_id: str
    known_at: datetime
    effective_start: date
    effective_end: date
    context_limit: int
    capability_support: Optional[tuple] = None
    accessible: bool = True

    def __post_init__(self):
        aware(self.known_at)
        interval(self.effective_start, self.effective_end)
        if not self.configuration_id or type(self.context_limit) is not int or self.context_limit < 0:
            raise ValueError('configuration identity and context limit required')
        if type(self.accessible) is not bool:
            raise ValueError('configuration access must be known')
        if self.capability_support is not None:
            object.__setattr__(self, 'capability_support', tuple(self.capability_support))
            if not self.capability_support:
                raise ValueError('empty capability support is unknown; use None')
            for value in self.capability_support:
                if not math.isfinite(value) or not 0 <= value <= 1:
                    raise ValueError('capability must be a supplied task-specific probability')


def fit_recurrent_hurdle(exposures, events, *, as_of, max_count=100):
    """Fit cohort occurrence, positive counts and start-day marks from full days.

    Unobserved or unknown/no-access days do not enter any denominator. Native
    start-day meters remain separate from future continuation. No latent-use
    labels, causal effects or unobserved opportunities are estimated.
    """
    replay = replay_execution(exposures, events, as_of=as_of)
    if type(max_count) is not int or not 1 <= max_count <= 10000:
        raise ValueError('bounded maximum count required')
    cohorts = {}
    for spell in replay.exposures:
        if not spell.observed or spell.access is not True:
            continue
        current = spell.start
        while current < min(spell.end, as_of.astimezone(timezone.utc).date()):
            roots = tuple(e for e in replay.starts if e.person_id == spell.person_id and
                          e.occurred_at.astimezone(timezone.utc).date() == current)
            counts, marks = cohorts.setdefault(spell.cohort, ([], []))
            counts.append(len(roots))
            if len(roots) > max_count:
                raise ValueError('observed count exceeds declared finite support; no silent clipping')
            for root in roots:
                leaves = tuple(e for e in replay.meters if e.root_id == root.root_id and
                               e.occurred_at.astimezone(timezone.utc).date() == current)
                if not leaves:
                    raise ValueError('positive roots need observed start-day meter marks')
                configurations = {(e.requested_configuration, e.served_configuration, e.billed_configuration) for e in leaves}
                if len(configurations) != 1:
                    raise ValueError('mixed-configuration root requires a joint mark adapter')
                requested, served, billed = next(iter(configurations))
                marks.append(ExecutionMark(math.fsum(e.tokens for e in leaves), requested, served, billed, root.qualifying))
            current += timedelta(days=1)
    if not cohorts:
        raise ValueError('no qualified observed exposure days for recurrent fit')
    result = []
    for cohort, (counts, marks) in sorted(cohorts.items()):
        positive = tuple(n for n in counts if n)
        result.append(HurdleParameters(cohort, len(positive)/len(counts), positive or (1,),
                                       tuple(marks) or (ExecutionMark(0.),), fit_id='fitted:' + digest((replay.evidence_id, cohort, max_count)),
                                       parameter_source='fitted', fit_as_of=as_of, fit_evidence_id=replay.evidence_id))
    return tuple(result)


@dataclass(frozen=True)
class EmittedRoot:
    root_id: str
    person_id: str
    day: date
    mark: ExecutionMark
    capability: Optional[float]


@dataclass(frozen=True)
class RecurrentPath:
    path_id: str
    roots: tuple
    first_trials: tuple
    first_observed_use: tuple
    ever_used: tuple
    last_use: tuple
    ongoing_roots: tuple
    capability_draws: tuple
    blocked_proposals: tuple


@dataclass(frozen=True)
class StateDiagnostics:
    mode: str
    unknown_capability_token_share: Optional[float]
    zero_exposure_path_share: float
    origin_ongoing_roots: tuple
    unknown_prior_use_people: tuple
    unknown_access_people: tuple
    assumptions: tuple


@dataclass(frozen=True)
class StateForecast:
    bundle: object
    paths: tuple
    diagnostics: StateDiagnostics


def generate_recurrent_scenarios(exposures, events, parameters, *, as_of, dates,
                                 path_count, seed, target, snapshot_id, catalog=(),
                                 shocks=(CommonShock(),), mode='delivered', admission=None,
                                 admission_id='', continuation_marks=(), evidence_class='unspecified',
                                 unknown_access=None):
    """Generate aligned paths; proposal admission is a pure per-path callback.

    For stateful admission pass a callable with ``for_path(path_id)`` returning
    a fresh callback; sharing capacity across Monte Carlo paths is invalid.
    Supplied capability probabilities are diagnostics, never token multipliers.
    """
    from .joint import OutputQualification, ProcedureSpec, ScenarioBundle, SeriesAxis

    replay = replay_execution(exposures, events, as_of=as_of)
    dates, parameters, shocks = tuple(dates), tuple(parameters), tuple(shocks)
    continuation_marks = tuple(continuation_marks)
    if mode not in ('delivered', 'proposal'):
        raise ValueError('execution mode must be delivered or proposal')
    if mode == 'proposal' and (admission is None or not admission_id):
        raise ValueError('proposal mode requires explicit admission policy and identity')
    if type(path_count) is not int or path_count < 1 or not dates or not shocks:
        raise ValueError('positive path count, dates and finite shocks required')
    if target.measure != 'metered_usage' or target.unit != 'tokens' or target.reporting_timezone != 'UTC':
        raise ValueError('recurrent kernel requires UTC native token target')
    if any(type(d) is not date for d in dates) or any(b-a != timedelta(days=1) for a,b in zip(dates,dates[1:])):
        raise ValueError('consecutive dates required')
    if datetime.combine(dates[0], time(), timezone.utc) != as_of:
        raise ValueError('recurrent target must begin at origin UTC midnight; bridge gaps explicitly')
    if replay.ongoing_roots and not continuation_marks:
        raise ValueError('ongoing roots require explicit continuation marks; zero future is not inferred')
    if unknown_access is not None and type(unknown_access) is not bool:
        raise ValueError('unknown access requires an explicit boolean scenario')
    parameter_map = _unique(parameters, lambda p: p.cohort, 'cohort parameters')
    if any(p.parameter_source == 'fitted' and p.fit_as_of > as_of for p in parameters):
        raise ValueError('fitted parameters were learned after the forecast origin')
    configs = _unique((c for c in catalog if c.known_at <= as_of), lambda c: c.configuration_id, 'configuration')
    all_marks = tuple(m for p in parameters for m in p.marks) + continuation_marks
    people = tuple(sorted({s.person_id for s in replay.exposures} | {e.person_id for e in replay.starts}))
    if not people or not parameters:
        raise ValueError('identified exposure population and parameters required')
    unknown_access_people = set()
    for d in dates:
        for spell in replay.exposures:
            if spell.start <= d < spell.end:
                if spell.cohort not in parameter_map:
                    raise ValueError('missing cohort parameters')
                if spell.access is None:
                    unknown_access_people.add(spell.person_id)
                    if unknown_access is None:
                        raise ValueError('unknown access needs an explicit conditional scenario')
    # Never silently resample infeasible routes; supplied start-day law must be feasible.
    def feasible(mark, d):
        if not mark.served_configuration:
            return
        c = configs.get(mark.served_configuration)
        if (c is None or not c.accessible or not c.effective_start <= d < c.effective_end
                or mark.context_tokens > c.context_limit):
            raise ValueError('supplied route is not feasible in origin-known catalog')
    for mark in all_marks:
        for d in dates:
            feasible(mark, d)
        for shock in shocks:
            _finite(mark.tokens * shock.mark_multiplier, 'derived mark')
    axes_keys = tuple(sorted({(person, m.billed_configuration or 'unknown') for person in people for m in all_marks}))
    axes = tuple(SeriesAxis(person, 'tokens', config, 'unassigned', 'tokens') for person,config in axes_keys)
    axis_index = {key:i for i,key in enumerate(axes_keys)}
    ever_initial, last_initial = {}, {}
    for person in people:
        past_spells = [s for s in replay.exposures if s.person_id == person and s.start <= dates[0]]
        known_priors = [s.prior_use for s in past_spells if s.prior_use is not None]
        prior = True if any(known_priors) else (False if known_priors else None)
        past_roots = [e for e in replay.starts if e.person_id == person and e.qualifying]
        ever_initial[person] = True if past_roots else prior
        last_initial[person] = max((e.occurred_at.astimezone(timezone.utc).date() for e in past_roots), default=None)
    assumptions = ('finite supplied/empirical support; no causal demand interpretation',
                   'cohort/day shock shared across people; occurrence=min(1,p*shock); conditional marks independently resampled',
                   'capability probability is supplied task-specific evidence, not a universal score',
                   'continuation marks are daily conditional scenarios, not learned workflow termination')
    config = {'evidence_id':replay.evidence_id, 'parameters':primitive(parameters),
              'catalog':primitive(tuple(configs.values())), 'shocks':primitive(shocks), 'mode':mode,
              'continuation_marks':primitive(continuation_marks), 'seed':seed, 'path_count':path_count,
              'admission_id':admission_id if mode == 'proposal' else '', 'unknown_access':unknown_access}
    procedure = ProcedureSpec('recurrent_finite_hurdle', config=config)
    rng = random.Random(seed)
    paths, values, unknown_shares = [], [], []
    for path_number in range(path_count):
        path_id = digest((procedure.identity, snapshot_id, dates, path_number))
        admit = admission.for_path(path_id) if mode == 'proposal' and hasattr(admission, 'for_path') else admission
        capabilities = {key:(rng.choice(c.capability_support) if c.capability_support is not None else None)
                        for key,c in sorted(configs.items())}
        ever, last = dict(ever_initial), dict(last_initial)
        roots, trials, first_observed, denied = [], [], [], []
        matrix = [[0. for _ in dates] for _ in axes]
        unknown_tokens = 0.
        for day_number, d in enumerate(dates):
            day_shocks = {cohort:rng.choice(shocks) for cohort in sorted(parameter_map)}
            for spell in replay.exposures:
                if not spell.start <= d < spell.end:
                    continue
                if d == spell.start and ever[spell.person_id] is not True and spell.prior_use is not None:
                    ever[spell.person_id] = spell.prior_use
                if not (spell.access if spell.access is not None else unknown_access):
                    continue
                par, shock = parameter_map[spell.cohort], day_shocks[spell.cohort]
                p = par.p_returning if ever[spell.person_id] is True and par.p_returning is not None else par.p_any
                if rng.random() >= min(1.,p*shock.occurrence_multiplier):
                    continue
                count = rng.choice(par.positive_counts)
                for ordinal in range(count):
                    mark = rng.choice(par.marks)
                    mark = replace(mark, tokens=mark.tokens*shock.mark_multiplier)
                    root_id = digest((path_id,d,spell.person_id,ordinal))
                    if mode == 'proposal' and not admit(root_id,datetime.combine(d,time(),timezone.utc),mark,spell.person_id):
                        denied.append(root_id)
                        continue
                    capability = capabilities.get(mark.served_configuration)
                    roots.append(EmittedRoot(root_id,spell.person_id,d,mark,capability))
                    index = axis_index[(spell.person_id,mark.billed_configuration or 'unknown')]
                    matrix[index][day_number] += mark.tokens
                    if capability is None:
                        unknown_tokens += mark.tokens
                    if mark.qualifying:
                        if ever[spell.person_id] is False:
                            trials.append((spell.person_id,d))
                        elif ever[spell.person_id] is None:
                            first_observed.append((spell.person_id,d))
                        ever[spell.person_id], last[spell.person_id] = True,d
            for root_id in replay.ongoing_roots:
                if not continuation_marks:
                    continue
                start = next(e for e in replay.starts if e.root_id == root_id)
                mark = rng.choice(continuation_marks)
                index = axis_index[(start.person_id,mark.billed_configuration or 'unknown')]
                matrix[index][day_number] += mark.tokens
                if capabilities.get(mark.served_configuration) is None:
                    unknown_tokens += mark.tokens
        total = sum(sum(row) for row in matrix)
        _finite(total, 'path total')
        unknown_shares.append(unknown_tokens/total if total else None)
        paths.append(RecurrentPath(path_id,tuple(roots),tuple(trials),tuple(first_observed),
                                   tuple(sorted(ever.items())),tuple(sorted(last.items())),replay.ongoing_roots,
                                   tuple(sorted(capabilities.items())),tuple(denied)))
        values.append(tuple(tuple(row) for row in matrix))
    bundle = ScenarioBundle(target=target,snapshot_id=snapshot_id,as_of=as_of,dates=dates,axes=axes,
                            path_ids=tuple(p.path_id for p in paths),values=tuple(values),
                            weights=tuple(1/path_count for _ in paths),procedure=procedure,
                            evidence_class=evidence_class,parent_ids=(replay.evidence_id,digest(tuple(paths))),
                            assumptions=assumptions,qualifications=(OutputQualification('execution',
                                'available_assumption_conditional',('finite structural law; not empirically calibrated',)),))
    positive_shares = [share for share in unknown_shares if share is not None]
    diagnostics = StateDiagnostics(mode,sum(positive_shares)/len(positive_shares) if positive_shares else None,
                                   sum(share is None for share in unknown_shares)/path_count,
                                   replay.ongoing_roots,tuple(p for p in people if ever_initial[p] is None),
                                   tuple(sorted(unknown_access_people)),assumptions)
    return StateForecast(bundle,tuple(paths),diagnostics)
