"""Pure mapping functions: backend service output -> frontend contract dicts (camelCase, money as numbers).

Rules (docs/frontend-alignment.md §2):
- Money becomes a JSON number only here, in `num`. Nothing produced by this module flows back into a
  service; the frontend never sends money except inside chat text, which `intent.py` parses as Decimal.
- No number the backend does not have is invented. Fields the backend cannot fill are omitted (they are
  optional in the TypeScript contract) or carry the frontend's own "unknown"/"unavailable" value.
- Values derived by a documented rule (context `title`, `confidence`) are marked as such in the doc.
"""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Iterable, Mapping

UNATTRIBUTED = "unattributed"
UNATTRIBUTED_TEAM = {"id": UNATTRIBUTED, "name": "Unattributed", "color": "var(--muted-foreground)",
                     "description": "Spend from source accounts with no team mapping yet. It counts toward the "
                                    "company total but toward no team."}
CHART_TOKENS = 5  # the frontend defines --chart-1 .. --chart-5

COMPONENT = {"subscription_fee": "subscription", "included_usage": "included_usage",
             "billable_overage": "extra_usage", "direct_api": "api"}
# Weakest provenance wins when a grouped row mixes kinds.
PROVENANCE = {"reported": "reported_charge", "simulated": "reported_charge", "measured": "usage_only",
              "estimated": "estimate"}
_PROVENANCE_RANK = {"reported_charge": 0, "usage_only": 1, "estimate": 2}
DOC_KIND = {"plan": "plan", "update": "project_doc", "note": "project_doc", "correspondence": "correspondence"}
DOC_ORIGIN = {"upload": "Uploaded document", "email_export": "Email export", "slack_export": "Slack export",
              "seed": "Seeded demo document"}
EFFECT = {"expansion": "increase", "reduction": "decrease", "continuation": "neutral",
          "timing_shift": "unknown", "other": "unknown"}
PROPOSAL_KIND = {"transfer": "redistribute", "addition": "add_budget"}
DECISION_ACTION = {"approved_applied": "applied", "rejected": "rejected"}
TITLE_MAX = 90
# A document's connector when its front matter names none (frontend-integration-design §1.1).
ORIGIN_INTEGRATION = {"email_export": "email", "slack_export": "slack"}
INTEGRATION_ORIGIN = {"slack": "Slack export", "asana": "Asana export", "monday": "monday.com export",
                      "email": "Email export"}
# Demo identities shown on receipts. "(demo)" is the honesty label: the dashboard identity is configured,
# not authenticated (docs/frontend-alignment.md G9). A header-supplied X-Actor-Id is shown as given.
APPROVER_LABELS = {"dashboard-approver": "Finance approver (demo)"}
SIMULATED_LIMITATION = "simulated projection for the demo company; not a forecast of real spend"
PERSON_SPLIT_LIMITATION = "person split is proportional to spend to date; not a person-level model"


# ---- scalars ----------------------------------------------------------------------------------


def num(value: Decimal | str | int | None) -> int | float | None:
    """Backend money (Decimal / canonical string) -> JSON number. Whole amounts are ints."""
    if value is None:
        return None
    d = value if isinstance(value, Decimal) else Decimal(str(value))
    if d == d.to_integral_value():
        return int(d)
    return float(round(d, 2))


def money_text(value: Decimal | str) -> str:
    d = value if isinstance(value, Decimal) else Decimal(str(value))
    return f"${d:,.2f}"


def unit(value: str | None) -> str:
    return (value or "USD").lower()


def iso(value: datetime | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def day(value: datetime | date | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)[:10]


def period(p: Any) -> dict:
    """PlanningPeriod row or `{id, label, starts_on, ends_on}` dict -> Period."""
    get = (lambda k: p.get(k)) if isinstance(p, Mapping) else (lambda k: getattr(p, k))
    out = {"start": day(get("starts_on")), "end": day(get("ends_on"))}
    if get("label"):
        out["label"] = get("label")
    return out


def team_color(index: int) -> str:
    return f"var(--chart-{index % CHART_TOKENS + 1})"


# ---- company / teams ----------------------------------------------------------------------------


def company(meta: dict, *, company_id: str, name: str) -> dict:
    rows = meta.get("real_vs_simulated") or []
    return {
        "id": company_id,
        "name": name,
        # Demo whenever any component (data, projections, runner, identity) is not real.
        "isDemo": any(r.get("status") != "real" for r in rows) or not rows,
        "budgetUnit": unit(meta.get("unit")),
        "currentPeriod": period(meta["period"]),
    }


def team_leads(people: Iterable[Any]) -> dict[str, str]:
    """Team.lead, derived: the name of the first active person on the team (by id) whose role ends with
    " lead". Teams without one get no lead (omitted, not invented)."""
    leads: dict[str, str] = {}
    for p in sorted(people, key=lambda p: p.id):
        if p.active and (p.role or "").strip().lower().endswith(" lead"):
            leads.setdefault(p.team_id, p.name)
    return leads


def teams(rows: Iterable[Any], *, include_unattributed: bool, leads: Mapping[str, str] | None = None) -> list[dict]:
    out = []
    for i, t in enumerate(rows):
        row = {"id": t.id, "name": t.name, "color": team_color(i)}
        if (leads or {}).get(t.id):
            row["lead"] = leads[t.id]
        out.append(row)
    if include_unattributed:
        out.append(dict(UNATTRIBUTED_TEAM))
    return out


def person(p: Any) -> dict:
    out = {"id": p.id, "teamId": p.team_id, "name": p.name}
    if p.role:
        out["role"] = p.role
    if p.email:
        out["email"] = p.email
    if p.integrations:
        out["integrations"] = list(p.integrations)
    if p.primary_tool:
        out["primaryTool"] = p.primary_tool
    return out


# ---- spending -----------------------------------------------------------------------------------


def spending(records: Iterable[dict], *, batch_labels: Mapping[str, str]) -> list[dict]:
    """Group backend usage records (spending.record_out dicts) into one row per team x person x day x
    component x provider (person None = a team-level row, e.g. included usage). Included usage carries amount 0 (it is covered by the subscription fee; its notional value is
    named in `source`). Unpriced token rows have no frontend equivalent that would not be summed into dollars,
    so they are left out.

    `complete` is per row and day, never the period-wide coverage status (which turns every team `partial`
    as soon as any record in the period is unattributed): a row is partial only when its own records are
    unattributed or include a cumulative counter reset. So spend on complete days + forecast.daily (from the
    day after as_of) still equals `projected` while unmapped records are present."""
    groups: dict[tuple[str, str, str, str, str], list[dict]] = defaultdict(list)
    for r in records:
        component = COMPONENT.get(r["cost_category"])
        if component is None:  # unpriced_usage
            continue
        key = (r["team"] or UNATTRIBUTED, r.get("person") or "", day(r["occurred_at"]), component,
               r["provider"] or "unknown")
        groups[key].append(r)

    out = []
    for (team, person_id, d, component, provider), recs in sorted(groups.items()):
        if component == "included_usage":
            amount = Decimal("0")
            provenance = "usage_only"
        else:
            amount = sum((Decimal(str(r["amount"])) for r in recs if r["counts_toward_spend"] and r["amount"] is not None),
                         Decimal("0"))
            provenance = max((PROVENANCE[r["value_kind"]] for r in recs), key=_PROVENANCE_RANK.__getitem__)
        labels = sorted({batch_labels.get(r["import_batch_id"], r["source_kind"]) for r in recs})
        source = "; ".join(labels)
        if any(r["value_kind"] == "simulated" for r in recs) and "simulated" not in source.lower():
            source += " (simulated)"
        if component == "included_usage":
            notional = sum((Decimal(str(r["notional_value"])) for r in recs if r["notional_value"] is not None),
                           Decimal("0"))
            source += (f"; included in the subscription fee, notional value {money_text(notional)} "
                       "is not counted as spend")
        complete = team != UNATTRIBUTED and not any(r["counter_reset"] for r in recs)
        row_id = f"{team}:{person_id}:{d}:{component}:{provider}" if person_id else f"{team}:{d}:{component}:{provider}"
        out.append({
            "id": row_id, "teamId": team, **({"personId": person_id} if person_id else {}), "date": d, "component": component, "provider": provider,
            "amount": num(amount), "unit": unit(recs[0]["unit"]), "provenance": provenance,
            "source": source, "complete": complete,
        })
    return out


# ---- budgets / forecasts ------------------------------------------------------------------------


def budgets(state: dict) -> list[dict]:
    p = period(state["period"])
    return [{"teamId": a["team"], "period": p, "allocated": num(a["amount"]), "unit": unit(state["unit"]),
             "version": str(state["state_version"])} for a in state["allocations"]]


def _daily(points: Iterable[Mapping[str, Any]] | None) -> list[dict] | None:
    if points is None:
        return None
    return [{"date": day(pt["date"]), "projected": num(pt["amount"])} for pt in points]


def _capitalize(text: str) -> str:
    return text[:1].upper() + text[1:]


def forecasts(result: Any, *, period_row: Any, team_ids: Iterable[str], now: datetime,
              people: Mapping[str, Iterable[str]] | None = None) -> list[dict]:
    """One backend ForecastResult -> one Forecast per team, then one per person (`personId` set).

    A team without a projection is `unavailable` with the provider's reason, and so is every active
    person on it (`people`: team -> person ids); no number is filled in. Person items are the provider's
    proportional split of the team placeholder, already reconciled by `forecasts._sanitize`
    (sum of person amounts + team-level remainder == team amount). Engine amounts retain their
    full-quarter meaning; absent person projections stay unavailable. Optional bounds are passed through."""
    r = result if isinstance(result, Mapping) else result.model_dump(mode="python")
    p = period(period_row)
    by_team = {pr["team"]: pr for pr in r.get("projections") or []}
    persons_by_team: dict[str, list[dict]] = defaultdict(list)
    for pp in r.get("person_projections") or []:
        persons_by_team[pp["team"]].append(pp)
    generated = iso(r.get("generated_at")) or iso(now)
    origin = "placeholder" if r.get("provider") == "placeholder" else "forecasting_service"
    basis = "remaining" if r.get("basis") == "remaining" else "full_period"
    person_limitations = [PERSON_SPLIT_LIMITATION] if origin == "placeholder" else []
    method = [r["method_label"]] if r.get("method_label") else []
    simulated = [SIMULATED_LIMITATION] if r.get("value_kind") == "simulated" else []
    teams_out, persons_out = [], []
    for team in team_ids:
        pr = by_team.get(team)
        limitations = method + simulated
        base = {"id": f"fc-{team}-{r['target_period']}", "teamId": team, "period": p, "unit": "usd",
                "generatedAt": generated, "origin": origin}
        if pr is None:
            reason = r.get("reason") or "no projection for this team"
            teams_out.append({**base, "status": "unavailable", "unavailableReason": reason, "assumptions": [],
                              "limitations": limitations + [reason]})
            for pid in sorted((people or {}).get(team, ())):
                persons_out.append({**base, "id": f"fc-{team}-{r['target_period']}-{pid}", "personId": pid,
                                    "status": "unavailable", "unavailableReason": reason, "assumptions": [],
                                    "limitations": limitations + person_limitations})
            continue
        if pr.get("uncertainty"):
            limitations = limitations + [pr["uncertainty"]]
        if r.get("reason"):
            limitations = limitations + [r["reason"]]
        assumptions = list(pr.get("assumptions") or [])
        split = sorted(persons_by_team.get(team, []), key=lambda pp: pp["person"])
        if split:
            label = "individual placeholder" if origin == "placeholder" else "individual"
            assumptions.append(f"Sum of {len(split)} {label} projections")
            team_level = Decimal(str(pr["amount"])) - sum((Decimal(str(pp["amount"])) for pp in split), Decimal("0"))
            if team_level > 0:
                assumptions.append(f"Includes {money_text(team_level)} of team-level spend not attributed to a person")
        item = {**base, "status": "available", "basis": basis, "kind": "forecast",
                "projected": num(pr["amount"]), "unit": unit(pr.get("unit")),
                "assumptions": assumptions, "limitations": limitations}
        for field in ("low", "high"):
            if pr.get(field) is not None:
                item[field] = num(pr[field])
        if pr.get("daily") is not None:
            item["daily"] = _daily(pr["daily"])
        teams_out.append(item)
        if not split:
            reason = next((x for x in (r.get("reason") or "").split("; ") if x.startswith(f"person split did not reconcile for {team}")),
                          "no person-level split for this team")
            for pid in sorted((people or {}).get(team, ())):
                persons_out.append({**base, "id": f"fc-{team}-{r['target_period']}-{pid}", "personId": pid,
                                    "status": "unavailable", "unavailableReason": reason, "assumptions": [],
                                    "limitations": method + simulated + person_limitations})
        for pp in split:
            person_item = {**base, "id": f"fc-{team}-{r['target_period']}-{pp['person']}", "personId": pp["person"],
                           "status": "available", "basis": "full_period", "kind": "forecast",
                           "projected": num(pp["amount"]), "unit": unit(pp.get("unit")),
                           "assumptions": [_capitalize(a) for a in pp.get("assumptions") or []],
                           "limitations": method + simulated + person_limitations}
            if pp.get("uncertainty") and pp["uncertainty"] not in person_item["limitations"]:
                person_item["limitations"] = person_item["limitations"] + [pp["uncertainty"]]
            for field in ("low", "high"):
                if pp.get(field) is not None:
                    person_item[field] = num(pp[field])
            if pp.get("daily") is not None:
                person_item["daily"] = _daily(pp["daily"])
            persons_out.append(person_item)
    persons_out.sort(key=lambda f: (f["teamId"], f["personId"]))
    return teams_out + persons_out


# ---- documents / context -----------------------------------------------------------------------


def doc_kind(doc_type: str | None) -> str:
    return DOC_KIND.get(doc_type or "", "project_doc")


def doc_integration(d: Any) -> str:
    return getattr(d, "integration", None) or ORIGIN_INTEGRATION.get(d.origin, "document")


def document(d: Any) -> dict:
    integration = doc_integration(d)
    origin = INTEGRATION_ORIGIN.get(integration) or DOC_ORIGIN.get(d.origin, d.origin)
    if d.is_simulated:
        origin += " (simulated)"
    out = {"id": d.id, "title": d.title, "kind": doc_kind(d.doc_type), "date": day(d.authored_at),
           "teamIds": list(d.team_tags or []), "origin": origin, "body": d.content,
           "personIds": list(d.person_tags or []), "integration": integration}
    if d.superseded_by_document_id:
        out["supersededBy"] = d.superseded_by_document_id
    return out


def source_ref(citation: dict, doc: Any | None) -> dict:
    out = {"documentId": citation["document_id"], "title": citation["title"], "excerpt": citation["quote"],
           "locator": f"chars {citation['char_start']}-{citation['char_end']}"
                      + (" (superseded version)" if citation.get("citation_currency") == "superseded" else "")}
    if doc is not None:
        out["date"] = day(doc.authored_at)
        out["kind"] = doc_kind(doc.doc_type)
        out["integration"] = doc_integration(doc)
        if doc.author:
            out["author"] = doc.author
    return out


def document_ref(doc: Any) -> dict:
    out = {"documentId": doc.id, "title": doc.title, "date": day(doc.authored_at), "kind": doc_kind(doc.doc_type),
           "integration": doc_integration(doc)}
    if doc.author:
        out["author"] = doc.author
    return out


def derived_title(summary: str) -> str:
    first = re.split(r"(?<=[.;])\s+", summary.strip(), maxsplit=1)[0].rstrip(".;")
    if len(first) <= TITLE_MAX:
        return first
    cut = first[: TITLE_MAX - 1].rsplit(" ", 1)[0]
    return cut.rstrip(",;:") + "…"


def confidence(status: str, docs: list[Any]) -> str:
    """Derived (the backend stores none): a current signal resting on an approved plan is `high`, any other
    current signal `medium`, and informal / conflicting / superseded / cancelled signals `low`."""
    if status != "current":
        return "low"
    return "high" if any(d is not None and d.plan_status == "approved" for d in docs) else "medium"


def expected_effect(change_type: str, signal_kind: str | None) -> str:
    """A timing shift's direction comes from its typed kind (G5): deferred -> decrease, accelerated -> increase."""
    if change_type == "timing_shift" and signal_kind == "project_deferred":
        return "decrease"
    if change_type == "timing_shift" and signal_kind == "project_accelerated":
        return "increase"
    return EFFECT.get(change_type, "unknown")


def context_item(sig: dict, docs: Mapping[str, Any], *, company_team_ids: Iterable[str] = ()) -> dict:
    """`company_team_ids`: the active teams a company-scope signal (team NULL) applies to."""
    cited = [docs.get(c["document_id"]) for c in sig["citations"]]
    first = next((d for d in cited if d is not None), None)
    first_type = first.doc_type if first is not None else None
    uncertainty = sig["uncertainty"]
    if sig.get("needs_review"):
        uncertainty += " Needs review: every cited document has since been superseded."
    scope = sig.get("scope") or "team"
    kind = sig.get("signal_kind")
    if scope == "company":
        team_ids = sorted(company_team_ids)
    else:
        team_ids = [sig["team"]] if sig["team"] else []
    if kind == "onboarding":
        claim = "observed_event"
    elif sig["status"] in ("current", "superseded", "cancelled") and first_type in ("plan", "update"):
        claim = "stated_plan"
    else:
        claim = "interpretation"
    out = {
        "id": sig["id"],
        "teamIds": team_ids,
        "title": sig.get("title") or derived_title(sig["summary"]),
        "summary": sig["summary"],
        "kind": doc_kind(first_type),
        "expectedEffect": expected_effect(sig["change_type"], kind),
        "confidence": confidence(sig["status"], cited),
        "sources": dedupe_refs(source_ref(c, docs.get(c["document_id"])) for c in sig["citations"]),
        "uncertainty": uncertainty,
        "claimType": claim,
        "scope": scope,
        "personIds": list(sig.get("person_ids") or []) if scope == "person" else [],
    }
    if kind:
        out["signal"] = kind
    if sig.get("applies_from"):
        out["effectiveFrom"] = day(sig["applies_from"])
    if sig.get("applies_to"):
        out["effectiveTo"] = day(sig["applies_to"])
    if sig.get("superseded_by_signal_id"):
        out["supersededBy"] = sig["superseded_by_signal_id"]
    if sig.get("supersedes_signal_ids"):
        out["supersedes"] = list(sig["supersedes_signal_ids"])
    return out


def dedupe_refs(refs: Iterable[dict]) -> list[dict]:
    seen, out = set(), []
    for r in refs:
        key = (r["documentId"], r.get("excerpt"))
        if key not in seen:
            seen.add(key)
            out.append(r)
    return out


# ---- proposals / decisions ---------------------------------------------------------------------


def lines(before: Mapping[str, Any], after: Mapping[str, Any]) -> list[dict]:
    teams_ = sorted(set(before) | set(after))
    return [{"teamId": t, "before": num(before.get(t, Decimal("0"))), "after": num(after.get(t, Decimal("0")))}
            for t in teams_]


def proposal_status(p: dict) -> str:
    if p["status"] == "pending_review":
        return "stale" if p["is_stale"] else "proposed"
    return p["status"]  # applied, rejected, stale, revised map 1:1


def proposal(p: dict, *, period_row: Any, citations: list[dict], forecasts_reviewed: list[dict]) -> dict:
    out = {
        "id": p["id"],
        "kind": PROPOSAL_KIND[p["action_type"]],
        "unit": unit(p["unit"]),
        "period": period(period_row),
        "totalBefore": num(p["before"]["total"]),
        "totalAfter": num(p["after"]["total"]),
        "lines": lines(p["before"]["allocations"], p["after"]["allocations"]),
        "rationale": p["rationale"],
        "citations": citations,
        "createdAt": iso(p["created_at"]),
        "status": proposal_status(p),
        "basedOnBudgetVersion": str(p["base_version"]),
    }
    if p["action_type"] == "addition":
        out["addedAmount"] = num(p["envelope_increase"])
    revises = p.get("revises_proposal_id") or p.get("rebased_from_proposal_id")
    if revises:
        out["revisesProposalId"] = revises
    if forecasts_reviewed:
        out["forecastsReviewed"] = forecasts_reviewed
    return out


# The rationale compat stores when the dashboard sends no note. Finance did not write these, so a Decision
# never returns them as `note` (the UI quotes any note as finance's words).
APPROVE_NOTE = "Approved from the dashboard (no note given)"
REJECT_NOTE = "Rejected from the dashboard"
DISMISS_NOTE = "Dismissed from the dashboard: the budget changed after this proposal was drafted"
SYSTEM_NOTES = frozenset({APPROVE_NOTE, REJECT_NOTE, DISMISS_NOTE})


def decision(d: dict, p: dict, *, forecasts_reviewed: list[dict]) -> dict:
    if d["after"] is not None:
        ln = lines(d["before"]["allocations"], d["after"]["allocations"])
    else:  # rejection: show the change that was declined
        ln = lines(p["before"]["allocations"], p["after"]["allocations"])
    out = {
        "id": d["id"],
        "proposalId": d["proposal_id"],
        "action": DECISION_ACTION[d["outcome"]],
        "kind": PROPOSAL_KIND[d["action_type"]],
        "appliedAt": iso(d["decided_at"]),
        "appliedBy": APPROVER_LABELS.get(d["actor"]["id"], d["actor"]["id"]),
        "lines": ln,
        "unit": unit(p["unit"]),
        "rationale": p["rationale"],
    }
    note = (d.get("rationale") or "").strip()
    if note and note not in SYSTEM_NOTES:
        out["note"] = d["rationale"]
    if forecasts_reviewed:
        out["forecastsReviewed"] = forecasts_reviewed
    return out
