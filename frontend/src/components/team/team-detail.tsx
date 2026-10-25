"use client";
import Link from "next/link";
import { ArrowLeft, SearchX } from "lucide-react";
import { useAppStore } from "@/lib/store";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { TeamHeader } from "./team-header";
import { TeamSpendChart } from "./team-spend-chart";
import { ContextCards } from "./context-cards";
import { teamRecords, teamUnit } from "./labels";

/** Client body for /teams/[teamId]: header, spend chart, context. Handles loading and unknown ids. */
export function TeamDetail({ teamId }: { teamId: string }) {
  const { loaded, teams, spending, budgets, forecasts, context } = useAppStore();

  if (!loaded) return <TeamDetailSkeleton />;

  const team = teams.find((t) => t.id === teamId);
  if (!team) {
    return (
      <div className="space-y-4">
        <Link href="/teams" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="size-3.5" /> Back to overview
        </Link>
        <Card>
          <CardContent className="flex flex-col items-center gap-2 py-10 text-center">
            <SearchX className="size-6 text-muted-foreground" />
            <div className="font-medium">Team not found</div>
            <p className="max-w-sm text-sm text-muted-foreground">
              No team with id <code className="rounded bg-muted px-1">{teamId}</code> exists in this company.
              {teams.length === 0 && " No teams are set up yet."}
            </p>
            <Button variant="outline" size="sm" className="mt-2" nativeButton={false} render={<Link href="/teams" />}>
              All teams
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  const records = teamRecords(spending, team.id);
  const budget = budgets.find((b) => b.teamId === team.id);
  const forecast = forecasts.find((f) => f.teamId === team.id);
  const unit = teamUnit(team, budget, records);
  const items = context.filter((c) => c.teamIds.includes(team.id));

  return (
    <div className="space-y-6">
      <TeamHeader team={team} budget={budget} forecast={forecast} records={records} />
      <TeamSpendChart team={team} records={records} unit={unit} />
      <ContextCards team={team} items={items} allItems={context} />
    </div>
  );
}

export function TeamDetailSkeleton() {
  return (
    <div className="space-y-6">
      <div className="space-y-3">
        <Skeleton className="h-4 w-28" />
        <div className="flex items-center gap-2">
          <Skeleton className="size-3 rounded-full" />
          <Skeleton className="h-6 w-40" />
        </div>
        <Skeleton className="h-4 w-72 max-w-full" />
      </div>
      <div className="grid gap-3 sm:grid-cols-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <Card key={i} size="sm">
            <CardContent className="space-y-2">
              <Skeleton className="h-3 w-20" />
              <Skeleton className="h-7 w-28" />
              <Skeleton className="h-3 w-36" />
            </CardContent>
          </Card>
        ))}
      </div>
      <Card>
        <CardContent className="space-y-3">
          <Skeleton className="h-4 w-24" />
          <Skeleton className="h-64 w-full" />
        </CardContent>
      </Card>
      <div className="grid gap-3 lg:grid-cols-2">
        {Array.from({ length: 2 }).map((_, i) => (
          <Card key={i} size="sm">
            <CardContent className="space-y-2">
              <Skeleton className="h-4 w-48" />
              <Skeleton className="h-3 w-full" />
              <Skeleton className="h-3 w-5/6" />
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
