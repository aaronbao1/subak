"use client";
import { useState } from "react";
import Link from "next/link";
import { BarRow } from "@/components/dashboard/bars";
import { BulletBar } from "@/components/team/viz";
import { Area, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { MessageSquare, RefreshCw } from "lucide-react";
import { useAppStore } from "@/lib/store";
import { completeScenario } from "@/lib/data/scenario-job";
import { getDataClient } from "@/lib/data";
import type { ForecastBundle, ForecastDriver, ForecastEvidence, ForecastPoint, ForecastScenarioReceipt, ForecastView } from "@/lib/contracts";
import type { ForecastDriverEffect } from "@/lib/contracts/forecast-view";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { evidenceDrivers, finite, forecastPrompt, historicalRange, omissionDrivers, pointRange, rangeStatus, scopeView, selectedDriverForView, sumPointBases } from "@/components/dashboard/forecast-derive";
import { AccuracyMeter, ColumnStrip, Meter, RangeBand, SignedBar, Swatch, amount, exact } from "./forecast-visuals";

const dates = (a?: string, b?: string) => `${a?.slice(0, 10) ?? "Unknown"} → ${b?.slice(0, 10) ?? "Unknown"} (end exclusive)`;
const short = (d?: string) => d ? new Date(`${d.slice(0, 10)}T00:00:00Z`).toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" }) : "—";
const label = (d: ForecastDriver) => d.title ?? d.kind?.replaceAll("_", " ") ?? d.id;
const json = (v: unknown) => JSON.stringify(v, null, 2);
const terminal = (s?: string) => !["pending", "queued", "running"].includes(s ?? "");
/** One readable line from a transport error, keeping its reason. */
const reasonLine = (e?: string) => {
  if (!e) return undefined;
  const http = e.match(/→\s*(\d{3})/);
  if (http) return `service returned ${http[1]}`;
  if (/failed to fetch|network/i.test(e)) return "service unreachable";
  return e;
};
const TOP = 5;

/** All scopes read one immutable run. Preview state never enters the publication store. */
export function ForecastPanel({ scopeType = "company", scopeId, embedded = false }: {
  scopeType?: "company" | "team" | "person";
  scopeId?: string;
  /** The page header already shows the quarter projection: omit the outlook figure, its bullet bar and the person share meter. */
  embedded?: boolean;
}) {
  const { forecastBundle, forecastEvidence, forecastError, forecastRefresh, refreshForecast, askForecastAssistant, people, budgets, teams } = useAppStore();
  const [band, setBand] = useState<"scenario" | "error">();
  const [errorLevel, setErrorLevel] = useState<"80" | "95">("80");
  const [showAll, setShowAll] = useState(false);
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
  const refreshing = !terminal(forecastRefresh?.status);

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

  const refreshButton = <Button size="sm" variant="ghost" disabled={refreshing} onClick={() => void refreshForecast()} aria-label="Refresh forecast"><RefreshCw className={`size-3.5 ${refreshing ? "animate-spin" : ""}`} /> Refresh</Button>;

  if (issued && validPreview && !view) return <section aria-label="Scenario preview" className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border bg-card px-5 py-4">
    <p className="text-sm text-muted-foreground">Scenario omitting {validPreview.omitted} has no {issued.scope.name ?? issued.scope.id} view. Nothing inferred.</p>
    <Button size="sm" variant="outline" onClick={() => setPreview(undefined)}>Back to issued</Button>
  </section>;

  if (!issued || !view) return <section aria-label="Published forecast" className="rounded-xl border border-border bg-card px-5 py-4">
    <div className="flex items-center justify-between gap-3">
      <p className="min-w-0 text-sm text-muted-foreground">
        <span className="text-foreground">Forecast unavailable</span> · {reasonLine(forecastError) ?? "none published for this scope yet"}
      </p>
      {refreshButton}
    </div>
    {forecastRefresh && <p className="mt-1 text-xs text-muted-foreground" role="status">Refresh {forecastRefresh.status}</p>}
    {scopeType === "company" && <EvidenceProcessing evidence={forecastEvidence} includeDrivers />}
  </section>;

  const unit = view.target.unit;
  const u = unit.toLowerCase();
  const pub = issued.publication ?? {};
  const quarter = view.quarter_outlook;
  const qBase = finite(quarter?.base);
  const qLow = finite(quarter?.low), qHigh = finite(quarter?.high);
  const recorded = finite(view.components?.recorded);
  const scopedBudgets = budgets.filter(b => b.unit === u && (scopeType === "company" || scopeType === "team" && b.teamId === scopeId));
  const allotment = scopeType === "person" || !scopedBudgets.length ? undefined : scopedBudgets.reduce((s, b) => s + b.allocated, 0);
  const personTeam = scopeType === "person" ? people.find(p => p.id === scopeId)?.teamId : undefined;
  const teamView = personTeam ? scopeView(validPreview?.bundle ?? forecastBundle, "team", personTeam) : undefined;
  const teamBase = finite(teamView?.quarter_outlook?.base);
  const share = qBase !== undefined && teamBase ? qBase / teamBase : undefined;
  const bulletTitle = [
    `Projected ${exact(qBase, unit)}`,
    qLow !== undefined && qHigh !== undefined ? `Range ${exact(qLow, unit)} to ${exact(qHigh, unit)}` : "Range unavailable",
    `Recorded ${exact(recorded, unit)}`,
    allotment !== undefined ? `Allotment ${exact(allotment, unit)}` : "No allotment",
  ].join(" · ");

  const allEffects = issued.driver_effects ?? forecastBundle?.driver_effects ?? [];
  const effectFor = (id?: string): ForecastDriverEffect | undefined => allEffects.find(e => e.driver_id === id && e.scope?.type === issued.scope.type && e.scope?.id === issued.scope.id) ?? allEffects.find(e => e.driver_id === id && !e.scope) ?? allEffects.find(e => e.driver_id === id);
  const selectedEffect = effectFor(selectedDriver?.id);
  const rows = evidenceDrivers(issued, forecastEvidence).filter(({ driver, status }) => {
    if (scopeType === "company" || status === "Included") return true;
    const scope = driver.scope as Record<string, unknown> | undefined;
    if (!scope || (!scope.team_id && !scope.person_id)) return true;
    if (scope?.[`${scopeType}_id`] === scopeId) return true;
    return scopeType === "team" ? people.some(p => p.id === scope.person_id && p.teamId === scopeId) : people.some(p => p.id === scopeId && p.teamId === scope.team_id);
  });
  const adjustments = rows.map(r => ({ ...r, delta: r.status === "Included" ? (effectFor(r.driver.id)?.available ? finite(effectFor(r.driver.id)?.base_delta) : undefined) : undefined }))
    .sort((a, b) => (a.status === "Included" ? 0 : 1) - (b.status === "Included" ? 0 : 1) || Math.abs(b.delta ?? 0) - Math.abs(a.delta ?? 0));
  const maxDelta = Math.max(0, ...adjustments.map(a => Math.abs(a.delta ?? 0)));
  const shown = showAll ? adjustments : adjustments.slice(0, TOP);

  const chart = view.cumulative.map(p => ({ ...p, date: p.date ?? p.end, scenario: pointRange(p), error: historicalRange(p, errorLevel) }));
  const hasScenario = chart.some(p => p.scenario);
  const hasError = chart.some(p => p.error);
  const activeBand = band ?? (hasScenario ? "scenario" : hasError ? "error" : undefined);
  const bandMissing = activeBand === undefined ? rangeStatus(view.scenario_range, "Range unavailable for this run") : undefined;

  const lastErr = [...view.cumulative].reverse().find(p => historicalRange(p, "80"));
  const lastRange = lastErr ? historicalRange(lastErr, "80") : undefined;
  const lastBase = finite(lastErr?.base);
  const halfWidth = lastRange && lastBase ? (lastRange[1] - lastRange[0]) / 2 / lastBase : undefined;
  const calib = view.historical_error_interval?.["80"];
  const accuracyTitle = calib
    ? `80% interval · n=${calib.n ?? 0} · rank ${calib.rank ?? "unavailable"}${finite(calib.coverage) !== undefined ? ` · coverage ${Math.round(calib.coverage! * 100)}%` : ""} · ${dates(calib.calibration_start ?? undefined, calib.calibration_end ?? undefined)}${calib.qualification ? ` · ${calib.qualification}` : ""}`
    : "Insufficient matching mature issued outcomes; no coverage claim.";

  const weeks = view.weekly.map((p, i) => ({ key: p.start ?? String(i), label: short(String(p.calendar_start ?? p.start ?? "")), value: finite(p.base), partial: p.partial === true }));
  const fourWeeks = sumPointBases(view.weekly);
  const teamViews = scopeType === "company" ? (forecastBundle?.views.filter(v => v.scope.type === "team") ?? []) : [];
  const sharedViews = scopeType === "company" ? (forecastBundle?.views.filter(v => v.scope.type === "shared") ?? []) : [];
  const teamMax = Math.max(0, ...teamViews.map(v => finite(v.quarter_outlook?.base) ?? 0), ...sharedViews.map(v => finite(v.quarter_outlook?.base) ?? 0));
  const issuedAt = String(pub.generated_at ?? issued.generated_at ?? "");
  const model = [issued.procedure_id, issued.procedure_version].filter(Boolean).join(" ");

  return <section aria-label="Published forecast" className="rounded-xl border border-border bg-card p-5">

    <header className="flex flex-wrap items-center justify-between gap-3">
      <div className="flex min-w-0 items-baseline gap-3">
        <h2 className="text-sm font-medium">{scopeType === "company" ? "Forecast" : `${issued.scope.name ?? scopeType} forecast`}</h2>
        <span className="num text-xs text-muted-foreground" title={`Run ${issued.run_id}${model ? ` · ${model}` : ""}`}>Issued {short(issuedAt)}</span>
      </div>
      <div className="flex gap-1">
        <Button size="sm" variant="ghost" onClick={() => askForecastAssistant(forecastPrompt(issued), { action: "explain", run_id: issued.run_id, scope_type: issued.scope.type, scope_id: issued.scope.id })}><MessageSquare className="size-3.5" /> Ask the assistant</Button>
        {refreshButton}
      </div>
    </header>

    {(forecastError || refreshing || (forecastRefresh?.status === "failed")) && <p role={forecastError ? "alert" : "status"} className={`mt-2 text-xs ${forecastError ? "text-destructive" : "text-muted-foreground"}`}>
      {forecastError ? `Update failed · ${reasonLine(forecastError)}` : refreshing ? "Refreshing · issued run stays visible" : "Refresh failed · issued run unchanged"}
    </p>}

    {validPreviewJob && !validPreview && <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-xs" role="status">
      <p className="text-muted-foreground">Scenario {validPreviewJob.receipt.status} · {previewError ?? `omits ${validPreviewJob.omitted}`}</p>
      {!previewBusy && <Button size="sm" variant="outline" onClick={() => { const driver = issued.included_drivers.find(d => d.id === validPreviewJob.omitted); if (driver) void previewWithout(driver); }}>{validPreviewJob.receipt.status === "failed" ? "Retry" : "Check status"}</Button>}
    </div>}

    {validPreview && <div className="mt-3 flex flex-wrap items-center justify-between gap-2 rounded-md bg-warning/10 px-3 py-2 text-xs">
      <p>Conditional scenario · omits {validPreview.omitted}. Issued run unchanged.</p>
      <Button size="sm" variant="outline" onClick={() => setPreview(undefined)}>Back to issued</Button>
    </div>}

    {/* Quarter outlook against the allotment (omitted when embedded: the page header shows it) */}
    <div className={`mt-5 grid gap-6 ${embedded ? "" : "md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]"}`}>
      <div className={`min-w-0 space-y-3 ${embedded ? "order-last" : ""}`}>
        {!embedded && <>
        <div className="flex items-baseline justify-between gap-3">
          <span className="eyebrow">Quarter outlook · conditional</span>
          <span className="num text-xl text-foreground" title={exact(qBase, unit)}>{amount(qBase, unit)}</span>
        </div>
        {qBase === undefined
          ? <p className="text-xs text-muted-foreground">Unavailable · {String(quarter?.reason ?? view.limitations[0] ?? "inputs incomplete")}</p>
          : <>
            <RangeBand low={qLow} high={qHigh} domain={Math.max(allotment ?? 0, qBase, recorded ?? 0)}>
              <BulletBar allocation={allotment} spent={recorded ?? 0} projected={qBase} grow title={bulletTitle} />
            </RangeBand>
            <div className="flex flex-wrap gap-x-4 gap-y-1">
              <Swatch className="bg-foreground">Recorded {amount(recorded, unit, true)}</Swatch>
              <Swatch className="bg-foreground opacity-30">Projected</Swatch>
              {qLow !== undefined && qHigh !== undefined && <Swatch className="bg-chart-1/40">Range</Swatch>}
              {allotment !== undefined && <Swatch className="bg-border">Allotment {amount(allotment, unit, true)}</Swatch>}
              {allotment !== undefined && qBase > allotment && <Swatch className="bg-destructive/40">Over {amount(qBase - allotment, unit, true)}</Swatch>}
            </div>
          </>}
        {scopeType === "person" && <Meter value={share} label={share === undefined ? "Share unavailable" : `${Math.round(share * 100)}% of team`} title={`Team quarter outlook ${exact(teamBase, unit)}`} />}
        </>}
        <div className={`space-y-1.5 ${embedded ? "" : "pt-2"}`}>
          <div className="flex items-baseline justify-between gap-3">
            <span className="eyebrow">Model accuracy</span>
            <span className="text-[11px] text-muted-foreground">80% backtest</span>
          </div>
          <AccuracyMeter halfWidth={halfWidth} title={accuracyTitle} />
        </div>
      </div>

      {/* Cumulative path with its band */}
      <div className="min-w-0 space-y-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex flex-wrap gap-x-3 gap-y-1">
            <Swatch className="bg-foreground">{validPreview ? "Scenario base" : "Base"}</Swatch>
            {activeBand === "scenario" && <Swatch className="bg-chart-1/40">Scenario range</Swatch>}
            {activeBand === "error" && <Swatch className="bg-chart-2/40">Error {errorLevel}%</Swatch>}
          </div>
          {(hasScenario && hasError || activeBand === "error") && <div className="flex gap-1">
            {hasScenario && hasError && <><Choice selected={activeBand === "scenario"} onClick={() => setBand("scenario")}>Scenario</Choice><Choice selected={activeBand === "error"} onClick={() => setBand("error")}>Error</Choice></>}
            {activeBand === "error" && <><Choice selected={errorLevel === "80"} onClick={() => setErrorLevel("80")}>80%</Choice><Choice selected={errorLevel === "95"} onClick={() => setErrorLevel("95")}>95%</Choice></>}
          </div>}
        </div>
        {bandMissing && <p className="truncate text-[11px] text-muted-foreground" title={bandMissing}>Range unavailable · {bandMissing}</p>}
        <div className="h-36 w-full min-w-0" role="img" aria-label={`Cumulative ${unit} including recorded quarter spend${activeBand === "scenario" ? ", with scenario range" : activeBand === "error" ? ", with historical error interval" : ""}`}>
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={chart} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
              <CartesianGrid stroke="var(--border)" vertical={false} />
              <XAxis dataKey="date" tickFormatter={v => short(String(v))} tick={{ fontSize: 11, fontFamily: "var(--font-mono)", fill: "var(--muted-foreground)" }} axisLine={false} tickLine={false} minTickGap={40} />
              <YAxis tickFormatter={v => amount(v, unit, true)} tick={{ fontSize: 11, fontFamily: "var(--font-mono)", fill: "var(--muted-foreground)" }} axisLine={false} tickLine={false} width={48} />
              <Tooltip formatter={(v) => Array.isArray(v) ? v.map(x => exact(x, unit)).join(" to ") : exact(v, unit)} contentStyle={{ background: "var(--popover)", border: "1px solid var(--border)", borderRadius: 6, fontSize: 12 }} />
              {activeBand === "scenario" && <Area dataKey="scenario" name="Scenario range" stroke="none" fill="var(--chart-1)" fillOpacity={0.2} connectNulls={false} />}
              {activeBand === "error" && <Area dataKey="error" name={`Historical error (${errorLevel}%)`} stroke="none" fill="var(--chart-2)" fillOpacity={0.2} connectNulls={false} />}
              <Line dataKey="base" name={validPreview ? "Scenario base (conditional)" : "Issued base"} type="linear" dot={false} stroke="var(--foreground)" strokeWidth={2} connectNulls={false} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>

    {/* Next month (four weeks) and per-team split */}
    <div className={`mt-5 grid gap-6 border-t border-border pt-4 ${teamViews.length ? "md:grid-cols-2" : ""}`}>
      <div className="min-w-0 space-y-2">
        <div className="flex items-baseline justify-between gap-3">
          <span className="eyebrow">Next month</span>
          <span className="num text-xs text-foreground" title={dates(view.weekly[0]?.start, view.weekly.at(-1)?.end)}>{amount(fourWeeks, unit)}</span>
        </div>
        <ColumnStrip items={weeks} unit={unit} />
      </div>
      {teamViews.length > 0 && <div className="min-w-0 space-y-2">
        <span className="eyebrow">By team · same run</span>
        <ul className="space-y-1.5">
          {teamViews.map((v, i) => {
            const value = finite(v.quarter_outlook?.base);
            const name = v.scope.name ?? v.scope.id ?? "Team";
            return <BarRow key={v.scope.id} index={i} label={<Link href={`/teams/${v.scope.id}`} className="truncate hover:text-foreground">{name}</Link>}
              value={value ?? 0} max={teamMax} color={teams.find(t => t.id === v.scope.id)?.color ?? "var(--foreground)"}
              valueNode={<span title={exact(value, unit)}>{amount(value, unit, true)}</span>} className="py-0" />;
          })}
          {sharedViews.map((v, i) => {
            const value = finite(v.quarter_outlook?.base);
            return <BarRow key={v.scope.id} index={teamViews.length + i} label={v.scope.name ?? "Shared / unattributed"} value={value ?? 0} max={teamMax}
              color="var(--muted-foreground)" muted valueNode={<span title={exact(value, unit)}>{amount(value, unit, true)}</span>} className="py-0" />;
          })}
        </ul>
      </div>}
    </div>

    {/* Evidence adjustments as signed bars */}
    <div className="mt-5 space-y-2 border-t border-border pt-4">
      <div className="flex items-baseline justify-between gap-3">
        <span className="eyebrow">What moved it</span>
        {rows.length > 0 && <span className="text-[11px] text-muted-foreground">Effect on quarter</span>}
      </div>
      {rows.length === 0 ? <p className="text-xs text-muted-foreground">No drivers in this run.</p> : <ul>
        {shown.map(({ driver, status, delta }) => <li key={driver.id}>
          <button className="grid w-full grid-cols-[minmax(0,1fr)_minmax(0,7rem)_5.5rem] items-center gap-3 py-1.5 text-left text-xs hover:text-foreground/80" onClick={() => void openDriver(driver)} title={String(driver.publication_reason ?? driver.reason ?? status)}>
            <span className="truncate">{label(driver)}</span>
            {status === "Included" ? <SignedBar value={delta} max={maxDelta} /> : <span className="text-[11px] text-muted-foreground">{status}</span>}
            <span className={`num text-right ${delta === undefined ? "text-muted-foreground" : ""}`}>
              {status !== "Included" ? "—" : delta === undefined ? "n/a" : `${delta >= 0 ? "+" : "−"}${amount(Math.abs(delta), unit, true)}`}
            </span>
          </button>
        </li>)}
      </ul>}
      {adjustments.length > TOP && <button className="text-xs text-muted-foreground hover:text-foreground" onClick={() => setShowAll(s => !s)}>{showAll ? "Show fewer" : `+${adjustments.length - TOP} more`}</button>}
    </div>

    {scopeType === "company" && <EvidenceProcessing evidence={forecastEvidence} />}

    <Details view={view} issued={issued} bundle={forecastBundle} unit={unit} model={model} />

    <Sheet open={!!selectedDriver} onOpenChange={open => { if (!open) setDriverSelection(undefined); }}>
      <SheetContent side="right" className="w-full overflow-y-auto sm:max-w-lg">
        <SheetHeader className="pr-10">
          <SheetTitle>
            {selectedDriver ? label(selectedDriver) : "Forecast evidence"}
          </SheetTitle>
          <SheetDescription className="num break-all text-xs">Run {issued.run_id}</SheetDescription>
        </SheetHeader>
        {selectedDriver && <div className="space-y-5 px-4 pb-6 text-xs">
          <div className="space-y-1.5">
            <span className="eyebrow">Effect on {issued.scope.name ?? scopeType} quarter</span>
            {selectedEffect?.available ? <>
              <p className="num text-lg">{(finite(selectedEffect.base_delta) ?? 0) >= 0 ? "+" : "−"}{amount(Math.abs(finite(selectedEffect.base_delta) ?? 0), unit)}</p>
              <p className="num text-muted-foreground">With {exact(selectedEffect.with_base, unit)} · without {exact(selectedEffect.without_base, unit)}</p>
            </> : <p className="text-muted-foreground">Unavailable · no effect inferred from a mention.</p>}
            {selectedEffect?.qualification && <p className="text-muted-foreground">{selectedEffect.qualification}</p>}
          </div>
          {(selectedDriver.publication_reason ?? selectedDriver.reason) && <p>{String(selectedDriver.publication_reason ?? selectedDriver.reason)}</p>}
          <p className="num text-muted-foreground">Effective {dates(selectedDriver.effective_from, selectedDriver.effective_to ?? undefined)}</p>
          <div className="space-y-2">
            <span className="eyebrow">Sources</span>
            {(selectedDriver.citations ?? []).map((citation, i) => <blockquote key={i} className="space-y-1 border-l-2 border-border pl-3 text-muted-foreground">
              <p>{String(citation.excerpt ?? citation.quote ?? citation.text ?? "No passage supplied")}</p>
              <footer>{String(citation.title ?? citation.source_id ?? selectedDriver.source_id ?? "Source")} · {String(citation.locator ?? citation.available_at ?? "")}</footer>
            </blockquote>)}
            {!selectedDriver.citations?.length && <p className="text-muted-foreground">No cited passage.</p>}
          </div>
          <div className="flex flex-wrap gap-2">
            {issued.included_drivers.some(d => d.id === selectedDriver.id) || issued.queued_changes.some(d => d.id === selectedDriver.id)
              ? <Button variant="outline" size="sm" onClick={() => { askForecastAssistant(forecastPrompt(issued, selectedDriver), { action: "explain", run_id: issued.run_id, scope_type: issued.scope.type, scope_id: issued.scope.id, driver_id: selectedDriver.id }); setDriverSelection(undefined); }}>Ask the assistant</Button>
              : <p className="text-muted-foreground">Not in the issued run. Refresh first.</p>}
            {issued.included_drivers.some(d => d.id === selectedDriver.id) && <Button variant="outline" size="sm" disabled={previewBusy} onClick={() => void previewWithout(selectedDriver)}>
              {previewBusy ? "Calculating…" : validPreviewJob?.omitted === selectedDriver.id ? validPreviewJob.receipt.status === "failed" ? "Retry scenario" : "Check scenario status" : "Scenario without this"}
            </Button>}
          </div>
          {previewError && <p role="alert" className="text-destructive">{previewError}</p>}
          {validPreview && <p role="status">Conditional scenario ready. Close to inspect; issued numbers unchanged.</p>}
          <details>
            <summary className="cursor-pointer text-muted-foreground">Driver {selectedDriver.id} · {selectedDriver.source_id ?? "source unavailable"} rev {selectedDriver.source_revision ?? "unknown"}</summary>
            <pre className="mt-2 overflow-x-auto rounded-md bg-muted/30 p-3 text-[11px]">{json(selectedDriver.parameters ?? {})}</pre>
          </details>
          <details>
            <summary className="cursor-pointer text-muted-foreground">Calculation record</summary>
            <pre className="mt-2 max-h-96 overflow-auto whitespace-pre-wrap rounded-md bg-muted/30 p-3 text-[10px]">
              {json(explanation?.run === issued.run_id ? explanation.value : { status: "Loading issued explanation…" })}
            </pre>
          </details>
        </div>}
      </SheetContent>
    </Sheet>

  </section>;
}

/** Exact values, model, assumptions and limitations. Closed by default. */
function Details({ view, issued, bundle, unit, model }: { view: ForecastView; issued: ForecastView; bundle?: ForecastBundle; unit: string; model: string }) {
  const pub = issued.publication ?? {};
  const quarter = view.quarter_outlook;
  const actuals = bundle?.current_actuals;
  const assumptions = Array.isArray(quarter?.assumptions) ? quarter.assumptions.map(String) : [];
  const row = (k: string, v: React.ReactNode) => <div className="flex justify-between gap-4 py-1"><dt className="text-muted-foreground">{k}</dt><dd className="num min-w-0 break-all text-right">{v}</dd></div>;
  return <details className="mt-4 border-t border-border pt-3 text-xs">
    <summary className="cursor-pointer text-muted-foreground hover:text-foreground">Details</summary>
    <div className="mt-3 grid gap-6 md:grid-cols-2">
      <dl className="divide-y divide-border">
        {row("Model", model || "Unspecified")}
        {row("Run", issued.run_id)}
        {row("Issued", String(pub.generated_at ?? issued.generated_at ?? "unknown"))}
        {row("Evidence cutoff", String(pub.information_cutoff ?? issued.information_cutoff ?? "unknown"))}
        {row("Timezone", view.timezone ?? "UTC")}
        {row("Schedule", "Weekly, Monday 00:00 UTC")}
        {row("Quarter", `${dates(String(quarter?.start ?? ""), String(quarter?.end ?? ""))}${quarter?.complete === false ? " · incomplete" : ""}`)}
        {row("Quarter base", exact(quarter?.base, unit))}
        {row("Recorded", exact(view.components?.recorded, unit))}
        {row("Late", exact(view.components?.late, unit))}
        {row("Future", exact(view.components?.future, unit))}
        {row("Fixed", exact(view.components?.fixed, unit))}
        {view.scenario_range?.complete === false && row("Scenario range", "Partial; rate uncertainty omitted")}
        {actuals && row("Current actuals", actuals.status === "unavailable" ? String(actuals.reason ?? "Unavailable") : `Through ${String(actuals.as_of ?? "unknown")} · separate from issued run`)}
      </dl>
      <div className="space-y-3">
        <PointTable title="Weekly" points={view.weekly} unit={unit} />
        <PointTable title="Daily" points={view.daily} unit={unit} />
      </div>
    </div>
    {(assumptions.length > 0 || view.limitations.length > 0) && <ul className="mt-4 list-disc space-y-1 pl-4 text-muted-foreground">
      {assumptions.map((a, i) => <li key={`a${i}`}>{a}</li>)}
      {view.limitations.map((l, i) => <li key={`l${i}`}>{l}</li>)}
    </ul>}
  </details>;
}

function PointTable({ title, points, unit }: { title: string; points: ForecastPoint[]; unit: string }) {
  if (!points.length) return null;
  return <table className="w-full text-xs">
    <thead><tr className="text-left"><th className="eyebrow pb-1 font-normal">{title}</th><th className="eyebrow pb-1 text-right font-normal">Base</th><th className="eyebrow pb-1 text-right font-normal">Range</th></tr></thead>
    <tbody>
      {points.map((p, i) => <tr key={p.date ?? p.start ?? i} className="border-t border-border">
        <td className="num py-1">{(p.date ?? p.start ?? "").slice(5, 10)}{p.partial === true && " · partial"}{p.complete === false && " · incomplete"}</td>
        <td className="num text-right">{exact(p.base, unit)}</td>
        <td className="num text-right text-muted-foreground">{pointRange(p)?.map(v => amount(v, unit, true)).join("–") ?? "—"}</td>
      </tr>)}
    </tbody>
  </table>;
}

function EvidenceProcessing({ evidence, includeDrivers = false }: { evidence: ForecastEvidence[]; includeDrivers?: boolean }) {
  const items = evidence.filter(item => includeDrivers || !item.drivers?.length);
  if (!items.length) return null;
  return <div className="mt-4 space-y-1.5 border-t border-border pt-3 text-xs" aria-label="Evidence processing">
    <span className="eyebrow">Evidence in progress</span>
    <ul className="space-y-1">
      {items.map((item, index) => {
        const envelope = item.envelope as Record<string, unknown> | undefined;
        const status = String(item.status ?? item.queue_status ?? "received");
        const failed = status === "failed" || typeof item.last_error === "string";
        return <li key={item.id ?? item.source_id ?? index} className="flex flex-wrap items-center gap-x-2" title={item.drivers?.length ? item.drivers.map(d => `${label(d)} · ${d.status === "context_only" ? "Context only" : "Queued"}`).join("\n") : "No numerical driver yet. Issued forecast unchanged."}>
          <span className={`size-1.5 rounded-full ${failed ? "bg-destructive" : "bg-muted-foreground"}`} />
          <span className="truncate">{String(item.source_id ?? envelope?.source_id ?? item.id ?? "Source")}</span>
          <span className="text-muted-foreground">{status}</span>
          {typeof item.last_error === "string" && <span className="text-destructive">{item.last_error}</span>}
        </li>;
      })}
    </ul>
  </div>;
}

function Choice({ selected, onClick, children }: { selected: boolean; onClick: () => void; children: React.ReactNode }) {
  return <button aria-pressed={selected} onClick={onClick} className={`rounded-sm px-2 py-1 text-[11px] transition-colors duration-300 ${selected ? "bg-muted text-foreground" : "text-muted-foreground hover:text-foreground"}`}>
    {children}
  </button>;
}
