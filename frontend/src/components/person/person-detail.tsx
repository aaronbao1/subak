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
import { PageTitle } from "@/components/shared/stat-tile";
import { riseDelay, useMounted } from "@/components/shared/motion";
import { CountUpAmount } from "@/components/team/count-up";
import { BulletBar, BulletLegend, DeltaChip, ShareMeter, Sparkline } from "@/components/team/viz";
import { TeamSpendChart } from "@/components/team/team-spend-chart";
import { ContextCards } from "@/components/team/context-cards";
import { TeamDetailSkeleton } from "@/components/team/team-detail";
import { fmtDate } from "@/components/team/labels";
import { INTEGRATION_LABEL } from "./signal-badges";
import { personContextItems, summarizePeople } from "./derive";

/* Entrance (ms): link and title 0 · summary card 60 (numbers count up 60/120, meter 180) ·
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
  // A person has no allocation; the bar's track is the high end of the projection range (or the projection itself).
  const rangeTop = Math.max(summary?.high ?? 0, summary?.projected ?? 0, summary?.spent ?? 0) || undefined;
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
                <span title="Connected sources"> · via {person.integrations.map((i) => INTEGRATION_LABEL[i]).join(", ")}</span>
              )}
            </>
          }
          actions={
            <Button variant="outline" onClick={() => askAssistant(`Why is ${person.name}'s usage changing this week?`)}>
              <MessageSquare className="text-muted-foreground" strokeWidth={1.5} /> Ask the assistant
            </Button>
          }
        />

        <section className={cn("rounded-xl border border-border bg-card p-5", rise)} style={riseDelay(1)} aria-label="Spend and projection">
          <div className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3">
            <BulletLegend
              size="lg"
              items={[
                { label: "Spent", mark: "fill", color: team.color, value: <CountUpAmount value={summary?.spent ?? 0} unit={unit} delay={60} /> },
                {
                  label: "Projected",
                  mark: "tick",
                  value: summary?.projected != null ? <CountUpAmount value={summary.projected} unit={unit} delay={120} /> : "None",
                  muted: summary?.projected == null,
                  title: summary?.projected != null
                    ? [
                        "Full period, includes spend to date",
                        forecast?.status === "available" && forecast.assumptions.length > 0 ? `Assumes ${forecast.assumptions.join(" · ")}` : undefined,
                        forecast?.generatedAt ? `Generated ${fmtDate(forecast.generatedAt)}` : undefined,
                      ].filter(Boolean).join(" · ")
                    : forecast?.unavailableReason,
                },
              ]}
            />
            <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-xs text-muted-foreground">
              <span className="inline-flex items-center gap-2" title={summary?.share != null ? "Share of the team's projected total" : "Needs a matching team projection"}>
                Share of team <ShareMeter share={summary?.share} color={team.color} grow={mounted} delay={180} />
              </span>
              <span className="inline-flex items-center gap-2" title="Daily spend, last 14 days; change is this week vs last week">
                <Sparkline values={summary?.recentDaily ?? []} partialLast={summary?.recentPartial} color={team.color} />
                <DeltaChip value={summary?.weekChange} className="text-sm" />
              </span>
            </div>
          </div>
          <BulletBar
            className="mt-4"
            size="md"
            allocation={rangeTop}
            spent={summary?.spent ?? 0}
            projected={summary?.projected}
            color={team.color}
            grow={mounted}
            delay={120}
          />
          <div className="mt-2 flex flex-wrap gap-x-3 text-xs text-muted-foreground">
            {period?.label && <span>{period.label}</span>}
            {summary?.low != null && summary?.high != null && (
              <span>Range <span className="num">{formatAmount(summary.low, unit, { compact: true })} – {formatAmount(summary.high, unit, { compact: true })}</span></span>
            )}
            {summary?.projected == null && forecast?.unavailableReason && <span>{forecast.unavailableReason}</span>}
          </div>
        </section>
      </header>

      <ForecastPanel scopeType="person" scopeId={personId} embedded />
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
      <div className="space-y-4 rounded-xl border border-border bg-card p-5">
        <Skeleton className="h-6 w-80 max-w-full" />
        <Skeleton className="h-2.5 w-full" />
        <Skeleton className="h-3 w-32" />
      </div>
      <Skeleton className="h-64 w-full rounded-xl" />
    </div>
  );
}
