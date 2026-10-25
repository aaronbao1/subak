"use client";
import { displaySourceText } from "@/lib/display-copy";
import { useState } from "react";
import Link from "next/link";
import { ArrowLeft, ArrowUpRight, MessageSquare } from "lucide-react";
import type { Budget, SpendingRecord, Team } from "@/lib/contracts";
import { useAppStore } from "@/lib/store";
import { formatAmount } from "@/lib/format";
import { selectScopeSummary } from "@/lib/finance-summary";
import { usageActivityHref } from "@/lib/usage-link";
import { scopeView } from "@/components/dashboard/forecast-derive";
import { PageTitle, StatTile } from "@/components/shared/stat-tile";
import { Button } from "@/components/ui/button";
import { AllocationWorkbench } from "@/components/allocation/allocation-workbench";
import { fmtDate, teamUnit } from "./labels";

interface Props { team: Team; budget?: Budget; records: SpendingRecord[] }

/** Keep the current period's recorded spend and allocation ahead of the longer outlook. */
export function TeamHeader({ team, budget, records }: Props) {
  const { askAssistant, company, budgets, forecastBundle } = useAppStore();
  const [allocationOpen, setAllocationOpen] = useState(false);
  const period = company?.currentPeriod ?? budget?.period;
  const unit = teamUnit(budget, records);
  const summary = period ? selectScopeSummary({ scope: { type: "team", id: team.id }, period, unit, datasetId: company?.id ?? "current", spending: records, budgets, forecastView: scopeView(forecastBundle, "team", team.id) }) : undefined;
  const periodRecords = records.filter(record => !period || record.date >= period.start && record.date <= period.end);
  const lastDate = periodRecords.reduce<string | undefined>((latest, record) => !latest || record.date > latest ? record.date : latest, undefined);
  const periodLabel = period?.label ?? (period ? `${fmtDate(period.start)} – ${fmtDate(period.end)}` : "Current period");
  const usageHref = usageActivityHref({ type: "team", id: team.id }, period);
  const canAdjust = !!company?.currentPeriod && summary?.allocation != null && unit === company.budgetUnit;

  return (
    <header className="space-y-5">
      <Link href="/teams" className="inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground">
        <ArrowLeft className="size-4" aria-hidden strokeWidth={1.5} /> All teams
      </Link>
      <PageTitle
        title={<span className="flex items-center gap-2.5"><span aria-hidden className="size-2.5 shrink-0 rounded-full" style={{ background: team.color }} />{displaySourceText(team.name, "Team")}</span>}
        description={<>{team.lead ? `Led by ${displaySourceText(team.lead, "team lead")}` : "No lead listed"}{team.description && <> · {displaySourceText(team.description)}</>}</>}
        actions={<div className="flex flex-wrap gap-2"><Button disabled={!canAdjust} onClick={() => setAllocationOpen(true)}>Adjust allocation</Button><Button variant="outline" onClick={() => askAssistant(`Tell me about ${team.name}'s spending and outlook for ${periodLabel}`)}><MessageSquare className="text-muted-foreground" strokeWidth={1.5} /> Ask about this team</Button></div>}
      />
      <section className="overflow-hidden rounded-xl border border-border bg-card" aria-label={`${displaySourceText(team.name, "Team")} current period spending`}>
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-5 py-3">
          <h2 className="text-sm font-medium">{displaySourceText(periodLabel, "Current period")}</h2>
          <div className="flex items-center gap-4"><Link href={usageHref} className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground">Usage activity <ArrowUpRight aria-hidden className="size-3.5" /></Link><Link href={`/requests?team=${encodeURIComponent(team.id)}`} className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground">Team requests <ArrowUpRight aria-hidden className="size-3.5" /></Link></div>
        </div>
        <div className="grid divide-y divide-border sm:grid-cols-2 sm:divide-x sm:divide-y-0">
          <StatTile className="p-5" size="primary" label="Recorded spend" value={summary?.observed.amount == null ? "—" : formatAmount(summary.observed.amount, unit)} muted={summary?.observed.amount == null} caption={lastDate ? `Data through ${fmtDate(lastDate)}${summary?.observed.byProvenance.estimate ? " · includes estimates" : ""}` : "No spending recorded for this period"} />
          <StatTile className="p-5" size="primary" label="Allocation" value={summary?.allocation == null ? "—" : formatAmount(summary.allocation, unit)} muted={summary?.allocation == null} caption={summary?.allocation == null ? "No matching allocation" : "Team budget for this period"} />
        </div>
      </section>
      <AllocationWorkbench open={allocationOpen} onOpenChange={setAllocationOpen} initialTeamId={team.id} />
    </header>
  );
}
