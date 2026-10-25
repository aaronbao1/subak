"use client";
import type { ReactNode } from "react";
import Link from "next/link";
import { ArrowLeft, ChevronRight, Info, MessageSquare } from "lucide-react";
import type { Budget, Forecast, SpendingRecord, Team } from "@/lib/contracts";
import { useAppStore } from "@/lib/store";
import { formatAmount } from "@/lib/format";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { fmtDate, fmtDateTime, PlaceholderBadge, spentToDate, StatusChip, Tag, teamStatus, teamUnit } from "./labels";

interface Props {
  team: Team;
  budget?: Budget;
  forecast?: Forecast;
  records: SpendingRecord[];
}

/** Team identity, three stat tiles, and a quiet disclosure with the forecast's metadata, assumptions and limitations. */
export function TeamHeader({ team, budget, forecast, records }: Props) {
  const askAssistant = useAppStore((s) => s.askAssistant);
  const spent = spentToDate(records);
  const unit = teamUnit(team, budget, records);
  const lastDate = records.reduce<string | undefined>((m, r) => (!m || r.date > m ? r.date : m), undefined);
  const status = teamStatus(budget, forecast, spent);

  const available = forecast?.status === "available" && forecast.projected != null;
  const isRemaining = forecast?.basis === "remaining";
  // full_period totals already include spend; only a remaining basis is added to spent.
  const projectedTotal = available ? (isRemaining ? spent + forecast.projected! : forecast.projected!) : undefined;
  const low = available && forecast.low != null ? (isRemaining ? spent + forecast.low : forecast.low) : undefined;
  const high = available && forecast.high != null ? (isRemaining ? spent + forecast.high : forecast.high) : undefined;
  const fUnit = forecast?.unit ?? unit;
  const isScenario = forecast?.kind === "scenario";
  const isPlaceholder = forecast?.origin === "placeholder";
  const periodLabel = (p: { start: string; end: string; label?: string }) => p.label ?? `${fmtDate(p.start)} – ${fmtDate(p.end, { year: true })}`;

  return (
    <div className="space-y-6">
      <Link href="/teams" className="inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors duration-300 hover:text-foreground">
        <ArrowLeft className="size-4" aria-hidden /> All teams
      </Link>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
            <h1 className="flex items-center gap-2.5 text-[22px] leading-[1.15]">
              <span aria-hidden className="size-2.5 shrink-0 rounded-full" style={{ background: team.color }} />
              {team.name}
            </h1>
            <StatusChip status={status} />
          </div>
          <div className="mt-1.5 text-sm text-muted-foreground">
            {team.lead ? <>Lead <span className="text-foreground/80">{team.lead}</span></> : "No lead listed"}
            {team.description && <> · {team.description}</>}
          </div>
        </div>
        <Button
          variant="outline"
          size="lg"
          className="shrink-0 self-start border-border bg-popover hover:border-border-strong"
          onClick={() => askAssistant(`Tell me about ${team.name}'s spending and projection`)}
        >
          <MessageSquare className="text-muted-foreground" /> Ask the assistant
        </Button>
      </div>

      <dl className="grid gap-4 sm:grid-cols-3">
        <Tile
          label="Allocation"
          value={budget ? formatAmount(budget.allocated, budget.unit) : "—"}
          muted={!budget}
          caption={budget ? periodLabel(budget.period) : "No allocation recorded"}
        />
        <Tile
          label="Spent to date"
          value={formatAmount(spent, unit)}
          caption={lastDate ? `Through ${fmtDate(lastDate, { year: true })}` : "No spending recorded"}
        />
        <Tile
          label={isScenario ? "Scenario" : "Projection"}
          value={projectedTotal != null ? formatAmount(projectedTotal, fUnit) : "No projection"}
          muted={projectedTotal == null}
          tag={isPlaceholder ? <PlaceholderBadge /> : undefined}
          caption={
            projectedTotal != null
              ? low != null && high != null
                ? <><span className="num">{formatAmount(low, fUnit)} – {formatAmount(high, fUnit)}</span> · full period, includes spend to date</>
                : "Full period, includes spend to date"
              : forecast?.status === "unavailable" ? "See reason below" : "Not supplied"
          }
        />
      </dl>

      {forecast?.status === "unavailable" && (
        <Alert className="border-border bg-card">
          <Info className="size-4 text-muted-foreground" />
          <AlertTitle>Projection unavailable</AlertTitle>
          <AlertDescription>
            {forecast.unavailableReason ?? "The forecasting service did not return a projection for this team."}{" "}
            Spending and allocation remain current.
          </AlertDescription>
        </Alert>
      )}

      {forecast && (
        <details className="group rounded-xl border border-border bg-card">
          <summary className="flex cursor-pointer list-none items-center gap-2 px-4 py-3 text-sm transition-colors duration-300 [&::-webkit-details-marker]:hidden">
            <ChevronRight className="size-4 shrink-0 text-muted-foreground transition-transform group-open:rotate-90" aria-hidden />
            <span className="font-medium">About this {isScenario ? "scenario" : "projection"}</span>
            <span className="hidden min-w-0 flex-wrap items-center gap-x-2 text-xs text-muted-foreground sm:flex">
              <span aria-hidden>·</span>
              <span className="truncate">{periodLabel(forecast.period)}</span>
              {isPlaceholder && <PlaceholderBadge />}
              {isScenario && <Tag title="Conditional on the stated assumptions; not an unconditional forecast">Scenario</Tag>}
              {isRemaining && <Tag>Remaining basis, added to spend</Tag>}
            </span>
          </summary>
          <div className="space-y-5 border-t border-border px-4 py-4 text-sm">
            <dl className="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-[auto_1fr]">
              <dt className="text-muted-foreground">Kind</dt>
              <dd className="flex flex-wrap items-center gap-2">
                {isScenario ? "Scenario, conditional on the assumptions below" : "Forecast"}
                {isPlaceholder && <PlaceholderBadge />}
              </dd>
              <dt className="text-muted-foreground">Period</dt>
              <dd>{periodLabel(forecast.period)}</dd>
              <dt className="text-muted-foreground">Generated</dt>
              <dd className="num">{fmtDateTime(forecast.generatedAt)}</dd>
              <dt className="text-muted-foreground">Basis</dt>
              <dd>{isRemaining ? "Remaining spend to period end; added to spend to date above" : "Full-period total; already includes spend to date"}</dd>
              <dt className="text-muted-foreground">Origin</dt>
              <dd>{isPlaceholder ? "Shared placeholder number, not the output of the forecasting service" : "Forecasting service"}</dd>
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

/** Stat tile per spec: eyebrow above, mono 32px value, caption below. */
function Tile({ label, value, caption, muted, tag }: { label: string; value: string; caption?: ReactNode; muted?: boolean; tag?: ReactNode }) {
  return (
    <div className="min-w-0 rounded-xl border border-border bg-card p-4">
      <dt className="flex items-center gap-2">
        <span className="eyebrow">{label}</span>
        {tag}
      </dt>
      <dd className={cn("num mt-2 truncate text-[32px] leading-none tracking-[-0.01em]", muted && "text-muted-foreground")}>{value}</dd>
      {caption && <dd className="mt-2 text-xs leading-relaxed text-muted-foreground">{caption}</dd>}
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
