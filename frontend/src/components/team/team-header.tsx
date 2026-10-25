"use client";
import Link from "next/link";
import { ArrowLeft, ChevronRight, Info, MessageSquare } from "lucide-react";
import type { Budget, Forecast, Provenance, SpendingRecord, Team } from "@/lib/contracts";
import { useAppStore } from "@/lib/store";
import { formatAmount } from "@/lib/format";
import { PageTitle, StatTile } from "@/components/shared/stat-tile";
import { riseDelay, useMounted } from "@/components/shared/motion";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { fmtDate, fmtDateTime, ProvenanceBadge, spentToDate, StatusChip, Tag, teamStatus, teamUnit } from "./labels";
import { CountUpAmount } from "./count-up";
import { cn } from "@/lib/utils";

interface Props {
  team: Team;
  budget?: Budget;
  forecast?: Forecast;
  records: SpendingRecord[];
}

/** Team identity, three stat tiles, and a quiet disclosure with the forecast's metadata, assumptions and limitations. */
export function TeamHeader({ team, budget, forecast, records }: Props) {
  const askAssistant = useAppStore((s) => s.askAssistant);
  // Entrance (ms): link and title 0 · tiles 60/120/180 (numbers count up from each tile's delay) · alert and disclosure 240.
  const mounted = useMounted();
  const rise = mounted ? "animate-rise" : "opacity-0";
  const spent = spentToDate(records);
  const unit = teamUnit(budget, records);
  const lastDate = records.reduce<string | undefined>((m, r) => (!m || r.date > m ? r.date : m), undefined);
  const provenances = [...new Set<Provenance>(records.map((r) => r.provenance))];
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
        description={
          <>
            {team.lead ? <>Lead <span className="text-foreground/80">{team.lead}</span></> : "No lead listed"}
            {team.description && <> · {team.description}</>}
          </>
        }
        actions={
          <Button variant="outline" onClick={() => askAssistant(`Tell me about ${team.name}'s spending and projection`)}>
            <MessageSquare className="text-muted-foreground" strokeWidth={1.5} /> Ask the assistant
          </Button>
        }
      />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className={rise} style={riseDelay(1)}>
          <StatTile
            className="h-full"
            size="primary"
            card
            label="Allocation"
            value={budget ? <CountUpAmount value={budget.allocated} unit={budget.unit} delay={60} /> : "—"}
            muted={!budget}
            caption={budget ? periodLabel(budget.period) : "No allocation recorded"}
          />
        </div>
        <div className={rise} style={riseDelay(2)}>
          <StatTile
            className="h-full"
            size="primary"
            card
            label="Spent to date"
            value={<CountUpAmount value={spent} unit={unit} delay={120} />}
            caption={
              lastDate ? (
                <span className="inline-flex flex-wrap items-center gap-1.5">
                  <span>Through <span className="num">{fmtDate(lastDate, { year: true })}</span></span>
                  {provenances.map((p) => <ProvenanceBadge key={p} provenance={p} />)}
                </span>
              ) : "No spending recorded"
            }
          />
        </div>
        <div className={rise} style={riseDelay(3)}>
          <StatTile
            className="h-full"
            size="primary"
            card
            label={isScenario ? "Scenario" : "Projection"}
            value={projectedTotal != null ? <CountUpAmount value={projectedTotal} unit={fUnit} delay={180} /> : "No projection"}
            muted={projectedTotal == null}
            caption={
              projectedTotal != null
                ? low != null && high != null
                  ? <><span className="num">{formatAmount(low, fUnit)} – {formatAmount(high, fUnit)}</span> · full period, includes spend to date</>
                  : "Full period, includes spend to date"
                : forecast?.status === "unavailable" ? "See reason below" : "Not supplied"
            }
          />
        </div>
      </div>

      {forecast?.status === "unavailable" && (
        <Alert className={cn("border-border bg-card", rise)} style={riseDelay(4)}>
          <Info className="size-4 text-muted-foreground" strokeWidth={1.5} />
          <AlertTitle>Projection unavailable</AlertTitle>
          <AlertDescription>
            {forecast.unavailableReason ?? "The forecasting service did not return a projection for this team."}{" "}
            Spending and allocation remain current.
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
              {isRemaining && <Tag>Remaining basis, added to spend</Tag>}
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
