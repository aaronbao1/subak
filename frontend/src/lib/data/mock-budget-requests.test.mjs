import test from 'node:test';
import assert from 'node:assert/strict';
import { tsModuleUrl } from '../../../tests/load-ts-module.mjs';
const { MockBudgetRequests } = await import(tsModuleUrl(new URL('./mock-budget-requests.ts', import.meta.url)));
const period={start:'2026-10-19',end:'2026-10-25'};
const input={clientRequestId:'request-1',teamId:'research',title:'Atlas expansion',requestKind:'project',projectName:'Atlas',narrative:'Add evaluation capacity, possibly costing $999.',requestedAmount:'50.00',unit:'USD',periodStart:period.start,periodEndExclusive:'2026-10-26'};
function setup() {
 const budgets=[{teamId:'research',allocated:60_000,unit:'usd',version:'v1',period},{teamId:'product',allocated:80_000,unit:'usd',version:'v1',period}];
 const proposals=[],decisions=[]; let version=1;
 const fx={company:{id:'company',name:'Company',budgetUnit:'usd',currentPeriod:period},teams:[{id:'research',name:'Research'},{id:'product',name:'Product'}],people:[],budgets,spending:[{id:'spend',teamId:'research',date:'2026-10-25',unit:'usd',component:'api',provenance:'simulated',amount:45000,complete:false,source:'Synthetic'}],forecasts:[],documents:[],context:[]};
 const bundle={views:[['research',85000],['product',50000]].map(([id,base])=>({run_id:'immutable-1',dataset_id:'company',scope:{type:'team',id},target:{unit:'usd',basis:'planning',quantity:'spend',timezone:'UTC'},planning_period_outlook:{start:period.start,end:'2026-10-26',base},publication:{generated_at:'2026-10-25T12:00:00Z'},weekly:[],daily:[]}))};
 const helper=new MockBudgetRequests(fx,{getBudgets:()=>budgets,getProposals:()=>proposals,getDecisions:()=>decisions,getBudgetVersion:()=>version,getBudgetVersionToken:()=>`v${version}`,getForecastBundle:()=>bundle,createProposal:p=>proposals.push(p),actorId:'finance-demo'});
 const apply=(proposal,amount)=>{const lines=structuredClone(proposal.lines);if(amount!==undefined){const row=lines.find(r=>r.teamId==='research');row.after=row.before+amount;}decisions.push({id:`decision-${decisions.length}`,proposalId:proposal.id,action:'applied',kind:proposal.kind,appliedAt:'2026-10-25T12:01:00Z',appliedBy:'Reviewer',unit:'usd',lines});proposal.status='applied';for(const line of lines)budgets.find(b=>b.teamId===line.teamId).allocated=line.after;version++;};
 return {fx,budgets,proposals,decisions,bundle,helper,apply,setVersion:v=>version=v};
}

test('intake preserves explicit amounts, null updates and immutable forecasts without applying budgets',()=>{
 const s=setup();const before=JSON.stringify({budgets:s.budgets,bundle:s.bundle});
 const row=s.helper.createRequest(input);
 assert.equal(row.status,'submitted');assert.equal(row.requestedAmount,'50.00');assert.equal(row.assessment.requestedAllocation,'60050.00');assert.equal(row.assessment.forecastAmount,'85000.00');assert.equal(row.assessment.forecastRunId,'immutable-1');assert.equal(row.assessment.amountIncludedInForecast,false);
 assert.equal(JSON.stringify({budgets:s.budgets,bundle:s.bundle}),before);assert.equal(s.proposals.length,0);assert.equal(s.decisions.length,0);
 const update=s.helper.createRequest({...input,clientRequestId:'update',requestedAmount:null});assert.equal(update.requestedAmount,null);assert.equal(update.remainingRequestedAmount,null);assert.equal(update.assessment.requestedAllocation,null);assert.throws(()=>s.helper.draftRequest(update.id,{baseVersion:1,actionType:'addition'},'null-draft'),/explicit|amount/i);
 row.title='mutated';assert.equal(s.helper.getRequest(row.id).title,'Atlas expansion');
});

test('request and draft retries retain actor-local receipts, reject key conflicts and reconcile',()=>{
 const s=setup();const row=s.helper.createRequest(input);assert.equal(s.helper.createRequest({...input,requestedAmount:'50'}).id,row.id);
 assert.throws(()=>s.helper.createRequest({...input,requestedAmount:'40'}),/different|reused/i);
 const d=s.helper.draftRequest(row.id,{baseVersion:1,actionType:'addition'},'op');assert.equal(s.helper.draftRequest(row.id,{baseVersion:1,actionType:'addition'},'op').proposalId,d.proposalId);assert.equal(s.helper.reconcileDraft('op').proposalId,d.proposalId);assert.equal(s.helper.reconcileDraft('missing'),undefined);assert.equal(s.proposals.length,1);assert.equal(s.helper.getRequest(row.id).status,'pending_review');
 assert.throws(()=>s.helper.draftRequest(row.id,{baseVersion:1,actionType:'transfer',sourceTeamId:'product'},'op'),/different|reused/i);
 s.apply(s.proposals[0]);assert.equal(s.helper.draftRequest(row.id,{baseVersion:1,actionType:'addition'},'op').proposalId,d.proposalId);assert.equal(s.helper.getRequest(row.id).status,'approved_applied');assert.equal(s.helper.getRequest(row.id).remainingRequestedAmount,'0.00');assert.equal(s.helper.getRequest(row.id).assessment.requestedAllocation,'60050.00');
});

test('request fulfillment requires actual decisions and follows partial revision lineage',()=>{
 const s=setup();const r=s.helper.createRequest(input);s.helper.draftRequest(r.id,{baseVersion:1,actionType:'addition'},'draft');
 const original=s.proposals[0];original.status='applied';assert.notEqual(s.helper.getRequest(r.id).status,'approved_applied');
 const revised={...structuredClone(original),id:'revision',status:'proposed',revisesProposalId:original.id};original.status='revised';s.proposals.push(revised);s.apply(revised,20);
 const row=s.helper.getRequest(r.id);assert.equal(row.status,'partially_funded');assert.equal(row.approvedAmount,'20.00');assert.equal(row.remainingRequestedAmount,'30.00');assert.equal(row.assessment.requestedAllocation,'60050.00');assert.equal(row.requestedAmount,'50.00');assert.deepEqual(new Set(row.linkedProposalIds),new Set([original.id,revised.id]));assert.equal(row.decisionIds.length,1);
 s.decisions.push({...s.decisions[0]});assert.equal(s.helper.getRequest(r.id).approvedAmount,'20.00');
});

test('full-map drafts conserve cents and validate stale, incomplete, mixed and unchanged targets',()=>{
 const s=setup();s.budgets[0].allocated=0.1;s.budgets[1].allocated=0.2;
 const body={baseVersion:1,periodStart:period.start,periodEndExclusive:'2026-10-26',unit:'USD',allocations:{research:'0.15',product:'0.15'},rationale:'Equal allocation.'};
 const receipt=s.helper.draftAllocationTargets(body,'cents');const p=s.proposals.find(p=>p.id===receipt.proposalId);assert.equal(p.totalBefore,0.3);assert.equal(p.totalAfter,0.3);assert.equal(p.kind,'redistribute');assert.deepEqual(p.lines.map(l=>l.after),[0.15,0.15]);assert.deepEqual(s.budgets.map(b=>b.allocated),[0.1,0.2]);
 for(const patch of [{baseVersion:0},{allocations:{research:'0.3'}},{allocations:{research:'0.10',product:'0.20'}},{allocations:{research:'0.01',product:'0.30'}},{allocations:{research:'0.15',product:'0.10'}},{allocations:{research:'0.151',product:'0.149'}}])assert.throws(()=>s.helper.draftAllocationTargets({...body,...patch},JSON.stringify(patch)));
 const add=s.helper.draftAllocationTargets({...body,allocations:{research:'0.15',product:'0.20'}},'addition');assert.equal(s.proposals.find(p=>p.id===add.proposalId).addedAmount,0.05);
});

test('transfers require explicit supported donor headroom and never silently cap requests',()=>{
 const s=setup();const r=s.helper.createRequest(input);
 assert.throws(()=>s.helper.draftRequest(r.id,{baseVersion:1,actionType:'transfer'},'no-source'),/source/i);
 assert.throws(()=>s.helper.draftRequest(r.id,{baseVersion:1,actionType:'addition',sourceTeamId:'product'},'bad-source'),/source/i);
 const large=s.helper.createRequest({...input,clientRequestId:'large',requestedAmount:'30000.01'});assert.throws(()=>s.helper.draftRequest(large.id,{baseVersion:1,actionType:'transfer',sourceTeamId:'product'},'too-large'),/headroom/i);
 const d=s.helper.draftRequest(r.id,{baseVersion:1,actionType:'transfer',sourceTeamId:'product'},'transfer');const p=s.proposals.find(p=>p.id===d.proposalId);assert.equal(p.totalAfter,p.totalBefore);assert.equal(p.lines.find(l=>l.teamId==='product').after,79950);
});

test('full-map direct request links reject ambiguous same-team demands and amountless updates',()=>{
 const s=setup();const a=s.helper.createRequest(input),b=s.helper.createRequest({...input,clientRequestId:'second'}),update=s.helper.createRequest({...input,clientRequestId:'context',requestedAmount:null});
 const body={baseVersion:1,periodStart:period.start,periodEndExclusive:'2026-10-26',unit:'USD',allocations:{research:'60050.00',product:'79950.00'},rationale:'Review needs.'};
 assert.throws(()=>s.helper.draftAllocationTargets({...body,requestIds:[a.id,b.id]},'joint'),/same.team|ambiguous/i);
 assert.throws(()=>s.helper.draftAllocationTargets({...body,requestIds:[update.id]},'context'),/amount|funding/i);
 assert.equal(s.proposals.length,0);
});

test('amountless update provenance supports a funding clarification without double attribution and retains request/document source identities',()=>{
 const s=setup();s.fx.documents.push({id:'plan-doc',title:'Atlas source plan',date:'2026-10-20'});
 const source=s.helper.createRequest({...input,clientRequestId:'context',requestedAmount:null});
 const demand=s.helper.createRequest({...input,clientRequestId:'clarified',evidenceRefs:[{kind:'budget_request',id:source.id},{kind:'document',id:'plan-doc'}]});
 assert.deepEqual(demand.evidenceRefs,[{kind:'budget_request',id:source.id},{kind:'document',id:'plan-doc'}]);
 const draft=s.helper.draftRequest(demand.id,{baseVersion:1,actionType:'addition'},'clarified');
 const proposal=s.proposals.find(p=>p.id===draft.proposalId);assert.deepEqual(new Set(proposal.citations.map(c=>c.documentId)),new Set([source.id,demand.id,'plan-doc']));
 s.apply(proposal);
 const funded=s.helper.getRequest(demand.id),context=s.helper.getRequest(source.id);
 assert.equal(funded.status,'approved_applied');assert.equal(funded.approvedAmount,'50.00');assert.equal(funded.remainingRequestedAmount,'0.00');assert.equal(funded.assessment.requestedAllocation,'60050.00');
 assert.equal(context.approvedAmount,'0.00');assert.equal(context.remainingRequestedAmount,null);assert.notEqual(context.status,'approved_applied');assert.deepEqual(context.linkedProposalIds,[]);assert.equal(context.decisionIds.length,0);
});

test('a sized source request remains provenance rather than a second funding earmark',()=>{
 const s=setup();const source=s.helper.createRequest({...input,clientRequestId:'earlier',requestedAmount:'25.00'});
 const demand=s.helper.createRequest({...input,clientRequestId:'new-demand',evidenceRefs:[{kind:'budget_request',id:source.id}]});
 const draft=s.helper.draftRequest(demand.id,{baseVersion:1,actionType:'addition'},'sized-source');const proposal=s.proposals.find(p=>p.id===draft.proposalId);s.apply(proposal);
 assert.equal(s.helper.getRequest(demand.id).approvedAmount,'50.00');assert.equal(s.helper.getRequest(demand.id).status,'approved_applied');
 assert.equal(s.helper.getRequest(source.id).approvedAmount,'0.00');assert.deepEqual(s.helper.getRequest(source.id).linkedProposalIds,[]);
 assert.ok(proposal.citations.some(c=>c.documentId===source.id));
});

test('missing compatible budget or forecast stays null; allocation state preserves explicit spend coverage',()=>{
 const s=setup();s.bundle.views[0].planning_period_outlook.end='2027-01-01';s.budgets.splice(0,1);
 const r=s.helper.createRequest(input);assert.equal(r.assessment.teamAllocation,null);assert.equal(r.assessment.requestedAllocation,null);assert.equal(r.assessment.forecastAmount,null);assert.equal(r.assessment.projectedHeadroom,null);
 const state=s.helper.getAllocationState();assert.equal(state.envelopeTotal,'80000.00');assert.equal(state.allocatedTotal,'80000.00');assert.equal(state.unallocatedAmount,'0.00');assert.equal(state.allocations[0].coverageStatus,'missing');
 s.budgets.length=0;const fresh=s.helper.assessRequest(r.id);assert.equal(fresh.assessment.budgetVersion,null);assert.equal(fresh.assessment.envelopeTotal,null);
 for(const patch of [{requestedAmount:'-1'},{requestedAmount:'0'},{requestedAmount:'0.001'},{requestedAmount:50},{teamId:'unknown'},{periodEndExclusive:'2026-12-31'},{narrative:' '}])assert.throws(()=>s.helper.createRequest({...input,clientRequestId:JSON.stringify(patch),...patch}));
});
