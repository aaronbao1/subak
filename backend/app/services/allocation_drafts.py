"""Translate complete allocation targets into the existing proposal authority boundary.

This service writes proposals and durable draft submission receipts only. It never writes a budget,
forecast, or decision. Approval, self-approval protection and application remain native operations.
"""

from __future__ import annotations

import hashlib
import json
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.actors import FINANCE_ROLES, Actor
from app.core.clock import Clock, IdFactory
from app.core.errors import DomainError
from app.core.money import MoneyError, money_str, parse_money
from app.db.models import AllocationDraftSubmission, BudgetRequest, PlanningPeriod, Proposal, Team
from app.schemas.allocation_drafts import AllocationDraftCreate
from app.schemas.proposals import AdditionCreate, EvidenceRef, TransferCreate
from app.services import budget as budget_svc
from app.services import proposals as proposal_svc

ZERO = Decimal("0.00")


def _require_finance(actor: Actor) -> None:
    if actor.role not in FINANCE_ROLES:
        raise DomainError("role_forbidden", 403, "only finance may draft an allocation plan",
                          {"role": actor.role, "allowed_roles": list(FINANCE_ROLES)})


def _key(raw: str | None) -> str:
    key = (raw or "").strip()
    if not key:
        raise DomainError("idempotency_key_required", 400,
                          "an Idempotency-Key header is required to recover repeated draft submissions")
    if len(key) > 200:
        raise DomainError("idempotency_key_invalid", 400, "Idempotency-Key is limited to 200 chars")
    return key


def _lookup(session: Session, actor: Actor, key: str, fingerprint: str | None = None) -> Proposal | None:
    submission = session.get(AllocationDraftSubmission, (actor.id, key))
    if submission is None:
        return None
    if fingerprint is not None and submission.fingerprint != fingerprint:
        raise DomainError("idempotency_key_reused", 409,
                          "this Idempotency-Key was already used for a different allocation draft",
                          {"proposal_id": submission.proposal_id})
    return proposal_svc.get_proposal(session, submission.proposal_id)


def get_submission(session: Session, key: str, *, actor: Actor) -> Proposal:
    """Recover the actor's native proposal after a lost submission response."""
    _require_finance(actor)
    proposal = _lookup(session, actor, _key(key))
    if proposal is None:
        raise DomainError("allocation_draft_not_found", 404, "no allocation draft was saved for this key")
    return proposal


def _amounts(body: AllocationDraftCreate) -> dict[str, Decimal]:
    amounts: dict[str, Decimal] = {}
    reasons = []
    for team, raw in sorted(body.allocations.items()):
        field = f"allocations.{team}"
        try:
            amount = parse_money(raw)
        except MoneyError as exc:
            reasons.append(proposal_svc._reason(exc.code, str(exc), field_name=field))
            continue
        if not isinstance(raw, str):
            reasons.append(proposal_svc._reason("money_string_required", "allocation amounts must be decimal strings",
                                                field_name=field))
        elif amount < ZERO:
            reasons.append(proposal_svc._reason("negative_allocation", "allocation amounts cannot be negative",
                                                field_name=field))
        else:
            amounts[team] = amount
    if reasons:
        raise proposal_svc.validation_failed(reasons)
    try:
        parse_money(sum(amounts.values(), ZERO))
    except MoneyError as exc:
        raise proposal_svc.validation_failed([proposal_svc._reason(
            exc.code, "the total allocation exceeds the supported money range", field_name="allocations")]) from exc
    return amounts


def _request_refs(session: Session, request_ids: list[str], period_id: str, teams: set[str]) -> list[EvidenceRef]:
    reasons = []
    refs = []
    referenced_teams: set[str] = set()
    for request_id in sorted(set(request_ids)):
        request = session.get(BudgetRequest, request_id)
        if request is None:
            reasons.append(proposal_svc._reason("unknown_budget_request", f"budget request {request_id!r} not found",
                                                field_name="request_ids"))
        elif request.period_id != period_id:
            reasons.append(proposal_svc._reason("request_period_mismatch",
                                                f"budget request {request_id!r} belongs to another planning period",
                                                field_name="request_ids"))
        elif request.team_id not in teams:
            reasons.append(proposal_svc._reason("request_team_mismatch",
                                                f"budget request {request_id!r} belongs to an unallocated team",
                                                field_name="request_ids"))
        elif request.requested_amount is None:
            reasons.append(proposal_svc._reason("request_amount_required",
                                                "a context update needs an explicit requested amount before "
                                                "it can be linked as a funding request",
                                                field_name="request_ids"))
        elif request.team_id in referenced_teams:
            reasons.append(proposal_svc._reason("request_team_ambiguous",
                                                "cite at most one request per team so one allocation change "
                                                "cannot be counted against multiple requests",
                                                field_name="request_ids"))
        else:
            referenced_teams.add(request.team_id)
            refs.append(EvidenceRef(kind="budget_request", id=request_id))
    if reasons:
        raise proposal_svc.validation_failed(reasons)
    return refs


def _native_body(session: Session, body: AllocationDraftCreate, amounts: dict[str, Decimal]) -> AdditionCreate | TransferCreate:
    if body.period_end_exclusive <= body.period_start:
        raise proposal_svc.validation_failed([proposal_svc._reason(
            "period_mismatch", "period_end_exclusive must follow period_start", field_name="period_end_exclusive")])
    period = session.scalar(select(PlanningPeriod).where(
        PlanningPeriod.starts_on == body.period_start,
        PlanningPeriod.ends_on == body.period_end_exclusive - timedelta(days=1),
    ))
    if period is None:
        raise proposal_svc.validation_failed([proposal_svc._reason(
            "period_mismatch", "allocation dates must exactly match a saved planning period", field_name="period_start")])
    env = budget_svc.require_envelope(session, period.id)
    if body.base_version < env.state_version:
        raise proposal_svc._stale_base_error(env, body.base_version)
    if body.base_version > env.state_version:
        raise proposal_svc.validation_failed([proposal_svc._reason(
            "base_version_in_future", "base_version is newer than the current budget", field_name="base_version")])
    current = budget_svc.allocation_map(env)
    expected, supplied = set(current), set(amounts)
    if expected != supplied:
        raise proposal_svc.validation_failed([proposal_svc._reason(
            "allocation_team_mismatch", "include every currently allocated team exactly once; "
            f"missing: {sorted(expected - supplied)}; unexpected: {sorted(supplied - expected)}",
            field_name="allocations")])
    active = set(session.scalars(select(Team.id).where(Team.active.is_(True))))
    inactive = sorted(expected - active)
    if inactive:
        raise proposal_svc.validation_failed([proposal_svc._reason(
            "inactive_team", f"allocation plan includes inactive teams: {inactive}", field_name="allocations")])
    refs = _request_refs(session, body.request_ids, period.id, expected)
    changes = {team: amount - current[team] for team, amount in amounts.items()}
    increase = sum(changes.values(), ZERO)
    common = {"base_version": body.base_version, "period": period.id, "unit": body.unit,
              "rationale": body.rationale, "evidence_refs": refs}
    if not any(changes.values()):
        raise proposal_svc.validation_failed([proposal_svc._reason(
            "no_allocation_change", "the allocation plan matches the current budget", field_name="allocations")])
    if increase < ZERO:
        raise proposal_svc.validation_failed([proposal_svc._reason(
            "envelope_decrease_unsupported", "reducing the company envelope is not supported; "
            "redistribute the existing envelope or add funding", field_name="allocations")])
    if increase > ZERO:
        if any(delta < ZERO for delta in changes.values()):
            raise proposal_svc.validation_failed([proposal_svc._reason(
                "mixed_addition_and_transfer", "redistribute the existing envelope in a separate proposal first, "
                "then add funding in a new proposal", field_name="allocations")])
        return AdditionCreate(action_type="addition", envelope_increase=money_str(increase),
                              lines=[{"to_team": team, "amount": money_str(delta)}
                                     for team, delta in sorted(changes.items()) if delta > ZERO], **common)
    # Pair sorted donors/recipients deterministically. Each team only gives or receives, never both.
    donors = [[team, -delta] for team, delta in sorted(changes.items()) if delta < ZERO]
    recipients = [[team, delta] for team, delta in sorted(changes.items()) if delta > ZERO]
    lines = []
    donor_index = 0
    for recipient, needed in recipients:
        while needed > ZERO:
            donor, remaining = donors[donor_index]
            amount = min(remaining, needed)
            lines.append({"from_team": donor, "to_team": recipient, "amount": money_str(amount)})
            needed -= amount
            donors[donor_index][1] -= amount
            if donors[donor_index][1] == ZERO:
                donor_index += 1
    return TransferCreate(action_type="transfer", lines=lines, **common)


def create_draft(session: Session, body: AllocationDraftCreate, *, actor: Actor,
                 idempotency_key: str | None, clock: Clock, ids: IdFactory) -> tuple[Proposal, bool]:
    """Save the native proposal and replay receipt atomically; returns (proposal, replayed)."""
    _require_finance(actor)
    key = _key(idempotency_key)
    amounts = _amounts(body)
    canonical = body.model_dump(mode="json")
    canonical["allocations"] = {team: money_str(amount) for team, amount in amounts.items()}
    canonical["rationale"] = body.rationale.strip()
    canonical["request_ids"] = sorted(set(body.request_ids))
    fingerprint = hashlib.sha256(json.dumps(
        {"endpoint": "allocation-drafts", "actor_id": actor.id, "body": canonical},
        sort_keys=True, separators=(",", ":"),
    ).encode()).hexdigest()
    existing = _lookup(session, actor, key, fingerprint)
    if existing is not None:
        return existing, True
    native = _native_body(session, body, amounts)
    try:
        warnings = [{"code": "manual_allocation_targets", "message":
                     "This manual allocation plan cites team requests; the targets are finance choices, "
                     "not a saved forecast assessment."}] if body.request_ids else []
        proposal = proposal_svc.create_proposal(session, native, actor=actor, clock=clock, ids=ids,
                                                extra_warnings=warnings)
        session.add(AllocationDraftSubmission(actor_id=actor.id, idempotency_key=key,
                                             fingerprint=fingerprint, proposal_id=proposal.id,
                                             created_at=clock.now()))
        session.commit()
        return proposal, False
    except IntegrityError:
        session.rollback()
        existing = _lookup(session, actor, key, fingerprint)
        if existing is not None:
            return existing, True
        raise
    except Exception:
        session.rollback()
        raise


def allocation_state(session: Session, *, period_id: str | None, clock: Clock) -> dict:
    """Expose native budget facts with explicit half-open dates and stable team IDs."""
    period, env = budget_svc.resolve_envelope(session, period_id, clock)
    state = budget_svc.budget_state(session, period, env)
    state["period"] = {"id": period.id, "start_date": period.starts_on,
                       "end_date_exclusive": period.ends_on + timedelta(days=1), "label": period.label}
    state["unallocated_amount"] = state["envelope_total"] - state["allocated_total"]
    state["allocations"] = [{"team_id": row["team"], **{key: value for key, value in row.items() if key != "team"}}
                            for row in state["allocations"]]
    return state
