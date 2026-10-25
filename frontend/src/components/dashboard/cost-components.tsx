"use client";
import { useId, useMemo } from "react";
import type { Period, SpendingRecord, Unit } from "@/lib/contracts";
import { Skeleton } from "@/components/ui/skeleton";
import { COMPONENT_COLOR } from "@/components/shared/components";
import { COMPONENT_LABEL } from "@/components/team/labels";
import { cn } from "@/lib/utils";
import { selectCostComponents } from "./cost-components-derive";

const amountLabel = (amount: number, unit: Unit) => unit === "usd"
  ? new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(amount)
  : `${new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 }).format(amount)} ${unit === "credits" ? "cr" : "tokens"}`;

/** The latest compact component layout, with informational usage kept outside recorded spend. */
export function CostComponents({ spending, period, unit, className }: { spending: SpendingRecord[]; period: Period; unit: Unit; className?: string }) {
  const headingId = useId();
  const result = useMemo(() => selectCostComponents({ records: spending, period, unit }), [spending, period, unit]);
  const max = Math.max(0, ...result.components.map(row => Math.abs(row.amount ?? 0)));
  const hasEstimate = result.components.some(row => row.provenances.includes("estimate"));
  return <section aria-labelledby={headingId} className={cn("min-w-0 rounded-xl border border-border bg-card p-5", className)}>
    <header className="flex flex-wrap items-baseline justify-between gap-2"><h2 id={headingId} className="text-base font-medium">Cost components</h2><span className="text-xs text-muted-foreground">Recorded <span className="ml-1 font-medium tabular-nums text-foreground">{result.total === null ? "—" : amountLabel(result.total, unit)}</span></span></header>
    <p className="mt-1 text-[11px] text-muted-foreground">{period.label ?? `${period.start} – ${period.end}`}</p>
    {!result.recordCount ? <p className="py-8 text-sm text-muted-foreground">No recorded costs for this period.</p> : <>
      <div className="mt-4 flex h-1.5 overflow-hidden rounded-sm bg-muted" aria-hidden>{result.canShowShares && result.components.filter(row => (row.amount ?? 0) > 0).map(row => <span key={row.component} style={{ width: `${row.amount! / result.total! * 100}%`, background: COMPONENT_COLOR[row.component] }} />)}</div>
      <ul className="mt-3 divide-y divide-border">
        {result.components.map(row => <li key={row.component} className="grid grid-cols-[minmax(0,1fr)_minmax(36px,.7fr)_auto] items-center gap-3 py-2.5 text-xs">
          <span className="flex items-center gap-2"><span className="size-2 shrink-0 rounded-sm" style={{ background: COMPONENT_COLOR[row.component] }} aria-hidden />{COMPONENT_LABEL[row.component]}</span>
          <span className="h-1.5 overflow-hidden rounded-sm bg-muted" aria-hidden><span className={cn("block h-full rounded-sm", (row.amount ?? 0) < 0 && "opacity-40")} style={{ width: `${max ? Math.abs(row.amount ?? 0) / max * 100 : 0}%`, background: COMPONENT_COLOR[row.component] }} /></span>
          <span className={cn("min-w-20 text-right font-medium tabular-nums", row.provenances.includes("estimate") && "underline decoration-dotted underline-offset-4")} title={row.amount === null ? "No priced records for this component" : undefined}>{row.amount === null ? "—" : amountLabel(row.amount, unit)}</span>
        </li>)}
        <li className="flex flex-wrap items-center justify-between gap-2 py-2.5 text-xs text-muted-foreground"><span className="flex items-center gap-2"><span className="size-2 rounded-sm border border-dashed border-muted-foreground" aria-hidden />Included usage</span><span>{result.included.recordCount ? "Covered by subscriptions" : "No records"}</span></li>
        {result.unpricedRecordCount > 0 && <li className="flex items-center justify-between gap-3 py-2.5 text-xs text-muted-foreground"><span>Unpriced usage</span><span>{result.unpricedRecordCount} record{result.unpricedRecordCount === 1 ? "" : "s"}</span></li>}
      </ul>
      {(result.hasPartialRecords || result.invalidAmountCount > 0) && <p className="mt-2 text-[11px] text-warning">{result.invalidAmountCount ? "Some charge amounts are unavailable." : "Includes partial days."}</p>}
      <details className="mt-2 border-t border-border pt-2 text-[11px] text-muted-foreground"><summary className="cursor-pointer">Cost details</summary><div className="space-y-1.5 pt-2"><p>Recorded spend excludes included and unpriced usage. Source coverage may be incomplete.</p>{result.included.notional !== null && <p>Included usage value: {amountLabel(result.included.notional, unit)} · already covered, not an additional charge.</p>}{hasEstimate && <p>Dotted amounts include estimates.</p>}{result.components.some(row => (row.amount ?? 0) < 0) && <p>Negative amounts are net credits or refunds; mix shares are withheld.</p>}</div></details>
    </>}
  </section>;
}
export function CostComponentsSkeleton() {
  return <div className="space-y-4 rounded-xl border border-border bg-card p-5"><Skeleton className="h-4 w-32" /><Skeleton className="h-1.5 w-full" />{[1,2,3,4].map(key => <Skeleton key={key} className="h-5 w-full" />)}</div>;
}
