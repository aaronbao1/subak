import type { WeeklyHistoryResponse, WeeklyHistoryWeek } from "@/lib/contracts/weekly-history";

export type WeeklyChartRow = {
  week: WeeklyHistoryWeek;
  start: string;
  actual: number | null;
  forecast: number | null;
  forecastKind: "original" | "outlook" | null;
  variance: number | null;
  comparison: "over" | "under" | "on_forecast" | "in_progress" | "upcoming" | "missing_forecast" | "awaiting_actuals" | "unavailable";
};
export function weeklyNumber(value: string | number | null | undefined): number | null {
  if (typeof value === "number") return Number.isFinite(value) ? value : null;
  if (typeof value !== "string" || !/^-?\d+(?:\.\d+)?$/.test(value)) return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}
/** Presentation selects supplied values only; it never builds a full-week forecast from a remainder or recomputes a final miss. */
export function weeklyChartRows(history: WeeklyHistoryResponse): WeeklyChartRow[] {
  return history.weeks.map(week => {
    const prior = week.priorForecast;
    const priorMatches = prior && prior.start === week.start && prior.endExclusive === week.endExclusive
      && Number.isFinite(Date.parse(prior.issuedAt)) && Date.parse(prior.issuedAt) <= Date.parse(`${week.start}T00:00:00Z`);
    const outlook = week.outlook;
    const outlookMatches = outlook && !outlook.partial && outlook.start === week.start && outlook.endExclusive === week.endExclusive;
    const actual = week.state === "future" || week.actual.status === "future" ? null : weeklyNumber(week.actual.amount);
    const priorAmount = priorMatches ? weeklyNumber(prior.amount) : null;
    const outlookAmount = outlookMatches ? weeklyNumber(outlook.amount) : null;
    const forecast = week.state === "closed" ? priorAmount : outlookAmount ?? priorAmount;
    const forecastKind = forecast === null ? null : ((week.state !== "closed" && outlookAmount !== null) || week.state === "future") ? "outlook" : "original";
    const variance = week.state === "closed" && week.actual.status === "mature" && actual !== null && priorAmount !== null && week.actual.datasetId === prior?.datasetId && week.variance.status === "available" ? weeklyNumber(week.variance.amount) : null;
    const comparison = variance !== null ? variance > 0 ? "over" : variance < 0 ? "under" : "on_forecast"
      : week.state === "current" ? "in_progress" : week.state === "future" ? "upcoming" : priorAmount === null ? "missing_forecast" : week.actual.status !== "mature" ? "awaiting_actuals" : "unavailable";
    return { week, start: week.start, actual, forecast, forecastKind, variance, comparison };
  });
}
export function defaultReviewWeek(rows: WeeklyChartRow[]): WeeklyChartRow | undefined {
  return [...rows].reverse().find(row => row.variance !== null) ?? rows.find(row => row.week.state === "current") ?? [...rows].reverse().find(row => row.week.state === "closed") ?? rows[0];
}
export function weeklyMoney(value: number | string | null | undefined, compact = false): string {
  const amount = weeklyNumber(value);
  if (amount === null) return "—";
  const abbreviated = compact && Math.abs(amount) >= 1_000;
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", notation: abbreviated ? "compact" : "standard", maximumFractionDigits: abbreviated ? 1 : 2, minimumFractionDigits: !abbreviated && amount % 1 !== 0 ? 2 : 0 }).format(amount);
}
export function weeklyDate(value: string): string { return new Date(`${value.slice(0, 10)}T00:00:00Z`).toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" }); }
export function weekRange(start: string, endExclusive: string): string { return `${weeklyDate(start)}–${weeklyDate(new Date(Date.parse(`${endExclusive}T00:00:00Z`) - 86_400_000).toISOString().slice(0, 10))}`; }
export const comparisonLabel = (row: WeeklyChartRow, compact = false): string => row.variance !== null
  ? row.variance === 0 ? "On forecast" : `${row.variance > 0 ? "+" : "−"}${weeklyMoney(Math.abs(row.variance), compact)} ${row.variance > 0 ? "over" : "under"}`
  : ({ in_progress: "In progress", upcoming: "Upcoming", missing_forecast: "No prior forecast", awaiting_actuals: "Awaiting actuals", unavailable: "Not comparable", over: "Over", under: "Under", on_forecast: "On forecast" }[row.comparison]);
