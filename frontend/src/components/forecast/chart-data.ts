import type { ForecastPoint, ForecastView } from "@/lib/contracts/forecast-view";

export type ChartHorizon = "cumulative" | "daily" | "weekly";
export type ChartBand = "none" | "scenario" | "error";
export type ChartRow = {
  date: string;
  base: number | null;
  scenario?: [number, number];
  error?: [number, number];
  point: ForecastPoint;
};

const finite = (value: unknown): value is number => typeof value === "number" && Number.isFinite(value);
/** Preserve the published paths exactly. A missing value stays missing and bounds never become another kind of interval. */
export function forecastChartRows(view: ForecastView, horizon: ChartHorizon, level: "80" | "95" = "80"): ChartRow[] {
  return view[horizon].map(point => {
    const interval = point.historical_error_interval?.[level];
    return {
      date: point.date ?? point.end ?? point.start ?? "",
      base: finite(point.base) ? point.base : null,
      scenario: finite(point.low) && finite(point.high) ? [point.low, point.high] : undefined,
      error: interval?.status === "available_assumption_conditional" && finite(interval.lower) && finite(interval.upper)
        ? [interval.lower, interval.upper] : undefined,
      point,
    };
  });
}

export function chartDate(value: string): string {
  if (!value) return "Unknown date";
  const date = new Date(`${value.slice(0, 10)}T00:00:00Z`);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" });
}
export function chartMoney(value: unknown, unit: string, compact = false): string {
  if (!finite(value)) return "Unavailable";
  const amount = new Intl.NumberFormat("en-US", { notation: compact ? "compact" : "standard", minimumFractionDigits: !compact && value % 1 !== 0 ? 2 : 0, maximumFractionDigits: compact ? 1 : 2 }).format(value);
  return unit.toLowerCase() === "usd" ? `$${amount}` : `${amount} ${unit.toLowerCase()}`;
}
