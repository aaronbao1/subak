"use client";
import { displayCopy, displaySourceText } from "@/lib/display-copy";

import { useState } from "react";
import { ArrowDownLeft, ArrowUpRight, ChevronRight, Minus } from "lucide-react";
import type { ForecastDriver, ForecastEvidence, ForecastView } from "@/lib/contracts";
import { rankForecastInsights, type DriverInsight } from "@/lib/driver-insights";
import { DriverDetail, effectAmount, insightDates } from "@/components/forecast/driver-detail";
import { Button } from "@/components/ui/button";

const statusLabel: Record<DriverInsight["status"], string> = {
  modeled: "Modeled comparison", included: "Comparison unavailable", queued: "Queued", context: "Context only", unknown_scope: "Scope unknown",
};

export function DriverOverview({ view, evidence = [], compact = false, onEditDriver }: {
  view: ForecastView;
  evidence?: ForecastEvidence[];
  compact?: boolean;
  onEditDriver?: (driver: ForecastDriver) => void;
}) {
  const contextKey = JSON.stringify([view.run_id, view.scope.type, view.scope.id, view.quarter_outlook?.start, view.quarter_outlook?.end, view.target]);
  const [selection, setSelection] = useState<{ contextKey: string; driverId: string }>();
  const [expandedKey, setExpandedKey] = useState<string>();
  const insights = rankForecastInsights({ view, evidence });
  const modeled = insights.filter(insight => insight.status === "modeled");
  const supporting = insights.filter(insight => insight.status !== "modeled");
  const priorityChanges = modeled.length ? [] : supporting.filter(insight => insight.status === "included" || insight.status === "queued" || insight.status === "context").slice(0, 5);
  const remaining = supporting.filter(insight => !priorityChanges.includes(insight));
  const expanded = expandedKey === contextKey;
  const visible = expanded ? modeled : modeled.slice(0, 5);
  const selected = selection?.contextKey === contextKey ? insights.find(insight => insight.driver.id === selection.driverId) : undefined;
  const open = (insight: DriverInsight) => setSelection({ contextKey, driverId: insight.driver.id });

  return <section aria-label="What changes the outlook" className={compact ? "space-y-3" : "rounded-xl border border-border bg-card p-5 space-y-4"}>
    {!compact && <div className="flex flex-wrap items-start justify-between gap-3">
      <div>
        <h2 className="text-sm font-medium">What changes the outlook</h2>
        <p className="mt-1 text-xs text-muted-foreground">{displayCopy(view.scope.name ?? view.scope.type)} · conditional quarter</p>
      </div>
    </div>}

    {modeled.length > 0 ? <>
      <ol className="divide-y divide-border">
        {visible.map(insight => <li key={insight.driver.id}>
          <button type="button" onClick={() => open(insight)} className="group flex w-full items-center gap-3 rounded-md py-3 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
            <span className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-muted/60 text-muted-foreground" aria-hidden="true">
              {insight.delta! > 0 ? <ArrowUpRight className="size-4" /> : insight.delta! < 0 ? <ArrowDownLeft className="size-4" /> : <Minus className="size-4" />}
            </span>
            <span className="min-w-0 flex-1">
              <span className="block text-sm font-medium group-hover:underline underline-offset-4">{displayCopy(insight.title, "Forecast assumption")}</span>
              <span className="mt-0.5 block text-xs text-muted-foreground">{displayCopy(insight.scope.name ?? insight.scope.type)} · {insightDates(insight.driver.effective_from, insight.driver.effective_to)}</span>
              <span className="mt-0.5 block truncate text-[11px] text-muted-foreground">{displaySourceText(insight.sourceSummary, "Source details")}</span>
            </span>
            <span className="shrink-0 text-right">
              <span className="block text-sm font-medium tabular-nums">{effectAmount(insight.delta, insight.target.unit, true)}</span>
              <span className="mt-0.5 block text-[10px] text-muted-foreground">Quarter difference</span>
            </span>
            <ChevronRight className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
          </button>
        </li>)}
      </ol>
      {modeled.length > 5 && <Button size="sm" variant="ghost" onClick={() => setExpandedKey(expanded ? undefined : contextKey)}>{expanded ? "Show top five" : `See all ${modeled.length} comparisons`}</Button>}
      <p className="text-[11px] leading-relaxed text-muted-foreground">Individual model comparisons with each assumption omitted. They can interact and do not add to a total or establish realized savings.</p>
    </> : priorityChanges.length === 0 ? <p className="py-2 text-sm text-muted-foreground">No modeled quarter comparisons are available for this forecast.</p> : null}

    {priorityChanges.length > 0 && <div>
      <p className="text-[11px] text-muted-foreground">Assumptions and source context · financial comparisons unavailable</p>
      <ul className="mt-1 divide-y divide-border">
        {priorityChanges.map(insight => <li key={insight.driver.id}>
          <button type="button" onClick={() => open(insight)} className="flex w-full items-center gap-3 rounded-md py-3 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
            <span className="min-w-0 flex-1"><span className="block text-sm font-medium">{displayCopy(insight.title, "Forecast assumption")}</span><span className="mt-1 block text-xs text-muted-foreground">{insightDates(insight.driver.effective_from, insight.driver.effective_to)}</span></span>
            <span className="shrink-0 text-[10px] text-muted-foreground">{insight.status === "queued" ? "Queued" : insight.status === "context" ? "Source context" : "Included"}</span>
            <ChevronRight className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
          </button>
        </li>)}
      </ul>
    </div>}

    {remaining.length > 0 && <details className="border-t border-border pt-3">
      <summary className="cursor-pointer text-xs text-muted-foreground">Other assumptions and source context ({remaining.length})</summary>
      <ul className="mt-2 divide-y divide-border">
        {remaining.map(insight => <li key={insight.driver.id}>
          <button type="button" onClick={() => open(insight)} className="flex w-full items-center justify-between gap-3 rounded-md py-3 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
            <span className="min-w-0"><span className="block text-xs font-medium">{displayCopy(insight.title, "Forecast assumption")}</span><span className="mt-1 block text-[11px] text-muted-foreground">{displayCopy(insight.reason)}</span></span>
            <span className="shrink-0 text-[10px] text-muted-foreground">{statusLabel[insight.status]}</span>
          </button>
        </li>)}
      </ul>
    </details>}
    <DriverDetail insight={selected} onClose={() => setSelection(undefined)} onEditDriver={onEditDriver} />
  </section>;
}
