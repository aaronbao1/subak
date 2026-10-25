"use client";
import type { ScopeSummary } from "@/lib/contracts/finance-view";
import { chartMoney } from "./chart-data";

/** One matching scope, period and financial basis across every number in the strip. */
export function ForecastSummary({ summary, periodLabel }: { summary: ScopeSummary; periodLabel: string }) {
  const { observed, issued, allocation, variance, target } = summary;
  const hasEstimate = observed.byProvenance.estimate > 0;
  const sourceNote = hasEstimate ? "Includes estimated charges" : "Recorded spend";
  const items = [
    { label: "Spend to date", value: observed.amount, note: `${sourceNote}${observed.complete ? "" : " · partial day"}` },
    { label: "Budget", value: allocation, note: allocation === null ? "No budget set for this period" : periodLabel },
    { label: "Expected spend", value: issued.amount, note: issued.amount === null ? "No forecast for this exact period" : periodLabel },
    { label: variance === null || variance <= 0 ? "Budget remaining" : "Expected over budget", value: variance === null ? null : Math.abs(variance), note: variance === null ? "Matching forecast required" : variance <= 0 ? "After expected spending" : "Review the allocation", warning: variance !== null && variance > 0 },
  ];
  return <section aria-label="Period financial summary" className="rounded-xl border border-border bg-card">
    <dl className="grid grid-cols-2 divide-border xl:grid-cols-4">{items.map((item, index) => <div key={item.label} className={`min-w-0 px-5 py-5 ${index > 0 ? "xl:border-l" : ""} ${index % 2 ? "border-l" : ""} ${index > 1 ? "border-t xl:border-t-0" : ""}`}><dt className="text-xs text-muted-foreground">{item.label}</dt><dd className={`mt-2 text-[22px] font-medium leading-tight tabular-nums sm:text-[28px] xl:text-[30px] ${item.warning ? "text-warning" : "text-foreground"}`}>{chartMoney(item.value, target.unit)}</dd><dd className="mt-2 text-[11px] leading-snug text-muted-foreground">{item.note}</dd></div>)}</dl>
  </section>;
}
