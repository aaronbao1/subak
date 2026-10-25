"use client";
import Link from "next/link";
import { ChevronRight } from "lucide-react";
import type { Provenance, Unit } from "@/lib/contracts";
import { useAppStore } from "@/lib/store";
import { formatAmount } from "@/lib/format";
import { PageTitle } from "@/components/shared/stat-tile";
import { riseDelay, useMounted } from "@/components/shared/motion";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { cn } from "@/lib/utils";
import { PROVENANCE_LABEL, provenanceNote, spentToDate, StatusChip, teamRecords, teamStatus, teamUnit } from "./labels";
import { CountUpAmount, riseAt, rowStep } from "./count-up";
import { BulletBar, BulletLegend } from "./viz";

const CELL = "px-4 text-sm";
/* Entrance (ms): totals bar 0 · table card 180 · rows 180 + i*step (≤300 of stagger) · last rise ends ≤1180. */
const TABLE_AT = 180;

/** All teams: one bullet bar per row (allocation, spend, projection), exact spent and projected/allocation values, and a status badge. */
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
    return { team, budget, forecast, spent, unit, projected, status: teamStatus(budget, forecast, spent) };
  });

  // Company totals for the top row. Projected is summed only over teams that have one; the rest are counted.
  const totalUnit = company?.budgetUnit ?? budgets[0]?.unit ?? "usd";
  const totalAllocation = budgets.length ? budgets.reduce((n, b) => n + b.allocated, 0) : undefined;
  const totalSpent = rows.reduce((n, r) => n + r.spent, 0);
  const withProjection = rows.filter((r) => r.projected != null);
  // Same rule as the overview hero: teams without a projection count at their spend to date (a floor, not a forecast).
  const totalProjected = withProjection.length ? rows.reduce((n, r) => n + (r.projected != null ? (r.projected as number) : r.spent), 0) : undefined;
  const missing = rows.length - withProjection.length;
  const periodLabel = company?.currentPeriod.label;
  // Provenance of the spend total: one badge when every record agrees, "Mixed" plus the set when they differ.
  const provenances = [...new Set<Provenance>(spending.map((r) => r.provenance))];
  const step = rowStep(rows.length);

  const provenanceTitle = provenances.length ? `Spend provenance: ${provenances.map((p) => PROVENANCE_LABEL[p]).join(", ")}` : undefined;

  return (
    <div className="space-y-6">
      <PageTitle className={rise} title="Teams" description={periodLabel} />

      {rows.length === 0 ? (
        <div className="flex flex-col items-center gap-2 rounded-xl border border-border py-16 text-center">
          <div className="eyebrow">No teams yet</div>
          <p className="max-w-sm text-sm text-muted-foreground">Teams appear once the backend supplies them.</p>
        </div>
      ) : (
        <>
          {/* Company totals: one bullet bar */}
          <section className={cn("rounded-xl border border-border bg-card p-5", rise)} style={riseDelay(0)} aria-label="Company totals">
            <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1">
              <div className="eyebrow">Company</div>
              {missing > 0 && (
                <div className="text-xs text-muted-foreground" title="Teams without a projection count at spend to date">
                  <span className="num">{missing}</span> unprojected, counted at spend
                </div>
              )}
            </div>
            <BulletBar
              className="mt-3"
              size="md"
              allocation={totalAllocation}
              spent={totalSpent}
              projected={totalProjected}
              grow={mounted}
              delay={60}
            />
            <BulletLegend
              className="mt-3"
              items={[
                { label: "Spent", mark: "fill", value: <CountUpAmount value={totalSpent} unit={totalUnit} delay={60} />, title: provenanceTitle, note: provenanceNote(provenances) },
                { label: "Projected", mark: "tick", value: totalProjected != null ? <CountUpAmount value={totalProjected} unit={totalUnit} delay={120} /> : "None", muted: totalProjected == null, title: "Full-period total; includes spend to date" },
                { label: "Allocation", mark: "track", value: totalAllocation != null ? <CountUpAmount value={totalAllocation} unit={totalUnit} /> : "None", muted: totalAllocation == null },
              ]}
            />
          </section>

          {/* Table on md and up */}
          <div className={cn("hidden overflow-hidden rounded-xl border border-border bg-card md:block", rise)} style={riseAt(TABLE_AT)}>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Team</TableHead>
                  <TableHead className="w-[40%]">
                    <span className="inline-flex items-center gap-3">
                      Spent vs allocation
                      <span className="inline-flex items-center gap-1 normal-case tracking-normal" title="Tick marks the projected full-period total">
                        <span aria-hidden className="h-2.5 w-0.5 rounded-sm bg-foreground" /> projected
                      </span>
                    </span>
                  </TableHead>
                  <TableHead className="text-right">Spent</TableHead>
                  <TableHead className="text-right">Projected / allocation</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="w-12"><span className="sr-only">Open</span></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map(({ team, budget, spent, unit, projected, status }, i) => (
                  <TableRow key={team.id} className={cn("group relative", rise)} style={riseAt(TABLE_AT + i * step)}>
                    <TableCell className={cn(CELL, "font-medium")}>
                      <Link
                        href={`/teams/${team.id}`}
                        title={team.lead ? `Lead: ${team.lead}` : undefined}
                        className="flex items-center gap-2.5 outline-none after:absolute after:inset-0 focus-visible:after:ring-2 focus-visible:after:ring-ring focus-visible:after:ring-inset"
                      >
                        <span aria-hidden className="size-2 shrink-0 rounded-full" style={{ background: team.color }} />
                        {team.name}
                      </Link>
                    </TableCell>
                    <TableCell className={CELL}>
                      {/* The bar's root is positioned and later in tree order than the row link's ::after overlay, so it would
                          paint above it and take the click. pointer-events-none lets clicks reach the overlay; exact values sit
                          in the Spent and Projected columns. */}
                      <BulletBar
                        className="pointer-events-none"
                        allocation={budget?.allocated}
                        spent={spent}
                        projected={projected}
                        color={team.color}
                        grow={mounted}
                        delay={TABLE_AT + i * step}
                        title={bulletTitle(spent, projected, budget?.allocated, unit)}
                      />
                    </TableCell>
                    <TableCell className={cn(CELL, "num whitespace-nowrap text-right text-foreground")}>{formatAmount(spent, unit)}</TableCell>
                    <TableCell className={cn(CELL, "text-right")}>
                      <ProjectedOf projected={projected} allocation={budget?.allocated} unit={unit} />
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
            {rows.map(({ team, budget, spent, unit, projected, status }, i) => (
              <li key={team.id} className={rise} style={riseAt(TABLE_AT + i * step)}>
                <Link
                  href={`/teams/${team.id}`}
                  className="block rounded-xl border border-border bg-card p-4 outline-none transition-colors duration-300 hover:border-border-strong focus-visible:ring-2 focus-visible:ring-ring"
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex min-w-0 items-center gap-2 text-sm font-medium">
                      <span aria-hidden className="size-2 shrink-0 rounded-full" style={{ background: team.color }} />
                      <span className="truncate">{team.name}</span>
                    </div>
                    <StatusChip status={status} />
                  </div>
                  <BulletBar
                    className="mt-3"
                    allocation={budget?.allocated}
                    spent={spent}
                    projected={projected}
                    color={team.color}
                    grow={mounted}
                    delay={TABLE_AT + i * step}
                    title={bulletTitle(spent, projected, budget?.allocated, unit)}
                  />
                  <div className="mt-2 flex items-baseline justify-between text-xs text-muted-foreground">
                    <span>Spent <span className="num text-foreground">{formatAmount(spent, unit)}</span></span>
                    <ProjectedOf projected={projected} allocation={budget?.allocated} unit={unit} />
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}

function bulletTitle(spent: number, projected: number | undefined, allocation: number | undefined, unit: Unit) {
  return [
    `Spent ${formatAmount(spent, unit)}`,
    projected != null ? `projected ${formatAmount(projected, unit)}` : "no projection",
    allocation != null ? `allocation ${formatAmount(allocation, unit)}` : "no allocation",
  ].join(" · ");
}

/** "$48k / $50k": the projected full-period total against the allocation. Over runs read in --destructive. */
function ProjectedOf({ projected, allocation, unit }: { projected?: number; allocation?: number; unit: Unit }) {
  const over = projected != null && allocation != null && projected > allocation;
  return (
    <span className="num whitespace-nowrap text-sm">
      {projected != null ? (
        <span className={over ? "text-destructive" : "text-foreground"}>{formatAmount(projected, unit, { compact: true })}</span>
      ) : (
        <span className="text-muted-foreground" title="No projection">—</span>
      )}
      <span className="text-muted-foreground"> / {allocation != null ? formatAmount(allocation, unit, { compact: true }) : "—"}</span>
    </span>
  );
}

function TeamListSkeleton() {
  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <Skeleton className="h-7 w-24" />
        <Skeleton className="h-4 w-32" />
      </div>
      <div className="space-y-3 rounded-xl border border-border bg-card p-5">
        <Skeleton className="h-3 w-20" />
        <Skeleton className="h-2.5 w-full" />
        <Skeleton className="h-4 w-80 max-w-full" />
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
