"use client";
import Link from "next/link";
import { ArrowLeft, MessageSquare, SearchX } from "lucide-react";
import { useAppStore } from "@/lib/store";
import type { Team } from "@/lib/contracts";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { formatAmount, formatPct } from "@/lib/format";
import { cn } from "@/lib/utils";
import { TeamSpendChart } from "@/components/team/team-spend-chart";
import { ContextCards } from "@/components/team/context-cards";
import { TeamDetailSkeleton } from "@/components/team/team-detail";
import { fmtDate } from "@/components/team/labels";
import { IntegrationChip } from "./signal-badges";
import { WeekChange } from "./people-table";
import { personContextItems, summarizePeople } from "./derive";

/** /teams/[teamId]/people/[personId]: one individual's spend, projection, and the connector signals that explain it. */
export function PersonDetail({ teamId, personId }: { teamId: string; personId: string }) {
  const { loaded, company, teams, people, spending, spendingHistory, budgets, personForecasts, context, askAssistant } = useAppStore();
  if (!loaded) return <TeamDetailSkeleton />;

  const team = teams.find((t) => t.id === teamId);
  const person = people.find((p) => p.id === personId && p.teamId === teamId);
  if (!team || !person) {
    return (
      <div className="mx-auto max-w-5xl space-y-5">
        <Link href={team ? `/teams/${team.id}` : "/teams"} className="inline-flex items-center gap-1 text-xs text-muted-foreground transition-colors hover:text-foreground">
          <ArrowLeft className="size-3" /> {team ? team.name : "All teams"}
        </Link>
        <div className="flex flex-col items-center gap-2 rounded-xl border border-dashed py-14 text-center">
          <SearchX className="size-5 text-muted-foreground" />
          <div className="text-sm font-medium">Person not found</div>
          <p className="max-w-sm text-sm text-muted-foreground">
            No one with id <code className="rounded-sm bg-muted px-1 font-mono text-xs">{personId}</code> is on {team?.name ?? "this team"}.
          </p>
        </div>
      </div>
    );
  }

  const period = company?.currentPeriod ?? budgets[0]?.period;
  const summary = period ? summarizePeople(people, team.id, spending, spendingHistory, personForecasts, context, period).find((s) => s.person.id === person.id) : undefined;
  const unit = budgets.find((b) => b.teamId === team.id)?.unit ?? company?.budgetUnit ?? "usd";
  const records = spending.filter((r) => r.personId === person.id);
  const forecast = summary?.forecast;
  const items = personContextItems(context, person);
  // Downstream components are keyed on a Team; a person renders through the same chart and cards in the team's color.
  const asTeam: Team = { id: person.id, name: person.name, color: team.color, lead: team.lead, description: person.role };

  return (
    <div className="mx-auto max-w-5xl space-y-8">
      <header className="space-y-5">
        <Link href={`/teams/${team.id}`} className="inline-flex items-center gap-1 text-xs text-muted-foreground transition-colors hover:text-foreground">
          <ArrowLeft className="size-3" /> {team.name}
        </Link>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0 space-y-1.5">
            <h1 className="flex items-center gap-2.5 text-lg font-semibold tracking-tight">
              <span aria-hidden className="size-2.5 shrink-0 rounded-full" style={{ background: team.color }} />
              {person.name}
            </h1>
            <p className="text-sm text-muted-foreground">
              {person.role ?? "Member"} · <Link href={`/teams/${team.id}`} className="text-foreground/85 hover:underline">{team.name}</Link>
              {person.primaryTool && <span className="text-muted-foreground/80"> · {person.primaryTool}</span>}
            </p>
            {person.integrations && person.integrations.length > 0 && (
              <div className="flex flex-wrap items-center gap-1.5 pt-0.5">
                <span className="text-[11px] text-muted-foreground">Connected:</span>
                {person.integrations.map((i) => <IntegrationChip key={i} integration={i} />)}
              </div>
            )}
          </div>
          <Button variant="outline" size="sm" onClick={() => askAssistant(`Why is ${person.name}'s usage changing this week?`)}>
            <MessageSquare /> Ask assistant
          </Button>
        </div>

        <dl className="grid overflow-hidden rounded-xl border sm:grid-cols-4 sm:divide-x sm:divide-border/60 max-sm:divide-y max-sm:divide-border/60">
          <Figure label="Spent to date" value={formatAmount(summary?.spent ?? 0, unit)} sub={period?.label} />
          <Figure
            label="Projected for period"
            value={summary?.projected != null ? formatAmount(summary.projected, unit) : "No projection"}
            muted={summary?.projected == null}
            sub={summary?.low != null && summary?.high != null ? `${formatAmount(summary.low, unit, { compact: true })} to ${formatAmount(summary.high, unit, { compact: true })}` : forecast?.unavailableReason}
          />
          <Figure label="Share of team projection" value={summary?.share != null ? formatPct(summary.share * 100) : "—"} muted={summary?.share == null} sub="of the team's projected total" />
          <div className="min-w-0 px-4 py-3.5">
            <dt className="text-[11px] text-muted-foreground">vs last week</dt>
            <dd className="mt-0.5 text-xl font-semibold tracking-tight"><WeekChange value={summary?.weekChange} /></dd>
            <dd className="mt-0.5 truncate text-[11px] text-muted-foreground">average daily spend, complete days</dd>
          </div>
        </dl>

        {forecast?.status === "available" && forecast.assumptions.length > 0 && (
          <div className={cn("rounded-xl border bg-card px-4 py-3 text-xs", forecast.origin === "placeholder" && "border-dashed")}>
            <span className="font-medium text-foreground/90">Projection assumes:</span>{" "}
            <span className="text-muted-foreground">{forecast.assumptions.join(" · ")}</span>
            {forecast.origin === "placeholder" && <span className="ml-2 rounded-full border border-border px-1.5 text-[10px] text-muted-foreground">placeholder projection</span>}
            <span className="ml-2 text-muted-foreground/70">Generated {fmtDate(forecast.generatedAt)}</span>
          </div>
        )}
      </header>

      <TeamSpendChart team={asTeam} records={records} forecast={forecast} unit={unit} />
      <ContextCards team={asTeam} items={items} allItems={context} people={people} />
    </div>
  );
}

function Figure({ label, value, sub, muted }: { label: string; value: string; sub?: string; muted?: boolean }) {
  return (
    <div className="min-w-0 px-4 py-3.5">
      <dt className="text-[11px] text-muted-foreground">{label}</dt>
      <dd className={cn("mt-0.5 truncate text-xl font-semibold tracking-tight tabular-nums", muted && "text-base font-normal text-muted-foreground")}>{value}</dd>
      {sub && <dd className="mt-0.5 truncate text-[11px] text-muted-foreground tabular-nums">{sub}</dd>}
    </div>
  );
}

export function PersonDetailSkeleton() {
  return (
    <div className="mx-auto max-w-5xl space-y-8">
      <Skeleton className="h-3 w-16" />
      <Skeleton className="h-6 w-48" />
      <Skeleton className="h-20 w-full rounded-xl" />
      <Skeleton className="h-64 w-full rounded-xl" />
    </div>
  );
}
