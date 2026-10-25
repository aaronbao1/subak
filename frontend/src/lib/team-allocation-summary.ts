import type { AllocationState, Budget, Company, ForecastBundle, SpendingRecord, Team } from "./contracts";
import { comparisonTarget, selectScopeSummary, sumMoney } from "./finance-summary";
import { scopeView } from "../components/dashboard/forecast-derive";

export interface TeamAllocationRow {
  team: Team;
  projected: number | null;
  allocation: number | null;
  canAdjust: boolean;
  /** Expected full-period spend minus the allocation for that same target. */
  gap: number | null;
  gapState: "over" | "headroom" | "balanced" | "unavailable";
}

const sharedScopeIds = new Set(["", "unattributed", "shared", "unknown", "unassigned", "people_unallocated", "teams_unallocated"]);
const isSharedScope = (team: Team) => sharedScopeIds.has(team.id.trim().toLowerCase());

const gapPriority: Record<TeamAllocationRow["gapState"], number> = { over: 0, headroom: 1, balanced: 2, unavailable: 3 };

/** Uses the authoritative company target; no quarter scaling or observed-spend fallback. */
export function selectTeamAllocationRows(input: {
  company?: Company;
  teams: Team[];
  spending: SpendingRecord[];
  budgets: Budget[];
  forecastBundle?: ForecastBundle;
}): TeamAllocationRow[] {
  const { company } = input;
  if (!company) return [];
  return input.teams.filter(team => !isSharedScope(team)).map((team): TeamAllocationRow => {
    const summary = selectScopeSummary({
      scope: { type: "team", id: team.id }, period: company.currentPeriod,
      unit: company.budgetUnit, datasetId: company.id, spending: input.spending,
      budgets: input.budgets, forecastView: scopeView(input.forecastBundle, "team", team.id),
    });
    const gap = summary.variance;
    return {
      team, projected: summary.issued.amount, allocation: summary.allocation, gap,
      canAdjust: summary.allocation !== null && Number.isFinite(summary.allocation) && summary.allocation >= 0,
      gapState: gap === null ? "unavailable" : gap > 0 ? "over" : gap < 0 ? "headroom" : "balanced",
    };
  }).sort((left, right) => gapPriority[left.gapState] - gapPriority[right.gapState]
    || Math.abs(right.gap ?? 0) - Math.abs(left.gap ?? 0)
    || left.team.name.localeCompare(right.team.name));
}


export interface TeamAllocationSummaryView {
  /** Exact native company envelope; absent unless ready and on the selected target. */
  overallBudget: string | null;
  nativeAllocatedTotal: string | null;
  /** Positive native unallocated amount only; never inferred from legacy row sums. */
  unallocatedAmount: string | null;
  rows: Array<TeamAllocationRow & { allocationShare: number | null }>;
  totalAllocation: number | null;
  /** Matching allocations whose team is absent from the current directory. */
  unlistedAllocation: number | null;
  missingTeamCount: number;
  hasSharedScope: boolean;
}

/** The company denominator includes every matching allocation, including teams outside the visible list. */
export function selectTeamAllocationSummary(input: Parameters<typeof selectTeamAllocationRows>[0] & {
  allocationState?: AllocationState;
  allocationStateStatus?: "idle" | "loading" | "ready" | "stale" | "error";
}): TeamAllocationSummaryView {
  const rows = selectTeamAllocationRows(input);
  const { company } = input;
  const totalAllocation = company ? selectScopeSummary({
    scope: { type: "company", id: company.id }, period: company.currentPeriod,
    unit: company.budgetUnit, datasetId: company.id, spending: input.spending, budgets: input.budgets,
  }).allocation : null;
  const target = company ? comparisonTarget({ scope: { type: "company", id: company.id }, period: company.currentPeriod, unit: company.budgetUnit, datasetId: company.id }) : null;
  const native = input.allocationState;
  const exactNonnegativeMoney = (value: unknown): value is string => typeof value === "string" && /^\d+(?:\.\d+)?$/.test(value);
  const nativeMatches = input.allocationStateStatus === "ready" && !!native && !!target
    && native.period.startDate === target.startDate && native.period.endDateExclusive === target.endDateExclusive
    && native.unit.toLowerCase() === target.unit
    && [native.envelopeTotal, native.allocatedTotal, native.unallocatedAmount].every(exactNonnegativeMoney);
  const listedAllocation = sumMoney(rows.flatMap(row => row.allocation === null ? [] : [row.allocation]));
  return {
    overallBudget: nativeMatches ? native.envelopeTotal : null,
    nativeAllocatedTotal: nativeMatches ? native.allocatedTotal : null,
    unallocatedAmount: nativeMatches && /[1-9]/.test(native.unallocatedAmount) ? native.unallocatedAmount : null,
    totalAllocation,
    unlistedAllocation: totalAllocation === null ? null : sumMoney([totalAllocation, -listedAllocation]),
    missingTeamCount: rows.filter(row => row.allocation === null).length,
    hasSharedScope: input.teams.some(isSharedScope),
    rows: rows.map(row => ({
      ...row,
      allocationShare: totalAllocation !== null && totalAllocation > 0 && row.allocation !== null && row.allocation >= 0 && row.allocation <= totalAllocation
        ? row.allocation / totalAllocation : null,
    })),
  };
}
