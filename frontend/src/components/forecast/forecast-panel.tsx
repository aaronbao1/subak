"use client";
import { useState } from "react";
import Link from "next/link";
import { Area, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { MessageSquare, RefreshCw } from "lucide-react";
import { useAppStore } from "@/lib/store";
import { completeScenario } from "@/lib/data/scenario-job";
import { getDataClient } from "@/lib/data";
import type { ForecastBundle, ForecastDriver, ForecastEvidence, ForecastScenarioReceipt } from "@/lib/contracts";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { evidenceDrivers, finite, forecastPrompt, historicalRange, omissionDrivers, pointRange, scopeView, selectedDriverForView, sumPointBases } from "@/components/dashboard/forecast-derive";

const dates = (a?: string, b?: string) => `${a?.slice(0, 10) ?? "Unknown"} → ${b?.slice(0, 10) ?? "Unknown"} (end exclusive)`;
const money = (v: unknown, unit: string) => finite(v) === undefined ? "Unavailable" : `${unit.toUpperCase()} ${new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 }).format(v as number)}`;
const label = (d: ForecastDriver) => d.title ?? d.kind?.replaceAll("_", " ") ?? d.id;
const json = (v: unknown) => JSON.stringify(v, null, 2);
const terminal = (s?: string) => !["pending", "queued", "running"].includes(s ?? "");

/** All scopes read one immutable run. Preview state never enters the publication store. */
export function ForecastPanel({ scopeType = "company", scopeId }: { scopeType?: "company" | "team" | "person"; scopeId?: string }) {
  const { forecastBundle, forecastEvidence, forecastError, forecastRefresh, refreshForecast, askForecastAssistant, people } = useAppStore();
  const [horizon, setHorizon] = useState<"daily" | "weekly">("daily");
  const [band, setBand] = useState<"scenario" | "error">("scenario");
  const [errorLevel, setErrorLevel] = useState<"80" | "95">("80");
  const [driverSelection, setDriverSelection] = useState<{ driver: ForecastDriver; runId: string; scopeType: string; scopeId: string | null }>();
  const [preview, setPreview] = useState<{ sourceRun: string; bundle: ForecastBundle; omitted: string }>();
  const [previewJob, setPreviewJob] = useState<{ sourceRun: string; omitted: string; receipt: ForecastScenarioReceipt }>();
  const [previewBusy, setPreviewBusy] = useState(false);
  const [previewError, setPreviewError] = useState<string>();
  const [explanation, setExplanation] = useState<{ run: string; value: Record<string, unknown> }>();
  const issued = scopeView(forecastBundle, scopeType, scopeId);
  const validPreview = preview?.sourceRun === issued?.run_id ? preview : undefined;
  const validPreviewJob = previewJob?.sourceRun === issued?.run_id ? previewJob : undefined;
  const view = validPreview ? scopeView(validPreview.bundle, scopeType, scopeId) : issued;
  const selectedDriver = selectedDriverForView(driverSelection, issued);

  async function previewWithout(driver: ForecastDriver) {
    if (!issued) return;
    setPreviewBusy(true); setPreviewError(undefined);
    try {
      const client = getDataClient();
      const existing = validPreviewJob?.omitted === driver.id && validPreviewJob.receipt.status !== "failed" ? validPreviewJob.receipt : undefined;
      const response = existing ?? await client.previewForecastScenario(issued.run_id, omissionDrivers(forecastBundle, issued, driver.id));
      const bundle = await completeScenario(response, issued.run_id, client, receipt => setPreviewJob({ sourceRun: issued.run_id, omitted: driver.id, receipt }));
      setPreviewJob(undefined);
      setPreview({ sourceRun: issued.run_id, bundle, omitted: driver.id });
    } catch (e) { setPreviewError(e instanceof Error ? e.message : "Scenario preview failed."); }
    finally { setPreviewBusy(false); }
  }
  async function openDriver(driver: ForecastDriver) {
    if (!issued) return;
    setDriverSelection({ driver, runId: issued.run_id, scopeType: issued.scope.type, scopeId: issued.scope.id });
    try { setExplanation({ run: issued.run_id, value: await getDataClient().getForecastExplanation(issued.run_id) }); }
    catch { setExplanation({ run: issued.run_id, value: { unavailable: "Calculation explanation could not be retrieved. The cited publication remains visible." } }); }
  }

  if (issued && validPreview && !view) return <section aria-label="Scenario preview" className="space-y-3 rounded-xl border border-border bg-card p-5"><h2 className="text-sm font-medium">Scenario scope unavailable</h2><p className="text-xs text-muted-foreground">The isolated scenario omitting {validPreview.omitted} no longer contains {issued.scope.name ?? issued.scope.id}. No value is inferred. Issued run {issued.run_id} remains available.</p><Button size="sm" variant="outline" onClick={() => setPreview(undefined)}>Return to issued forecast</Button></section>;

  if (!issued || !view) return <section aria-label="Published forecast" className="rounded-xl border border-border bg-card p-5">
    <div className="flex items-center justify-between gap-3">
      <h2 className="text-sm font-medium">Published forecast</h2>
      <Button size="sm" variant="outline" disabled={!terminal(forecastRefresh?.status)} onClick={() => void refreshForecast()}><RefreshCw className="size-3" /> Refresh forecast</Button>
    </div>
    <p className="mt-3 text-sm text-muted-foreground">
      {forecastError ?? "No forecast has been published for this scope. Refresh to create an immutable run."}
    </p>
    <p className="mt-2 text-xs text-muted-foreground" role="status">
      {forecastRefresh && `Refresh ${forecastRefresh.id}: ${forecastRefresh.status}`}
    </p>
    {scopeType === "company" && <EvidenceProcessing evidence={forecastEvidence} includeDrivers />}
  </section>;

  const unit = view.target.unit;
  const pub = issued.publication ?? {};
  const points = view[horizon];
  const quarter = view.quarter_outlook;
  const effects = issued.driver_effects ?? forecastBundle?.driver_effects ?? [];
  const selectedEffect = effects.find(e => e.driver_id === selectedDriver?.id);
  const rows = evidenceDrivers(issued, forecastEvidence).filter(({ driver, status }) => {
    if (scopeType === "company" || status === "Included") return true;
    const scope = driver.scope as Record<string, unknown> | undefined;
    if (!scope || (!scope.team_id && !scope.person_id)) return true;
    if (scope?.[`${scopeType}_id`] === scopeId) return true;
    return scopeType === "team" ? people.some(p => p.id === scope.person_id && p.teamId === scopeId) : people.some(p => p.id === scopeId && p.teamId === scope.team_id);
  });
  const active = rows.filter(r => r.status === "Included");
  const chart = view.cumulative.map(p => {
    const scenario = pointRange(p);
    const error = historicalRange(p, errorLevel);
    return { ...p, date: p.date ?? p.end, scenario, error };
  });
  const historicalSummary = view.historical_error_interval?.[errorLevel];
  const hasScenario = chart.some(p => p.scenario);
  const hasError = chart.some(p => p.error);
  const totalWeeks = sumPointBases(view.weekly);
  const sharedViews = forecastBundle?.views.filter(v => v.scope.type === "shared") ?? [];

  return <section aria-label="Published forecast" className="space-y-5 rounded-xl border border-border bg-card p-5">

    <header className="flex flex-wrap items-start justify-between gap-3">

      <div className="space-y-1">
        <h2 className="text-sm font-medium">{scopeType === "company" ? "Company" : issued.scope.name ?? scopeType} forecast</h2>
        <p className="text-xs text-muted-foreground">Issued {String(pub.generated_at ?? issued.generated_at ?? "unknown")} · {view.timezone ?? "UTC"}</p>
        <p className="break-all font-mono text-[10px] text-muted-foreground">Run {issued.run_id} · evidence cutoff {String(pub.information_cutoff ?? issued.information_cutoff ?? "unknown")}</p>
      </div>

      <div className="flex flex-wrap gap-2">
        <Button size="sm" variant="outline" onClick={() => askForecastAssistant(forecastPrompt(issued), { action: "explain", run_id: issued.run_id, scope_type: issued.scope.type, scope_id: issued.scope.id })}><MessageSquare className="size-3" /> Ask Droid</Button>
        <Button size="sm" variant="outline" disabled={!terminal(forecastRefresh?.status)} onClick={() => void refreshForecast()}><RefreshCw className="size-3" /> Refresh forecast</Button>
      </div>

    </header>

    {(view.is_synthetic || issued.procedure_version === "synthetic-ui-fixture" || issued.limitations.some(l => l.toLowerCase().includes("synthetic"))) && <p className="rounded-md border border-dashed px-3 py-2 text-xs text-muted-foreground">Synthetic demo · scenario envelopes are descriptive assumptions, never evidence of enterprise accuracy.</p>}

    <p className="text-xs text-muted-foreground">Weekly publication: Monday 00:00 UTC. Manual refresh publishes a new run.</p>

    {forecastBundle?.current_actuals && <p className="text-xs text-muted-foreground">{forecastBundle.current_actuals.status === "unavailable" ? String(forecastBundle.current_actuals.reason ?? "Current actuals are unavailable. The issued forecast is unchanged.") : <>Current actuals received through {String(forecastBundle.current_actuals.as_of ?? "unknown")}; complete through {String(forecastBundle.current_actuals.history_complete_through ?? "unknown")}. Shown separately from the frozen issued forecast.</>}</p>}

    {forecastRefresh && <p className="text-xs text-muted-foreground" role="status">Refresh {forecastRefresh.id}: {forecastRefresh.status}. Issued runs remain immutable.</p>}

    {forecastError && <p role="alert" className="text-xs text-destructive">
      {forecastError}
    </p>}

    {validPreviewJob && !validPreview && <div className="space-y-2 rounded-md border border-border p-3 text-xs" role="status"><p>Isolated scenario {validPreviewJob.receipt.scenario_id}: {validPreviewJob.receipt.status}. Published run {issued.run_id} remains visible.</p>{previewError && <p className="text-destructive">{previewError}</p>}{!previewBusy && <Button size="sm" variant="outline" onClick={() => { const driver = issued.included_drivers.find(d => d.id === validPreviewJob.omitted); if(driver) void previewWithout(driver); }}>{validPreviewJob.receipt.status === "failed" ? "Retry preview" : "Check scenario status"}</Button>}</div>}

    {validPreview && <div className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-warning/30 p-3 text-xs">
      <p>Isolated scenario preview · omits {validPreview.omitted}. Published run {issued.run_id} is unchanged.</p>
      <Button size="sm" variant="outline" onClick={() => setPreview(undefined)}>Return to issued forecast</Button>
    </div>}

    <dl className="grid gap-4 sm:grid-cols-3">
      <Metric label="Four calendar weeks" value={money(totalWeeks, unit)} note={dates(view.weekly[0]?.start, view.weekly.at(-1)?.end)} />
      <Metric label="Conditional quarter outlook" value={money(quarter?.base, unit)} note={`${dates(String(quarter?.start ?? ""), String(quarter?.end ?? ""))}${quarter?.complete === false ? " · incomplete" : ""}`} />
      <Metric label="Historical error interval" value={hasError ? "Available" : "Unavailable"} note={hasError ? "Separate from the scenario envelope" : "Insufficient matching mature issued outcomes; no coverage claim."} />
    </dl>

    <div className="space-y-3 border-t border-border pt-4">

      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="text-xs font-medium">Cumulative spending fan · includes recorded quarter spend</h3>
        <div className="flex gap-2">
          <Choice selected={band === "scenario"} onClick={() => setBand("scenario")}>Scenario envelope</Choice>
          <Choice selected={band === "error"} onClick={() => setBand("error")}>Historical error</Choice>
          {band === "error" && <><Choice selected={errorLevel === "80"} onClick={() => setErrorLevel("80")}>80%</Choice><Choice selected={errorLevel === "95"} onClick={() => setErrorLevel("95")}>95%</Choice></>}
        </div>
      </div>

      <p className="text-xs text-muted-foreground">
        {band === "scenario" ? hasScenario ? "Low/base/high joint assumptions, summed before pricing summary. Descriptive spending envelope; no confidence or coverage level." : "Scenario envelope unavailable: insufficient supported bounds or history. Base values are shown where available." : hasError ? "Empirical error interval from matching mature publications. It is independent of the scenario envelope." : "Historical error interval unavailable. Synthetic history and inferred assumptions do not establish calibration."}
      </p>

      {band === "scenario" && view.scenario_range?.complete === false && <p className="text-xs text-muted-foreground">Partial scenario envelope, conditional on base rates: supported driver bounds are included, but unavailable rate uncertainty is omitted. See the published limitations.</p>}
      {band === "error" && historicalSummary && <p className="text-xs text-muted-foreground">Cumulative calibration: n={historicalSummary.n ?? 0}, rank={historicalSummary.rank ?? "unavailable"}; {dates(historicalSummary.calibration_start ?? undefined, historicalSummary.calibration_end ?? undefined)}. {historicalSummary.qualification}{historicalSummary.is_synthetic && " Synthetic demonstration only."}</p>}
      <div className="h-60 w-full min-w-0" role="img" aria-label={`Cumulative spending with ${band === "scenario" ? "descriptive scenario envelope" : "historical error interval"}`}>
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={chart} margin={{ top: 8, right: 12, left: 0, bottom: 4 }}>
            <CartesianGrid stroke="var(--border)" vertical={false} />
            <XAxis dataKey="date" tickFormatter={v => String(v).slice(5, 10)} tick={{ fontSize: 10 }} minTickGap={35} />
            <YAxis tick={{ fontSize: 10 }} width={65} />
            <Tooltip formatter={(v) => Array.isArray(v) ? v.map(x => money(x, unit)).join(" to ") : money(v, unit)} />
            {band === "scenario" && hasScenario && <Area dataKey="scenario" name="Descriptive scenario envelope" stroke="none" fill="var(--chart-1)" fillOpacity={0.2} connectNulls={false} />}
            {band === "error" && hasError && <Area dataKey="error" name={`Historical error interval (${errorLevel}%)`} stroke="none" fill="var(--chart-2)" fillOpacity={0.2} connectNulls={false} />}
            <Line dataKey="base" name={validPreview ? "Scenario preview base" : "Issued base"} type="linear" dot={false} stroke="var(--foreground)" strokeWidth={2} connectNulls={false} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

    </div>

    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="text-xs font-medium">Same issued paths · {horizon === "daily" ? "7 daily details from publication" : "4 calendar weeks (first may be partial)"}</h3>
        <div className="flex gap-2">
          <Choice selected={horizon === "daily"} onClick={() => setHorizon("daily")}>7 daily</Choice>
          <Choice selected={horizon === "weekly"} onClick={() => setHorizon("weekly")}>4 weekly</Choice>
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead className="text-muted-foreground">
            <tr>
              <th className="py-2 font-normal">UTC dates</th>
              <th className="font-normal">Base</th>
              <th className="font-normal">{band === "scenario" ? "Scenario envelope" : `Historical error (${errorLevel}%)`}</th>
              <th className="font-normal">Coverage</th>
            </tr>
          </thead>
          <tbody>
            {points.map((p, i) => <tr key={p.date ?? p.start ?? i} className="border-t border-border">
              <td className="py-2 pr-3">
                {p.date ?? dates(p.start, p.end)}
                {p.partial === true && " · partial bucket"}
              </td>
              <td className="pr-3 tabular-nums">
                {money(p.base, unit)}
              </td>
              <td className="pr-3 tabular-nums">
                {(band === "scenario" ? pointRange(p) : historicalRange(p,errorLevel))?.map(v => money(v, unit)).join(" – ") ?? "Unavailable"}
              </td>
              <td>
                {p.complete === false ? "Incomplete inputs" : "Covered inputs"}
                {horizon === "weekly" && p.start && p.partial === true && " · partial forecast week"}
              </td>
            </tr>)}
          </tbody>
        </table>
      </div>
    </div>

    {quarter && <div className="space-y-2 border-t border-border pt-4">
      <h3 className="text-xs font-medium">Conditional quarter continuation · separate from four weeks</h3>
      <p className="text-xs text-muted-foreground">
        {(Array.isArray(quarter.assumptions) ? quarter.assumptions : []).map(String).join(" · ") || "Continues the published weekday, exposure, schedule, mix and supported tariff assumptions through quarter end."}
      </p>
      <p className="text-xs text-muted-foreground">Recorded {money(view.components?.recorded, unit)} · late {money(view.components?.late, unit)} · future {money(view.components?.future, unit)} · fixed {money(view.components?.fixed, unit)}</p>
    </div>}

    {scopeType === "company" && <div className="space-y-2 border-t border-border pt-4">
      <h3 className="text-xs font-medium">Scope reconciliation · same issued run</h3>
      <p className="text-xs text-muted-foreground">Team and person views use these same paths. Each shared residual is used only in its specified people or team rollup; it is preserved for reconciliation.</p>
      <div className="flex flex-wrap gap-2">
        {forecastBundle?.views.filter(v => v.scope.type === "team").map(v => <Link key={v.scope.id} href={`/teams/${v.scope.id}`} className="rounded-md border px-3 py-2 text-xs hover:bg-muted">{v.scope.name ?? v.scope.id} · {money(v.quarter_outlook?.base, unit)}</Link>)}
        {sharedViews.map(shared => <span key={shared.scope.id} className="rounded-md border border-dashed px-3 py-2 text-xs">{shared.scope.name ?? "Shared / unattributed"} · {money(shared.quarter_outlook?.base, unit)}</span>)}
      </div>
    </div>}

    <div className="space-y-3 border-t border-border pt-4">
      <h3 className="text-xs font-medium">What changed · evidence and inclusion</h3>
      <div className="flex flex-wrap gap-2">
        {active.slice(0, 2).map(({ driver }) => <button key={driver.id} className="rounded-full border border-border bg-muted/30 px-3 py-1.5 text-left text-xs hover:bg-muted" onClick={() => void openDriver(driver)}>Included · {label(driver)}</button>)}
      </div>
      {rows.length === 0 ? <p className="text-xs text-muted-foreground">No supported drivers are included in this run.</p> : <ul className="divide-y divide-border">
        {rows.map(({ driver, status }) => <li key={driver.id}>
          <button className="flex w-full items-start justify-between gap-3 py-2.5 text-left text-xs hover:text-foreground/70" onClick={() => void openDriver(driver)}>
            <span className="min-w-0">
              <span className="font-medium">
                {label(driver)}
              </span>
              <span className="mt-1 block text-muted-foreground">
                {String(driver.publication_reason ?? driver.reason ?? (status === "Included" ? "Used in this immutable publication" : status === "Queued" ? "Arrived after publication; waits for refresh" : "Does not change forecast numbers"))}
              </span>
            </span>
            <span className="shrink-0 rounded-md border px-2 py-1">
              {status}
            </span>
          </button>
        </li>)}
      </ul>}
    </div>

    {scopeType === "company" && <EvidenceProcessing evidence={forecastEvidence} />}

    {view.limitations.length > 0 && <details className="border-t border-border pt-3 text-xs">
      <summary className="cursor-pointer text-muted-foreground">Assumptions and limitations ({view.limitations.length})</summary>
      <ul className="mt-2 list-disc space-y-1 pl-4 text-muted-foreground">
        {view.limitations.map((l, i) => <li key={i}>
          {l}
        </li>)}
      </ul>
    </details>}

    <Sheet open={!!selectedDriver} onOpenChange={open => { if (!open) setDriverSelection(undefined); }}>
      <SheetContent side="right" className="w-full overflow-y-auto sm:max-w-lg">
        <SheetHeader className="pr-10">
          <SheetTitle>
            {selectedDriver ? label(selectedDriver) : "Forecast evidence"}
          </SheetTitle>
          <SheetDescription>Source passage, numerical transformation and paired effect for run {issued.run_id}.</SheetDescription>
        </SheetHeader>
        {selectedDriver && <div className="space-y-5 px-4 pb-6 text-xs">
          <p className="text-muted-foreground">Driver {selectedDriver.id} · {selectedDriver.source_id ?? "source unavailable"} revision {selectedDriver.source_revision ?? "unknown"}</p>
          <p>
            {String(selectedDriver.publication_reason ?? selectedDriver.reason ?? "")}
          </p>
          <p>Effective {dates(selectedDriver.effective_from, selectedDriver.effective_to ?? undefined)}</p>
          <h4 className="font-medium">Cited source passages</h4>
          {(selectedDriver.citations ?? []).map((citation, i) => <blockquote key={i} className="space-y-2 border-l-2 border-border pl-3 text-muted-foreground">
            <p>
              {String(citation.excerpt ?? citation.quote ?? citation.text ?? "No passage supplied")}
            </p>
            <footer>{String(citation.title ?? citation.source_id ?? selectedDriver.source_id ?? "Source")} · {String(citation.locator ?? citation.available_at ?? "")}</footer>
          </blockquote>)}
          {!selectedDriver.citations?.length && <p className="text-muted-foreground">No cited source passage is available.</p>}
          <h4 className="font-medium">Numerical parameters</h4>
          <pre className="overflow-x-auto rounded-md bg-muted/30 p-3 text-[11px]">
            {json(selectedDriver.parameters ?? {})}
          </pre>
          <h4 className="font-medium">Paired omission effect · {issued.scope.name ?? scopeType} conditional quarter</h4>
          <p>
            {selectedEffect?.available ? `${money(selectedEffect.base_delta, unit)} with this driver compared with its omission. With ${money(selectedEffect.with_base, unit)}; without ${money(selectedEffect.without_base, unit)}.` : "Unavailable for this driver. No numerical effect is inferred from a source mention."}
          </p>
          <p className="text-muted-foreground">
            {selectedEffect?.qualification ?? "Paired reruns use common randomness. Interacting driver effects need not add to the total change."}
          </p>
          <div className="flex flex-wrap gap-2">
            {issued.included_drivers.some(d => d.id === selectedDriver.id) || issued.queued_changes.some(d => d.id === selectedDriver.id)
              ? <Button variant="outline" size="sm" onClick={() => { askForecastAssistant(forecastPrompt(issued, selectedDriver), { action: "explain", run_id: issued.run_id, scope_type: issued.scope.type, scope_id: issued.scope.id, driver_id: selectedDriver.id }); setDriverSelection(undefined); }}>Ask Droid about this driver</Button>
              : <p className="text-muted-foreground">This evidence is not in the issued snapshot. Refresh before asking Droid about its effect on a published run.</p>}
            {issued.included_drivers.some(d => d.id === selectedDriver.id) && <Button variant="outline" size="sm" disabled={previewBusy} onClick={() => void previewWithout(selectedDriver)}>
              {previewBusy ? "Calculating…" : validPreviewJob?.omitted === selectedDriver.id ? validPreviewJob.receipt.status === "failed" ? "Retry preview" : "Check scenario status" : "Preview without this driver"}
            </Button>}
          </div>
          {previewError && <p role="alert" className="text-destructive">
            {previewError}
          </p>}
          {validPreview && <p role="status">Scenario preview ready. Close this drawer to inspect it; published numbers are unchanged.</p>}
          <details>
            <summary className="cursor-pointer text-muted-foreground">Source calculation record</summary>
            <pre className="mt-2 max-h-96 overflow-auto whitespace-pre-wrap rounded-md bg-muted/30 p-3 text-[10px]">
              {json(explanation?.run === issued.run_id ? explanation.value : { status: "Loading issued explanation…" })}
            </pre>
          </details>
        </div>}
      </SheetContent>
    </Sheet>

  </section>;
}
function EvidenceProcessing({ evidence, includeDrivers = false }: { evidence: ForecastEvidence[]; includeDrivers?: boolean }) {
  const items = evidence.filter(item => includeDrivers || !item.drivers?.length);
  if (!items.length) return null;
  return <div className="mt-4 space-y-2 border-t border-border pt-3 text-xs" aria-label="Evidence processing">
    <h3 className="font-medium">Evidence processing</h3>
    <ul className="space-y-3">
      {items.map((item, index) => {
        const envelope = item.envelope as Record<string, unknown> | undefined;
        return <li key={item.id ?? item.source_id ?? index}>
          <p>{String(item.source_id ?? envelope?.source_id ?? item.id ?? "Source")} · {String(item.status ?? item.queue_status ?? "received")}</p>
          {typeof item.last_error === "string" && <p className="mt-1 text-destructive">{item.last_error}</p>}
          {item.drivers?.map(driver => <p key={driver.id} className="mt-1 text-muted-foreground">{label(driver)} · {driver.status === "context_only" ? "Context only" : "Queued"}</p>)}
          {!item.drivers?.length && <p className="mt-1 text-muted-foreground">No numerical driver is available from this evidence. The issued forecast is unchanged.</p>}
        </li>;
      })}
    </ul>
  </div>;
}
function Choice({ selected, onClick, children }: { selected: boolean; onClick: () => void; children: React.ReactNode }) {
  return <button aria-pressed={selected} onClick={onClick} className={`rounded-md border px-2.5 py-1.5 text-xs ${selected ? "border-foreground/30 bg-muted text-foreground" : "border-border text-muted-foreground"}`}>
    {children}
  </button>;
}
function Metric({ label, value, note }: { label: string; value: string; note?: string }) {
  return <div className="min-w-0">
    <dt className="text-xs text-muted-foreground">
      {label}
    </dt>
    <dd className="mt-1 text-xl font-medium tabular-nums">
      {value}
    </dd>
    <dd className="mt-1 text-[11px] text-muted-foreground">
      {note}
    </dd>
  </div>;
}
