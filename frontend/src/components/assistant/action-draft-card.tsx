"use client";
import { useEffect, useRef, useState } from "react";
import type { ForecastBundle, ForecastScenarioReceipt } from "@/lib/contracts";
import { useAppStore } from "@/lib/store";
import { getDataClient } from "@/lib/data";
import { completeScenario } from "@/lib/data/scenario-job";
import { buildScenarioDrivers, driverStart, editableParameters, validateAllocationDraft, type ActionDraft, type AllocationActionDraft, type ScenarioActionDraft } from "@/lib/planning-drafts";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { DateField } from "./date-field";
import { ScenarioPreview } from "./scenario-preview";

const exact = (value: number, unit: string) => new Intl.NumberFormat("en-US", unit === "usd" ? { style: "currency", currency: "USD", maximumFractionDigits: 2 } : { maximumFractionDigits: 2 }).format(value) + (unit === "usd" ? "" : ` ${unit}`);
export function ActionDraftCard({ draft, onChange, onReview }: { draft: ActionDraft; onChange?: (draft: ActionDraft) => void; onReview?: (id: string) => void }) {
  return draft.kind === "scenario" ? <ScenarioDraftCard key={`${draft.id}:${draft.revision ?? 1}`} initial={draft} onChange={onChange}/> : <AllocationDraftCard key={`${draft.id}:${draft.revision ?? 1}`} initial={draft} onChange={onChange} onReview={onReview}/>;
}

function ScenarioDraftCard({ initial, onChange }: { initial: ScenarioActionDraft; onChange?: (draft: ActionDraft) => void }) {
  const { forecastBundle, teams } = useAppStore();
  const [draft, setDraft] = useState(initial);
  const [baseline, setBaseline] = useState<ForecastBundle | undefined>(() => forecastBundle?.views.some(v => v.run_id === initial.parentRunId && v.scope.type === "company") ? structuredClone(forecastBundle) : undefined);
  const [result, setResult] = useState<ForecastBundle>();
  const [job, setJob] = useState<ForecastScenarioReceipt>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();
  const request = useRef(0);
  useEffect(() => {
    if (baseline) return;
    let active = true;
    getDataClient().getForecastViews({ run_id: initial.parentRunId }).then(bundle => {
      if (active) { if (!bundle.views.some(v => v.run_id === initial.parentRunId && v.scope.type === "company")) setError("The original forecast is unavailable. Reopen a plan from an issued forecast."); else setBaseline(bundle); }
    }).catch(e => { if (active) setError(e instanceof Error ? e.message : "Could not retrieve the original forecast."); });
    return () => { active = false; request.current += 1; };
  }, [baseline, initial.parentRunId]);
  const parent = baseline?.views.find(v => v.run_id === draft.parentRunId && v.scope.type === draft.scope.type && v.scope.id === draft.scope.id);
  const driver = baseline?.views.find(v => v.run_id === draft.parentRunId && v.scope.type === "company")?.included_drivers.find(d => d.id === draft.driverId);
  function edit(patch: Partial<ScenarioActionDraft>) {
    request.current += 1;
    const next = { ...draft, ...patch, revision: (draft.revision ?? 1) + 1 };
    setDraft(next); setResult(undefined); setJob(undefined); setError(undefined); onChange?.(next);
  }
  async function preview() {
    if (!baseline || !parent) return;
    const revision = ++request.current;
    setBusy(true); setError(undefined);
    try {
      const client = getDataClient();
      const drivers = buildScenarioDrivers(baseline, draft, teams.map(t => t.id));
      const response = job && job.status !== "failed" ? job : await client.previewForecastScenario(draft.parentRunId, drivers);
      const bundle = await completeScenario(response, draft.parentRunId, client, receipt => { if (request.current === revision) setJob(receipt); });
      if (request.current === revision) { setResult(bundle); setJob(undefined); }
    } catch (e) { if (request.current === revision) setError(e instanceof Error ? e.message : "Scenario preview failed."); }
    finally { if (request.current === revision) setBusy(false); }
  }
  return <section aria-label="Edit hypothetical plan" className="space-y-4 rounded-xl border border-border bg-card p-4">
    <header><p className="eyebrow">Draft what-if</p><h3 className="mt-1 text-sm font-medium">{draft.title}</h3><p className="mt-1 text-xs text-muted-foreground">{draft.scope.name ?? draft.scope.type} · Revision {draft.revision ?? 1} · UTC dates</p></header>
    {driver && <>
      <p className="text-xs text-muted-foreground">Current start: <time dateTime={driverStart(driver)}>{driverStart(driver) ?? "Not specified"}</time>{driver.kind === "project_schedule" ? ". The original project duration is preserved." : driver.effective_to ? ` · Ends ${driver.effective_to} (exclusive)` : ""}</p>
      <fieldset disabled={busy} className="space-y-3">
        <DateField label="Proposed start" value={draft.proposedStart} onChange={proposedStart => edit({ proposedStart })}/>
        <details className="text-xs"><summary className="cursor-pointer text-muted-foreground">More assumptions</summary><div className="mt-3 space-y-3">
          {driver.kind !== "project_schedule" && <DateField label="Proposed end (exclusive)" optional value={draft.proposedEnd ?? ""} min={draft.proposedStart} onChange={proposedEnd => edit({ proposedEnd: proposedEnd || null })}/>}
          {editableParameters(driver).map(field => <label key={field.key} className="block space-y-1.5"><span className="font-medium">{field.label}</span><Input type="number" min={field.min} max={field.max} step="any" value={String(draft.parameters?.[field.key] ?? driver.parameters?.[field.key] ?? "")} onChange={e => edit({ parameters: { ...draft.parameters, [field.key]: e.target.value === "" ? "" : Number(e.target.value) } })}/></label>)}
          {driver.kind === "membership" && <label className="block space-y-1.5"><span className="font-medium">Destination team</span><select aria-label="Destination team" className="h-9 w-full rounded-md border border-border bg-background px-2 text-sm" value={String(draft.parameters?.team_id ?? driver.parameters?.team_id ?? "")} onChange={e => edit({ parameters: { ...draft.parameters, team_id: e.target.value } })}>{teams.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}</select></label>}
          {driver.kind === "project_schedule" && <p className="text-muted-foreground">Original source window: {String(driver.parameters?.from_start)} to {String(driver.parameters?.from_end)} (end exclusive).</p>}
        </div></details>
      </fieldset>
    </>}
    {!driver && !error && <p className="text-xs text-muted-foreground">Loading the original plan…</p>}
    {error && <p role="alert" className="text-xs text-destructive">{error}</p>}
    {job && <p role="status" className="text-xs text-muted-foreground">Preview {job.status}. The published forecast is unchanged.</p>}
    <Button type="button" size="sm" disabled={busy || !driver || !parent} onClick={() => void preview()}>{busy ? "Previewing…" : job && job.status !== "failed" ? "Check preview" : "Preview impact"}</Button>
    <p className="text-xs text-muted-foreground">A preview changes assumptions only. It does not publish a forecast or apply a budget change.</p>
    {result && parent && <ScenarioPreview baseline={parent} scenario={result}/>}
  </section>;
}

function AllocationDraftCard({ initial, onChange, onReview }: { initial: AllocationActionDraft; onChange?: (draft: ActionDraft) => void; onReview?: (id: string) => void }) {
  const { teams, budgets, proposals, askAssistant } = useAppStore();
  const [draft, setDraft] = useState(initial);
  const [error, setError] = useState<string>();
  let summary: ReturnType<typeof validateAllocationDraft> | undefined;
  try { summary = validateAllocationDraft(draft, budgets); } catch { /* Show actionable validation when the user continues. */ }
  function edit(patch: Partial<AllocationActionDraft>) { const next = { ...draft, ...patch, revision: (draft.revision ?? 1) + 1 }; setDraft(next); setError(undefined); onChange?.(next); }
  function prepare() {
    try {
      const checked = validateAllocationDraft(draft, budgets);
      const from = teams.find(t => t.id === draft.sourceTeamId)?.name, to = teams.find(t => t.id === draft.destinationTeamId)?.name;
      if (!from || !to) throw new Error("Choose known source and destination teams.");
      const proposal = proposals.find(p => p.id === draft.proposalId);
      askAssistant(`Move ${exact(checked.amount, draft.unit)} from ${from} to ${to} for ${draft.period.start} through ${draft.period.end}. Keep the company budget unchanged. Prepare this transfer for review.`, {
        intent: "allocation", ...(draft.proposalId ? { selected_proposal_id: draft.proposalId, selected_proposal_version: proposal?.version } : {}), period: draft.period.label ?? `${draft.period.start} to ${draft.period.end}`,
      });
    } catch (e) { setError(e instanceof Error ? e.message : "Check the transfer details."); }
  }
  return <section aria-label="Edit budget transfer" className="space-y-3 rounded-xl border border-border bg-card p-4">
    <header><p className="eyebrow">Draft budget transfer</p><p className="mt-1 text-xs text-muted-foreground">{draft.period.label ?? `${draft.period.start} to ${draft.period.end}`}</p></header>
    <div className="grid grid-cols-2 gap-3">{([ ["sourceTeamId", "From"], ["destinationTeamId", "To"] ] as const).map(([key, label]) => <label key={key} className="space-y-1.5 text-xs"><span>{label}</span><select className="h-9 w-full rounded-md border border-border bg-background px-2 text-sm" value={draft[key]} onChange={e => edit({ [key]: e.target.value })}><option value="">Choose team</option>{teams.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}</select></label>)}</div>
    <label className="block space-y-1.5 text-xs"><span>Amount ({draft.unit.toUpperCase()})</span><Input inputMode="decimal" value={draft.amount} onChange={e => edit({ amount: e.target.value })}/></label>
    <p className="text-xs font-medium">Company budget change: {exact(0, draft.unit)}</p>
    {summary && <p className="text-xs text-muted-foreground">Source: {exact(summary.sourceBefore, draft.unit)} → {exact(summary.sourceAfter, draft.unit)}. Destination: {exact(summary.destinationBefore, draft.unit)} → {exact(summary.destinationAfter, draft.unit)}.</p>}
    {error && <p role="alert" className="text-xs text-destructive">{error}</p>}
    <Button size="sm" type="button" onClick={prepare}>Continue in Droid Assistant</Button>
    {draft.proposalId && draft.revision === initial.revision && onReview && <Button variant="outline" size="sm" onClick={() => onReview(draft.proposalId!)}>Review existing proposal</Button>}
    <p className="text-xs text-muted-foreground">Finance must review and apply a proposal before allocations change.</p>
  </section>;
}
