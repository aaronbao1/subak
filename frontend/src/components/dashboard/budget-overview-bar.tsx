"use client";
import { useMemo } from "react";
import Link from "next/link";
import { useAppStore } from "@/lib/store";
import { selectCompanyOverview } from "@/lib/company-overview";
import { weeklyMoney, weekRange } from "@/components/forecast/weekly-spend-derive";
import { Skeleton } from "@/components/ui/skeleton";

/** Company envelope and its saved allocation map share the same authoritative version and period. */
export function BudgetOverviewBar() {
  const { allocationState: state, allocationStateStatus, allocationStateError, loadAllocationState, company, spending, forecastBundle, teams, requests } = useAppStore();
  const summary = useMemo(() => selectCompanyOverview({ company, spending, forecastBundle, allocationState: state, allocationStateStatus }), [company, spending, forecastBundle, state, allocationStateStatus]);
  if (!state) return allocationStateStatus === "error"
    ? <section className="flex items-center justify-between rounded-xl border border-border p-4 text-sm" aria-label="Company budget"><span>Budget could not be loaded.</span><button onClick={() => void loadAllocationState()} className="underline">Try again</button></section>
    : <Skeleton className="h-28 w-full rounded-xl" aria-label="Loading company budget" />;
  const matchingPeriod = company?.currentPeriod.start === state.period.startDate
    && Date.parse(`${company.currentPeriod.end}T00:00:00Z`) + 86_400_000 === Date.parse(`${state.period.endDateExclusive}T00:00:00Z`)
    && company.budgetUnit.toLowerCase() === state.unit.toLowerCase();
  const total = Number(state.envelopeTotal);
  // Keep small directories unchanged; a larger legend follows the bar from largest to smallest.
  const allocations = state.allocations.length > 5
    ? [...state.allocations].sort((a, b) => Number(b.amount) - Number(a.amount))
    : state.allocations;
  const visible = allocations.slice(0, 5), remaining = allocations.slice(5);
  const allocationItem = (row: typeof allocations[number]) => {
    const team = teams.find(item => item.id === row.teamId);
    return <li key={row.teamId} className="inline-flex min-w-0 items-center gap-2"><span className="size-2 shrink-0 rounded-full" aria-hidden style={{ backgroundColor: team?.color ?? "var(--chart-other)" }} /><span className="text-muted-foreground">{team?.name ?? "Team"}</span><span className="shrink-0 font-medium tabular-nums">{weeklyMoney(row.amount)}</span></li>;
  };
  const pending = requests.filter(request => request.period.startDate === state.period.startDate && request.period.endDateExclusive === state.period.endDateExclusive && ["submitted", "pending_review", "needs_revision", "partially_funded"].includes(request.status));
  return <section className="min-w-0 space-y-4 rounded-xl border border-border bg-card px-5 py-4" aria-label="Company budget and team allocation">
    <p className="text-xs text-muted-foreground">Company outlook <span className="ml-1.5">{weekRange(state.period.startDate, state.period.endDateExclusive)}</span></p>
    <dl className="grid grid-cols-2 gap-x-5 gap-y-4 sm:grid-cols-3">
      <div><dt className="text-xs text-muted-foreground">Company budget</dt><dd className="mt-1.5 text-xl font-medium leading-tight tabular-nums lg:text-[28px]">{weeklyMoney(state.envelopeTotal)}</dd></div>
      <div><dt className="text-xs text-muted-foreground">Recorded spend</dt><dd className="mt-1.5 text-xl font-medium leading-tight tabular-nums lg:text-[28px]">{weeklyMoney(matchingPeriod ? summary.recorded : null)}</dd></div>
      <div className="col-span-2 sm:col-span-1"><dt className="text-xs text-muted-foreground">Expected spend</dt><dd className="mt-1.5 text-xl font-medium leading-tight tabular-nums lg:text-[28px]">{weeklyMoney(matchingPeriod ? summary.expected : null)}</dd>{summary.gap !== null && <dd className={`mt-1.5 text-xs ${summary.gap > 0 ? "text-destructive" : summary.gap < 0 ? "text-success" : "text-muted-foreground"}`}>{summary.gap === 0 ? "On budget" : `${weeklyMoney(Math.abs(summary.gap))} ${summary.gap > 0 ? "over budget" : "headroom"}`}</dd>}</div>
    </dl>
    <div className="min-w-0 border-t border-border pt-4">
      <div className="mb-3 flex items-center justify-between gap-3 text-xs"><span className="font-medium">Allocated by team</span><Link href="/requests" className="text-muted-foreground hover:text-foreground hover:underline">{pending.length ? `${pending.length} open ${pending.length === 1 ? "request" : "requests"} →` : "Team requests →"}</Link></div>
      <div className="flex h-2.5 overflow-hidden rounded-full bg-muted" aria-hidden>{allocations.map(row => { const team = teams.find(item => item.id === row.teamId); return <span key={row.teamId} style={{ width: `${total > 0 ? Math.max(0, Number(row.amount) / total * 100) : 0}%`, backgroundColor: team?.color ?? "var(--chart-other)" }} />; })}</div>
      <ul className="mt-3 flex flex-wrap gap-x-5 gap-y-2 text-xs">{visible.map(allocationItem)}{Number(state.unallocatedAmount) > 0 && <li className="text-muted-foreground">Unallocated {weeklyMoney(state.unallocatedAmount)}</li>}</ul>
      {remaining.length > 0 && <details className="mt-2 text-xs"><summary className="w-fit cursor-pointer text-muted-foreground hover:text-foreground">{remaining.length} more {remaining.length === 1 ? "team" : "teams"}</summary><ul className="mt-3 grid gap-x-5 gap-y-2 sm:grid-cols-2 xl:grid-cols-3">{remaining.map(allocationItem)}</ul></details>}
      {allocationStateError && <p role="status" className="mt-2 text-xs text-warning">Showing the last saved budget. <button onClick={() => void loadAllocationState()} className="underline">Refresh</button></p>}
    </div>
  </section>;
}
