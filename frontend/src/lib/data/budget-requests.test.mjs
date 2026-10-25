import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {stripTypeScriptTypes} from 'node:module';
const source=stripTypeScriptTypes(fs.readFileSync(new URL('./budget-requests.ts',import.meta.url),'utf8'));
const {adaptBudgetRequest,adaptAllocationState,budgetRequestBody,allocationTargetsBody}=await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);
const input={clientRequestId:'stable-1',teamId:'research',title:'Project',requestKind:'project',narrative:'Need funding eventually',requestedAmount:null,unit:'USD',periodStart:'2026-10-01',periodEndExclusive:'2027-01-01'};
test('request adapter retains explicit null amount, exact approval decimals and unavailable assessment',()=>{
 const wire={...budgetRequestBody(input),id:'r1',period:{id:'q4',start_date:'2026-10-01',end_date_exclusive:'2027-01-01',label:'Q4'},source:{reference:null,submitted_by:'actor',submitted_at:'now'},status:'partially_funded',linked_proposal_ids:['p1'],decision_ids:['d1'],approved_amount:'0.0000000001',remaining_requested_amount:null,assessment:{assessed_at:'now',budget_version:null,envelope_total:null,team_allocation:null,recorded_spend:'0',forecast_amount:null,forecast_run_id:null,forecast_status:'unavailable',forecast_unit:'USD',forecast_basis:'full_period_total',projected_headroom:null,requested_allocation:null,available_donors:[],qualification:'No budget',amount_included_in_forecast:false}};
 const value=adaptBudgetRequest(wire);assert.equal(value.requestedAmount,null);assert.equal(value.approvedAmount,'0.0000000001');assert.equal(value.assessment.budgetVersion,null);assert.equal(value.assessment.forecastAmount,null);assert.equal(value.assessment.amountIncludedInForecast,false);assert.equal(value.period.endDateExclusive,'2027-01-01');assert.deepEqual(value.linkedProposalIds,['p1']);
});
test('allocation state uses native envelope and unallocated amount without inferring from rounded team totals',()=>{
 const value=adaptAllocationState({period:{id:'p',label:'Period',start_date:'2026-10-01',end_date_exclusive:'2027-01-01'},unit:'USD',state_version:4,envelope_total:'100.00000000001',allocated_total:'90.00000000001',unallocated_amount:'10',allocations:[{team_id:'t',amount:'90.00000000001',recorded_spend:'91',remaining:'-0.99999999999',coverage_status:'partial'}],updated_at:'now',last_decision_id:'d',spend_coverage:{status:'partial',unattributed_spend:'2',unattributed_records:1,notes:['partial']},note:'Exact'});
 assert.equal(value.envelopeTotal,'100.00000000001');assert.equal(value.unallocatedAmount,'10');assert.equal(value.allocations[0].remaining,'-0.99999999999');assert.equal(value.period.endDateExclusive,'2027-01-01');
});
test('mutation body maps fields without inferring amounts or coercing decimal precision',()=>{
 assert.equal(budgetRequestBody(input).requested_amount,null);
 const value=allocationTargetsBody({baseVersion:4,periodStart:input.periodStart,periodEndExclusive:input.periodEndExclusive,unit:'USD',allocations:{t:'100.00000000001'},rationale:'Review',requestIds:['r']});
 assert.deepEqual(value,{base_version:4,period_start:'2026-10-01',period_end_exclusive:'2027-01-01',unit:'USD',allocations:{t:'100.00000000001'},rationale:'Review',request_ids:['r']});
});
