"use client";
import { useCallback, useMemo, useState } from "react";
import { useAppStore } from "@/lib/store";
import { Card, CardContent } from "@/components/ui/card";
import { Hero, HeroSkeleton } from "@/components/dashboard/hero";
import { SpendByTeamChart, SpendByTeamChartSkeleton } from "@/components/dashboard/spend-by-team-chart";
import { TeamBreakdownPanel } from "@/components/dashboard/team-breakdown-panel";
import { CostComponents, CostComponentsSkeleton } from "@/components/dashboard/cost-components";
import { TeamGrid, TeamGridSkeleton } from "@/components/dashboard/team-grid";
import { buildDailyRows, completion, dateLabel, summarizeTeams } from "@/components/dashboard/derive";

export default function OverviewPage() {
  const { loaded, company, teams, spending, budgets, forecasts, askAssistant } = useAppStore();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const toggleTeam = useCallback((id: string) => setSelectedId((cur) => (cur === id ? null : id)), []);

  const unit = company?.budgetUnit ?? budgets[0]?.unit ?? "usd";
  const summaries = useMemo(() => summarizeTeams(teams, spending, budgets, forecasts), [teams, spending, budgets, forecasts]);
  const rows = useMemo(() => buildDailyRows(teams, spending), [teams, spending]);
  const { asOf, partialDates } = useMemo(() => completion(spending), [spending]);

  const spent = summaries.reduce((s, t) => s + t.spent, 0);
  const envelope = budgets.length ? budgets.reduce((s, b) => s + b.allocated, 0) : undefined;
  const withProjection = summaries.filter((s) => typeof s.projected === "number");
  const projected = withProjection.length ? withProjection.reduce((s, t) => s + (t.projected ?? 0), 0) : undefined;
  const unavailableCount = teams.length - withProjection.length;
  const hasPlaceholder = forecasts.some((f) => f.origin === "placeholder");
  const period = forecasts.find((f) => f.period.label)?.period ?? budgets.find((b) => b.period.label)?.period ?? company?.currentPeriod;
  const periodRange = period ? `${dateLabel(period.start)} to ${dateLabel(period.end)}` : undefined;

  // Drop a selection that no longer exists (e.g. dataset switched).
  const selected = selectedId !== null ? summaries.find((s) => s.team.id === selectedId) ?? null : null;

  if (!loaded) {
    return (
      <div className="space-y-6">
        <HeroSkeleton />
        <SpendByTeamChartSkeleton />
        <CostComponentsSkeleton />
        <TeamGridSkeleton />
      </div>
    );
  }

  return (
    <div className="min-w-0 space-y-6">
      <Hero
        unit={unit} spent={spent} envelope={envelope} projected={projected}
        projectedTeamCount={withProjection.length} unavailableCount={unavailableCount} teamCount={teams.length}
        periodLabel={period?.label} periodRange={periodRange} asOf={asOf}
        hasPlaceholder={hasPlaceholder} isDemo={company?.isDemo ?? false}
      />

      {teams.length === 0 ? (
        <Card>
          <CardContent className="py-10 text-center">
            <p className="font-medium">No teams yet.</p>
            <p className="mt-1 text-sm text-muted-foreground">Add teams and budgets to start planning.</p>
          </CardContent>
        </Card>
      ) : (
        <>
          <section className="grid min-w-0 gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(300px,340px)]" aria-label="Daily spend">
            <SpendByTeamChart
              teams={teams} rows={rows} partialDates={partialDates} unit={unit}
              selectedId={selectedId} onSelect={toggleTeam}
            />
            <TeamBreakdownPanel summary={selected} unit={unit} onClose={() => setSelectedId(null)} askAssistant={askAssistant} />
          </section>

          <CostComponents spending={spending} unit={unit} />

          <TeamGrid summaries={summaries} unit={unit} selectedId={selectedId} onSelect={toggleTeam} />
        </>
      )}
    </div>
  );
}
