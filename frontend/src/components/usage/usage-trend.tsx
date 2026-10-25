"use client";

import { useId, useMemo } from "react";
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { DailyUsageBucket, UsageMetric } from "@/lib/contracts/usage";
import { formatExactUsd, formatUsageValue, usageValue } from "@/lib/usage-derive";

interface Props {
  buckets: DailyUsageBucket[];
  metric: UsageMetric;
  selectedDate: string | null;
  onSelect: (date: string | null) => void;
}

const AXIS_TICK = { fontSize: 11, fill: "var(--muted-foreground)", fontFamily: "var(--font-mono)" };

function shortDate(date: string) {
  return new Date(`${date}T00:00:00Z`).toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" });
}

/** Only observed values are plotted. Null telemetry breaks the line. */
export function UsageTrend({ buckets, metric, selectedDate, onSelect }: Props) {
  const id = useId();
  const rows = useMemo(() => [...buckets].sort((a, b) => a.date.localeCompare(b.date)).map((bucket) => ({ ...bucket, value: bucket.coverage === "future" ? null : usageValue(bucket, metric) })), [buckets, metric]);
  const hasValues = rows.some((row) => row.value !== null);

  return (
    <section className="min-w-0 rounded-xl border border-border bg-card" aria-labelledby={`${id}-heading`}>
      <div className="px-5 pt-5">
        <h2 id={`${id}-heading`} className="text-base font-medium">{metric === "spend" ? "Daily spend" : "Daily tokens"}</h2>
        <p className="mt-1 text-xs text-muted-foreground">Select a day to inspect. Gaps mean missing data.</p>
      </div>
      {!hasValues ? <p className="px-5 py-10 text-sm text-muted-foreground">No observed {metric === "spend" ? "spending" : "token totals"} to plot in this range.</p> : (
        <div className="h-60 min-w-0 px-2 pt-5 sm:h-64 sm:px-4" aria-label={`Daily observed ${metric}. Exact values are available in the activity calendar and daily values table.`}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={rows} margin={{ top: 8, right: 12, bottom: 12, left: 0 }} accessibilityLayer onClick={(state) => {
              const date = state.activeLabel;
              if (typeof date === "string" && rows.some((row) => row.date === date)) onSelect(date === selectedDate ? null : date);
            }}>
              <CartesianGrid vertical={false} stroke="var(--border)" />
              <XAxis dataKey="date" tickFormatter={shortDate} tick={AXIS_TICK} axisLine={false} tickLine={false} minTickGap={36} tickMargin={10} interval="preserveStartEnd" />
              <YAxis tickFormatter={(value: number) => formatUsageValue(value, metric, { compact: true })} tick={AXIS_TICK} axisLine={false} tickLine={false} width={64} domain={[0, "auto"]} />
              <Tooltip cursor={{ stroke: "var(--border-strong)", strokeDasharray: "3 3" }} content={({ active, payload }) => {
                const row = payload?.[0]?.payload as (DailyUsageBucket & { value: number | null }) | undefined;
                if (!active || !row) return null;
                return <div className="max-w-72 rounded-lg border border-border-strong bg-popover px-3 py-2.5 text-xs text-popover-foreground shadow-(--shadow-floating)"><p className="font-medium">{row.date} · UTC</p><p className="num mt-2 text-sm">{metric === "spend" ? formatExactUsd(row.recordedSpend) : `${formatUsageValue(row.tokens.total, "tokens")} tokens`}</p><p className="mt-1 capitalize text-muted-foreground">{row.coverage} coverage · {row.recordCount.toLocaleString("en-US")} records</p></div>;
              }} />
              {selectedDate && <ReferenceLine x={selectedDate} stroke="var(--muted-foreground)" strokeDasharray="4 3" />}
              <Line dataKey="value" type="linear" stroke="var(--chart-1)" strokeWidth={2} dot={{ r: 2, fill: "var(--chart-1)", strokeWidth: 0 }} activeDot={{ r: 4, fill: "var(--chart-1)", stroke: "var(--card)", strokeWidth: 2 }} connectNulls={false} isAnimationActive={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </section>
  );
}
