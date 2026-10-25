import type { AllocationState, Company, ForecastBundle, SpendingRecord } from './contracts';
import { selectScopeSummary, sumMoney } from './finance-summary';

export interface CompanyOverview {
  recorded: number | null;
  expected: number | null;
  /** Expected spend minus the matching native envelope; positive means over budget. */
  gap: number | null;
}
const safeMoney = (value: number | null): number | null => value !== null && Number.isFinite(value)
  && Number.isSafeInteger(Math.round(value * 100)) ? value : null;

/** The company publication includes shared costs; team projections are never substituted. */
export function selectCompanyOverview(input: {
  company?: Company;
  spending: SpendingRecord[];
  forecastBundle?: ForecastBundle;
  allocationState?: AllocationState;
  allocationStateStatus?: 'idle' | 'loading' | 'ready' | 'stale' | 'error';
}): CompanyOverview {
  const { company, allocationState: native } = input;
  if (!company) return { recorded: null, expected: null, gap: null };
  const view = input.forecastBundle?.views.find(view => view.scope.type === 'company' && view.scope.id === company.id);
  const summary = selectScopeSummary({
    scope: { type: 'company', id: company.id }, period: company.currentPeriod,
    unit: company.budgetUnit, datasetId: company.id, spending: input.spending, budgets: [],
    forecastView: view,
  });
  const financialRows = input.spending.filter(row => row.date >= company.currentPeriod.start && row.date <= company.currentPeriod.end
    && row.unit === company.budgetUnit && row.component !== 'included_usage' && row.component !== 'unpriced_usage' && row.provenance !== 'usage_only');
  const recorded = financialRows.length && financialRows.every(row => safeMoney(row.amount) !== null)
    ? safeMoney(summary.observed.amount) : null;
  // Mirror only the selector's point priority so an explicitly incomplete target cannot drive a KPI.
  const point = [view?.planning_period_outlook as Record<string, unknown> | undefined, view?.quarter_outlook,
    ...(view?.weekly ?? []).filter(point => !point.partial), ...(view?.cumulative ?? [])]
    .find(point => point?.start === summary.target.startDate && point?.end === summary.target.endDateExclusive);
  const spendTarget = view?.target.quantity === undefined || view.target.quantity === 'spend';
  const expected = spendTarget && point?.complete !== false && point?.partial !== true ? safeMoney(summary.issued.amount) : null;
  const matchingBudget = input.allocationStateStatus === 'ready' && native
    && native.period.startDate === summary.target.startDate
    && native.period.endDateExclusive === summary.target.endDateExclusive
    && native.unit.toLowerCase() === summary.target.unit;
  const envelope = matchingBudget && /^\d+(?:\.\d+)?$/.test(native.envelopeTotal)
    ? safeMoney(Number(native.envelopeTotal)) : null;
  return { recorded, expected, gap: expected !== null && envelope !== null ? safeMoney(sumMoney([expected, -envelope])) : null };
}
