import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { stripTypeScriptTypes } from 'node:module';
const source = stripTypeScriptTypes(fs.readFileSync(new URL('./action-intent.ts', import.meta.url), 'utf8'));
const { interpretActionIntent } = await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);
const teams = [{ id: 'research', name: 'Research' }, { id: 'product', name: 'Product' }, { id: 'engineering', name: 'Engineering' }];
const parse = (text, options) => interpretActionIntent(text, teams, options);
const proposal = { id: 'p1', version: 2, kind: 'add_budget', status: 'proposed', addedAmount: 50000, lines: [{teamId:'research',before:60000,after:110000},{teamId:'product',before:80000,after:80000}] };
test('questions and negated additions never authorize money', () => {
  for (const text of ['Why did you add $50k?', 'Can we add $50?', 'What would adding 50k do?', 'Do not add funding', "Don't add $50", 'Never add more funding']) {
    const result = parse(text);
    assert.equal(result.readOnly, true, text);
    assert.notEqual(result.action, 'addition', text);
    assert.notEqual(result.context?.pending_slot, 'amount', text);
  }
});
test('negated addition plus redistribution preserves the transfer action', () => {
  for (const text of ['Do not add funding; redistribute the current budget', 'Redistribute without adding new funding', 'Without adding funding, move $50 from Product to Research']) {
    assert.equal(parse(text).action, 'transfer', text);
  }
});
test('money is exact dollars, with only explicit suffix scaling', () => {
  for (const [text, amount] of [['Add $50', '50'], ['Add 50', '50'], ['Add $50.25 to Research','50.25'], ['Add 0.000001m','1'], ['Add 1.25k','1250'], ['Add $1,250.50','1250.5'], ['Add 50k','50000']]) {
    const result = parse(text);
    assert.equal(result.action, 'addition', text);
    assert.equal(result.amount, amount, text);
  }
});
test('negative zero malformed fractional-cent and unsafe amounts never yield a proposal', () => {
  for (const text of ['Add -$50', 'Add $-50', 'Add −50k', 'Add 0', 'Add $50.001', 'Add $12,34', 'Add 9007199254740992', 'Add 10k or 20k']) {
    const result = parse(text);
    assert.equal(result.action, 'clarify', text);
    assert.equal(result.readOnly, true, text);
  }
});
test('explicit transfer retains source destination and exact amount', () => {
  const result = parse('Move $50.25 from Product to Research');
  assert.equal(result.action, 'transfer'); assert.equal(result.amount, '50.25');
  assert.equal(result.sourceTeamId, 'product'); assert.equal(result.targetTeamId, 'research');
  assert.equal(parse('Move $50 from Product to Product').action, 'clarify');
  assert.equal(parse('Move $50 from Legal to Research').action, 'clarify');
});
test('an addition with no amount asks and a bare amount fills that draft', () => {
  const first = parse('Add funding to Research', {context:{scope_type:'company',forecast_run_id:'issued-1'}});
  assert.equal(first.action, 'clarify'); assert.equal(first.context.pending_slot, 'amount');
  const next = parse('50k', {context:first.context});
  assert.equal(next.action, 'addition'); assert.equal(next.amount, '50000'); assert.equal(next.targetTeamId, 'research');
  assert.equal(next.context.forecast_run_id, 'issued-1');
});
test('bare amounts without an action or selected proposal ask what change to make', () => {
  assert.equal(parse('50k').action, 'clarify'); assert.equal(parse('50k').context.pending_slot, 'change');
});
test('selected proposal identity and version direct an amount revision', () => {
  const result = parse('Make it 40k instead', {proposals:[proposal,{...proposal,id:'p2'}],context:{selected_proposal_id:'p1',selected_proposal_version:2}});
  assert.equal(result.action, 'addition'); assert.equal(result.amount, '40000'); assert.equal(result.reviseProposalId, 'p1'); assert.equal(result.targetTeamId,'research');
  assert.equal(parse('Make it 40k instead', {proposals:[proposal],context:{selected_proposal_id:'p1',selected_proposal_version:1}}).action,'clarify');
});
test('one open proposal can be revised while multiple drafts require selection', () => {
  assert.equal(parse('40k', {proposals:[proposal]}).reviseProposalId,'p1');
  const ambiguous=parse('Make it 40k instead',{proposals:[proposal,{...proposal,id:'p2'}]});
  assert.equal(ambiguous.action,'clarify'); assert.equal(ambiguous.context.pending_slot,'proposal');
});
test('pending team fills the same transfer and does not pick a default team', () => {
  const first=parse('Move $50 from Product');
  assert.equal(first.action,'clarify'); assert.equal(first.context.pending_slot,'team');
  const next=parse('Research',{context:first.context});
  assert.equal(next.action,'transfer'); assert.equal(next.amount,'50'); assert.equal(next.sourceTeamId,'product'); assert.equal(next.targetTeamId,'research');
});
test('explanation and scenario context cannot turn a numeric question into a budget change', () => {
  assert.equal(parse('Why did you add $50?', {context:{intent:'allocation',draft:{mode:'addition',amount:'100'}}}).action,'explain');
  assert.equal(parse('50k', {context:{intent:'explain',forecast_run_id:'r1'}}).readOnly,true);
  assert.equal(parse('Add $50', {context:{intent:'scenario'}}).readOnly,true);
});
test('date follow-ups never become dollar amount revisions',()=>{
 for(const text of ['Make it October 30 instead','Move the effective date to 2026-11-01','Make it tomorrow instead']) {
  const result=parse(text,{proposals:[proposal],context:{selected_proposal_id:'p1',pending_slot:'effective_date'}});
  assert.equal(result.readOnly,true,text); assert.equal(result.context.pending_slot,'effective_date',text);
 }
});
const uri = (s) => `data:text/javascript;base64,${Buffer.from(s).toString('base64')}`;
const helperUrl=uri(source);
const generatorSource=stripTypeScriptTypes(fs.readFileSync(new URL('../fixtures/generate.ts',import.meta.url),'utf8')).replaceAll('"@/lib/action-intent"',JSON.stringify(helperUrl));
const generatorUrl=uri(generatorSource);
const generated=await import(generatorUrl);
const fixtureSource=stripTypeScriptTypes(fs.readFileSync(new URL('../fixtures/index.ts',import.meta.url),'utf8')).replaceAll('"./generate"',JSON.stringify(generatorUrl)).replaceAll('"@/lib/action-intent"',JSON.stringify(helperUrl));
const fixture=await import(uri(fixtureSource));
const fixtureState={proposals:[],budgets:fixture.budgets,budgetVersion:'v1'};
for(const [label,reply] of [['Northstar',fixture.scriptedReply],['generated',generated.makeGenericReply(fixture.teams,fixture.forecasts,fixture.context,fixture.people)]]) {
 test(`${label} replies apply the validated intent boundary and exact financial constraints`,()=>{
  assert.equal(reply('Why did you add $50?',fixtureState).proposal,undefined);
  assert.equal(reply('Do not add funding',fixtureState).proposal,undefined);
  assert.equal(reply('Add -$50',fixtureState).proposal,undefined);
  const addition=reply('Add $50 to Research',fixtureState).proposal;
  assert.equal(addition.addedAmount,50); assert.equal(addition.totalAfter-addition.totalBefore,50);
  assert.equal(addition.lines.find(x=>x.teamId==='research').after-addition.lines.find(x=>x.teamId==='research').before,50);
  const transfer=reply('Do not add funding; move $50 from Product to Research',fixtureState).proposal;
  assert.equal(transfer.totalAfter,transfer.totalBefore);
  assert.equal(transfer.lines.find(x=>x.teamId==='product').after-transfer.lines.find(x=>x.teamId==='product').before,-50);
  assert.equal(transfer.lines.find(x=>x.teamId==='research').after-transfer.lines.find(x=>x.teamId==='research').before,50);
  assert.equal(reply('Move $90000 from Product to Research',fixtureState).proposal,undefined);
  const first=reply('Add funding to Research',fixtureState);
  assert.equal(first.proposal,undefined); assert.equal(first.message.conversationContext.pending_slot,'amount');
  const second=reply('50k',fixtureState,first.message.conversationContext);
  assert.equal(second.proposal.addedAmount,50000);
  const revision=reply('Make it 40k instead',{...fixtureState,proposals:[second.proposal]},{selected_proposal_id:second.proposal.id,selected_proposal_version:second.proposal.version});
  assert.equal(revision.proposal.addedAmount,40000); assert.equal(revision.proposal.revisesProposalId,second.proposal.id);
 });
}
test('non-dollar units percentages and ambiguous teams never become dollar proposals',()=>{
 for(const text of ['Add 50 credits','Add 50 tokens','Add €50','Add £50','Add 50%','Add $50 to Research and Product']) assert.equal(parse(text).readOnly,true,text);
});
test('explicit unknown revision teams do not silently retain old teams',()=>{
 const context={selected_proposal_id:'p1',draft:{mode:'addition',amount:'50',prioritize:'research'}};
 assert.equal(parse('Make it 40k for Legal instead',{context,proposals:[proposal]}).action,'clarify');
});
test('explanation context requires an explicit action before resuming a stale draft',()=>{
 const context={intent:'explain',selected_proposal_id:'p1',draft:{mode:'addition',amount:'50',prioritize:'research'}};
 assert.equal(parse('40k',{context,proposals:[proposal]}).readOnly,true);
 assert.equal(parse('Add $50',{context,proposals:[proposal]}).action,'addition');
});
test('fractional-cent allocation across many recipients never creates a negative addition',()=>{
 const many=Array.from({length:16},(_,i)=>({id:`team-${i}`,name:`Team ${i}`}));
 const reply=generated.makeGenericReply(many,many.map(t=>({teamId:t.id,status:'available',projected:2})),[]);
 const state={proposals:[],budgets:many.map(t=>({teamId:t.id,allocated:1})),budgetVersion:'v1'};
 const p=reply('Add $0.09',state).proposal;
 assert.ok(p.lines.every(line=>line.after>=line.before));
 assert.equal(Math.round(p.lines.reduce((sum,line)=>sum+line.after-line.before,0)*100),9);
});
test('a negated or unrelated follow-up never authorizes the pending addition',()=>{
 const context={intent:'allocation',pending_slot:'amount',draft:{mode:'addition',amount:'50',prioritize:'research'}};
 for(const text of ["Don't transfer 50k",'Do not allocate 50k','Ignore that','Research received 50k last week']) assert.equal(parse(text,{context,proposals:[proposal]}).readOnly,true,text);
});
test('structured allocation card period qualifiers retain dollars and validate the actual planning period',()=>{
 for(const reply of [fixture.scriptedReply,generated.makeGenericReply(fixture.teams,fixture.forecasts,fixture.context,fixture.people)]) {
  const command=`Move $40.00 from Product to Research for ${fixture.period.start} through ${fixture.period.end}. Keep the company budget unchanged. Prepare this transfer for review.`;
  const result=reply(command,fixtureState,{intent:'allocation',period:fixture.period.label});
  assert.equal(result.proposal?.kind,'redistribute'); assert.equal(result.proposal.totalAfter,result.proposal.totalBefore);
  assert.equal(result.proposal.lines.find(line=>line.teamId==='product').before-result.proposal.lines.find(line=>line.teamId==='product').after,40);
  const mismatched=reply(command.replace(fixture.period.start,'2020-01-01'),fixtureState,{intent:'allocation'});
  assert.equal(mismatched.proposal,undefined); assert.ok(mismatched.message.content);
 }
});
test('fixture factual replies return read-only context instead of retaining an older action draft',()=>{
 for(const reply of [fixture.scriptedReply,generated.makeGenericReply(fixture.teams,fixture.forecasts,fixture.context,fixture.people)]) {
  const first=reply('Add funding to Research',fixtureState);
  const explanation=reply('Why did you add funding to Research?',fixtureState,first.message.conversationContext);
  assert.equal(explanation.message.conversationContext?.intent,'explain');
  assert.equal(reply('50k',fixtureState,explanation.message.conversationContext).proposal,undefined);
 }
});
test('date clarification carries the original request into the selected scenario card',()=>{
 const first=parse('Move the start date to November 10, 2026',{context:{intent:'explain',forecast_run_id:'issued-1'}});
 assert.equal(first.context.intent,'scenario'); assert.equal(first.context.effective_date_text,'Move the start date to November 10, 2026');
 assert.equal(first.context.forecast_run_id,'issued-1');
 const next=parse('Make it two weeks later',{context:first.context});
 assert.equal(next.context.effective_date_text,'Make it two weeks later'); assert.equal(next.readOnly,true);
});
test('a complete new action clears a closed selection without inheriting its draft',()=>{
 for(const status of ['applied','rejected','revised','stale','failed','pending']) {
  const context={intent:'allocation',selected_proposal_id:'p1',selected_proposal_version:2,draft:{mode:'addition',amount:'50000',prioritize:'engineering'}};
  for(const [text,action] of [['Move $50 from Product to Research without adding funding','transfer'],['Add $50 for Research','addition']]) {
   const result=parse(text,{context,proposals:[{...proposal,status}]});
   assert.equal(result.action,action,`${status}: ${text}`); assert.equal(result.amount,'50');
   assert.equal(result.targetTeamId,'research'); assert.equal(result.reviseProposalId,undefined);
   assert.equal(result.context.selected_proposal_id,undefined); assert.equal(result.context.selected_proposal_version,undefined);
  }
 }
});
test('closed selections still reject revision wording and bare follow-ups',()=>{
 for(const status of ['applied','rejected','revised','stale','failed','pending']) {
  for(const text of ['Make it 40k instead','40k','Revise the proposal: add $50 for Research']) {
   const result=parse(text,{context:{selected_proposal_id:'p1',selected_proposal_version:2},proposals:[{...proposal,status}]});
   assert.equal(result.action,'clarify',`${status}: ${text}`); assert.equal(result.context.pending_slot,'proposal');
  }
 }
});
test('an open selected transfer card revises while a closed selected card starts a new proposal',()=>{
 const command=`Move $40.00 from Product to Research for ${fixture.period.start} through ${fixture.period.end}. Keep the company budget unchanged. Prepare this transfer for review.`;
 for(const reply of [fixture.scriptedReply,generated.makeGenericReply(fixture.teams,fixture.forecasts,fixture.context,fixture.people)]) {
  const context={intent:'allocation',selected_proposal_id:'p1',selected_proposal_version:2};
  const open=reply(command,{...fixtureState,proposals:[proposal]},context);
  assert.equal(open.proposal.revisesProposalId,'p1');
  const closed=reply(command,{...fixtureState,proposals:[{...proposal,status:'applied'}]},context);
  assert.equal(closed.proposal?.kind,'redistribute'); assert.equal(closed.proposal.revisesProposalId,undefined);
  assert.notEqual(closed.message.conversationContext.selected_proposal_id,'p1');
 }
});
test('a pending revision slot keeps a closed selection even for explicit action wording',()=>{
 for(const pending_slot of ['amount','team','change']) {
  for(const text of ['Add $50 for Research','Move $50 from Product to Research without adding funding']) {
   const result=parse(text,{context:{intent:'allocation',selected_proposal_id:'p1',selected_proposal_version:2,pending_slot},proposals:[{...proposal,status:'applied'}]});
   assert.equal(result.action,'clarify',`${pending_slot}: ${text}`);
   assert.equal(result.context.pending_slot,'proposal'); assert.equal(result.context.selected_proposal_id,'p1');
  }
 }
});
