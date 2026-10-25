import type { Period, Provenance, SpendingRecord, Unit } from "@/lib/contracts";
import { billableAmount, sumMoney } from "@/lib/finance-summary";

const FINANCIAL_COMPONENTS = ["subscription", "extra_usage", "api"] as const;
export interface RecordedComponent {
  component: typeof FINANCIAL_COMPONENTS[number];
  amount: number | null;
  recordCount: number;
  provenances: Provenance[];
}
/** Exact selected target; row completeness is not a claim about whole-source coverage. */
export function selectCostComponents({ records, period, unit }: { records: SpendingRecord[]; period: Period; unit: Unit }) {
  const scoped = records.filter(row => row.date >= period.start && row.date <= period.end && row.unit === unit);
  const financial = scoped.filter(row => unit !== "tokens" && FINANCIAL_COMPONENTS.some(component => component === row.component) && row.provenance !== "usage_only");
  const known = financial.filter(row => Number.isFinite(row.amount));
  const components: RecordedComponent[] = FINANCIAL_COMPONENTS.map(component => {
    const rows = known.filter(row => row.component === component);
    return { component, amount: rows.length ? sumMoney(rows.map(billableAmount)) : null, recordCount: rows.length, provenances: [...new Set(rows.map(row => row.provenance))] };
  });
  const included = scoped.filter(row => row.component === "included_usage");
  const notionals = included.map(row => Number.isFinite(row.includedUsageNotional) ? row.includedUsageNotional! : Number.isFinite(row.amount) && row.amount !== 0 ? row.amount : null).filter((amount): amount is number => amount !== null);
  const total = known.length ? sumMoney(known.map(billableAmount)) : null;
  return {
    recordCount: scoped.length,
    components, total,
    canShowShares: total !== null && total > 0 && components.every(row => row.amount === null || row.amount >= 0),
    hasPartialRecords: scoped.some(row => !row.complete),
    invalidAmountCount: financial.length - known.length,
    included: { recordCount: included.length, notional: notionals.length ? sumMoney(notionals) : null },
    unpricedRecordCount: scoped.filter(row => row.component === "unpriced_usage" || row.provenance === "usage_only" && row.component !== "included_usage").length,
  };
}
