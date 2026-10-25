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
from sqlalchemy import func, select
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
from app.db.models import CorpusDocument, ImportBatch, PlanningPeriod, Proposal, Team, UsageRecord
from app.db.session import get_session
from app.schemas.agent import AgentRunCreate
from app.schemas.decisions import DecisionCreate
from app.services import agent_runs as run_svc
from app.services import budget as budget_svc
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


def _people_by_team(session: Session) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for p in people_svc.list_people(session):
        out.setdefault(p.team_id, []).append(p.id)
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
    return mappers.proposal(out, period_row=_period_row(session, p.period_id),
                            citations=_evidence_citations(session, out["evidence_refs"]),
                            forecasts_reviewed=_snapshot_forecasts(session, out["evidence_refs"]))


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
    # meta["company"]: BACKEND_COMPANY_ID/NAME env vars > company_profile row > Northstar default.
    return mappers.company(meta, company_id=meta["company"]["id"], name=meta["company"]["name"])


@router.get("/teams", response_model=list[S.Team], **JSON_OPTS)
def get_teams(session: Session = Depends(get_session), clock: Clock = Depends(get_clock)):
    period = _period_or_none(session, clock)
    unattributed = period is not None and _has_unattributed(session, period.id)  # no period yet: plain list
    return mappers.teams(_active_teams(session), include_unattributed=unattributed,
                         leads=mappers.team_leads(people_svc.list_people(session)))


@router.get("/people", response_model=list[S.Person], **JSON_OPTS)
def get_people(request: Request, session: Session = Depends(get_session)):
    def build() -> list[dict]:
        active = {t.id for t in _active_teams(session)}
        return [mappers.person(p) for p in people_svc.list_people(session) if p.team_id in active]

    # Polled every second; people change only on writes, which move the data stamp (cache.py).
    return cache.cached_json(request, ("people", cache.data_stamp(session)), list[S.Person], build)


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

    # Polled every second while the live feed appends records every few seconds: the incremental index
    # (spending_index.py) re-maps only the rows new records touch and rebuilds fully only after an
    # in-place change (e.g. a team re-attribution); unchanged data gets the stored body.
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
    # Only the allocations are shown here: skip budget_state's spend-coverage report, which loads every
    # usage record of the period (~0.4 s on the Uber dataset) for fields this route never returns.
    allocations = budget_svc.allocation_map(env)
    return mappers.budgets({"period": period, "unit": env.unit, "state_version": env.state_version,
                            "allocations": [{"team": t, "amount": a} for t, a in sorted(allocations.items())]})


@router.get("/forecasts", response_model=list[S.Forecast], **JSON_OPTS)
def get_forecasts(request: Request, session: Session = Depends(get_session), clock: Clock = Depends(get_clock),
                  provider=Depends(get_forecast_provider)):
    period = _period_or_none(session, clock)
    if period is None:
        return []
    result = forecast_svc.forecast_for_period(session, provider, period, clock=clock)  # read only: no snapshot
    team_ids = forecast_svc.active_team_ids(session)
    people = _people_by_team(session)
    now = clock.now()
    key = _forecast_key(result, period, team_ids, people, now)
    def build() -> cache.Body:
        raw = cache.render(list[S.Forecast], mappers.forecasts(result, period_row=period, team_ids=team_ids,
                                                                now=now, people=people))
        return cache.Body(raw, keep=result)  # holding `result` keeps the object ids in its key from reuse

    return cache.cache_for(request.app.state).get_or_build(key, build).response(request)  # single-flight


def _forecast_key(result: Any, period: PlanningPeriod, team_ids: list[str], people: dict[str, list[str]],
                  now: Any) -> tuple:
    """Everything mappers.forecasts reads. Projections are keyed by object identity: a provider that
    caches its results (forecasting_package) hands back the same projection objects until its inputs
    change, so the ~0.05 s mapping of ~150 forecasts x daily points runs once per new result; a provider
    that builds fresh objects per call (placeholder) simply never hits."""
    return ("forecasts", result.provider, result.availability, result.reason, result.target_period,
            result.basis, result.method_label, result.value_kind, result.generated_at,
            result.generated_at is None and now, result.as_of,
            tuple(id(p) for p in result.projections), tuple(id(p) for p in result.person_projections),
            period.id, period.label, period.starts_on, period.ends_on, tuple(team_ids),
            tuple((t, tuple(ids)) for t, ids in sorted(people.items())))


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
    return mappers.document(doc) if doc is not None else None


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
def get_thread(thread_id: str, session: Session = Depends(get_session)):
    return [threads.message_out(m) for m in threads.list_messages(session, thread_id[:MAX_THREAD_ID])]


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
    return {"id": p.id, "stale": stale, "mode": p.action_type, "prioritize": favoured, "label": label}


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
    user = threads.add_message(session, thread_id, "user", content, clock=clock, ids=ids)
    session.commit()

    parsed = intent.parse(content, **_intent_context(session, request, clock))
    if parsed.ask is not None:
        reply = threads.add_message(session, thread_id, "assistant",
                                    f"**Read as:** {parsed.read_as}.\n\n{parsed.ask}", clock=clock, ids=ids)
        session.commit()
        return [threads.message_out(user), threads.message_out(reply)]

    session.commit()  # end this session's read transaction: the run writes through its own sessions
    run_id: str | None = None
    try:
        run_id, _ = run_svc.start_run(request.app.state, AgentRunCreate(**parsed.run, wait=True), actor=actor)
    except DomainError as exc:
        run_id = (exc.details or {}).get("run_id")
        text = (f"**Read as:** {parsed.read_as}.\n\n{errors.plain_message(exc.code, exc.message, exc.details)}"
                + ("" if exc.code == "runner_unavailable" else " Nothing was changed."))
        if exc.code == "runner_unavailable":
            text += f"\n\n_Detail: {exc.message}_"
        reply = threads.add_message(session, thread_id, "assistant", text, clock=clock, ids=ids,
                                    agent_run_id=run_id)
        session.commit()
        return [threads.message_out(user), threads.message_out(reply)]

    session.commit()
    session.expire_all()  # the run wrote through its own sessions
    run = run_svc.run_out(session, run_svc.get_run(session, run_id))
    proposal_id = run["proposals"][0]["id"] if run["proposals"] else None
    revised_note = _link_revision(session, parsed.revises, proposal_id, actor=actor, clock=clock)
    proposal = (proposal_svc.proposal_out(session, proposal_svc.get_proposal(session, proposal_id))
                if proposal_id else None)
    reply = threads.add_message(
        session, thread_id, "assistant", threads.reply_text(parsed.read_as, run) + revised_note, clock=clock, ids=ids,
        agent_run_id=run_id, proposal_id=proposal_id, citations=threads.citations(session, run, proposal),
        tool_calls=threads.tool_calls(run),
    )
    session.commit()
    return [threads.message_out(user), threads.message_out(reply)]


def _link_revision(session: Session, original_id: str | None, new_id: str | None, *, actor: Actor,
                   clock: Clock) -> str:
    """A chat revise: finance asked for `original_id` to be revised and the run drafted `new_id`. The original
    becomes `revised` and the draft records what it replaces. Returns a line for the reply ("" when no link)."""
    if not original_id or not new_id:
        return ""
    if new_id == original_id:
        return f"\n\n_The revised draft came out the same as {original_id}, so {original_id} stays open._"
    try:
        linked = proposal_svc.link_revision(session, original_id, new_id, actor=actor, clock=clock)
    except DomainError as exc:
        session.rollback()
        return f"\n\n_{new_id} was drafted, but {original_id} could not be marked revised: {exc.message}._"
    session.commit()
    if not linked:
        return f"\n\n_{new_id} was drafted, but {original_id} had already moved on, so it was not marked revised._"
    return f"\n\n_{new_id} replaces {original_id}, which is now marked revised._"


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
