"use client";
import { useCallback, useMemo, useState } from "react";
import { useAppStore } from "@/lib/store";
import { Hero, HeroSkeleton } from "@/components/dashboard/hero";
import { SpendByTeamChart, SpendByTeamChartSkeleton } from "@/components/dashboard/spend-by-team-chart";
import { TeamBreakdownPanel } from "@/components/dashboard/team-breakdown-panel";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import Link from "next/link";
import { CostComponents, CostComponentsSkeleton } from "@/components/dashboard/cost-components";
import { buildDailyRows, completion, dateLabel, summarizeTeams } from "@/components/dashboard/derive";
import { summarizePeople } from "@/components/person/derive";


export default function OverviewPage() {
  const { loaded, company, teams, people, spending, spendingHistory, budgets, forecasts, personForecasts, context, askAssistant } = useAppStore();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const toggleTeam = useCallback((id: string) => setSelectedId((cur) => (cur === id ? null : id)), []);

  const unit = company?.budgetUnit ?? budgets[0]?.unit ?? "usd";
  const summaries = useMemo(() => summarizeTeams(teams, spending, budgets, forecasts), [teams, spending, budgets, forecasts]);
  const period = forecasts.find((f) => f.period.label)?.period ?? budgets.find((b) => b.period.label)?.period ?? company?.currentPeriod;
  // The chart gets the full history so finance can scroll back and see growth; totals stay on the period.
  const rows = useMemo(() => buildDailyRows(teams, spendingHistory, forecasts, period), [teams, spendingHistory, forecasts, period]);
  const { asOf, partialDates } = useMemo(() => completion(spending), [spending]);

  const spent = summaries.reduce((s, t) => s + t.spent, 0);
  const envelope = budgets.length ? budgets.reduce((s, b) => s + b.allocated, 0) : undefined;
  const withProjection = summaries.filter((s) => typeof s.projected === "number");
  const projected = withProjection.length ? withProjection.reduce((s, t) => s + (t.projected ?? 0), 0) : undefined;
  const unavailableCount = teams.length - withProjection.length;
  const unavailableTeams = useMemo(() => summaries.filter((s) => typeof s.projected !== "number").map((s) => s.team.name), [summaries]);
  const hasPlaceholder = forecasts.some((f) => f.origin === "placeholder");
  const periodRange = period ? `${dateLabel(period.start)} to ${dateLabel(period.end)}` : undefined;

  // Drop a selection that no longer exists (e.g. dataset switched).
  const selected = selectedId !== null ? summaries.find((s) => s.team.id === selectedId) ?? null : null;
  const selectedPeople = useMemo(
    () => (selected && period ? summarizePeople(people, selected.team.id, spending, spendingHistory, personForecasts, context, period) : []),
    [selected, period, people, spending, spendingHistory, personForecasts, context],
  );

  if (!loaded) {
    return (
      <div className="mx-auto w-full max-w-7xl min-w-0 space-y-6">
        <HeroSkeleton />
        <SpendByTeamChartSkeleton />
        <CostComponentsSkeleton />
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-7xl min-w-0 space-y-6">
      <Hero
        unit={unit} spent={spent} envelope={envelope} projected={projected}
        projectedTeamCount={withProjection.length} unavailableCount={unavailableCount} unavailableTeams={unavailableTeams} teamCount={teams.length}
        periodLabel={period?.label} periodRange={periodRange} asOf={asOf}
        hasPlaceholder={hasPlaceholder} isDemo={company?.isDemo ?? false}
        summaries={summaries}
      />

      {teams.length === 0 ? (
        <div className="flex flex-col items-center rounded-xl border border-border bg-card px-6 py-16 text-center">
          <p className="eyebrow">No teams yet</p>
          <p className="mt-3 text-sm text-muted-foreground">Add teams and budgets to start planning.</p>
          <Button variant="outline" className="mt-6" nativeButton={false} render={<Link href="/teams" />}>Go to teams</Button>
        </div>
      ) : (
        <>
          <section aria-label="Daily spend">
            <SpendByTeamChart
              teams={teams} rows={rows} partialDates={partialDates} unit={unit} period={period}
              selectedId={selectedId} onSelect={toggleTeam} placeholder={hasPlaceholder}
            />
          </section>

          {/* Team breakdown slides in from the right when a line or legend chip is clicked. */}
          {/* Non-modal so the chart and hero stay visible and clickable while a team's breakdown is open. */}
          <Sheet open={selected !== null} onOpenChange={(open) => { if (!open) setSelectedId(null); }} modal={false} disablePointerDismissal>
            <SheetContent side="right" overlay={false} showCloseButton={false} className="w-full gap-0 overflow-y-auto border-l border-border p-0 shadow-2xl sm:max-w-md">
              {selected && <SheetTitle className="sr-only">{selected.team.name} breakdown</SheetTitle>}
              <TeamBreakdownPanel summary={selected} unit={unit} onClose={() => setSelectedId(null)} askAssistant={askAssistant} people={selectedPeople} />
            </SheetContent>
          </Sheet>

          <CostComponents spending={spending} unit={unit} />
        </>
      )}
    </div>
  );
}
