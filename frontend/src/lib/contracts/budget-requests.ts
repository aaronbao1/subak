export type BudgetRequestKind = "team" | "project" | "initiative";
export type BudgetRequestStatus = "submitted" | "pending_review" | "needs_revision" | "partially_funded" | "approved_applied" | "rejected";
export interface BudgetRequestEvidenceRef {
  kind: "signal" | "document" | "forecast_snapshot" | "spend_summary" | "budget_request";
  id: string;
  version?: number | null;
  note?: string | null;
}
/** Explicit additional team allocation requested, never a predictive spend estimate. */
export interface BudgetRequestInput {
  clientRequestId: string;
  teamId: string;
  title: string;
  requestKind: BudgetRequestKind;
  projectName?: string;
  narrative: string;
  requestedAmount: string | null;
  unit: "USD";
  periodStart: string;
  periodEndExclusive: string;
  sourceRef?: string;
  evidenceRefs?: BudgetRequestEvidenceRef[];
}
export interface BudgetRequestAssessment {
  assessedAt: string;
  budgetVersion: number | null;
  envelopeTotal: string | null;
  teamAllocation: string | null;
  recordedSpend: string;
  forecastAmount: string | null;
  forecastRunId: string | null;
  forecastStatus: "available" | "unavailable";
  forecastUnit: "USD";
  forecastBasis: "full_period_total";
  projectedHeadroom: string | null;
  requestedAllocation: string | null;
  availableDonors: Array<{ teamId: string; headroom: string }>;
  qualification: string;
  amountIncludedInForecast: false;
}
export interface BudgetRequest extends BudgetRequestInput {
  id: string;
  period: { id: string; startDate: string; endDateExclusive: string; label: string };
  source: { reference: string | null; submittedBy: string; submittedAt: string };
  status: BudgetRequestStatus;
  linkedProposalIds: string[];
  decisionIds: string[];
  approvedAmount: string;
  remainingRequestedAmount: string | null;
  assessment: BudgetRequestAssessment;
}
export interface BudgetRequestDraftInput {
  baseVersion: number;
  actionType: "addition" | "transfer";
  sourceTeamId?: string;
}
/** Full explicitly edited allocation map; backend validates transfer conservation or an explicit addition. */
export interface AllocationTargetsInput {
  baseVersion: number;
  periodStart: string;
  periodEndExclusive: string;
  unit: "USD";
  allocations: Record<string, string>;
  rationale: string;
  requestIds?: string[];
}
export interface AllocationDraftReceipt { proposalId: string; request?: BudgetRequest }
export interface AllocationState {
  period: { id: string; label: string; startDate: string; endDateExclusive: string };
  unit: "USD";
  stateVersion: number;
  envelopeTotal: string;
  allocatedTotal: string;
  unallocatedAmount: string;
  allocations: Array<{ teamId: string; amount: string; recordedSpend: string; remaining: string; coverageStatus: "complete" | "partial" | "missing" }>;
  updatedAt: string;
  lastDecisionId: string | null;
  spendCoverage: { status: "complete" | "partial" | "missing"; unattributedSpend: string; unattributedRecords: number; notes: string[] };
  note: string;
}
