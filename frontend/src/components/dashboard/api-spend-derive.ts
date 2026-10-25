import type { Period, Provenance, SpendingRecord, Unit } from "@/lib/contracts";
import { sumMoney } from "@/lib/finance-summary";

export interface ApiSpendGroup {
  key: string;
  provider?: string;
  model?: string;
  amount: number;
  /** Null if any financial row lacks a usable token count. */
  tokens: number | null;
  /** The reported subset; never presented as a complete token total. */
  reportedTokens: number | null;
  missingTokenCount: number;
  recordCount: number;
  share: number | null;
  byProvenance: Partial<Record<Provenance, number>>;
}

export interface ApiSpendResult {
  status: "available" | "no_records" | "no_financial_records" | "unavailable_amounts";
  total: number | null;
  tokens: number | null;
  reportedTokens: number | null;
  missingTokenCount: number;
  recordCount: number;
  unpricedRecordCount: number;
  invalidAmountCount: number;
  coverage: "partial" | "unknown" | "missing";
  hasRefunds: boolean;
  models: ApiSpendGroup[];
  providers: ApiSpendGroup[];
}

const attribution = (value: string | undefined) => value?.trim() || undefined;
const hasTokens = (row: SpendingRecord) => typeof row.tokens === "number" && Number.isFinite(row.tokens) && row.tokens >= 0;

function tokenTotals(rows: SpendingRecord[]) {
  const reported = rows.filter(hasTokens);
  const missingTokenCount = rows.length - reported.length;
  const reportedTokens = reported.length ? reported.reduce((sum, row) => sum + row.tokens!, 0) : null;
  return { tokens: missingTokenCount ? null : reportedTokens, reportedTokens, missingTokenCount };
}

/** Every eligible charge belongs to one provider and one provider/model partition. */
export function selectApiSpend(input: { records: SpendingRecord[]; period: Period; unit: Unit }): ApiSpendResult {
  const scoped = input.records.filter(row => row.date >= input.period.start && row.date <= input.period.end && row.unit === input.unit);
  const candidates = scoped.filter(row => row.component === "api" && row.provenance !== "usage_only" && row.unit !== "tokens");
  const rows = candidates.filter(row => Number.isFinite(row.amount));
  const unpriced = scoped.filter(row => row.component === "unpriced_usage" || row.component === "api" && row.provenance === "usage_only");
  const invalidAmountCount = candidates.length - rows.length;
  const empty: ApiSpendResult = {
    status: "no_records", total: null, tokens: null, reportedTokens: null, missingTokenCount: 0,
    recordCount: 0, unpricedRecordCount: unpriced.length, invalidAmountCount,
    // Complete rows do not establish complete source or date coverage.
    coverage: invalidAmountCount || [...candidates, ...unpriced].some(row => !row.complete) ? "partial" : rows.length ? "unknown" : "missing",
    hasRefunds: false, models: [], providers: [],
  };
  if (!scoped.length) return empty;
  if (!candidates.length) return { ...empty, status: "no_financial_records" };
  if (!rows.length) return { ...empty, status: "unavailable_amounts" };

  const total = sumMoney(rows.map(row => row.amount));
  const modelGroups = new Map<string, SpendingRecord[]>();
  const providerGroups = new Map<string, SpendingRecord[]>();
  for (const row of rows) {
    const providerKey = JSON.stringify([attribution(row.provider) ?? null]);
    const modelKey = JSON.stringify([attribution(row.provider) ?? null, attribution(row.model) ?? null]);
    const providerRows = providerGroups.get(providerKey) ?? [];
    const modelRows = modelGroups.get(modelKey) ?? [];
    providerRows.push(row);
    modelRows.push(row);
    providerGroups.set(providerKey, providerRows);
    modelGroups.set(modelKey, modelRows);
  }
  const aggregate = (key: string, records: SpendingRecord[]): ApiSpendGroup => {
    const amount = sumMoney(records.map(row => row.amount));
    const byProvenance: Partial<Record<Provenance, number>> = {};
    for (const provenance of new Set(records.map(row => row.provenance))) {
      byProvenance[provenance] = sumMoney(records.filter(row => row.provenance === provenance).map(row => row.amount));
    }
    return { key, provider: attribution(records[0].provider), amount, ...tokenTotals(records), recordCount: records.length, share: total > 0 ? amount / total : null, byProvenance };
  };
  const rank = (a: ApiSpendGroup, b: ApiSpendGroup) => b.amount - a.amount || a.key.localeCompare(b.key);
  return {
    ...empty, status: "available", total, ...tokenTotals(rows), recordCount: rows.length,
    hasRefunds: rows.some(row => row.amount < 0),
    models: [...modelGroups].map(([key, records]) => ({ ...aggregate(key, records), model: attribution(records[0].model) })).sort(rank),
    providers: [...providerGroups].map(([key, records]) => aggregate(key, records)).sort(rank),
  };
}
