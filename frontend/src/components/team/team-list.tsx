"use client";
import { displaySourceText } from "@/lib/display-copy";
import { Suspense } from "react";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { ChevronRight, Search, X } from "lucide-react";
import type { Unit } from "@/lib/contracts";
import { useAppStore } from "@/lib/store";
import { formatAmount } from "@/lib/format";
import { selectScopeSummary } from "@/lib/finance-summary";
import { scopeView } from "@/components/dashboard/forecast-derive";
import { PageTitle, StatTile } from "@/components/shared/stat-tile";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { cn } from "@/lib/utils";
import { fmtDate, StatusChip } from "./labels";
import { filterTeamRows, parseTeamFilters, teamFilterQuery, type TeamFilters, type TeamSort } from "./team-list-filters";

export function TeamList() {
  return <Suspense fallback={<TeamListSkeleton />}><TeamListContent /></Suspense>;
}

function TeamListContent() {
  const { loaded, teams, spending, budgets, company, forecastBundle } = useAppStore();
  const params = useSearchParams();
  const pathname = usePathname();
  const filters = parseTeamFilters(params);
  const setFilters = (next: TeamFilters) => {
    const query = teamFilterQuery(params, next);
    window.history.replaceState(null, "", `${pathname}${query ? `?${query}` : ""}`);
  };

  if (!loaded) return <TeamListSkeleton />;

  const period = company?.currentPeriod ?? budgets[0]?.period;
  const unit = company?.budgetUnit ?? budgets[0]?.unit ?? "usd";
  const input = { period: period!, unit, datasetId: company?.id ?? "current", spending, budgets };
  const companySummary = period ? selectScopeSummary({ ...input, scope: scopeView(forecastBundle, "company")?.scope ?? { type: "company", id: company?.id }, forecastView: scopeView(forecastBundle, "company") }) : undefined;
  const allRows = teams.map(team => {
    const summary = period ? selectScopeSummary({ ...input, scope: { type: "team", id: team.id }, forecastView: scopeView(forecastBundle, "team", team.id) }) : undefined;
    return { team, spent: summary?.observed.amount ?? null, allocation: summary?.allocation ?? null, projected: summary?.issued.amount ?? null, variance: summary?.variance ?? null };
  });
  const rows = filterTeamRows(allRows, filters);
  const periodLabel = period?.label ?? (period ? `${fmtDate(period.start)} – ${fmtDate(period.end)}` : "Current period");

  return (
    <div className="min-w-0 space-y-6">
      <PageTitle title="Teams" description={<>Compare recorded spend and expected spend against each team’s allocation. <span className="text-foreground/80">{displaySourceText(periodLabel, "Current period")}</span></>} />

      {teams.length === 0 ? (
        <div className="rounded-xl border border-border bg-card px-6 py-16 text-center">
          <h2 className="text-base font-medium">No teams yet</h2>
          <p className="mt-2 text-sm text-muted-foreground">Teams will appear here when company data is available.</p>
        </div>
      ) : (
        <>
          <section className="grid divide-y divide-border rounded-xl border border-border bg-card sm:grid-cols-3 sm:divide-x sm:divide-y-0" aria-label="Company totals">
            <StatTile className="p-5" label="Recorded spend" value={amount(companySummary?.observed.amount, unit)} caption={companySummary?.observed.byProvenance.estimate ? "Includes estimates · all teams and shared costs" : "All teams and shared costs"} />
            <StatTile className="p-5" label="Total allocation" value={amount(companySummary?.allocation, unit)} caption={displaySourceText(periodLabel, "Current period")} />
            <StatTile className="p-5" label="Expected spend" value={amount(companySummary?.issued.amount, unit)} muted={companySummary?.issued.amount == null} caption={companySummary?.issued.amount == null ? "No outlook for this period" : displaySourceText(periodLabel, "Current period")} />
          </section>

          <section aria-label="Team comparison" className="space-y-4">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div className="relative w-full sm:max-w-sm">
                <Search aria-hidden className="pointer-events-none absolute top-3 left-3 size-4 text-muted-foreground" />
                <label htmlFor="team-search" className="sr-only">Search teams or leads</label>
                <input id="team-search" type="search" value={filters.query} onChange={event => setFilters({ ...filters, query: event.target.value })} placeholder="Search teams or leads" className="h-10 w-full rounded-lg border border-border bg-card pr-10 pl-9 text-sm outline-none placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring" />
                {filters.query && <button type="button" onClick={() => setFilters({ ...filters, query: "" })} className="absolute top-1 right-1 flex size-8 items-center justify-center rounded-md text-muted-foreground hover:text-foreground focus-visible:outline-2 focus-visible:outline-ring" aria-label="Clear team search"><X className="size-4" aria-hidden /></button>}
              </div>
              <div className="flex items-center justify-between gap-3 sm:justify-end">
                <p className="text-xs text-muted-foreground" aria-live="polite">{rows.length} of {teams.length} teams</p>
                <label htmlFor="team-sort" className="sr-only">Sort teams</label>
                <select id="team-sort" value={filters.sort} onChange={event => setFilters({ ...filters, sort: event.target.value as TeamSort })} className="h-10 min-w-44 rounded-lg border border-border bg-card px-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring">
                  <option value="spend">Highest spend</option>
                  <option value="projection">Highest expected spend</option>
                  <option value="variance">Largest overrun</option>
                  <option value="name">Name A–Z</option>
                </select>
              </div>
            </div>

            {rows.length === 0 ? (
              <div className="rounded-xl border border-border bg-card px-6 py-12 text-center">
                <h2 className="text-base font-medium">No teams match your search</h2>
                <p className="mt-2 text-sm text-muted-foreground">Try a team name, lead or description.</p>
                <Button variant="outline" className="mt-4" onClick={() => setFilters({ ...filters, query: "" })}>Clear search</Button>
              </div>
            ) : (
              <>
                <div className="hidden overflow-hidden rounded-xl border border-border bg-card lg:block">
                  <Table>
                    <caption className="sr-only">Team spend and allocation for {displaySourceText(periodLabel, "Current period")}</caption>
                    <TableHeader><TableRow>
                      <TableHead className="px-5">Team</TableHead>
                      <TableHead className="text-right">Recorded spend</TableHead>
                      <TableHead className="text-right">Allocation</TableHead>
                      <TableHead className="text-right">Expected spend</TableHead>
                      <TableHead className="text-right">Over / under</TableHead>
                      <TableHead className="pr-5">Status</TableHead>
                    </TableRow></TableHeader>
                    <TableBody>{rows.map(row => (
                      <TableRow key={row.team.id} className="group relative h-[76px]">
                        <TableCell className="px-5">
                          <Link href={`/teams/${row.team.id}`} className="flex items-center gap-3 outline-none after:absolute after:inset-0 focus-visible:after:ring-2 focus-visible:after:ring-inset focus-visible:after:ring-ring">
                            <span aria-hidden className="size-2 shrink-0 rounded-full" style={{ background: row.team.color }} />
                            <span><span className="font-medium">{displaySourceText(row.team.name, "Team")}</span><span className="mt-1 block text-xs text-muted-foreground">{displaySourceText(row.team.lead, "No lead listed")}</span></span>
                          </Link>
                        </TableCell>
                        <TableCell className="num text-right">{amount(row.spent, unit)}</TableCell>
                        <TableCell className="num text-right">{amount(row.allocation, unit)}</TableCell>
                        <TableCell className="num text-right">{amount(row.projected, unit)}</TableCell>
                        <TableCell className="text-right"><Variance value={row.variance} unit={unit} /></TableCell>
                        <TableCell className="pr-5"><OutlookStatus projected={row.projected} allocation={row.allocation} variance={row.variance} /></TableCell>
                      </TableRow>
                    ))}</TableBody>
                  </Table>
                </div>

                <ul className="grid gap-3 md:grid-cols-2 lg:hidden">{rows.map(row => (
                  <li key={row.team.id}>
                    <Link href={`/teams/${row.team.id}`} className="block h-full rounded-xl border border-border bg-card p-4 outline-none transition-colors hover:border-border-strong focus-visible:ring-2 focus-visible:ring-ring">
                      <div className="flex items-start justify-between gap-3">
                        <div><div className="flex items-center gap-2 font-medium"><span aria-hidden className="size-2 shrink-0 rounded-full" style={{ background: row.team.color }} />{displaySourceText(row.team.name, "Team")}</div><p className="mt-1 text-xs text-muted-foreground">{displaySourceText(row.team.lead, "No lead listed")}</p></div>
                        <ChevronRight aria-hidden className="size-4 text-muted-foreground" />
                      </div>
                      <dl className="mt-5 grid grid-cols-2 gap-x-4 gap-y-4">
                        <Stat label="Recorded spend" value={amount(row.spent, unit)} /><Stat label="Allocation" value={amount(row.allocation, unit)} />
                        <Stat label="Expected spend" value={amount(row.projected, unit)} /><div><dt className="text-xs text-muted-foreground">Over / under</dt><dd className="mt-1 text-sm"><Variance value={row.variance} unit={unit} /></dd></div>
                      </dl>
                      <div className="mt-4 border-t border-border pt-3"><OutlookStatus projected={row.projected} allocation={row.allocation} variance={row.variance} /></div>
                    </Link>
                  </li>
                ))}</ul>
              </>
            )}
            {allRows.some(row => row.projected == null) && <p className="text-xs text-muted-foreground">Expected spend and comparisons appear only when an outlook covers the allocation period.</p>}
          </section>
        </>
      )}
    </div>
  );
}

function amount(value: number | null | undefined, unit: Unit) { return value == null ? "—" : formatAmount(value, unit); }
function Variance({ value, unit }: { value: number | null; unit: Unit }) {
  return <span className={cn("num", value != null && value > 0 && "text-destructive", value == null && "text-muted-foreground")}>{value == null ? "—" : `${value > 0 ? "+" : value < 0 ? "−" : ""}${formatAmount(Math.abs(value), unit)}`}</span>;
}
function OutlookStatus({ projected, allocation, variance }: { projected: number | null; allocation: number | null; variance: number | null }) {
  if (variance == null || projected == null || allocation == null) return <span className="text-xs text-muted-foreground">No matching outlook</span>;
  return <StatusChip status={variance > 0 ? "likely_over" : projected >= allocation * 0.9 ? "watch" : "on_track"} />;
}
function Stat({ label, value }: { label: string; value: string }) {
  return <div className="min-w-0"><dt className="text-xs text-muted-foreground">{label}</dt><dd className="num mt-1 text-sm">{value}</dd></div>;
}
function TeamListSkeleton() {
  return <div className="space-y-6"><Skeleton className="h-8 w-32" /><Skeleton className="h-4 w-80 max-w-full" /><div className="grid grid-cols-1 gap-4 sm:grid-cols-3">{Array.from({ length: 3 }, (_, i) => <Skeleton key={i} className="h-28 rounded-xl" />)}</div><Skeleton className="h-10 w-full" /><Skeleton className="h-96 w-full rounded-xl" /></div>;
}
