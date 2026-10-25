"use client";
import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import type { ForecastBundle, ForecastDriver } from "@/lib/contracts";
import { useAppStore } from "@/lib/store";
import { getDataClient } from "@/lib/data";
import { createScenarioDraft, type ScenarioActionDraft } from "@/lib/planning-drafts";
import { PlanningCalendar } from "@/components/forecast/planning-calendar";
import { ActionDraftCard } from "@/components/assistant/action-draft-card";

export default function PlanningPage() {
  const { forecastBundle, forecastEvidence, loaded, teams, people } = useAppStore();
  const search = useSearchParams();
  const requestedRun = search.get("run") ?? undefined;
  const [historic, setHistoric] = useState<ForecastBundle>();
  const [error, setError] = useState<string>();
  const [scope, setScope] = useState(() => {
    const type = search.get("scope") ?? search.get("scope_type") ?? (search.get("team") ? "team" : "company");
    const id = search.get("scopeId") ?? search.get("scope_id") ?? search.get("team");
    return type !== "company" && id ? `${type}:${id}` : "company";
  });
  const [selected, setSelected] = useState<ScenarioActionDraft>();
  const requestedDriver = search.get("driver");
  const currentMatches = !requestedRun || forecastBundle?.views.some(v => v.run_id === requestedRun);
  const bundle = currentMatches ? forecastBundle : historic;
  const view = bundle?.views.find(v => (!requestedRun || v.run_id === requestedRun) && (scope === "company" ? v.scope.type === "company" : `${v.scope.type}:${v.scope.id}` === scope));
  useEffect(() => {
    if (!requestedRun || currentMatches) return;
    let active = true;
    getDataClient().getForecastViews({ run_id: requestedRun }).then(data => { if (active) setHistoric(data); }).catch(e => { if (active) setError(e instanceof Error ? e.message : "Could not load this publication."); });
    return () => { active = false; };
  }, [requestedRun, currentMatches]);
  const linkedDriver = view?.included_drivers.find(d => d.id === requestedDriver);
  const draft = selected ?? (view && linkedDriver ? createScenarioDraft(view, linkedDriver) : undefined);
  const shownDraft = draft && draft.parentRunId === view?.run_id && draft.scope.type === view.scope.type && draft.scope.id === view.scope.id ? draft : undefined;
  const select = (driver: ForecastDriver) => { if (view) setSelected(createScenarioDraft(view, driver)); };
  return <>
    <header className="flex flex-wrap items-start justify-between gap-4"><div><p className="eyebrow">Planning</p><h1 className="mt-2 text-2xl font-semibold tracking-tight">Try a change before committing</h1><p className="mt-2 max-w-2xl text-sm text-muted-foreground">Explore a project date or workload assumption against the published forecast.</p></div><Link href="/overview" className="text-xs text-muted-foreground underline underline-offset-4">Back to overview</Link></header>
    <div className="flex flex-wrap items-center gap-3"><label className="flex items-center gap-2 text-xs text-muted-foreground">Scope<select aria-label="Planning scope" className="h-9 rounded-md border border-border bg-card px-3 text-sm text-foreground" value={scope} onChange={e => { setScope(e.target.value); setSelected(undefined); }}><option value="company">Company</option><optgroup label="Teams">{teams.map(t => <option key={t.id} value={`team:${t.id}`}>{t.name}</option>)}</optgroup><optgroup label="People">{people.map(p => <option key={p.id} value={`person:${p.id}`}>{p.name}</option>)}</optgroup></select></label>{view && <p className="text-xs text-muted-foreground">{String(view.quarter_outlook?.start ?? "")} to {String(view.quarter_outlook?.end ?? "")} · end exclusive</p>}</div>
    {error && <p role="alert" className="rounded-lg border border-destructive/30 p-4 text-sm text-destructive">{error}</p>}
    {view ? <div className="grid items-start gap-5 lg:grid-cols-[1.1fr_1fr]"><PlanningCalendar view={view} evidence={forecastEvidence} onSelect={select}/><div className="space-y-4">{shownDraft ? <ActionDraftCard key={shownDraft.id} draft={shownDraft}/> : <section className="rounded-xl border border-dashed border-border px-6 py-10"><h2 className="text-sm font-medium">Choose a plan to explore</h2><p className="mt-2 text-sm text-muted-foreground">Select a published assumption from Upcoming changes. You can edit dates and supported assumptions, then compare a separate preview.</p><p className="mt-3 text-xs text-muted-foreground">Source context without a modeled assumption can be inspected in Evidence.</p><Link href="/evidence" className="mt-4 inline-block text-xs underline underline-offset-4">View evidence</Link></section>}</div></div> : <p className="rounded-xl border border-border bg-card p-6 text-sm text-muted-foreground">{loaded && currentMatches ? "No issued forecast is available for this scope. Update the forecast from Overview to begin planning." : "Loading the selected publication…"}</p>}
  </>;
}
