"use client";
import Link from "next/link";
import { ArrowLeft, SearchX } from "lucide-react";
import { useAppStore } from "@/lib/store";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { TeamHeader } from "./team-header";
import { TeamSpendChart } from "./team-spend-chart";
import { ContextCards } from "./context-cards";
import { teamRecords, teamUnit } from "./labels";
import { PeopleTable } from "@/components/person/people-table";
import { summarizePeople } from "@/components/person/derive";

/** Client body for /teams/[teamId]: header, spend chart, context. Handles loading and unknown ids. */
export function TeamDetail({ teamId }: { teamId: string }) {
  const { loaded, company, teams, people, spending, spendingHistory, budgets, forecasts, personForecasts, context } = useAppStore();

  if (!loaded) return <TeamDetailSkeleton />;

  const team = teams.find((t) => t.id === teamId);
  if (!team) {
    return (
      <div className="mx-auto max-w-5xl space-y-6">
        <Link href="/teams" className="inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors duration-300 hover:text-foreground">
          <ArrowLeft className="size-4" aria-hidden /> All teams
        </Link>
        <div className="flex flex-col items-center gap-2 rounded-xl border border-border py-16 text-center">
          <SearchX className="size-4 text-muted-foreground" aria-hidden />
          <div className="eyebrow">Team not found</div>
          <p className="max-w-sm text-sm text-muted-foreground">
            No team with id <code className="rounded-sm bg-popover px-1 font-mono text-xs">{teamId}</code> exists in this company.
            {teams.length === 0 && " No teams are set up yet."}
          </p>
          <Button variant="outline" className="mt-2 border-border bg-popover hover:border-border-strong" nativeButton={false} render={<Link href="/teams" />}>
            All teams
          </Button>
        </div>
      </div>
    );
  }

  const records = teamRecords(spending, team.id);
  const budget = budgets.find((b) => b.teamId === team.id);
  const forecast = forecasts.find((f) => f.teamId === team.id);
  const unit = teamUnit(team, budget, records);
  const items = context.filter((c) => c.teamIds.includes(team.id));
  const period = budget?.period ?? forecast?.period ?? company?.currentPeriod;
  const peopleSummaries = period ? summarizePeople(people, team.id, spending, spendingHistory, personForecasts, context, period) : [];

  return (
    <div className="mx-auto max-w-5xl space-y-8">
      <TeamHeader team={team} budget={budget} forecast={forecast} records={records} />
      <TeamSpendChart team={team} records={records} forecast={forecast} unit={unit} />
      <PeopleTable team={team} summaries={peopleSummaries} unit={unit} />
      <ContextCards team={team} items={items} allItems={context} people={people} />
    </div>
  );
}

export function TeamDetailSkeleton() {
  return (
    <div className="mx-auto max-w-5xl space-y-8">
      <div className="space-y-6">
        <Skeleton className="h-4 w-20" />
        <div className="space-y-2">
          <div className="flex items-center gap-2.5">
            <Skeleton className="size-2.5 rounded-full" />
            <Skeleton className="h-6 w-40" />
            <Skeleton className="h-6 w-20 rounded-md" />
          </div>
          <Skeleton className="h-4 w-72 max-w-full" />
        </div>
        <div className="grid gap-4 sm:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="space-y-2 rounded-xl border border-border bg-card p-4">
              <Skeleton className="h-3 w-20" />
              <Skeleton className="h-8 w-28" />
              <Skeleton className="h-3 w-36 max-w-full" />
            </div>
          ))}
        </div>
        <Skeleton className="h-11 w-full rounded-xl" />
      </div>
      <div className="rounded-xl border border-border bg-card">
        <div className="flex items-start justify-between gap-3 p-5 pb-0">
          <div className="space-y-1.5">
            <Skeleton className="h-4 w-24" />
            <Skeleton className="h-3 w-64 max-w-full" />
          </div>
          <Skeleton className="hidden h-3 w-56 sm:block" />
        </div>
        <div className="p-5">
          <Skeleton className="h-64 w-full" />
        </div>
      </div>
      <div className="space-y-3">
        <div className="space-y-1.5">
          <Skeleton className="h-4 w-40" />
          <Skeleton className="h-3 w-72 max-w-full" />
        </div>
        <div className="grid gap-4 lg:grid-cols-2">
          {Array.from({ length: 2 }).map((_, i) => (
            <div key={i} className="space-y-2.5 rounded-xl border border-border bg-card p-5">
              <Skeleton className="h-4 w-48 max-w-full" />
              <Skeleton className="h-3 w-full" />
              <Skeleton className="h-3 w-5/6" />
              <div className="flex gap-1.5 pt-1">
                <Skeleton className="h-6 w-20 rounded-md" />
                <Skeleton className="h-6 w-24 rounded-md" />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
