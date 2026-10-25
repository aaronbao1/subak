"use client";

import { useId, useMemo } from "react";
import type { DailyUsageBucket, UsageMetric, UsageTokens, UsageValueKind } from "@/lib/contracts/usage";
import { aggregateUsageBreakdowns, formatExactUsd, formatUsageValue, summarizeUsage } from "@/lib/usage-derive";
import { cn } from "@/lib/utils";
import { displayCopy, displayReference } from "@/lib/display-copy";

interface Props {
  buckets: DailyUsageBucket[];
  selectedDate: string | null;
  metric: UsageMetric;
  synthetic: boolean;
}

const VALUE_KINDS: { kind: UsageValueKind; label: string }[] = [
  { kind: "reported", label: "Reported" }, { kind: "estimated", label: "Estimated" },
  { kind: "measured", label: "Measured" }, { kind: "simulated", label: "Usage value" },
];
const TOKEN_CATEGORIES: { key: keyof UsageTokens; label: string; subset?: boolean }[] = [
  { key: "input", label: "Input" }, { key: "cachedInput", label: "Cached input", subset: true },
  { key: "output", label: "Output" }, { key: "reasoning", label: "Reasoning", subset: true },
];

export function DayDetail({ buckets, selectedDate, metric }: Props) {
  const id = useId();
  const selectedBuckets = useMemo(() => selectedDate ? buckets.filter((bucket) => bucket.date === selectedDate) : buckets, [buckets, selectedDate]);
  const observedBuckets = useMemo(() => selectedBuckets.filter((bucket) => bucket.coverage !== "future" && bucket.coverage !== "missing"), [selectedBuckets]);
  const summary = useMemo(() => summarizeUsage(observedBuckets), [observedBuckets]);
  const breakdowns = useMemo(() => aggregateUsageBreakdowns(observedBuckets), [observedBuckets]);
  const sourceRefs = useMemo(() => [...new Set(observedBuckets.flatMap((bucket) => bucket.sourceRefs))], [observedBuckets]);
  const coverageCounts = selectedBuckets.reduce<Record<string, number>>((counts, bucket) => ({ ...counts, [bucket.coverage]: (counts[bucket.coverage] ?? 0) + 1 }), {});
  const coverageText = Object.entries(coverageCounts).map(([coverage, count]) => `${count} ${coverage}`).join(" · ");
  const hasIncompleteCoverage = selectedBuckets.some((bucket) => bucket.coverage !== "complete");
  const tokenCoverage = (key: keyof UsageTokens) => observedBuckets.every((bucket) => bucket.recordCount === 0 || bucket.tokenObservedRecordCounts?.[key] !== undefined)
    ? `${(summary.tokenObservedRecordCounts?.[key] ?? 0).toLocaleString("en-US")} of ${summary.recordCount.toLocaleString("en-US")} records`
    : "Record coverage not supplied";

  return (
    <section className="min-w-0 rounded-xl border border-border bg-card" aria-labelledby={`${id}-heading`}>
      <div className="flex flex-wrap items-start justify-between gap-2 px-5 pt-5">
        <div>
          <h2 id={`${id}-heading`} className="text-base font-medium">{selectedDate ? selectedDate : "Selected range"}</h2>
          <p className="mt-1 text-xs text-muted-foreground" aria-live="polite">{selectedDate ? "Day detail · UTC" : `${selectedBuckets.length} UTC days`} · {summary.recordCount.toLocaleString("en-US")} records</p>
        </div>
        {selectedDate && selectedBuckets[0] && <span className="rounded-md border border-border px-2 py-1 text-[11px] capitalize text-muted-foreground">{selectedBuckets[0].coverage} coverage</span>}
      </div>

      {selectedBuckets.length === 0 ? <p className="px-5 py-8 text-sm text-muted-foreground">No recorded usage is available for this selection.</p> : (
        <>
          <div className="grid gap-5 px-5 py-5 sm:grid-cols-2">
            <div>
              <p className="text-xs text-muted-foreground">Recorded spend</p>
              <p className={cn("num mt-1 break-words font-medium tracking-tight", metric === "spend" ? "text-2xl" : "text-xl")}>{formatExactUsd(summary.recordedSpend)}</p>
              <p className="mt-1 text-[11px] text-muted-foreground">USD · excludes included usage</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Observed tokens</p>
              <p className={cn("num mt-1 break-words font-medium tracking-tight", metric === "tokens" ? "text-2xl" : "text-xl")}>{formatUsageValue(summary.tokens.total, "tokens")}</p>
              <p className="mt-1 text-[11px] text-muted-foreground">{tokenCoverage("total")}</p>
            </div>
          </div>

          <details className="border-t border-border">
            <summary className="cursor-pointer px-5 py-3 text-sm text-muted-foreground hover:text-foreground">Cost & token details</summary>
          <div className="border-t border-border px-5 py-4">
            <h3 className="text-xs font-medium">Cost sources</h3>
            <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-3 xl:grid-cols-4">
              {VALUE_KINDS.map(({ kind, label }) => <div key={kind}><dt className="text-[11px] text-muted-foreground">{label}</dt><dd className="num mt-1 break-words text-sm">{formatExactUsd(summary.costsByValueKind[kind])}</dd></div>)}
            </dl>
            <div className="mt-4 flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 rounded-md bg-muted/40 px-3 py-2 text-xs text-muted-foreground">
              <span>Included usage · informational, excluded from spend</span><span className="num">{formatExactUsd(summary.includedUsageNotional)}</span>
            </div>
          </div>

          <div className="border-t border-border px-5 py-4">
            <h3 className="text-xs font-medium">Token categories</h3>
            <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-3 xl:grid-cols-4">
              {TOKEN_CATEGORIES.map(({ key, label, subset }) => <div key={key}><dt className="text-[11px] text-muted-foreground">{label}{subset ? " · subset" : ""}</dt><dd className="num mt-1 text-sm">{formatUsageValue(summary.tokens[key], "tokens")}<span className="mt-1 block text-[10px] text-muted-foreground">{tokenCoverage(key)}</span></dd></div>)}
            </dl>
            <p className="mt-3 text-[11px] leading-relaxed text-muted-foreground">Cached input is a subset of input; reasoning is a subset of output. Neither is added again. Unavailable telemetry stays unavailable, even when spend is zero.</p>
            {hasIncompleteCoverage && <p className="mt-2 text-[11px] leading-relaxed text-muted-foreground">This selection has incomplete coverage. Totals reflect available records; they do not fill missing days or predict future usage.</p>}
          </div>

          </details>

          <div className="border-t border-border px-5 py-4">
            <h3 className="text-xs font-medium">Usage by model</h3>
            {breakdowns.length === 0 ? <p className="mt-3 text-xs text-muted-foreground">No provider or model breakdown is available for this selection.</p> : (
              <div className="mt-3 max-h-80 overflow-auto">
                <table className="w-full text-left text-xs">
                  <caption className="sr-only">Recorded spending and observed tokens grouped by the full provider, model and tool identity.</caption>
                  <thead className="sticky top-0 bg-card text-[11px] text-muted-foreground"><tr><th scope="col" className="pb-2 pr-4 font-normal">Provider / model / tool</th><th scope="col" className="pb-2 pr-4 text-right font-normal">Tokens</th><th scope="col" className="pb-2 text-right font-normal">Spend</th></tr></thead>
                  <tbody className="divide-y divide-border">{breakdowns.map((row) => <tr key={JSON.stringify([row.provider, row.model, row.tool ?? null])}>
                    <th scope="row" className="min-w-36 py-3 pr-4 font-normal"><span className="block break-words">{displayCopy(row.model, "No model supplied")}</span><span className="mt-1 block break-words text-[11px] text-muted-foreground">{displayCopy(row.provider, "No provider supplied")}{row.tool ? ` · ${displayCopy(row.tool)}` : ""}</span></th>
                    <td className="num whitespace-nowrap py-3 pr-4 text-right text-muted-foreground">{formatUsageValue(row.tokens.total, "tokens")}</td>
                    <td className="num whitespace-nowrap py-3 text-right">{formatExactUsd(row.recordedSpend)}</td>
                  </tr>)}</tbody>
                </table>
              </div>
            )}
          </div>

          <details className="border-t border-border">
            <summary className="cursor-pointer px-5 py-3 text-xs text-muted-foreground hover:text-foreground">Data details</summary>
            <div className="space-y-4 px-5 pb-5 text-xs">
              <p className="text-muted-foreground">{coverageText || "Coverage unavailable"}.</p>
              <div className="max-h-44 overflow-auto"><table className="w-full text-left text-[11px]"><thead className="text-muted-foreground"><tr><th scope="col" className="pb-2 pr-3 font-normal">UTC day</th><th scope="col" className="pb-2 pr-3 font-normal">Coverage</th><th scope="col" className="pb-2 font-normal">Records</th></tr></thead><tbody className="divide-y divide-border">{selectedBuckets.map((bucket) => <tr key={bucket.date}><th scope="row" className="whitespace-nowrap py-2 pr-3 font-normal">{bucket.date}</th><td className="py-2 pr-3 capitalize text-muted-foreground">{bucket.coverage}</td><td className="break-all py-2 font-mono text-muted-foreground">{bucket.recordCount.toLocaleString("en-US")}</td></tr>)}</tbody></table></div>
              <div><h3 className="text-xs font-medium">Source references · {sourceRefs.length.toLocaleString("en-US")}</h3>{sourceRefs.length === 0 ? <p className="mt-2 text-muted-foreground">No source references supplied.</p> : <ul className="mt-2 max-h-40 space-y-1 overflow-auto font-mono text-[11px] text-muted-foreground">{sourceRefs.map((reference, index) => <li key={reference} className="break-all">{displayCopy(displayReference(reference, `Source ${index + 1}`))}</li>)}</ul>}</div>
            </div>
          </details>
        </>
      )}
    </section>
  );
}
