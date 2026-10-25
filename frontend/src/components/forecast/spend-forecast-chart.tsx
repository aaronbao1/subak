"use client";
import { useState } from "react";
import { Area, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { ForecastView } from "@/lib/contracts";
import { chartDate, chartMoney, forecastChartRows, type ChartBand, type ChartHorizon } from "./chart-data";

const horizonLabel: Record<ChartHorizon, string> = { cumulative: "Cumulative detail", daily: "Daily forecast", weekly: "Weekly forecast" };

/** One readable chart; uncertainty and exact records are deliberate, secondary choices. */
export function SpendForecastChart({ view }: { view: ForecastView }) {
  const [horizon, setHorizon] = useState<ChartHorizon>("cumulative");
  const [band, setBand] = useState<ChartBand>("none");
  const [level, setLevel] = useState<"80" | "95">("80");
  const rows = forecastChartRows(view, horizon, level);
  const hasBand = band !== "none" && rows.some(row => row[band]);
  const unit = view.target.unit;
  const first = rows[0], last = rows.at(-1);
  const chartStart = horizon === "weekly" ? first?.point.start ?? first?.date : first?.date;
  const chartEnd = horizon === "weekly" && last?.point.end
    ? new Date(Date.parse(`${last.point.end.slice(0, 10)}T00:00:00Z`) - 86_400_000).toISOString().slice(0, 10)
    : last?.date;
  const chartWindow = chartStart && chartEnd ? `${chartDate(chartStart)}–${chartDate(chartEnd)}` : undefined;
  return <div className="min-w-0">
    <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <span aria-hidden className="h-0.5 w-5 bg-primary" /> {horizonLabel[horizon]}{chartWindow ? ` · ${chartWindow}` : ""}
      </div>
      <label className="flex items-center gap-2 text-xs text-muted-foreground">
        View
        <select aria-label="Forecast chart view" value={horizon} onChange={event => setHorizon(event.target.value as ChartHorizon)} className="h-8 rounded-md border border-border bg-card px-2 text-foreground">
          {Object.entries(horizonLabel).map(([key, value]) => <option key={key} value={key}>{value}</option>)}
        </select>
      </label>
    </div>
    {rows.length ? <div className="h-64 w-full min-w-0 sm:h-72" aria-label={`${horizonLabel[horizon]} chart; exact values available below`}>
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={rows} accessibilityLayer margin={{ top: 8, right: 12, left: 0, bottom: 8 }}>
          <CartesianGrid stroke="var(--border)" vertical={false} strokeDasharray="3 5" />
          <XAxis dataKey="date" tickFormatter={chartDate} tick={{ fontSize: 11, fill: "var(--muted-foreground)" }} axisLine={false} tickLine={false} minTickGap={35} dy={8} />
          <YAxis tickFormatter={value => chartMoney(value, unit, true)} tick={{ fontSize: 11, fill: "var(--muted-foreground)" }} axisLine={false} tickLine={false} width={68} />
          <Tooltip content={({ active, payload, label }) => active && payload?.length ? <div className="min-w-44 rounded-lg border border-border bg-popover px-3 py-2.5 text-xs text-popover-foreground shadow-xl">
            <p className="mb-2 font-medium">{chartDate(String(label))}</p>
            {payload.map(item => <p key={String(item.dataKey)} className="mt-1 flex items-center justify-between gap-5"><span className="text-muted-foreground">{String(item.name)}</span><span className="font-medium tabular-nums">{Array.isArray(item.value) ? item.value.map(value => chartMoney(value, unit)).join(" – ") : chartMoney(item.value, unit)}</span></p>)}
          </div> : null} />
          {band === "scenario" && hasBand && <Area dataKey="scenario" name="Scenario range" stroke="none" fill="var(--primary)" fillOpacity={0.16} connectNulls={false} isAnimationActive={false} />}
          {band === "error" && hasBand && <Area dataKey="error" name={`Historical range (${level}%)`} stroke="none" fill="var(--chart-2)" fillOpacity={0.18} connectNulls={false} isAnimationActive={false} />}
          <Line dataKey="base" name={horizon === "cumulative" ? "Cumulative spend" : "Published forecast"} type="linear" dot={false} stroke="var(--primary)" strokeWidth={2.5} connectNulls={false} isAnimationActive={false} />
        </ComposedChart>
      </ResponsiveContainer>
    </div> : <p className="py-12 text-center text-sm text-muted-foreground">No published values for this view.</p>}
    <p className="mt-1 text-xs text-muted-foreground">{horizon === "cumulative" ? "Published cumulative detail includes recorded spend. The full-period total above can extend beyond this chart." : horizon === "weekly" ? "Published calendar weeks; the first week may be partial." : "Published daily values, limited to the available forecast horizon."} {view.timezone ?? "UTC"}</p>
    <details className="mt-4 border-t border-border pt-3">
      <summary className="cursor-pointer text-xs text-muted-foreground hover:text-foreground">Chart options and exact values</summary>
      <div className="mt-4 space-y-4">
        <div className="flex flex-wrap items-center gap-3 text-xs">
          <label className="flex items-center gap-2">Range<select aria-label="Forecast range" value={band} onChange={event => setBand(event.target.value as ChartBand)} className="rounded-md border border-border bg-card p-2"><option value="none">Base only</option><option value="scenario">Scenario range</option><option value="error">Historical error</option></select></label>
          {band === "error" && <label className="flex items-center gap-2">Level<select aria-label="Historical error level" value={level} onChange={event => setLevel(event.target.value as "80" | "95")} className="rounded-md border border-border bg-card p-2"><option value="80">80%</option><option value="95">95%</option></select></label>}
        </div>
        {band !== "none" && <p className="text-xs text-muted-foreground">{!hasBand ? `${band === "scenario" ? "Scenario range" : "Historical error interval"} unavailable for this view. No bounds are inferred.` : band === "scenario" ? "Low and high assumptions describe possible spending; this is not a confidence interval." : "Intervals apply separately to each date, not the whole path. They are separate from scenario assumptions."}</p>}
        {band === "scenario" && view.scenario_range?.complete === false && <p className="text-xs text-warning">Partial range: some uncertainty is unavailable. See calculation details.</p>}
        <div className="max-h-72 overflow-auto rounded-md border border-border">
          <table className="w-full min-w-[420px] text-left text-xs"><caption className="sr-only">Exact published {horizonLabel[horizon].toLowerCase()} values in {unit}</caption><thead className="sticky top-0 bg-card text-muted-foreground"><tr><th className="p-3 font-normal">Date / period (UTC)</th><th className="p-3 text-right font-normal">Published amount</th>{band !== "none" && <th className="p-3 text-right font-normal">{band === "scenario" ? "Scenario range" : `Historical error (${level}%)`}</th>}<th className="p-3 font-normal">Coverage</th></tr></thead><tbody>{rows.map((row, index) => <tr key={`${row.date}-${index}`} className="border-t border-border"><td className="p-3">{row.point.start && row.point.end ? `${row.point.start} → ${row.point.end} (exclusive)` : row.date}{row.point.partial === true && " · partial period"}</td><td className="p-3 text-right tabular-nums">{chartMoney(row.base, unit)}</td>{band !== "none" && <td className="p-3 text-right tabular-nums">{row[band]?.map(value => chartMoney(value, unit)).join(" – ") ?? "Unavailable"}</td>}<td className="p-3 text-muted-foreground">{row.point.complete === false ? "Incomplete inputs" : "Published inputs"}</td></tr>)}</tbody></table>
        </div>
      </div>
    </details>
  </div>;
}
