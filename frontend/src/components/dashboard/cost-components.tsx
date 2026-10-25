"use client";
import type { CostComponent, SpendingRecord, Unit } from "@/lib/contracts";
import { Skeleton } from "@/components/ui/skeleton";
import { StatTile } from "@/components/shared/stat-tile";
import { riseDelay } from "@/components/shared/motion";
import { COMPONENT_COLOR } from "@/components/shared/components";
import { COMPONENT_LABEL, ProvenanceBadge } from "@/components/team/labels";
import { formatAmount } from "@/lib/format";
import { cn } from "@/lib/utils";
import { componentTotals } from "./derive";

/**
 * Hairline dividers between the four tiles: stacked below sm, a 2x2 grid from sm, one row from xl.
 * Indexed by tile position so every rule is a 1px border and nothing is a nested card.
 */
const TILE_DIVIDER = [
  "",
  "border-t sm:border-t-0 sm:border-l",
  "border-t xl:border-t-0 xl:border-l",
  "border-t sm:border-l xl:border-t-0",
];

/**
 * Full section, always open: one tile per cost component with its share of recorded spend,
 * a bar against the largest component, and provenance badges. Included usage is drawn dashed
 * because it is informational, not billed on top of subscriptions.
 * On first paint the tiles rise in with a 60ms stagger, their bars grow from the left on the same delay, and the values count up.
 */
export function CostComponents({ spending, unit }: { spending: SpendingRecord[]; unit: Unit }) {
  const totals = componentTotals(spending);
  const max = Math.max(0, ...totals.map((t) => t.amount));
  const billable = totals.filter((t) => t.component !== "included_usage").reduce((s, t) => s + t.amount, 0);

  return (
    <section aria-labelledby="cost-components-heading" className="min-w-0 rounded-xl border border-border bg-card">
      <header className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 p-5 pb-4">
        <div className="min-w-0">
          <h2 id="cost-components-heading" className="text-base font-medium">Cost components</h2>
          <p className="mt-0.5 text-xs text-muted-foreground">
            Subscription, included usage, extra usage and API stay separate. Included usage is informational and is not billed on top of subscriptions.
          </p>
        </div>
        {spending.length > 0 && (
          <p className="text-xs text-muted-foreground">
            Billable <span className="num text-foreground">{formatAmount(billable, unit)}</span>
          </p>
        )}
      </header>

      {spending.length === 0 ? (
        <p className="border-t border-border px-5 py-4 text-sm text-muted-foreground">No spending recorded yet.</p>
      ) : (
        <ul className="grid border-t border-border sm:grid-cols-2 xl:grid-cols-4">
          {totals.map((t, i) => {
            const informational = t.component === "included_usage";
            const width = max > 0 ? Math.max(t.amount > 0 ? 1 : 0, (t.amount / max) * 100) : 0;
            const share = billable > 0 && !informational ? t.amount / billable : undefined;
            const color = COMPONENT_COLOR[t.component];
            const noRecords = t.provenances.length === 0;
            return (
              <li key={t.component} className={cn("animate-rise min-w-0 border-border p-4", TILE_DIVIDER[i] ?? "")} style={riseDelay(i)}>
                <StatTile
                  size="secondary" animate format={(n) => formatAmount(n, unit)}
                  label={
                    <>
                      <ComponentSwatch component={t.component} />
                      {COMPONENT_LABEL[t.component]}
                    </>
                  }
                  value={noRecords ? "No records" : t.amount}
                  muted={noRecords || informational}
                  caption={informational ? "Informational, not billed" : share !== undefined ? <span className="num">{Math.round(share * 100)}% of billable</span> : undefined}
                />
                <div className="mt-3 h-1.5 w-full overflow-hidden rounded-sm bg-muted" aria-hidden>
                  <div
                    className={cn("animate-grow-x h-full", informational && "border border-dashed")}
                    style={{ ...riseDelay(i), ...(informational ? { width: `${width}%`, borderColor: color } : { width: `${width}%`, background: color }) }}
                  />
                </div>
                <div className="mt-3 flex min-h-5 flex-wrap gap-1.5">
                  {t.provenances.map((p) => <ProvenanceBadge key={p} provenance={p} />)}
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

/** Square swatch in the component's color; included usage is drawn as a dashed outline because it is not billed. */
function ComponentSwatch({ component }: { component: CostComponent }) {
  const color = COMPONENT_COLOR[component];
  const dashed = component === "included_usage";
  return (
    <span
      aria-hidden
      className={cn("mr-1.5 inline-block size-2 shrink-0 rounded-sm align-[-1px]", dashed && "border border-dashed")}
      style={dashed ? { borderColor: color } : { background: color }}
    />
  );
}

export function CostComponentsSkeleton() {
  return (
    <div className="rounded-xl border border-border bg-card">
      <div className="space-y-1.5 p-5 pb-4">
        <Skeleton className="h-4 w-32" />
        <Skeleton className="h-3 w-80 max-w-full" />
      </div>
      <div className="grid border-t border-border sm:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className={cn("space-y-2 border-border p-4", TILE_DIVIDER[i])}>
            <Skeleton className="h-3 w-24" />
            <Skeleton className="h-6 w-24" />
            <Skeleton className="h-3 w-20" />
            <Skeleton className="h-1.5 w-full rounded-sm" />
          </div>
        ))}
      </div>
    </div>
  );
}
