"use client";
import { useId, useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ChevronRight, RefreshCw } from "lucide-react";
import type { WeeklyHistoryResponse } from "@/lib/contracts/weekly-history";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { WeekReview } from "./week-review";
import { comparisonLabel, defaultReviewWeek, weeklyChartRows, weeklyDate, weeklyMoney, weekRange, type WeeklyChartRow } from "./weekly-spend-derive";

/** One weekly finance view. The lower table is also the keyboard and touch equivalent of selecting a chart bar. */
export function WeeklySpendOverview({ history, loading = false, error, onRetry, onUpdateForecast, updatingForecast = false }: {
  history?: WeeklyHistoryResponse;
  loading?: boolean;
  error?: string;
  onRetry?: () => void;
  onUpdateForecast?: () => void;
  updatingForecast?: boolean;
}) {
  const [selection, setSelection] = useState<{ context: string; start: string }>();
  const [reviewOpen, setReviewOpen] = useState(false);
  const patternId = `weekly-partial-${useId().replaceAll(":", "")}`;
  const rows = useMemo(() => history ? weeklyChartRows(history) : [], [history]);
  const context = history ? `${history.datasetId}:${history.scope.type}:${history.scope.id}:${history.startDate}:${history.endDateExclusive}` : "";
  const selected = selection?.context === context ? rows.find(row => row.start === selection.start) ?? defaultReviewWeek(rows) : defaultReviewWeek(rows);
  const select = (row: WeeklyChartRow) => { setSelection({ context, start: row.start }); setReviewOpen(true); };
  const selectedTone = selected?.variance == null ? "text-muted-foreground" : selected.variance > 0 ? "text-destructive" : selected.variance < 0 ? "text-success" : "text-foreground";

  if (!history && loading) return <section aria-label="Loading weekly spending" className="space-y-6 rounded-xl border border-border bg-card p-5"><Skeleton className="h-5 w-40" /><div className="grid grid-cols-3 gap-5">{[1, 2, 3].map(key => <Skeleton key={key} className="h-16" />)}</div><Skeleton className="h-56" /></section>;
  if (!history || !rows.length) return <section aria-label="Weekly spending" className="rounded-xl border border-border bg-card px-5 py-10"><h2 className="text-base font-medium">Weekly spending</h2><p className="mt-2 text-sm text-muted-foreground">{error ? "Weekly spending could not be loaded." : "No weekly records are available yet."}</p>{onRetry && <Button onClick={onRetry} variant="outline" size="sm" className="mt-4"><RefreshCw className="size-3.5" />Try again</Button>}</section>;

  return <section aria-label="Weekly spending" className="min-w-0 overflow-hidden rounded-xl border border-border bg-card">
    <header className="flex flex-wrap items-center justify-between gap-2 px-5 pt-4">
      <h2 className="text-base font-medium">Weekly spending</h2>
      <div className="flex flex-wrap items-center gap-3"><span className="text-xs text-muted-foreground">{weekRange(history.startDate, history.endDateExclusive)}</span>{onUpdateForecast && <Button variant="ghost" size="sm" disabled={updatingForecast} onClick={onUpdateForecast} className="h-7 text-xs text-muted-foreground"><RefreshCw className={`size-3 ${updatingForecast ? "animate-spin" : ""}`} />{updatingForecast ? "Updating…" : "Update forecast"}</Button>}</div>
    </header>
    {error && <div role="status" className="mx-5 mt-3 flex flex-wrap items-center justify-between gap-2 rounded-md border border-warning/30 px-3 py-2 text-xs"><span>Showing previously loaded weeks. Refresh failed.</span>{onRetry && <button onClick={onRetry} className="font-medium underline underline-offset-4">Try again</button>}</div>}
    {selected && <div className="mx-5 my-3 rounded-lg border border-border">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border px-4 py-2 text-xs"><p className="font-medium">{weekRange(selected.week.start, selected.week.endExclusive)} <span className="ml-2 font-normal text-muted-foreground">{selected.week.state === "current" ? "This week" : selected.week.state === "future" ? "Upcoming" : selected.week.actual.status === "mature" ? "Completed week" : selected.week.actual.status === "disputed" ? "Under review" : "Awaiting final actuals"}</span></p><button onClick={() => select(selected)} className="inline-flex items-center gap-1 text-muted-foreground hover:text-foreground">Week review <ChevronRight className="size-3" /></button></div>
      <dl className="grid divide-y divide-border lg:grid-cols-3 lg:divide-x lg:divide-y-0">
        <SummaryAmount label={selected.week.state === "current" ? "Spend so far" : selected.week.actual.status === "mature" ? "Actual spend" : "Spend recorded"} value={selected.week.state === "future" ? "Not started" : weeklyMoney(selected.actual)} />
        <SummaryAmount label={selected.forecastKind === "original" ? "Original forecast" : selected.week.state === "current" ? "Latest forecast" : "Forecast"} value={weeklyMoney(selected.forecast)} />
        <SummaryAmount label="Over / under forecast" value={comparisonLabel(selected)} tone={selectedTone} />
      </dl>
    </div>}
    <div className="flex flex-wrap items-center justify-between gap-3 px-5 pb-2 text-xs text-muted-foreground">
      <div className="flex flex-wrap items-center gap-5"><span className="inline-flex items-center gap-2"><span aria-hidden className="h-2.5 w-3 rounded-sm bg-primary" />Actual spend</span><span className="inline-flex items-center gap-2" title="For previous weeks, the forecast published before the week began. For future weeks, the current full-week outlook."><span aria-hidden className="h-2.5 w-3 rounded-sm border border-dashed border-primary bg-primary/10" />Forecast</span>{rows.some(row => row.week.state === "current" && row.actual !== null) && <span className="inline-flex items-center gap-2"><span aria-hidden className="h-2.5 w-3 rounded-sm border border-primary bg-primary/30" />This week is in progress</span>}</div>
    </div>
    <div className="overflow-x-auto pb-2" tabIndex={0} aria-label="Weekly chart and values; scroll horizontally for all weeks">
      <div style={{ minWidth: Math.max(680, rows.length * 70 + 92) }}>
        <div className="h-[180px] w-full" aria-label="Actual and forecast spending by week">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={rows} margin={{ top: 12, right: 16, bottom: 0, left: 0 }} barCategoryGap="24%" barGap={3} accessibilityLayer>
              <defs><pattern id={patternId} patternUnits="userSpaceOnUse" width="6" height="6" patternTransform="rotate(45)"><rect width="6" height="6" fill="var(--card)" /><rect width="3" height="6" fill="var(--primary)" fillOpacity="0.75" /></pattern></defs>
              <CartesianGrid vertical={false} stroke="var(--border)" strokeDasharray="3 4" />
              <XAxis dataKey="start" axisLine={false} tickLine={false} tick={false} height={4} />
              <YAxis width={76} tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: "var(--muted-foreground)" }} tickFormatter={value => weeklyMoney(value, true)} domain={[(minimum: number) => Math.min(0, minimum), "auto"]} />
              <Tooltip cursor={{ fill: "var(--muted)", fillOpacity: 0.45 }} content={({ active, payload }) => <WeeklyTooltip active={active} row={payload?.[0]?.payload as WeeklyChartRow | undefined} />} />
              <Bar dataKey="actual" name="Actual spend" radius={[3, 3, 0, 0]} maxBarSize={27} isAnimationActive={false}>{rows.map(row => <Cell key={row.start} fill={row.week.state === "current" ? `url(#${patternId})` : "var(--primary)"} cursor="pointer" onClick={() => select(row)} />)}</Bar>
              <Bar dataKey="forecast" name="Forecast" fill="var(--primary)" fillOpacity={0.12} stroke="var(--primary)" strokeWidth={1.25} strokeDasharray="3 2" radius={[3, 3, 0, 0]} maxBarSize={27} isAnimationActive={false}>{rows.map(row => <Cell key={row.start} cursor="pointer" onClick={() => select(row)} />)}</Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
        <table className="w-full table-fixed border-collapse text-center text-xs"><caption className="sr-only">Weekly spending and forecast comparison. Select a week for its review.</caption><colgroup><col style={{ width: 76 }} />{rows.map(row => <col key={row.start} />)}<col style={{ width: 16 }} /></colgroup>
          <thead><tr><th className="text-left pl-4 font-normal text-muted-foreground">Week of</th>{rows.map(row => <th key={row.start} scope="col" className={`px-0.5 font-normal ${selected?.start === row.start ? "bg-primary/5" : ""}`}><button data-week-start={row.start} aria-pressed={selected?.start === row.start} aria-label={`Week review, ${weekRange(row.week.start, row.week.endExclusive)}. Actual ${weeklyMoney(row.actual)}. Forecast ${weeklyMoney(row.forecast)}. ${comparisonLabel(row)}.`} onClick={() => select(row)} className={`w-full rounded-md py-2 text-xs transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring ${selected?.start === row.start ? "font-semibold text-primary" : "font-medium"}`}>{weeklyDate(row.start)}{row.week.state === "current" && <span className="mt-1 block text-[9px] font-normal text-muted-foreground">This week</span>}</button></th>)}<th aria-hidden /></tr></thead>
          <tbody>
            <tr className="border-t border-border"><th scope="row" className="py-2 pl-4 text-left font-normal text-muted-foreground">Actual</th>{rows.map(row => <td key={row.start} className={`py-2 tabular-nums ${selected?.start === row.start ? "bg-primary/5" : ""}`} title={weeklyMoney(row.actual)}>{weeklyMoney(row.actual, true)}{row.actual !== null && row.week.actual.status !== "mature" && <span className="mt-0.5 block text-[9px] text-muted-foreground">{row.week.state === "current" ? "so far" : row.week.actual.status === "disputed" ? "under review" : row.week.actual.status === "pending" ? "pending" : "partial"}</span>}</td>)}<td /></tr>
            <tr className="border-t border-border"><th scope="row" className="py-2 pl-4 text-left font-normal text-muted-foreground">Forecast</th>{rows.map(row => <td key={row.start} className={`py-2 tabular-nums text-muted-foreground ${selected?.start === row.start ? "bg-primary/5" : ""}`} title={weeklyMoney(row.forecast)}>{weeklyMoney(row.forecast, true)}</td>)}<td /></tr>
            <tr className="border-t border-border"><th scope="row" className="py-2 pl-4 text-left font-normal text-muted-foreground">Over / under</th>{rows.map(row => <td key={row.start} className={`px-1 py-2 tabular-nums ${selected?.start === row.start ? "bg-primary/5" : ""} ${row.variance === null ? "text-[10px] text-muted-foreground" : row.variance > 0 ? "font-medium text-destructive" : row.variance < 0 ? "font-medium text-success" : "font-medium"}`} title={comparisonLabel(row)}>{comparisonLabel(row, true)}</td>)}<td /></tr>
          </tbody>
        </table>
      </div>
    </div>
    <WeekReview week={reviewOpen && selection?.context === context ? selected?.week : undefined} history={history} onClose={() => setReviewOpen(false)} />
  </section>;
}
function SummaryAmount({ label, value, tone = "text-foreground" }: { label: string; value: string; tone?: string }) { return <div className="min-w-0 px-4 py-2.5"><dt className="text-[11px] text-muted-foreground">{label}</dt><dd className={`mt-1 break-words text-lg font-medium leading-snug tabular-nums sm:text-[26px] ${tone}`}>{value}</dd></div>; }
function WeeklyTooltip({ active, row }: { active?: boolean; row?: WeeklyChartRow }) {
  if (!active || !row) return null;
  return <div className="min-w-48 rounded-lg border border-border bg-popover px-3 py-2 text-xs text-popover-foreground shadow-lg"><p className="mb-2 font-medium">{weekRange(row.week.start, row.week.endExclusive)}</p><p className="flex justify-between gap-5"><span className="text-muted-foreground">{row.week.state === "current" ? "Spend so far" : "Actual spend"}</span><span className="tabular-nums">{weeklyMoney(row.actual)}</span></p><p className="mt-1 flex justify-between gap-5"><span className="text-muted-foreground">{row.forecastKind === "original" ? "Original forecast" : row.week.state === "current" ? "Latest forecast" : "Forecast"}</span><span className="tabular-nums">{weeklyMoney(row.forecast)}</span></p><p className="mt-2 border-t border-border pt-2 font-medium">{comparisonLabel(row)}</p></div>;
}
