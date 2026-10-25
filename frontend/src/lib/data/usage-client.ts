import type { DailyUsageBucket, DailyUsageQuery, DailyUsageResponse, UsageAggregate, UsageCosts, UsageCoverage, UsageTokens } from "../contracts/usage";

type WireTokens = { input_tokens: number | null; cached_input_tokens: number | null; output_tokens: number | null; reasoning_tokens: number | null; total_tokens: number | null };
type WireAggregate = { recorded_spend: string | null; costs_by_value_kind: UsageCosts; included_usage_notional: string | null; tokens: WireTokens; record_count: number; token_observed_record_counts?: Partial<Record<keyof WireTokens, number>> };
export interface DailyUsageWireResponse {
  scope: DailyUsageResponse["scope"]; start_date: string; end_date_exclusive: string; timezone: "UTC"; unit: "USD";
  dataset_id: string; dataset_revision: string; synthetic: boolean; as_of: string; available_start_date: string | null; available_end_date_exclusive: string | null;
  filters: DailyUsageResponse["filters"];
  buckets: Array<WireAggregate & { date: string; coverage: UsageCoverage; revision: string; source_refs: string[]; breakdowns: Array<WireAggregate & { provider: string | null; model: string | null; tool?: string | null }> }>;
  source_coverage: Array<{ source_kind: string; source_account: string | null; record_count: number; coverage: UsageCoverage; last_record_at: string | null }>;
  notes: string[];
}
const tokenFields = { input: "input_tokens", cachedInput: "cached_input_tokens", output: "output_tokens", reasoning: "reasoning_tokens", total: "total_tokens" } as const;
function adaptAggregate(row: WireAggregate): UsageAggregate {
  const keys = Object.keys(row.costs_by_value_kind).sort();
  if (keys.join(",") !== "estimated,measured,reported,simulated") throw new Error("Unsupported usage cost value kind.");
  const monetaryValues = [row.recorded_spend, row.included_usage_notional, ...Object.values(row.costs_by_value_kind)];
  if (monetaryValues.some(value => value !== null && (typeof value !== "string" || !/^-?\d+(\.\d+)?$/.test(value)))) throw new Error("Usage costs must be exact decimal strings.");
  return { recordedSpend: row.recorded_spend, costsByValueKind: { ...row.costs_by_value_kind }, includedUsageNotional: row.included_usage_notional,
    tokens: Object.fromEntries(Object.entries(tokenFields).map(([key, field]) => [key, row.tokens[field]])) as unknown as UsageTokens,
    recordCount: row.record_count,
    tokenObservedRecordCounts: Object.fromEntries(Object.entries(tokenFields).map(([key, field]) => [key, row.token_observed_record_counts?.[field] ?? 0])),
  };
}
/** Explicit adapter: native wire names never leak into the view model. */
export function adaptDailyUsage(response: DailyUsageWireResponse): DailyUsageResponse {
  if (response.timezone !== "UTC" || response.unit !== "USD") throw new Error("Unsupported usage timezone or currency.");
  const buckets: DailyUsageBucket[] = response.buckets.map(bucket => ({ ...adaptAggregate(bucket), date: bucket.date, coverage: bucket.coverage,
    revision: bucket.revision, sourceRefs: bucket.source_refs, breakdowns: bucket.breakdowns.map(row => ({ ...adaptAggregate(row), provider: row.provider, model: row.model, tool: row.tool })) }));
  return { scope: response.scope, startDate: response.start_date, endDateExclusive: response.end_date_exclusive, timezone: response.timezone, unit: response.unit,
    datasetId: response.dataset_id, datasetRevision: response.dataset_revision, synthetic: response.synthetic, asOf: response.as_of,
    availableStartDate: response.available_start_date, availableEndDateExclusive: response.available_end_date_exclusive, filters: response.filters, buckets,
    sourceCoverage: response.source_coverage.map(source => ({ sourceKind: source.source_kind, sourceAccount: source.source_account, recordCount: source.record_count, coverage: source.coverage, lastRecordAt: source.last_record_at })), notes: response.notes };
}
export async function fetchDailyUsage(baseUrl: string, query: DailyUsageQuery, signal?: AbortSignal): Promise<DailyUsageResponse> {
  const days = (Date.parse(`${query.endDateExclusive}T00:00:00Z`) - Date.parse(`${query.startDate}T00:00:00Z`)) / 86_400_000;
  if (!Number.isInteger(days) || days < 1 || days > 366) throw new Error("Choose a date range between 1 and 366 days.");
  const params = new URLSearchParams({ scope_type: query.scopeType, start_date: query.startDate, end_date_exclusive: query.endDateExclusive });
  if (query.scopeId) params.set("scope_id", query.scopeId);
  if (query.provider) params.set("provider", query.provider);
  if (query.model) params.set("model", query.model);
  const response = await fetch(`${baseUrl.replace(/\/$/, "")}/api/usage/daily?${params}`, { cache: "no-store", signal });
  if (!response.ok) throw new Error(`Usage could not be loaded (${response.status}).`);
  return adaptDailyUsage(await response.json());
}
