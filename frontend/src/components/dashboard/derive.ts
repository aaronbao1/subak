import type { Budget, CostComponent, Forecast, Provenance, SpendingRecord, Team } from "@/lib/contracts";
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
  byComponent: ComponentTotal[];
}

/** Row of the daily chart: one key per team as `t_<teamId>`; null where that team has no record that day. */
export interface DailyRow {
  ts: number;
  date: string;
  partial: boolean;
  [key: string]: number | string | boolean | null;
}

export const teamKey = (teamId: string) => `t_${teamId}`;

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
    return {
      team, budget, forecast, spent, daily,
      ...projectedTotals(forecast, spent),
      byComponent: componentTotals(records),
    };
  });
}

/** One row per calendar day from the first to the last recorded date, all teams side by side. */
export function buildDailyRows(teams: Team[], spending: SpendingRecord[]): DailyRow[] {
  if (spending.length === 0) return [];
  const byDate = new Map<string, { partial: boolean; totals: Map<string, number> }>();
  for (const r of spending) {
    const e = byDate.get(r.date) ?? { partial: false, totals: new Map() };
    e.partial = e.partial || !r.complete;
    e.totals.set(r.teamId, (e.totals.get(r.teamId) ?? 0) + r.amount);
    byDate.set(r.date, e);
  }
  const dates = [...byDate.keys()].sort();
  const start = toTs(dates[0]);
  const end = toTs(dates[dates.length - 1]);
  const rows: DailyRow[] = [];
  for (let ts = start; ts <= end; ts += DAY_MS) {
    const date = fromTs(ts);
    const e = byDate.get(date);
    const row: DailyRow = { ts, date, partial: e?.partial ?? false };
    for (const t of teams) {
      const v = e?.totals.get(t.id);
      row[teamKey(t.id)] = typeof v === "number" ? v : null;
    }
    rows.push(row);
  }
  return rows;
}
