"""Export the generated dataset in the shapes the project's components consume."""
from __future__ import annotations

import csv
import gzip
import json
import statistics
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from . import config as C
from .people import slug

INTEGRATION_LABEL = {"slack": "Slack", "teams": "Microsoft Teams", "gmail": "Gmail", "outlook": "Outlook", "asana": "Asana", "monday": "monday.com"}
DOC_ORIGIN = {"slack": "slack_export", "teams": "slack_export", "gmail": "email_export", "outlook": "email_export", "asana": "upload", "monday": "upload"}
SIGNAL_MAP = {
    "out_of_office": "out_of_office", "extra_load": "project_accelerated", "project_accelerated": "project_accelerated",
    "project_deferred": "project_deferred", "project_paused": "project_paused", "project_resumed": "project_accelerated",
    "model_change": "model_change", "model_release": "model_change", "pricing_change": "pricing_change",
    "policy_change": "policy_change", "tool_change": "tool_change", "onboarding": "onboarding", "departure": "out_of_office",
    "incident": "project_accelerated", "hackathon": "project_accelerated", "holiday_notice": "project_paused",
    "hiring_freeze": "project_paused", "quarter_close": "project_accelerated", "steady": "steady",
}
COMPONENT = {"direct_api": "api", "billable_overage": "extra_usage", "included_usage": "included_usage", "subscription_fee": "subscription"}
MODEL_LABEL = {mid: v[1] for mid, v in C.MODELS.items()}
TOOL_LABEL = {"Cursor": "cursor", "GitHub Copilot": "github", "ChatGPT Enterprise": "openai", "Gemini Enterprise": "google", "Claude Code": "anthropic"}


def money(x: float) -> str:
    return f"{x:.2f}"


def period_dict(pid: str) -> dict:
    p = next(p for p in C.PERIODS if p["id"] == pid)
    return {"start": p["start"].isoformat(), "end": p["end"].isoformat(), "label": p["label"]}


def artifact_doc_key(kind: str, obj_id: str) -> str:
    return f"uber-{obj_id.replace('_', '-')}"


# ---------------------------------------------------------------------------------------------
# backend
# ---------------------------------------------------------------------------------------------

def export_backend(out: Path, *, teams, people, story, usage_rows, seat_rows, budgets) -> dict:
    bdir = out / "backend"
    (bdir / "billing").mkdir(parents=True, exist_ok=True)
    (bdir / "corpus").mkdir(parents=True, exist_ok=True)
    person_tool = {}
    by_month = defaultdict(list)
    def half(d: date) -> str:
        return d.strftime("%Y-%m") + ("a" if d.day <= 15 else "b")
    for r in usage_rows:
        by_month[half(r.day)].append(r)
    seat_by_month = defaultdict(list)
    for s in seat_rows:
        seat_by_month[half(s.month)].append(s)
    header = ["record_id", "occurred_at", "source_account", "provider", "model", "cost_category", "value_kind", "amount", "unit",
              "notional_value", "input_tokens", "cached_input_tokens", "output_tokens", "reasoning_tokens", "description"]
    files = []
    for month in sorted(set(by_month) | set(seat_by_month)):
        path = bdir / "billing" / f"uber_billing_{month}.csv"
        n = 0
        with path.open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(header)
            for s in seat_by_month.get(month, []):
                w.writerow([f"ub-seat-{s.month.isoformat()}-{s.person_id}", f"{s.month.isoformat()}T00:00:00Z", f"ws-{s.team_id}", s.provider, "",
                            "subscription_fee", "simulated", money(s.amount_usd), "USD", "", "", "", "", "", f"{s.tool} seat for {s.person_id}"])
                n += 1
            for r in by_month.get(month, []):
                cat_tag = {"direct_api": "api", "billable_overage": "ovr", "included_usage": "inc"}[r.cost_category]
                rid = f"ub-{r.day.isoformat()}-{r.person_id}-{r.model_id}-{cat_tag}"
                amount = "" if r.cost_category == "included_usage" else money(r.cost_usd)
                notional = money(r.notional_usd) if r.cost_category == "included_usage" else ""
                w.writerow([rid, f"{r.day.isoformat()}T12:00:00Z", f"ws-{r.team_id}", r.provider, r.model_name, r.cost_category, "simulated",
                            amount, "USD", notional, r.input_tokens, r.cached_input_tokens, r.output_tokens, r.reasoning_tokens or "",
                            f"{r.person_id} via {r.tool}"])
                n += 1
        files.append({"file": path.name, "records": n, "bytes": path.stat().st_size})

    # corpus documents: one per message and per task, with front matter the backend's parser accepts
    ev_by_id = {e.id: e for e in story.events}
    people_by_id = {p.id: p for p in people}
    corpus = []
    idx = 0
    for m in story.messages:
        ev = ev_by_id[m.event_id]
        idx += 1
        key = artifact_doc_key("msg", m.id)
        title = (m.where if m.channel in ("gmail", "outlook") else f"{INTEGRATION_LABEL[m.channel]} {m.where}: {ev.title}")[:200]
        plan_status = "informal" if m.channel in ("slack", "teams") else "n/a"
        if ev.kind in ("model_release", "policy_change", "tool_change", "hackathon", "pricing_change"):
            plan_status = "approved"
        fm = {
            "doc_key": key, "title": title, "origin": DOC_ORIGIN[m.channel], "doc_type": "correspondence", "plan_status": plan_status,
            "authored_at": m.sent_at.date().isoformat(), "effective_from": ev.starts_on.isoformat(),
            "effective_to": ev.ends_on.isoformat() if ev.ends_on else "", "team_tags": m.team_ids,
            "project_tags": [slug(ev.project)] if ev.project else [], "author": m.from_name, "is_simulated": "true",
        }
        body = f"# {title}\n\n*{INTEGRATION_LABEL[m.channel]} · {m.sent_at.strftime('%A %b %-d, %Y')} · {m.where}*\n\n{m.body}\n"
        corpus.append((idx, key, fm, body))
    for t in story.tasks:
        ev = ev_by_id[t.event_id]
        idx += 1
        key = artifact_doc_key("task", t.id)
        title = f"{INTEGRATION_LABEL[t.tool]}: {t.title}"[:200]
        fm = {
            "doc_key": key, "title": title, "origin": "upload", "doc_type": "update", "plan_status": "approved" if t.status not in ("Not started", "Scheduled") else "draft",
            "authored_at": t.status_changed_at.date().isoformat(), "effective_from": ev.starts_on.isoformat(),
            "effective_to": ev.ends_on.isoformat() if ev.ends_on else "", "team_tags": t.team_ids,
            "project_tags": [slug(ev.project)] if ev.project else [], "author": t.assignee_name, "is_simulated": "true",
        }
        meta = f"**Board:** {t.board} · **Assignee:** {t.assignee_name} · **Status:** {t.status}" + (f" (was {t.prev_status})" if t.prev_status else "")
        if t.due_on:
            meta += f" · **Due:** {t.due_on.isoformat()}" + (f" (was {t.prev_due_on.isoformat()})" if t.prev_due_on else "")
        body = f"# {title}\n\n*{INTEGRATION_LABEL[t.tool]} · created {t.created_at.strftime('%b %-d, %Y')} · last change {t.status_changed_at.strftime('%b %-d, %Y')}*\n\n{meta}\n\n{t.body}\n"
        corpus.append((idx, key, fm, body))
    for i, key, fm, body in corpus:
        lines = ["---"]
        for k, v in fm.items():
            if isinstance(v, list):
                lines.append(f"{k}: [{', '.join(v)}]")
            elif v == "":
                continue
            else:
                lines.append(f"{k}: {v}")
        lines.append("---")
        (bdir / "corpus" / f"{i:03d}-{key}.md").write_text("\n".join(lines) + "\n" + body, encoding="utf-8")

    reference = {
        "company": {"id": C.COMPANY_ID, "name": C.COMPANY_NAME, "simulated": True, "as_of": C.AS_OF.isoformat()},
        "periods": [{"id": p["id"], "label": p["label"], "starts_on": p["start"].isoformat(), "ends_on": p["end"].isoformat()} for p in C.PERIODS],
        "teams": [{"id": t.id, "name": t.name} for t in teams],
        "team_mappings": {"northstar_billing": {f"ws-{t.id}": t.id for t in teams}},
        "budgets": {pid: {b["team_id"]: money(b["allocated_usd"]) for b in budgets if b["period_id"] == pid} for pid in [p["id"] for p in C.PERIODS]},
        "billing_files": files,
        "corpus_documents": len(corpus),
    }
    (bdir / "reference.json").write_text(json.dumps(reference, indent=2), encoding="utf-8")
    return reference


# ---------------------------------------------------------------------------------------------
# frontend (contract shapes from frontend/src/lib/contracts/index.ts)
# ---------------------------------------------------------------------------------------------

def export_frontend(out: Path, *, teams, people, story, usage_rows, seat_rows, budgets) -> dict:
    fdir = out / "frontend"
    fdir.mkdir(parents=True, exist_ok=True)
    lead_name = {t.id: next(p.name for p in people if p.id == t.lead_id) for t in teams}
    current = period_dict("2026-Q4")
    company = {"id": C.COMPANY_ID, "name": C.COMPANY_NAME, "isDemo": True, "budgetUnit": "usd", "currentPeriod": current}
    teams_out = [{"id": t.id, "name": t.name, "description": t.description, "lead": lead_name[t.id], "color": t.color} for t in teams]
    people_out = [{"id": p.id, "teamId": p.team_id, "name": p.name, "role": p.role, "email": p.email, "integrations": p.integrations, "primaryTool": p.tool}
                  for p in people]
    budgets_out = [{"teamId": b["team_id"], "period": period_dict(b["period_id"]), "allocated": b["allocated_usd"], "unit": "usd", "version": "v1"} for b in budgets]

    export_date = C.AS_OF.isoformat()
    def source_label(provider: str) -> str:
        return {"anthropic": f"Anthropic cost report export {export_date}", "openai": f"OpenAI usage export {export_date}",
                "google": f"Google Cloud billing export {export_date}", "cursor": f"Cursor Admin API export {export_date}",
                "github": f"GitHub Copilot billing export {export_date}"}.get(provider, f"{provider} export {export_date}")

    spending = []
    for r in usage_rows:
        spending.append({
            "id": f"{r.person_id}:{r.day.isoformat()}:{COMPONENT[r.cost_category]}:{r.provider}:{slug(r.model_name)}",
            "teamId": r.team_id, "personId": r.person_id, "date": r.day.isoformat(), "component": COMPONENT[r.cost_category],
            "provider": r.provider, "model": r.model_name, "tokens": r.input_tokens + r.output_tokens,
            "amount": round(r.cost_usd, 2), "unit": "usd",
            "provenance": "usage_only" if r.cost_category == "included_usage" else ("estimate" if r.cost_category == "billable_overage" else "reported_charge"),
            "source": source_label(r.provider) + (" (simulated)"), "complete": r.day < C.AS_OF,
        })
    for s in seat_rows:
        spending.append({
            "id": f"{s.person_id}:{s.month.isoformat()}:subscription:{s.provider}", "teamId": s.team_id, "personId": s.person_id,
            "date": s.month.isoformat(), "component": "subscription", "provider": s.provider, "amount": s.amount_usd, "unit": "usd",
            "provenance": "reported_charge", "source": source_label(s.provider) + " (simulated)", "complete": True,
        })
    spending.sort(key=lambda x: (x["date"], x["teamId"], x["id"]))

    # team x day x component x provider x model aggregate for lighter clients
    agg = defaultdict(lambda: {"amount": 0.0, "tokens": 0})
    for rec in spending:
        k = (rec["teamId"], rec["date"], rec["component"], rec["provider"], rec.get("model"))
        agg[k]["amount"] += rec["amount"]
        agg[k]["tokens"] += rec.get("tokens", 0)
    team_daily = []
    for (team, day, comp, prov, model), v in sorted(agg.items(), key=lambda kv: (kv[0][1], kv[0][0], kv[0][2], kv[0][3], kv[0][4] or "")):
        row = {"id": f"{team}:{day}:{comp}:{prov}" + (f":{slug(model)}" if model else ""), "teamId": team, "date": day, "component": comp,
               "provider": prov, "amount": round(v["amount"], 2), "unit": "usd",
               "provenance": "usage_only" if comp == "included_usage" else ("estimate" if comp == "extra_usage" else "reported_charge"),
               "source": source_label(prov) + " (simulated)", "complete": day < export_date}
        if model:
            row["model"] = model
            row["tokens"] = v["tokens"]
        team_daily.append(row)

    # documents + context items
    ev_by_id = {e.id: e for e in story.events}
    documents, doc_by_event = [], defaultdict(list)
    for m in story.messages:
        ev = ev_by_id[m.event_id]
        doc = {"id": f"doc-{m.id.replace('_', '-')}", "title": (m.where if m.channel in ("gmail", "outlook") else f"{INTEGRATION_LABEL[m.channel]} {m.where}: {ev.title}"),
               "kind": "correspondence", "date": m.sent_at.date().isoformat(), "teamIds": m.team_ids, "personIds": m.person_ids,
               "origin": f"{INTEGRATION_LABEL[m.channel]} ({m.where}, via connector)", "body": m.body, "integration": m.channel}
        documents.append(doc)
        doc_by_event[ev.id].append((doc, m.from_name, m.body))
    for t in story.tasks:
        ev = ev_by_id[t.event_id]
        doc = {"id": f"doc-{t.id.replace('_', '-')}", "title": f"{INTEGRATION_LABEL[t.tool]}: {t.title}", "kind": "project_doc",
               "date": t.status_changed_at.date().isoformat(), "teamIds": t.team_ids, "personIds": t.person_ids,
               "origin": f"{INTEGRATION_LABEL[t.tool]} ({t.board}, via connector)", "body": t.body, "integration": t.tool}
        documents.append(doc)
        doc_by_event[ev.id].append((doc, t.assignee_name, t.body))

    def excerpt(body: str) -> str:
        text = " ".join(line.strip() for line in body.splitlines() if line.strip() and not line.startswith(("**From", "**To", "**Date", "**Subject", "---", "#", "|")))
        text = text.replace("**", "")
        return (text[:220] + "…") if len(text) > 220 else text

    context = []
    for ev in story.events:
        srcs = []
        for doc, author, body in doc_by_event.get(ev.id, []):
            srcs.append({"documentId": doc["id"], "title": doc["title"], "excerpt": excerpt(body), "date": doc["date"], "kind": doc["kind"],
                         "integration": doc["integration"], "author": author})
        item = {
            "id": f"ctx-{ev.id.replace('_', '-')}", "teamIds": ev.team_ids, "personIds": ev.person_ids, "title": ev.title, "summary": ev.summary,
            "kind": "correspondence" if any(s["kind"] == "correspondence" for s in srcs) else "project_doc",
            "effectiveFrom": ev.starts_on.isoformat(), "expectedEffect": ev.expected_effect, "confidence": ev.confidence, "sources": srcs,
            "claimType": ev.claim_type, "scope": ev.scope, "signal": SIGNAL_MAP[ev.kind], "category": ev.category, "eventKind": ev.kind,
            "attribution": srcs[0]["author"] + (f" in {srcs[0]['title'].split(':')[0]}" if ":" in srcs[0]["title"] else "") if srcs else "Generated storyline",
        }
        if ev.ends_on:
            item["effectiveTo"] = ev.ends_on.isoformat()
        if ev.uncertainty:
            item["uncertainty"] = ev.uncertainty
        if ev.magnitude_pct is not None:
            item["magnitude"] = {"pct": ev.magnitude_pct, "basis": f"usage multiplier {ev.multiplier:.2f}x on the affected people for the window"}
        context.append(item)

    (fdir / "company.json").write_text(json.dumps({"company": company, "teams": teams_out, "people": people_out, "budgets": budgets_out}, indent=2), encoding="utf-8")
    with gzip.open(fdir / "spending-records.json.gz", "wt", encoding="utf-8") as fh:  # ~130 MB uncompressed
        json.dump(spending, fh)
    (fdir / "spending-team-daily.json").write_text(json.dumps(team_daily), encoding="utf-8")
    (fdir / "documents.json").write_text(json.dumps(documents, indent=1), encoding="utf-8")
    (fdir / "context.json").write_text(json.dumps(context, indent=1), encoding="utf-8")
    return {"spending_records": len(spending), "team_daily_records": len(team_daily), "documents": len(documents), "context_items": len(context)}


# ---------------------------------------------------------------------------------------------
# forecasting (src/forecasting observation export format)
# ---------------------------------------------------------------------------------------------

def export_forecasting(out: Path, *, teams, usage_rows, seat_rows, holdout_rows, holdout_seats) -> dict:
    fdir = out / "forecasting"
    fdir.mkdir(parents=True, exist_ok=True)

    def records(rows, seats, status_known_offset=1):
        daily = defaultdict(float)
        for r in rows:
            if r.cost_usd:
                daily[(r.team_id, r.day)] += r.cost_usd
        fixed = defaultdict(float)
        for s in seats:
            fixed[(s.team_id, s.month)] += s.amount_usd
        recs = []
        for (team, day), val in sorted(daily.items(), key=lambda kv: (kv[0][1], kv[0][0])):
            known = datetime.combine(day + timedelta(days=status_known_offset), datetime.min.time(), tzinfo=timezone.utc).isoformat()
            recs.append({"record_id": f"{team}:{day.isoformat()}:variable", "source_id": "billing", "entity_id": f"team:{team}",
                         "service_date": day.isoformat(), "value": money(val), "unit": "USD", "currency": "USD", "category": "variable",
                         "known_at": known, "ingested_at": known, "processed_at": known, "revision": 1,
                         "status": "partial" if day == C.AS_OF else "observed"})
        for (team, day), val in sorted(fixed.items(), key=lambda kv: (kv[0][1], kv[0][0])):
            known = datetime.combine(day + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc).isoformat()
            recs.append({"record_id": f"{team}:{day.isoformat()}:fixed", "source_id": "seats", "entity_id": f"team:{team}",
                         "service_date": day.isoformat(), "value": money(val), "unit": "USD", "currency": "USD", "category": "fixed",
                         "known_at": known, "ingested_at": known, "processed_at": known, "revision": 1, "status": "observed"})
        return recs

    # One source per export file (the forecasting extraction receipt requires it): variable API spend from
    # "billing", seat fees from "seats".
    var_hist = records(usage_rows, [])
    seat_hist = records([], seat_rows)
    (fdir / "uber-observations.json").write_text(json.dumps({"schema_version": "1.0", "records": var_hist}, indent=1), encoding="utf-8")
    (fdir / "uber-seat-observations.json").write_text(json.dumps({"schema_version": "1.0", "records": seat_hist}, indent=1), encoding="utf-8")
    truth = {"schema_version": "1.0", "note": "SYNTHETIC GROUND TRUTH for Oct 25 - Dec 31 2026. Never feed to a model; use only to score forecasts.",
             "records": records(holdout_rows, []) + records([], holdout_seats)}
    (fdir / "uber-holdout-truth.json").write_text(json.dumps(truth, indent=1), encoding="utf-8")
    as_of = datetime.combine(C.AS_OF, datetime.min.time(), tzinfo=timezone.utc).isoformat()
    config = {
        "schema_version": "1.0",
        "request": {"request_id": "uber-sim-q4-v1",
                    "target": {"target_id": "uber-sim-variable", "tenant_id": C.COMPANY_ID, "measure": "provider_reported_cost", "unit": "USD",
                               "currency": "USD", "sources": ["billing"], "categories": ["variable"]},
                    "as_of": as_of, "period_start": "2026-10-01", "period_end": "2026-12-31", "model": "trailing_mean"},
        "export": "uber-observations.json", "source_id": "billing", "history_start": C.YEAR_START.isoformat(),
        "coverage": [{"source_id": "billing", "start": C.YEAR_START.isoformat(), "end": C.AS_OF.isoformat(), "state": "complete", "maturity": "finalized", "known_at": as_of}],
        "evidence_class": "synthetic_fixture",
    }
    (fdir / "uber-config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    return {"observations": len(var_hist), "seat_observations": len(seat_hist), "holdout_truth": len(truth["records"])}


# ---------------------------------------------------------------------------------------------
# flat CSVs
# ---------------------------------------------------------------------------------------------

def export_csv(out: Path, *, teams, people, story, calendar, usage_rows, seat_rows, budgets) -> None:
    cdir = out / "csv"
    cdir.mkdir(parents=True, exist_ok=True)

    def write(name, header, rows):
        opener = (lambda: gzip.open(cdir / name, "wt", newline="", encoding="utf-8")) if name.endswith(".gz") else (lambda: (cdir / name).open("w", newline="", encoding="utf-8"))
        with opener() as fh:
            w = csv.writer(fh)
            w.writerow(header)
            w.writerows(rows)

    write("teams.csv", ["id", "name", "description", "cost_center", "lead_person_id", "default_tool", "color"],
          [(t.id, t.name, t.description, t.cost_center, t.lead_id, t.tool, t.color) for t in teams])
    write("people.csv", ["id", "team_id", "name", "role", "level", "email", "primary_tool", "start_date", "end_date", "is_lead", "timezone", "integrations"],
          [(p.id, p.team_id, p.name, p.role, p.level, p.email, p.tool, p.start_date, p.end_date or "", int(p.is_lead), p.timezone, "|".join(p.integrations)) for p in people])
    write("usage_daily.csv.gz", ["day", "weekday", "person_id", "team_id", "provider", "model", "tool", "cost_category", "input_tokens", "cached_input_tokens",
                              "output_tokens", "reasoning_tokens", "total_tokens", "requests", "cost_usd", "notional_usd"],
          [(r.day, r.day.strftime("%a"), r.person_id, r.team_id, r.provider, r.model_name, r.tool, r.cost_category, r.input_tokens, r.cached_input_tokens,
            r.output_tokens, r.reasoning_tokens, r.input_tokens + r.output_tokens, r.requests, f"{r.cost_usd:.2f}", f"{r.notional_usd:.2f}") for r in usage_rows])
    agg = defaultdict(lambda: [0, 0.0])
    for r in usage_rows:
        a = agg[(r.day, r.team_id)]
        a[0] += r.input_tokens + r.output_tokens
        a[1] += r.cost_usd
    write("team_daily.csv", ["day", "weekday", "is_weekend", "holiday", "team_id", "total_tokens", "cost_usd"],
          [(d, d.strftime("%a"), int(calendar[d].is_weekend), calendar[d].holiday or "", t, v[0], f"{v[1]:.2f}") for (d, t), v in sorted(agg.items())])
    write("seat_subscriptions.csv", ["month", "person_id", "team_id", "tool", "provider", "amount_usd"],
          [(s.month, s.person_id, s.team_id, s.tool, s.provider, f"{s.amount_usd:.2f}") for s in seat_rows])
    write("events.csv", ["id", "kind", "scope", "team_ids", "person_ids", "project", "starts_on", "ends_on", "usage_multiplier", "weekend_multiplier",
                         "announced_on", "expected_effect", "category", "confidence", "claim_type", "magnitude_pct", "is_future", "title"],
          [(e.id, e.kind, e.scope, "|".join(e.team_ids), "|".join(e.person_ids), e.project or "", e.starts_on, e.ends_on or "", e.multiplier,
            e.weekend_multiplier if e.weekend_multiplier is not None else "", e.announced_on, e.expected_effect, e.category, e.confidence, e.claim_type,
            e.magnitude_pct if e.magnitude_pct is not None else "", int(e.future), e.title) for e in story.events])
    write("messages.csv", ["id", "event_id", "channel", "sent_at", "weekday", "from_person_id", "from_name", "to", "where", "team_ids", "person_ids", "body"],
          [(m.id, m.event_id, m.channel, m.sent_at.isoformat(), m.weekday, m.from_person_id or "", m.from_name, "|".join(m.to), m.where, "|".join(m.team_ids),
            "|".join(m.person_ids), m.body) for m in story.messages])
    write("tasks.csv", ["id", "event_id", "tool", "board", "title", "assignee_id", "assignee_name", "created_at", "due_on", "prev_due_on", "status", "prev_status",
                        "status_changed_at", "team_ids", "person_ids", "body"],
          [(t.id, t.event_id, t.tool, t.board, t.title, t.assignee_id or "", t.assignee_name, t.created_at.isoformat(), t.due_on or "", t.prev_due_on or "",
            t.status, t.prev_status or "", t.status_changed_at.isoformat(), "|".join(t.team_ids), "|".join(t.person_ids), t.body) for t in story.tasks])
    write("model_events.csv", ["id", "provider", "models", "kind", "announced_on", "effective_on", "details"],
          [(m.id, m.provider, "|".join(m.model_ids), m.kind, m.announced_on, m.effective_on, json.dumps(m.details)) for m in story.model_events])
    write("calendar.csv", ["day", "weekday", "is_weekend", "holiday", "holiday_factor", "seasonal_factor", "period_id", "is_partial", "is_future"],
          [(c.day, c.day.strftime("%A"), int(c.is_weekend), c.holiday or "", c.holiday_factor, c.seasonal_factor, c.period_id or "", int(c.partial), int(c.day > C.AS_OF)) for c in calendar.values()])
    write("budgets.csv", ["team_id", "period_id", "allocated_usd", "actual_usd_to_date"],
          [(b["team_id"], b["period_id"], f"{b['allocated_usd']:.2f}", f"{b['actual_usd_to_date']:.2f}") for b in budgets])


# ---------------------------------------------------------------------------------------------
# answer key and summary
# ---------------------------------------------------------------------------------------------

def measured_effect(ev, usage_rows_by_person_day: dict, people_by_id: dict, calendar: dict):
    """Mean weekday cost per affected person inside the window vs the 28 days before it (weekdays, non-holiday)."""
    if ev.starts_on > C.AS_OF:
        return None
    end = min(ev.ends_on or C.AS_OF, C.AS_OF - timedelta(days=1))
    if end < ev.starts_on:
        return None
    pids = ev.person_ids or [pid for pid, p in people_by_id.items() if (ev.scope == "company" or p.team_id in ev.team_ids)]

    def mean_over(start, stop, weekend=False):
        vals = []
        d = start
        while d <= stop:
            c = calendar.get(d)
            if c is not None and c.is_weekend == weekend and c.holiday is None and C.YEAR_START <= d < C.AS_OF:
                vals.append(sum(usage_rows_by_person_day.get((pid, d), 0.0) for pid in pids))
            d += timedelta(days=1)
        return statistics.mean(vals) if vals else None

    inside = mean_over(ev.starts_on, end, weekend=ev.kind == "incident")
    before = mean_over(ev.starts_on - timedelta(days=28), ev.starts_on - timedelta(days=1), weekend=ev.kind == "incident")
    if inside is None or not before:
        return None
    return inside / before


def write_answer_key(out: Path, *, teams, people, story, calendar, usage_rows) -> None:
    people_by_id = {p.id: p for p in people}
    team_name = {t.id: t.name for t in teams}
    by_pd = defaultdict(float)
    for r in usage_rows:
        by_pd[(r.person_id, r.day)] += r.cost_usd
    msgs = defaultdict(list)
    for m in story.messages:
        msgs[m.event_id].append(f"{m.id} ({INTEGRATION_LABEL[m.channel]}, {m.sent_at.strftime('%a %b %-d')})")
    for t in story.tasks:
        msgs[t.event_id].append(f"{t.id} ({INTEGRATION_LABEL[t.tool]}, {t.status_changed_at.strftime('%b %-d')})")
    lines = ["# Answer key: planted storylines", "",
             f"Dataset: {C.COMPANY_NAME}, {C.YEAR_START} to {C.AS_OF} (as-of, partial day). Seed {C.SEED}.", "",
             "Every event below is in `events` (SQLite), `csv/events.csv` and `frontend/context.json`; its evidence is in `messages` / `tasks`,",
             "`backend/corpus/*.md` and `frontend/documents.json`. 'Planted' is the multiplier the generator applied to the affected",
             "people's daily volume inside the window. 'Measured' is the ratio of mean weekday cost per affected group inside the window to the",
             "28 weekdays before it, computed from the generated data (so trend, noise, overlapping events and holidays are included).",
             "Events starting after the as-of date have no measurement; the synthetic truth for them is in `usage_daily_holdout`.", ""]
    for scope in ("company", "team", "person"):
        evs = [e for e in story.events if e.scope == scope]
        lines += [f"## {scope.title()}-level events ({len(evs)})", "",
                  "| Event | Kind | Window | Affects | Planted | Measured | Announced | Evidence |", "|---|---|---|---|---|---|---|---|"]
        for e in evs:
            who = "company" if scope == "company" and not e.person_ids else (", ".join(team_name[t] for t in e.team_ids) if not e.person_ids else
                  (", ".join(people_by_id[p].name for p in e.person_ids) if len(e.person_ids) <= 3 else f"{len(e.person_ids)} people in {', '.join(team_name[t] for t in e.team_ids)}"))
            planted = f"{e.multiplier:.2f}x"
            if e.weekend_multiplier is not None:
                planted += f", weekend {e.weekend_multiplier:.2f}"
            if e.model_override:
                planted += ", model mix override"
            if e.provider_shift:
                planted += ", provider shift " + ", ".join(f"{k} {v:+.2f}" for k, v in e.provider_shift.items())
            m = measured_effect(e, by_pd, people_by_id, calendar)
            measured = f"{m:.2f}x" if m else ("future" if e.future else "n/a")
            window = f"{e.starts_on} → {e.ends_on or 'open'}"
            lines.append(f"| {e.id}: {e.title} | {e.kind} | {window} | {who} | {planted} | {measured} | {e.announced_on} | {'; '.join(msgs.get(e.id, [])) or '-'} |")
        lines.append("")
    lines += ["## Calendar effects", "",
              "| Date | Name | Planted factor |", "|---|---|---|"]
    for d, (name, f) in sorted({**C.HOLIDAYS, **C.RECHARGE_DAYS}.items()):
        lines.append(f"| {d} ({d.strftime('%a')}) | {name} | {f:.2f} |")
    lines += ["", "Seasonal windows: " + "; ".join(f"{s} to {e} ×{f}" for s, e, f in C.SEASONAL), "",
              f"Weekend factor: per person, around the team value ({', '.join(f'{t.name} {t.weekend:.2f}' for t in teams)}), unless an event overrides it.", "",
              "## Model timeline", ""]
    for me in story.model_events:
        lines.append(f"- {me.announced_on} → effective {me.effective_on}: **{me.kind}** {me.provider} {', '.join(MODEL_LABEL[m] for m in me.model_ids)} — {json.dumps(me.details, default=str)}")
    lines += ["", "Model mix ramps linearly over %d days after each adoption date; price changes apply from the effective date." % C.RAMP_DAYS]
    (out / "ANSWER_KEY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_summary(out: Path, *, teams, people, story, calendar, usage_rows, seat_rows, holdout_rows, budgets, backend_ref, fe_stats, fc_stats, elapsed: float) -> str:
    team_name = {t.id: t.name for t in teams}
    total_tokens = sum(r.input_tokens + r.output_tokens for r in usage_rows)
    total_cost = sum(r.cost_usd for r in usage_rows) + sum(s.amount_usd for s in seat_rows)
    by_tq = defaultdict(float)
    for r in usage_rows:
        by_tq[(r.team_id, calendar[r.day].period_id)] += r.cost_usd
    for s in seat_rows:
        by_tq[(s.team_id, calendar[s.month].period_id)] += s.amount_usd
    daily = defaultdict(float)
    for r in usage_rows:
        daily[r.day] += r.input_tokens + r.output_tokens
    wk = [v for d, v in daily.items() if not calendar[d].is_weekend and calendar[d].holiday is None and d < C.AS_OF]
    we = [v for d, v in daily.items() if calendar[d].is_weekend and d < C.AS_OF]
    hol = [v for d, v in daily.items() if calendar[d].holiday is not None and not calendar[d].is_weekend]
    by_provider = defaultdict(float)
    for r in usage_rows:
        by_provider[r.provider] += r.cost_usd
    by_channel = defaultdict(int)
    for m in story.messages:
        by_channel[m.channel] += 1
    for t in story.tasks:
        by_channel[t.tool] += 1
    budget_q4 = {b["team_id"]: b["allocated_usd"] for b in budgets if b["period_id"] == "2026-Q4"}
    lines = [f"# {C.COMPANY_NAME} AI spend dataset — summary", "",
             f"Generated in {elapsed:.1f}s with seed {C.SEED}. Period {C.YEAR_START} to {C.AS_OF} (as-of; {C.AS_OF.strftime('%A')}, partial). All data is synthetic.", "",
             "| Metric | Value |", "|---|---|",
             f"| Teams | {len(teams)} |", f"| People | {len(people)} (joiners {sum(1 for p in people if p.start_date >= C.YEAR_START)}, leavers {sum(1 for p in people if p.end_date)}) |",
             f"| Usage rows (person × day × model × category) | {len(usage_rows):,} |", f"| Seat rows | {len(seat_rows):,} |",
             f"| Holdout truth rows (Oct 25 - Dec 31) | {len(holdout_rows):,} |",
             f"| Total tokens | {total_tokens / 1e9:.2f} B |", f"| Total charged spend | ${total_cost:,.0f} |",
             f"| Events / messages / tasks / model events | {len(story.events)} / {len(story.messages)} / {len(story.tasks)} / {len(story.model_events)} |",
             f"| Mean weekday tokens (non-holiday) | {statistics.mean(wk) / 1e6:.0f} M |", f"| Mean weekend tokens | {statistics.mean(we) / 1e6:.0f} M ({statistics.mean(we) / statistics.mean(wk):.0%} of weekday) |",
             f"| Mean weekday-holiday tokens | {statistics.mean(hol) / 1e6:.0f} M ({statistics.mean(hol) / statistics.mean(wk):.0%} of weekday) |",
             "", "## Spend by provider (charged, USD)", "", "| Provider | Spend |", "|---|---|"]
    for prov, v in sorted(by_provider.items(), key=lambda kv: -kv[1]):
        lines.append(f"| {prov} | ${v:,.0f} |")
    lines += ["", "## Spend by team and quarter (charged incl. seats, USD) with Q4 allocation", "", "| Team | Q1 | Q2 | Q3 | Q4 to date | Q4 allocation |", "|---|---|---|---|---|---|"]
    for t in teams:
        lines.append(f"| {t.name} | ${by_tq[(t.id, '2026-Q1')]:,.0f} | ${by_tq[(t.id, '2026-Q2')]:,.0f} | ${by_tq[(t.id, '2026-Q3')]:,.0f} | ${by_tq[(t.id, '2026-Q4')]:,.0f} | ${budget_q4[t.id]:,.0f} |")
    lines += ["", "## Evidence by channel", "", "| Channel | Items |", "|---|---|"]
    for ch, n in sorted(by_channel.items(), key=lambda kv: -kv[1]):
        lines.append(f"| {INTEGRATION_LABEL[ch]} | {n} |")
    lines += ["", "## Exports", "",
              f"- `uber_ai_spend.sqlite`: everything (tables: company, periods, teams, people, models, model_prices, model_events, calendar, projects, events, messages, tasks, usage_daily, usage_daily_holdout, seat_subscriptions, budgets; views team_daily, person_daily, company_daily, model_monthly).",
              f"- `backend/billing/*.csv` ({len(backend_ref['billing_files'])} half-month files in the `northstar_billing` import format), `backend/corpus/*.md` ({backend_ref['corpus_documents']} documents with front matter), `backend/reference.json` (periods, teams, mappings, budgets). Load with `datagen/load_backend.py`.",
              f"- `frontend/*.json`: company/teams/people/budgets, {fe_stats['spending_records']:,} per-person `SpendingRecord`s, {fe_stats['team_daily_records']:,} team-daily records, {fe_stats['documents']} `CompanyDocument`s, {fe_stats['context_items']} `ContextItem`s (contract shapes from `frontend/src/lib/contracts`).",
              f"- `forecasting/uber-observations.json` ({fc_stats['observations']:,} team-day observations), `uber-config.json`, `uber-holdout-truth.json` ({fc_stats['holdout_truth']:,} rows of synthetic future truth for scoring).",
              "- `csv/*.csv`: flat tables.", "- `ANSWER_KEY.md`: every planted storyline with its window, multiplier and measured effect."]
    text = "\n".join(lines) + "\n"
    (out / "SUMMARY.md").write_text(text, encoding="utf-8")
    return text
