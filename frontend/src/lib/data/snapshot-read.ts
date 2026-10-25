import type { ForecastBundle, ForecastDriver } from "@/lib/contracts/forecast-view";
import type { WeeklyHistoryQuery, WeeklyHistoryResponse } from "@/lib/contracts/weekly-history";
import { validateWeeklyHistoryQuery } from "./weekly-history";

const WEEK = 7 * 86_400_000;
const PREVIEW_LIMITATION = "Saved-data preview retains the issued amounts; edited assumptions require a forecast run to recalculate.";

/** Read an existing issuance without renaming it or sharing mutable snapshot objects with callers. */
export function snapshotForecastBundle(bundle: ForecastBundle, runId?: string): ForecastBundle {
  if (runId === undefined) return structuredClone(bundle);
  const views = bundle.views.filter(view => view.run_id === runId);
  if (!views.length) throw new Error("This issued forecast is unavailable in the saved snapshot.");
  const result = structuredClone({ ...bundle, views });
  if (result.publication && result.publication.run_id !== runId) result.publication = null;
  return result;
}

/** Slice one coherent saved response. Gaps and unknown scopes are unavailable, never estimated. */
export function selectSnapshotWeeklyHistory(histories: WeeklyHistoryResponse[] | undefined, query: WeeklyHistoryQuery): WeeklyHistoryResponse {
  validateWeeklyHistoryQuery(query);
  const matches = (histories ?? []).filter(history => history.scope.type === query.scopeType
    && (query.scopeId === undefined || history.scope.id === query.scopeId)
    && history.startDate <= query.startDate && history.endDateExclusive >= query.endDateExclusive);
  if (!matches.length) throw new Error("Weekly history is unavailable for this scope and range in the saved snapshot.");
  const count = (Date.parse(query.endDateExclusive) - Date.parse(query.startDate)) / WEEK;
  const selections = matches.map(history => {
    const weeks = history.weeks.filter(week => week.start >= query.startDate && week.endExclusive <= query.endDateExclusive);
    if (weeks.length !== count || weeks.some((week, index) => Date.parse(week.start) !== Date.parse(query.startDate) + index * WEEK
      || Date.parse(week.endExclusive) !== Date.parse(week.start) + WEEK)) {
      throw new Error("The saved weekly history is missing a complete requested week.");
    }
    return { ...history, startDate: query.startDate, endDateExclusive: query.endDateExclusive, weeks };
  });
  // Never choose silently between different as-of snapshots, outcome revisions, or issued values.
  const first = JSON.stringify(selections[0]);
  if (selections.some(selection => JSON.stringify(selection) !== first)) throw new Error("Conflicting saved weekly histories are available for this range.");
  return structuredClone(selections[0]);
}

/** Preserve the issued financial baseline while recording hypothetical assumptions without an engine. */
export function previewSnapshotScenario(bundle: ForecastBundle, runId: string, drivers: ForecastDriver[]): ForecastBundle {
  const result = snapshotForecastBundle(bundle, runId);
  const replacements = new Map<string, ForecastDriver>();
  for (const driver of drivers) {
    if (!driver.id?.trim() || replacements.has(driver.id)) throw new Error("Scenario drivers need nonempty, nonduplicate identities.");
    replacements.set(driver.id, driver);
  }
  result.parent_run_id = runId;
  result.is_scenario = true;
  result.recalculation_required = true;
  result.publication = null;
  result.driver_effects = [];
  for (const view of result.views) {
    // Company stores the full replacement set. Other scopes retain only known issued applicability;
    // new memberships and other scope changes need a real forecast run to establish their effects.
    const selected = view.scope.type === "company" ? drivers : view.included_drivers.flatMap(driver => {
      const replacement = replacements.get(driver.id);
      return replacement ? [replacement] : [];
    });
    view.included_drivers = structuredClone(selected);
    view.driver_effects = [];
    view.recalculation_required = true;
    view.limitations = [...view.limitations, PREVIEW_LIMITATION];
  }
  return result;
}
