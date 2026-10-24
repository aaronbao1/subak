"use client";
import Link from "next/link";
import { ChevronRight, Users } from "lucide-react";
import { useAppStore } from "@/lib/store";
import { formatAmount } from "@/lib/format";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { spentToDate, StatusChip, teamRecords, teamStatus, teamUnit } from "./labels";

/** All teams with allocation, spend to date, projection and a restrained status chip. */
export function TeamList() {
  const { loaded, teams, spending, budgets, forecasts, company } = useAppStore();

  if (!loaded) return <TeamListSkeleton />;

  const rows = teams.map((team) => {
    const records = teamRecords(spending, team.id);
    const budget = budgets.find((b) => b.teamId === team.id);
    const forecast = forecasts.find((f) => f.teamId === team.id);
    const spent = spentToDate(records);
    const unit = teamUnit(team, budget, records);
    const projected =
      forecast?.status === "available" && forecast.projected != null
        ? forecast.basis === "remaining" ? spent + forecast.projected : forecast.projected
        : undefined;
    return { team, budget, forecast, spent, unit, projected, status: teamStatus(budget, forecast, spent) };
  });

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-lg font-semibold tracking-tight">Teams</h1>
        <p className="text-sm text-muted-foreground">
          Internal allocations, spend to date and projected totals for {company?.currentPeriod.label?.toLowerCase() ?? "the current period"}.
          Projections are full-period totals and already include spend to date.
        </p>
      </div>

      {rows.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-2 py-10 text-center">
            <Users className="size-6 text-muted-foreground" />
            <div className="font-medium">No teams yet</div>
            <p className="max-w-sm text-sm text-muted-foreground">
              Teams and their allocations appear here once the backend supplies them.
            </p>
          </CardContent>
        </Card>
      ) : (
        <>
          {/* Table on md and up */}
          <Card className="hidden py-0 md:block">
            <Table>
              <TableHeader>
                <TableRow className="hover:bg-transparent">
                  <TableHead className="pl-4">Team</TableHead>
                  <TableHead>Lead</TableHead>
                  <TableHead className="text-right">Allocation</TableHead>
                  <TableHead className="text-right">Spent to date</TableHead>
                  <TableHead className="text-right">Projection</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="w-8" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map(({ team, budget, spent, unit, projected, status }) => (
                  <TableRow key={team.id} className="relative">
                    <TableCell className="pl-4 font-medium">
                      <Link href={`/teams/${team.id}`} className="flex items-center gap-2 after:absolute after:inset-0">
                        <span aria-hidden className="size-2.5 shrink-0 rounded-full" style={{ background: team.color }} />
                        {team.name}
                      </Link>
                    </TableCell>
                    <TableCell className="text-muted-foreground">{team.lead ?? "—"}</TableCell>
                    <TableCell className="text-right tabular-nums">{budget ? formatAmount(budget.allocated, budget.unit) : "—"}</TableCell>
                    <TableCell className="text-right tabular-nums">{formatAmount(spent, unit)}</TableCell>
                    <TableCell className="text-right tabular-nums">
                      {projected != null ? formatAmount(projected, unit) : <span className="text-muted-foreground">No projection</span>}
                    </TableCell>
                    <TableCell><StatusChip status={status} /></TableCell>
                    <TableCell className="pr-3 text-muted-foreground"><ChevronRight className="size-4" /></TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>

          {/* Cards below md so nothing scrolls horizontally on a phone */}
          <ul className="grid gap-3 md:hidden">
            {rows.map(({ team, budget, spent, unit, projected, status }) => (
              <li key={team.id}>
                <Link href={`/teams/${team.id}`} className="block rounded-xl focus-visible:outline-2 focus-visible:outline-ring">
                  <Card size="sm">
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2">
                        <span aria-hidden className="size-2.5 shrink-0 rounded-full" style={{ background: team.color }} />
                        {team.name}
                      </CardTitle>
                      <CardDescription>{team.lead ?? "No lead listed"}</CardDescription>
                    </CardHeader>
                    <CardContent className="grid grid-cols-3 gap-2 text-sm">
                      <Stat label="Allocation" value={budget ? formatAmount(budget.allocated, budget.unit) : "—"} />
                      <Stat label="Spent" value={formatAmount(spent, unit)} />
                      <Stat label="Projection" value={projected != null ? formatAmount(projected, unit) : "None"} muted={projected == null} />
                      <div className="col-span-3 pt-1"><StatusChip status={status} /></div>
                    </CardContent>
                  </Card>
                </Link>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}

function Stat({ label, value, muted }: { label: string; value: string; muted?: boolean }) {
  return (
    <div className="min-w-0">
      <div className="text-[11px] uppercase tracking-wide text-muted-foreground">{label}</div>
      <div className={muted ? "text-muted-foreground" : "tabular-nums"}>{value}</div>
    </div>
  );
}

function TeamListSkeleton() {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Skeleton className="h-6 w-24" />
        <Skeleton className="h-4 w-80 max-w-full" />
      </div>
      <Card className="py-0">
        <div className="divide-y">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="flex items-center gap-4 px-4 py-3">
              <Skeleton className="size-2.5 rounded-full" />
              <Skeleton className="h-4 w-32" />
              <Skeleton className="ml-auto h-4 w-20" />
              <Skeleton className="hidden h-4 w-20 md:block" />
              <Skeleton className="hidden h-5 w-20 rounded-full md:block" />
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
