import type { Budget, CostComponent, Forecast, ForecastDailyPoint, Period, Provenance, SpendingRecord, Team } from "@/lib/contracts";
import { COMPONENT_ORDER } from "@/components/team/labels";
import { projectedTotals } from "./status";
import { billableAmount, sumMoney } from "@/lib/finance-summary";

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
  /** API spend by model, largest first; empty when no API rows exist. */
  byModel: ModelTotal[];
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
  if (!forecast?.daily?.length || forecast.status !== "available" && forecast.dailyCoverage !== "published_detail") return [];
  // A missing quarter prefix can make the total unavailable while future days remain supported.
  return forecast.daily.filter((d) => Number.isFinite(d.projected) && !completeDates.has(d.date)).sort((a, b) => a.date.localeCompare(b.date));
}

/** A real projected value, excluding the copied last-actual anchor of a dashed line. */
export function hasProjectedAmount(row: DailyRow, teamId: string): boolean {
  const projected = row[projectedKey(teamId)], recorded = row[teamKey(teamId)];
  return typeof projected === "number" && (typeof recorded !== "number" || projected !== recorded);
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
    return { component, amount: sumMoney(rows.map(billableAmount)), provenances };
  });
}

export function summarizeTeams(
  teams: Team[],
  spending: SpendingRecord[],
  budgets: Budget[],
  forecasts: Forecast[],
): TeamSummary[] {
  return teams.map((team) => {
    const budget = budgets.find((b) => b.teamId === team.id);
    const forecast = forecasts.find((f) => f.teamId === team.id && !f.personId && (!budget || f.unit === budget.unit && f.period.start === budget.period.start && f.period.end === budget.period.end));
    const target = budget?.period ?? forecast?.period;
    const unit = budget?.unit ?? forecast?.unit;
    const records = spending.filter((r) => r.teamId === team.id && (!target || r.date >= target.start && r.date <= target.end) && (!unit || r.unit === unit));
    const spent = sumMoney(records.map(billableAmount));
    const byDay = new Map<string, DailyPoint>();
    for (const r of records) {
      const p = byDay.get(r.date) ?? { date: r.date, amount: 0, partial: false };
      p.amount = sumMoney([p.amount,billableAmount(r)]);
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
      byModel: modelTotals(records),
    };
  });
}

/**
 * One row per calendar day across the period (widened to cover any recorded or projected date outside it),
 * all teams side by side. Recorded amounts come from spending; projected amounts from each team's forecast.
 */
export function buildDailyRows(teams: Team[], spending: SpendingRecord[], forecasts: Forecast[] = [], period?: Period): DailyRow[] {
  const byDate = new Map<string, { partial: boolean; totals: Map<string, number>; complete: Map<string, boolean> }>();
  for (const r of spending) {
    const e = byDate.get(r.date) ?? { partial: false, totals: new Map(), complete: new Map() };
    e.partial = e.partial || !r.complete;
    e.totals.set(r.teamId, sumMoney([e.totals.get(r.teamId) ?? 0,billableAmount(r)]));
    e.complete.set(r.teamId, (e.complete.get(r.teamId) ?? true) && r.complete);
    byDate.set(r.date, e);
  }
  const recordedDates = new Set(byDate.keys());
  const projected = new Map<string, Map<string, number>>();
  for (const t of teams) {
    const completeDates = new Set([...byDate.entries()].filter(([, e]) => e.complete.get(t.id) === true).map(([d]) => d));
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

export interface ModelTotal {
  model: string;
  provider: string;
  amount: number;
  /** Sum of reported tokens; undefined when no row reported any. */
  tokens?: number;
}

/** API spend grouped by model, largest first. Rows without a model are grouped under their provider. */
export function modelTotals(records: SpendingRecord[]): ModelTotal[] {
  const byModel = new Map<string, ModelTotal>();
  for (const r of records) {
    if (r.component !== "api") continue;
    const model = r.model ?? `${r.provider} (unspecified model)`;
    const key = `${r.provider}\0${model}`;
    const m = byModel.get(key) ?? { model, provider: r.provider, amount: 0 };
    m.amount = sumMoney([m.amount,billableAmount(r)]);
    if (typeof r.tokens === "number") m.tokens = (m.tokens ?? 0) + r.tokens;
    byModel.set(key, m);
  }
  return [...byModel.values()].sort((a, b) => b.amount - a.amount);
}

/** API spend grouped by provider, largest first. */
export function providerTotals(records: SpendingRecord[]): ModelTotal[] {
  const byProvider = new Map<string, ModelTotal>();
  for (const m of modelTotals(records)) {
    const p = byProvider.get(m.provider) ?? { model: m.provider, provider: m.provider, amount: 0 };
    p.amount = sumMoney([p.amount,m.amount]);
    if (typeof m.tokens === "number") p.tokens = (p.tokens ?? 0) + m.tokens;
    byProvider.set(m.provider, p);
  }
  return [...byProvider.values()].sort((a, b) => b.amount - a.amount);
}
