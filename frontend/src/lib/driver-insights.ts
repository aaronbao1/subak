import type { ForecastDriver, ForecastDriverEffect, ForecastEvidence, ForecastQuestionContext, ForecastScope, ForecastView } from "./contracts/forecast-view";

export type DriverInsightStatus = "modeled" | "included" | "queued" | "context" | "unknown_scope";
export interface DriverInsight {
  driver: ForecastDriver;
  title: string;
  status: DriverInsightStatus;
  delta: number | null;
  effect?: ForecastDriverEffect;
  reason: string;
  sourceSummary: string;
  runId: string;
  scope: ForecastScope;
  target: ForecastView["target"];
  horizon: { kind: "quarter"; start: string | null; end: string | null };
  /** Only immutable publication members can be explained as part of that run. */
  inSnapshot: boolean;
}

const finite = (value: unknown): value is number => typeof value === "number" && Number.isFinite(value);
const record = (value: unknown): Record<string, unknown> | undefined => value !== null && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : undefined;
const nonempty = (value: unknown): string | undefined => typeof value === "string" && value.trim() ? value : undefined;
const businessTitles: Record<string, string> = { project_schedule: "Project timing", membership: "Team assignment", workload: "Planned workload", adoption: "Model adoption", pricing: "Pricing update" };
const contextOnly = (driver: ForecastDriver): boolean => driver.status === "context_only" || driver.queue_status === "context_only";
const sameScope = (left: ForecastScope | undefined, right: ForecastScope): boolean => !!left && left.type === right.type && (left.id ?? null) === (right.id ?? null);

/** An explicit scoped publication effect is sufficient evidence of a cross-team influence.
 * Incoming source mentions require their own scope; an absent scope is not company-wide. */
function applicability(driver: ForecastDriver, scope: ForecastScope): "relevant" | "unrelated" | "unknown" {
  const mapped = driver.affected_scopes ?? driver.applicable_scopes;
  if (Array.isArray(mapped) && mapped.length) {
    const known = mapped.map(record).filter((item): item is Record<string, unknown> => !!item);
    return known.some(item => item.type === scope.type && item.id === scope.id) || scope.type === "company" && known.length > 0 ? "relevant" : "unrelated";
  }
  const source = record(driver.scope);
  if (!source || Object.keys(source).length === 0) return "unknown";
  if (scope.type === "company") return "relevant";
  if (source.type === scope.type) return source.id === scope.id ? "relevant" : "unrelated";
  const key = `${scope.type}_id`;
  if (typeof source[key] === "string") return source[key] === scope.id ? "relevant" : "unrelated";
  const ids = source[`${scope.type}_ids`];
  if (Array.isArray(ids)) return ids.includes(scope.id) ? "relevant" : "unrelated";
  return "unknown";
}

function effectFor(view: ForecastView, driverId: string): ForecastDriverEffect | undefined {
  const quarter = view.quarter_outlook;
  if (!finite(quarter?.base) || !nonempty(quarter?.start) || !nonempty(quarter?.end)) return undefined;
  const matching = (view.driver_effects ?? []).filter(effect => {
    if (effect.driver_id !== driverId || !sameScope(effect.scope, view.scope)) return false;
    if (effect.run_id !== undefined && effect.run_id !== view.run_id) return false;
    if (effect.target && Object.entries(effect.target).some(([key, value]) => value !== undefined && view.target[key as keyof ForecastView["target"]] !== value)) return false;
    return !effect.horizon || effect.horizon.kind === "quarter" && effect.horizon.start === quarter.start && effect.horizon.end === quarter.end;
  });
  const first = matching[0];
  if (!first || !first.available || !finite(first.base_delta) || !finite(first.with_base) || !finite(first.without_base) || first.with_base !== quarter.base) return undefined;
  // Repeated copies are harmless; conflicting records have no authoritative choice.
  if (matching.some(effect => effect.available !== first.available || effect.base_delta !== first.base_delta || effect.with_base !== first.with_base || effect.without_base !== first.without_base)) return undefined;
  return first;
}

/** Rank individual, non-additive quarter comparisons from one immutable view.
 * No bundle fallback, current evidence paired_effect, extrapolation or sum is permitted. */
export function rankForecastInsights({ view, evidence = [], limit }: { view: ForecastView; evidence?: ForecastEvidence[]; limit?: number }): DriverInsight[] {
  const candidates = new Map<string, { driver: ForecastDriver; status: "included" | "queued" | "context"; inSnapshot: boolean }>();
  for (const driver of view.included_drivers) if (!candidates.has(driver.id)) candidates.set(driver.id, { driver, status: contextOnly(driver) ? "context" : "included", inSnapshot: true });
  for (const driver of view.queued_changes) if (!candidates.has(driver.id)) candidates.set(driver.id, { driver, status: contextOnly(driver) ? "context" : "queued", inSnapshot: true });
  for (const item of evidence) {
    if (item.run_id !== undefined && item.run_id !== view.run_id) continue;
    for (const sourceDriver of item.drivers ?? []) {
      if (sourceDriver.run_id !== undefined && sourceDriver.run_id !== view.run_id || candidates.has(sourceDriver.id)) continue;
      const driver = sourceDriver.scope === undefined && item.scope !== undefined ? { ...sourceDriver, scope: item.scope } : sourceDriver;
      const queued = driver.queue_status === "queued" && !contextOnly(driver);
      candidates.set(driver.id, { driver, status: queued ? "queued" : "context", inSnapshot: false });
    }
  }
  const insights: DriverInsight[] = [];
  for (const { driver, status, inSnapshot } of candidates.values()) {
    const effect = status === "included" ? effectFor(view, driver.id) : undefined;
    const match = applicability(driver, view.scope);
    // Inclusion belongs to the scoped snapshot, including supplied indirect effects.
    if (status !== "included" && match === "unrelated") continue;
    const insightStatus = effect ? "modeled" : status !== "included" && match === "unknown" ? "unknown_scope" : status;
    const title = nonempty(driver.title) ?? nonempty(driver.event_title) ?? (driver.kind ? businessTitles[driver.kind] ?? driver.kind.replaceAll("_", " ") : "Forecast assumption");
    const citation = driver.citations?.[0];
    insights.push({ driver, title, status: insightStatus, delta: effect?.base_delta ?? null, effect,
      reason: nonempty(driver.publication_reason) ?? nonempty(driver.reason) ?? (effect ? "Difference with this assumption compared with omitting it." : insightStatus === "included" ? "Included in this forecast; a matching quarter comparison is unavailable." : insightStatus === "queued" ? "Received after publication; waiting for a forecast update." : insightStatus === "unknown_scope" ? "Scope has not been established for this source." : "Source context; no modeled financial effect is supplied."),
      sourceSummary: nonempty(citation?.title) ?? nonempty(driver.source_summary) ?? (nonempty(citation?.quote) ?? nonempty(citation?.excerpt) ?? "Source details").slice(0, 160),
      runId: view.run_id, scope: { ...view.scope, id: view.scope.id ?? null }, target: { ...view.target },
      horizon: { kind: "quarter", start: nonempty(view.quarter_outlook?.start) ?? null, end: nonempty(view.quarter_outlook?.end) ?? null }, inSnapshot,
    });
  }
  const priority: Record<DriverInsightStatus, number> = { modeled: 0, included: 1, queued: 2, context: 3, unknown_scope: 4 };
  insights.sort((left, right) => priority[left.status] - priority[right.status] || (left.status === "modeled" && right.status === "modeled" ? Math.abs(right.delta!) - Math.abs(left.delta!) : 0) || left.title.localeCompare(right.title) || left.driver.id.localeCompare(right.driver.id));
  return limit === undefined ? insights : insights.slice(0, Math.max(0, limit));
}

export function driverQuestion(insight: DriverInsight): { prompt: string; context: ForecastQuestionContext } {
  return {
    prompt: `Explain “${insight.title}” in the issued ${insight.scope.name ?? insight.scope.type} forecast for ${insight.horizon.start ?? "unknown start"} to ${insight.horizon.end ?? "unknown end"} (end exclusive). Use that issued publication, cite its source passages and assumptions, and explain the modeled omission comparison without treating it as a causal effect or realized savings. Do not substitute a newer run.`,
    context: { action: "explain", run_id: insight.runId, scope_type: insight.scope.type, scope_id: insight.scope.id ?? null, driver_id: insight.driver.id },
  };
}
