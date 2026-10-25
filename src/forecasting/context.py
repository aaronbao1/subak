"""Source-backed semantic evidence. Text is data, never numerical or tool authority.

The ledger is a reference extraction handoff, not a semantic extractor or a live
Factory integration. Callers provide canonical event identities and verified
supersession links. Current access applies even to historical queries. Character
ranges are Python Unicode code-point offsets, half-open, in an immutable version.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime, time
import hashlib
from itertools import combinations
from zoneinfo import ZoneInfo
from decimal import Decimal
from typing import Iterable, Optional, Tuple

from .contracts import Target, digest, exact_product


def _aware(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError('timestamp must be timezone-aware')


def _decimal(value: Decimal, name: str) -> None:
    if not isinstance(value, Decimal) or not value.is_finite() or value < 0:
        raise ValueError(name + ' must be a finite nonnegative Decimal')


@dataclass(frozen=True)
class SourceDocument:
    tenant: str
    document_id: str
    version: str
    text: str
    available_at: datetime

    def __post_init__(self):
        _aware(self.available_at)
        if not all((self.tenant, self.document_id, self.version)):
            raise ValueError('source identity required')


@dataclass(frozen=True)
class Citation:
    document_id: str
    version: str
    start: int
    end: int
    passage: str

    def __post_init__(self):
        if self.start < 0 or self.end <= self.start or not self.passage:
            raise ValueError('nonempty half-open passage required')


@dataclass(frozen=True)
class ContextEvent:
    tenant: str
    event_id: str
    canonical_id: str
    subject: str
    field: str
    value: str
    status: str
    available_at: datetime
    citations: Tuple[Citation, ...]
    supersedes: Tuple[str, ...] = ()
    approval_verified: bool = False
    processed_at: Optional[datetime] = None
    effective_start: Optional[date] = None
    effective_end: Optional[date] = None
    date_precision: str = 'unspecified'
    calendar_version: Optional[str] = None
    execution_status: str = 'unknown'
    extraction_confidence: Optional[Decimal] = None
    schema_version: str = '1.0'
    ingested_at: Optional[datetime] = None
    reviewed_at: Optional[datetime] = None
    publication_at: Optional[datetime] = None

    @property
    def known_at(self):
        return max(t for t in (self.available_at,self.processed_at,self.ingested_at,self.reviewed_at) if t is not None)

    def __post_init__(self):
        _aware(self.available_at)
        for stamp in (self.ingested_at,self.reviewed_at,self.publication_at):
            if stamp is not None:
                _aware(stamp)
        if self.processed_at is not None:
            _aware(self.processed_at)
            if self.processed_at < self.available_at:
                raise ValueError('processing precedes availability')
        if self.schema_version != '1.0' or self.status not in ('approved','informal','cancelled','observed'):
            raise ValueError('unsupported context schema or status')
        if self.execution_status not in ('unknown','planned','observed','cancelled'):
            raise ValueError('invalid execution status')
        if not all((self.tenant,self.event_id,self.canonical_id,self.subject,self.field,self.value,self.citations)):
            raise ValueError('context identity, value and citations required')
        if not isinstance(self.citations, tuple) or not isinstance(self.supersedes, tuple):
            raise ValueError('immutable citation and supersession tuples required')
        if self.effective_start and self.effective_end and self.effective_start >= self.effective_end:
            raise ValueError('effective interval must be half-open and nonempty')
        if self.extraction_confidence is not None:
            _decimal(self.extraction_confidence, 'extraction confidence')
            if self.extraction_confidence > 1:
                raise ValueError('extraction confidence must be at most one')


@dataclass(frozen=True)
class ContextResolution:
    events: Tuple[ContextEvent, ...]
    conflicts: Tuple[Tuple[str, ...], ...]
    superseded: Tuple[str, ...]
    restricted_event_count: int
    mode: str = 'explanation_only'
    limitations: Tuple[str, ...] = ('Approval does not establish execution probability; context has no automatic numerical effect.',)


def _duplicate_signature(event: ContextEvent):
    """The same assertion may be forwarded; period and state remain material."""
    return (event.canonical_id,event.subject,event.field,event.value,event.status,
            event.effective_start,event.effective_end,event.approval_verified,event.execution_status)


def _effective_ranges_overlap(left: ContextEvent, right: ContextEvent) -> bool:
    """Unknown endpoints are unbounded; known half-open endpoints can prove disjointness."""
    if left.effective_end is not None and right.effective_start is not None:
        if left.effective_end <= right.effective_start:
            return False
    if right.effective_end is not None and left.effective_start is not None:
        if right.effective_end <= left.effective_start:
            return False
    return True


def _assertion_state(event: ContextEvent) -> str:
    if event.status == 'cancelled' or event.execution_status == 'cancelled':
        return 'cancelled'
    if event.status in ('approved','observed') or event.execution_status in ('planned','observed'):
        return 'active'
    return 'unknown'


def _assertions_conflict(left: ContextEvent, right: ContextEvent) -> bool:
    return (left.value != right.value or
            {_assertion_state(left),_assertion_state(right)} == {'active','cancelled'})


class ContextLedger:
    """Append-only source/claim versions with explicitly mutable current ACLs."""
    def __init__(self):
        self._sources = {}
        self._access = {}
        self._events = {}

    def add_source(self, source: SourceDocument, principals: Iterable[str]) -> None:
        key = (source.tenant, source.document_id, source.version)
        if key in self._sources and self._sources[key] != source:
            raise ValueError('source version is immutable')
        if key not in self._sources:
            self._sources[key] = source
            self._access[key] = frozenset(principals)

    def set_access(self, tenant: str, document_id: str, version: str, principals: Iterable[str]) -> None:
        key = (tenant, document_id, version)
        if key not in self._sources:
            raise KeyError('unknown source version')
        self._access[key] = frozenset(principals)

    def source_hash(self, tenant: str, document_id: str, version: str, *, principal: str) -> str:
        key=(tenant,document_id,version)
        if principal not in self._access.get(key,()):
            raise PermissionError('current source access required')
        return hashlib.sha256(self._sources[key].text.encode()).hexdigest()

    def add_event(self, event: ContextEvent) -> None:
        key = (event.tenant, event.event_id)
        if key in self._events:
            if self._events[key] != event:
                raise ValueError('event identity is immutable')
            return
        for ref in event.citations:
            source = self._sources.get((event.tenant, ref.document_id, ref.version))
            if source is None or source.text[ref.start:ref.end] != ref.passage or ref.end > len(source.text):
                raise ValueError('citation passage does not match exact source version')
            if source.available_at > event.available_at:
                raise ValueError('event precedes source availability')
        for old_id in event.supersedes:
            old = self._events.get((event.tenant, old_id))
            if old is None:
                raise ValueError('superseded event must already exist')
            if (old.subject,old.field) != (event.subject,event.field):
                raise ValueError('supersession scope must match subject and field')
            if not event.approval_verified or event.status not in ('approved','cancelled','observed'):
                raise ValueError('supersession must be explicitly authority-verified')
            if event.known_at < old.known_at:
                raise ValueError('supersession cannot precede prior event knowledge')
        self._events[key] = event

    def resolve(self, tenant: str, principal: str, as_of: datetime) -> ContextResolution:
        _aware(as_of)
        eligible = [e for e in self._events.values() if e.tenant == tenant
                    and e.known_at <= as_of]
        superseded = {eid for e in eligible for eid in e.supersedes}
        # Supersession of one assertion also retires canonical forwarded copies.
        old_signatures = {_duplicate_signature(e) for e in eligible if e.event_id in superseded}
        superseded.update(e.event_id for e in eligible if _duplicate_signature(e) in old_signatures)
        active = [e for e in eligible if e.event_id not in superseded]
        def visible(event):
            return all(principal in self._access[(tenant,r.document_id,r.version)]
                       for r in event.citations)
        groups = {}
        restricted = 0
        for e in active:
            # Do not reveal a derivative when any of its source dependencies is denied.
            if not visible(e):
                restricted += 1
                continue
            signature = _duplicate_signature(e)
            if signature not in groups:
                groups[signature] = e
            else:
                old = groups[signature]
                groups[signature] = replace(old, citations=tuple(dict.fromkeys(old.citations+e.citations)))
        visible_ids = {e.event_id for e in eligible if visible(e)}
        # Returned event objects are also a metadata surface. Keep the complete
        # retirement graph above, but expose only currently authorized links.
        events = tuple(replace(e,supersedes=tuple(eid for eid in e.supersedes if eid in visible_ids))
                       for e in groups.values())
        scopes = {}
        for event in events:
            scopes.setdefault((event.subject,event.field), []).append(event)
        # Pairwise conflicts preserve the time scope: a third, disjoint monthly
        # claim must not be pulled into an overlapping pair's disagreement.
        conflicts = tuple(sorted(tuple(sorted((left.event_id,right.event_id)))
                          for group in scopes.values() for left,right in combinations(group,2)
                          if _assertions_conflict(left,right) and _effective_ranges_overlap(left,right)))
        visible_superseded = tuple(sorted(e.event_id for e in eligible
                                          if e.event_id in superseded and visible(e)))
        return ContextResolution(events, conflicts, visible_superseded, restricted)


@dataclass(frozen=True)
class NumericAssumption:
    supplied_by: str
    rationale: str
    multiplier: Decimal

    def __post_init__(self):
        if any(not isinstance(v,str) or not v.strip() for v in (self.supplied_by,self.rationale)):
            raise ValueError('explicit user identity and numeric-assumption rationale required')
        _decimal(self.multiplier, 'multiplier')


@dataclass(frozen=True)
class WorkloadScenario:
    values: Tuple[Tuple[date, Decimal], ...]
    assumption: NumericAssumption
    conditional: bool = True
    mapping: str = 'user_workload_multiplier'
    limitations: Tuple[str, ...] = ('User-supplied scenario, not a causal estimate or execution probability.',)


def workload_scenario(values: Tuple[Tuple[date, Decimal], ...], *, as_of: datetime,
                      assumption: NumericAssumption, configured_mappings: Tuple[str, ...],
                      reporting_timezone: str = 'UTC') -> WorkloadScenario:
    """Apply a disclosed user assumption to future quantities only, once per call.

Input must be the unadjusted future baseline, never incurred charges or fixed
obligations. Price-only scenarios belong to forecasting.pricing and are separate.
"""
    _aware(as_of)
    local_origin=as_of.astimezone(ZoneInfo(reporting_timezone))
    if local_origin.timetz().replace(tzinfo=None) != time():
        raise ValueError('daily scenario requires reporting-calendar midnight; subdaily adjustment unsupported')
    if 'user_workload_multiplier' not in configured_mappings:
        raise ValueError('scenario mapping is not configured')
    if not isinstance(assumption, NumericAssumption):
        raise ValueError('explicit numeric user assumption required')
    if len({day for day,_ in values}) != len(values):
        raise ValueError('duplicate scenario date')
    for day,value in values:
        if day < local_origin.date():
            raise ValueError('scenario may change future dates only')
        _decimal(value,'future quantity')
    return WorkloadScenario(tuple((day,exact_product(value,assumption.multiplier)) for day,value in values), assumption)


def _identity(value: str, name: str) -> None:
    if not isinstance(value,str) or not value.strip():
        raise ValueError(name+' must be a nonempty string')


@dataclass(frozen=True)
class WorkloadBaseline:
    """An immutable future physical forecast, bound to its artifact and origin."""
    baseline_id: str
    target: Target
    as_of: datetime
    values: Tuple[Tuple[date, Decimal], ...]

    def __post_init__(self):
        _identity(self.baseline_id,'baseline identity')
        if not isinstance(self.target,Target) or self.target.measure != 'metered_usage':
            raise ValueError('baseline requires a typed physical usage target')
        if not isinstance(self.values,tuple) or any(
                not isinstance(row,tuple) or len(row) != 2 or type(row[0]) is not date
                for row in self.values):
            raise ValueError('immutable dated baseline quantities required')
        workload_scenario(self.values,as_of=self.as_of,
                          assumption=NumericAssumption('baseline-validation','Identity mapping',Decimal(1)),
                          configured_mappings=('user_workload_multiplier',),
                          reporting_timezone=self.target.reporting_timezone)

    @property
    def baseline_digest(self) -> str:
        return digest(self)


@dataclass(frozen=True)
class WorkloadAdjustment:
    adjustment_id: str
    assumption_id: str
    assumption: NumericAssumption

    def __post_init__(self):
        _identity(self.adjustment_id,'adjustment identity')
        _identity(self.assumption_id,'assumption identity')
        if not isinstance(self.assumption,NumericAssumption):
            raise ValueError('explicit numeric user assumption required')


@dataclass(frozen=True)
class BoundWorkloadScenario:
    """Replay derives values from the baseline and each named adjustment once."""
    baseline: WorkloadBaseline
    adjustments: Tuple[WorkloadAdjustment, ...]
    conditional: bool = True
    mapping: str = 'user_workload_multiplier'
    limitations: Tuple[str, ...] = ('User-supplied scenario, not a causal estimate or execution probability.',)

    def __post_init__(self):
        if not isinstance(self.baseline,WorkloadBaseline):
            raise ValueError('immutable workload baseline required')
        if not isinstance(self.adjustments,tuple) or not self.adjustments or any(
                not isinstance(a,WorkloadAdjustment) for a in self.adjustments):
            raise ValueError('immutable workload adjustments required')
        for name in ('adjustment_id','assumption_id'):
            if len({getattr(a,name) for a in self.adjustments}) != len(self.adjustments):
                raise ValueError('workload adjustment or assumption already applied')
        if self.conditional is not True or self.mapping != 'user_workload_multiplier':
            raise ValueError('workload scenarios must retain conditional mapping semantics')
        if (not isinstance(self.limitations,tuple) or not self.limitations or
                any(not isinstance(v,str) or not v.strip() for v in self.limitations)):
            raise ValueError('immutable scenario limitations required')
        # Eager evaluation rejects arithmetic overflow at construction.
        self.values

    @property
    def values(self) -> Tuple[Tuple[date, Decimal], ...]:
        values = self.baseline.values
        for adjustment in self.adjustments:
            values = tuple((day,exact_product(value,adjustment.assumption.multiplier))
                           for day,value in values)
        return values

    @property
    def scenario_id(self) -> str:
        return digest(self)


def apply_workload_adjustment(baseline_or_scenario, *, adjustment: WorkloadAdjustment,
                              configured_mappings: Tuple[str, ...]) -> BoundWorkloadScenario:
    """Apply a material assumption once; replay the same baseline deterministically."""
    if 'user_workload_multiplier' not in configured_mappings:
        raise ValueError('scenario mapping is not configured')
    if isinstance(baseline_or_scenario,WorkloadBaseline):
        baseline, adjustments = baseline_or_scenario, ()
    elif isinstance(baseline_or_scenario,BoundWorkloadScenario):
        baseline, adjustments = baseline_or_scenario.baseline, baseline_or_scenario.adjustments
    else:
        raise ValueError('immutable workload baseline or bound scenario required')
    return BoundWorkloadScenario(baseline,adjustments+(adjustment,))
