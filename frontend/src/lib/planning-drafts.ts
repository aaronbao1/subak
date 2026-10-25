import type { Budget, ConversationContext, ForecastBundle, ForecastDriver, ForecastQuestionContext, ForecastScope, ForecastView, Period, Unit } from "./contracts";

/** Drafts describe hypothetical assumptions or requested transfers, never an approval. */
export type ActionDraft = ScenarioActionDraft | AllocationActionDraft;
export interface ScenarioActionDraft {
  kind: "scenario"; id: string; parentRunId: string; scope: ForecastScope; driverId: string; title: string;
  proposedStart?: string; proposedEnd?: string | null; parameters?: Record<string, number | string>; revision?: number;
}
export interface AllocationActionDraft {
  kind: "allocation"; id: string; proposalId?: string; sourceTeamId: string; destinationTeamId: string;
  amount: string; unit: Unit; period: Period; revision?: number;
}
const numeric = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);
const plusDays = (date: string, days: number) => new Date(Date.parse(`${date}T00:00:00Z`) + days * 86400000).toISOString().slice(0, 10);
const months = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"];

/** Date-only assumptions use UTC; an explicit reference is required for relative wording. */
export function resolvePlanningDate(input: string, reference?: string): string {
  const text = input.trim().toLowerCase();
  let date = text;
  const relative = text.match(/^(?:make it )?(\d+|one|two|three|four) (day|week)s? (later|earlier)$/);
  if (relative) {
    if (!reference) throw new Error("A current draft date is required as the reference.");
    const n = ({ one: 1, two: 2, three: 3, four: 4 } as Record<string, number>)[relative[1]] ?? Number(relative[1]);
    date = plusDays(resolvePlanningDate(reference), n * (relative[2] === "week" ? 7 : 1) * (relative[3] === "later" ? 1 : -1));
  } else {
    const named = text.match(/^([a-z]+) (\d{1,2})(?:st|nd|rd|th)?,? (\d{4})$/);
    if (named) {
      const month = months.indexOf(named[1]);
      if (month >= 0) date = `${named[3]}-${String(month + 1).padStart(2, "0")}-${named[2].padStart(2, "0")}`;
    }
  }
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) throw new Error("Use YYYY-MM-DD or a month, day and year, such as November 10, 2026.");
  const instant = Date.parse(`${date}T00:00:00Z`);
  if (!Number.isFinite(instant) || new Date(instant).toISOString().slice(0, 10) !== date) throw new Error("Enter a valid calendar date.");
  return date;
}

export function driverStart(driver: ForecastDriver): string | undefined {
  return driver.kind === "project_schedule" && typeof driver.parameters?.to_start === "string" ? driver.parameters.to_start : driver.effective_from;
}
export function createScenarioDraft(view: ForecastView, driver: ForecastDriver): ScenarioActionDraft {
  return { kind: "scenario", id: `${view.run_id}:${driver.id}`, parentRunId: view.run_id, scope: { ...view.scope }, driverId: driver.id, title: driver.title ?? driver.kind?.replaceAll("_", " ") ?? "Plan change", proposedStart: driverStart(driver), ...(driver.kind !== "project_schedule" ? { proposedEnd: driver.effective_to } : {}), revision: 1 };
}

/** Bridge only a selected, issued driver. Unresolved identity or prose stays a clarification. */
export function scenarioDraftFromConversation({ bundle, forecastContext, context, previousDraft }: {
  bundle?: ForecastBundle; forecastContext?: ForecastQuestionContext; context?: ConversationContext; previousDraft?: ScenarioActionDraft;
}): ScenarioActionDraft | undefined {
  if (context?.intent !== "scenario" || !context.effective_date_text || !forecastContext?.driver_id) return undefined;
  const view = bundle?.views.find(v => v.run_id === forecastContext.run_id && v.scope.type === forecastContext.scope_type && (v.scope.id ?? null) === (forecastContext.scope_id ?? null));
  const driver = view?.included_drivers.find(d => d.id === forecastContext.driver_id);
  if (!view || !driver || !["workload", "pricing", "membership", "adoption", "project_schedule"].includes(driver.kind ?? "")) return undefined;
  if (context.forecast_run_id && context.forecast_run_id !== view.run_id) return undefined;
  const previous = previousDraft?.parentRunId === view.run_id && previousDraft.driverId === driver.id && previousDraft.scope.type === view.scope.type && (previousDraft.scope.id ?? null) === (view.scope.id ?? null) ? previousDraft : undefined;
  const draft = previous ?? createScenarioDraft(view, driver);
  const text = context.effective_date_text.toLowerCase();
  // End-date and duration edits need their own named field rather than being mistaken for a start move.
  if (/\b(end|finish|duration)\b/.test(text)) return undefined;
  const date = text.match(/\b\d{4}-\d{2}-\d{2}\b|\b(?:january|february|march|april|may|june|july|august|september|october|november|december) \d{1,2}(?:st|nd|rd|th)?(?:,? \d{4})?\b|\b(?:\d+|one|two|three|four) (?:day|week)s? (?:later|earlier)\b/)?.[0];
  if (!date) return undefined;
  // A named date without a year resolves in the selected plan's year, then is restated on the card.
  const concrete = /^[a-z]+ \d{1,2}(?:st|nd|rd|th)?$/.test(date) && draft.proposedStart ? `${date} ${draft.proposedStart.slice(0, 4)}` : date;
  try { return { ...draft, proposedStart: resolvePlanningDate(concrete, draft.proposedStart), revision: previous ? (previous.revision ?? 1) + 1 : draft.revision }; }
  catch { return undefined; }
}

export function editableParameters(driver: ForecastDriver): Array<{ key: string; label: string; min: number; max?: number }> {
  const field = driver.kind === "workload" ? { key: "exposure", label: "Work units per day", min: 0 }
    : driver.kind === "pricing" ? { key: "rate", label: `Rate per ${String(driver.parameters?.unit ?? "unit")}`, min: 0 }
    : driver.kind === "adoption" ? { key: "share", label: "Configuration share (0–1)", min: 0, max: 1 } : undefined;
  if (!field) return [];
  return [field, ...["low", "high"].flatMap(bound => driver.parameters?.[`${field.key}_${bound}`] !== undefined ? [{ ...field, key: `${field.key}_${bound}`, label: `${field.label} — ${bound} assumption` }] : [])];
}

/** API replacement semantics require the complete same-run company list, even from a team card. */
export function buildScenarioDrivers(bundle: ForecastBundle, draft: ScenarioActionDraft, teamIds?: string[]): ForecastDriver[] {
  const parent = bundle.views.find(v => v.scope.type === "company" && v.run_id === draft.parentRunId);
  if (!parent) throw new Error("The same issued parent forecast is unavailable. Reopen this plan from its publication.");
  const scoped = bundle.views.find(v => v.run_id === draft.parentRunId && v.scope.type === draft.scope.type && (v.scope.id ?? null) === (draft.scope.id ?? null));
  if (!scoped?.included_drivers.some(d => d.id === draft.driverId)) throw new Error("This assumption is not included in the selected forecast scope.");
  const original = parent.included_drivers.find(d => d.id === draft.driverId);
  if (!original) throw new Error("This plan is not included in the selected issued forecast.");
  if (original.status === "context_only") throw new Error("Source context has no supported numerical assumption to edit.");
  if (!["workload", "pricing", "membership", "adoption", "project_schedule"].includes(original.kind ?? "")) throw new Error("This plan type has no supported editable assumptions.");
  const edited: ForecastDriver = structuredClone(original);
  const start = draft.proposedStart ? resolvePlanningDate(draft.proposedStart) : driverStart(original);
  if (!start) throw new Error("Choose a start date before previewing.");
  edited.parameters = { ...original.parameters };
  if (original.kind === "project_schedule") {
    const from = resolvePlanningDate(String(original.parameters?.from_start ?? ""));
    const end = resolvePlanningDate(String(original.parameters?.from_end ?? ""));
    if (end <= from) throw new Error("The source schedule must end after its start.");
    if (draft.proposedEnd) throw new Error("This schedule moves its original duration; an independent end edit is not supported.");
    edited.parameters.to_start = start;
  } else {
    const end = draft.proposedEnd === null ? null : draft.proposedEnd ? resolvePlanningDate(draft.proposedEnd) : original.effective_to;
    if (end && end <= start) throw new Error("End date must be after start date (end is exclusive).");
    edited.effective_from = start; edited.effective_to = end;
  }
  const allowed = editableParameters(original);
  for (const [key, value] of Object.entries(draft.parameters ?? {})) {
    const field = allowed.find(p => p.key === key);
    if (original.kind === "membership" && key === "team_id") {
      if (typeof value !== "string" || !teamIds?.includes(value)) throw new Error("Select a known destination team.");
    } else {
      if (!field) throw new Error(`The ${key} assumption is not supported for this plan.`);
      if (!numeric(value) || value < field.min || field.max !== undefined && value > field.max) throw new Error(`${field.label} must be a finite nonnegative value${field.max !== undefined ? ` no greater than ${field.max}` : ""}.`);
    }
    edited.parameters[key] = value;
  }
  for (const key of ["exposure", "rate", "share"]) {
    const base = edited.parameters[key], low = edited.parameters[`${key}_low`], high = edited.parameters[`${key}_high`];
    if (numeric(base) && (numeric(low) && low > base || numeric(high) && high < base)) throw new Error("Keep the base assumption inside its supplied low/high range. Edit the bounds under More assumptions.");
  }
  return parent.included_drivers.map(d => d.id === edited.id ? edited : structuredClone(d));
}

export function validateAllocationDraft(draft: AllocationActionDraft, budgets: Budget[]) {
  if (!draft.sourceTeamId || !draft.destinationTeamId || draft.sourceTeamId === draft.destinationTeamId) throw new Error("Choose two different teams.");
  if (!/^\d+(?:\.\d{1,2})?$/.test(draft.amount.trim())) throw new Error("Enter an exact positive amount with at most two decimal places.");
  const amount = Number(draft.amount);
  if (!Number.isFinite(amount) || amount <= 0 || !Number.isSafeInteger(Math.round(amount * 100))) throw new Error("Enter a valid positive amount.");
  const matches = (teamId: string) => budgets.filter(b => b.teamId === teamId && b.unit === draft.unit && b.period.start === draft.period.start && b.period.end === draft.period.end);
  const from = matches(draft.sourceTeamId), to = matches(draft.destinationTeamId);
  if (from.length !== 1 || to.length !== 1) throw new Error("Both teams need one matching allocation for this exact period and unit.");
  if (amount > from[0].allocated) throw new Error("Amount exceeds the source team's available allocation.");
  return { amount, companyChange: 0, sourceBefore: from[0].allocated, sourceAfter: (Math.round(from[0].allocated * 100) - Math.round(amount * 100)) / 100, destinationBefore: to[0].allocated, destinationAfter: (Math.round(to[0].allocated * 100) + Math.round(amount * 100)) / 100 };
}

export function scenarioComparison(baseline: ForecastView, scenario: ForecastBundle): { available: boolean; reason?: string; baseline?: number; scenario?: number; delta?: number; view?: ForecastView } {
  if (scenario.parent_run_id && scenario.parent_run_id !== baseline.run_id) throw new Error("Scenario belongs to a different parent forecast.");
  const view = scenario.views.find(v => v.scope.type === baseline.scope.type && (v.scope.id ?? null) === (baseline.scope.id ?? null));
  if (!view) return { available: false, reason: "The scenario has no result for this scope." };
  const before = baseline.quarter_outlook, after = view.quarter_outlook;
  if (view.target.unit !== baseline.target.unit || view.target.quantity !== baseline.target.quantity || view.target.basis !== baseline.target.basis || !before?.start || !before?.end || before.start !== after?.start || before.end !== after?.end) return { available: false, reason: "The scenario and baseline do not cover the same target and period.", view };
  if (!numeric(before?.base) || !numeric(after?.base)) return { available: false, reason: "A comparable total is not available for this scenario.", view };
  return { available: true, baseline: before.base, scenario: after.base, delta: after.base - before.base, view };
}
