"use client";
import Link from "next/link";
import { ArrowLeft, MessageSquare, SearchX } from "lucide-react";
import { ForecastPanel } from "@/components/forecast/forecast-panel";
import { useAppStore } from "@/lib/store";
import type { Team } from "@/lib/contracts";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { formatAmount } from "@/lib/format";
import { cn } from "@/lib/utils";
import { PageTitle, StatTile } from "@/components/shared/stat-tile";
import { riseDelay, useMounted } from "@/components/shared/motion";
import { CountUpAmount, CountUpPct } from "@/components/team/count-up";
import { TeamSpendChart } from "@/components/team/team-spend-chart";
import { ContextCards } from "@/components/team/context-cards";
import { TeamDetailSkeleton } from "@/components/team/team-detail";
import { fmtDate } from "@/components/team/labels";
import { IntegrationChip } from "./signal-badges";
import { WeekChange } from "./people-table";
import { personContextItems, summarizePeople } from "./derive";

/* Entrance (ms): link and title 0 · four tiles 60–240 (numbers count up from each tile's delay) · assumptions 300 ·
   chart card 300 with its columns rising 0–1180 · day buttons 360 · context cards 420+. Last rise ends ≤1200. */
const CHART_AT = 300;
const CONTEXT_AT = 420;

/** /teams/[teamId]/people/[personId]: one individual's spend, projection, and the connector signals that explain it. */
export function PersonDetail({ teamId, personId }: { teamId: string; personId: string }) {
  const { loaded, company, teams, people, spending, spendingHistory, budgets, forecasts, personForecasts, context, askAssistant } = useAppStore();
  const mounted = useMounted();
  const rise = mounted ? "animate-rise" : "opacity-0";
  if (!loaded) return <TeamDetailSkeleton />;

  const team = teams.find((t) => t.id === teamId);
  const person = people.find((p) => p.id === personId && p.teamId === teamId);
  if (!team || !person) {
    return (
      <div className="space-y-6">
        <Link href={team ? `/teams/${team.id}` : "/teams"} className="inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors duration-300 hover:text-foreground">
          <ArrowLeft className="size-4" aria-hidden strokeWidth={1.5} /> {team ? team.name : "All teams"}
        </Link>
        <div className="flex flex-col items-center gap-2 rounded-xl border border-border py-16 text-center">
          <SearchX className="size-4 text-muted-foreground" aria-hidden strokeWidth={1.5} />
          <div className="eyebrow">Person not found</div>
          <p className="max-w-sm text-sm text-muted-foreground">
            No one with id <code className="rounded-sm bg-popover px-1 font-mono text-xs">{personId}</code> is on {team?.name ?? "this team"}.
          </p>
        </div>
      </div>
    );
  }

  const period = company?.currentPeriod ?? budgets[0]?.period;
  const summary = period ? summarizePeople(people, team.id, spending, spendingHistory, personForecasts, context, period, forecasts.find(f => f.teamId === team.id)).find((s) => s.person.id === person.id) : undefined;
  const unit = budgets.find((b) => b.teamId === team.id)?.unit ?? company?.budgetUnit ?? "usd";
  const records = spending.filter((r) => r.personId === person.id);
  const forecast = summary?.forecast;
  const items = personContextItems(context, person);
  // Downstream components are keyed on a Team; a person renders through the same chart and cards in the team's color.
  const asTeam: Team = { id: person.id, name: person.name, color: team.color, lead: team.lead, description: person.role };

  return (
    <div className="space-y-8">
      <header className="space-y-6">
        <Link href={`/teams/${team.id}`} className={cn("inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors duration-300 hover:text-foreground", rise)}>
          <ArrowLeft className="size-4" aria-hidden strokeWidth={1.5} /> {team.name}
        </Link>

        <PageTitle
          className={rise}
          title={
            <span className="flex items-center gap-2.5">
              <span aria-hidden className="size-2.5 shrink-0 rounded-full" style={{ background: team.color }} />
              {person.name}
            </span>
          }
          description={
            <>
              {person.role ?? "Member"} · <Link href={`/teams/${team.id}`} className="text-foreground/80 underline-offset-4 hover:underline">{team.name}</Link>
              {person.primaryTool && <> · {person.primaryTool}</>}
              {person.integrations && person.integrations.length > 0 && (
                <span className="mt-2 flex flex-wrap items-center gap-1.5">
                  <span className="text-xs">Connected</span>
                  {person.integrations.map((i) => <IntegrationChip key={i} integration={i} />)}
                </span>
              )}
            </>
          }
          actions={
            <Button variant="outline" onClick={() => askAssistant(`Why is ${person.name}'s usage changing this week?`)}>
              <MessageSquare className="text-muted-foreground" strokeWidth={1.5} /> Ask the assistant
            </Button>
          }
        />

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div className={rise} style={riseDelay(1)}>
            <StatTile className="h-full" size="primary" card label="Spent to date" value={<CountUpAmount value={summary?.spent ?? 0} unit={unit} delay={60} />} caption={period?.label} />
          </div>
          <div className={rise} style={riseDelay(2)}>
            <StatTile
              className="h-full"
              size="primary"
              card
              label="Projected for period"
              value={summary?.projected != null ? <CountUpAmount value={summary.projected} unit={unit} delay={120} /> : "No projection"}
              muted={summary?.projected == null}
              caption={
                summary?.low != null && summary?.high != null
                  ? <span className="num">{formatAmount(summary.low, unit, { compact: true })} – {formatAmount(summary.high, unit, { compact: true })}</span>
                  : forecast?.unavailableReason
              }
            />
          </div>
          <div className={rise} style={riseDelay(3)}>
            <StatTile
              className="h-full"
              size="primary"
              card
              label="Share of team projection"
              value={summary?.share != null ? <CountUpPct value={summary.share * 100} delay={180} /> : "—"}
              muted={summary?.share == null}
              caption={summary?.share != null ? "Of the team's projected total" : "Requires a matching team total and historical team attribution"}
            />
          </div>
          <div className={rise} style={riseDelay(4)}>
            <StatTile
              className="h-full"
              size="primary"
              card
              label="vs last week"
              value={<WeekChange value={summary?.weekChange} />}
              caption="Average daily spend, complete days"
            />
          </div>
        </div>

        {forecast?.status === "available" && forecast.assumptions.length > 0 && (
          <div className={cn("flex flex-wrap items-center gap-x-2 gap-y-1.5 rounded-xl border border-border bg-card px-4 py-3 text-xs", rise)} style={riseDelay(5)}>
            <span className="font-medium text-foreground">Projection assumes</span>
            <span className="text-muted-foreground">{forecast.assumptions.join(" · ")}</span>
            <span className="text-muted-foreground">Generated <span className="num">{fmtDate(forecast.generatedAt)}</span></span>
          </div>
        )}
      </header>

      <ForecastPanel scopeType="person" scopeId={personId} />
      <TeamSpendChart team={asTeam} records={records} forecast={forecast} unit={unit} enterAt={CHART_AT} />
      <ContextCards team={asTeam} items={items} allItems={context} people={people} enterAt={CONTEXT_AT} evidenceHref={`/evidence?scope=person&team=${encodeURIComponent(team.id)}`} />
    </div>
  );
}

export function PersonDetailSkeleton() {
  return (
    <div className="space-y-8">
      <Skeleton className="h-4 w-20" />
      <Skeleton className="h-7 w-48" />
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="space-y-2 rounded-xl border border-border bg-card p-4">
            <Skeleton className="h-3 w-20" />
            <Skeleton className="h-8 w-28" />
            <Skeleton className="h-3 w-36 max-w-full" />
          </div>
        ))}
      </div>
      <Skeleton className="h-64 w-full rounded-xl" />
    </div>
  );
}
