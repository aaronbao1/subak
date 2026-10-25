"use client";
import Link from "next/link";
import { ArrowLeft, ChevronRight, SearchX } from "lucide-react";
import { ForecastPanel } from "@/components/forecast/forecast-panel";
import { useAppStore } from "@/lib/store";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { TeamHeader } from "./team-header";
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
      <div className="space-y-6">
        <Link href="/teams" className="inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors duration-300 hover:text-foreground">
          <ArrowLeft className="size-4" aria-hidden strokeWidth={1.5} /> All teams
        </Link>
        <div className="flex flex-col items-center gap-2 rounded-xl border border-border py-16 text-center">
          <SearchX className="size-4 text-muted-foreground" aria-hidden strokeWidth={1.5} />
          <h1 className="text-lg font-medium">Team not found</h1>
          <p className="max-w-sm text-sm text-muted-foreground">
            This team is not available in the current company.
            {teams.length === 0 && " No teams are set up yet."}
          </p>
          <Button variant="outline" size="lg" className="mt-2" nativeButton={false} render={<Link href="/teams" />}>
            All teams
          </Button>
        </div>
      </div>
    );
  }

  const records = teamRecords(spending, team.id);
  const budget = budgets.find((b) => b.teamId === team.id);
  const forecast = forecasts.find((f) => f.teamId === team.id);
  const unit = teamUnit(budget, records);
  const items = context.filter((c) => c.teamIds.includes(team.id));
  const period = company?.currentPeriod ?? budget?.period ?? forecast?.period;
  const peopleSummaries = period ? summarizePeople(people, team.id, spending, spendingHistory, personForecasts, context, period, forecast) : [];

  return (
    <div className="space-y-8">
      <TeamHeader team={team} budget={budget} records={records} />
      <ForecastPanel scopeType="team" scopeId={teamId} />
      <div className="space-y-3">
        <details className="group rounded-xl border border-border bg-card">
          <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-5 py-4 text-sm font-medium outline-none focus-visible:ring-2 focus-visible:ring-ring [&::-webkit-details-marker]:hidden">
            <span>People <span className="ml-2 font-normal text-muted-foreground">{peopleSummaries.length} members</span></span>
            <ChevronRight aria-hidden className="size-4 text-muted-foreground transition-transform group-open:rotate-90" />
          </summary>
          <div className="border-t border-border p-5"><PeopleTable team={team} summaries={peopleSummaries} unit={unit} /></div>
        </details>
        <details className="group rounded-xl border border-border bg-card">
          <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-5 py-4 text-sm font-medium outline-none focus-visible:ring-2 focus-visible:ring-ring [&::-webkit-details-marker]:hidden">
            <span>Assessed plans <span className="ml-2 font-normal text-muted-foreground">{items.length} items</span></span>
            <ChevronRight aria-hidden className="size-4 text-muted-foreground transition-transform group-open:rotate-90" />
          </summary>
          <div className="border-t border-border p-5"><ContextCards team={team} items={items} allItems={context} people={people} evidenceHref={`/evidence?team=${encodeURIComponent(team.id)}`} /></div>
        </details>
      </div>
    </div>
  );
}

export function TeamDetailSkeleton() {
  return (
    <div className="space-y-6">
      <Skeleton className="h-4 w-24" />
      <Skeleton className="h-8 w-48" />
      <Skeleton className="h-4 w-72 max-w-full" />
      <Skeleton className="h-44 w-full rounded-xl" />
      <Skeleton className="h-80 w-full rounded-xl" />
      <Skeleton className="h-14 w-full rounded-xl" />
      <Skeleton className="h-14 w-full rounded-xl" />
    </div>
  );
}
