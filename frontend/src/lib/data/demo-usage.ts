import type { Dataset } from "@/fixtures/generate";
import type { SpendingRecord } from "../contracts";
import type { DailyUsageQuery, DailyUsageResponse } from "../contracts/usage";
import { mockDailyUsage, normalizeUsageScope, usageDates } from "../usage-derive";
import { loadDemoSnapshot } from "./demo-snapshot";

type UsageSnapshot = { dataset: Pick<Dataset, "company" | "spending">; asOf: string };
const tokenFields = ["inputTokens", "outputTokens", "cachedInputTokens", "reasoningTokens", "tokens"] as const;

/** Saved compatibility rows retain their own values; no live source coverage is inferred. */
export function demoUsageFromSnapshot(snapshot: UsageSnapshot, query: DailyUsageQuery): DailyUsageResponse {
  if (!Number.isFinite(Date.parse(snapshot.asOf))) throw new Error("The saved usage date is unavailable.");
  usageDates(query.startDate, query.endDateExclusive);
  const scope = normalizeUsageScope({ type: query.scopeType, id: query.scopeId });
  if ((scope.type === "team" || scope.type === "person") && !scope.id) throw new Error("Choose a team or person.");
  const normalizedQuery = { ...query, scopeType: scope.type, scopeId: scope.id ?? undefined };
  const records = snapshot.dataset.spending.map(row => {
    const record: SpendingRecord = { ...row, teamId: row.teamId === "unattributed" ? "" : row.teamId };
    for (const key of tokenFields) if (record[key] == null) delete record[key];
    return record;
  });
  const result = mockDailyUsage(records, normalizedQuery, { asOf: snapshot.asOf, datasetId: snapshot.dataset.company.id });
  const unknownNotional = records.filter(row => row.component === "included_usage" && row.includedUsageNotional == null &&
    (scope.type === "company" || scope.type === "team" && row.teamId === scope.id || scope.type === "person" && row.personId === scope.id || scope.type === "shared" && (scope.id ? row.teamId === scope.id && !row.personId : !row.teamId)) &&
    (!query.provider || row.provider === query.provider) && (!query.model || row.model === query.model));
  const unknownDates = new Set(unknownNotional.map(row => row.date));
  const unknownGroups = new Set(unknownNotional.map(row => JSON.stringify([row.date, row.provider, row.model ?? null])));
  return {
    ...result,
    buckets: result.buckets.map(bucket => ({
      ...bucket, coverage: bucket.coverage === "complete" ? "partial" : bucket.coverage,
      includedUsageNotional: unknownDates.has(bucket.date) ? null : bucket.includedUsageNotional,
      breakdowns: bucket.breakdowns.map(row => ({ ...row, includedUsageNotional: unknownGroups.has(JSON.stringify([bucket.date, row.provider, row.model])) ? null : row.includedUsageNotional })),
    })),
    notes: [
      "Saved spending snapshot. Record counts refer to exported aggregate rows, not individual source events.",
      "Native source completion receipts are unavailable in this snapshot; days with recorded usage have partial coverage.",
      "Token values reflect only the categories supplied in the saved records. Missing values remain unknown.",
      "Included usage is informational and excluded from spending. All dates use UTC.",
    ],
  };
}

export async function fetchDemoUsage(query: DailyUsageQuery, signal?: AbortSignal): Promise<DailyUsageResponse> {
  signal?.throwIfAborted();
  const snapshot = await loadDemoSnapshot();
  signal?.throwIfAborted();
  return demoUsageFromSnapshot(snapshot, query);
}
