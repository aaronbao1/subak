import type { Budget, CostComponent, Forecast, ForecastDailyPoint, Period, Provenance, SpendingRecord, Team } from "@/lib/contracts";
import { projectedTotals } from "./status";

export const COMPONENT_ORDER: CostComponent[] = ["subscription", "included_usage", "extra_usage", "api"];

export const COMPONENT_LABEL: Record<CostComponent, string> = {
  subscription: "Subscription",
  included_usage: "Included usage",
  extra_usage: "Extra usage",
  api: "API",
};

export const PROVENANCE_LABEL: Record<Provenance, string> = {
  reported_charge: "Reported charge",
  estimate: "Estimate",
  usage_only: "Usage only",
};

export interface ComponentTotal {
  component: CostComponent;
  amount: number;
  provenances: Provenance[];
}

export interface DailyPoint {
  date: string;
  amount: number;
  partial: boolean;
  /** True for a forecast day: nothing has been recorded yet, the amount is a projection. */
  projected?: boolean;
}

export interface TeamSummary {
  team: Team;
  budget?: Budget;
  forecast?: Forecast;
  spent: number;
  /** Full-period projected total (never double counted). Undefined when no projection is available. */
  projected?: number;
  low?: number;
  high?: number;
  daily: DailyPoint[];
  /** Day-by-day projection for days not complete yet (the partial day's full-day total, then later days); empty when none was supplied. */
  dailyProjected: DailyPoint[];
  byComponent: ComponentTotal[];
}

/**
 * Row of the daily chart. Per team: `t_<teamId>` is the recorded amount (null when nothing was recorded that day)
 * and `p_<teamId>` the projected amount (null on complete days). A partial day can carry both: what was recorded
 * so far and the projected full-day total. The last complete day also carries the projected key so the dashed
 * line starts where the solid one ends.
 */
export interface DailyRow {
  ts: number;
  date: string;
  partial: boolean;
  /** recorded: at least one team has a record; projected: only projections exist; empty: nothing at all. */
  kind: "recorded" | "projected" | "empty";
  [key: string]: number | string | boolean | null;
}

export const teamKey = (teamId: string) => `t_${teamId}`;
export const projectedKey = (teamId: string) => `p_${teamId}`;

const DAY_MS = 86_400_000;

export function toTs(iso: string): number {
  const [y, m, d] = iso.split("-").map(Number);
  return Date.UTC(y, (m ?? 1) - 1, d ?? 1);
}

export function fromTs(ts: number): string {
  return new Date(ts).toISOString().slice(0, 10);
}

export function dateLabel(value: string | number): string {
  const d = new Date(typeof value === "number" ? value : toTs(value));
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" });
}

/** "Mon 19" for a weekly axis, "Mon, Oct 19" for tooltips. */
export function dayLabel(value: string | number, opts: { month?: boolean } = {}): string {
  const d = new Date(typeof value === "number" ? value : toTs(value));
  const weekday = d.toLocaleDateString("en-US", { weekday: "short", timeZone: "UTC" });
  return opts.month ? `${weekday}, ${dateLabel(value)}` : `${weekday} ${d.getUTCDate()}`;
}

/** Projection days the forecast supplies for dates that are not complete yet (the partial day and later), in date order. */
export function projectedDays(forecast: Forecast | undefined, completeDates: Set<string>): ForecastDailyPoint[] {
  if (!forecast || forecast.status !== "available" || !forecast.daily?.length) return [];
  return forecast.daily.filter((d) => !completeDates.has(d.date)).sort((a, b) => a.date.localeCompare(b.date));
}

/** Days where any record is partial, and the latest day where every record is complete. */
export function completion(spending: SpendingRecord[]): { asOf?: string; partialDates: string[] } {
  const byDate = new Map<string, boolean>();
  for (const r of spending) byDate.set(r.date, (byDate.get(r.date) ?? true) && r.complete);
  const dates = [...byDate.keys()].sort();
  const partialDates = dates.filter((d) => !byDate.get(d));
  const asOf = [...dates].reverse().find((d) => byDate.get(d));
  return { asOf, partialDates };
}

export function componentTotals(records: SpendingRecord[]): ComponentTotal[] {
  return COMPONENT_ORDER.map((component) => {
    const rows = records.filter((r) => r.component === component);
    const provenances = [...new Set(rows.map((r) => r.provenance))];
    return { component, amount: rows.reduce((s, r) => s + r.amount, 0), provenances };
  });
}

export function summarizeTeams(
  teams: Team[],
  spending: SpendingRecord[],
  budgets: Budget[],
  forecasts: Forecast[],
): TeamSummary[] {
  return teams.map((team) => {
    const records = spending.filter((r) => r.teamId === team.id);
    const spent = records.reduce((s, r) => s + r.amount, 0);
    const budget = budgets.find((b) => b.teamId === team.id);
    const forecast = forecasts.find((f) => f.teamId === team.id);
    const byDay = new Map<string, DailyPoint>();
    for (const r of records) {
      const p = byDay.get(r.date) ?? { date: r.date, amount: 0, partial: false };
      p.amount += r.amount;
      p.partial = p.partial || !r.complete;
      byDay.set(r.date, p);
    }
    const daily = [...byDay.values()].sort((a, b) => a.date.localeCompare(b.date));
    const completeDates = new Set([...byDay.values()].filter((p) => !p.partial).map((p) => p.date));
    const dailyProjected: DailyPoint[] = projectedDays(forecast, completeDates)
      .map((d) => ({ date: d.date, amount: d.projected, partial: false, projected: true }));
    return {
      team, budget, forecast, spent, daily, dailyProjected,
      ...projectedTotals(forecast, spent),
      byComponent: componentTotals(records),
    };
  });
}

/**
 * One row per calendar day across the period (widened to cover any recorded or projected date outside it),
 * all teams side by side. Recorded amounts come from spending; projected amounts from each team's forecast.
 */
export function buildDailyRows(teams: Team[], spending: SpendingRecord[], forecasts: Forecast[] = [], period?: Period): DailyRow[] {
  const byDate = new Map<string, { partial: boolean; totals: Map<string, number> }>();
  for (const r of spending) {
    const e = byDate.get(r.date) ?? { partial: false, totals: new Map() };
    e.partial = e.partial || !r.complete;
    e.totals.set(r.teamId, (e.totals.get(r.teamId) ?? 0) + r.amount);
    byDate.set(r.date, e);
  }
  const recordedDates = new Set(byDate.keys());
  const completeDates = new Set([...byDate.entries()].filter(([, e]) => !e.partial).map(([d]) => d));
  const projected = new Map<string, Map<string, number>>();
  for (const t of teams) {
    for (const d of projectedDays(forecasts.find((f) => f.teamId === t.id), completeDates)) {
      const m = projected.get(d.date) ?? new Map<string, number>();
      m.set(t.id, d.projected);
      projected.set(d.date, m);
    }
  }
  const dates = [...recordedDates, ...projected.keys()].sort();
  if (dates.length === 0 && !period) return [];
  const start = Math.min(...(period ? [toTs(period.start)] : []), ...(dates.length ? [toTs(dates[0])] : []));
  const end = Math.max(...(period ? [toTs(period.end)] : []), ...(dates.length ? [toTs(dates[dates.length - 1])] : []));
  if (recordedDates.size === 0 && projected.size === 0) return [];

  const rows: DailyRow[] = [];
  for (let ts = start; ts <= end; ts += DAY_MS) {
    const date = fromTs(ts);
    const e = byDate.get(date);
    const p = projected.get(date);
    const row: DailyRow = { ts, date, partial: e?.partial ?? false, kind: e ? "recorded" : p ? "projected" : "empty" };
    for (const t of teams) {
      const v = e?.totals.get(t.id);
      row[teamKey(t.id)] = typeof v === "number" ? v : null;
      const pv = p?.get(t.id);
      row[projectedKey(t.id)] = typeof pv === "number" ? pv : null;
    }
    rows.push(row);
  }
  // Anchor each dashed line to the team's last recorded point that has no projection, so it continues the solid one.
  for (const t of teams) {
    const tk = teamKey(t.id), pk = projectedKey(t.id);
    const first = rows.findIndex((r) => r[pk] !== null);
    if (first <= 0) continue;
    const anchor = rows[first - 1];
    if (anchor[tk] !== null) anchor[pk] = anchor[tk];
  }
  return rows;
}
