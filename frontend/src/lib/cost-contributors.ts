import type { Period, Provenance, SpendingRecord, Unit } from "./contracts";
import { billableAmount, sumMoney } from "./finance-summary";

type FinancialUnit = Exclude<Unit, "tokens">;

export interface CostContributor {
  key: string;
  provider?: string;
  model?: string;
  amount: number;
  /** Net share is unavailable when the eligible total is zero or negative. */
  share: number | null;
  byProvenance: Partial<Record<Provenance, number>>;
  recordCount: number;
  groupCount: number;
  sources: string[];
}

export interface CostContributorsResult {
  status: "available" | "no_records" | "no_financial_records" | "mixed_units" | "unavailable_amounts";
  unit: FinancialUnit | null;
  total: number | null;
  contributors: CostContributor[];
  other: CostContributor | null;
  /** Row completeness does not establish complete source or date coverage. */
  coverage: "unknown" | "partial" | "missing";
  invalidAmountCount: number;
}

/** A single provider/model partition: each eligible record belongs to exactly one row. */
export function selectCostContributors(input: {
  records: SpendingRecord[];
  period: Period;
  teamId?: string;
  personId?: string;
  unit?: FinancialUnit;
}): CostContributorsResult {
  const scoped = input.records.filter(row => row.date >= input.period.start && row.date <= input.period.end
    && (input.teamId === undefined || row.teamId === input.teamId)
    && (input.personId === undefined || row.personId === input.personId)
    && (input.unit === undefined || row.unit === input.unit));
  const financial = scoped.filter(row => row.component !== "included_usage" && row.component !== "unpriced_usage" && row.provenance !== "usage_only" && row.unit !== "tokens");
  const units = [...new Set(financial.map(row => row.unit as FinancialUnit))];
  const unit = input.unit ?? (units.length === 1 ? units[0] : null);
  const invalidAmountCount = financial.filter(row => !Number.isFinite(row.amount)).length;
  const empty: CostContributorsResult = {
    status: "no_records", unit, total: null, contributors: [], other: null,
    coverage: !scoped.length ? "missing" : invalidAmountCount || scoped.some(row => !row.complete) ? "partial" : "unknown",
    invalidAmountCount,
  };
  if (!scoped.length) return empty;
  if (!financial.length) return { ...empty, status: "no_financial_records" };
  if (units.length !== 1) return { ...empty, status: "mixed_units" };
  const rows = financial.filter(row => Number.isFinite(row.amount));
  if (!rows.length) return { ...empty, status: "unavailable_amounts" };

  const total = sumMoney(rows.map(billableAmount));
  const groups = new Map<string, SpendingRecord[]>();
  for (const row of rows) {
    const key = JSON.stringify([row.provider, row.model ?? null]);
    const group = groups.get(key) ?? [];
    group.push(row);
    groups.set(key, group);
  }
  function aggregate(key: string, records: SpendingRecord[], groupCount: number): CostContributor {
    const amount = sumMoney(records.map(billableAmount));
    const byProvenance: Partial<Record<Provenance, number>> = {};
    for (const provenance of new Set(records.map(row => row.provenance))) {
      byProvenance[provenance] = sumMoney(records.filter(row => row.provenance === provenance).map(billableAmount));
    }
    return {
      key, amount, share: total > 0 ? amount / total : null, byProvenance,
      recordCount: records.length, groupCount,
      sources: [...new Set(records.map(row => row.source).filter(Boolean))].sort(),
    };
  }
  const ranked = [...groups.entries()].map(([key, records]) => ({
    ...aggregate(key, records, 1), provider: records[0].provider, model: records[0].model,
  })).sort((a, b) => b.amount - a.amount || a.key.localeCompare(b.key));
  const tail = ranked.slice(5);
  const other = tail.length ? aggregate("other", tail.flatMap(row => groups.get(row.key) ?? []), tail.length) : null;
  return { ...empty, status: "available", total, contributors: ranked.slice(0, 5), other };
}
