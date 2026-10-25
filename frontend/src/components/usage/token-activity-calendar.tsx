"use client";

import { useId, useMemo, useRef, useState, type KeyboardEvent } from "react";
import type { DailyUsageBucket, UsageCoverage, UsageMetric } from "@/lib/contracts/usage";
import { formatExactUsd, formatUsageValue, usageIntensity, usageValue } from "@/lib/usage-derive";
import { cn } from "@/lib/utils";

interface Props {
  buckets: DailyUsageBucket[];
  metric: UsageMetric;
  selectedDate: string | null;
  onSelect: (date: string | null) => void;
}

const DAY_MS = 86_400_000;
const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const INTENSITY_COLORS = [
  "var(--muted)",
  "color-mix(in oklch, var(--chart-1) 20%, var(--card))",
  "color-mix(in oklch, var(--chart-1) 38%, var(--card))",
  "color-mix(in oklch, var(--chart-1) 56%, var(--card))",
  "color-mix(in oklch, var(--chart-1) 78%, var(--card))",
  "var(--chart-1)",
];
const COVERAGE_MARK: Record<UsageCoverage, string> = {
  complete: "", partial: "◐", missing: "×", unknown: "?", future: "–",
};

function calendarDate(date: string) {
  return new Date(`${date}T00:00:00Z`);
}

function valueLabel(bucket: DailyUsageBucket, metric: UsageMetric) {
  if (bucket.coverage === "future" || bucket.coverage === "missing") return "Not available";
  return metric === "spend" ? formatExactUsd(bucket.recordedSpend) : formatUsageValue(bucket.tokens.total, metric);
}

/** Week columns keep longer ranges compact; exactly one day is in the tab order. */
export function TokenActivityCalendar({ buckets, metric, selectedDate, onSelect }: Props) {
  const id = useId();
  const buttonRefs = useRef(new Map<string, HTMLButtonElement>());
  const [focusedDate, setFocusedDate] = useState<string | null>(null);
  const ordered = useMemo(() => [...buckets].sort((a, b) => a.date.localeCompare(b.date)), [buckets]);
  const byDate = useMemo(() => new Map(ordered.map((bucket) => [bucket.date, bucket])), [ordered]);
  const first = ordered[0]?.date;
  const last = ordered[ordered.length - 1]?.date;
  const activeDate = focusedDate && byDate.has(focusedDate) ? focusedDate : selectedDate && byDate.has(selectedDate) ? selectedDate : first;
  const weeks = useMemo(() => {
    if (!first || !last) return [];
    const start = calendarDate(first);
    const mondayOffset = (start.getUTCDay() + 6) % 7;
    const beginning = start.getTime() - mondayOffset * DAY_MS;
    const count = Math.ceil(((calendarDate(last).getTime() - beginning) / DAY_MS + 1) / 7);
    return Array.from({ length: count }, (_, week) => Array.from({ length: 7 }, (_, day) => new Date(beginning + (week * 7 + day) * DAY_MS).toISOString().slice(0, 10)));
  }, [first, last]);

  function handleKeyDown(event: KeyboardEvent<HTMLButtonElement>, date: string) {
    const delta = { ArrowUp: -1, ArrowDown: 1, ArrowLeft: -7, ArrowRight: 7 }[event.key];
    let target: string | undefined;
    if (event.key === "Home") target = first;
    else if (event.key === "End") target = last;
    else if (delta !== undefined) target = new Date(calendarDate(date).getTime() + delta * DAY_MS).toISOString().slice(0, 10);
    else if (event.key === "Escape") {
      onSelect(null);
      return;
    } else return;
    event.preventDefault();
    if (target && byDate.has(target)) {
      setFocusedDate(target);
      buttonRefs.current.get(target)?.focus();
    }
  }

  const thresholds = metric === "spend" ? ["0", "< $100", "$100+", "$1K+", "$10K+", "$50K+"] : ["0", "< 100K", "100K+", "1M+", "10M+", "100M+"];

  return (
    <section className="min-w-0 rounded-xl border border-border bg-card" aria-labelledby={`${id}-heading`}>
      <div className="flex flex-wrap items-start justify-between gap-3 px-5 pt-5">
        <div>
          <h2 id={`${id}-heading`} className="text-base font-medium">Daily activity</h2>
          <p className="mt-1 text-xs text-muted-foreground">{metric === "spend" ? "Recorded spend" : "Observed tokens"} · UTC days · select a day to inspect</p>
        </div>
        {selectedDate && <button type="button" onClick={() => onSelect(null)} className="rounded-md px-2.5 py-1.5 text-xs text-muted-foreground hover:bg-muted hover:text-foreground">Show full range</button>}
      </div>

      {weeks.length === 0 ? <p className="px-5 py-8 text-sm text-muted-foreground">No daily usage is available in this range.</p> : (
        <div className="px-5 pt-5">
          <div className="overflow-x-auto pb-2">
            <div className="w-max min-w-full">
              <div className="mb-2 grid gap-1 pl-10 text-[11px] text-muted-foreground" style={{ gridTemplateColumns: `repeat(${weeks.length}, minmax(28px, 1fr))` }} aria-hidden="true">
                {weeks.map((week, index) => {
                  const monthDate = week.find((date) => date.endsWith("-01")) ?? (index === 0 ? first : undefined);
                  return <span className="h-4 whitespace-nowrap" key={week[0]}>{monthDate ? calendarDate(monthDate).toLocaleDateString("en-US", { month: "short", timeZone: "UTC" }) : ""}</span>;
                })}
              </div>
              <div role="grid" aria-label={`Daily ${metric === "spend" ? "recorded spending" : "observed tokens"}, UTC`} aria-describedby={`${id}-keys`} aria-rowcount={7} aria-colcount={weeks.length}>
                {WEEKDAYS.map((weekday, day) => (
                  <div key={weekday} role="row" className="mb-1 flex items-center gap-1">
                    <span role="rowheader" className="w-9 shrink-0 text-[11px] text-muted-foreground">{weekday}</span>
                    {weeks.map((week) => {
                      const date = week[day];
                      const bucket = byDate.get(date);
                      if (!bucket) return <span role="gridcell" key={date} className="size-7 min-w-7 flex-1" />;
                      const value = usageValue(bucket, metric);
                      const intensity = usageIntensity(value, metric);
                      const selected = date === selectedDate;
                      const recordCount = bucket.coverage === "future" || bucket.coverage === "missing" ? 0 : bucket.recordCount;
                      const label = `${date}, ${weekday}, ${valueLabel(bucket, metric)}${metric === "tokens" && value !== null ? " tokens" : ""}, ${bucket.coverage} coverage, ${recordCount.toLocaleString("en-US")} records`;
                      return (
                        <span role="gridcell" aria-selected={selected} key={date} className="flex min-w-7 flex-1">
                          <button
                            ref={(node) => { if (node) buttonRefs.current.set(date, node); else buttonRefs.current.delete(date); }}
                            type="button"
                            tabIndex={date === activeDate ? 0 : -1}
                            aria-label={label}
                            aria-pressed={selected}
                            title={label}
                            onFocus={() => setFocusedDate(date)}
                            onKeyDown={(event) => handleKeyDown(event, date)}
                            onClick={() => onSelect(selected ? null : date)}
                            className={cn("relative flex h-7 min-w-7 flex-1 items-center justify-center rounded-[4px] border text-[13px] font-medium text-foreground transition-[outline] hover:outline hover:outline-1 hover:outline-foreground/60 focus-visible:z-10", selected ? "border-foreground outline-2 outline-offset-2 outline-brand" : "border-border-strong", bucket.coverage === "future" && "border-dashed")}
                            style={{ backgroundColor: value === null ? "var(--card)" : INTENSITY_COLORS[intensity], color: value !== null && intensity === 5 ? "var(--brand-foreground)" : "var(--foreground)", backgroundImage: bucket.coverage === "missing" ? "repeating-linear-gradient(135deg, transparent 0 4px, var(--border-strong) 4px 5px)" : undefined }}
                          >
                            <span aria-hidden="true">{COVERAGE_MARK[bucket.coverage]}</span>
                          </button>
                        </span>
                      );
                    })}
                  </div>
                ))}
              </div>
            </div>
          </div>
          <div className="mt-4 flex flex-wrap items-center gap-x-5 gap-y-3 border-t border-border pt-4 text-[11px] text-muted-foreground">
            <ul className="flex flex-wrap items-center gap-x-3 gap-y-2" aria-label={`${metric} intensity thresholds`}>
              {thresholds.map((threshold, index) => <li key={threshold} className="flex items-center gap-1.5"><span aria-hidden="true" className="size-3 rounded-[2px] border border-border-strong" style={{ backgroundColor: INTENSITY_COLORS[index] }} />{threshold}</li>)}
            </ul>
            <ul className="flex flex-wrap gap-x-3 gap-y-2" aria-label="Coverage markers">
              <li>◐ Partial</li><li>× Missing</li><li>? Unknown</li><li>– Future</li>
            </ul>
          </div>
          <p id={`${id}-keys`} className="mt-3 pb-5 text-[11px] leading-relaxed text-muted-foreground">Arrow up/down: one day. Left/right: one week. Home/End: range ends. Enter or Space: select. Escape: full range. Color scales stay fixed when the range changes.</p>
        </div>
      )}

      {ordered.length > 0 && (
        <details className="border-t border-border">
          <summary className="cursor-pointer px-5 py-3 text-xs text-muted-foreground hover:text-foreground">Daily values · {ordered.length} days</summary>
          <div className="max-h-96 overflow-auto px-5 pb-4">
            <table className="w-full whitespace-nowrap text-left text-xs">
              <caption className="sr-only">Daily usage values. Costs are USD; included usage is informational and excluded from spend. Tokens are observed input plus output.</caption>
              <thead className="sticky top-0 bg-card text-[11px] text-muted-foreground">
                <tr>{["Date (UTC)", "Coverage", "Recorded spend", "Reported", "Estimated", "Measured", "Usage value", "Included notional", "Total tokens"].map((label, index) => <th scope="col" key={label} className={cn("px-3 py-2 font-normal first:pl-0", index > 1 && "text-right")}>{label}</th>)}</tr>
              </thead>
              <tbody className="divide-y divide-border">
                {ordered.map((bucket) => {
                  const observed = bucket.coverage !== "future" && bucket.coverage !== "missing";
                  return <tr key={bucket.date} className={cn(bucket.date === selectedDate && "bg-brand-soft")}>
                  <th scope="row" className="py-2 pr-3 font-normal">{bucket.date}</th>
                  <td className="px-3 py-2 capitalize">{bucket.coverage}</td>
                  <td className="num px-3 py-2 text-right">{formatExactUsd(observed ? bucket.recordedSpend : null)}</td>
                  {(["reported", "estimated", "measured", "simulated"] as const).map((kind) => <td key={kind} className="num px-3 py-2 text-right text-muted-foreground">{formatExactUsd(observed ? bucket.costsByValueKind[kind] : null)}</td>)}
                  <td className="num px-3 py-2 text-right text-muted-foreground">{formatExactUsd(observed ? bucket.includedUsageNotional : null)}</td>
                  <td className="num px-3 py-2 text-right">{formatUsageValue(observed ? bucket.tokens.total : null, "tokens")}</td>
                </tr>;
                })}
              </tbody>
            </table>
          </div>
        </details>
      )}
    </section>
  );
}
