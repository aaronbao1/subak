"use client";
import { displayCopy, displaySourceText } from "@/lib/display-copy";
import { useState } from "react";
import { CalendarDays, ChevronRight, FileText } from "lucide-react";
import type { ForecastDriver, ForecastEvidence, ForecastView } from "@/lib/contracts";
import { rankForecastInsights } from "@/lib/driver-insights";
import { driverStart } from "@/lib/planning-drafts";
import { DriverDetail } from "./driver-detail";

/** Planning events are effective assumptions, separate from the observed usage calendar. */
export function PlanningCalendar({ view, evidence = [], onSelect }: { view: ForecastView; evidence?: ForecastEvidence[]; onSelect: (driver: ForecastDriver) => void }) {
  const [selected, setSelected] = useState<string>();
  const insights = rankForecastInsights({ view, evidence });
  const relevant = insights.filter(i => i.status !== "unknown_scope");
  const scheduled = relevant.filter(i => driverStart(i.driver)).sort((a, b) => driverStart(a.driver)!.localeCompare(driverStart(b.driver)!));
  const undated = relevant.filter(i => !driverStart(i.driver));
  const active = insights.find(i => i.driver.id === selected);
  return <section className="rounded-xl border border-border bg-card" aria-label="Upcoming plan changes">
    <header className="border-b border-border px-5 py-4"><h2 className="text-sm font-medium">Upcoming changes</h2><p className="mt-1 text-xs text-muted-foreground">Effective plan dates in UTC. Select a published assumption to try a what-if.</p></header>
    {scheduled.length ? <ol className="divide-y divide-border">{scheduled.map(item => {
      const included = item.status === "modeled" || item.status === "included";
      return <li key={item.driver.id}><button type="button" onClick={() => included ? onSelect(item.driver) : setSelected(item.driver.id)} className="flex w-full items-start gap-4 px-5 py-4 text-left transition-colors hover:bg-muted/30 focus-visible:outline-2 focus-visible:outline-ring">
        <div className="num min-w-16 text-xs text-muted-foreground"><CalendarDays className="mb-1.5 size-4"/><time dateTime={driverStart(item.driver)}>{driverStart(item.driver)}</time></div>
        <div className="min-w-0 flex-1"><p className="text-sm font-medium">{displayCopy(item.title, "Forecast assumption")}</p><p className="mt-1 text-xs text-muted-foreground">{included ? "In published forecast" : item.status === "queued" ? "Waiting for forecast update" : "Source context only"} · {displaySourceText(item.sourceSummary, "Source details")}</p><p className="mt-1 text-xs text-muted-foreground">{included ? "Create a separate hypothetical preview." : "No modeled financial effect supplied."}</p></div><ChevronRight className="mt-1 size-4 shrink-0 text-muted-foreground"/>
      </button></li>;
    })}</ol> : <div className="space-y-2 px-5 py-8 text-sm"><p className="font-medium">No dated changes for this scope</p><p className="text-xs text-muted-foreground">A plan needs a supported assumption and an effective date before it can appear here.</p></div>}
    {undated.length > 0 && <details className="border-t border-border px-5 py-4 text-xs"><summary className="cursor-pointer text-muted-foreground">{undated.length} source {undated.length === 1 ? "item" : "items"} without an effective date</summary><ul className="mt-3 space-y-2">{undated.map(item => <li key={item.driver.id}><button onClick={() => setSelected(item.driver.id)} className="flex items-center gap-2 text-left hover:underline"><FileText className="size-3.5"/>{displayCopy(item.title, "Forecast assumption")}</button></li>)}</ul></details>}
    {insights.some(i => i.status === "unknown_scope") && <p className="border-t border-border px-5 py-3 text-xs text-muted-foreground">Sources with unconfirmed scope are available in Evidence.</p>}
    {/* The detail component retains the selected publication context. */}
    <DriverDetail insight={active} onClose={() => setSelected(undefined)} onEditDriver={onSelect}/>
  </section>;
}
