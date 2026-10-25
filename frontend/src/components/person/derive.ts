import type { ContextItem, Forecast, Period, Person, SpendingRecord } from "@/lib/contracts";

export type Trend = "up" | "down" | "flat" | "unknown";

export interface PersonSummary {
  person: Person;
  /** Spend to date inside the period (every record, partial day included). */
  spent: number;
  forecast?: Forecast;
  /** Full-period projection; undefined when unavailable. Never adds spent to a full_period number. */
  projected?: number;
  low?: number;
  high?: number;
  /** Share of the team's full-period projection, 0..1; undefined when the team has no projection. */
  share?: number;
  /** Average daily spend on complete days this week relative to last week's daily average; e.g. -0.32. */
  weekChange?: number;
  trend: Trend;
  /** Connector signals about this person (scope "person"), newest first, superseded last. */
  signals: ContextItem[];
}

const DAY_MS = 86_400_000;
const toTs = (iso: string) => { const [y, m, d] = iso.split("-").map(Number); return Date.UTC(y, m - 1, d); };
const fromTs = (ts: number) => new Date(ts).toISOString().slice(0, 10);
const addDays = (iso: string, n: number) => fromTs(toTs(iso) + n * DAY_MS);

function dailyAverage(records: SpendingRecord[], dates: Set<string>) {
  const rows = records.filter((r) => dates.has(r.date));
  const days = new Set(rows.map((r) => r.date));
  if (days.size === 0) return undefined;
  return rows.reduce((s, r) => s + r.amount, 0) / days.size;
}

/**
 * Week-over-week change on like-for-like days: this week's complete days against the same weekdays last week,
 * so a Monday-to-Wednesday comparison is never diluted by last weekend.
 */
function weekOverWeek(records: SpendingRecord[], period: Period) {
  const thisWeekDays = new Set(records.filter((r) => r.date >= period.start && r.date <= period.end && r.complete).map((r) => r.date));
  if (thisWeekDays.size === 0) return undefined;
  const lastWeekDays = new Set([...thisWeekDays].map((d) => addDays(d, -7)));
  const now = dailyAverage(records, thisWeekDays);
  const before = dailyAverage(records, lastWeekDays);
  return now !== undefined && before ? now / before - 1 : undefined;
}

/**
 * Roll a team's people up from the same records the team view uses, so the two never disagree.
 * `spendingHistory` supplies last week for the week-over-week change; `spending` is the current period.
 */
export function summarizePeople(
  people: Person[],
  teamId: string,
  spending: SpendingRecord[],
  spendingHistory: SpendingRecord[],
  personForecasts: Forecast[],
  context: ContextItem[],
  period: Period,
): PersonSummary[] {
  const members = people.filter((p) => p.teamId === teamId);
  const teamProjected = members.reduce((s, p) => {
    const f = personForecasts.find((x) => x.personId === p.id);
    return f?.status === "available" && f.projected != null ? s + f.projected : s;
  }, 0);

  return members.map((person) => {
    const own = spending.filter((r) => r.personId === person.id);
    const ownHistory = spendingHistory.filter((r) => r.personId === person.id);
    const spent = own.reduce((s, r) => s + r.amount, 0);
    const forecast = personForecasts.find((f) => f.personId === person.id);
    const available = forecast?.status === "available" && forecast.projected != null;
    const projected = available ? (forecast!.basis === "remaining" ? spent + forecast!.projected! : forecast!.projected) : undefined;
    const weekChange = weekOverWeek(ownHistory, period);
    const trend: Trend = weekChange === undefined ? "unknown" : weekChange > 0.15 ? "up" : weekChange < -0.15 ? "down" : "flat";
    const signals = context
      .filter((c) => c.scope === "person" && c.personIds?.includes(person.id))
      .sort((a, b) => (a.supersededBy ? 1 : 0) - (b.supersededBy ? 1 : 0) || (b.effectiveFrom ?? "").localeCompare(a.effectiveFrom ?? ""));
    return {
      person, spent, forecast, projected,
      low: available ? forecast!.low : undefined,
      high: available ? forecast!.high : undefined,
      share: available && teamProjected > 0 ? (projected as number) / teamProjected : undefined,
      weekChange, trend, signals,
    };
  });
}

/** Context that bears on one person: their own signals plus company-wide (macro) items for their team. */
export function personContextItems(context: ContextItem[], person: Person): ContextItem[] {
  return context.filter(
    (c) => (c.scope === "person" && c.personIds?.includes(person.id)) || (c.scope === "company" && c.teamIds.includes(person.teamId)),
  );
}
