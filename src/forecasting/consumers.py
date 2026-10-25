"""Backend-owned REFERENCE finance harness, separate from numerical forecasting.

This local SQLite harness demonstrates review, current authority, evidence
staleness, atomic internal allocation changes and durable idempotency receipts.
It is not a provider control API, live Factory SDK, or production authentication.
The host must authenticate actors, protect this database and its administrative
methods, and supply current time. No text or forecast grants apply authority.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass, replace
from datetime import date, datetime
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Optional, Tuple
import uuid

from .contracts import exact_sum

Amounts = Tuple[Tuple[str, Decimal], ...]


class FinanceError(ValueError):
    """Concrete review or application declined; no partial mutation occurred."""


class InjectedFailure(RuntimeError):
    """Harness failure; after_commit requires authoritative receipt lookup."""


def _time(now: datetime):
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError('timezone-aware time required')


def _amount(value, name='amount', signed=False):
    if not isinstance(value, Decimal) or not value.is_finite() or (value < 0 and not signed):
        raise ValueError(name + ' must be a finite nonnegative Decimal')


def _amounts(values: Amounts, signed=False):
    if not isinstance(values,tuple) or len({k for k,v in values}) != len(values):
        raise ValueError('unique immutable entity amounts required')
    for key,value in values:
        if not key:
            raise ValueError('entity identity required')
        _amount(value,signed=signed)


def _encode(value):
    def default(obj):
        if isinstance(obj,(Decimal,date,datetime)):
            return str(obj) if isinstance(obj,Decimal) else obj.isoformat()
        raise TypeError(type(obj).__name__)
    return json.dumps(value,default=default,sort_keys=True,separators=(',',':'),allow_nan=False)


def _hash(value):
    return hashlib.sha256(_encode(value).encode()).hexdigest()


def _pairs(values):
    return tuple((k,Decimal(v)) for k,v in values)


@dataclass(frozen=True)
class BudgetState:
    tenant: str
    version: int
    period_start: date
    period_end: date
    unit: str
    coverage: Tuple[str, ...]
    allocations: Amounts
    protected_allocations: Amounts = ()
    provenance: str = 'synthetic'
    schema_version: str = '1.0'

    def __post_init__(self):
        if not self.tenant or not self.unit or self.version < 1 or self.period_start >= self.period_end:
            raise ValueError('explicit valid budget identity, unit and period required')
        if self.schema_version != '1.0' or not self.coverage or not isinstance(self.coverage,tuple):
            raise ValueError('supported schema and immutable coverage required')
        _amounts(self.allocations)
        _amounts(self.protected_allocations)
        allocated = dict(self.allocations)
        if not allocated or any(k not in allocated or v > allocated[k] for k,v in self.protected_allocations):
            raise ValueError('protected allocations must fit current allocations')

    @property
    def envelope(self):
        return exact_sum(v for _,v in self.allocations)


@dataclass(frozen=True)
class ForecastEvidence:
    tenant: str
    result_id: str
    period_start: date
    period_end: date
    unit: str
    coverage: Tuple[str, ...]
    complete: bool
    period_semantics: str
    totals: Amounts
    provenance: str = 'synthetic'
    limitations: Tuple[str, ...] = ()

    def __post_init__(self):
        if type(self.complete) is not bool:
            raise ValueError('forecast completeness must be bool')
        _amounts(self.totals,signed=True)
        if not self.result_id or self.period_start >= self.period_end:
            raise ValueError('valid forecast result identity and period required')
        if self.period_semantics not in ('full_period','remaining'):
            raise ValueError('unknown period semantics')


@dataclass(frozen=True)
class BudgetComparison:
    status: str
    gaps: Amounts
    limitations: Tuple[str, ...]
    meaning: str = 'Internal allocation minus compatible projected full-period spending; not safely removable funds.'


def compare_budget(state: BudgetState, forecast: Optional[ForecastEvidence]) -> BudgetComparison:
    if forecast is None:
        return BudgetComparison('unavailable',(),('Forecast unavailable; actual spending and budgets remain usable.',))
    compatible = (state.tenant == forecast.tenant and state.unit == forecast.unit
                  and state.period_start == forecast.period_start and state.period_end == forecast.period_end
                  and set(state.coverage) == set(forecast.coverage) and forecast.complete
                  and state.provenance == forecast.provenance and forecast.period_semantics == 'full_period'
                  and set(dict(state.allocations)) == set(dict(forecast.totals)))
    if not compatible:
        return BudgetComparison('unavailable',(),('Budget and forecast population, coverage, unit or period are incompatible/incomplete.',))
    totals = dict(forecast.totals)
    return BudgetComparison('available',tuple((k,exact_sum((v,totals[k].copy_negate()))) for k,v in state.allocations),
                            forecast.limitations+('A point estimate does not establish donor safety or overspend probability.',))


@dataclass(frozen=True)
class Proposal:
    proposal_id: str
    before: BudgetState
    after: BudgetState
    addition: Decimal
    operation: str
    business_requester: str
    requester_kind: str
    assistant_proposer: str
    rationale: str
    dependencies: Tuple[Tuple[str,str], ...]
    forecast_result_id: Optional[str]

    @property
    def content_hash(self):
        return _hash(asdict(self))


@dataclass(frozen=True)
class Review:
    review_id: str
    proposal_id: str
    actor: str
    proposal_hash: str
    reviewed_at: datetime


@dataclass(frozen=True)
class Receipt:
    receipt_id: str
    idempotency_key: str
    proposal_id: str
    proposal_hash: str
    after: BudgetState
    business_requester: str
    assistant_proposer: str
    finance_approver: str
    policy_version: str
    applied_at: datetime
    rationale: str
    forecast_result_id: Optional[str]
    dependencies: Tuple[Tuple[str,str], ...]
    evidence_access: str = 'available'


def _budget(d):
    return BudgetState(d['tenant'],d['version'],date.fromisoformat(d['period_start']),
                       date.fromisoformat(d['period_end']),d['unit'],tuple(d['coverage']),
                       _pairs(d['allocations']),_pairs(d['protected_allocations']),d['provenance'],d['schema_version'])


def _proposal(d):
    return Proposal(d['proposal_id'],_budget(d['before']),_budget(d['after']),Decimal(d['addition']),
                    d['operation'],d['business_requester'],d['requester_kind'],d['assistant_proposer'],
                    d['rationale'],tuple(tuple(v) for v in d['dependencies']),d['forecast_result_id'])


def _receipt(d):
    d = dict(d)
    d['after'] = _budget(d['after'])
    d['applied_at'] = datetime.fromisoformat(d['applied_at'])
    d['dependencies'] = tuple(tuple(v) for v in d['dependencies'])
    return Receipt(**d)


class FinanceStore:
    """Tenant-bound backend harness. Administrative configuration is trusted host code.

    All material dependencies listed on a proposal are compared exactly at apply;
    changing only display metadata with material=False leaves that version intact.
    The host must list every decision-relevant source/forecast/policy dependency.
    Approval is permitted for a finance instruction's initiator, but a beneficiary
    business requester cannot approve their own request. The assistant identity
    never replaces the underlying business requester.
    """
    def __init__(self, path, tenant: str):
        if not tenant:
            raise ValueError('tenant required')
        self.path = str(Path(path))
        self.tenant = tenant
        with self._connection() as c:
            c.executescript('''
            CREATE TABLE IF NOT EXISTS budgets (tenant TEXT PRIMARY KEY, body TEXT NOT NULL, spend TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS authority (tenant TEXT, actor TEXT, may_approve INTEGER, policy TEXT, expires TEXT, PRIMARY KEY(tenant,actor));
            CREATE TABLE IF NOT EXISTS dependencies (tenant TEXT, name TEXT, version TEXT, material_version TEXT, allowed TEXT, PRIMARY KEY(tenant,name));
            CREATE TABLE IF NOT EXISTS proposals (tenant TEXT, id TEXT, body TEXT, status TEXT, PRIMARY KEY(tenant,id));
            CREATE TABLE IF NOT EXISTS reviews (tenant TEXT, id TEXT, body TEXT, PRIMARY KEY(tenant,id));
            CREATE TABLE IF NOT EXISTS receipts (tenant TEXT, key TEXT, fingerprint TEXT, body TEXT, PRIMARY KEY(tenant,key));
            CREATE TABLE IF NOT EXISTS decisions (tenant TEXT, id TEXT, body TEXT, PRIMARY KEY(tenant,id));
            ''')

    def _connect(self):
        conn=sqlite3.connect(self.path, timeout=10, isolation_level=None)
        conn.execute('PRAGMA synchronous=FULL')
        conn.row_factory=sqlite3.Row
        return conn

    @contextmanager
    def _connection(self):
        c=self._connect()
        try:
            yield c
        finally:
            c.close()

    @contextmanager
    def _transaction(self):
        c=self._connect()
        try:
            c.execute('BEGIN IMMEDIATE')
            yield c
            c.commit()
        except BaseException:
            c.rollback()
            raise
        finally:
            c.close()

    def initialize(self, budget: BudgetState, recorded_spend: Amounts = ()):
        if budget.tenant != self.tenant:
            raise FinanceError('tenant scope mismatch')
        _amounts(recorded_spend,signed=True)
        with self._transaction() as c:
            existing=c.execute('SELECT body,spend FROM budgets WHERE tenant=?',(self.tenant,)).fetchone()
            body, spend = _encode(asdict(budget)), _encode(recorded_spend)
            if existing:
                if existing['body'] != body or existing['spend'] != spend:
                    raise FinanceError('existing budget cannot be overwritten by initialization')
                return
            c.execute('INSERT INTO budgets VALUES (?,?,?)',(self.tenant,body,spend))

    def grant_authority(self, actor: str, *, policy_version: str, may_approve=True, expires_at=None):
        if type(may_approve) is not bool:
            raise ValueError('may_approve must be bool')
        if not actor or not policy_version:
            raise ValueError('actor and explicit policy version required')
        if expires_at is not None:
            _time(expires_at)
        with self._transaction() as c:
            c.execute('INSERT OR REPLACE INTO authority VALUES (?,?,?,?,?)',
                      (self.tenant,actor,int(may_approve),policy_version,expires_at.isoformat() if expires_at else None))

    def revoke_authority(self, actor: str):
        with self._transaction() as c:
            c.execute('UPDATE authority SET may_approve=0 WHERE tenant=? AND actor=?',(self.tenant,actor))

    def set_dependency(self, name: str, version: str, *, material=True):
        if type(material) is not bool:
            raise ValueError('material must be bool')
        if not name or not version:
            raise ValueError('dependency name and version required')
        with self._transaction() as c:
            old=c.execute('SELECT material_version,allowed FROM dependencies WHERE tenant=? AND name=?',(self.tenant,name)).fetchone()
            material_version=version if material or old is None else old['material_version']
            c.execute('INSERT OR REPLACE INTO dependencies VALUES (?,?,?,?,?)',
                      (self.tenant,name,version,material_version,old['allowed'] if old else None))

    def set_dependency_access(self, name: str, principals: Tuple[str,...]):
        with self._transaction() as c:
            result=c.execute('UPDATE dependencies SET allowed=? WHERE tenant=? AND name=?',(_encode(principals),self.tenant,name))
            if result.rowcount != 1:
                raise FinanceError('unknown evidence dependency')

    def _read_access(self,c,actor):
        row=c.execute('SELECT * FROM authority WHERE tenant=? AND actor=?',(self.tenant,actor)).fetchone()
        if row is None:
            raise FinanceError('current tenant access denied')
        return row

    def _authorize(self,c,actor,proposal,now):
        row=self._read_access(c,actor)
        if not row['may_approve']:
            raise FinanceError('current finance authority required')
        if row['expires'] and now >= datetime.fromisoformat(row['expires']):
            raise FinanceError('current finance authority expired')
        if actor == proposal.assistant_proposer:
            raise FinanceError('assistant has no finance approval authority')
        if proposal.requester_kind == 'beneficiary_request' and actor == proposal.business_requester:
            raise FinanceError('business requester self-approval prohibited')
        return row['policy']

    def _state(self,c):
        row=c.execute('SELECT body FROM budgets WHERE tenant=?',(self.tenant,)).fetchone()
        if row is None:
            raise FinanceError('budget not initialized')
        return _budget(json.loads(row['body']))

    def _load_proposal(self,c,proposal_id):
        row=c.execute('SELECT body,status FROM proposals WHERE tenant=? AND id=?',(self.tenant,proposal_id)).fetchone()
        if row is None:
            raise FinanceError('proposal not found')
        return _proposal(json.loads(row['body'])),row['status']

    def _evidence_access(self,c,proposal,actor):
        for name,_ in proposal.dependencies:
            row=c.execute('SELECT allowed FROM dependencies WHERE tenant=? AND name=?',(self.tenant,name)).fetchone()
            if row is None or (row['allowed'] is not None and actor not in json.loads(row['allowed'])):
                return False
        return True

    def _fresh(self,c,proposal):
        if self._state(c) != proposal.before:
            raise FinanceError('stale budget: renewed concrete review required')
        for name,version in proposal.dependencies:
            row=c.execute('SELECT material_version FROM dependencies WHERE tenant=? AND name=?',(self.tenant,name)).fetchone()
            if row is None or row['material_version'] != version:
                raise FinanceError('stale evidence: renewed concrete review required')

    def prepare_proposal(self, *, after: Amounts, addition: Decimal, business_requester: str,
                         requester_kind: str, assistant_proposer: str, rationale: str,
                         dependency_keys: Tuple[str,...], forecast_result_id: Optional[str] = None,
                         unit: Optional[str] = None, period_start: Optional[date] = None,
                         period_end: Optional[date] = None, tenant: Optional[str] = None) -> Proposal:
        """Persist an explained draft; this does not authorize or apply anything."""
        _amount(addition,'addition')
        _amounts(after)
        if requester_kind not in ('finance_instruction','beneficiary_request'):
            raise FinanceError('explicit business requester kind required')
        if not all((business_requester,assistant_proposer,rationale)) or business_requester == assistant_proposer:
            raise FinanceError('distinct business requester and assistant proposer required')
        with self._transaction() as c:
            before=self._state(c)
            if ((tenant is not None and tenant != self.tenant) or (unit is not None and unit != before.unit)
                or (period_start is not None and period_start != before.period_start)
                or (period_end is not None and period_end != before.period_end)):
                raise FinanceError('proposal unit/period/tenant scope mismatch')
            if set(dict(after)) != set(dict(before.allocations)):
                raise FinanceError('proposal entity scope mismatch')
            if any(dict(after)[k] < value for k,value in before.protected_allocations):
                raise FinanceError('proposal violates protected allocations')
            if exact_sum(v for _,v in after) != exact_sum((before.envelope,addition)):
                raise FinanceError('allocation totals must reconcile to authorized addition')
            if addition and any(dict(after)[k]<v for k,v in before.allocations):
                raise FinanceError('funding addition must not silently include redistribution')
            dependencies=[]
            for name in sorted(set(dependency_keys)):
                row=c.execute('SELECT material_version FROM dependencies WHERE tenant=? AND name=?',(self.tenant,name)).fetchone()
                if row is None:
                    raise FinanceError('unknown evidence dependency')
                dependencies.append((name,row['material_version']))
            after_state=replace(before,version=before.version+1,allocations=after)
            proposal=Proposal(uuid.uuid4().hex,before,after_state,addition,'addition' if addition else 'redistribution',
                              business_requester,requester_kind,assistant_proposer,rationale,tuple(dependencies),forecast_result_id)
            c.execute('INSERT INTO proposals VALUES (?,?,?,?)',(self.tenant,proposal.proposal_id,_encode(asdict(proposal)),'pending'))
            return proposal

    def get_proposal(self, proposal_id: str, *, actor: str) -> Proposal:
        with self._connection() as c:
            self._read_access(c,actor)
            proposal,_=self._load_proposal(c,proposal_id)
            if not self._evidence_access(c,proposal,actor):
                raise FinanceError('proposal derivative restricted by current evidence access')
            return proposal

    def review(self, proposal_id: str, *, actor: str, now: datetime) -> Review:
        _time(now)
        with self._transaction() as c:
            proposal,status=self._load_proposal(c,proposal_id)
            if status != 'pending':
                raise FinanceError('proposal is '+status)
            self._authorize(c,actor,proposal,now)
            self._fresh(c,proposal)
            if not self._evidence_access(c,proposal,actor):
                raise FinanceError('review evidence restricted')
            review=Review(uuid.uuid4().hex,proposal_id,actor,proposal.content_hash,now)
            c.execute('INSERT INTO reviews VALUES (?,?,?)',(self.tenant,review.review_id,_encode(asdict(review))))
            return review

    def apply(self, review_id: str, *, actor: str, idempotency_key: str, now: datetime, fault=None) -> Receipt:
        _time(now)
        if not idempotency_key:
            raise FinanceError('idempotency key required')
        if fault not in (None,'before_commit','after_commit'):
            raise ValueError('unknown fault injection stage')
        with self._transaction() as c:
            self._read_access(c,actor)
            row=c.execute('SELECT body FROM reviews WHERE tenant=? AND id=?',(self.tenant,review_id)).fetchone()
            if row is None:
                raise FinanceError('explicit finance review required')
            review=json.loads(row['body'])
            if review['actor'] != actor:
                raise FinanceError('review belongs to another actor')
            proposal,status=self._load_proposal(c,review['proposal_id'])
            fingerprint=_hash({'proposal':proposal.content_hash,'actor':actor,'review':review_id})
            previous=c.execute('SELECT fingerprint,body FROM receipts WHERE tenant=? AND key=?',(self.tenant,idempotency_key)).fetchone()
            if previous:
                if previous['fingerprint'] != fingerprint:
                    raise FinanceError('idempotency key reused with different request')
                return self._visible_receipt(c,_receipt(json.loads(previous['body'])),actor)
            if status != 'pending':
                raise FinanceError('proposal is '+status)
            policy=self._authorize(c,actor,proposal,now)
            self._fresh(c,proposal)
            if review['proposal_hash'] != proposal.content_hash:
                raise FinanceError('review content hash mismatch')
            if not self._evidence_access(c,proposal,actor):
                raise FinanceError('apply evidence restricted')
            receipt=Receipt(uuid.uuid4().hex,idempotency_key,proposal.proposal_id,proposal.content_hash,proposal.after,
                            proposal.business_requester,proposal.assistant_proposer,actor,policy,now,proposal.rationale,
                            proposal.forecast_result_id,proposal.dependencies)
            c.execute('UPDATE budgets SET body=? WHERE tenant=?',(_encode(asdict(proposal.after)),self.tenant))
            c.execute('UPDATE proposals SET status=? WHERE tenant=? AND id=?',('applied',self.tenant,proposal.proposal_id))
            c.execute('INSERT INTO receipts VALUES (?,?,?,?)',(self.tenant,idempotency_key,fingerprint,_encode(asdict(receipt))))
            c.execute('INSERT INTO decisions VALUES (?,?,?)',(self.tenant,receipt.receipt_id,_encode({'status':'applied','receipt_id':receipt.receipt_id,'proposal_id':proposal.proposal_id})))
            if fault == 'before_commit':
                raise InjectedFailure('before_commit: all staged changes rolled back')
        if fault == 'after_commit':
            raise InjectedFailure('after_commit: response lost; retrieve receipt using the same key')
        return receipt

    def _visible_receipt(self,c,receipt,actor):
        if not self._evidence_access(c,receipt,actor):
            return replace(receipt,rationale='[restricted evidence]',evidence_access='restricted')
        return receipt

    def receipt(self, idempotency_key: str, *, actor: str) -> Optional[Receipt]:
        with self._connection() as c:
            self._read_access(c,actor)
            row=c.execute('SELECT body FROM receipts WHERE tenant=? AND key=?',(self.tenant,idempotency_key)).fetchone()
            return self._visible_receipt(c,_receipt(json.loads(row['body'])),actor) if row else None

    def reject(self, proposal_id: str, *, actor: str, reason: str, now: datetime):
        _time(now)
        if not reason:
            raise FinanceError('decision reason required')
        with self._transaction() as c:
            proposal,status=self._load_proposal(c,proposal_id)
            self._authorize(c,actor,proposal,now)
            if status != 'pending':
                raise FinanceError('proposal is '+status)
            decision={'decision_id':uuid.uuid4().hex,'proposal_id':proposal_id,'status':'rejected','reason':reason,
                      'actor':actor,'decided_at':now.isoformat(),'forecast_result_id':proposal.forecast_result_id}
            c.execute('UPDATE proposals SET status=? WHERE tenant=? AND id=?',('rejected',self.tenant,proposal_id))
            c.execute('INSERT INTO decisions VALUES (?,?,?)',(self.tenant,decision['decision_id'],_encode(decision)))
            return decision

    def decision_count(self):
        """Trusted administrative count for this tenant's local harness."""
        with self._connection() as c:
            return c.execute('SELECT COUNT(*) FROM decisions WHERE tenant=?',(self.tenant,)).fetchone()[0]

    def read_dashboard(self, *, actor: str, forecast: Optional[ForecastEvidence] = None):
        with self._connection() as c:
            self._read_access(c,actor)
            state=self._state(c)
            row=c.execute('SELECT spend FROM budgets WHERE tenant=?',(self.tenant,)).fetchone()
            comparison=compare_budget(state,forecast)
            return {'budget':state,'recorded_spend':_pairs(json.loads(row['spend'])),
                    'forecast_status':comparison.status,'comparison':comparison,
                    'forecast_result_id':forecast.result_id if forecast is not None else None,
                    'scope':'Internal planning only; external usage is unaffected.'}

    def proposal_status(self, proposal_id: str, *, actor: str) -> str:
        with self._connection() as c:
            self._read_access(c,actor)
            proposal,status=self._load_proposal(c,proposal_id)
            if not self._evidence_access(c,proposal,actor):
                return 'restricted'
            if status != 'pending':
                return status
            if self._state(c) != proposal.before:
                return 'stale_budget'
            try:
                self._fresh(c,proposal)
            except FinanceError:
                return 'stale_evidence'
            return 'pending'

    def decision_history(self, *, actor: str):
        with self._connection() as c:
            self._read_access(c,actor)
            result=[]
            for row in c.execute('SELECT body FROM decisions WHERE tenant=? ORDER BY rowid',(self.tenant,)):
                decision=json.loads(row['body'])
                proposal,_=self._load_proposal(c,decision['proposal_id'])
                if decision['status']=='applied':
                    # Look up the original receipt, never regenerate its explanation.
                    receipts=c.execute('SELECT body FROM receipts WHERE tenant=?',(self.tenant,)).fetchall()
                    receipt=next(_receipt(json.loads(r['body'])) for r in receipts
                                 if json.loads(r['body'])['receipt_id']==decision['receipt_id'])
                    decision['receipt']=json.loads(_encode(asdict(self._visible_receipt(c,receipt,actor))))
                elif not self._evidence_access(c,proposal,actor):
                    decision['reason']='[restricted evidence]'
                    decision['evidence_access']='restricted'
                result.append(decision)
            return tuple(result)

    def erase_dependency(self, name: str):
        """Do not pretend read-time redaction supplies retention/backup erasure."""
        raise FinanceError('unsupported: retention erasure requires host lineage purge and backup tombstone policy')


def target_coverage(target: dict) -> Tuple[str, ...]:
    """Canonical comparison scope; category equality alone is insufficient."""
    required=('sources','categories','measure','period_basis','gross_net','tax_treatment','reporting_timezone','currency')
    if any(key not in target for key in required):
        raise FinanceError('incomplete financial target scope')
    return tuple(sorted(['source:'+v for v in target['sources']]+['category:'+v for v in target['categories']]
                        +[key+':'+str(target[key]) for key in required if key not in ('sources','categories')]))


def _financial_value(value):
    if not isinstance(value,(str,Decimal)):
        raise FinanceError('financial adapter values require decimal strings')
    result=Decimal(value)
    if not result.is_finite():
        raise FinanceError('nonfinite financial adapter value')
    return result


def forecast_evidence(payload: dict, *, provenance: str = 'unspecified') -> ForecastEvidence:
    """Map the service JSON result to comparison evidence without inventing coverage.

    Late amounts currently have company scope, without a team allocation. Unknown
    or nonzero late amounts therefore cannot establish complete team forecasts.
    Bound service provenance cannot be relabeled. Legacy unbound payloads may
    retain an explicit host label; incurred coverage is checked independently
    from the numerical late-charge estimate.
    """
    if payload.get('schema_version')!='1.0':
        raise FinanceError('unsupported forecast schema')
    result=payload['result'];target=result['target']
    bound=payload['manifest'].get('evidence_class','unspecified')
    if bound!='unspecified':
        if provenance not in ('unspecified',bound):
            raise FinanceError('forecast evidence provenance cannot be relabeled')
        provenance=bound
    output=payload['manifest']['request']['output']
    if output not in ('full_period','remainder'):
        raise FinanceError('unsupported forecast period semantics')
    point=payload.get('capabilities',{}).get('point',False)
    if type(point) is not bool:
        raise FinanceError('point capability must be bool')
    available=result['status']!='unavailable' and point
    totals=()
    if available:
        totals=tuple((entity, exact_sum((_financial_value(row['future']),
                      _financial_value(row['recorded']) if output=='full_period' else Decimal(0))))
                     for entity,row in payload['entities'].items())
    late=result.get('late')
    limitations=list(result.get('limitations',()))
    incurred_flags=tuple(container['incurred_complete'] for container in (payload,payload['manifest'])
                         if 'incurred_complete' in container)
    if any(type(flag) is not bool for flag in incurred_flags):
        raise FinanceError('incurred_complete must be bool')
    # An adapter-level flag cannot upgrade incompleteness bound in the issued
    # manifest. Legacy limitations remain conservative evidence as well.
    incurred_complete=all(incurred_flags) and not any(v.startswith('incurred_gap:') for v in limitations)
    complete=available and bool(totals) and incurred_complete and late is not None and _financial_value(late)==0
    if not incurred_complete:
        limitations.append('Incomplete observed incurred coverage prevents a complete full-period comparison.')
    if late is None or _financial_value(late)!=0:
        limitations.append('Team totals exclude unavailable or unallocated late-incurred amounts.')
    if payload.get('read_status')=='stale' or result['status']=='stale':
        complete=False
        limitations.append('Stale result requires renewed evidence review before comparison.')
    return ForecastEvidence(target['tenant_id'],payload.get('artifact_id',result['result_id']),
                            date.fromisoformat(result['period_start']),date.fromisoformat(result['period_end']),
                            target['unit'],target_coverage(target),complete,
                            'full_period' if output=='full_period' else 'remaining',totals,provenance,tuple(limitations))


def frontend_view(state: BudgetState, recorded_spend: Amounts, *, forecast_payload: Optional[dict] = None,
                  receipt: Optional[Receipt] = None, action_state: str = 'idle', provenance: str = 'unspecified') -> dict:
    """Serializable reference frontend contract, not a rendered application.

    A successful finance action requires the backend receipt matching the displayed
    state. Unknown transport outcomes remain unknown until receipt lookup succeeds.
    """
    _amounts(recorded_spend,signed=True)
    if action_state not in ('idle','pending','unknown','failed','rejected','applied'):
        raise FinanceError('unsupported action state')
    if action_state=='applied' and (receipt is None or receipt.after!=state):
        raise FinanceError('applied state requires matching authoritative backend receipt')
    evidence=forecast_evidence(forecast_payload,provenance=provenance) if forecast_payload is not None else None
    comparison=compare_budget(state,evidence)
    status=forecast_payload['result']['status'] if forecast_payload is not None else 'unavailable'
    forecast={'status':status,'read_status':forecast_payload.get('read_status',status) if forecast_payload is not None else status,
              'result_id':evidence.result_id if evidence else None,
              'projected_totals':evidence.totals if evidence is not None and status!='unavailable' else None,
              'comparison_status':comparison.status,'gaps':comparison.gaps,'limitations':comparison.limitations,
              'period_semantics':evidence.period_semantics if evidence else None}
    return json.loads(_encode({'schema_version':'1.0','budget':asdict(state),'recorded_spend':recorded_spend,
                              'forecast':forecast,'action_state':action_state,'receipt':asdict(receipt) if receipt else None,
                              'scope':'Internal planning only; external usage is unaffected.'}))


def require_consumer_capability(capability: str) -> None:
    """Gate unsupported assistant requests before constructing numerical claims.

    Supported names identify reference handoffs, not independent permission to
    invoke them. Normal source and finance authority checks remain mandatory.
    """
    supported={'source_explanation','point_budget_comparison','manual_allocation_review'}
    if capability in supported:
        return
    reasons={
        'productivity_improvement':'spend does not identify effort, outcomes or opportunity cost',
        'causal_savings':'forecast-minus-actual is not an identified counterfactual',
        'shap_causal_explanation':'feature attribution does not establish a causal cost reduction',
        'causal_intervention':'internal allocations do not identify workload response or spillovers',
        'optimal_allocation':'no business utility or optimization policy has been supplied',
        'safe_transfer':'point forecasts and incomplete coverage do not certify removable funds',
        'latent_unconstrained_demand':'observed usage under hard caps does not identify uncensored demand',
        'retention_erasure':'host lineage purge and backup tombstone policy are required',
        'live_factory_sdk':'no authenticated Factory SDK runtime has been connected',
    }
    raise FinanceError('unsupported '+capability+': '+reasons.get(capability,'unknown consumer capability'))
