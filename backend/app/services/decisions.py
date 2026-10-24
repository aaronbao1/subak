"""Finance decisions: approve (apply) or reject, exactly once, with separation of duties (design.md §5).

`decide` order of checks:
1. Proposal must exist (404).
2. Role must be `finance_approver` (403 `role_forbidden`, recorded as a `role_blocked` event). Checked
   before the idempotency lookup so a non-approver can never obtain a decision through this route.
3. `Idempotency-Key` lookup: same fingerprint -> stored decision with `replayed: true`; a different
   fingerprint -> 409 `idempotency_key_reused`. The fingerprint covers proposal, outcome, rationale and
   deciding actor.
4. Approve by anyone who drafted this proposal or any proposal it was revised/rebased from, or who
   started the Droid run that drafted any of them (`AgentRun.input.initiated_by`) ->
   403 `self_approval_forbidden` (recorded). A requester may still reject its own proposal.
5. Status must be `pending_review` (409 `proposal_not_pending`).
6. Reject: decision row, status `rejected`, budget untouched.
7. Approve: optimistic lock `UPDATE budget_envelopes SET state_version = base+1 WHERE state_version = base`.
   0 rows -> proposal `stale` (only if it is still `pending_review`; a proposal that a concurrent
   approver already applied is reported as `proposal_not_pending`), `stale_rejected` event, 409
   `stale_proposal`. The proposal's own status is moved with a compare-and-set
   (`UPDATE proposals SET status=... WHERE status='pending_review'`), so a concurrent revise or other
   status change makes the decision fail as `proposal_not_pending`. Otherwise the lines are
   re-evaluated against the locked state, allocations written, snapshot + decision stored, invariant
   asserted, committed in one transaction. The unique constraints on `decisions.proposal_id` and
   `decisions.idempotency_key` make a concurrent second apply impossible at the database level.
"""

from __future__ import annotations

import hashlib
import json

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.actors import Actor
from app.core.clock import Clock, IdFactory
from app.core.errors import DomainError
from app.db.models import (
    AgentRun,
    BudgetAllocation,
    BudgetEnvelope,
    BudgetSnapshot,
    Decision,
    DecisionEvent,
    PlanningPeriod,
    Proposal,
)
from app.schemas.decisions import DecisionCreate
from app.services import budget as budget_svc
from app.services import proposals as proposal_svc

APPROVER_ROLE = "finance_approver"
MAX_IDEMPOTENCY_KEY = 200


def fingerprint(proposal_id: str, outcome: str, rationale: str, actor_id: str) -> str:
    payload = json.dumps([proposal_id, outcome, rationale.strip(), actor_id], separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def _record_event(session: Session, p: Proposal, event: str, actor: Actor, details: dict, *,
                  clock: Clock, ids: IdFactory) -> None:
    session.add(DecisionEvent(id=ids.new_id("evt_"), proposal_id=p.id, event=event, actor_id=actor.id,
                              details={"actor_role": actor.role, **details}, at=clock.now(), created_at=clock.now()))
    session.commit()


def _stale_error(p: Proposal, env: BudgetEnvelope) -> DomainError:
    return DomainError(
        "stale_proposal", 409,
        f"proposal was drafted against budget version {p.base_version} but the budget is now at version "
        f"{env.state_version}; it was not applied. Rebase it onto the current state and review it again.",
        {"proposal_id": p.id, "base_version": p.base_version, "current_version": env.state_version,
         "proposal_before": p.before, "current": budget_svc.current_figures(env)},
    )


def _lookup_key(session: Session, key: str, fp: str) -> Decision | None:
    existing = session.scalar(select(Decision).where(Decision.idempotency_key == key))
    if existing is None:
        return None
    if existing.request_fingerprint != fp:
        raise DomainError(
            "idempotency_key_reused", 409,
            "this Idempotency-Key was already used for a different decision request",
            {"decision_id": existing.id, "proposal_id": existing.proposal_id},
        )
    return existing


def _not_pending(session: Session, p: Proposal) -> DomainError:
    decision_id = session.scalar(select(Decision.id).where(Decision.proposal_id == p.id))
    return DomainError("proposal_not_pending", 409, f"proposal is {p.status}; it can no longer be decided",
                       {"status": p.status, "decision_id": decision_id})


def _mark_stale(session: Session, p: Proposal, actor: Actor, *, clock: Clock, ids: IdFactory) -> DomainError:
    session.rollback()
    p = session.get(Proposal, p.id)
    session.refresh(p)
    env = budget_svc.require_envelope(session, p.period_id)
    session.refresh(env)
    # A concurrent approver may have applied this very proposal (that is why the lock failed). Never
    # overwrite `applied` (or any other settled status) with `stale`: that would contradict the
    # decision history and let a rebase apply the same intent a second time.
    if not proposal_svc.claim_status(session, p, "stale", from_statuses=("pending_review",), now=clock.now()):
        session.rollback()
        p = session.get(Proposal, p.id)
        session.refresh(p)
        return _not_pending(session, p)
    _record_event(session, p, "stale_rejected", actor,
                  {"base_version": p.base_version, "current_version": env.state_version}, clock=clock, ids=ids)
    return _stale_error(p, env)


def decide(
    session: Session,
    proposal_id: str,
    body: DecisionCreate,
    *,
    actor: Actor,
    idempotency_key: str | None,
    clock: Clock,
    ids: IdFactory,
) -> tuple[Decision, bool]:
    """Returns (decision, replayed). Commits its own transaction(s)."""
    key = (idempotency_key or "").strip()
    if not key:
        raise DomainError("idempotency_key_required", 400,
                          "an Idempotency-Key header is required so a repeated click cannot apply twice")
    if len(key) > MAX_IDEMPOTENCY_KEY:
        raise DomainError("idempotency_key_invalid", 400, f"Idempotency-Key is limited to {MAX_IDEMPOTENCY_KEY} chars")

    p = proposal_svc.get_proposal(session, proposal_id)

    if actor.role != APPROVER_ROLE:
        _record_event(session, p, "role_blocked", actor, {"outcome": body.outcome}, clock=clock, ids=ids)
        raise DomainError("role_forbidden", 403,
                          f"role {actor.role!r} cannot decide proposals; only {APPROVER_ROLE} can",
                          {"role": actor.role, "allowed_roles": [APPROVER_ROLE]})

    fp = fingerprint(p.id, body.outcome, body.rationale, actor.id)
    existing = _lookup_key(session, key, fp)
    if existing is not None:
        return existing, True

    if body.outcome == "approve":
        authors = requesters(session, p)
        if actor.id in authors:
            via_run = actor.id not in {q.created_by_actor for q in proposal_svc.lineage(session, p)}
            _record_event(session, p, "self_approval_blocked", actor,
                          {"requester": p.created_by_actor, "via_agent_run": via_run}, clock=clock, ids=ids)
            raise DomainError("self_approval_forbidden", 403,
                              "a requester cannot approve its own request; another finance approver must decide"
                              + (" (you started the Droid run that drafted this proposal)" if via_run else ""),
                              {"actor_id": actor.id, "requester": p.created_by_actor, "via_agent_run": via_run})

    if p.status != "pending_review":
        raise _not_pending(session, p)

    env = budget_svc.require_envelope(session, p.period_id)
    now = clock.now()
    try:
        if body.outcome == "reject":
            decision = Decision(
                id=ids.new_id("dec_"), proposal_id=p.id, outcome="rejected", actor_id=actor.id,
                actor_role=actor.role, rationale=body.rationale, evidence_refs=_evidence(session, body),
                idempotency_key=key, request_fingerprint=fp, from_version=env.state_version, to_version=None,
                before=budget_svc.current_figures(env), after=None, decided_at=now, created_at=now,
            )
            if not proposal_svc.claim_status(session, p, "rejected", from_statuses=("pending_review",), now=now):
                raise _Moved()
            session.add(decision)
            session.commit()
            return decision, False

        decision = _apply(session, p, env, body, actor=actor, key=key, fp=fp, clock=clock, ids=ids)
        session.commit()
        return decision, False
    except _Stale:
        raise _mark_stale(session, p, actor, clock=clock, ids=ids) from None
    except _Moved:
        session.rollback()
        p = proposal_svc.get_proposal(session, proposal_id)
        session.refresh(p)
        raise _not_pending(session, p) from None
    except IntegrityError:
        # A concurrent request won the race for this key or this proposal.
        session.rollback()
        existing = _lookup_key(session, key, fp)
        if existing is not None:
            return existing, True
        p = proposal_svc.get_proposal(session, proposal_id)
        raise DomainError("proposal_not_pending", 409, f"proposal is {p.status}; it can no longer be decided",
                          {"status": p.status}) from None
    except Exception:
        session.rollback()
        raise


class _Stale(Exception):
    pass


class _Moved(Exception):
    """The proposal left `pending_review` (revised, decided, ...) while this decision was in flight."""


def requesters(session: Session, p: Proposal) -> set[str]:
    """Everyone who asked for this change: the author of each proposal in the revise/rebase lineage,
    plus the human who started the Droid run that drafted any of them."""
    chain = proposal_svc.lineage(session, p)
    ids = {q.id for q in chain}
    run_ids = {q.agent_run_id for q in chain if q.agent_run_id}
    out: set[str] = {q.created_by_actor for q in chain}
    # A later run that re-asked for an identical pending draft reuses it instead of drafting again;
    # whoever started that run asked for this change too.
    for run in session.scalars(select(AgentRun)):
        if run.id in run_ids or ids & set((run.output or {}).get("proposal_ids") or []):
            initiated = (run.input or {}).get("initiated_by") or {}
            if initiated.get("id"):
                out.add(initiated["id"])
    return out


def _evidence(session: Session, body: DecisionCreate) -> list[dict]:
    reasons, _, refs = proposal_svc.check_evidence(session, body.evidence_refs)
    if reasons:
        raise proposal_svc.validation_failed(reasons)
    return refs if body.evidence_refs else []


def _apply(session: Session, p: Proposal, env: BudgetEnvelope, body: DecisionCreate, *, actor: Actor, key: str,
           fp: str, clock: Clock, ids: IdFactory) -> Decision:
    if env.state_version != p.base_version:
        raise _Stale()
    evidence = _evidence(session, body)
    now = clock.now()
    # Optimistic lock: only one writer can move the envelope from base_version to base_version + 1.
    result = session.execute(
        update(BudgetEnvelope)
        .where(BudgetEnvelope.id == env.id, BudgetEnvelope.state_version == p.base_version)
        .values(state_version=p.base_version + 1, updated_at=now)
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        raise _Stale()
    # Compare-and-set the proposal itself: a concurrent revise does not bump the budget version.
    if not proposal_svc.claim_status(session, p, "applied", from_statuses=("pending_review",), now=now):
        raise _Moved()
    session.refresh(env)

    current = {a.team_id: a.amount for a in env.allocations}
    ev = proposal_svc.evaluate(
        session, action_type=p.action_type,
        envelope_increase=p.envelope_increase if p.action_type == "addition" else None,
        lines=p.lines, total=env.total_amount, allocations=current,
    )
    if ev.reasons:
        raise DomainError("proposal_no_longer_valid", 409, "the proposal does not apply to the current budget",
                          {"reasons": ev.reasons})
    if ev.before != p.before or ev.after != p.after:
        raise DomainError("proposal_state_mismatch", 409,
                          "the saved budget differs from the state the proposal was reviewed against",
                          {"expected_before": p.before, "actual_before": ev.before})

    by_team = {a.team_id: a for a in env.allocations}
    for team, amount in ev.after_allocations.items():
        row = by_team.get(team)
        if row is None:
            session.add(BudgetAllocation(id=ids.new_id("alloc_"), envelope_id=env.id, team_id=team,
                                         amount=amount, created_at=now))
        elif row.amount != amount:
            row.amount = amount
    env.total_amount = budget_svc.figures_to_decimal(ev.after)[0]

    decision = Decision(
        id=ids.new_id("dec_"), proposal_id=p.id, outcome="approved_applied", actor_id=actor.id,
        actor_role=actor.role, rationale=body.rationale, evidence_refs=evidence, idempotency_key=key,
        request_fingerprint=fp, from_version=p.base_version, to_version=p.base_version + 1,
        before=ev.before, after=ev.after, decided_at=now, created_at=now,
    )
    session.add(decision)
    session.flush()
    session.add(BudgetSnapshot(
        id=ids.new_id("snap_"), envelope_id=env.id, state_version=p.base_version + 1,
        total_amount=env.total_amount, allocations=ev.after["allocations"], decision_id=decision.id, created_at=now,
    ))
    session.flush()
    session.refresh(env)
    budget_svc.assert_invariant(env)
    return decision


# ---- history / output -----------------------------------------------------------------------


def list_decisions(session: Session, proposal_id: str | None = None) -> list[Decision]:
    q = select(Decision).order_by(Decision.decided_at, Decision.id)
    if proposal_id:
        q = q.where(Decision.proposal_id == proposal_id)
    return list(session.scalars(q))


def get_decision(session: Session, decision_id: str) -> Decision:
    d = session.get(Decision, decision_id)
    if d is None:
        raise DomainError("decision_not_found", 404, f"decision {decision_id!r} not found")
    return d


def list_events(session: Session, proposal_id: str | None = None) -> list[DecisionEvent]:
    q = select(DecisionEvent).order_by(DecisionEvent.at, DecisionEvent.id)
    if proposal_id:
        q = q.where(DecisionEvent.proposal_id == proposal_id)
    return list(session.scalars(q))


def decision_out(session: Session, d: Decision, *, replayed: bool = False) -> dict:
    p = session.get(Proposal, d.proposal_id)
    period = session.get(PlanningPeriod, p.period_id)
    env = budget_svc.require_envelope(session, p.period_id)
    return {
        "id": d.id,
        "proposal_id": d.proposal_id,
        "action_type": p.action_type,
        "outcome": d.outcome,
        "actor": {"id": d.actor_id, "role": d.actor_role},
        "requester": {"id": p.created_by_actor, "role": p.created_by_role},
        "rationale": d.rationale,
        "evidence_refs": d.evidence_refs,
        "proposal_evidence_refs": p.evidence_refs,
        "decided_at": d.decided_at,
        "from_version": d.from_version,
        "to_version": d.to_version,
        "before": proposal_svc._figures_out(d.before),
        "after": proposal_svc._figures_out(d.after) if d.after else None,
        "lines": proposal_svc.lines_out(p),
        "replayed": replayed,
        "budget_state": budget_svc.budget_state(session, period, env),
    }
