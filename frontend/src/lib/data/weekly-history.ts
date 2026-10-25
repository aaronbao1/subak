import type { ForecastScope } from "../contracts/forecast-view";
import type { WeeklyActual, WeeklyHistoryQuery, WeeklyHistoryResponse, WeeklyHistoryWeek } from "../contracts/weekly-history";

type WireIssued = { amount: string; run_id: string; target_id: string; dataset_id: string; issued_at: string; information_cutoff: string; start: string; end_exclusive: string };
type WireOutlook = Omit<WireIssued, "target_id"> & { partial: boolean };
export interface WeeklyHistoryWireResponse {
  scope: ForecastScope; start_date: string; end_date_exclusive: string; timezone: "UTC"; unit: "USD"; basis: "planning"; quantity: "spend";
  dataset_id: string; as_of: string; synthetic: boolean; actuals_revision: string; selection_policy: "latest_published_before_week_start"; notes: string[];
  weeks: Array<{ start: string; end_exclusive: string; state: WeeklyHistoryWeek["state"];
    actual: { amount: string | null; status: WeeklyActual["status"]; source: WeeklyActual["source"]; dataset_id: string | null; revision: string | null; corrected: boolean; source_refs: string[] };
    prior_forecast: WireIssued | null; outlook: WireOutlook | null; variance: WeeklyHistoryWeek["variance"] }>;
}
const DAY = 86_400_000;
function dateValue(value: string): number {
  const parsed = Date.parse(`${value}T00:00:00Z`);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value) || !Number.isFinite(parsed) || new Date(parsed).toISOString().slice(0, 10) !== value) throw new Error("Weekly history needs valid ISO dates.");
  return parsed;
}
function requireMoney(value: string | null) {
  if (value !== null && (typeof value !== "string" || !/^-?\d+(?:\.\d+)?$/.test(value))) throw new Error("Weekly money must remain an exact decimal string.");
}
function requireIssue(issued: WireIssued | WireOutlook, asOf: string) {
  const issuedAt = Date.parse(issued.issued_at), cutoff = Date.parse(issued.information_cutoff);
  if (!Number.isFinite(issuedAt) || !Number.isFinite(cutoff) || cutoff > issuedAt || issuedAt > Date.parse(asOf)) throw new Error("Forecast issue and information cutoff must precede this view.");
  requireMoney(issued.amount);
}
export function validateWeeklyHistoryQuery(query: WeeklyHistoryQuery): void {
  const start = dateValue(query.startDate), end = dateValue(query.endDateExclusive);
  const weeks = (end - start) / (7 * DAY);
  if (!Number.isInteger(weeks) || weeks < 1 || weeks > 26 || new Date(start).getUTCDay() !== 1 || new Date(end).getUTCDay() !== 1) throw new Error("Choose between 1 and 26 full Monday–Sunday weeks.");
  if (!["company", "team", "person", "shared"].includes(query.scopeType) || query.scopeType !== "company" && !query.scopeId?.trim()) throw new Error("Choose an identified weekly history scope.");
}
/** The clock is explicit; the demo never silently slides to the computer's current week. */
export function defaultWeeklyHistoryQuery(asOf: string, scope: ForecastScope, pastWeeks = 4, futureWeeks = 3): WeeklyHistoryQuery {
  const date = Date.parse(asOf);
  if (!Number.isFinite(date) || !Number.isInteger(pastWeeks) || !Number.isInteger(futureWeeks) || pastWeeks < 0 || futureWeeks < 0) throw new Error("Choose a valid weekly history window.");
  const midnight = dateValue(new Date(date).toISOString().slice(0, 10));
  const monday = midnight - ((new Date(midnight).getUTCDay() + 6) % 7) * DAY;
  const query = { scopeType: scope.type, ...(scope.id ? { scopeId: scope.id } : {}), startDate: new Date(monday - pastWeeks * 7 * DAY).toISOString().slice(0, 10), endDateExclusive: new Date(monday + (futureWeeks + 1) * 7 * DAY).toISOString().slice(0, 10) };
  validateWeeklyHistoryQuery(query);
  return query;
}
/** Preserve exact values and identities; reject an incoherent comparison instead of manufacturing a delta. */
export function adaptWeeklyHistory(response: WeeklyHistoryWireResponse, query?: WeeklyHistoryQuery): WeeklyHistoryResponse {
  const responseQuery = { scopeType: response.scope.type, ...(response.scope.id ? { scopeId: response.scope.id } : {}), startDate: response.start_date, endDateExclusive: response.end_date_exclusive };
  validateWeeklyHistoryQuery(responseQuery);
  if (query) {
    validateWeeklyHistoryQuery(query);
    if (query.scopeType !== response.scope.type || query.scopeId && query.scopeId !== response.scope.id) throw new Error("Weekly history belongs to another scope.");
    if (query.startDate !== response.start_date || query.endDateExclusive !== response.end_date_exclusive) throw new Error("Weekly history belongs to another date range.");
  }
  if (response.timezone !== "UTC" || response.unit !== "USD" || response.basis !== "planning" || response.quantity !== "spend" || response.selection_policy !== "latest_published_before_week_start") throw new Error("Unsupported weekly financial target or forecast selection policy.");
  if (!Number.isFinite(Date.parse(response.as_of))) throw new Error("Weekly history needs a valid as-of time.");
  const count = (dateValue(response.end_date_exclusive) - dateValue(response.start_date)) / (7 * DAY);
  if (response.weeks.length !== count) throw new Error("Weekly history is missing a requested week.");
  const weeks = response.weeks.map((row, index): WeeklyHistoryWeek => {
    const expected = dateValue(response.start_date) + index * 7 * DAY;
    if (dateValue(row.start) !== expected || dateValue(row.end_exclusive) !== expected + 7 * DAY) throw new Error("Weekly history contains a mismatched week target.");
    const actual = row.actual, prior = row.prior_forecast, outlook = row.outlook;
    requireMoney(actual.amount); requireMoney(row.variance.amount);
    if ((row.state === "future" || actual.status === "future") && actual.amount !== null) throw new Error("Future weeks cannot contain observed actuals.");
    if (prior) {
      requireIssue(prior, response.as_of);
      if (prior.start !== row.start || prior.end_exclusive !== row.end_exclusive || Date.parse(prior.issued_at) > expected) throw new Error("Historical forecast must be issued before its exact week starts.");
    }
    if (row.variance.status === "available" && (row.state !== "closed" || actual.status !== "mature" || actual.source !== "observed_outcome" || !prior || actual.amount === null || row.variance.amount === null)) throw new Error("Only a closed week with a mature matching outcome has a final variance.");
    if (row.variance.status === "available" && actual.dataset_id !== prior?.dataset_id) throw new Error("The forecast and mature actual must use the same target dataset.");
    if (row.variance.status === "unavailable" && row.variance.amount !== null) throw new Error("Unavailable weekly variance must remain unknown.");
    if (outlook) {
      requireIssue(outlook, response.as_of);
      const start = dateValue(outlook.start), end = dateValue(outlook.end_exclusive);
      if (start < expected || end > expected + 7 * DAY || end <= start || !outlook.partial && (start !== expected || end !== expected + 7 * DAY)) throw new Error("Outlook must retain its exact full or partial week target.");
    }
    return { start: row.start, endExclusive: row.end_exclusive, state: row.state,
      actual: { amount: actual.amount, status: actual.status, source: actual.source, datasetId: actual.dataset_id, revision: actual.revision, corrected: actual.corrected, sourceRefs: actual.source_refs },
      priorForecast: prior ? { amount: prior.amount, runId: prior.run_id, targetId: prior.target_id, datasetId: prior.dataset_id, issuedAt: prior.issued_at, informationCutoff: prior.information_cutoff, start: prior.start, endExclusive: prior.end_exclusive } : null,
      outlook: outlook ? { amount: outlook.amount, runId: outlook.run_id, datasetId: outlook.dataset_id, issuedAt: outlook.issued_at, informationCutoff: outlook.information_cutoff, start: outlook.start, endExclusive: outlook.end_exclusive, partial: outlook.partial } : null,
      variance: { ...row.variance } };
  });
  return { scope: response.scope, startDate: response.start_date, endDateExclusive: response.end_date_exclusive, timezone: response.timezone, unit: response.unit, basis: response.basis, quantity: response.quantity,
    datasetId: response.dataset_id, asOf: response.as_of, synthetic: response.synthetic, actualsRevision: response.actuals_revision, selectionPolicy: response.selection_policy, weeks, notes: response.notes };
}
