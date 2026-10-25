import type { Period, SpendingRecord, Team, Unit } from "@/lib/contracts";
import { billableAmount, sumMoney } from "@/lib/finance-summary";
import type { DailyRow } from "./derive";

const DAY = 86_400_000;
const UNASSIGNED = "__daily_unassigned";
const PALETTE = Array.from({ length: 8 }, (_, index) => `var(--chart-${index + 1})`);

function dateTime(date: string): number | null {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) return null;
  const time = Date.parse(`${date}T00:00:00Z`);
  return Number.isFinite(time) && new Date(time).toISOString().slice(0, 10) === date ? time : null;
}

/** Resolve repeated palette tokens from a full directory before any team is hidden. */
function distinctColors(teams: Team[]): Team[] {
  const reserved = new Set(teams.map(team => team.color).filter(Boolean));
  const used = new Set<string>();
  const colors = new Map<string, string>();
  let fallbackIndex = 0;
  for (const team of [...teams].sort((a, b) => a.id.localeCompare(b.id))) {
    let color = team.id === "unattributed" || team.id === UNASSIGNED ? "var(--chart-other)" : team.color;
    if (!color || used.has(color)) {
      color = PALETTE.find(candidate => !used.has(candidate) && !reserved.has(candidate)) ?? PALETTE.find(candidate => !used.has(candidate)) ?? "";
      while (!color || used.has(color)) {
        const hue = Math.round((31 + fallbackIndex * 137.508) % 360);
        color = `hsl(${hue} 60% 35%)`;
        fallbackIndex++;
      }
    }
    used.add(color);
    colors.set(team.id, color);
  }
  return teams.map(team => ({ ...team, color: colors.get(team.id)! }));
}

/** A single amount surrounded by gaps needs a visible dot even in a long date range. */
export function isIsolatedDailyAmount(rows: DailyRow[], index: number, key: string): boolean {
  if (typeof rows[index]?.[key] !== "number") return false;
  return typeof rows[index - 1]?.[key] !== "number" && typeof rows[index + 1]?.[key] !== "number";
}

/** Remove only empty edges; keep missing dates between recorded days as gaps. */
export function recordedDailyExtent(rows: DailyRow[]): DailyRow[] {
  const first = rows.findIndex(row => row.kind === "recorded");
  if (first === -1) return [];
  let last = rows.length - 1;
  while (last > first && rows[last].kind !== "recorded") last--;
  return rows.slice(first, last + 1);
}

export interface DailySpendData {
  teams: Team[];
  rows: DailyRow[];
  partialDates: string[];
  hasEstimates: boolean;
  hasUnpricedUsage: boolean;
  invalidAmountCount: number;
}

/** Actual USD charges only, inside the inclusive planning period. An absent amount is never a zero. */
export function buildDailySpendData(records: SpendingRecord[], teams: Team[], period: Period): DailySpendData {
  const start = dateTime(period.start), end = dateTime(period.end);
  const inPeriod = records.filter(record => record.unit === "usd" && record.date >= period.start && record.date <= period.end && dateTime(record.date) !== null);
  const charges = inPeriod.filter(record => record.component !== "included_usage" && record.component !== "unpriced_usage" && record.provenance !== "usage_only" && Number.isFinite(record.amount));
  const teamIds = new Set(teams.map(team => team.id));
  const unassignedId = teamIds.has("unattributed") ? "unattributed" : UNASSIGNED;
  const hasUnassigned = charges.some(record => !teamIds.has(record.teamId));
  const chartTeams = distinctColors(hasUnassigned && !teamIds.has(unassignedId) ? [...teams, { id: unassignedId, name: "Unassigned", color: "var(--chart-other)" }] : teams);
  const result: DailySpendData = {
    teams: chartTeams, rows: [], partialDates: [],
    hasEstimates: charges.some(record => record.provenance === "estimate"),
    hasUnpricedUsage: inPeriod.some(record => record.component === "unpriced_usage" || (record.provenance === "usage_only" && record.component !== "included_usage")),
    invalidAmountCount: inPeriod.filter(record => record.component !== "included_usage" && record.component !== "unpriced_usage" && record.provenance !== "usage_only" && !Number.isFinite(record.amount)).length,
  };
  if (start === null || end === null || start > end) return result;

  const totals = new Map<string, Map<string, number[]>>();
  const partial = new Set<string>();
  for (const record of charges) {
    const teamId = teamIds.has(record.teamId) ? record.teamId : unassignedId;
    const date = totals.get(record.date) ?? new Map<string, number[]>();
    const amounts = date.get(teamId) ?? [];
    amounts.push(billableAmount(record));
    date.set(teamId, amounts);
    totals.set(record.date, date);
    if (!record.complete) partial.add(record.date);
  }
  for (let time = start; time <= end; time += DAY) {
    const date = new Date(time).toISOString().slice(0, 10);
    const amounts = totals.get(date);
    const row: DailyRow = { ts: time, date, partial: partial.has(date), kind: amounts ? "recorded" : "empty" };
    for (const team of chartTeams) {
      const values = amounts?.get(team.id);
      row[`t_${team.id}`] = values ? sumMoney(values) : null;
      row[`p_${team.id}`] = null;
    }
    result.rows.push(row);
  }
  result.partialDates = [...partial].sort();
  return result;
}

/** A folded series is a recorded subtotal when some constituents have no amount. */
export function foldDailySeries(row: DailyRow, ids: string[], prefix: "t_" | "p_", unit: Unit = "usd"): { amount: number | null; missingTeams: number } {
  const values = ids.flatMap(id => typeof row[`${prefix}${id}`] === "number" && Number.isFinite(row[`${prefix}${id}`]) ? [row[`${prefix}${id}`] as number] : []);
  return { amount: values.length ? unit === "usd" ? sumMoney(values) : values.reduce((sum, value) => sum + value, 0) : null, missingTeams: ids.length - values.length };
}
