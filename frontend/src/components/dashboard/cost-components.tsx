"use client";
import type { CostComponent, Provenance, SpendingRecord, Unit } from "@/lib/contracts";
import { Skeleton } from "@/components/ui/skeleton";
import { COMPONENT_COLOR } from "@/components/shared/components";
import { COMPONENT_LABEL, PROVENANCE_LABEL } from "@/components/team/labels";
import { formatAmount } from "@/lib/format";
import { cn } from "@/lib/utils";
import { componentTotals } from "./derive";
import { BarRow, CountUp, StackedBar } from "./bars";

/** "Reported charge" / "Estimate + usage only": provenance for a tooltip. */
export function provenanceText(provenances: Provenance[]): string {
  return provenances.length ? provenances.map((p) => PROVENANCE_LABEL[p]).join(" + ") : "No records";
}

/** Anything that is not a reported charge gets a dotted underline at rest, so estimates stay distinguishable. */
export function isUnbilled(provenances: Provenance[]): boolean {
  return provenances.some((p) => p !== "reported_charge");
}

/**
 * Billable mix as one stacked bar, then a bar list per component (label · bar · amount · share).
 * Included usage stays visible but dashed and muted: it is informational, not billed, and has no share.
 * Provenance is in each row's tooltip; estimated amounts carry a dotted underline.
 */
export function CostComponents({ spending, unit, className }: { spending: SpendingRecord[]; unit: Unit; className?: string }) {
  const totals = componentTotals(spending);
  const max = Math.max(0, ...totals.map((t) => t.amount));
  const billable = totals.filter((t) => t.component !== "included_usage").reduce((s, t) => s + t.amount, 0);
  const money = (n: number) => formatAmount(n, unit, { compact: true });

  return (
    <section aria-labelledby="cost-components-heading" className={cn("min-w-0 rounded-xl border border-border bg-card p-5", className)}>
      <header className="flex items-baseline justify-between gap-4">
        <h2 id="cost-components-heading" className="text-base font-medium">Cost components</h2>
        {spending.length > 0 && (
          <span className="flex items-baseline gap-4 text-xs text-muted-foreground">
            <EstimateLegend />
            <span>Billable <span className="num text-foreground"><CountUp value={billable} format={money} /></span></span>
          </span>
        )}
      </header>

      {spending.length === 0 ? (
        <p className="mt-4 text-sm text-muted-foreground">No spending recorded yet.</p>
      ) : (
        <>
          <StackedBar
            className="mt-4"
            segments={totals.filter((t) => t.component !== "included_usage").map((t) => ({
              key: t.component, value: t.amount, color: COMPONENT_COLOR[t.component],
              title: `${COMPONENT_LABEL[t.component]} ${formatAmount(t.amount, unit)}`,
            }))}
          />
          <ul className="mt-3">
            {totals.map((t, i) => {
              const informational = t.component === "included_usage";
              const noRecords = t.provenances.length === 0;
              const share = billable > 0 && !informational ? Math.round((t.amount / billable) * 100) : undefined;
              return (
                <BarRow
                  key={t.component} index={i}
                  label={<><ComponentSwatch component={t.component} />{COMPONENT_LABEL[t.component]}</>}
                  value={t.amount} max={max} color={COMPONENT_COLOR[t.component]} dashed={informational} muted={informational || noRecords}
                  title={`${formatAmount(t.amount, unit)} · ${provenanceText(t.provenances)}${informational ? " · informational, not billed" : ""}`}
                  valueNode={noRecords ? "—" : (
                    <span className={cn(isUnbilled(t.provenances) && "underline decoration-dotted decoration-muted-foreground underline-offset-4")}>
                      <CountUp value={t.amount} format={money} />
                    </span>
                  )}
                  trailing={<span className="num w-9 text-right text-muted-foreground">{share !== undefined ? `${share}%` : ""}</span>}
                />
              );
            })}
          </ul>
        </>
      )}
    </section>
  );
}

/** Legend entry that explains the dotted underline on amounts that are not a reported charge. */
export function EstimateLegend({ className }: { className?: string }) {
  return (
    <span className={cn("inline-flex items-baseline gap-1.5 text-xs text-muted-foreground", className)} title="Dotted amounts are estimates or usage only, not a reported charge">
      <span aria-hidden className="num underline decoration-dotted decoration-muted-foreground underline-offset-4">$0</span>
      <span>estimate / usage only</span>
    </span>
  );
}

/** Square swatch in the component's color; included usage is drawn as a dashed outline because it is not billed. */
export function ComponentSwatch({ component }: { component: CostComponent }) {
  const color = COMPONENT_COLOR[component];
  const dashed = component === "included_usage";
  return (
    <span
      aria-hidden
      className={cn("inline-block size-2 shrink-0 rounded-sm", dashed && "border border-dashed")}
      style={dashed ? { borderColor: color } : { background: color }}
    />
  );
}

export function CostComponentsSkeleton() {
  return (
    <div className="space-y-4 rounded-xl border border-border bg-card p-5">
      <Skeleton className="h-4 w-32" />
      <Skeleton className="h-1.5 w-full rounded-sm" />
      <div className="space-y-2.5">
        {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-3 w-full" />)}
      </div>
    </div>
  );
}
