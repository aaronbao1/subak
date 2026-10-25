"""Frontend compat routes: the 15 paths the Next.js HttpDataClient calls, under `/compat/api`.

Point the frontend at `NEXT_PUBLIC_API_URL=http://localhost:8787/compat`; its `/api/company` then lands
on `/compat/api/company`. Nothing here collides with `/api/*`, and none of it is in `openapi.json`.

- Reads call the services directly and never write: `/forecasts` creates no snapshot and `/context`
  starts no run.
- Writes go only through `agent_runs.start_run` (chat, as the demo analyst) and `decisions.decide`
  (apply / reject, as the demo approver), so every authority rule (approver role, no self-approval,
  stale version, exactly-once) is the real service's. Droid still only drafts.
- Errors are `{"error": "<plain English>", "code": "<backend code>"}` (see `errors.py`).
- The frontend loads 10 GETs with `Promise.all`, so every list route answers `200 []` on an unseeded or
  empty DB (no period, no envelope, no rows). Only `/company` refuses (503 `not_seeded`): a Company cannot
  be built without its current period.
- Identity: the frontend sends none. Compat uses two configured demo actors unless the request carries
  `X-Actor-Id` + `X-Actor-Role`, which then win (docs/frontend-alignment.md G9).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Body, Depends, Header, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.api import routes_meta
from app.api.deps import get_clock, get_forecast_provider, get_ids
from app.compat import cache, errors, intent, mappers, spending_index, threads
from app.compat import schemas as S
# Stored as the decision rationale when the dashboard sends no note; mappers.decision never returns them as `note`.
from app.compat.mappers import APPROVE_NOTE, DISMISS_NOTE, REJECT_NOTE
from app.core.actors import Actor, get_actor
from app.core.clock import Clock, IdFactory
from app.core.errors import DomainError
from app.db.models import (AssistantMessage, AssistantRequest, BudgetRequest, CorpusDocument, ImportBatch,
                           PlanningPeriod, Proposal, Team, UsageRecord)
from app.db.session import get_session
from app.schemas.agent import AgentRunCreate
from app.schemas.decisions import DecisionCreate
from app.services import agent_runs as run_svc
from app.services import budget as budget_svc
from app.services import company as company_svc
from app.services import corpus as corpus_svc
from app.services import people as people_svc
from app.services import coverage as coverage_svc
from app.services import decisions as decision_svc
from app.services import forecasts as forecast_svc
from app.services import proposals as proposal_svc
from app.services import signals as signal_svc
from app.services import spending as spending_svc

PREFIX = "/compat/api"
ANALYST = Actor(id="dashboard-analyst", role="finance_analyst")
APPROVER = Actor(id="dashboard-approver", role="finance_approver")
MAX_MESSAGE = 4000
MAX_THREAD_ID = 200


class CompatRoute(APIRoute):
    """Renders DomainError / request validation errors on compat paths in the frontend's envelope. The
    app-wide handlers (used by `/api/*`) are untouched."""

    def get_route_handler(self) -> Callable:
        original = super().get_route_handler()

        async def handler(request: Request) -> Response:
            try:
                return await original(request)
            except DomainError as exc:
                return errors.from_domain(exc)
            except RequestValidationError as exc:
                details = {"errors": [{"msg": f"{'.'.join(map(str, e.get('loc', ())))}: {e.get('msg', '')}"}
                                      for e in exc.errors()]}
                return errors.error_response(422, "validation_failed", "request validation failed", details)

        return handler


router = APIRouter(prefix=PREFIX, tags=["compat"], route_class=CompatRoute)
JSON_OPTS: dict[str, Any] = {"response_model_exclude_none": True}


def _actor(default: Actor) -> Callable[..., Actor]:
    def _dep(x_actor_id: str | None = Header(default=None), x_actor_role: str | None = Header(default=None)) -> Actor:
        if not (x_actor_id or "").strip() and not (x_actor_role or "").strip():
            return default
        return get_actor(x_actor_id, x_actor_role)

    return _dep


# ---- shared lookups ----------------------------------------------------------------------------


def _period(session: Session, clock: Clock) -> PlanningPeriod:
    return coverage_svc.resolve_period(session, None, clock.now())


def _period_or_none(session: Session, clock: Clock) -> PlanningPeriod | None:
    """The current period, or None on an unseeded DB (list routes then answer `200 []`)."""
    try:
        return _period(session, clock)
    except DomainError:
        return None


def _people_by_team(session: Session, request: Request) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for p in _people_rows(request, session):
        out.setdefault(p["teamId"], []).append(p["id"])
    return out


def _active_teams(session: Session) -> list[Team]:
    return [t for t in session.scalars(select(Team).order_by(Team.id)) if t.active]


def _has_unattributed(session: Session, period_id: str) -> bool:
    return session.scalar(select(UsageRecord.id).where(UsageRecord.period_id == period_id,
                                                       UsageRecord.team_id.is_(None)).limit(1)) is not None


def _period_row(session: Session, period_id: str) -> PlanningPeriod:
    p = session.get(PlanningPeriod, period_id)
    if p is None:
        raise DomainError("unknown_period", 404, f"unknown period {period_id!r}")
    return p


def _snapshot_forecasts(session: Session, refs: list[dict]) -> list[dict]:
    """Forecast[] for each forecast snapshot an evidence list cites: exactly what was reviewed."""
    out: list[dict] = []
    for ref in refs or []:
        if ref.get("kind") != "forecast_snapshot":
            continue
        try:
            snap = forecast_svc.get_snapshot(session, ref["id"])
        except DomainError:
            continue
        result = forecast_svc.snapshot_out(snap)["forecast"]
        team_ids = [p.team for p in result.projections] + list(result.missing_teams)
        # Team-level items only: proposal-review finds the reviewed projection by teamId, so a person
        # item must never shadow its team (frontend-integration-design §1.1).
        out.extend(f for f in mappers.forecasts(result, period_row=_period_row(session, result.target_period),
                                                team_ids=sorted(set(team_ids)), now=snap.fetched_at)
                   if "personId" not in f)
    return out


def _evidence_citations(session: Session, refs: list[dict]) -> list[dict]:
    cites: list[dict] = []
    for ref in refs or []:
        if ref.get("kind") == "signal":
            try:
                sig = signal_svc.signal_out(session, signal_svc.get_signal(session, ref["id"]))
            except DomainError:
                continue
            cites += [mappers.source_ref(c, session.get(CorpusDocument, c["document_id"])) for c in sig["citations"]]
        elif ref.get("kind") == "document":
            doc = session.get(CorpusDocument, ref["id"])
            if doc is not None:
                cites.append(mappers.document_ref(doc))
    return mappers.dedupe_refs(cites)


def _proposal(session: Session, p: Proposal) -> dict:
    out = proposal_svc.proposal_out(session, p)
    return {**mappers.proposal(out, period_row=_period_row(session, p.period_id),
                            citations=_evidence_citations(session, out["evidence_refs"]),
                            forecasts_reviewed=_snapshot_forecasts(session, out["evidence_refs"])),
            "version": p.base_version}


def _decision(session: Session, d: Any) -> dict:
    out = decision_svc.decision_out(session, d)
    p = proposal_svc.proposal_out(session, proposal_svc.get_proposal(session, d.proposal_id))
    return mappers.decision(out, p, forecasts_reviewed=_snapshot_forecasts(session, out["proposal_evidence_refs"]))


# ---- reads -------------------------------------------------------------------------------------


@router.get("/company", response_model=S.Company, **JSON_OPTS)
def get_company(request: Request, session: Session = Depends(get_session), clock: Clock = Depends(get_clock),
                provider=Depends(get_forecast_provider)):
    meta = routes_meta.meta(request, session, clock, provider)
    if meta["period"] is None:
        raise DomainError("not_seeded", 503, "the database is not seeded yet")
    return mappers.company(meta, company_id=meta["company"]["id"], name=meta["company"]["name"])


@router.get("/teams", response_model=list[S.Team], **JSON_OPTS)
def get_teams(session: Session = Depends(get_session), clock: Clock = Depends(get_clock)):
    period = _period_or_none(session, clock)
    unattributed = period is not None and _has_unattributed(session, period.id)  # no period yet: plain list
    return mappers.teams(_active_teams(session), include_unattributed=unattributed,
                         leads=mappers.team_leads(people_svc.list_people(session)))


@router.get("/people", response_model=list[S.Person], **JSON_OPTS)
def get_people(request: Request, session: Session = Depends(get_session)):
    # The forecast fixture directory has its own publication/source identities and is already cheap.
    if request.app.state.settings.forecast_demo:
        return _people_rows(request, session)
    return cache.cached_json(request, ("people", cache.data_stamp(session)), list[S.Person],
                             lambda: _people_rows(request, session))


def _people_rows(request: Request, session: Session) -> list[dict]:
    active = {t.id for t in _active_teams(session)}
    return [mappers.person(p) for p in people_svc.list_people(session)
            if request.app.state.settings.forecast_demo or p.team_id in active]


@router.get("/spending", response_model=list[S.SpendingRecord], **JSON_OPTS)
def get_spending(
    request: Request,
    team_id: str | None = Query(default=None, alias="teamId"),
    date_from: date | None = Query(default=None, alias="from"),
    date_to: date | None = Query(default=None, alias="to"),
    session: Session = Depends(get_session),
    clock: Clock = Depends(get_clock),
):
    period = _period_or_none(session, clock)
    if period is None:
        return []
    if request.app.state.settings.forecast_demo:
        from app.forecasting.fixtures import northstar_spending_records
        try:
            rows = northstar_spending_records(request.app.state.forecast_service.current_snapshot())
        except ValueError as exc:
            raise DomainError("pricing_unavailable", 422, str(exc)) from exc
        return [r for r in rows if (not team_id or r['teamId'] == team_id)
                and (not date_from or r['date'] >= date_from.isoformat())
                and (not date_to or r['date'] <= date_to.isoformat())]
    return spending_index.index_for(request.app.state).response(
        request, session, period.id, team_id or None,
        date_from.isoformat() if date_from else None, date_to.isoformat() if date_to else None)


@router.get("/budgets", response_model=list[S.Budget], **JSON_OPTS)
def get_budgets(session: Session = Depends(get_session), clock: Clock = Depends(get_clock)):
    if _period_or_none(session, clock) is None:
        return []
    try:
        period, env = budget_svc.resolve_envelope(session, None, clock)
    except DomainError as exc:
        if exc.code == "no_budget":
            return []
        raise
    allocations = budget_svc.allocation_map(env)
    return mappers.budgets({"period": period, "unit": env.unit, "state_version": env.state_version,
                           "allocations": [{"team": team, "amount": amount}
                                           for team, amount in sorted(allocations.items())]})


@router.get("/forecasts", response_model=list[S.Forecast], **JSON_OPTS)
def get_forecasts(request: Request, session: Session = Depends(get_session), clock: Clock = Depends(get_clock),
                  provider=Depends(get_forecast_provider)):
    period = _period_or_none(session, clock)
    if period is None:
        return []
    result = forecast_svc.forecast_for_period(session, provider, period, clock=clock)  # read only: no snapshot
    return mappers.forecasts(result, period_row=period, team_ids=forecast_svc.active_team_ids(session),
                             now=clock.now(), people=_people_by_team(session, request))


@router.get("/context", response_model=list[S.ContextItem], **JSON_OPTS)
def get_context(team_id: str | None = Query(default=None, alias="teamId"), session: Session = Depends(get_session)):
    """A `teamId` filter returns that team's signals plus every company-scope signal (they apply to all teams)."""
    team_ids = [t.id for t in _active_teams(session)]
    items = []
    for sig in signal_svc.list_signals(session, team=team_id or None, include_company=True):
        out = signal_svc.signal_out(session, sig)
        docs = {c["document_id"]: session.get(CorpusDocument, c["document_id"]) for c in out["citations"]}
        items.append(mappers.context_item(out, docs, company_team_ids=team_ids))
    return items


@router.get("/documents", response_model=list[S.CompanyDocument], **JSON_OPTS)
def get_documents(session: Session = Depends(get_session)):
    docs = [d for d, _, _ in corpus_svc.search_documents(session, include_superseded=True)]
    docs.sort(key=lambda d: (d.authored_at, d.id))
    return [mappers.document(d) for d in docs]


# DataClient.getDocument / getProposal resolve to `T | undefined`, and HttpDataClient throws on any non-2xx,
# so an unknown id answers 200 `null` (the frontend's "not found" branch), not 404.
@router.get("/documents/{document_id}", response_model=S.CompanyDocument | None, **JSON_OPTS)
def get_document(document_id: str, session: Session = Depends(get_session)):
    doc = session.get(CorpusDocument, document_id)
    if doc is not None:
        return mappers.document(doc)
    request = session.get(BudgetRequest, document_id)
    if request is None:
        return None
    period = session.get(PlanningPeriod, request.period_id)
    amount_text = (f"Additional allocation requested: {request.unit} {request.requested_amount:.2f}."
                   if request.requested_amount is not None else
                   "Context update: no additional allocation amount specified.")
    details = [amount_text]
    if period is not None:
        details.append(f"Planning period: {period.starts_on.isoformat()} through "
                       f"{period.ends_on.isoformat()} (inclusive).")
    if request.source_ref:
        details.append(f"Source: {request.source_ref}")
    details.append("This submission is planning evidence; it is not included in the forecast "
                   "and does not approve or change any allocation.")
    return {"id": request.id, "title": request.title, "kind": "correspondence",
            "date": request.created_at.date().isoformat(), "teamIds": [request.team_id],
            "origin": "Submitted budget request", "integration": "document",
            "body": "\n\n".join(["\n".join(details), request.narrative])}


@router.get("/proposals", response_model=list[S.AllocationProposal], **JSON_OPTS)
def get_proposals(session: Session = Depends(get_session)):
    return [_proposal(session, p) for p in reversed(proposal_svc.list_proposals(session))]


@router.get("/proposals/{proposal_id}", response_model=S.AllocationProposal | None, **JSON_OPTS)
def get_proposal(proposal_id: str, session: Session = Depends(get_session)):
    p = session.get(Proposal, proposal_id)
    return _proposal(session, p) if p is not None else None


@router.get("/decisions", response_model=list[S.Decision], **JSON_OPTS)
def get_decisions(session: Session = Depends(get_session)):
    return [_decision(session, d) for d in reversed(decision_svc.list_decisions(session))]


@router.get("/threads/{thread_id}", response_model=list[S.AssistantMessage], **JSON_OPTS)
def get_thread(thread_id: str, session: Session = Depends(get_session), actor: Actor = Depends(_actor(ANALYST))):
    return threads.thread_out(session, thread_id[:MAX_THREAD_ID], company_id=company_svc.resolve(session)["id"], actor_id=actor.id)


@router.get("/threads/{thread_id}/messages/{client_message_id}", **JSON_OPTS)
def reconcile_message(thread_id: str, client_message_id: str, request: Request, session: Session = Depends(get_session),
                      clock: Clock = Depends(get_clock), ids: IdFactory = Depends(get_ids),
                      actor: Actor = Depends(_actor(ANALYST))):
    receipt = threads.accepted_request(session, company_id=company_svc.resolve(session)["id"], actor_id=actor.id,
        thread_id=thread_id[:MAX_THREAD_ID], client_message_id=client_message_id)
    if receipt is None:
        raise DomainError("message_not_found", 404, "This message has not been accepted.")
    messages = _reconcile_request(session, receipt, actor=actor, clock=clock, ids=ids, app_state=request.app.state)
    return {"status": "completed", "messages": messages} if messages else {"status": "pending"}


# ---- writes ------------------------------------------------------------------------------------


def _intent_context(session: Session, request: Request, clock: Clock) -> dict:
    teams = [(t.id, t.name) for t in _active_teams(session)]
    names = dict(teams)
    gaps: dict[str, Decimal] = {}
    open_: list[dict] = []
    try:
        period, env = budget_svc.resolve_envelope(session, None, clock)
        alloc = budget_svc.allocation_map(env)
        result = forecast_svc.forecast_for_period(session, request.app.state.forecast_provider, period, clock=clock)
        recorded = budget_svc.recorded_spend_by_team(session, period.id)
        for pr in result.projections:
            projected = pr.amount + recorded.get(pr.team, Decimal("0")) if result.basis == "remaining" else pr.amount
            if pr.team in alloc:
                gaps[pr.team] = projected - alloc[pr.team]
        for p in reversed(proposal_svc.list_proposals(session)):
            if p.status in proposal_svc.REVISABLE_STATUSES:
                open_.append(_open_proposal(p, env.state_version, names))
    except DomainError:
        pass  # unseeded: the parser asks instead of guessing
    return {"teams": teams, "gaps": gaps, "open_proposals": open_}


def _open_proposal(p: Proposal, version: int, names: dict[str, str]) -> dict:
    """What the chat parser needs to revise a proposal: its mode, the team it favours most, a short label."""
    gains = {t: d for t, d in proposal_svc.deltas(p.before, p.after).items() if d > 0}
    favoured = max(sorted(gains), key=lambda t: gains[t]) if gains else None
    stale = p.status == "stale" or p.base_version != version
    amount = p.envelope_increase if p.action_type == "addition" else sum(gains.values(), Decimal("0"))
    what = "add" if p.action_type == "addition" else "move"
    label = (f"{'stale' if stale else 'awaiting review'}, {what} ${amount:,.2f}"
             + (f" toward {names.get(favoured, favoured)}" if favoured else ""))
    losses = {t: d for t, d in proposal_svc.deltas(p.before, p.after).items() if d < 0}
    source = next(iter(losses)) if len(losses) == 1 else None
    return {"id": p.id, "stale": stale, "mode": p.action_type, "prioritize": favoured, "label": label,
            "amount": str(amount), "source_team": source, "base_version": p.base_version}


@router.post("/threads/{thread_id}/messages", response_model=list[S.AssistantMessage], **JSON_OPTS)
def post_message(
    thread_id: str,
    request: Request,
    body: S.MessageIn,
    session: Session = Depends(get_session),
    clock: Clock = Depends(get_clock),
    ids: IdFactory = Depends(get_ids),
    actor: Actor = Depends(_actor(ANALYST)),
):
    content = body.content.strip()
    if not content:
        raise DomainError("validation_failed", 422, "message is empty",
                          {"reasons": [{"message": "the message is empty"}]})
    if len(content) > MAX_MESSAGE:
        raise DomainError("validation_failed", 422, "message too long",
                          {"reasons": [{"message": f"messages are limited to {MAX_MESSAGE} characters"}]})
    thread_id = thread_id[:MAX_THREAD_ID]
    payload = body.model_dump(exclude_none=True, exclude={"client_message_id"})
    payload["content"] = content
    client_id = body.client_message_id or ids.new_id("client_")
    existing = threads.accepted_request(session, company_id=company_svc.resolve(session)["id"], actor_id=actor.id,
        thread_id=thread_id, client_message_id=client_id)
    interpretation, next_context = {}, {}
    if existing is None:
        # Prepare entirely read-only before accepting. A parser/provider failure leaves the identity
        # unclaimed, so reconnect can safely resend rather than getting stuck in a pending receipt.
        context = (body.conversation_context.model_dump(exclude_none=True) if body.conversation_context is not None
                   else threads.latest_context(session, company_id=company_svc.resolve(session)["id"], actor_id=actor.id, thread_id=thread_id))
        parsed = intent.parse(content, **_intent_context(session, request, clock), conversation_context=context)
        # A pin constrains factual answers; it must not swallow a later allocation instruction.
        if body.forecast_context and parsed.run and parsed.run["task_type"] == "answer_question":
            parsed.run.setdefault("params", {})["forecast_context"] = body.forecast_context.model_dump(exclude_none=True)
        interpretation = {"read_as": parsed.read_as, "ask": parsed.ask, "revises": parsed.revises, "run": parsed.run}
        next_context = {
            **{key: context[key] for key in ("scope_type", "scope_id", "period", "forecast_run_id") if key in context},
            **parsed.conversation_context,
        }
    receipt, _ = threads.accept_request(session, company_id=company_svc.resolve(session)["id"], actor_id=actor.id,
        thread_id=thread_id, client_message_id=client_id, payload=payload, clock=clock, ids=ids,
        interpretation=interpretation, conversation_context=next_context)
    messages = _reconcile_request(session, receipt, actor=actor, clock=clock, ids=ids, app_state=request.app.state)
    if messages is not None:
        return messages
    raise DomainError("message_pending", 409,
                      "This message was accepted and is still being processed. Check its receipt before retrying.")


def _start_request(session: Session, receipt: AssistantRequest, *, app_state: Any, actor: Actor,
                   clock: Clock, ids: IdFactory) -> list[dict] | None:
    receipt_id = receipt.id
    parsed = receipt.interpretation
    session.commit()

    def attach_run(run_session: Session, run_id: str) -> None:
        # The run insert already holds SQLite's writer lock. Persist its association atomically;
        # competing resumes roll back their candidate run before any tools execute.
        accepted = run_session.get(AssistantRequest, receipt_id)
        if accepted.status == "completed" or accepted.agent_run_id:
            raise DomainError("message_pending", 409, "This accepted message already has an execution.")
        accepted.agent_run_id = run_id
        run_session.flush()

    try:
        run_svc.start_run(app_state, AgentRunCreate(**parsed["run"], wait=True), actor=actor,
                          on_created_in_session=attach_run)
    except DomainError as exc:
        session.expire_all()
        session.refresh(receipt)
        if exc.code != "message_pending":
            text = (f"**Read as:** {parsed['read_as']}.\n\n{errors.plain_message(exc.code, exc.message, exc.details)}"
                    + ("" if exc.code == "runner_unavailable" else " Nothing was changed."))
            if exc.code == "runner_unavailable":
                text += f"\n\n_Detail: {exc.message}_"
            return _complete_request(session, receipt, actor=actor, clock=clock, ids=ids, text=text)
    return _reconcile_request(session, receipt, actor=actor, clock=clock, ids=ids, app_state=app_state)


def _reconcile_request(session: Session, receipt: AssistantRequest, *, actor: Actor, clock: Clock,
                       ids: IdFactory, app_state: Any) -> list[dict] | None:
    session.refresh(receipt)
    if receipt.status == "completed":
        return receipt.response
    if receipt.interpretation.get("ask") is not None:
        return _complete_request(session, receipt, actor=actor, clock=clock, ids=ids,
            text=f"**Read as:** {receipt.interpretation['read_as']}.\n\n{receipt.interpretation['ask']}")
    if not receipt.agent_run_id:
        return _start_request(session, receipt, app_state=app_state, actor=actor, clock=clock, ids=ids)
    run = run_svc.get_run(session, receipt.agent_run_id)
    session.refresh(run)
    if run.status == "running":
        return None
    return _complete_request(session, receipt, actor=actor, clock=clock, ids=ids)


def _complete_request(session: Session, receipt: AssistantRequest, *, actor: Actor, clock: Clock,
                      ids: IdFactory, text: str | None = None) -> list[dict]:
    # Serialize completion across retries/processes. The lock also protects the thread sequence and
    # revision linkage. A failed response can be reconstructed from the already persisted run.
    session.execute(update(AssistantRequest).where(AssistantRequest.id == receipt.id)
                    .values(status=AssistantRequest.status))
    session.refresh(receipt)
    if receipt.status == "completed":
        session.commit()
        return receipt.response
    proposal_id, citations, calls = None, [], []
    if text is None:
        run = run_svc.run_out(session, run_svc.get_run(session, receipt.agent_run_id))
        proposal_id = run["proposals"][0]["id"] if run["proposals"] else None
        revised_note = _link_revision(session, receipt.interpretation.get("revises"), proposal_id,
                                      actor=actor, clock=clock)
        proposal = (proposal_svc.proposal_out(session, proposal_svc.get_proposal(session, proposal_id))
                    if proposal_id else None)
        text = threads.reply_text(receipt.interpretation["read_as"], run) + revised_note
        citations, calls = threads.citations(session, run, proposal), threads.tool_calls(run)
        if proposal_id and receipt.conversation_context.get("selected_proposal_id"):
            proposal_row = proposal_svc.get_proposal(session, proposal_id)
            receipt.conversation_context = {**receipt.conversation_context,
                "selected_proposal_id": proposal_id, "selected_proposal_version": proposal_row.base_version}
    user = session.get(AssistantMessage, receipt.user_message_id)
    reply = threads.add_message(session, receipt.thread_id, "assistant", text, clock=clock, ids=ids,
        agent_run_id=receipt.agent_run_id, proposal_id=proposal_id, citations=citations, tool_calls=calls)
    receipt.reply_message_id = reply.id
    receipt.status = "completed"
    receipt.response = [threads.message_out(user, receipt), threads.message_out(reply, receipt)]
    session.commit()
    return receipt.response


def _link_revision(session: Session, original_id: str | None, new_id: str | None, *, actor: Actor,
                   clock: Clock) -> str:
    """A chat revise: finance asked for `original_id` to be revised and the run drafted `new_id`. The original
    becomes `revised` and the draft records what it replaces. Returns a line for the reply ("" when no link)."""
    if not original_id or not new_id:
        return ""
    if new_id == original_id:
        return "\n\n_The requested changes match the existing draft, which stays open for review._"
    try:
        with session.begin_nested():
            linked = proposal_svc.link_revision(session, original_id, new_id, actor=actor, clock=clock)
    except DomainError:
        return "\n\n_The new draft is ready, but the earlier draft could not be replaced. Review both before applying a change._"
    if not linked:
        return "\n\n_The new draft is ready, but the earlier draft had already changed and was not replaced._"
    return "\n\n_This draft replaces the earlier version._"


def _guard_settled(p: Proposal) -> None:
    if p.status == "applied":
        raise DomainError("already_applied", 409, "proposal already applied", {"status": p.status})
    if p.status == "rejected":
        raise DomainError("already_rejected", 409, "proposal already rejected", {"status": p.status})


@router.post("/proposals/{proposal_id}/apply", response_model=S.Decision, **JSON_OPTS)
def apply_proposal(
    proposal_id: str,
    body: S.ApplyIn | None = Body(default=None),
    session: Session = Depends(get_session),
    clock: Clock = Depends(get_clock),
    ids: IdFactory = Depends(get_ids),
    actor: Actor = Depends(_actor(APPROVER)),
):
    p = proposal_svc.get_proposal(session, proposal_id)
    _guard_settled(p)
    note = ((body.note if body else None) or "").strip() or APPROVE_NOTE
    decision, replayed = decision_svc.decide(
        session, proposal_id, DecisionCreate(outcome="approve", rationale=note), actor=actor,
        idempotency_key=f"compat-approve-{proposal_id}", clock=clock, ids=ids)
    if replayed:  # a retried click: it was applied once; the frontend expects a second apply to fail
        raise DomainError("already_applied", 409, "proposal already applied", {"decision_id": decision.id})
    return _decision(session, decision)


@router.post("/proposals/{proposal_id}/reject", response_model=S.AllocationProposal, **JSON_OPTS)
def reject_proposal(
    proposal_id: str,
    session: Session = Depends(get_session),
    clock: Clock = Depends(get_clock),
    ids: IdFactory = Depends(get_ids),
    actor: Actor = Depends(_actor(APPROVER)),
):
    """The dashboard's Reject and Dismiss. A stale proposal (status `stale`, or still pending on an outdated
    budget version) is retired with DISMISS_NOTE; the decision is `rejected` and allocations are untouched.
    The backend never stores `failed` (proposals are validated when drafted), so there is no failed case."""
    p = proposal_svc.get_proposal(session, proposal_id)
    _guard_settled(p)
    stale = proposal_svc.proposal_out(session, p)["is_stale"]
    decision_svc.decide(session, proposal_id,
                        DecisionCreate(outcome="reject", rationale=DISMISS_NOTE if stale else REJECT_NOTE),
                        actor=actor, idempotency_key=f"compat-reject-{proposal_id}", clock=clock, ids=ids)
    session.expire_all()
    return _proposal(session, proposal_svc.get_proposal(session, proposal_id))


@router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"], include_in_schema=False)
def unknown(path: str):
    raise DomainError("not_found", 404, f"no compat route /api/{path}")
