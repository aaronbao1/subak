import type { AllocationState, AllocationTargetsInput, BudgetRequest, BudgetRequestInput } from "@/lib/contracts";

export type BudgetRequestWire = {
  id: string; client_request_id: string; team_id: string; title: string; request_kind: BudgetRequest["requestKind"]; project_name?: string | null;
  narrative: string; requested_amount: string | null; unit: "USD"; period_start: string; period_end_exclusive: string;
  source_ref?: string | null; evidence_refs: NonNullable<BudgetRequestInput["evidenceRefs"]>;
  period: { id: string; start_date: string; end_date_exclusive: string; label: string };
  source: { reference: string | null; submitted_by: string; submitted_at: string };
  status: BudgetRequest["status"]; linked_proposal_ids: string[]; decision_ids: string[]; approved_amount: string; remaining_requested_amount: string | null;
  assessment: {
    assessed_at: string; budget_version: number | null; envelope_total: string | null; team_allocation: string | null; recorded_spend: string;
    forecast_amount: string | null; forecast_run_id: string | null; forecast_status: "available" | "unavailable"; forecast_unit: "USD"; forecast_basis: "full_period_total";
    projected_headroom: string | null; requested_allocation: string | null; available_donors: Array<{team_id: string; headroom: string}>;
    qualification: string; amount_included_in_forecast: false;
  };
};
export type AllocationStateWire = {
  period: { id: string; label: string; start_date: string; end_date_exclusive: string };
  unit: "USD"; state_version: number; envelope_total: string; allocated_total: string; unallocated_amount: string;
  allocations: Array<{team_id: string; amount: string; recorded_spend: string; remaining: string; coverage_status: "complete" | "partial" | "missing"}>;
  updated_at: string; last_decision_id: string | null;
  spend_coverage: {status: "complete" | "partial" | "missing"; unattributed_spend: string; unattributed_records: number; notes: string[]}; note: string;
};
export function budgetRequestBody(input: BudgetRequestInput) {
  return {client_request_id:input.clientRequestId,team_id:input.teamId,title:input.title,request_kind:input.requestKind,
    project_name:input.projectName ?? null,narrative:input.narrative,requested_amount:input.requestedAmount,unit:input.unit,
    period_start:input.periodStart,period_end_exclusive:input.periodEndExclusive,source_ref:input.sourceRef ?? null,evidence_refs:input.evidenceRefs ?? []};
}
export function allocationTargetsBody(input: AllocationTargetsInput) {
  return {base_version:input.baseVersion,period_start:input.periodStart,period_end_exclusive:input.periodEndExclusive,unit:input.unit,
    allocations:input.allocations,rationale:input.rationale,request_ids:input.requestIds ?? []};
}
export function adaptBudgetRequest(w: BudgetRequestWire): BudgetRequest {
  const a=w.assessment;
  return {id:w.id,clientRequestId:w.client_request_id,teamId:w.team_id,title:w.title,requestKind:w.request_kind,projectName:w.project_name ?? undefined,
    narrative:w.narrative,requestedAmount:w.requested_amount,unit:w.unit,periodStart:w.period_start,periodEndExclusive:w.period_end_exclusive,
    sourceRef:w.source_ref ?? undefined,evidenceRefs:w.evidence_refs,period:{id:w.period.id,startDate:w.period.start_date,endDateExclusive:w.period.end_date_exclusive,label:w.period.label},
    source:{reference:w.source.reference,submittedBy:w.source.submitted_by,submittedAt:w.source.submitted_at},status:w.status,linkedProposalIds:w.linked_proposal_ids,
    decisionIds:w.decision_ids,approvedAmount:w.approved_amount,remainingRequestedAmount:w.remaining_requested_amount,
    assessment:{assessedAt:a.assessed_at,budgetVersion:a.budget_version,envelopeTotal:a.envelope_total,teamAllocation:a.team_allocation,recordedSpend:a.recorded_spend,
      forecastAmount:a.forecast_amount,forecastRunId:a.forecast_run_id,forecastStatus:a.forecast_status,forecastUnit:a.forecast_unit,forecastBasis:a.forecast_basis,
      projectedHeadroom:a.projected_headroom,requestedAllocation:a.requested_allocation,availableDonors:a.available_donors.map(d=>({teamId:d.team_id,headroom:d.headroom})),
      qualification:a.qualification,amountIncludedInForecast:a.amount_included_in_forecast}};
}
export function adaptAllocationState(w: AllocationStateWire): AllocationState {
  return {period:{id:w.period.id,label:w.period.label,startDate:w.period.start_date,endDateExclusive:w.period.end_date_exclusive},unit:w.unit,
    stateVersion:w.state_version,envelopeTotal:w.envelope_total,allocatedTotal:w.allocated_total,unallocatedAmount:w.unallocated_amount,
    allocations:w.allocations.map(a=>({teamId:a.team_id,amount:a.amount,recordedSpend:a.recorded_spend,remaining:a.remaining,coverageStatus:a.coverage_status})),
    updatedAt:w.updated_at,lastDecisionId:w.last_decision_id,spendCoverage:{status:w.spend_coverage.status,unattributedSpend:w.spend_coverage.unattributed_spend,
      unattributedRecords:w.spend_coverage.unattributed_records,notes:w.spend_coverage.notes},note:w.note};
}
