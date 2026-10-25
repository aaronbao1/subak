"use client";
import Link from "next/link";
import { ChevronRight } from "lucide-react";
import type { Provenance, Unit } from "@/lib/contracts";
import { useAppStore } from "@/lib/store";
import { formatAmount } from "@/lib/format";
import { PageTitle, StatTile } from "@/components/shared/stat-tile";
import { riseDelay, useMounted } from "@/components/shared/motion";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { cn } from "@/lib/utils";
import { ProvenanceBadge, spentToDate, StatusChip, teamRecords, teamStatus, teamUnit } from "./labels";
import { CountUpAmount, riseAt, rowStep } from "./count-up";

const CELL = "px-4 text-sm";
/* Entrance (ms): tiles 0/60/120 · table card 180 · rows 180 + i*step (≤300 of stagger) · last rise ends ≤1180. */
const TABLE_AT = 180;

/** All teams with allocation, spend to date, projection, variance and a status badge. */
export function TeamList() {
  const { loaded, teams, spending, budgets, forecasts, company } = useAppStore();
  // Entrance classes apply once, on the client after load; re-renders keep the end state.
  const mounted = useMounted();
  const rise = mounted ? "animate-rise" : "opacity-0";

  if (!loaded) return <TeamListSkeleton />;

  const rows = teams.map((team) => {
    const records = teamRecords(spending, team.id);
    const budget = budgets.find((b) => b.teamId === team.id);
    const forecast = forecasts.find((f) => f.teamId === team.id);
    const spent = spentToDate(records);
    const unit = teamUnit(budget, records);
    const projected =
      forecast?.status === "available" && forecast.projected != null
        ? forecast.basis === "remaining" ? spent + forecast.projected : forecast.projected
        : undefined;
    // Variance = projected full-period total − allocation. Positive means the team is heading over.
    const variance = projected != null && budget ? projected - budget.allocated : undefined;
    return { team, budget, forecast, spent, unit, projected, variance, status: teamStatus(budget, forecast, spent) };
  });

  // Company totals for the top row. Projected is summed only over teams that have one; the rest are counted.
  const totalUnit = company?.budgetUnit ?? budgets[0]?.unit ?? "usd";
  const totalAllocation = budgets.length ? budgets.reduce((n, b) => n + b.allocated, 0) : undefined;
  const totalSpent = rows.reduce((n, r) => n + r.spent, 0);
  const withProjection = rows.filter((r) => r.projected != null);
  // Same rule as the overview hero: teams without a projection count at their spend to date (a floor, not a forecast).
  const totalProjected = withProjection.length ? rows.reduce((n, r) => n + (r.projected != null ? (r.projected as number) : r.spent), 0) : undefined;
  const missing = rows.length - withProjection.length;
  const periodLabel = company?.currentPeriod.label ?? "the current period";
  // Provenance of the spend total: one badge when every record agrees, "Mixed" plus the set when they differ.
  const provenances = [...new Set<Provenance>(spending.map((r) => r.provenance))];
  const step = rowStep(rows.length);

  return (
    <div className="space-y-6">
      <PageTitle
        className={rise}
        title="Teams"
        description={<>Internal allocations, spend to date and projected totals for {periodLabel}. Projections are full-period totals and already include spend to date.</>}
      />

      {rows.length === 0 ? (
        <div className="flex flex-col items-center gap-2 rounded-xl border border-border py-16 text-center">
          <div className="eyebrow">No teams yet</div>
          <p className="max-w-sm text-sm text-muted-foreground">Teams and their allocations appear here once the backend supplies them.</p>
        </div>
      ) : (
        <>
          {/* Company totals */}
          <section className="grid grid-cols-1 gap-4 sm:grid-cols-3" aria-label="Company totals">
            <div className={rise} style={riseDelay(0)}>
              <StatTile
                className="h-full"
                size="secondary"
                card
                label="Total allocation"
                value={totalAllocation != null ? <CountUpAmount value={totalAllocation} unit={totalUnit} /> : "—"}
                muted={totalAllocation == null}
              />
            </div>
            <div className={rise} style={riseDelay(1)}>
              <StatTile
                className="h-full"
                size="secondary"
                card
                label="Spent to date"
                value={<CountUpAmount value={totalSpent} unit={totalUnit} delay={60} />}
                caption={
                  provenances.length > 0 ? (
                    <span className="inline-flex flex-wrap items-center gap-1.5">
                      {provenances.length > 1 && <span>Mixed</span>}
                      {provenances.map((p) => <ProvenanceBadge key={p} provenance={p} />)}
                    </span>
                  ) : undefined
                }
              />
            </div>
            <div className={rise} style={riseDelay(2)}>
              <StatTile
                className="h-full"
                size="secondary"
                card
                label="Projection"
                caption={missing > 0 ? `${missing} ${missing === 1 ? "team" : "teams"} with no projection, counted at spend to date` : undefined}
                value={totalProjected != null ? <CountUpAmount value={totalProjected} unit={totalUnit} delay={120} /> : "None"}
                muted={totalProjected == null}
              />
            </div>
          </section>

          {/* Table on md and up */}
          <div className={cn("hidden overflow-hidden rounded-xl border border-border bg-card md:block", rise)} style={riseAt(TABLE_AT)}>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Team</TableHead>
                  <TableHead>Lead</TableHead>
                  <TableHead className="text-right">Allocation</TableHead>
                  <TableHead className="text-right">Spent to date</TableHead>
                  <TableHead className="text-right">Projection</TableHead>
                  <TableHead className="text-right">Variance</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="w-12"><span className="sr-only">Open</span></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map(({ team, budget, spent, unit, projected, variance, status }, i) => (
                  <TableRow key={team.id} className={cn("group relative", rise)} style={riseAt(TABLE_AT + i * step)}>
                    <TableCell className={cn(CELL, "font-medium")}>
                      <Link
                        href={`/teams/${team.id}`}
                        className="flex items-center gap-2.5 outline-none after:absolute after:inset-0 focus-visible:after:ring-2 focus-visible:after:ring-ring focus-visible:after:ring-inset"
                      >
                        <span aria-hidden className="size-2 shrink-0 rounded-full" style={{ background: team.color }} />
                        {team.name}
                      </Link>
                    </TableCell>
                    <TableCell className={cn(CELL, "text-muted-foreground")}>{team.lead ?? "—"}</TableCell>
                    <TableCell className={cn(CELL, "num text-right")}>{budget ? formatAmount(budget.allocated, budget.unit) : <Dash />}</TableCell>
                    <TableCell className={cn(CELL, "num text-right")}>{formatAmount(spent, unit)}</TableCell>
                    <TableCell className={cn(CELL, "num text-right")}>
                      {projected != null ? formatAmount(projected, unit) : <span className="font-sans text-muted-foreground">No projection</span>}
                    </TableCell>
                    <TableCell className={cn(CELL, "text-right")}>
                      {variance != null && budget ? <Variance variance={variance} allocation={budget.allocated} unit={unit} grow={mounted} delay={TABLE_AT + i * step} /> : <Dash />}
                    </TableCell>
                    <TableCell className={CELL}><StatusChip status={status} /></TableCell>
                    <TableCell className={cn(CELL, "pr-4")}>
                      <ChevronRight className="size-4 text-muted-foreground" aria-hidden strokeWidth={1.5} />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>

          {/* Cards below md so nothing scrolls horizontally on a phone */}
          <ul className="grid gap-3 md:hidden">
            {rows.map(({ team, budget, spent, unit, projected, variance, status }, i) => (
              <li key={team.id} className={rise} style={riseAt(TABLE_AT + i * step)}>
                <Link
                  href={`/teams/${team.id}`}
                  className="block rounded-xl border border-border bg-card p-4 outline-none transition-colors duration-300 hover:border-border-strong focus-visible:ring-2 focus-visible:ring-ring"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 text-sm font-medium">
                        <span aria-hidden className="size-2 shrink-0 rounded-full" style={{ background: team.color }} />
                        <span className="truncate">{team.name}</span>
                      </div>
                      <div className="mt-0.5 text-xs text-muted-foreground">{team.lead ?? "No lead listed"}</div>
                    </div>
                    <StatusChip status={status} />
                  </div>
                  <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3">
                    <Stat label="Allocation" value={budget ? formatAmount(budget.allocated, budget.unit) : "—"} />
                    <Stat label="Spent" value={formatAmount(spent, unit)} />
                    <Stat label="Projection" value={projected != null ? formatAmount(projected, unit) : "None"} muted={projected == null} />
                    <div className="min-w-0">
                      <dt className="eyebrow">Variance</dt>
                      <dd className="mt-1 text-sm">
                        {variance != null && budget ? <Variance variance={variance} allocation={budget.allocated} unit={unit} grow={mounted} delay={TABLE_AT + i * step} /> : <Dash />}
                      </dd>
                    </div>
                  </dl>
                </Link>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}

function Dash() {
  return <span className="text-muted-foreground">—</span>;
}

/**
 * Signed variance with a 48px bar scaled to the allocation. Over runs read in --destructive; headroom in --success.
 * The bar grows from the left once on load, after the row's own delay.
 */
function Variance({ variance, allocation, unit, grow, delay = 0 }: { variance: number; allocation: number; unit: Unit; grow?: boolean; delay?: number }) {
  const over = variance > 0;
  const share = allocation > 0 ? Math.min(1, Math.abs(variance) / allocation) : 0;
  const label = variance === 0 ? formatAmount(0, unit) : `${over ? "+" : "−"}${formatAmount(Math.abs(variance), unit)}`;
  return (
    <span className="inline-flex items-center justify-end gap-2">
      <span className={cn("num", over ? "text-destructive" : "text-foreground")}>{label}</span>
      <span aria-hidden className="h-1.5 w-12 shrink-0 overflow-hidden rounded-sm bg-border">
        <span
          className={cn("block h-full rounded-sm", over ? "bg-destructive" : "bg-success", grow ? "animate-grow-x" : "scale-x-0")}
          style={{ width: `${Math.round(share * 100)}%`, ...riseAt(delay) }}
        />
      </span>
    </span>
  );
}

function Stat({ label, value, muted }: { label: string; value: string; muted?: boolean }) {
  return (
    <div className="min-w-0">
      <dt className="eyebrow">{label}</dt>
      <dd className={cn("num mt-1 truncate text-sm", muted && "text-muted-foreground")}>{value}</dd>
    </div>
  );
}

function TeamListSkeleton() {
  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <Skeleton className="h-7 w-24" />
        <Skeleton className="h-4 w-80 max-w-full" />
      </div>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="space-y-2 rounded-xl border border-border bg-card p-4">
            <Skeleton className="h-3 w-24" />
            <Skeleton className="h-6 w-28" />
          </div>
        ))}
      </div>
      <div className="overflow-hidden rounded-xl border border-border bg-card">
        <div className="flex h-10 items-center gap-4 border-b border-border-strong px-4">
          <Skeleton className="h-3 w-12" />
          <Skeleton className="ml-auto h-3 w-16" />
          <Skeleton className="hidden h-3 w-16 md:block" />
        </div>
        <div className="divide-y divide-border">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="flex h-12 items-center gap-4 px-4">
              <Skeleton className="size-2 rounded-full" />
              <Skeleton className="h-4 w-32" />
              <Skeleton className="ml-auto h-4 w-20" />
              <Skeleton className="hidden h-4 w-20 md:block" />
              <Skeleton className="hidden h-6 w-20 rounded-md md:block" />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
