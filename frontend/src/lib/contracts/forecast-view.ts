/** Immutable publication contract. Forecast horizons are never inferred from the budget period. */
export type ForecastScope = { type: "company" | "team" | "person" | "shared"; id: string | null; name?: string };
export interface ForecastBand {
  status?: "available" | "unavailable";
  available?: boolean;
  low?: number | null;
  high?: number | null;
  reason?: string;
  label?: string;
  qualification?: string;
  sample_count?: number;
  [key: string]: unknown;
}
export interface HistoricalErrorEstimate {
  status: "available_assumption_conditional" | "insufficient_evidence";
  lower: number | null;
  upper: number | null;
  coverage?: number;
  n?: number;
  rank?: number;
  calibration_start?: string | null;
  calibration_end?: string | null;
  qualification?: string;
  is_synthetic?: boolean;
  [key: string]: unknown;
}
export type HistoricalErrorIntervals = Partial<Record<"80" | "95", HistoricalErrorEstimate>>;
export interface ForecastPoint {
  date?: string;
  start?: string;
  end?: string;
  period_start?: string;
  period_end?: string;
  base?: number | null;
  low?: number | null;
  high?: number | null;
  partial?: boolean;
  scenario_range?: ForecastBand | null;
  historical_error_interval?: HistoricalErrorIntervals | null;
  [key: string]: unknown;
}
export interface ForecastDriver {
  id: string;
  kind?: string;
  title?: string;
  source_id?: string;
  source_revision?: string | number;
  status?: string;
  reason?: string;
  scope?: unknown;
  effective_from?: string;
  effective_to?: string | null;
  parameters?: Record<string, unknown>;
  citations?: Array<Record<string, unknown>>;
  paired_effect?: Record<string, unknown>;
  [key: string]: unknown;
}
export interface ForecastView {
  schema_version?: string | number;
  run_id: string;
  id?: string;
  view_id?: string;
  procedure_id?: string;
  procedure_version?: string;
  scope: ForecastScope;
  target: { unit: string; quantity?: string; basis?: string; timezone?: string };
  generated_at?: string;
  publication?: Record<string, unknown>;
  information_cutoff?: string;
  evidence_cutoff?: string;
  forecast_start?: string;
  timezone?: string;
  components?: Record<string, unknown>;
  daily: ForecastPoint[];
  weekly: ForecastPoint[];
  cumulative: ForecastPoint[];
  quarter_outlook?: Record<string, unknown>;
  scenario_range?: ForecastBand | null;
  historical_error_interval?: HistoricalErrorIntervals | null;
  included_drivers: ForecastDriver[];
  driver_effects?: ForecastDriverEffect[];
  queued_changes: ForecastDriver[];
  limitations: string[];
  explanation_refs?: unknown;
  is_synthetic?: boolean;
  [key: string]: unknown;
}
export interface ForecastDriverEffect {
  scope?: ForecastScope;
  driver_id: string; base_delta: number | null; without_base: number | null; with_base: number | null; available: boolean; qualification?: string;
}
export interface ForecastBundle {
  driver_effects?: ForecastDriverEffect[];
  views: ForecastView[];
  current_actuals?: Record<string, unknown>;
  publication?: { run_id: string; sequence?: number; published_at?: string } | null;
  [key: string]: unknown;
}
export interface ForecastRefresh {
  id: string;
  status: string;
  run_id?: string;
  sequence?: number;
  error?: string;
  [key: string]: unknown;
}
export interface ForecastEvidence {
  id?: string;
  source_id?: string;
  source?: string;
  revision?: string | number;
  text?: string;
  drivers?: ForecastDriver[];
  [key: string]: unknown;
}

export interface ForecastQuestionContext {
  action: "explain";
  run_id: string;
  scope_type: ForecastScope["type"];
  scope_id: string | null;
  driver_id?: string;
}

export interface ForecastScenarioReceipt {
  scenario_id: string;
  parent_run_id: string;
  job_id: string;
  status: string;
  last_error?: string | null;
  views?: ForecastView[];
  is_scenario?: boolean;
}
export type ForecastScenarioResponse = ForecastBundle | ForecastScenarioReceipt;
