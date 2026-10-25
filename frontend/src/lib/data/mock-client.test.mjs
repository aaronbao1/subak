import test from 'node:test';
import assert from 'node:assert/strict';
import {tsModuleUrl} from '../../../tests/load-ts-module.mjs';
const {MockDataClient}=await import(tsModuleUrl(new URL('./mock-client.ts',import.meta.url)));
test('mock chat deduplicates concurrent identical requests and reconciles the single resulting proposal',async()=>{
 const client=new MockDataClient();
 const before=(await client.getProposals()).length;
 const options={clientMessageId:'stable-1',conversationContext:{intent:'allocation'}};
 const first=client.sendMessage('main','Move $50 from Product to Research',undefined,options);
 assert.equal((await client.reconcileMessage('main','stable-1')).status,'pending');
 const second=client.sendMessage('main','Move $50 from Product to Research',undefined,options);
 const [a,b]=await Promise.all([first,second]);assert.deepEqual(a,b);
 assert.equal((await client.getProposals()).length,before+1);
 assert.deepEqual((await client.reconcileMessage('main','stable-1')).messages,a);
 await assert.rejects(client.sendMessage('main','Move $100 from Product to Research',undefined,options),/different content/);
 assert.equal(a[0].clientMessageId,'stable-1');assert.equal(a[1].clientMessageId,'stable-1');
 const proposal=await client.getProposal(a[1].proposalId);
 assert.equal(proposal.totalAfter-proposal.totalBefore,0);
 assert.equal(proposal.lines.find(line=>line.teamId==='research').after-proposal.lines.find(line=>line.teamId==='research').before,50);
});
test('mock selected revision remains linked and an explanation clears a pending allocation amount',async()=>{
 const client=new MockDataClient();
 const added=await client.sendMessage('main','Add $50 to Research');
 const original=await client.getProposal(added.at(-1).proposalId);
 const revised=await client.sendMessage('main','Make it $40 instead',undefined,{conversationContext:{intent:'allocation',selected_proposal_id:original.id,selected_proposal_version:original.version}});
 const next=await client.getProposal(revised.at(-1).proposalId);
 assert.equal(next.addedAmount,40);assert.equal(next.revisesProposalId,original.id);assert.equal((await client.getProposal(original.id)).status,'revised');
 const clarification=await client.sendMessage('main','Add funding');
 const pending=clarification.at(-1).conversationContext;
 assert.equal(pending.pending_slot,'amount');
 const explained=await client.sendMessage('main','Why did you add funding?',{action:'explain',run_id:'synthetic-ui-run-1',scope_type:'company',scope_id:'northstar'},{conversationContext:pending});
 assert.equal(explained.at(-1).proposalId,undefined);assert.equal(explained.at(-1).conversationContext.pending_slot,undefined);
 const amount=await client.sendMessage('main','50k',undefined,{conversationContext:explained.at(-1).conversationContext});
 assert.equal(amount.at(-1).proposalId,undefined);
});

test('weekly mock transport keeps historical issues immutable when the current forecast refreshes',async()=>{
 const client=new MockDataClient();
 const query={scopeType:'company',scopeId:'northstar',startDate:'2026-09-21',endDateExclusive:'2026-11-16'};
 const before=await client.getWeeklyForecastHistory(query);
 assert.equal(before.synthetic,true);assert.ok(before.weeks.slice(0,4).every(week=>week.variance.status==='available'));
 const job=await client.refreshForecast('new-current-week');const after=await client.getWeeklyForecastHistory(query);
 assert.deepEqual(after.weeks.slice(0,4),before.weeks.slice(0,4));
 assert.equal(after.actualsRevision,before.actualsRevision);
 assert.equal(after.weeks.find(week=>week.state==='current').outlook.runId,job.run_id);
});

test('mock explicit request remains pending until apply, then exact approved state and fulfillment refresh',async()=>{
 const client=new MockDataClient();const state=await client.getAllocationState();const curves=await client.getForecastViews();
 const request=await client.ingestTeamUpdate({clientRequestId:'explicit-1',teamId:'research',title:'Evaluation expansion',requestKind:'project',narrative:'Request incremental allocation',requestedAmount:'50.25',unit:'USD',periodStart:state.period.startDate,periodEndExclusive:state.period.endDateExclusive});
 assert.equal(request.approvedAmount,'0.00');assert.equal((await client.getAllocationState()).envelopeTotal,state.envelopeTotal);
 const receipt=await client.prepareBudgetRequestDraft(request.id,{baseVersion:state.stateVersion,actionType:'addition'},'request-draft');
 assert.equal((await client.getBudgetRequest(request.id)).status,'pending_review');assert.equal((await client.reconcileAllocationProposal('request-draft')).proposalId,receipt.proposalId);
 await client.applyProposal(receipt.proposalId);const updated=await client.getBudgetRequest(request.id);assert.equal(updated.status,'approved_applied');assert.equal(updated.approvedAmount,'50.25');assert.equal(updated.remainingRequestedAmount,'0.00');assert.equal((await client.getAllocationState()).stateVersion,state.stateVersion+1);assert.deepEqual(await client.getForecastViews(),curves);
});
test('mock apply reconciles exact cent sums instead of binary floating point totals',async()=>{
 const client=new MockDataClient();client.budgets.forEach((budget,index)=>{budget.allocated=[0.1,0.2,0.3][index]});
 const state=await client.getAllocationState();const receipt=await client.prepareAllocationProposal({baseVersion:state.stateVersion,periodStart:state.period.startDate,periodEndExclusive:state.period.endDateExclusive,unit:'USD',allocations:{research:'0.15',product:'0.15',engineering:'0.30'},rationale:'Redistribute five cents'},'exact-cents');
 await client.applyProposal(receipt.proposalId);assert.equal((await client.getAllocationState()).envelopeTotal,'0.60');
});

test('pinned mock explanation retains current team request consideration without changing forecast or budget',async()=>{
 const client=new MockDataClient();const state=await client.getAllocationState();
 const request=await client.ingestTeamUpdate({clientRequestId:'context-update',teamId:'research',title:'Proposed evaluation workload',requestKind:'project',narrative:'New project context',requestedAmount:null,unit:'USD',periodStart:state.period.startDate,periodEndExclusive:state.period.endDateExclusive});
 const bundle=await client.getForecastViews();const view=bundle.views.find(view=>view.scope.type==='team'&&view.scope.id==='research');const reply=await client.sendMessage('main','Explain this forecast',{action:'explain',run_id:view.run_id,scope_type:'team',scope_id:'research'},{conversationContext:{intent:'explain'}});
 const assistant=reply.at(-1);assert.equal(assistant.proposalId,undefined);assert.match(assistant.content,/Proposed evaluation workload/);assert.ok(assistant.content.includes(encodeURIComponent(request.id)));assert.equal(assistant.toolCalls.filter(tool=>tool.name==='list_budget_requests').length,1);assert.deepEqual(await client.getForecastViews(),bundle);assert.equal((await client.getAllocationState()).envelopeTotal,state.envelopeTotal);
});

test('a mock request citation opens the immutable submitted source, not an invented forecast document',async()=>{
 const client=new MockDataClient();const state=await client.getAllocationState();const request=await client.ingestTeamUpdate({clientRequestId:'source',teamId:'research',title:'Original update',requestKind:'team',narrative:'Original submitted context.',requestedAmount:null,unit:'USD',periodStart:state.period.startDate,periodEndExclusive:state.period.endDateExclusive,sourceRef:'Manager weekly note'});
 const doc=await client.getDocument(request.id);assert.equal(doc.title,'Original update');assert.ok(doc.body.includes('Original submitted context.'));assert.match(doc.body,/not specified/i);assert.match(doc.body,/does not change.*forecast/i);assert.deepEqual(doc.teamIds,['research']);assert.equal(doc.origin,'Submitted budget request');assert.ok(doc.body.includes('Manager weekly note'));assert.equal(doc.integration,'document');assert.equal(await client.getDocument('unknown'),undefined);
});
