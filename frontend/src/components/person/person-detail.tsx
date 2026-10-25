"use client";
import { displaySourceText } from "@/lib/display-copy";
import Link from "next/link";
import { ArrowLeft, ArrowUpRight, ChevronRight, MessageSquare, SearchX } from "lucide-react";
import { ForecastPanel } from "@/components/forecast/forecast-panel";
import { useAppStore } from "@/lib/store";
import type { Team } from "@/lib/contracts";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { formatAmount } from "@/lib/format";
import { selectScopeSummary } from "@/lib/finance-summary";
import { usageActivityHref } from "@/lib/usage-link";
import { scopeView } from "@/components/dashboard/forecast-derive";
import { PageTitle, StatTile } from "@/components/shared/stat-tile";
import { ContextCards } from "@/components/team/context-cards";
import { fmtDate } from "@/components/team/labels";
import { IntegrationChip } from "./signal-badges";
import { personContextItems } from "./derive";

export function PersonDetail({ teamId, personId }: { teamId: string; personId: string }) {
  const { loaded, company, teams, people, spending, budgets, context, forecastBundle, askAssistant } = useAppStore();
  if (!loaded) return <PersonDetailSkeleton />;
  const team = teams.find(item => item.id === teamId);
  const person = people.find(item => item.id === personId && item.teamId === teamId);
  if (!team || !person) return (
    <div className="space-y-6">
      <Link href={team ? `/teams/${team.id}` : "/teams"} className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"><ArrowLeft className="size-4" aria-hidden />{team ? displaySourceText(team.name, "Team") : "All teams"}</Link>
      <div className="flex flex-col items-center gap-2 rounded-xl border border-border bg-card px-5 py-16 text-center">
        <SearchX className="size-5 text-muted-foreground" aria-hidden />
        <h1 className="text-lg font-medium">Person not found</h1>
        <p className="max-w-sm text-sm text-muted-foreground">This person is not available on {displaySourceText(team?.name, "this team")}.</p>
      </div>
    </div>
  );
  const budget = budgets.find(item => item.teamId === team.id);
  const period = company?.currentPeriod ?? budget?.period;
  const unit = budget?.unit ?? company?.budgetUnit ?? "usd";
  const records = spending.filter(record => record.personId === person.id && (!period || record.date >= period.start && record.date <= period.end));
  const summary = period ? selectScopeSummary({ scope: { type: "person", id: person.id }, period, unit, datasetId: company?.id ?? "current", spending: records, budgets, forecastView: scopeView(forecastBundle, "person", person.id) }) : undefined;
  const lastDate = records.reduce<string | undefined>((latest, record) => !latest || record.date > latest ? record.date : latest, undefined);
  const periodLabel = period?.label ?? (period ? `${fmtDate(period.start)} – ${fmtDate(period.end)}` : "Current period");
  const items = personContextItems(context, person);
  const asTeam: Team = { id: person.id, name: person.name, color: team.color, lead: team.lead, description: person.role };
  const usageHref = usageActivityHref({ type: "person", id: person.id }, period);
  return (
    <div className="min-w-0 space-y-6">
      <header className="space-y-5">
        <Link href={`/teams/${team.id}`} className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"><ArrowLeft className="size-4" aria-hidden strokeWidth={1.5} />{displaySourceText(team.name, "Team")}</Link>
        <PageTitle
          title={<span className="flex items-center gap-2.5"><span aria-hidden className="size-2.5 shrink-0 rounded-full" style={{ background: team.color }} />{displaySourceText(person.name, "Person")}</span>}
          description={<>{displaySourceText(person.role, "Member")} · <Link href={`/teams/${team.id}`} className="text-foreground/80 underline-offset-4 hover:underline">{displaySourceText(team.name, "Team")}</Link>{person.primaryTool && <> · {displaySourceText(person.primaryTool)}</>}</>}
          actions={<Button variant="outline" onClick={() => askAssistant(`Explain ${person.name}'s recorded spend and outlook for ${periodLabel}`)}><MessageSquare className="text-muted-foreground" strokeWidth={1.5} /> Ask about this person</Button>}
        />
        <section className="rounded-xl border border-border bg-card" aria-label={`${displaySourceText(person.name, "Person")} recorded spending`}>
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-5 py-3"><h2 className="text-sm font-medium">{displaySourceText(periodLabel, "Current period")}</h2><Link href={usageHref} className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground">Usage activity <ArrowUpRight aria-hidden className="size-3.5" /></Link></div>
          <StatTile className="p-5" size="primary" label="Recorded spend" value={summary?.observed.amount == null ? "—" : formatAmount(summary.observed.amount, unit)} muted={summary?.observed.amount == null} caption={lastDate ? `Data through ${fmtDate(lastDate)}${summary?.observed.byProvenance.estimate ? " · includes estimates" : ""}` : "No spending recorded for this period"} />
        </section>
      </header>
      <ForecastPanel scopeType="person" scopeId={personId} />
      <details className="group rounded-xl border border-border bg-card">
        <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-5 py-4 text-sm font-medium outline-none focus-visible:ring-2 focus-visible:ring-ring [&::-webkit-details-marker]:hidden"><span>Connected activity and sources <span className="ml-2 font-normal text-muted-foreground">{items.length} items</span></span><ChevronRight aria-hidden className="size-4 text-muted-foreground transition-transform group-open:rotate-90" /></summary>
        <div className="space-y-5 border-t border-border p-5">
          {!!person.integrations?.length && <div className="flex flex-wrap items-center gap-2"><span className="text-xs text-muted-foreground">Connected tools</span>{person.integrations.map(integration => <IntegrationChip key={integration} integration={integration} />)}</div>}
          <ContextCards team={asTeam} items={items} allItems={context} people={people} evidenceHref={`/evidence?scope=person&team=${encodeURIComponent(team.id)}`} />
        </div>
      </details>
    </div>
  );
}

export function PersonDetailSkeleton() {
  return <div className="space-y-6"><Skeleton className="h-4 w-24" /><Skeleton className="h-8 w-48" /><Skeleton className="h-4 w-64 max-w-full" /><Skeleton className="h-40 w-full rounded-xl" /><Skeleton className="h-80 w-full rounded-xl" /></div>;
}
