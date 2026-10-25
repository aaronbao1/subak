"use client";
import { displayCopy, displayReference } from "@/lib/display-copy";
import Link from "next/link";
import { ArrowUpRight, ChevronRight } from "lucide-react";
import type { WeeklyHistoryResponse, WeeklyHistoryWeek } from "@/lib/contracts/weekly-history";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";

interface Props {
  week?: WeeklyHistoryWeek;
  history: WeeklyHistoryResponse;
  onClose: () => void;
}

function numeric(value: string | null | undefined): number | null {
  if (value == null || value.trim() === "") return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function amount(value: string | null | undefined, unit: string, absolute = false): string {
  const number = numeric(value);
  if (number === null) return "—";
  const shown = absolute ? Math.abs(number) : number;
  return unit.toLowerCase() === "usd"
    ? new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(shown)
    : `${new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 }).format(shown)} ${unit.toLowerCase()}`;
}

function date(value: string): string {
  const parsed = new Date(value.length === 10 ? `${value}T00:00:00Z` : value);
  return Number.isNaN(parsed.getTime()) ? value : new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", timeZone: "UTC" }).format(parsed);
}

function dateRange(start: string, endExclusive: string): string {
  const end = new Date(`${endExclusive}T00:00:00Z`);
  if (Number.isNaN(end.getTime())) return date(start);
  end.setUTCDate(end.getUTCDate() - 1);
  return `${date(start)} – ${date(end.toISOString().slice(0, 10))}`;
}

function actualNote(week: WeeklyHistoryWeek): string {
  if (week.state === "future" || week.actual.status === "future") return "This week has not started.";
  if (week.state === "current") return "Week in progress. The final difference will be available after the week closes and actuals are complete.";
  if (week.actual.status === "mature") return week.actual.corrected ? "Recorded actuals include a correction." : "Recorded actuals for the full week.";
  if (week.actual.status === "partial") return "Some actuals are still missing. A final comparison is not ready.";
  if (week.actual.status === "disputed") return "Actuals are under review. A final comparison is not ready.";
  if (week.actual.status === "pending") return "Actuals are awaiting review.";
  return "Actual spending is not available for this week.";
}

/** Reviews one immutable weekly target without replacing it with the latest forecast. */
export function WeekReview({ week, history, onClose }: Props) {
  const prior = week?.priorForecast;
  const outlook = week?.outlook;
  const preferFullOutlook = (week?.state === "future" || week?.state === "current") && outlook != null && !outlook.partial
    && outlook.start === week.start && outlook.endExclusive === week.endExclusive
    && numeric(outlook.amount) !== null;
  const mainForecast = preferFullOutlook ? outlook : prior;
  const actual = week ? numeric(week.actual.amount) : null;
  const delta = week ? numeric(week.variance.amount) : null;
  const comparable = !!week && week.state === "closed" && week.actual.status === "mature"
    && actual !== null && prior != null && numeric(prior.amount) !== null
    && prior.datasetId === week.actual.datasetId
    && prior.start === week.start && prior.endExclusive === week.endExclusive
    && Date.parse(prior.issuedAt) <= Date.parse(`${week.start}T00:00:00Z`)
    && week.variance.status === "available" && delta !== null;
  const scopeName = "name" in history.scope && typeof history.scope.name === "string" ? history.scope.name
    : history.scope.type === "company" ? "All teams" : history.scope.type === "shared" ? "Shared usage" : history.scope.type === "team" ? "Team" : "Person";
  const usageParams = week ? new URLSearchParams({
    scope_type: history.scope.type,
    ...(history.scope.id && history.scope.type !== "company" && history.scope.type !== "shared" ? { scope_id: history.scope.id } : {}),
    start_date: week.start,
    end_date_exclusive: week.endExclusive,
    metric: history.quantity.toLowerCase() === "tokens" ? "tokens" : "spend",
  }) : undefined;
  const missingComparison = week?.state === "closed" && !comparable;
  const showOutlook = !!outlook && !preferFullOutlook && (outlook.partial || !prior || outlook.runId !== prior.runId || outlook.amount !== prior.amount);

  return (
    <Sheet open={!!week} onOpenChange={open => { if (!open) onClose(); }}>
      <SheetContent side="right" className="w-full gap-0 overflow-y-auto sm:max-w-[480px]">
        <SheetHeader className="gap-1.5 border-b border-border px-5 py-5 pr-12">
          <SheetTitle className="text-xl">{week ? dateRange(week.start, week.endExclusive) : "Week review"}</SheetTitle>
          <SheetDescription className="text-xs">{displayCopy(scopeName, "Selected scope")}{week?.state === "current" ? " · Current week" : week?.state === "future" ? " · Upcoming week" : " · Week review"}</SheetDescription>
        </SheetHeader>
        {week && <div className="space-y-5 px-5 py-5">
          <dl className="grid grid-cols-2 gap-5">
            <div className="min-w-0">
              <dt className="text-xs text-muted-foreground">{week.state === "current" || week.actual.status === "partial" ? "Spend so far" : "Recorded spend"}</dt>
              <dd className="mt-2 text-2xl font-medium tabular-nums">{week.state === "future" || week.actual.status === "future" ? "Not started" : amount(week.actual.amount, history.unit)}</dd>
              {week.actual.corrected && <dd className="mt-2 text-xs text-muted-foreground">Corrected actuals</dd>}
            </div>
            <div className="min-w-0">
              <dt className="text-xs text-muted-foreground">{week.state === "future" ? "Forecast" : preferFullOutlook ? "Latest forecast" : "Original forecast"}</dt>
              <dd className="mt-2 text-2xl font-medium tabular-nums">{amount(mainForecast?.amount, history.unit)}</dd>
              <dd className="mt-2 text-xs text-muted-foreground">{mainForecast ? `Issued ${date(mainForecast.issuedAt)}` : week.state === "future" ? "No full-week forecast available" : "No saved forecast before this week"}</dd>
            </div>
          </dl>

          {comparable && <div className={`rounded-lg border px-4 py-3 ${delta! > 0 ? "border-warning/30 bg-warning/5" : "border-border bg-muted/30"}`}>
            <p className="text-base font-medium tabular-nums">{delta === 0 ? "Matched the original forecast" : `${amount(week.variance.amount, history.unit, true)} ${delta! > 0 ? "over" : "under"} forecast`}</p>
            <p className="mt-1 text-xs text-muted-foreground">Recorded spend compared with the original full-week forecast.</p>
          </div>}
          <p className="text-xs leading-relaxed text-muted-foreground">{actualNote(week)}</p>
          {missingComparison && <p className="text-xs leading-relaxed text-muted-foreground">{displayCopy(week.variance.reason, "A like-for-like comparison is not available for this week.")}</p>}

          {showOutlook && <section className="rounded-lg border border-border p-4" aria-label={outlook.partial ? "Forecast remaining" : "Latest outlook"}>
            <div className="flex flex-wrap items-start justify-between gap-2"><h3 className="text-sm font-medium">{outlook.partial ? "Forecast remaining" : "Latest outlook"}</h3><p className="font-medium tabular-nums">{amount(outlook.amount, history.unit)}</p></div>
            <p className="mt-2 text-xs text-muted-foreground">{dateRange(outlook.start, outlook.endExclusive)} · Issued {date(outlook.issuedAt)}</p>
            {outlook.partial && <p className="mt-1 text-xs text-muted-foreground">Covers the remaining dates only.</p>}
          </section>}

          <Link href={`/usage?${usageParams}`} onClick={onClose} className="inline-flex min-h-10 items-center gap-2 rounded-lg border border-border px-4 py-2 text-sm font-medium transition-colors hover:bg-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring">View daily usage <ArrowUpRight className="size-4" aria-hidden /></Link>

          <details className="group border-t border-border pt-4 text-xs">
            <summary className="flex cursor-pointer list-none items-center justify-between gap-2 font-medium outline-none focus-visible:ring-2 focus-visible:ring-ring [&::-webkit-details-marker]:hidden">Forecast and data details <ChevronRight aria-hidden className="size-4 text-muted-foreground transition-transform group-open:rotate-90" /></summary>
            <p className="mt-3 text-muted-foreground">Displayed amounts are rounded to cents. The recorded difference uses the exact values below and may differ by a cent from subtracting rounded amounts.</p>
            <dl className="mt-4 space-y-4">
              <Detail label="Actual spend (exact)" value={week.actual.amount === null ? "Unavailable" : `${history.unit.toUpperCase()} ${week.actual.amount}`} />
              {comparable && <Detail label="Over / under original forecast (exact)" value={`${history.unit.toUpperCase()} ${week.variance.amount}`} />}
              {prior && <>
                <Detail label="Original forecast amount (exact)" value={`${history.unit.toUpperCase()} ${prior.amount}`} />
                <Detail label="Original forecast issued" value={`${prior.issuedAt} (UTC)`} />
                <Detail label="Information available through" value={`${prior.informationCutoff} (UTC)`} />
                <Detail label="Original forecast period" value={dateRange(prior.start, prior.endExclusive)} />
                <Detail label="Saved forecast" value={displayReference(prior.runId, "Original forecast")} />
                <Detail label="Saved target" value={displayReference(prior.targetId, "Weekly target")} />
              </>}
              {outlook && (showOutlook || preferFullOutlook) && <>
                <Detail label="Latest outlook issued" value={`${outlook.issuedAt} (UTC)`} />
                <Detail label="Latest outlook run" value={displayReference(outlook.runId, "Latest forecast")} />
              </>}
              <Detail label="Actuals source" value={week.actual.source === "observed_outcome" ? "Recorded weekly outcome" : week.actual.source === "repository_ledger" ? "Recorded ledger entries" : "No actuals source available"} />
              <Detail label="Actuals revision" value={displayReference(week.actual.revision ?? history.actualsRevision, "Loaded revision")} />
              <Detail label="Data as of" value={`${history.asOf} (UTC)`} />
              {week.actual.sourceRefs.length > 0 && <Detail label="Source records" value={week.actual.sourceRefs.map((reference, index) => displayReference(reference, `Source record ${index + 1}`)).join(", ")} />}
            </dl>
          </details>
        </div>}
      </SheetContent>
    </Sheet>
  );
}

function Detail({ label, value }: { label: string; value: string }) {
  return <div><dt className="text-muted-foreground">{label}</dt><dd className="mt-1 break-words leading-relaxed">{displayCopy(value)}</dd></div>;
}
