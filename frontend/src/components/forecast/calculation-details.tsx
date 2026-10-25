"use client";
import { displayCopy, displayReference } from "@/lib/display-copy";
import Link from "next/link";
import type { ReactNode } from "react";
import type { ForecastBundle, ForecastEvidence, ForecastView } from "@/lib/contracts";
import { chartMoney } from "./chart-data";
import { sumPointBases } from "@/components/dashboard/forecast-derive";

/** Third layer: exact identities, reconciliation and limitations remain accessible without dominating finance tasks. */
export function CalculationDetails({ view, bundle, evidence, actions }: { view: ForecastView; bundle?: ForecastBundle; evidence: ForecastEvidence[]; actions?: ReactNode }) {
  const publication = view.publication ?? {};
  const unit = view.target.unit;
  const quarter = view.quarter_outlook;
  const history = view.historical_error_interval;
  return <details className="border-t border-border pt-3 text-xs">
    <summary className="cursor-pointer text-muted-foreground hover:text-foreground">Sources and calculation details</summary>
    <div className="mt-4 space-y-5">
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
      <dl className="grid gap-x-6 gap-y-3 sm:grid-cols-2">
        <Detail label="Published" value={String(publication.generated_at ?? view.generated_at ?? "Unknown")} />
        <Detail label="Information cutoff" value={String(publication.information_cutoff ?? view.information_cutoff ?? "Unknown")} />
        <Detail label="Forecast identity" value={displayReference(view.run_id, "Published forecast")} />
        <Detail label="Financial basis" value={`${view.target.quantity ?? "Spend"} · ${view.target.basis ?? "Published basis"} · ${unit.toUpperCase()}`} />
        <Detail label="Four published calendar weeks" value={`${chartMoney(sumPointBases(view.weekly), unit)} · ${view.weekly[0]?.start ?? "Unknown"} → ${view.weekly.at(-1)?.end ?? "Unknown"} (end exclusive)`} />
        <Detail label="Longer-term outlook" value={`${chartMoney(quarter?.base, unit)} · ${String(quarter?.start ?? "Unknown")} → ${String(quarter?.end ?? "Unknown")} (end exclusive)`} />
      </dl>
      <div><h3 className="font-medium">Published components</h3><p className="mt-2 text-muted-foreground">Recorded {chartMoney(view.components?.recorded, unit)} · late {chartMoney(view.components?.late, unit)} · future {chartMoney(view.components?.future, unit)} · fixed {chartMoney(view.components?.fixed, unit)}</p></div>
      {bundle?.current_actuals && <div><h3 className="font-medium">Current actuals</h3><p className="mt-2 text-muted-foreground">{bundle.current_actuals.status === "unavailable" ? displayCopy(String(bundle.current_actuals.reason ?? "Current actuals are unavailable.")) : `Received through ${String(bundle.current_actuals.as_of ?? "unknown")}; complete through ${String(bundle.current_actuals.history_complete_through ?? "unknown")}.`} Current actuals do not change a published forecast.</p></div>}
      <div><h3 className="font-medium">Assumptions and limitations</h3>{Array.isArray(quarter?.assumptions) && <p className="mt-2 text-muted-foreground">{quarter.assumptions.map(item => displayCopy(String(item))).filter(Boolean).join(" · ")}</p>}{view.limitations.length ? <ul className="mt-2 list-disc space-y-1.5 pl-4 text-muted-foreground">{view.limitations.map((item, index) => <li key={index}>{displayCopy(item)}</li>)}</ul> : <p className="mt-2 text-muted-foreground">No additional limitations supplied.</p>}</div>
      <div><h3 className="font-medium">Historical error intervals</h3><p className="mt-2 text-muted-foreground">These intervals are evaluated separately at each date. They do not describe simultaneous coverage of an entire spending path.</p>{(["80", "95"] as const).map(level => <p key={level} className="mt-2 text-muted-foreground">{level}%: {history?.[level]?.status === "available_assumption_conditional" ? `${chartMoney(history[level]?.lower, unit)}–${chartMoney(history[level]?.upper, unit)} · ${history[level]?.n ?? 0} matching outcomes. ${displayCopy(history[level]?.qualification)}` : "Unavailable; insufficient matching mature outcomes."}</p>)}</div>
      {view.scope.type === "company" && bundle && <div><h3 className="font-medium">Scope reconciliation</h3><p className="mt-2 text-muted-foreground">Company values include their supplied shared amounts. Missing team or person values are not filled with inferred totals.</p><div className="mt-2 flex flex-wrap gap-2">{bundle.views.filter(item => item.run_id === view.run_id && (item.scope.type === "team" || item.scope.type === "shared")).map(item => item.scope.type === "team" ? <Link key={item.scope.id} href={`/teams/${item.scope.id}`} className="rounded-md border border-border px-2.5 py-1.5 hover:bg-muted">{displayCopy(item.scope.name, "Team")} · {chartMoney(item.quarter_outlook?.base, unit)}</Link> : <span key={item.scope.id} className="rounded-md border border-dashed border-border px-2.5 py-1.5">{displayCopy(item.scope.name, "Shared / unattributed")} · {chartMoney(item.quarter_outlook?.base, unit)}</span>)}</div></div>}
      {view.scope.type === "company" && evidence.length > 0 && <details><summary className="cursor-pointer text-muted-foreground">Evidence processing ({evidence.length})</summary><ul className="mt-3 space-y-3">{evidence.map((item, index) => <li key={item.id ?? item.source_id ?? index} className="rounded-md border border-border p-3"><p>{displayReference(item.source_id ?? item.id, `Source ${index + 1}`)} · {displayCopy(String(item.status ?? item.queue_status ?? "received"))}</p>{typeof item.last_error === "string" && <p className="mt-1 text-destructive">{displayCopy(item.last_error)}</p>}{!item.drivers?.length && <p className="mt-1 text-muted-foreground">No numerical driver is available from this evidence. The published forecast is unchanged.</p>}</li>)}</ul></details>}
    </div>
  </details>;
}
function Detail({ label, value }: { label: string; value: string }) { return <div className="min-w-0"><dt className="text-muted-foreground">{label}</dt><dd className="mt-1 break-words">{displayCopy(value)}</dd></div>; }
