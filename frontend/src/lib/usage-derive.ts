import type { SpendingRecord } from "./contracts";
import type { DailyUsageBucket, DailyUsageQuery, DailyUsageResponse, UsageAggregate, UsageBreakdown, UsageCosts, UsageMetric, UsageScope, UsageTokens, UsageValueKind } from "./contracts/usage";

const VALUE_KINDS: UsageValueKind[] = ["reported", "estimated", "measured", "simulated"];
const TOKEN_KEYS: (keyof UsageTokens)[] = ["input", "cachedInput", "output", "reasoning", "total"];
const DAY_MS = 86_400_000;
/** The compatibility directory's residual pseudo-team has a native shared scope. */
export function normalizeUsageScope(scope: UsageScope): UsageScope {
  return scope.type === "team" && scope.id === "unattributed" ? { type: "shared" } : scope;
}
export const usageDateOffset = (iso: string, days: number) => new Date(Date.parse(`${iso}T00:00:00Z`) + days * DAY_MS).toISOString().slice(0, 10);
export function usageDates(start: string, endExclusive: string): string[] {
  const days = Math.round((Date.parse(`${endExclusive}T00:00:00Z`) - Date.parse(`${start}T00:00:00Z`)) / DAY_MS);
  if (!Number.isInteger(days) || days < 1 || days > 366) throw new Error("Choose a date range between 1 and 366 days.");
  return Array.from({ length: days }, (_, index) => usageDateOffset(start, index));
}

/** Decimal addition without a binary-float intermediate. Null means no recorded value. */
export function sumUsageMoney(values: (string | null | undefined)[]): string | null {
  const known = values.filter((value): value is string => value != null);
  if (!known.length) return null;
  if (known.some(value => !/^-?\d+(\.\d+)?$/.test(value))) throw new Error("Invalid exact USD value.");
  const scale = Math.max(2, ...known.map(value => value.split(".")[1]?.length ?? 0));
  const sum = known.reduce((total, value) => {
    const sign = value.startsWith("-") ? -BigInt(1) : BigInt(1);
    const [whole, fraction = ""] = value.replace(/^-/, "").split(".");
    return total + sign * BigInt(whole + fraction.padEnd(scale, "0"));
  }, BigInt(0));
  const digits = (sum < BigInt(0) ? -sum : sum).toString().padStart(scale + 1, "0");
  return `${sum < BigInt(0) ? "-" : ""}${digits.slice(0, -scale)}.${digits.slice(-scale)}`;
}
function sumKnown(values: (number | null)[]) {
  const known = values.filter((value): value is number => value !== null);
  return known.length ? known.reduce((sum, value) => sum + value, 0) : null;
}
export function summarizeUsage(buckets: UsageAggregate[]): UsageAggregate {
  const tokens = Object.fromEntries(TOKEN_KEYS.map(key => [key, sumKnown(buckets.map(bucket => bucket.tokens[key]))])) as unknown as UsageTokens;
  if (buckets.some(bucket => bucket.tokens.total === null && (bucket.tokens.input !== null || bucket.tokens.output !== null))) tokens.total = null;
  return {
    recordedSpend: sumUsageMoney(buckets.map(bucket => bucket.recordedSpend)),
    costsByValueKind: Object.fromEntries(VALUE_KINDS.map(kind => [kind, sumUsageMoney(buckets.map(bucket => bucket.costsByValueKind[kind]))])) as UsageCosts,
    includedUsageNotional: sumUsageMoney(buckets.map(bucket => bucket.includedUsageNotional)),
    tokens,
    recordCount: buckets.reduce((sum, bucket) => sum + bucket.recordCount, 0),
    tokenObservedRecordCounts: Object.fromEntries(TOKEN_KEYS.map(key => [key, buckets.reduce((sum, bucket) => sum + (bucket.tokenObservedRecordCounts?.[key] ?? 0), 0)])),
  };
}
export function aggregateUsageBreakdowns(buckets: DailyUsageBucket[]): UsageBreakdown[] {
  const groups = new Map<string, UsageBreakdown[]>();
  for (const bucket of buckets) for (const row of bucket.breakdowns) {
    const key = JSON.stringify([row.provider, row.model, row.tool ?? null]);
    groups.set(key, [...(groups.get(key) ?? []), row]);
  }
  return [...groups.values()].map(rows => ({ provider: rows[0].provider, model: rows[0].model, tool: rows[0].tool, ...summarizeUsage(rows) }))
    .sort((a, b) => Number(b.recordedSpend ?? 0) - Number(a.recordedSpend ?? 0));
}
export function usageValue(bucket: Pick<DailyUsageBucket, "coverage" | "recordedSpend" | "tokens">, metric: UsageMetric): number | null {
  if (bucket.coverage === "future" || bucket.coverage === "missing") return null;
  return metric === "tokens" ? bucket.tokens.total : bucket.recordedSpend === null ? null : Number(bucket.recordedSpend);
}
/** Fixed thresholds make the same color mean the same value in every scope. */
export function usageIntensity(value: number | null, metric: UsageMetric): number {
  if (value === null || value === 0) return 0;
  const thresholds = metric === "spend" ? [100, 1_000, 10_000, 50_000] : [100_000, 1_000_000, 10_000_000, 100_000_000];
  return 1 + thresholds.filter(threshold => Math.abs(value) >= threshold).length;
}
export function formatUsageValue(value: number | null, metric: UsageMetric, options: { compact?: boolean } = {}): string {
  if (value === null) return "Not recorded";
  return new Intl.NumberFormat("en-US", { ...(metric === "spend" ? { style: "currency", currency: "USD" } : {}), ...(options.compact ? { notation: "compact", maximumFractionDigits: 1 } : { maximumFractionDigits: metric === "spend" ? 2 : 0 }) }).format(value);
}
export function formatExactUsd(value: string | null): string {
  if (value === null) return "Not available";
  if (!/^-?\d+(\.\d+)?$/.test(value)) throw new Error("Invalid exact USD value.");
  const [whole, fraction = ""] = value.replace(/^-/, "").split(".");
  return `${value.startsWith("-") ? "−" : ""}$${whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",")}.${fraction.padEnd(2, "0")}`;
}

type FixtureRecord = SpendingRecord & { inputTokens?: number; outputTokens?: number; cachedInputTokens?: number; reasoningTokens?: number; includedUsageNotional?: number };
const exactFixtureAmount = (value: number) => /e/i.test(String(value)) ? value.toFixed(8) : String(value);
function aggregateFixtureRows(rows: FixtureRecord[]): UsageAggregate {
  const costs = { reported: [] as string[], estimated: [] as string[], measured: [] as string[], simulated: [] as string[] };
  const included: string[] = [];
  for (const row of rows) {
    const provenance: string = row.provenance;
    const kind = ({ reported_charge: "reported", estimate: "estimated", measured: "measured", simulated: "simulated", usage_only: null } as const)[provenance as "reported_charge" | "estimate" | "measured" | "simulated" | "usage_only"];
    if (kind === undefined) throw new Error(`Unsupported usage provenance: ${provenance}`);
    if (row.component === "included_usage") included.push(exactFixtureAmount(row.includedUsageNotional ?? row.amount));
    else if (kind && row.unit === "usd" && String(row.component) !== "unpriced_usage") costs[kind].push(exactFixtureAmount(row.amount));
  }
  const tokenRows = rows.map(row => {
    const paired = row.inputTokens !== undefined && row.outputTokens !== undefined;
    const hasCategories = row.inputTokens !== undefined || row.outputTokens !== undefined;
    return { input: row.inputTokens ?? null, output: row.outputTokens ?? null, cachedInput: row.cachedInputTokens ?? null, reasoning: row.reasoningTokens ?? null, total: paired ? row.inputTokens! + row.outputTokens! : hasCategories ? null : row.tokens ?? null };
  });
  const tokens = Object.fromEntries(TOKEN_KEYS.map(key => [key, sumKnown(tokenRows.map(row => row[key]))])) as unknown as UsageTokens;
  if (tokenRows.some(row => row.total === null && (row.input !== null || row.output !== null))) tokens.total = null;
  const empty = rows.length ? "0.00" : null;
  const costsByValueKind = Object.fromEntries(VALUE_KINDS.map(kind => [kind, sumUsageMoney(costs[kind]) ?? empty])) as UsageCosts;
  return {
    recordedSpend: rows.length ? sumUsageMoney(Object.values(costsByValueKind)) : null, costsByValueKind,
    includedUsageNotional: sumUsageMoney(included) ?? empty, tokens, recordCount: rows.length,
    tokenObservedRecordCounts: Object.fromEntries(TOKEN_KEYS.map(key => [key, tokenRows.filter(row => row[key] !== null).length])),
  };
}
/** Adapter over the already-loaded synthetic ledger; it never invents a native input/output split. */
export function mockDailyUsage(records: FixtureRecord[], query: DailyUsageQuery, options: { asOf: string; datasetId: string }): DailyUsageResponse {
  const dates = usageDates(query.startDate, query.endDateExclusive);
  const asOfDate = options.asOf.slice(0, 10);
  const latest = [...new Map(records.map(row => [row.id, row])).values()];
  const scoped = latest.filter(row => row.date <= asOfDate &&
    (query.scopeType === "company" || query.scopeType === "team" && row.teamId === query.scopeId || query.scopeType === "person" && row.personId === query.scopeId || query.scopeType === "shared" && (query.scopeId ? row.teamId === query.scopeId && !row.personId : !row.teamId)) &&
    (!query.provider || row.provider === query.provider) && (!query.model || row.model === query.model));
  const availableDates = scoped.map(row => row.date).sort();
  const buckets: DailyUsageBucket[] = dates.map(date => {
    const rows = date <= asOfDate ? scoped.filter(row => row.date === date) : [];
    const groups = new Map<string, FixtureRecord[]>();
    for (const row of rows) { const key = JSON.stringify([row.provider, row.model ?? null]); groups.set(key, [...(groups.get(key) ?? []), row]); }
    return { date, ...aggregateFixtureRows(rows), coverage: date > asOfDate ? "future" : !rows.length ? "missing" : date === asOfDate || rows.some(row => !row.complete) ? "partial" : "complete",
      revision: `synthetic:${date}:${JSON.stringify([...rows].sort((a,b) => a.id.localeCompare(b.id))).split("").reduce((hash, char) => ((hash * 31) + char.charCodeAt(0)) | 0, 0)}`,
      breakdowns: [...groups.values()].map(group => ({ provider: group[0].provider, model: group[0].model ?? null, ...aggregateFixtureRows(group) })),
      sourceRefs: [...new Set(rows.map(row => row.source))],
    };
  });
  return { scope: { type: query.scopeType, id: query.scopeId }, startDate: query.startDate, endDateExclusive: query.endDateExclusive, timezone: "UTC", unit: "USD", datasetId: options.datasetId,
    datasetRevision: `synthetic:${options.asOf}`, synthetic: true, asOf: options.asOf, availableStartDate: availableDates[0] ?? null,
    availableEndDateExclusive: availableDates.length ? usageDateOffset(availableDates.at(-1)!, 1) : null, filters: { provider: query.provider, model: query.model }, buckets,
    sourceCoverage: [], notes: ["Synthetic demo ledger. Token totals are generated from fixture pricing; native input/output categories are unavailable unless explicitly supplied.", "Included usage is informational and excluded from spending. All dates use UTC."] };
}
