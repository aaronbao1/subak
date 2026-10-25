/** Daily observed usage. Exact USD strings stay exact until display/chart conversion. */
export type UsageValueKind = "reported" | "estimated" | "measured" | "simulated";
export type UsageCoverage = "complete" | "partial" | "missing" | "unknown" | "future";
export type UsageMetric = "spend" | "tokens";
export type UsageScope = { type: "company" | "team" | "person" | "shared"; id?: string | null };
export type UsageCosts = Record<UsageValueKind, string | null>;
export interface UsageTokens {
  input: number | null;
  cachedInput: number | null;
  output: number | null;
  reasoning: number | null;
  /** Native total = input + output. Cache and reasoning are subsets, never additions. */
  total: number | null;
}
export interface UsageAggregate {
  recordedSpend: string | null;
  costsByValueKind: UsageCosts;
  includedUsageNotional: string | null;
  tokens: UsageTokens;
  recordCount: number;
  tokenObservedRecordCounts?: Partial<Record<keyof UsageTokens, number>>;
}
export interface UsageBreakdown extends UsageAggregate {
  provider: string | null;
  model: string | null;
  tool?: string | null;
}
export interface DailyUsageBucket extends UsageAggregate {
  date: string;
  coverage: UsageCoverage;
  revision: string;
  breakdowns: UsageBreakdown[];
  sourceRefs: string[];
}
export interface DailyUsageResponse {
  scope: UsageScope;
  startDate: string;
  endDateExclusive: string;
  timezone: "UTC";
  unit: "USD";
  datasetId: string;
  datasetRevision: string;
  synthetic: boolean;
  asOf: string;
  availableStartDate: string | null;
  availableEndDateExclusive: string | null;
  filters: { provider?: string | null; model?: string | null };
  buckets: DailyUsageBucket[];
  sourceCoverage: Array<{ sourceKind: string; sourceAccount: string | null; recordCount: number; coverage: UsageCoverage; lastRecordAt: string | null }>;
  notes: string[];
}
export interface DailyUsageQuery {
  scopeType: UsageScope["type"];
  scopeId?: string;
  startDate: string;
  endDateExclusive: string;
  provider?: string;
  model?: string;
}
