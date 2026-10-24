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


def teams(rows: Iterable[Any], *, include_unattributed: bool) -> list[dict]:
    out = [{"id": t.id, "name": t.name, "color": team_color(i)} for i, t in enumerate(rows)]
    if include_unattributed:
        out.append(dict(UNATTRIBUTED_TEAM))
    return out


# ---- spending -----------------------------------------------------------------------------------


def spending(records: Iterable[dict], *, team_status: Mapping[str, str], batch_labels: Mapping[str, str]) -> list[dict]:
    """Group backend usage records (spending.record_out dicts) into one row per team x day x component x
    provider. Included usage carries amount 0 (it is covered by the subscription fee; its notional value is
    named in `source`). Unpriced token rows have no frontend equivalent that would not be summed into dollars,
    so they are left out; the team's coverage is then not complete, which shows as `complete: false`."""
    groups: dict[tuple[str, str, str, str], list[dict]] = defaultdict(list)
    for r in records:
        component = COMPONENT.get(r["cost_category"])
        if component is None:  # unpriced_usage
            continue
        key = (r["team"] or UNATTRIBUTED, day(r["occurred_at"]), component, r["provider"] or "unknown")
        groups[key].append(r)

    out = []
    for (team, d, component, provider), recs in sorted(groups.items()):
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
        complete = (team != UNATTRIBUTED and team_status.get(team) == "complete"
                    and not any(r["counter_reset"] for r in recs))
        out.append({
            "id": f"{team}:{d}:{component}:{provider}",
            "teamId": team, "date": d, "component": component, "provider": provider,
            "amount": num(amount), "unit": unit(recs[0]["unit"]), "provenance": provenance,
            "source": source, "complete": complete,
        })
    return out


# ---- budgets / forecasts ------------------------------------------------------------------------


def budgets(state: dict) -> list[dict]:
    p = period(state["period"])
    return [{"teamId": a["team"], "period": p, "allocated": num(a["amount"]), "unit": unit(state["unit"]),
             "version": str(state["state_version"])} for a in state["allocations"]]


def forecasts(result: Any, *, period_row: Any, team_ids: Iterable[str], now: datetime) -> list[dict]:
    """One backend ForecastResult -> one Forecast per team. A team without a projection is `unavailable`
    with the provider's reason; no number is filled in. The backend has no low/high range: omitted."""
    r = result if isinstance(result, Mapping) else result.model_dump(mode="python")
    p = period(period_row)
    by_team = {pr["team"]: pr for pr in r.get("projections") or []}
    generated = iso(r.get("generated_at")) or iso(now)
    origin = "placeholder" if r.get("provider") == "placeholder" else "forecasting_service"
    basis = "remaining" if r.get("basis") == "remaining" else "full_period"
    out = []
    for team in team_ids:
        pr = by_team.get(team)
        limitations = [r["method_label"]] if r.get("method_label") else []
        if r.get("value_kind") == "simulated":
            limitations.append("simulated projection for the demo company; not a forecast of real spend")
        base = {"id": f"fc-{team}-{r['target_period']}", "teamId": team, "period": p, "unit": "usd",
                "generatedAt": generated, "origin": origin}
        if pr is None:
            reason = r.get("reason") or "no projection for this team"
            out.append({**base, "status": "unavailable", "unavailableReason": reason, "assumptions": [],
                        "limitations": limitations + [reason]})
            continue
        if pr.get("uncertainty"):
            limitations.append(pr["uncertainty"])
        if r.get("reason"):
            limitations.append(r["reason"])
        out.append({**base, "status": "available", "basis": basis, "kind": "forecast",
                    "projected": num(pr["amount"]), "unit": unit(pr.get("unit")),
                    "assumptions": list(pr.get("assumptions") or []), "limitations": limitations})
    return out


# ---- documents / context -----------------------------------------------------------------------


def doc_kind(doc_type: str | None) -> str:
    return DOC_KIND.get(doc_type or "", "project_doc")


def document(d: Any) -> dict:
    origin = DOC_ORIGIN.get(d.origin, d.origin)
    if d.is_simulated:
        origin += " (simulated)"
    out = {"id": d.id, "title": d.title, "kind": doc_kind(d.doc_type), "date": day(d.authored_at),
           "teamIds": list(d.team_tags or []), "origin": origin, "body": d.content}
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
    return out


def document_ref(doc: Any) -> dict:
    return {"documentId": doc.id, "title": doc.title, "date": day(doc.authored_at), "kind": doc_kind(doc.doc_type)}


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


def context_item(sig: dict, docs: Mapping[str, Any]) -> dict:
    cited = [docs.get(c["document_id"]) for c in sig["citations"]]
    first = next((d for d in cited if d is not None), None)
    first_type = first.doc_type if first is not None else None
    uncertainty = sig["uncertainty"]
    if sig.get("needs_review"):
        uncertainty += " Needs review: every cited document has since been superseded."
    out = {
        "id": sig["id"],
        "teamIds": [sig["team"]] if sig["team"] else [],
        "title": derived_title(sig["summary"]),
        "summary": sig["summary"],
        "kind": doc_kind(first_type),
        "expectedEffect": EFFECT.get(sig["change_type"], "unknown"),
        "confidence": confidence(sig["status"], cited),
        "sources": dedupe_refs(source_ref(c, docs.get(c["document_id"])) for c in sig["citations"]),
        "uncertainty": uncertainty,
        "claimType": ("stated_plan" if sig["status"] in ("current", "superseded", "cancelled")
                      and first_type in ("plan", "update") else "interpretation"),
    }
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
        "appliedBy": d["actor"]["id"],
        "note": d["rationale"],
        "lines": ln,
        "unit": unit(p["unit"]),
        "rationale": p["rationale"],
    }
    if forecasts_reviewed:
        out["forecastsReviewed"] = forecasts_reviewed
    return out
