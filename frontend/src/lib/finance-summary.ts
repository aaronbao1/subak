import type { Budget, ForecastView, Period, Provenance, SpendingRecord, Unit } from './contracts';
import type { ComparisonTarget, ScopeRef, ScopeSummary, TargetInput } from './contracts/finance-view';

const dayAfter = (date: string) => /^\d{4}-\d{2}-\d{2}$/.test(date) && Number.isFinite(Date.parse(date)) ? new Date(Date.parse(`${date}T00:00:00Z`) + 86400000).toISOString().slice(0,10) : '';
const numeric = (value: unknown): number | null => typeof value === 'number' && Number.isFinite(value) ? value : null;
/** Compatibility transport carries money as numbers. Sum in minor units, never floating chart coordinates. */
export const sumMoney = (values: number[]): number => values.reduce((sum,value) => sum + Math.round(value * 100),0) / 100;
export function billableAmount(record: Pick<SpendingRecord,'component'|'provenance'|'amount'>): number {
  return record.component === 'included_usage' || record.component === 'unpriced_usage' || record.provenance === 'usage_only' ? 0 : numeric(record.amount) ?? 0;
}
export function comparisonTarget(input: TargetInput): ComparisonTarget {
  return { scope: input.scope, startDate: input.period.start, endDateExclusive: dayAfter(input.period.end), timezone:'UTC', unit:input.unit, basis:input.basis ?? 'planning', datasetId:input.datasetId, ...(input.issuedRunId ? {issuedRunId:input.issuedRunId} : {}) };
}
export function canCompareTargets(a: ComparisonTarget | null | undefined, b: ComparisonTarget | null | undefined): boolean {
  return !!a && !!b && !!a.startDate && !!a.endDateExclusive && !!a.datasetId && !!a.basis
    && a.startDate < a.endDateExclusive && a.scope.type === b.scope.type && (a.scope.id ?? null) === (b.scope.id ?? null)
    && a.startDate === b.startDate && a.endDateExclusive === b.endDateExclusive && a.timezone === b.timezone
    && a.unit === b.unit && a.basis === b.basis && a.datasetId === b.datasetId;
}
/** Only an explicitly supplied full target is eligible. Never scale a quarter into a week. */
export function forecastForPeriod(view: ForecastView | undefined, period: Period): number | null {
  if (!view) return null;
  const end = dayAfter(period.end);
  const matches = (point: Record<string, unknown> | undefined) => point?.start === period.start && point.end === end;
  const planning = view.planning_period_outlook as Record<string, unknown> | undefined;
  if (matches(planning)) return numeric(planning?.base);
  if (matches(view.quarter_outlook)) return numeric(view.quarter_outlook?.base);
  const week = view.weekly?.find(p => matches(p) && !p.partial);
  if (week) return numeric(week.base);
  const cumulative = view.cumulative?.find(p => matches(p));
  return numeric(cumulative?.base);
}
function inScope(record: SpendingRecord, scope: ScopeRef) {
  return scope.type === 'company' || scope.type === 'team' && record.teamId === scope.id || scope.type === 'person' && record.personId === scope.id
    || scope.type === 'shared' && (scope.id === 'people_unallocated' ? !!record.teamId && !record.personId : scope.id === 'teams_unallocated' ? !record.teamId && !!record.personId : !record.teamId && !record.personId);
}
export function selectScopeSummary(input: {
  scope: ScopeRef; period: Period; unit: Unit; datasetId: string; basis?: string;
  spending: SpendingRecord[]; budgets: Budget[]; forecastView?: ForecastView; datasetRevision?: string;
}): ScopeSummary {
  const {scope,period,unit,datasetId,forecastView:view} = input;
  const target = comparisonTarget(input);
  const rows = input.spending.filter(r => inScope(r,scope) && r.date >= period.start && r.date <= period.end && r.unit === unit);
  const byProvenance: Record<Provenance, number> = {reported_charge:0, estimate:0, usage_only:0, measured:0, simulated:0};
  for (const provenance of Object.keys(byProvenance) as Provenance[]) byProvenance[provenance] = sumMoney(rows.filter(r=>r.provenance === provenance).map(billableAmount));
  const observed = { amount:rows.length ? sumMoney(rows.map(billableAmount)) : null, byProvenance, includedNotional:sumMoney(rows.filter(r=>r.component === 'included_usage').map(r=>r.amount)), recordCount:rows.length, complete:rows.length > 0 && rows.every(r=>r.complete), revision:input.datasetRevision };
  const matchingBudgets = input.budgets.filter(b => (scope.type === 'company' || scope.type === 'team' && b.teamId === scope.id)
    && canCompareTargets(target,comparisonTarget({scope,period:b.period,unit:b.unit,datasetId,basis:input.basis})));
  const allocation = matchingBudgets.length ? sumMoney(matchingBudgets.map(b=>b.allocated)) : null;
  const viewTarget = view ? {...target, scope:view.scope, unit:view.target.unit.toLowerCase() as Unit, basis:view.target.basis ?? '', timezone:(view.target.timezone ?? view.timezone ?? '') as 'UTC', datasetId:typeof view.dataset_id === 'string' ? view.dataset_id : datasetId} : undefined;
  const amount = canCompareTargets(target,viewTarget) ? forecastForPeriod(view,period) : null;
  const quality = [!rows.length ? 'No recorded spending for this target.' : !observed.complete ? 'Recorded spending includes a partial day.' : '', allocation === null ? 'No matching budget for this target.' : '', amount === null ? 'No issued forecast available for this exact target.' : ''].filter(Boolean);
  return { target, observed, issued:{amount,runId:view?.run_id,synthetic:!!view?.is_synthetic}, allocation, variance:allocation !== null && amount !== null ? sumMoney([amount,-allocation]) : null, quality };
}
