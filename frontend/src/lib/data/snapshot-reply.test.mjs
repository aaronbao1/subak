import test from 'node:test';
import assert from 'node:assert/strict';
import { tsModuleUrl } from '../../../tests/load-ts-module.mjs';
const { makeSnapshotReply } = await import(tsModuleUrl(new URL('./snapshot-reply.ts', import.meta.url)));
const { makeGenericReply } = await import(tsModuleUrl(new URL('../../fixtures/generate.ts', import.meta.url)));

const period = { start: '2026-10-01', end: '2026-12-31', label: 'Q4 2026' };
function fixture() {
  const teams = [{ id:'freight', name:'Freight' }, { id:'support', name:'Support' }];
  const budgets = teams.map((team, i) => ({teamId:team.id, period, unit:'usd', allocated:[50000,30000][i], version:'v8'}));
  const spending = teams.map((team, i) => ({id:team.id, teamId:team.id, date:'2026-10-24', component:'api', provider:'test', amount:[10000,15000][i], unit:'usd', provenance:'reported_charge', source:'Saved spending export', complete:true}));
  spending.push({...spending[0],id:'included',component:'included_usage',amount:99999});
  const forecasts = teams.map((team, i) => ({teamId:team.id, period, unit:'usd', basis:'full_period', status:'available', projected:[40000,35000][i]}));
  const context = [{id:'support-plan',scope:'team',teamIds:['support'],title:'Support rollout',summary:'Support has a planned rollout in November.',sources:[{documentId:'plan',title:'Support rollout plan',excerpt:'Rollout begins in November.'}]}];
  const dataset = {company:{id:'company',name:'Example Co',budgetUnit:'usd',currentPeriod:period,isDemo:true},teams,people:[],budgets,spending,forecasts,context,documents:[],proposals:[],decisions:[],threads:{}};
  const view = (type,id,base) => ({run_id:'saved-run',scope:{type,id},target:{unit:'USD',basis:'planning',quantity:'spend',timezone:'UTC'},dataset_id:'company',information_cutoff:'2026-10-25T00:00:00Z',daily:[],weekly:[],cumulative:[],quarter_outlook:{start:period.start,end:'2027-01-01',base,complete:true},included_drivers:[],queued_changes:[],limitations:[]});
  const bundle={views:[view('company','company',76000),view('team','freight',40000),view('team','support',35000)],publication:{run_id:'saved-run'}};
  const state={budgets,proposals:[],budgetVersion:'v8'};
  return {dataset,bundle,state,reply:makeSnapshotReply(dataset,bundle)};
}

test('analysis uses saved company total, exact-period spending, and current allocations without inventing a prior comparison',()=>{
  const {reply,dataset,bundle,state}=fixture(); const before=JSON.stringify({dataset,bundle,state});
  const out=reply('What changed our spending outlook?',state);
  assert.equal(out.proposal,undefined);
  assert.match(out.message.content,/\$25,000/); assert.match(out.message.content,/\$76,000/); assert.match(out.message.content,/\$80,000/);
  assert.doesNotMatch(out.message.content,/\$75,000|\$124,999|weekly envelope|I can help/);
  assert.match(out.message.content,/prior.*(unavailable|not included)|cannot quantify/i);
  assert.match(out.message.content,/Q4 2026/);
  assert.ok(out.message.content.split('\n\n')[0].length<=320);
  assert.equal(JSON.stringify({dataset,bundle,state}),before);
  assert.doesNotMatch(JSON.stringify(out.message.toolCalls),/live|Pulled|Slack|Asana|Monday/i);
});

test('named team explanation uses saved team receipt and cited context',()=>{
  const {reply,state}=fixture(); const out=reply('Why is Support over budget?',state);
  assert.match(out.message.content,/Support/); assert.match(out.message.content,/\$35,000/); assert.match(out.message.content,/\$30,000/);
  assert.match(out.message.content,/rollout/); assert.equal(out.message.citations[0].documentId,'plan');
  assert.equal(out.proposal,undefined);
});

test('selected team forecast explanation follows the pinned saved receipt',()=>{
  const {reply,state}=fixture(); const out=reply('Explain this forecast',state,undefined,{action:'explain',run_id:'saved-run',scope_type:'team',scope_id:'support'});
  assert.match(out.message.content.split('\n\n')[0],/Support/);assert.match(out.message.content.split('\n\n')[0],/\$35,000/);
  assert.doesNotMatch(out.message.content.split('\n\n')[0],/\$76,000/);
});

test('a missing pinned run is not silently substituted with the current saved receipt',()=>{
  const {reply,state}=fixture(); const out=reply('Explain this forecast',state,undefined,{action:'explain',run_id:'missing-run',scope_type:'team',scope_id:'support'});
  assert.match(out.message.content,/selected.*forecast.*not available/i);assert.equal(out.proposal,undefined);
  assert.doesNotMatch(out.message.content,/\$35,000/);
});

test('pinned forecast validation precedes a transfer and valid explain context cannot authorize an allocation',()=>{
  const {reply,state}=fixture();
  const text='Move $1000 from Freight to Support';
  const missing=reply(text,state,undefined,{action:'explain',run_id:'missing-run',scope_type:'team',scope_id:'freight'});
  assert.equal(missing.proposal,undefined);assert.match(missing.message.content,/selected.*forecast.*not available/i);
  const pinned=reply(text,state,undefined,{action:'explain',run_id:'saved-run',scope_type:'team',scope_id:'freight'});
  assert.equal(pinned.proposal,undefined);assert.match(pinned.message.content,/clear|adjust budgets/i);
  assert.equal(pinned.message.conversationContext.intent,'explain');
  assert.equal(pinned.message.conversationContext.draft,undefined);
});

test('a named different team cannot override the pinned forecast scope',()=>{
  const {reply,state}=fixture();
  const out=reply('Why is Support over budget?',state,undefined,{action:'explain',run_id:'saved-run',scope_type:'team',scope_id:'freight'});
  assert.match(out.message.content.split('\n\n')[0],/Freight/);assert.match(out.message.content.split('\n\n')[0],/\$40,000/);
  assert.doesNotMatch(out.message.content.split('\n\n')[0],/Support|\$35,000/);
});

test('invalid pinned scenarios and unsupported forecast refresh never create a scenario or claim a publication',()=>{
  const {reply,state}=fixture();
  const invalid=reply('Move project start to November 10',state,undefined,{action:'explain',run_id:'missing-run',scope_type:'team',scope_id:'freight',driver_id:'driver'});
  assert.equal(invalid.message.conversationContext.intent,'explain');assert.equal(invalid.message.actionDraft,undefined);
  const refresh=reply('Refresh the forecast',state,undefined,{action:'explain',run_id:'saved-run',scope_type:'team',scope_id:'freight'});
  assert.match(refresh.message.content,/cannot.*(?:recalculate|publish)|does not.*(?:recalculate|publish)/i);assert.equal(refresh.proposal,undefined);
});

test('a pinned cross-team comparison asks to clear the selected scope',()=>{
  const {reply,state}=fixture();
  const out=reply('Compare Freight and Support',state,undefined,{action:'explain',run_id:'saved-run',scope_type:'team',scope_id:'freight'});
  assert.match(out.message.content,/clear|selected forecast/i);assert.equal(out.proposal,undefined);
});

test('a selected person receipt never answers with company totals',()=>{
  const {dataset,bundle,state}=fixture();dataset.people=[{id:'pat',teamId:'support',name:'Pat Lee'}];
  dataset.spending=[{...dataset.spending[1],personId:'pat'}];
  bundle.views.push({...bundle.views[2],scope:{type:'person',id:'pat'},quarter_outlook:{...bundle.views[2].quarter_outlook,base:18000}});
  const out=makeSnapshotReply(dataset,bundle)('Explain this forecast',state,undefined,{action:'explain',run_id:'saved-run',scope_type:'person',scope_id:'pat'});
  assert.match(out.message.content.split('\n\n')[0],/Pat Lee/);assert.match(out.message.content.split('\n\n')[0],/\$18,000/);assert.doesNotMatch(out.message.content,/\$76,000/);
});

test('missing or incompatible company receipt is withheld instead of summing teams',()=>{
  const {dataset,bundle,state}=fixture(); bundle.views[0].quarter_outlook.end='2026-12-01';
  const out=makeSnapshotReply(dataset,bundle)('Analyze spend',state);
  assert.match(out.message.content,/no matching.*company forecast|company forecast.*unavailable/i);
  assert.doesNotMatch(out.message.content.split('\n\n')[0],/\$75,000|\$76,000/);
});

test('Q4 transfer and selected revision preserve exact amount, complete team lines and snapshot period',()=>{
  const {reply,state}=fixture();
  const out=reply('Move $1,000 from Freight to Support for 2026-10-01 through 2026-12-31 without adding funding',state);
  const p=out.proposal; assert.ok(p); assert.deepEqual(p.period,period); assert.equal(p.totalAfter,p.totalBefore);
  assert.deepEqual(p.lines.map(l=>l.after-l.before),[-1000,1000]);
  assert.doesNotMatch(out.message.content,/weekly|Pulled|live/i); assert.match(out.message.content,/not applied|review/i);
  state.proposals.push(p);
  const revision=reply('Make it $500 instead',state,out.message.conversationContext).proposal;
  assert.equal(revision.revisesProposalId,p.id); assert.deepEqual(revision.lines.map(l=>l.after-l.before),[-500,500]);
  assert.deepEqual(revision.period,period);
});

test('generic helper accepts an explicit planning period for proposals and requests',()=>{
  const {dataset,state}=fixture();
  const reply=makeGenericReply(dataset.teams,dataset.forecasts,dataset.context,[],period);
  const out=reply('Add $50 to Support for 2026-10-01 through 2026-12-31',state);
  assert.equal(out.proposal.addedAmount,50);assert.deepEqual(out.proposal.period,period);
});

test('current Q4 funding requests are considered without automatic approval or forecast changes',()=>{
  const {reply,state}=fixture();
  state.budgetRequests=[{id:'request1',teamId:'support',title:'Support capacity',requestedAmount:'1000.00',remainingRequestedAmount:'1000.00',unit:'USD',status:'submitted',periodStart:period.start,periodEndExclusive:'2027-01-01',period:{startDate:period.start,endDateExclusive:'2027-01-01'},source:{reference:'Team update',submittedBy:'Support manager'}}];
  const out=reply('Review funding requests',state);
  assert.match(out.message.content,/Support capacity/);assert.match(out.message.content,/\$1,000/);
  assert.match(out.message.content,/not added to the published forecast/);assert.equal(out.proposal,undefined);
  assert.equal(out.message.toolCalls.filter(t=>t.name==='list_budget_requests').length,1);
});

test('scenario date requests retain structured date intent and guide a saved driver selection',()=>{
  const {reply,state}=fixture(); const out=reply('Move the project start to November 10',state);
  assert.equal(out.proposal,undefined);assert.equal(out.message.conversationContext.intent,'scenario');
  assert.equal(out.message.conversationContext.effective_date_text,'Move the project start to November 10');
  assert.match(out.message.content,/scenario|driver|assumption/i);assert.doesNotMatch(out.message.content,/forecast (?:updated|changed)/i);
});

test('negation and financial questions never create allocation proposals',()=>{
  const {reply,state}=fixture();
  for(const text of ['Do not add funding','Why did Support request $1000?','Should we move $1000 from Freight to Support?']) assert.equal(reply(text,state).proposal,undefined,text);
});

test('a transfer cannot use money needed by the saved source forecast or recorded spend',()=>{
  const {reply,state}=fixture();
  const out=reply('Move $20,000 from Freight to Support',state);
  assert.equal(out.proposal,undefined);assert.match(out.message.content,/\$10,000/);assert.match(out.message.content,/headroom|available/i);
});

test('unique team shorthand resolves Support to Customer Support Automation without guessing ambiguous names',()=>{
  const {dataset,bundle,state}=fixture();
  dataset.teams[1]={id:'support-automation',name:'Customer Support Automation'};
  dataset.forecasts[1].teamId='support-automation';dataset.spending[1].teamId='support-automation';state.budgets[1].teamId='support-automation';bundle.views[2].scope.id='support-automation';
  const reply=makeSnapshotReply(dataset,bundle);
  const out=reply('Move $1000 from Freight to Support without adding funding',state);
  assert.ok(out.proposal);assert.equal(out.proposal.lines.find(line=>line.teamId==='support-automation').after,31000);
  dataset.teams.push({id:'support-sales',name:'Sales Support'});
  const ambiguous=makeSnapshotReply(dataset,bundle)('Move $1000 from Freight to Support',state);
  assert.equal(ambiguous.proposal,undefined);assert.match(ambiguous.message.content,/known team|destination|team should/i);
});

test('unallocated reserve is preserved in envelope analysis after a session funding increase',()=>{
  const {dataset,bundle,state}=fixture();const reply=makeSnapshotReply(dataset,bundle,{envelopeTotal:90000});
  state.budgets=state.budgets.map(b=>({...b,allocated:b.allocated+(b.teamId==='support'?1000:0)}));
  const out=reply('Analyze spend',state);assert.match(out.message.content,/Company envelope: \*\*\$91,000/);
});
