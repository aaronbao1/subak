"use client";
import Link from "next/link";
import { ArrowLeft, ChevronRight, Info, MessageSquare } from "lucide-react";
import type { Budget, Forecast, Provenance, SpendingRecord, Team } from "@/lib/contracts";
import { useAppStore } from "@/lib/store";
import { formatAmount } from "@/lib/format";
import { PageTitle } from "@/components/shared/stat-tile";
import { riseDelay, useMounted } from "@/components/shared/motion";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { fmtDate, fmtDateTime, PROVENANCE_LABEL, provenanceNote, spentToDate, StatusChip, Tag, teamStatus, teamUnit } from "./labels";
import { CountUpAmount } from "./count-up";
import { BulletBar, BulletLegend, dailySeries, Sparkline } from "./viz";
import { cn } from "@/lib/utils";

interface Props {
  team: Team;
  budget?: Budget;
  forecast?: Forecast;
  records: SpendingRecord[];
}

/** Team identity, one bullet bar (allocation, spend, projection) with a spend sparkline, and a quiet disclosure with the forecast's metadata, assumptions and limitations. */
export function TeamHeader({ team, budget, forecast, records }: Props) {
  const askAssistant = useAppStore((s) => s.askAssistant);
  // Entrance (ms): link and title 0 · bullet card 60 (numbers count up 60/120/180) · alert and disclosure 240.
  const mounted = useMounted();
  const rise = mounted ? "animate-rise" : "opacity-0";
  const spent = spentToDate(records);
  const unit = teamUnit(budget, records);
  const lastDate = records.reduce<string | undefined>((m, r) => (!m || r.date > m ? r.date : m), undefined);
  const provenances = [...new Set<Provenance>(records.map((r) => r.provenance))];
  const provenanceTitle = provenances.length ? `Provenance: ${provenances.map((p) => PROVENANCE_LABEL[p]).join(", ")}` : undefined;
  const series = dailySeries(records);
  const status = teamStatus(budget, forecast, spent);

  const available = forecast?.status === "available" && forecast.projected != null;
  const isRemaining = forecast?.basis === "remaining";
  // full_period totals already include spend; only a remaining basis is added to spent.
  const projectedTotal = available ? (isRemaining ? spent + forecast.projected! : forecast.projected!) : undefined;
  const low = available && forecast.low != null ? (isRemaining ? spent + forecast.low : forecast.low) : undefined;
  const high = available && forecast.high != null ? (isRemaining ? spent + forecast.high : forecast.high) : undefined;
  const fUnit = forecast?.unit ?? unit;
  const isScenario = forecast?.kind === "scenario";
  const periodLabel = (p: { start: string; end: string; label?: string }) => p.label ?? `${fmtDate(p.start)} – ${fmtDate(p.end, { year: true })}`;

  return (
    <div className="space-y-6">
      <Link href="/teams" className={cn("inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors duration-300 hover:text-foreground", rise)}>
        <ArrowLeft className="size-4" aria-hidden strokeWidth={1.5} /> All teams
      </Link>

      <PageTitle
        className={rise}
        title={
          <span className="flex flex-wrap items-center gap-x-3 gap-y-2">
            <span className="flex items-center gap-2.5">
              <span aria-hidden className="size-2.5 shrink-0 rounded-full" style={{ background: team.color }} />
              {team.name}
            </span>
            <StatusChip status={status} />
          </span>
        }
        description={team.lead ? <span title={team.description}>Lead <span className="text-foreground/80">{team.lead}</span></span> : undefined}
        actions={
          <Button variant="outline" onClick={() => askAssistant(`Tell me about ${team.name}'s spending and projection`)}>
            <MessageSquare className="text-muted-foreground" strokeWidth={1.5} /> Ask the assistant
          </Button>
        }
      />

      <section className={cn("rounded-xl border border-border bg-card p-5", rise)} style={riseDelay(1)} aria-label="Spend against allocation">
        <div className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3">
          <BulletLegend
            size="lg"
            items={[
              { label: "Spent", mark: "fill", color: team.color, value: <CountUpAmount value={spent} unit={unit} delay={60} />, title: provenanceTitle, note: provenanceNote(provenances) },
              {
                label: isScenario ? "Scenario" : "Projected",
                mark: "tick",
                value: projectedTotal != null ? <CountUpAmount value={projectedTotal} unit={fUnit} delay={120} /> : "None",
                muted: projectedTotal == null,
                title: projectedTotal != null
                  ? `Full period, includes spend to date${low != null && high != null ? ` · range ${formatAmount(low, fUnit)} – ${formatAmount(high, fUnit)}` : ""}${isScenario ? " · conditional on its assumptions" : ""}`
                  : undefined,
              },
              { label: "Allocation", mark: "track", value: budget ? <CountUpAmount value={budget.allocated} unit={budget.unit} delay={180} /> : "None", muted: !budget },
            ]}
          />
          {series.values.length >= 2 && (
            <div className="flex items-center gap-2 text-xs text-muted-foreground" title={`Daily spend, ${fmtDate(series.from)} – ${fmtDate(series.to)}`}>
              <Sparkline values={series.values} partialLast={series.partialLast} color={team.color} className="w-24" />
              <span className="num">{series.values.length}d</span>
            </div>
          )}
        </div>
        <BulletBar
          className="mt-4"
          size="md"
          allocation={budget?.allocated}
          spent={spent}
          projected={projectedTotal}
          color={team.color}
          grow={mounted}
          delay={120}
        />
        <div className="mt-2 flex flex-wrap gap-x-3 text-xs text-muted-foreground">
          {budget ? <span>{periodLabel(budget.period)}</span> : <span>No allocation recorded</span>}
          {lastDate ? <span>Through <span className="num">{fmtDate(lastDate)}</span></span> : <span>No spending recorded</span>}
        </div>
      </section>

      {forecast?.status === "unavailable" && (
        <Alert className={cn("border-border bg-card", rise)} style={riseDelay(4)}>
          <Info className="size-4 text-muted-foreground" strokeWidth={1.5} />
          <AlertTitle>Projection unavailable</AlertTitle>
          <AlertDescription>
            {forecast.unavailableReason ?? "No projection returned for this team."}
          </AlertDescription>
        </Alert>
      )}

      {forecast && (
        <details className={cn("group rounded-xl border border-border bg-card", rise)} style={riseDelay(4)}>
          <summary className="flex cursor-pointer list-none items-center gap-2 px-4 py-3 text-sm transition-colors duration-300 [&::-webkit-details-marker]:hidden">
            <ChevronRight className="size-4 shrink-0 text-muted-foreground transition-transform group-open:rotate-90" aria-hidden strokeWidth={1.5} />
            <span className="font-medium">About this {isScenario ? "scenario" : "projection"}</span>
            <span className="hidden min-w-0 flex-wrap items-center gap-x-2 text-xs text-muted-foreground sm:flex">
              <span aria-hidden>·</span>
              <span className="truncate">{periodLabel(forecast.period)}</span>
              {isScenario && <Tag title="Conditional on the stated assumptions; not an unconditional forecast">Scenario</Tag>}
            </span>
          </summary>
          <div className="space-y-5 border-t border-border px-4 py-4 text-sm">
            <dl className="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-[auto_1fr]">
              <dt className="text-muted-foreground">Kind</dt>
              <dd className="flex flex-wrap items-center gap-2">
                {isScenario ? "Scenario, conditional on the assumptions below" : "Forecast"}
              </dd>
              <dt className="text-muted-foreground">Period</dt>
              <dd>{periodLabel(forecast.period)}</dd>
              <dt className="text-muted-foreground">Generated</dt>
              <dd className="num">{fmtDateTime(forecast.generatedAt)}</dd>
              <dt className="text-muted-foreground">Basis</dt>
              <dd>{isRemaining ? "Remaining spend to period end; added to spend to date above" : "Full-period total; already includes spend to date"}</dd>
            </dl>
            <div className="grid gap-5 sm:grid-cols-2">
              <ListBlock title="Assumptions" items={forecast.assumptions} empty="No assumptions stated." />
              <ListBlock title="Limitations" items={forecast.limitations} empty="No limitations stated." />
            </div>
          </div>
        </details>
      )}
    </div>
  );
}

function ListBlock({ title, items, empty }: { title: string; items: string[]; empty: string }) {
  return (
    <div>
      <div className="eyebrow">
        {title} <span className="num">({items.length})</span>
      </div>
      {items.length === 0 ? (
        <p className="mt-2 text-sm text-muted-foreground">{empty}</p>
      ) : (
        <ul className="mt-2 space-y-1.5 text-sm text-foreground/80">
          {items.map((it, i) => (
            <li key={i} className="flex gap-2.5">
              <span aria-hidden className="mt-[8px] size-1 shrink-0 rounded-full bg-muted-foreground" />
              <span>{it}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
