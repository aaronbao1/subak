"use client";
import { useEffect, useMemo, useState } from "react";
import { SlidersHorizontal } from "lucide-react";
import { scopeView } from "@/components/dashboard/forecast-derive";
import { WeeklySpendOverview } from "@/components/forecast/weekly-spend-overview";
import { BudgetOverviewBar } from "@/components/dashboard/budget-overview-bar";
import { BudgetRequestsOverview } from "@/components/requests/budget-requests-overview";
import { TeamAllocationSummary } from "@/components/dashboard/team-allocation-summary";
import { CostComponents } from "@/components/dashboard/cost-components";
import { ModelBreakdown } from "@/components/dashboard/model-breakdown";
import { DailySpendByTeam } from "@/components/dashboard/daily-spend-by-team";
import { AllocationWorkbench } from "@/components/allocation/allocation-workbench";
import { HeroSkeleton } from "@/components/dashboard/hero";
import { useAppStore } from "@/lib/store";
import { defaultWeeklyHistoryQuery } from "@/lib/data/weekly-history";
import { Button } from "@/components/ui/button";
import { PageTitle } from "@/components/shared/stat-tile";

export default function OverviewPage() {
  const { loaded, company, teams, spending, forecastBundle, forecastRefresh, forecastError, refreshForecast, weeklyHistory, weeklyHistoryState, weeklyHistoryError, loadWeeklyHistory } = useAppStore();
  const [allocation, setAllocation] = useState<{ open: boolean; teamId?: string }>({ open: false });
  const [initialAsOf] = useState(() => new Date().toISOString());
  const issued = scopeView(forecastBundle, "company");
  const asOf = String(issued?.publication?.information_cutoff ?? issued?.information_cutoff ?? issued?.generated_at ?? initialAsOf);
  const query = useMemo(() => defaultWeeklyHistoryQuery(asOf, { type: "company", id: company?.id ?? null }, 4, 3), [asOf, company?.id]);
  useEffect(() => { if (loaded) void loadWeeklyHistory(query); }, [loaded, query, loadWeeklyHistory]);
  const updatingForecast = ["pending", "queued", "running"].includes(forecastRefresh?.status ?? "");
  if (!loaded) return <div className="space-y-6"><PageTitle title="Overview" /><HeroSkeleton /></div>;
  return <div className="min-w-0 space-y-5">
    <PageTitle title="Overview" actions={<Button onClick={() => setAllocation({ open: true })} className="bg-brand text-brand-foreground hover:bg-brand-hover"><SlidersHorizontal className="size-4" />Adjust allocations</Button>} />
    <BudgetOverviewBar />
    {forecastError && <p role="alert" className="rounded-md border border-warning/30 px-4 py-3 text-sm">{forecastError}</p>}
    <WeeklySpendOverview history={weeklyHistory} loading={weeklyHistoryState === "loading" || weeklyHistoryState === "idle"} error={weeklyHistoryError} onRetry={() => void loadWeeklyHistory(query)} onUpdateForecast={() => void refreshForecast()} updatingForecast={updatingForecast} />
    <div className="grid min-w-0 items-start gap-5 xl:grid-cols-[minmax(0,1.8fr)_minmax(280px,1fr)]">
      <TeamAllocationSummary onAdjust={teamId => setAllocation({ open: true, teamId })} compact showBudgetSummary={false} />
      <BudgetRequestsOverview />
    </div>
    {company && <div className="grid min-w-0 items-start gap-5 lg:grid-cols-2">
      <CostComponents spending={spending} period={company.currentPeriod} unit={company.budgetUnit} />
      <ModelBreakdown spending={spending} period={company.currentPeriod} unit={company.budgetUnit} />
    </div>}
    {company && <DailySpendByTeam records={spending} teams={teams} period={company.currentPeriod} unit="usd" />}
    <AllocationWorkbench open={allocation.open} initialTeamId={allocation.teamId} onOpenChange={open => setAllocation(previous => ({ ...previous, open }))} />
  </div>;
}
