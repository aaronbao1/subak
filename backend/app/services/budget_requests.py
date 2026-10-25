"""Durable intake, read-only current assessment, and receipt-derived request fulfillment.

Intake never appends forecast evidence or changes an issued forecast. Explicit requested amounts are
additional allocation intent, not new predicted spend. Drafting uses the native proposal boundary.
"""
from __future__ import annotations

import hashlib
import json
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.actors import Actor
from app.core.clock import Clock, IdFactory
from app.core.errors import DomainError
from app.core.money import MoneyError, money_str, parse_money
from app.db.models import AllocationDraftSubmission, BudgetRequest, Decision, PlanningPeriod, Proposal, Team
from app.schemas.budget_requests import BudgetRequestCreate, BudgetRequestDraft
from app.schemas.forecasts import ForecastResult
from app.schemas.proposals import AdditionCreate, EvidenceRef, TransferCreate
from app.services import allocation_drafts as draft_svc
from app.services import budget as budget_svc
from app.services import forecasts as forecast_svc
from app.services import proposals as proposal_svc
from app.services.source_completion import source_completion

ZERO = Decimal("0.00")


def _fingerprint(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def get_request(session: Session, request_id: str) -> BudgetRequest:
    row = session.get(BudgetRequest, request_id)
    if row is None:
        raise DomainError("budget_request_not_found", 404, "budget request not found")
    return row


def _period(session: Session, body: BudgetRequestCreate) -> PlanningPeriod:
    period = session.scalar(select(PlanningPeriod).where(
        PlanningPeriod.starts_on == body.period_start,
        PlanningPeriod.ends_on == body.period_end_exclusive - timedelta(days=1)))
    if period is None or body.period_end_exclusive <= body.period_start:
        raise DomainError("request_period_mismatch", 422,
                          "request dates must exactly match an existing planning period")
    return period


def create_request(session: Session, body: BudgetRequestCreate, *, actor: Actor, clock: Clock,
                   ids: IdFactory) -> tuple[BudgetRequest, bool]:
    draft_svc._require_finance(actor)
    fingerprint = _fingerprint(body.model_dump(mode="json"))
    def existing():
        prior = session.scalar(select(BudgetRequest).where(BudgetRequest.submitted_by == actor.id,
                                                           BudgetRequest.client_request_id == body.client_request_id))
        if prior is not None and prior.fingerprint != fingerprint:
            raise DomainError("request_key_reused", 409,
                              "client_request_id already identifies a different submitted request",
                              {"request_id": prior.id})
        return prior
    prior = existing()
    if prior is not None:
        return prior, True
    team = session.get(Team, body.team_id)
    if team is None or not team.active:
        raise DomainError("request_team_invalid", 422, "the request must name an active team")
    period = _period(session, body)
    env = budget_svc.get_envelope(session, period.id)
    if body.requested_amount is not None and env is not None:
        try:
            parse_money(budget_svc.allocation_map(env).get(body.team_id, ZERO) + body.requested_amount)
        except MoneyError as exc:
            raise DomainError(exc.code, 422, "requested funding would exceed the supported budget amount range") from exc
    reasons, _, refs = proposal_svc.check_evidence(session, body.evidence_refs)
    if reasons:
        raise proposal_svc.validation_failed(reasons)
    row = BudgetRequest(id=ids.new_id("brq_"), client_request_id=body.client_request_id,
                        submitted_by=actor.id, fingerprint=fingerprint, team_id=body.team_id,
                        period_id=period.id, title=body.title, request_kind=body.request_kind,
                        project_name=body.project_name, narrative=body.narrative,
                        requested_amount=body.requested_amount, unit=body.unit, source_ref=body.source_ref,
                        evidence_refs=refs, created_at=clock.now())
    session.add(row)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        prior = existing()
        if prior is None:
            raise
        return prior, True
    return row, False


def _lineage(session: Session, row: BudgetRequest) -> tuple[list[Proposal], list[Decision], Decimal, str, bool]:
    proposals = list(session.scalars(select(Proposal).where(Proposal.period_id == row.period_id)
                                    .order_by(Proposal.created_at, Proposal.id)))
    linked = {p.id for p in proposals if any(ref.get("kind") == "budget_request" and ref.get("id") == row.id
                                           for ref in p.evidence_refs)}
    changed = True
    while changed:
        changed = False
        for proposal in proposals:
            if proposal.id not in linked and (proposal.revises_proposal_id in linked or
                                              proposal.rebased_from_proposal_id in linked):
                linked.add(proposal.id)
                changed = True
    included = [p for p in proposals if p.id in linked]
    decisions = list(session.scalars(select(Decision).where(Decision.proposal_id.in_(linked))
                                    .order_by(Decision.decided_at, Decision.id))) if linked else []
    approved = ZERO
    ambiguous = False
    for receipt in decisions:
        if row.requested_amount is None or receipt.outcome != "approved_applied" or receipt.after is None:
            continue
        # A team-level increase is not evidence of earmarking across multiple same-team requests.
        proposal = next(p for p in included if p.id == receipt.proposal_id)
        ancestry = [proposal]
        seen = set()
        while ancestry:
            parent = ancestry.pop()
            if parent.id in seen:
                continue
            seen.add(parent.id)
            ancestry.extend(p for p in proposals if p.id in (parent.revises_proposal_id, parent.rebased_from_proposal_id))
        refs = {ref.get("id") for p in proposals if p.id in seen for ref in p.evidence_refs
                if ref.get("kind") == "budget_request"}
        same_team = [r for r in (session.get(BudgetRequest, rid) for rid in refs)
                     if r is not None and r.team_id == row.team_id and r.requested_amount is not None]
        if len(same_team) > 1:
            ambiguous = True
            continue
        before = Decimal(receipt.before.get("allocations", {}).get(row.team_id, "0"))
        after = Decimal(receipt.after.get("allocations", {}).get(row.team_id, "0"))
        approved += max(ZERO, after - before)
    env = budget_svc.get_envelope(session, row.period_id)
    replaced = {p.revises_proposal_id for p in included} | {p.rebased_from_proposal_id for p in included}
    leaves = [p for p in included if p.id not in replaced]
    if row.requested_amount is None:
        status = "submitted"
    elif ambiguous:
        status = "needs_revision"
    elif row.requested_amount is not None and approved >= row.requested_amount:
        status = "approved_applied"
    elif approved > ZERO:
        status = "partially_funded"
    elif any(p.status == "pending_review" and env is not None and p.base_version == env.state_version for p in leaves):
        status = "pending_review"
    elif any(p.status in ("pending_review", "stale", "revised") for p in leaves):
        status = "needs_revision"
    elif leaves and all(p.status == "rejected" for p in leaves):
        status = "rejected"
    else:
        status = "submitted"
    return included, decisions, approved, status, ambiguous


def _assessment(session: Session, row: BudgetRequest, forecast: ForecastResult, *, clock: Clock,
                remaining_amount: Decimal | None = None) -> dict:
    requested = row.requested_amount if remaining_amount is None else remaining_amount
    env = budget_svc.get_envelope(session, row.period_id)
    allocations = budget_svc.allocation_map(env) if env else {}
    spend = budget_svc.recorded_spend_by_team(session, row.period_id)
    from app.services.forecast_freshness import current_revision
    stale = bool(forecast.input_revision and forecast.input_revision !=
                 current_revision(session, forecast.tenant_id or "northstar", clock.now()))
    if forecast.repository_revision:
        from app.forecasting.repository import repository_revision
        stale = stale or forecast.repository_revision != repository_revision(session, clock.now())
    usable = (not stale and forecast.target_period == row.period_id and forecast.basis == "full_period_total"
              and forecast.availability in ("available", "partial"))
    projections = {p.team: p.amount for p in forecast.projections if p.unit == row.unit} if usable else {}
    projected = projections.get(row.team_id)
    allocation = allocations.get(row.team_id)
    headroom = None if allocation is None or projected is None else allocation - max(projected, spend.get(row.team_id, ZERO))
    donors = [{"team_id": team, "headroom": money_str(amount - max(projections[team], spend.get(team, ZERO)))}
              for team, amount in sorted(allocations.items()) if team != row.team_id and team in projections
              and amount > max(projections[team], spend.get(team, ZERO))]
    requested_allocation = None
    requested_overflow = False
    if allocation is not None and requested is not None:
        try:
            requested_allocation = money_str(allocation + requested)
        except MoneyError:
            # A later allocation change must not make an older, immutable request unreadable.
            requested_overflow = True
    completion = source_completion(session, clock.now())
    period = session.get(PlanningPeriod, row.period_id)
    through = completion.period_through(row.team_id, period.starts_on, period.ends_on + timedelta(days=1),
                                       clock.now(), spend.get(row.team_id, ZERO)) if completion is not None and period and completion.is_current(session) else None
    reason = (f"Current team allocation and matching full-period forecast; recorded spend is complete through {through.isoformat()}. Later days remain unknown. "
              if through else "Current team allocation and matching full-period forecast; recorded spend is a subtotal with incomplete source coverage. ")
    reason += "The requested amount is additional allocation intent and is not included in this forecast."
    if row.requested_amount is None:
        reason += " No funding amount was requested; this is source context and linked decisions do not assign funding to this update."
    if row.request_kind != "team":
        reason += " Project context is assessed against its funding team; no separate project forecast is available."
    if requested_overflow:
        reason += " The resulting requested allocation is outside the supported monetary range; revise the request before drafting."
    if stale:
        reason += " The issued forecast is stale because its source inputs changed; publish a new forecast before relying on headroom."
    if projected is None:
        reason += " A matching complete team forecast amount is unavailable; projected headroom is unknown."
    if env is None:
        reason += " No budget envelope exists for this period."
    return {"assessed_at": clock.now(), "budget_version": env.state_version if env else None,
            "envelope_total": money_str(env.total_amount) if env else None,
            "team_allocation": money_str(allocation) if allocation is not None else None,
            "recorded_spend": money_str(spend.get(row.team_id, ZERO)),
            "forecast_amount": money_str(projected) if projected is not None else None,
            "forecast_run_id": forecast.forecast_run_id if projected is not None else None,
            "forecast_status": "available" if projected is not None else "unavailable",
            "forecast_unit": "USD", "forecast_basis": "full_period_total",
            "projected_headroom": money_str(headroom) if headroom is not None else None,
            "requested_allocation": requested_allocation,
            "available_donors": donors, "qualification": reason, "amount_included_in_forecast": False}


def request_out(session: Session, row: BudgetRequest, *, provider, clock: Clock,
                forecast: ForecastResult | None = None) -> dict:
    period = session.get(PlanningPeriod, row.period_id)
    forecast = forecast or forecast_svc.forecast_for_period(session, provider, period, clock=clock)
    proposals, decisions, approved, status, ambiguous = _lineage(session, row)
    assessment = _assessment(session, row, forecast, clock=clock,
                             remaining_amount=max(ZERO, row.requested_amount - approved)
                             if row.requested_amount is not None else None)
    if ambiguous:
        assessment["requested_allocation"] = None
        assessment["qualification"] += " An applied decision cites multiple requests for this team; request-specific funding attribution is unresolved. No remaining funding amount can be inferred."
    end = period.ends_on + timedelta(days=1)
    return {"id": row.id, "client_request_id": row.client_request_id, "team_id": row.team_id,
            "title": row.title, "request_kind": row.request_kind, "project_name": row.project_name,
            "narrative": row.narrative, "requested_amount": money_str(row.requested_amount) if row.requested_amount is not None else None,
            "unit": row.unit, "period_start": period.starts_on, "period_end_exclusive": end,
            "source_ref": row.source_ref, "evidence_refs": row.evidence_refs,
            "period": {"id": period.id, "start_date": period.starts_on, "end_date_exclusive": end, "label": period.label},
            "source": {"reference": row.source_ref, "submitted_by": row.submitted_by, "submitted_at": row.created_at},
            "status": status, "linked_proposal_ids": [p.id for p in proposals], "decision_ids": [d.id for d in decisions],
            "approved_amount": money_str(approved),
            "remaining_requested_amount": money_str(max(ZERO, row.requested_amount - approved)) if row.requested_amount is not None and not ambiguous else None,
            "assessment": assessment}


def list_requests(session: Session, *, provider, clock: Clock) -> list[dict]:
    rows = list(session.scalars(select(BudgetRequest).order_by(BudgetRequest.created_at.desc(), BudgetRequest.id.desc())))
    forecasts = {pid: forecast_svc.forecast_for_period(session, provider, session.get(PlanningPeriod, pid), clock=clock)
                 for pid in {row.period_id for row in rows}}
    return [request_out(session, row, provider=provider, clock=clock, forecast=forecasts[row.period_id]) for row in rows]


def create_draft(session: Session, row: BudgetRequest, body: BudgetRequestDraft, *, actor: Actor,
                 provider, idempotency_key: str | None, clock: Clock, ids: IdFactory) -> tuple[Proposal, bool]:
    draft_svc._require_finance(actor)
    key = draft_svc._key(idempotency_key)
    fingerprint = _fingerprint({"endpoint": "budget-request-draft", "request_id": row.id,
                                "actor_id": actor.id, "body": body.model_dump(mode="json")})
    prior = draft_svc._lookup(session, actor, key, fingerprint)
    if prior:
        return prior, True
    if row.requested_amount is None:
        raise DomainError("request_amount_required", 422, "this update has no explicit funding amount; submit a funding request before drafting")
    _, _, funded, _, ambiguous = _lineage(session, row)
    if ambiguous:
        raise DomainError("request_funding_attribution_unclear", 409,
                          "an applied decision covers multiple requests for this team; resolve funding attribution before drafting more")
    remaining = max(ZERO, row.requested_amount - funded)
    if remaining == ZERO:
        raise DomainError("request_already_funded", 409, "confirmed decisions already cover the requested amount")
    if body.action_type == "addition":
        env = budget_svc.require_envelope(session, row.period_id)
        try:
            parse_money(env.total_amount + remaining)
        except MoneyError as exc:
            raise DomainError(exc.code, 422, "additional funding would exceed the supported budget amount range") from exc
    period = session.get(PlanningPeriod, row.period_id)
    forecast = forecast_svc.forecast_for_period(session, provider, period, clock=clock)
    assessment = _assessment(session, row, forecast, clock=clock)
    # Supporting request references describe source provenance, not additional funding earmarks.
    # The saved intake retains that source chain; this proposal funds only the selected request.
    refs = [EvidenceRef(kind="budget_request", id=row.id),
            *[EvidenceRef.model_validate(r) for r in row.evidence_refs if r.get("kind") != "budget_request"]]
    receipt = forecast_svc.snapshot(session, forecast, clock=clock, ids=ids)
    refs.append(EvidenceRef(kind="forecast_snapshot", id=receipt.id))
    common = {"base_version": body.base_version, "period": row.period_id, "unit": row.unit,
              "rationale": f"Review request: {row.title}. {row.narrative}"[:10000], "evidence_refs": refs}
    if body.action_type == "addition":
        if body.source_team_id is not None:
            raise DomainError("request_source_invalid", 422, "additional funding has no source team; choose transfer for redistribution")
        native = AdditionCreate(action_type="addition", envelope_increase=money_str(remaining),
                                lines=[{"to_team": row.team_id, "amount": money_str(remaining)}], **common)
    else:
        donors = {d["team_id"]: Decimal(d["headroom"]) for d in assessment["available_donors"]}
        if not body.source_team_id or body.source_team_id == row.team_id:
            raise DomainError("request_source_required", 422, "select a different explicit source team for this transfer")
        if donors.get(body.source_team_id, ZERO) < remaining:
            raise DomainError("request_source_headroom_insufficient", 422,
                              "the selected source has insufficient supported forecast headroom for the full remaining request",
                              {"source_team_id": body.source_team_id, "requested_amount": money_str(remaining),
                               "supported_headroom": money_str(donors.get(body.source_team_id, ZERO))})
        native = TransferCreate(action_type="transfer", lines=[{"from_team": body.source_team_id,
                                "to_team": row.team_id, "amount": money_str(remaining)}], **common)
    proposal = proposal_svc.create_proposal(session, native, actor=actor, clock=clock, ids=ids)
    session.add(AllocationDraftSubmission(actor_id=actor.id, idempotency_key=key, fingerprint=fingerprint,
                                          proposal_id=proposal.id, created_at=clock.now()))
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        prior = draft_svc._lookup(session, actor, key, fingerprint)
        if prior is None:
            raise
        return prior, True
    return proposal, False
