import type { ForecastScope } from "./forecast-view";

/** Monday-based full weeks, with the exclusive end boundary preserved over the wire. */
export interface WeeklyHistoryQuery {
  scopeType: ForecastScope["type"];
  scopeId?: string;
  startDate: string;
  endDateExclusive: string;
}
export interface WeeklyIssuedForecast {
  amount: string;
  runId: string;
  targetId: string;
  datasetId: string;
  issuedAt: string;
  informationCutoff: string;
  start: string;
  endExclusive: string;
}
export interface WeeklyOutlook {
  amount: string;
  runId: string;
  datasetId: string;
  issuedAt: string;
  informationCutoff: string;
  start: string;
  endExclusive: string;
  /** True means this is only the supplied remainder window, not a full-week forecast. */
  partial: boolean;
}
export interface WeeklyActual {
  amount: string | null;
  status: "mature" | "partial" | "missing" | "pending" | "disputed" | "future";
  source: "observed_outcome" | "repository_ledger" | "none";
  datasetId: string | null;
  revision: string | null;
  corrected: boolean;
  sourceRefs: string[];
}
export interface WeeklyHistoryWeek {
  start: string;
  endExclusive: string;
  state: "closed" | "current" | "future";
  actual: WeeklyActual;
  priorForecast: WeeklyIssuedForecast | null;
  outlook: WeeklyOutlook | null;
  /** Positive means actual spend exceeded the prior issued forecast. Only exact mature outcomes qualify. */
  variance: { amount: string | null; status: "available" | "unavailable"; reason: string | null };
}
export interface WeeklyHistoryResponse {
  scope: ForecastScope;
  startDate: string;
  endDateExclusive: string;
  timezone: "UTC";
  unit: "USD";
  basis: "planning";
  quantity: "spend";
  /** Aggregation response identity; compare actual.datasetId with priorForecast.datasetId, not this field. */
  datasetId: string;
  asOf: string;
  synthetic: boolean;
  actualsRevision: string;
  selectionPolicy: "latest_published_before_week_start";
  weeks: WeeklyHistoryWeek[];
  notes: string[];
}
