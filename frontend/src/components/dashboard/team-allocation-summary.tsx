"use client";

import { useId, useMemo } from "react";
import Link from "next/link";
import { ArrowUpRight } from "lucide-react";
import type { Unit } from "@/lib/contracts";
import { useAppStore } from "@/lib/store";
import { selectTeamAllocationSummary } from "@/lib/team-allocation-summary";
import { cn } from "@/lib/utils";
import { usageActivityHref } from "@/lib/usage-link";
import { formatExactUsd } from "@/lib/usage-derive";
import { fmtDate } from "@/components/team/labels";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

const dollars = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 0, maximumFractionDigits: 2 });
const percentages = new Intl.NumberFormat("en-US", { style: "percent", maximumFractionDigits: 1 });
const numbers = new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 });
const amount = (value: number, unit: Unit) => unit === "usd" ? dollars.format(value) : `${numbers.format(value)} ${unit === "credits" ? "cr" : "tokens"}`;

export function TeamAllocationSummary({ onAdjust, compact = true, showBudgetSummary = true }: {
  onAdjust?: (teamId: string) => void;
  compact?: boolean;
  showBudgetSummary?: boolean;
}) {
  const headingId = useId();
  const { loaded, company, teams, spending, budgets, forecastBundle, allocationState, allocationStateStatus } = useAppStore();
  const summary = useMemo(() => selectTeamAllocationSummary({ company, teams, spending, budgets, forecastBundle, allocationState, allocationStateStatus }), [company, teams, spending, budgets, forecastBundle, allocationState, allocationStateStatus]);
  const { rows, totalAllocation, unlistedAllocation, missingTeamCount, hasSharedScope, overallBudget, nativeAllocatedTotal, unallocatedAmount } = summary;
  const visibleRows = compact ? rows.slice(0, 5) : rows;
  const period = company?.currentPeriod;
  const periodLabel = period ? `${fmtDate(period.start, { year: period.start.slice(0, 4) !== period.end.slice(0, 4) })} – ${fmtDate(period.end, { year: true })}` : "";
  const hasUnavailable = visibleRows.some(row => row.gap === null);
  const showAllocationBar = totalAllocation !== null && totalAllocation > 0 && unlistedAllocation !== null && unlistedAllocation >= 0
    && rows.every(row => row.allocation === null || row.allocationShare !== null);

  return (
    <section aria-labelledby={headingId} className="min-w-0 overflow-hidden rounded-xl border border-border bg-card">
      <div className={cn("space-y-4", compact ? "px-4 pt-4 pb-3" : "px-5 pt-5 pb-4")}>
        <div className="flex items-start justify-between gap-4">
          {showBudgetSummary ? <div>
            <h2 id={headingId} className="text-xs font-medium text-muted-foreground">{overallBudget !== null ? "Overall budget" : missingTeamCount > 0 && totalAllocation !== null ? "Known allocations" : "Total allocated"}</h2>
            {!loaded ? <Skeleton className="mt-2 h-8 w-32" /> : company && (
              <p className="num mt-1 text-2xl font-semibold tracking-tight">{overallBudget !== null ? formatExactUsd(overallBudget) : totalAllocation === null ? <Unavailable /> : amount(totalAllocation, company.budgetUnit)}</p>
            )}
            {periodLabel && <p className="mt-1 text-xs text-muted-foreground">{periodLabel}</p>}
            {unallocatedAmount !== null && <p className="mt-1 text-xs text-muted-foreground"><span className="num">{formatExactUsd(nativeAllocatedTotal)}</span> allocated · <span className="num">{formatExactUsd(unallocatedAmount)}</span> unallocated</p>}
          </div> : <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1"><h2 id={headingId} className="text-sm font-medium">Team allocations</h2>{periodLabel && <span className="text-xs text-muted-foreground">{periodLabel}</span>}</div>}
          <Link href="/teams" className="mt-0.5 inline-flex items-center gap-1 rounded-sm text-xs text-muted-foreground outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring">
            All teams <ArrowUpRight aria-hidden="true" className="size-3.5" />
          </Link>
        </div>
        {showBudgetSummary && loaded && showAllocationBar && (
          <div className="flex h-2 gap-0.5 overflow-hidden rounded-full bg-muted" aria-hidden="true">
            {rows.map(row => row.allocationShare !== null && row.allocationShare > 0 && (
              <span key={row.team.id} className="h-full" title={`${row.team.name}: ${percentages.format(row.allocationShare)}`} style={{ width: `${row.allocationShare * 100}%`, background: row.team.color }} />
            ))}
            {unlistedAllocation > 0 && <span className="h-full bg-muted-foreground/50" style={{ width: `${unlistedAllocation / totalAllocation * 100}%` }} />}
          </div>
        )}
      </div>
      {!loaded ? (
        <div className="space-y-3 px-4 pb-4" aria-label="Loading team allocations" aria-busy="true">
          {[0, 1, 2].map(index => <Skeleton key={index} className="h-10 w-full" />)}
        </div>
      ) : !company ? (
        <p className="px-4 pb-5 text-sm text-muted-foreground">No planning period is available.</p>
      ) : !rows.length ? (
        <p className="px-4 pb-5 text-sm text-muted-foreground">Team allocations will appear here when teams are available.</p>
      ) : (
        <>
          <Table>
            <caption className="sr-only">Team allocations, shares of {missingTeamCount > 0 ? "known allocations" : "the allocation total"}, projected spend and expected gap for {periodLabel}. Gap is projected spend minus allocation.</caption>
            <TableHeader>
              <TableRow>
                <TableHead scope="col">Team</TableHead>
                <TableHead scope="col" className="text-right">Allocation</TableHead>
                <TableHead scope="col" className="text-right">Projected <span className="sr-only">{periodLabel}</span></TableHead>
                <TableHead scope="col" className="text-right" title="Projected spend minus allocation">Gap</TableHead>
                {onAdjust && <TableHead scope="col"><span className="sr-only">Actions</span></TableHead>}
              </TableRow>
            </TableHeader>
            <TableBody>
              {visibleRows.map(row => (
                <TableRow key={row.team.id}>
                  <TableCell className="font-medium">
                    <Link href={`/teams/${encodeURIComponent(row.team.id)}`} className="inline-flex items-center gap-2 rounded-sm outline-none hover:underline focus-visible:ring-2 focus-visible:ring-ring">
                      <span aria-hidden="true" className="size-2 shrink-0 rounded-full" style={{ background: row.team.color }} />
                      {row.team.name}
                    </Link>
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="ml-auto min-w-24">
                      <span className="num font-medium">{row.allocation === null ? <Unavailable /> : amount(row.allocation, company.budgetUnit)}</span>
                      {row.allocationShare !== null && (
                        <div className="mt-1 flex items-center justify-end gap-2">
                          <div className="h-1 w-12 overflow-hidden rounded-full bg-muted" aria-hidden="true"><div className="h-full rounded-full" style={{ width: `${row.allocationShare * 100}%`, background: row.team.color }} /></div>
                          <span className="num min-w-8 text-[10px] text-muted-foreground" aria-label={`${percentages.format(row.allocationShare)} of ${missingTeamCount > 0 ? "known allocations" : "the allocation total"}`}>{percentages.format(row.allocationShare)}</span>
                        </div>
                      )}
                    </div>
                  </TableCell>
                  <TableCell className="num text-right">{row.projected === null ? <Unavailable /> : amount(row.projected, company.budgetUnit)}</TableCell>
                  <TableCell className={cn("text-right", row.gapState === "over" && "text-destructive", row.gapState === "headroom" && "text-success")}>
                    {row.gap === null ? <Unavailable /> : row.gap === 0 ? <span className="text-xs text-muted-foreground">On allocation</span> : (
                      <span className="inline-flex flex-wrap items-baseline justify-end gap-x-1.5">
                        <span className="num">{amount(Math.abs(row.gap), company.budgetUnit)}</span>
                        <span className="text-xs">{row.gapState === "over" ? "over" : "headroom"}</span>
                      </span>
                    )}
                  </TableCell>
                  {onAdjust && <TableCell className="text-right">{row.canAdjust ? <Button variant="ghost" size="sm" aria-label={`Adjust ${row.team.name} allocation`} onClick={() => onAdjust(row.team.id)}>Adjust</Button> : <span className="sr-only">No matching allocation to adjust</span>}</TableCell>}
                </TableRow>
              ))}
            </TableBody>
          </Table>
          {(hasUnavailable || visibleRows.length < rows.length || (unlistedAllocation ?? 0) > 0) && (
            <div className="flex flex-wrap justify-between gap-2 border-t border-border px-4 py-2 text-[11px] text-muted-foreground">
              {hasUnavailable && <p>— No matching value for this period</p>}
              {unlistedAllocation !== null && unlistedAllocation > 0 && <p>Other allocations: <span className="num">{amount(unlistedAllocation, company.budgetUnit)}</span></p>}
              {visibleRows.length < rows.length && <p>{visibleRows.length} of {rows.length} teams</p>}
            </div>
          )}
        </>
      )}
      {loaded && hasSharedScope && (
        <div className="border-t border-border px-4 py-2">
          <Link href={usageActivityHref({ type: "shared" }, period)} className="inline-flex items-center gap-1 rounded-sm text-xs text-muted-foreground outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring">
            Shared &amp; unattributed spending <ArrowUpRight aria-hidden="true" className="size-3" />
          </Link>
        </div>
      )}
    </section>
  );
}

function Unavailable() {
  return <span className="text-muted-foreground" title="Unavailable for this period" aria-label="Unavailable for this period">—</span>;
}
