import type { Period } from "./contracts";
/** Drill-down links preserve the financial selection, converting inclusive planning dates to usage's half-open range. */
export function usageActivityHref(scope: { type: "company" | "team" | "person" | "shared"; id?: string }, period?: Period, metric: "spend" | "tokens" = "spend"): string {
  const params = new URLSearchParams({ scope_type: scope.type, metric });
  if (scope.id) params.set("scope_id", scope.id);
  if (period) {
    params.set("start_date", period.start);
    params.set("end_date_exclusive", new Date(Date.parse(`${period.end}T00:00:00Z`) + 86_400_000).toISOString().slice(0, 10));
  }
  return `/usage?${params}`;
}
