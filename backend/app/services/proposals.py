"""Draft, validate, rebase and revise allocation proposals (design.md §3.7, §5).

A proposal is either an `addition` (new money enters the envelope and is allocated to teams) or a
`transfer` (existing money moves between teams; the envelope is unchanged). They are never mixed: a
mixed intent is two proposals. The backend computes `before`/`after` from the saved state at
`base_version`; nothing about the result is trusted from the client.

Every validation problem is reported at once as `422 validation_failed` with
`details.reasons[] = {code, message, line?, field?}`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Iterable

from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from app.core.actors import FINANCE_ROLES, Actor
from app.core.clock import Clock, IdFactory
from app.core.errors import DomainError
from app.core.money import MoneyError, money_str, parse_money
from app.db.models import (
    AgentRun,
    BudgetEnvelope,
    ContextSignal,
    CorpusDocument,
    Decision,
    DecisionEvent,
    ForecastSnapshot,
    PlanningPeriod,
    Proposal,
    Team,
)
from app.schemas.proposals import AdditionCreate, EvidenceRef, RebaseIn, TransferCreate
from app.services import budget as budget_svc

ZERO = Decimal("0.00")
DRAFTING_ROLES = ("droid_agent", "finance_approver", "finance_analyst")
REVISABLE_STATUSES = ("pending_review", "stale")


def _reason(code: str, message: str, *, line: int | None = None, field_name: str | None = None) -> dict:
    out: dict[str, Any] = {"code": code, "message": message}
    if line is not None:
        out["line"] = line
    if field_name is not None:
        out["field"] = field_name
    return out


def validation_failed(reasons: list[dict], **extra: Any) -> DomainError:
    return DomainError(
        "validation_failed", 422, "proposal is invalid: " + ", ".join(sorted({r["code"] for r in reasons})),
        {"reasons": reasons, **extra},
    )


@dataclass
class Evaluation:
    """Result of applying proposed lines to one budget state."""

    reasons: list[dict] = field(default_factory=list)
    warnings: list[dict] = field(default_factory=list)
    envelope_increase: Decimal = ZERO
    lines: list[dict] = field(default_factory=list)  # canonical JSON lines (amounts as strings)
    before: dict | None = None
    after: dict | None = None
    after_allocations: dict[str, Decimal] = field(default_factory=dict)


def _parse_amount(raw: Any, *, line: int | None, field_name: str, reasons: list[dict]) -> Decimal | None:
    try:
        amount = parse_money(raw)
    except MoneyError as exc:
        reasons.append(_reason(exc.code, str(exc), line=line, field_name=field_name))
        return None
    if amount <= ZERO:
        reasons.append(_reason("non_positive_amount", f"{field_name} must be greater than 0.00, got {money_str(amount)}",
                               line=line, field_name=field_name))
        return None
    return amount


def _active_teams(session: Session) -> set[str]:
    return set(session.scalars(select(Team.id).where(Team.active.is_(True))))


def evaluate(
    session: Session,
    *,
    action_type: str,
    envelope_increase: Any,
    lines: Iterable[Any],
    total: Decimal,
    allocations: dict[str, Decimal],
) -> Evaluation:
    """Validate lines against a budget state and compute the resulting state. Pure: writes nothing.

    `lines` are objects/dicts with `to_team`, `amount` and (transfers) `from_team`.
    """
    ev = Evaluation()
    reasons = ev.reasons
    teams = _active_teams(session)
    raw_lines = [ln if isinstance(ln, dict) else ln.model_dump() for ln in lines]
    after = dict(allocations)
    ev.before = budget_svc.figures(total, allocations)

    if not raw_lines:
        reasons.append(_reason("empty_lines", "a proposal needs at least one line", field_name="lines"))

    def check_team(team: Any, *, line: int, field_name: str) -> bool:
        if not isinstance(team, str) or team not in teams:
            reasons.append(_reason("unknown_team", f"unknown or inactive team {team!r}", line=line, field_name=field_name))
            return False
        return True

    seen: set[tuple] = set()
    if action_type == "transfer":
        if envelope_increase is not None:
            try:
                inc = parse_money(envelope_increase)
            except MoneyError:
                inc = None
            if inc is None or inc != ZERO:
                reasons.append(_reason(
                    "transfer_with_envelope_change",
                    "a transfer moves existing funds and cannot change the envelope; "
                    "use a separate addition proposal for new money",
                    field_name="envelope_increase",
                ))
        debited: set[str] = set()
        credited: set[str] = set()
        for i, ln in enumerate(raw_lines):
            src, dst = ln.get("from_team"), ln.get("to_team")
            ok = check_team(src, line=i, field_name="from_team") & check_team(dst, line=i, field_name="to_team")
            if ok and src == dst:
                reasons.append(_reason("same_team_transfer", f"cannot transfer from {src!r} to itself", line=i))
                ok = False
            if ok and (src, dst) in seen:
                reasons.append(_reason("duplicate_line", f"more than one line moves funds {src} -> {dst}", line=i))
                ok = False
            amount = _parse_amount(ln.get("amount"), line=i, field_name="amount", reasons=reasons)
            if not ok or amount is None:
                continue
            seen.add((src, dst))
            debited.add(src)
            credited.add(dst)
            after[src] = after.get(src, ZERO) - amount
            after[dst] = after.get(dst, ZERO) + amount
            ev.lines.append({"from_team": src, "to_team": dst, "amount": money_str(amount)})
        new_total = total
        overlap = sorted(debited & credited)
        if overlap:
            ev.warnings.append({
                "code": "team_both_debited_and_credited",
                "message": f"team(s) {', '.join(overlap)} both give and receive funds in this transfer",
            })
    elif action_type == "addition":
        inc = _parse_amount(envelope_increase, line=None, field_name="envelope_increase", reasons=reasons)
        line_sum = ZERO
        for i, ln in enumerate(raw_lines):
            if ln.get("from_team") is not None:
                reasons.append(_reason("addition_line_has_source",
                                       "an addition allocates new money; it has no source team", line=i))
            dst = ln.get("to_team")
            ok = check_team(dst, line=i, field_name="to_team")
            if ok and dst in seen:
                reasons.append(_reason("duplicate_line", f"more than one line allocates new funds to {dst}", line=i))
                ok = False
            amount = _parse_amount(ln.get("amount"), line=i, field_name="amount", reasons=reasons)
            if not ok or amount is None:
                continue
            seen.add(dst)
            line_sum += amount
            after[dst] = after.get(dst, ZERO) + amount
            ev.lines.append({"from_team": None, "to_team": dst, "amount": money_str(amount)})
        if inc is not None:
            ev.envelope_increase = inc
            # Only meaningful when every line parsed; otherwise the line errors already explain it.
            if len(ev.lines) == len(raw_lines) and raw_lines and line_sum != inc:
                reasons.append(_reason(
                    "addition_lines_do_not_sum_to_increase",
                    f"lines allocate {money_str(line_sum)} but the envelope increase is {money_str(inc)}; "
                    "every added unit must be allocated exactly",
                    field_name="lines",
                ))
        new_total = total + (inc or ZERO)
    else:  # pragma: no cover - the schema discriminator prevents this
        reasons.append(_reason("unknown_action_type", f"unknown action type {action_type!r}"))
        new_total = total

    for team, amount in sorted(after.items()):
        if amount < ZERO:
            reasons.append(_reason(
                "negative_allocation_result",
                f"{team} would be left with {money_str(amount)} (has {money_str(allocations.get(team, ZERO))})",
                field_name=team,
            ))

    if not reasons:
        if sum(after.values(), ZERO) != new_total:  # pragma: no cover - arithmetic guard
            reasons.append(_reason("arithmetic_mismatch", "resulting allocations do not sum to the resulting envelope"))
        else:
            ev.after_allocations = after
            ev.after = budget_svc.figures(new_total, after)
    return ev


# ---- evidence and warnings ------------------------------------------------------------------


def check_evidence(session: Session, refs: list[EvidenceRef]) -> tuple[list[dict], list[dict], list[dict]]:
    """Returns (reasons, warnings, canonical refs). Cited ids must exist; superseded sources warn."""
    reasons: list[dict] = []
    warnings: list[dict] = []
    out: list[dict] = []
    seen: set[tuple] = set()
    for i, ref in enumerate(refs):
        key = (ref.kind, ref.id)
        if key in seen:
            continue
        seen.add(key)
        canonical = {"kind": ref.kind, "id": ref.id, "version": ref.version, "note": ref.note}
        if ref.kind == "document":
            doc = session.get(CorpusDocument, ref.id)
            if doc is None or (ref.version is not None and ref.version != doc.version):
                reasons.append(_reason("unknown_evidence", f"document {ref.id!r} (version {ref.version}) not found",
                                       line=i, field_name="evidence_refs"))
                continue
            canonical["version"] = doc.version
            if doc.superseded_by_document_id:
                warnings.append({"code": "cites_superseded_document",
                                 "message": f"{doc.doc_key} v{doc.version} has been superseded; "
                                            "check the newer document before relying on it"})
            if doc.plan_status == "cancelled":
                warnings.append({"code": "cites_cancelled_document",
                                 "message": f"{doc.doc_key} v{doc.version} is a cancelled plan, not current work"})
        elif ref.kind == "signal":
            sig = session.get(ContextSignal, ref.id)
            if sig is None:
                reasons.append(_reason("unknown_evidence", f"signal {ref.id!r} not found", line=i,
                                       field_name="evidence_refs"))
                continue
            if sig.status != "current":
                warnings.append({"code": "cites_non_current_signal",
                                 "message": f"signal {sig.id} is {sig.status}, not a current plan"})
        elif ref.kind == "forecast_snapshot":
            snap = session.get(ForecastSnapshot, ref.id)
            if snap is None:
                reasons.append(_reason("unknown_evidence", f"forecast snapshot {ref.id!r} not found", line=i,
                                       field_name="evidence_refs"))
                continue
            if snap.availability != "available":
                warnings.append({"code": "forecast_unavailable",
                                 "message": f"cited forecast snapshot is {snap.availability}"})
        # spend_summary refs name a period/summary view; there is no stored row to resolve.
        out.append(canonical)
    if not refs:
        warnings.append({"code": "no_evidence_cited", "message": "the proposal cites no evidence"})
    return reasons, warnings, out


def spend_warnings(session: Session, period_id: str, after: dict[str, Decimal]) -> list[dict]:
    spend = budget_svc.recorded_spend_by_team(session, period_id)
    out = []
    for team, amount in sorted(after.items()):
        s = spend.get(team, ZERO)
        if amount < s:
            out.append({"code": "allocation_below_recorded_spend", "team": team,
                        "message": f"{team} would be allocated {money_str(amount)} but has already recorded "
                                   f"{money_str(s)} of spend this period"})
    return out


# ---- create / rebase / revise ---------------------------------------------------------------


def _stale_base_error(env: BudgetEnvelope, base_version: int) -> DomainError:
    return DomainError(
        "stale_base_version", 409,
        f"proposal was drafted against budget version {base_version} but the current version is "
        f"{env.state_version}; re-read the budget and draft against the current state",
        {"base_version": base_version, "current_version": env.state_version,
         "current": budget_svc.current_figures(env)},
    )


def create_proposal(
    session: Session,
    body: AdditionCreate | TransferCreate,
    *,
    actor: Actor,
    clock: Clock,
    ids: IdFactory,
    extra_warnings: list[dict] | None = None,
    revises: Proposal | None = None,
    rebased_from: Proposal | None = None,
) -> Proposal:
    if actor.role not in DRAFTING_ROLES:
        raise DomainError("role_forbidden", 403, f"role {actor.role!r} may not draft proposals",
                          {"role": actor.role, "allowed_roles": list(DRAFTING_ROLES)})
    reasons: list[dict] = []

    if body.period is not None and session.get(PlanningPeriod, body.period) is None:
        reasons.append(_reason("period_mismatch", f"unknown planning period {body.period!r}", field_name="period"))
        raise validation_failed(reasons)
    period, env = budget_svc.resolve_envelope(session, body.period, clock)

    unit = body.unit if body.unit is not None else env.unit
    if unit != env.unit:
        reasons.append(_reason("currency_mismatch", f"proposal unit {unit!r} does not match budget unit {env.unit!r}",
                               field_name="unit"))
    if body.base_version > env.state_version:
        reasons.append(_reason("base_version_in_future",
                               f"base_version {body.base_version} is newer than the current version {env.state_version}",
                               field_name="base_version"))
    elif body.base_version < env.state_version:
        raise _stale_base_error(env, body.base_version)
    if body.base_version < 1:
        reasons.append(_reason("invalid_base_version", "base_version starts at 1", field_name="base_version"))
    rationale = (body.rationale or "").strip()
    if not rationale:
        reasons.append(_reason("rationale_required", "a proposal must explain why", field_name="rationale"))
    if body.agent_run_id is not None and session.get(AgentRun, body.agent_run_id) is None:
        reasons.append(_reason("unknown_agent_run", f"agent run {body.agent_run_id!r} not found",
                               field_name="agent_run_id"))

    ev = evaluate(
        session, action_type=body.action_type, envelope_increase=body.envelope_increase, lines=body.lines,
        total=env.total_amount, allocations=budget_svc.allocation_map(env),
    )
    reasons.extend(ev.reasons)
    ev_reasons, ev_warnings, evidence = check_evidence(session, body.evidence_refs)
    reasons.extend(ev_reasons)
    if reasons:
        raise validation_failed(reasons, base_version=env.state_version)

    warnings = list(extra_warnings or []) + ev.warnings + ev_warnings + spend_warnings(session, period.id, ev.after_allocations)
    now = clock.now()
    p = Proposal(
        id=ids.new_id("prop_"),
        period_id=period.id,
        unit=env.unit,
        action_type=body.action_type,
        base_version=env.state_version,
        envelope_increase=ev.envelope_increase if body.action_type == "addition" else ZERO,
        lines=ev.lines,
        before=ev.before,
        after=ev.after,
        status="pending_review",
        rationale=rationale,
        evidence_refs=evidence,
        created_by_actor=actor.id,
        created_by_role=actor.role,
        origin="droid_run" if actor.role == "droid_agent" else "finance_manual",
        agent_run_id=body.agent_run_id,
        revises_proposal_id=revises.id if revises else None,
        rebased_from_proposal_id=rebased_from.id if rebased_from else None,
        warnings=warnings,
        created_at=now,
        updated_at=now,
    )
    session.add(p)
    session.flush()  # acquire the SQLite write lock before checking input dependencies
    from app.services.forecast_freshness import stale_forecast_refs
    stale = stale_forecast_refs(session, evidence, clock.now())
    if stale:
        raise validation_failed([_reason("stale_forecast_evidence",
            "New forecast evidence arrived; publish a new forecast before drafting against it.",
            field_name="evidence_refs")], forecast_snapshot_ids=stale)
    return p


def claim_status(session: Session, p: Proposal, new_status: str, *, from_statuses: tuple[str, ...],
                 now: Any) -> bool:
    """Compare-and-set a proposal's status inside the current transaction.

    `UPDATE proposals SET status=:new WHERE id=:id AND status IN (:from)`; False (nothing written)
    when a concurrent request already moved the proposal on. Every status transition that retires
    or settles a proposal goes through this so two writers can never both win.
    """
    result = session.execute(
        update(Proposal)
        .where(Proposal.id == p.id, Proposal.status.in_(from_statuses))
        .values(status=new_status, updated_at=now)
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        return False
    session.refresh(p)
    return True


def _moved_error(session: Session, p: Proposal) -> DomainError:
    session.refresh(p)
    return DomainError("proposal_not_pending", 409,
                       f"proposal is {p.status}; it changed while this request was in flight",
                       {"status": p.status})


def get_proposal(session: Session, proposal_id: str) -> Proposal:
    p = session.get(Proposal, proposal_id)
    if p is None:
        raise DomainError("proposal_not_found", 404, f"proposal {proposal_id!r} not found")
    return p


def list_proposals(session: Session, status: str | None = None) -> list[Proposal]:
    q = select(Proposal).order_by(Proposal.created_at, Proposal.id)
    if status:
        q = q.where(Proposal.status == status)
    return list(session.scalars(q))


def _body_from(p: Proposal, *, rationale: str) -> AdditionCreate | TransferCreate:
    common = {
        "base_version": 0,  # replaced by caller
        "rationale": rationale,
        "evidence_refs": [EvidenceRef(**{k: v for k, v in r.items() if v is not None}) for r in p.evidence_refs],
        "period": p.period_id,
        "unit": p.unit,
        "agent_run_id": p.agent_run_id,
    }
    if p.action_type == "addition":
        return AdditionCreate(action_type="addition", envelope_increase=money_str(p.envelope_increase),
                              lines=[{"to_team": ln["to_team"], "amount": ln["amount"]} for ln in p.lines], **common)
    return TransferCreate(action_type="transfer",
                          lines=[{"from_team": ln["from_team"], "to_team": ln["to_team"], "amount": ln["amount"]}
                                 for ln in p.lines], **common)


def rebase(session: Session, proposal_id: str, body: RebaseIn, *, actor: Actor, clock: Clock, ids: IdFactory) -> Proposal:
    """Re-draft a stale proposal's intent against the current budget as a NEW pending proposal.

    The rebasing actor becomes the requester of the new draft (they own what it now says), and the
    new draft needs its own fresh review. If the intent no longer fits the current state (e.g. the
    source team no longer has the funds) this fails with the usual validation reasons.
    """
    p = get_proposal(session, proposal_id)
    env = budget_svc.require_envelope(session, p.period_id)
    decided = session.scalar(select(Decision.id).where(Decision.proposal_id == p.id))
    if decided is not None:
        # Defensive: a decided proposal is never stale, whatever its status column says.
        raise DomainError("proposal_not_stale", 409, f"proposal already has decision {decided}; it cannot be rebased",
                          {"status": p.status, "decision_id": decided})
    outdated_pending = p.status == "pending_review" and p.base_version < env.state_version
    if p.status != "stale" and not outdated_pending:
        raise DomainError("proposal_not_stale", 409,
                          f"proposal is {p.status} at base version {p.base_version} (current {env.state_version}); "
                          "only stale proposals can be rebased",
                          {"status": p.status, "base_version": p.base_version, "current_version": env.state_version})
    draft = _body_from(p, rationale=(body.rationale or p.rationale))
    draft.base_version = env.state_version
    new = create_proposal(session, draft, actor=actor, clock=clock, ids=ids, rebased_from=p,
                          extra_warnings=[w for w in p.warnings if w.get("code") == "forecast_unavailable"])
    if not claim_status(session, p, "stale", from_statuses=("pending_review", "stale"), now=clock.now()):
        raise _moved_error(session, p)
    return new


def revise(session: Session, proposal_id: str, body: AdditionCreate | TransferCreate, *, actor: Actor,
           clock: Clock, ids: IdFactory) -> Proposal:
    """Finance replaces a pending (or stale) proposal with changed lines. Original -> `revised`."""
    p = get_proposal(session, proposal_id)
    if p.status not in REVISABLE_STATUSES:
        raise DomainError("proposal_not_pending", 409, f"proposal is {p.status}; only pending or stale proposals "
                          "can be revised", {"status": p.status})
    new = create_proposal(session, body, actor=actor, clock=clock, ids=ids, revises=p)
    if not claim_status(session, p, "revised", from_statuses=REVISABLE_STATUSES, now=clock.now()):
        raise _moved_error(session, p)
    return new


def link_revision(session: Session, original_id: str, new_id: str, *, actor: Actor, clock: Clock) -> bool:
    """Finance asked (in chat) for `original_id` to be revised and a Droid run drafted `new_id` from that
    request: the original becomes `revised` and the new draft records `revises_proposal_id`. Finance roles
    only, like `revise`. False (nothing written) when the new draft is not a fresh pending proposal or the
    original is no longer pending or stale."""
    if actor.role not in FINANCE_ROLES:
        raise DomainError("role_forbidden", 403, f"role {actor.role!r} may not revise proposals",
                          {"role": actor.role, "allowed_roles": list(FINANCE_ROLES)})
    p = get_proposal(session, original_id)
    new = get_proposal(session, new_id)
    if (new.id == p.id or new.status != "pending_review" or new.revises_proposal_id
            or new.rebased_from_proposal_id):
        return False
    if not claim_status(session, p, "revised", from_statuses=REVISABLE_STATUSES, now=clock.now()):
        return False
    new.revises_proposal_id = p.id
    new.updated_at = clock.now()
    session.flush()
    return True


def lineage(session: Session, p: Proposal) -> list[Proposal]:
    """The proposal and every proposal it was revised or rebased from (oldest last)."""
    chain = [p]
    seen = {p.id}
    cur = p
    while True:
        parent_id = cur.revises_proposal_id or cur.rebased_from_proposal_id
        if not parent_id or parent_id in seen:
            return chain
        cur = session.get(Proposal, parent_id)
        if cur is None:  # pragma: no cover - FK guarantees presence
            return chain
        seen.add(cur.id)
        chain.append(cur)


# ---- output ---------------------------------------------------------------------------------


def _figures_out(data: dict) -> dict:
    total, allocs = budget_svc.figures_to_decimal(data)
    return {"total": total, "allocations": allocs}


def deltas(before: dict, after: dict) -> dict[str, Decimal]:
    _, b = budget_svc.figures_to_decimal(before)
    _, a = budget_svc.figures_to_decimal(after)
    return {t: a.get(t, ZERO) - b.get(t, ZERO) for t in sorted(set(a) | set(b))}


def lines_out(p: Proposal) -> list[dict]:
    return [{"from_team": ln.get("from_team"), "to_team": ln["to_team"], "amount": Decimal(ln["amount"])}
            for ln in p.lines]


def proposal_out(session: Session, p: Proposal) -> dict:
    env = budget_svc.get_envelope(session, p.period_id)
    current_version = env.state_version if env else p.base_version
    replaced_by = session.scalar(
        select(Proposal.id).where(
            or_(Proposal.revises_proposal_id == p.id, Proposal.rebased_from_proposal_id == p.id)
        ).order_by(Proposal.created_at.desc(), Proposal.id.desc())
    )
    decision_id = session.scalar(select(Decision.id).where(Decision.proposal_id == p.id))
    events = session.scalars(
        select(DecisionEvent).where(DecisionEvent.proposal_id == p.id).order_by(DecisionEvent.at, DecisionEvent.id)
    ).all()
    return {
        "id": p.id,
        "period": p.period_id,
        "unit": p.unit,
        "action_type": p.action_type,
        "status": p.status,
        "base_version": p.base_version,
        "current_version": current_version,
        "is_stale": p.status == "stale" or (p.status == "pending_review" and p.base_version != current_version),
        "envelope_increase": p.envelope_increase,
        "lines": lines_out(p),
        "before": _figures_out(p.before),
        "after": _figures_out(p.after),
        "deltas": deltas(p.before, p.after),
        "rationale": p.rationale,
        "evidence_refs": p.evidence_refs,
        "warnings": p.warnings,
        "requester": {"id": p.created_by_actor, "role": p.created_by_role},
        "origin": p.origin,
        "agent_run_id": p.agent_run_id,
        "revises_proposal_id": p.revises_proposal_id,
        "rebased_from_proposal_id": p.rebased_from_proposal_id,
        "replaced_by_proposal_id": replaced_by,
        "decision_id": decision_id,
        "blocked_attempts": [
            {"id": e.id, "event": e.event, "actor_id": e.actor_id, "details": e.details, "at": e.at} for e in events
        ],
        "created_at": p.created_at,
        "updated_at": p.updated_at,
    }
