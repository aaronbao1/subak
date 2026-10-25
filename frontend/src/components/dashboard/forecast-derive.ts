import type { ForecastBand, ForecastBundle, ForecastDriver, ForecastPoint, ForecastView } from "../../lib/contracts/forecast-view";

export function finite(value: unknown): number | undefined {
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}
export function pointBase(point: ForecastPoint | Record<string, unknown> | undefined): number | undefined { return finite(point?.base); }
export function scopeView(bundle: ForecastBundle | undefined, type: string, id?: string): ForecastView | undefined {
  return bundle?.views.find(v => v.scope.type === type && (!id || v.scope.id === id));
}
export function rangeStatus(band: ForecastBand | null | undefined, fallback: string): string {
  if (!band || band.status === "unavailable") return band?.reason ?? fallback;
  return [band.label, band.qualification].filter(Boolean).join(" · ") || fallback;
}
export function pointRange(point: ForecastPoint): [number, number] | undefined {
  const low = finite(point.low), high = finite(point.high);
  return low !== undefined && high !== undefined ? [low, high] : undefined;
}
export function forecastPrompt(view: ForecastView, driver?: ForecastDriver): string {
  return `Explain the issued forecast run_id=${view.run_id}, scope_type=${view.scope.type}, scope_id=${view.scope.id ?? "shared"}${driver ? `, driver_id=${driver.id}` : ""}. Cite the source passages, effective dates, numerical assumptions, paired omission effect and unavailable uncertainty. Do not substitute a newer run.`;
}
/** Only exact source-linked driver identifiers count as inclusion. */
export function evidenceDrivers(view: ForecastView, evidence: Array<{ drivers?: ForecastDriver[] }>): Array<{ driver: ForecastDriver; status: "Included" | "Queued" | "Context only" }> {
  const included = new Set(view.included_drivers.map(d => d.id));
  const queued = new Set(view.queued_changes.map(d => d.id));
  const all = new Map<string, ForecastDriver>();
  for (const d of [...view.included_drivers, ...view.queued_changes, ...evidence.flatMap(e => e.drivers ?? [])]) if (!all.has(d.id)) all.set(d.id, d);
  return [...all.values()].map(driver => ({ driver, status: included.has(driver.id) ? "Included" : queued.has(driver.id) || driver.queue_status === "queued" ? "Queued" : "Context only" }));
}

/** Compatibility surfaces receive the full conditional quarter, never a four-week subtotal. */
export function quarterForecasts(bundle: ForecastBundle): import("../../lib/contracts").Forecast[] {
  return bundle.views.filter(v=>v.scope.type === "team" || v.scope.type === "person").map(view=>{
    const q = view.quarter_outlook;
    const base = finite(q?.base);
    const endExclusive = typeof q?.end === "string" ? q.end : "";
    const end = endExclusive ? new Date(Date.parse(`${endExclusive}T00:00:00Z`)-86400000).toISOString().slice(0,10) : "";
    return { id:view.id ?? `${view.run_id}:${view.scope.type}:${view.scope.id}`,teamId:view.scope.type === "team" ? view.scope.id ?? "shared" : "",...(view.scope.type === "person" ? {personId:view.scope.id ?? "shared"} : {}),period:{start:typeof q?.start === "string" ? q.start : "",end,label:"Conditional quarter outlook"},status:base===undefined ? "unavailable" as const : "available" as const,basis:"full_period" as const,kind:"forecast" as const,origin:view.is_synthetic ? "placeholder" as const : "forecasting_service" as const,projected:base,unit:view.target.unit.toLowerCase() as "usd" | "credits" | "tokens",assumptions:["Conditional quarter continuation; see issued scenario envelope and limitations.",...(Array.isArray(q?.assumptions)?q.assumptions.map(String):[])],limitations:view.limitations,generatedAt:String(view.publication?.generated_at ?? view.generated_at ?? ""),unavailableReason:base===undefined ? "Quarter continuation unavailable; see issued publication limitations." : undefined };
  });
}

export function historicalRange(point: ForecastPoint, level: "80" | "95" = "80"): [number, number] | undefined {
  const estimate = point.historical_error_interval?.[level];
  const low = finite(estimate?.lower), high = finite(estimate?.upper);
  return estimate?.status === "available_assumption_conditional" && low !== undefined && high !== undefined ? [low, high] : undefined;
}

export function sumPointBases(points: ForecastPoint[]): number | undefined {
  return points.length && points.every(p => pointBase(p) !== undefined) ? points.reduce((sum, p) => sum + (pointBase(p) ?? 0), 0) : undefined;
}

/** Scenario API replaces the global driver set, even when launched from a scoped view. */
export function omissionDrivers(bundle: ForecastBundle | undefined, issued: ForecastView, driverId: string): ForecastDriver[] {
  const company = bundle?.views.find(v => v.scope.type === "company" && v.run_id === issued.run_id);
  if (!company) throw new Error("The same-run company driver set is unavailable. Reload the publication before previewing.");
  if (!company.included_drivers.some(d => d.id === driverId)) throw new Error("This driver is not included in the issued company publication.");
  return company.included_drivers.filter(d => d.id !== driverId);
}

export function selectedDriverForView(selection: { driver: ForecastDriver; runId: string; scopeType: string; scopeId: string | null } | undefined, issued: ForecastView | undefined): ForecastDriver | undefined {
  return selection && issued && selection.runId === issued.run_id && selection.scopeType === issued.scope.type && selection.scopeId === issued.scope.id ? selection.driver : undefined;
}
