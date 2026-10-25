import type { SpendingRecord, Unit } from "@/lib/contracts";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { formatAmount } from "@/lib/format";
import { cn } from "@/lib/utils";
import { COMPONENT_LABEL, PROVENANCE_LABEL, componentTotals } from "./derive";

export function CostComponents({ spending, unit }: { spending: SpendingRecord[]; unit: Unit }) {
  const totals = componentTotals(spending);
  const max = Math.max(0, ...totals.map((t) => t.amount));

  return (
    <Card className="min-w-0">
      <CardHeader>
        <CardTitle>Spend by cost component</CardTitle>
        <CardDescription>Included usage is informational; it is not billed on top of subscriptions.</CardDescription>
      </CardHeader>
      <CardContent>
        {spending.length === 0 ? (
          <p className="text-sm text-muted-foreground">No spending recorded yet.</p>
        ) : (
          <ul className="grid gap-x-8 gap-y-3 sm:grid-cols-2 xl:grid-cols-4">
            {totals.map((t) => {
              const informational = t.component === "included_usage";
              const width = max > 0 ? Math.max(t.amount > 0 ? 1 : 0, (t.amount / max) * 100) : 0;
              return (
                <li key={t.component} className="min-w-0 space-y-1.5">
                  <div className="flex flex-wrap items-baseline justify-between gap-x-2 text-sm">
                    <span className="flex flex-wrap items-center gap-x-1.5">
                      {COMPONENT_LABEL[t.component]}
                      {informational && <span className="text-xs text-muted-foreground">informational</span>}
                    </span>
                    <span className={cn("tabular-nums", informational ? "text-muted-foreground" : "font-medium")}>
                      {t.provenances.length === 0 ? "No records" : formatAmount(t.amount, unit)}
                    </span>
                  </div>
                  <div className="h-2 w-full rounded-full bg-muted">
                    <div
                      className={cn("h-full rounded-full", informational ? "border border-dashed border-foreground/40 bg-foreground/10" : "bg-foreground/70")}
                      style={{ width: `${width}%` }}
                    />
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {t.provenances.map((p) => (
                      <Badge key={p} variant="outline" className="h-4 px-1.5 text-[10px] font-normal text-muted-foreground">{PROVENANCE_LABEL[p]}</Badge>
                    ))}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

export function CostComponentsSkeleton() {
  return (
    <Card>
      <CardHeader><Skeleton className="h-5 w-48" /><Skeleton className="h-4 w-80 max-w-full" /></CardHeader>
      <CardContent><Skeleton className="h-16 w-full" /></CardContent>
    </Card>
  );
}
