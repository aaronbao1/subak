import test from 'node:test';
import assert from 'node:assert/strict';
import { tsModuleUrl } from '../../../tests/load-ts-module.mjs';
const { buildAssistantAnswer, cleanAssistantPresentation, formatAssistantAmount } = await import(tsModuleUrl(new URL('./assistant-answer-model.ts', import.meta.url)));
const message={id:'m',threadId:'main',role:'assistant',createdAt:'2026-10-25T12:00:00Z',content:'A complete explanation with its limitations.'};
const proposal={id:'p',kind:'add_budget',unit:'usd',period:{start:'2026-10-19',end:'2026-10-25',label:'This week'},totalBefore:0.3,totalAfter:0.4,addedAmount:0.1,lines:[{teamId:'research',before:0.3,after:0.4}],rationale:'Original rationale',citations:[],createdAt:message.createdAt,status:'proposed'};
const teams=[{id:'research',name:'Research'}];
const model=(m=message,p,action)=>buildAssistantAnswer({message:m,proposal:p,proposalAction:action,teams});

test('general narratives remain complete without extracting misleading first-sentence financial summaries',()=>{
 const content=`All spending appears within plan. ${'The current-day source remains incomplete and the forecast is not calibrated. '.repeat(6)}`;
 const answer=model({...message,content,conversationContext:{intent:'explain'}});
 assert.equal(answer.headline,'Spending analysis');assert.equal(answer.summary,null);assert.equal(answer.body,content);assert.equal(answer.bodyMode,'details');assert.equal(answer.allocation,undefined);
 const short=model({...message,content:'Spending is $50 so far, but the source is incomplete.'});assert.equal(short.bodyMode,'inline');assert.equal(short.body,'Spending is $50 so far, but the source is incomplete.');assert.equal(short.allocation,undefined);
 assert.equal(model({...message,content:'First paragraph.\n\nMaterial qualification.'}).bodyMode,'details');
});

test('all typed pending slots display the intact clarification regardless of length',()=>{
 for(const slot of ['amount','team','change','proposal','effective_date']){
  const content=`Before continuing, clarify ${slot}. ${'Do not assume this has changed the budget. '.repeat(12)}`;
  const answer=model({...message,content,conversationContext:{intent:'allocation',pending_slot:slot}});
  assert.equal(answer.kind,'clarification');assert.equal(answer.clarification.slot,slot);assert.ok(answer.clarification.label);assert.equal(answer.bodyMode,'inline');assert.equal(answer.body,content);assert.equal(answer.summary,null);
 }
});

test('only the matching typed proposal supplies exact allocation facts and unambiguous period dates',()=>{
 const answer=model({...message,proposalId:'p',content:'Pretend the amount is $999,999.'},proposal);
 assert.equal(answer.kind,'proposal');assert.equal(answer.proposalId,'p');assert.equal(answer.allocation.before,'0.30');assert.equal(answer.allocation.after,'0.40');assert.equal(answer.allocation.delta,'0.10');assert.equal(answer.allocation.lines[0].delta,'0.10');assert.equal(answer.allocation.lines[0].teamName,'Research');
 assert.equal(answer.allocation.period.start,'2026-10-19');assert.equal(answer.allocation.period.end,'2026-10-25');assert.match(answer.allocation.period.label,/Oct 19, 2026/);assert.match(answer.allocation.period.label,/Oct 25, 2026/);
 assert.equal(model({...message,proposalId:'other'},proposal).allocation,undefined);
 assert.equal(model({...message,conversationContext:{selected_proposal_id:'p',intent:'explain'}},proposal).allocation,undefined);
 assert.equal(formatAssistantAmount('12345.67','usd'),'$12,345.67');assert.equal(formatAssistantAmount('-0.10','usd'),'−$0.10');assert.equal(formatAssistantAmount('2500.00','tokens'),'2,500 tokens');
});

test('nonfinite, unsafe, fractional-cent and unconserved proposals withhold financial cards',()=>{
 for(const patch of [{totalAfter:NaN},{totalAfter:0.401},{totalAfter:1e20},{totalAfter:0.5},{lines:[{teamId:'research',before:0.3,after:0.401}]}]){
  const answer=model({...message,proposalId:'p'},{...proposal,...patch});assert.equal(answer.allocation,undefined);assert.match(answer.notice,/verify|verification|exact/i);
 }
 assert.equal(model({...message,proposalId:'p'},{...proposal,kind:'redistribute'}).allocation,undefined);
});

test('proposal terminal states and pending mutations never appear ready for approval',()=>{
 const expected={applied:'Applied',rejected:'Rejected',stale:'Outdated',revised:'Revised',failed:'Unavailable',pending:'Saving'};
 for(const [status,label] of Object.entries(expected))assert.equal(model({...message,proposalId:'p'},{...proposal,status}).status,label);
 const pending=model({...message,proposalId:'p'},proposal,{operationId:'o',action:'reject',mutation:'pending',sync:'idle'});assert.equal(pending.status,'Saving');assert.match(pending.headline,/rejection/i);assert.doesNotMatch(pending.headline,/ready/i);
 const unknown=model({...message,proposalId:'p'},proposal,{operationId:'o',action:'apply',mutation:'unknown',sync:'idle'});assert.equal(unknown.status,'Confirmation needed');assert.match(unknown.summary,/may have been recorded/);assert.doesNotMatch(`${unknown.headline} ${unknown.summary} ${unknown.notice}`,/unchanged|not applied/i);
});

test('confirmed receipts outrank stale proposal summaries and refresh failures retain confirmation',()=>{
 const receipt={id:'decision',proposalId:'p',action:'applied',kind:'add_budget',unit:'usd',lines:[{teamId:'research',before:0.3,after:0.35}],appliedAt:message.createdAt,appliedBy:'Finance'};
 const answer=model({...message,proposalId:'p'},{...proposal,status:'stale'},{operationId:'o',action:'apply',mutation:'confirmed',sync:'failed',receipt,syncError:'Totals are unavailable.'});
 assert.equal(answer.status,'Applied');assert.match(answer.headline,/applied/i);assert.match(answer.notice,/saved|confirmed/i);assert.match(answer.notice,/Totals are unavailable/);assert.equal(answer.allocation.after,'0.35');assert.equal(answer.allocation.delta,'0.05');
 const receiptWins=model({...message,proposalId:'p'},proposal,{operationId:'o',action:'apply',mutation:'unknown',sync:'failed',receipt});assert.equal(receiptWins.status,'Applied');assert.equal(receiptWins.allocation.after,'0.35');
 const rejected=model({...message,proposalId:'p'},proposal,{operationId:'o',action:'reject',mutation:'confirmed',sync:'synced',receipt:{...receipt,action:'rejected'}});assert.equal(rejected.status,'Rejected');
 const mismatch=model({...message,proposalId:'p'},proposal,{operationId:'o',action:'apply',mutation:'confirmed',sync:'synced',receipt:{...receipt,proposalId:'other'}});assert.notEqual(mismatch.status,'Applied');
});

test('typed scenario and allocation drafts do not invent forecast results or before/after allocations',()=>{
 const scenario=model({...message,actionDraft:{kind:'scenario',id:'s',parentRunId:'run',scope:{type:'team',id:'research'},driverId:'driver',title:'Move plan',proposedStart:'2026-11-01',parameters:{cost:500}}});
 assert.equal(scenario.kind,'scenario');assert.match(scenario.headline,/preview/i);assert.equal(scenario.allocation,undefined);assert.doesNotMatch(scenario.summary??'',/500/);
 const transfer=model({...message,actionDraft:{kind:'allocation',id:'a',sourceTeamId:'research',destinationTeamId:'product',amount:'50.00',unit:'usd',period:proposal.period}});assert.equal(transfer.kind,'allocation_draft');assert.equal(transfer.allocation,undefined);
 const selectedOnly=model({...message,conversationContext:{intent:'scenario'}});assert.equal(selectedOnly.kind,'answer');assert.doesNotMatch(selectedOnly.headline,/ready|complete/i);
});

test('known provenance copy cleanup retains every financial limitation and approval qualifier',()=>{
 const note='_Simulated: this reply comes from the deterministic fake Droid runner (a scripted playbook, not a model). Proposals still need a finance approver._';
 const content=`This is a synthetic UI fixture for issued run **run-1**. The interface uses a constant observed-rate illustration. Historical error intervals and source-derived numerical effects are unavailable in this mock. Connect the backend fixture pipeline for cited calculations and paired reruns.\n\n${note}`;
 const cleaned=cleanAssistantPresentation(content);
 assert.doesNotMatch(cleaned,/synthetic UI fixture|scripted playbook|fake Droid runner|in this mock|backend fixture/i);
 for(const qualification of ['constant observed-rate illustration','Historical error intervals and source-derived numerical effects are unavailable','Proposals still need a finance approver'])assert.ok(cleaned.includes(qualification));
 assert.equal(cleanAssistantPresentation('Synthetic fixture only; no production forecast or calibration was executed.'),'No production forecast or calibration was executed.');
});

test('presentation cleanup protects quoted text, code, links, business words and immutable message data',()=>{
 const protectedText='"Synthetic demo: retain this quote."\n> Synthetic demo: quoted source\n`Synthetic demo: literal`\n```text\nSynthetic fixture only; literal.\n```\n[Scripted assistant](https://example.test/demo)\nThe team scheduled a demo. Synthetic controls are unavailable.';
 assert.equal(cleanAssistantPresentation(protectedText),protectedText);
 const original={...message,proposalId:'p',content:'Synthetic demo: Source coverage is partial.'};const before=JSON.stringify({original,proposal});const answer=model(original,proposal);assert.equal(answer.body,'Source coverage is partial.');assert.equal(JSON.stringify({original,proposal}),before);
});

test('actual runner copy loses only runner labels while keeping unsupported-analysis limitations',()=>{
 const source='2 current source updates need review; the scripted assistant has not inferred a numerical effect from them.';
 assert.equal(cleanAssistantPresentation(source),'2 current source updates need review; the assistant has not inferred a numerical effect from them.');
 const limitation='Limitation: the deterministic fake runner does not interpret free-text questions; this is the standard per-team comparison. Analyses beyond it (for example token multipliers or scenarios the forecast provider does not supply) are not computed.';
 assert.equal(cleanAssistantPresentation(limitation),'Limitation: the assistant does not interpret free-text questions; this is the standard per-team comparison. Analyses beyond it (for example token multipliers or scenarios the forecast provider does not supply) are not computed.');
 const ordinary='The scripted assistant project costs $50; the deterministic fake runner test requires two days.';assert.equal(cleanAssistantPresentation(ordinary),ordinary);
});

test('only the known pinned fixture introduction becomes a selected-forecast reference',()=>{
 const tail=' The interface uses a constant observed-rate illustration. Historical error intervals and source-derived numerical effects are unavailable in this mock.';
 for(const scope of ['team **research**','company **northstar**, driver **driver-1**']){
  const content=`This is a synthetic UI fixture for issued run **synthetic-ui-run-1**, ${scope}.${tail}`;
  assert.equal(cleanAssistantPresentation(content),'This explanation uses the selected forecast. The interface uses a constant observed-rate illustration. Historical error intervals and source-derived numerical effects are unavailable.');
 }
 const ordinary='For issued run **run-2026**, team **Research**. Actual charges are $50 with partial coverage.';assert.equal(cleanAssistantPresentation(ordinary),ordinary);
});

test('long general answer exposes an intact first paragraph with qualifiers and retains the complete answer',()=>{
 const first='The $50 forecast is conditional on complete source coverage; the current day remains partial.';
 const content=`## Spending outlook\n\n${first}\n\n${'Additional source detail. '.repeat(25)}Do not treat this as an approved budget.`;
 const answer=model({...message,content,conversationContext:{intent:'explain'}});
 assert.equal(answer.preview,`## Spending outlook\n\n${first}`);assert.equal(answer.body,content);assert.equal(answer.allocation,undefined);assert.equal(answer.summary,null);
 assert.equal(model({...message,content,conversationContext:{pending_slot:'amount'}}).preview,undefined);
 assert.equal(model({...message,content,proposalId:'p'},proposal).preview,undefined);
});

test('real read-only intent preface stays in details while preview starts at the substantive qualified answer',()=>{
 const preface='**Read as:** a question about spend, budgets and projections (read-only).';
 const answerText='Research is projected above its allocation, but source coverage is partial and the open requests remain unapproved.';
 const content=`${preface}\n\n${answerText}\n\nAdditional calculations and source details.`;
 const answer=model({...message,content,conversationContext:{intent:'explain'}});
 assert.equal(answer.preview,answerText);assert.equal(answer.body,content);assert.equal(answer.allocation,undefined);
 const qualified=model({...message,content:`${preface}\n\nCoverage is incomplete; do not treat this as a final comparison.\n\n${answerText}`});
 assert.equal(qualified.preview,'Coverage is incomplete; do not treat this as a final comparison.');
});

test('known projection label becomes estimates while method, partial coverage and raw quotes stay intact',()=>{
 const original='Projections are simulated (observed-rate baseline with conditional plan adjustments), not measured spend; partial: no projection for Research.';
 const expected='Projections are estimates (observed-rate baseline with conditional plan adjustments), not measured spend; partial: no projection for Research.';
 assert.equal(cleanAssistantPresentation(original),expected);
 assert.equal(cleanAssistantPresentation(`"${original}"`),`"${original}"`);
 assert.equal(cleanAssistantPresentation('The research team simulated three model configurations.'),'The research team simulated three model configurations.');
});
