"use client";
import Link from "next/link";
import { ArrowLeft, Info, MessageSquare } from "lucide-react";
import type { Budget, Forecast, SpendingRecord, Team } from "@/lib/contracts";
import { useAppStore } from "@/lib/store";
import { formatAmount } from "@/lib/format";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { fmtDate, fmtDateTime, spentToDate, StatusChip, teamStatus, teamUnit } from "./labels";

interface Props {
  team: Team;
  budget?: Budget;
  forecast?: Forecast;
  records: SpendingRecord[];
}

/** Team identity, three stat tiles, forecast metadata, assumptions and limitations. */
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

  return (
    <div className="space-y-4">
      <Link href="/teams" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="size-3.5" /> Back to overview
      </Link>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span aria-hidden className="size-3 shrink-0 rounded-full" style={{ background: team.color }} />
            <h1 className="text-xl font-semibold tracking-tight">{team.name}</h1>
            <StatusChip status={status} />
          </div>
          <div className="mt-1 text-sm text-muted-foreground">
            {team.lead ? <>Lead: <span className="text-foreground">{team.lead}</span></> : "No lead listed"}
            {team.description && <> · {team.description}</>}
          </div>
        </div>
        <Button
          variant="outline"
          size="sm"
          className="shrink-0 self-start"
          onClick={() => askAssistant(`Tell me about ${team.name}'s spending and projection`)}
        >
          <MessageSquare /> Ask the assistant about this team
        </Button>
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        <Tile
          label="Allocation"
          value={budget ? formatAmount(budget.allocated, budget.unit) : "—"}
          caption={budget?.period.label ?? (budget ? `${fmtDate(budget.period.start)} – ${fmtDate(budget.period.end, { year: true })}` : "No allocation recorded")}
        />
        <Tile
          label="Spent to date"
          value={formatAmount(spent, unit)}
          caption={lastDate ? `Through ${fmtDate(lastDate, { year: true })}` : "No spending recorded"}
        />
        <Tile
          label="Projection"
          value={projectedTotal != null ? formatAmount(projectedTotal, fUnit) : "No projection"}
          muted={projectedTotal == null}
          caption={
            projectedTotal != null
              ? low != null && high != null
                ? `${formatAmount(low, fUnit)} – ${formatAmount(high, fUnit)} · full-period total, includes spend to date`
                : "Full-period total, includes spend to date"
              : forecast?.status === "unavailable" ? "See reason below" : "Not supplied"
          }
        />
      </div>

      {forecast?.status === "unavailable" && (
        <Alert>
          <Info />
          <AlertTitle>Projection unavailable</AlertTitle>
          <AlertDescription>
            {forecast.unavailableReason ?? "The forecasting service did not return a projection for this team."}{" "}
            Spending and allocation remain current.
          </AlertDescription>
        </Alert>
      )}

      {forecast && (
        <Card size="sm">
          <CardContent className="space-y-3">
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
              <span className="font-medium text-foreground">{forecast.kind === "scenario" ? "Scenario" : "Projection"}</span>
              <span>{forecast.period.label ?? `${fmtDate(forecast.period.start)} – ${fmtDate(forecast.period.end, { year: true })}`}</span>
              <span>Generated {fmtDateTime(forecast.generatedAt)}</span>
              {forecast.origin === "placeholder" && (
                <Badge variant="outline" className="font-normal text-muted-foreground" title="Shared placeholder number, not the output of the forecasting service">
                  placeholder projection
                </Badge>
              )}
              {forecast.kind === "scenario" && (
                <Badge variant="secondary" className="font-normal" title="Conditional on the stated assumptions; not an unconditional forecast">
                  scenario
                </Badge>
              )}
              {isRemaining && (
                <Badge variant="outline" className="font-normal text-muted-foreground">remaining basis, added to spend</Badge>
              )}
            </div>
            <div className="grid gap-2 sm:grid-cols-2">
              <Expandable title="Assumptions" items={forecast.assumptions} empty="No assumptions stated." />
              <Expandable title="Limitations" items={forecast.limitations} empty="No limitations stated." />
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function Tile({ label, value, caption, muted }: { label: string; value: string; caption?: string; muted?: boolean }) {
  return (
    <Card size="sm">
      <CardContent>
        <div className="text-xs uppercase tracking-wide text-muted-foreground">{label}</div>
        <div className={cn("mt-1 text-2xl font-semibold tracking-tight", muted && "text-muted-foreground text-lg font-medium")}>{value}</div>
        {caption && <div className="mt-1 text-xs text-muted-foreground">{caption}</div>}
      </CardContent>
    </Card>
  );
}

function Expandable({ title, items, empty }: { title: string; items: string[]; empty: string }) {
  return (
    <details className="group rounded-lg border bg-muted/30 px-3 py-2 open:bg-muted/50">
      <summary className="flex cursor-pointer list-none items-center justify-between text-sm font-medium [&::-webkit-details-marker]:hidden">
        <span>{title} <span className="text-xs font-normal text-muted-foreground">({items.length})</span></span>
        <span className="text-xs text-muted-foreground group-open:hidden">Show</span>
        <span className="hidden text-xs text-muted-foreground group-open:inline">Hide</span>
      </summary>
      {items.length === 0 ? (
        <p className="mt-2 text-sm text-muted-foreground">{empty}</p>
      ) : (
        <ul className="mt-2 list-disc space-y-1 pl-4 text-sm text-muted-foreground">
          {items.map((it, i) => <li key={i}>{it}</li>)}
        </ul>
      )}
    </details>
  );
}
