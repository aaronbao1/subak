import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { stripTypeScriptTypes } from 'node:module';
const source=stripTypeScriptTypes(fs.readFileSync(new URL('./allocation-workbench.ts',import.meta.url),'utf8'));
const {prepareAllocationRequest,checkPreparedAllocation}=await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);
const intentSource=stripTypeScriptTypes(fs.readFileSync(new URL('./action-intent.ts',import.meta.url),'utf8'));
const {interpretActionIntent}=await import(`data:text/javascript;base64,${Buffer.from(intentSource).toString('base64')}`);
const period={start:'2026-10-19',end:'2026-10-25',label:'Oct 19–25'};
const teams=[{id:'research',name:'Research'},{id:'product',name:'Product'}];
const budgets=[{teamId:'research',period,unit:'usd',allocated:60000},{teamId:'product',period,unit:'usd',allocated:80000}];
const draft={mode:'transfer',sourceTeamId:'product',targetTeamId:'research',amount:'5000.25',unit:'usd',period};
test('transfer preview preserves cents, exact source/destination and a constant company envelope',()=>{
 const request=prepareAllocationRequest(draft,{teams,budgets});
 assert.equal(request.amount,'5000.25');assert.equal(request.companyBefore,140000);assert.equal(request.companyAfter,140000);
 assert.deepEqual(request.changes,[{teamId:'product',before:80000,after:74999.75},{teamId:'research',before:60000,after:65000.25}]);
 assert.match(request.content,/Move \$5000.25 from Product to Research for 2026-10-19 through 2026-10-25/);
 assert.equal(prepareAllocationRequest({...draft,amount:'5,000.25'},{teams,budgets}).amount,'5000.25');
});
test('addition previews only envelope and states team priority without promising a split',()=>{
 const request=prepareAllocationRequest({...draft,mode:'addition',amount:'50000'},{teams,budgets});
 assert.equal(request.companyAfter,190000);assert.deepEqual(request.changes,[]);
 assert.match(request.content,/Add \$50000.00.*prioritiz.*Research/);
});
test('invalid amounts, same team, insufficient allocation, units and mismatched periods cannot be drafted',()=>{
 for(const amount of ['0','-1','5000.255','NaN','1e4','50,00'])assert.throws(()=>prepareAllocationRequest({...draft,amount},{teams,budgets}),/amount|decimal/);
 assert.throws(()=>prepareAllocationRequest({...draft,amount:'80000.01'},{teams,budgets}),/allocation/);
 assert.throws(()=>prepareAllocationRequest({...draft,sourceTeamId:'research'},{teams,budgets}),/different/);
 assert.throws(()=>prepareAllocationRequest({...draft,unit:'credits'},{teams,budgets}),/USD/);
 assert.throws(()=>prepareAllocationRequest({...draft,period:{...period,start:'2026-10-20'}},{teams,budgets}),/period/);
});
test('returned transfer must match requested teams cents period and complete envelope before review',()=>{
 const request=prepareAllocationRequest(draft,{teams,budgets});
 const proposal={id:'p',kind:'redistribute',unit:'usd',period,totalBefore:140000,totalAfter:140000,lines:[{teamId:'product',before:80000,after:74999.75},{teamId:'research',before:60000,after:65000.25}]};
 assert.equal(checkPreparedAllocation(request,proposal).matches,true);
 assert.equal(checkPreparedAllocation(request,{...proposal,lines:[{teamId:'product',before:80000,after:79000},{teamId:'research',before:60000,after:61000}]}).matches,false);
 assert.equal(checkPreparedAllocation(request,{...proposal,period:{...period,end:'2026-11-01'}}).matches,false);
 assert.equal(checkPreparedAllocation(request,{...proposal,totalAfter:145000}).matches,false);
});
test('a recommended addition may split across teams but must preserve the authorized total',()=>{
 const request=prepareAllocationRequest({...draft,mode:'addition',amount:'50000'},{teams,budgets});
 const proposal={id:'p',kind:'add_budget',unit:'usd',period,totalBefore:140000,totalAfter:190000,addedAmount:50000,lines:[{teamId:'product',before:80000,after:95000},{teamId:'research',before:60000,after:95000}]};
 assert.equal(checkPreparedAllocation(request,proposal).matches,true);
 assert.equal(checkPreparedAllocation(request,{...proposal,totalAfter:200000,addedAmount:60000}).matches,false);
});
test('form requests pass the real intent boundary with period dates and exact monetary action',()=>{
 for(const mode of ['transfer','addition']){
  const request=prepareAllocationRequest({...draft,mode},{teams,budgets});
  const intent=interpretActionIntent(request.content,teams,{planningPeriod:period,context:{intent:'allocation'}});
  assert.equal(intent.action,mode);assert.equal(intent.amount,'5000.25');assert.equal(intent.targetTeamId,'research');
  if(mode==='transfer')assert.equal(intent.sourceTeamId,'product');
 }
});
const loadTargets=async()=>await import(`data:text/javascript;base64,${Buffer.from(stripTypeScriptTypes(fs.readFileSync(new URL('./allocation-targets.ts',import.meta.url),'utf8'))).toString('base64')}`);
test('all-team target drafts retain exact decimals and selected budget version without changing source rows',async()=>{
 const {prepareAllocationTargets}=await loadTargets();
 const sourceBudgets=budgets.map(b=>({...b,version:'v7'}));
 const result=prepareAllocationTargets({research:'65000.25',product:'74999.75'},{budgets:sourceBudgets,teams,period,unit:'usd'});
 assert.deepEqual(result.input.allocations,{research:'65000.25',product:'74999.75'});
 assert.equal(result.input.baseVersion,7);assert.equal(result.input.periodEndExclusive,'2026-10-26');
 assert.equal(result.companyBefore,140000);assert.equal(result.companyAfter,140000);
 assert.equal(sourceBudgets[0].allocated,60000);
});
test('all-team target input requires complete same-period rows and does not hide mixed additions and cuts',async()=>{
 const {prepareAllocationTargets}=await loadTargets();const sourceBudgets=budgets.map(b=>({...b,version:'v7'}));
 for(const targets of [{research:'65000'}, {research:'65000',product:'-1'}, {research:'60000',product:'80000'}, {research:'65000',product:'79000'}])assert.throws(()=>prepareAllocationTargets(targets,{budgets:sourceBudgets,teams,period,unit:'usd'}));
 assert.throws(()=>prepareAllocationTargets({research:'65000',product:'75000'},{budgets:[sourceBudgets[0],{...sourceBudgets[1],version:'v8'}],teams,period,unit:'usd'}),/version/);
 const addition=prepareAllocationTargets({research:'65000',product:'80000'},{budgets:sourceBudgets,teams,period,unit:'usd'});
 assert.equal(addition.companyAfter,145000);assert.equal(addition.kind,'addition');
});
test('authoritative returned all-team draft must match all targets and original snapshots',async()=>{
 const {prepareAllocationTargets,checkAllocationTargets}=await loadTargets();
 const prepared=prepareAllocationTargets({research:'65000.25',product:'74999.75'},{budgets:budgets.map(b=>({...b,version:'v7'})),teams,period,unit:'usd'});
 const proposal={unit:'usd',period,totalBefore:140000,totalAfter:140000,lines:prepared.changes};
 assert.equal(checkAllocationTargets(prepared,proposal).matches,true);
 assert.equal(checkAllocationTargets(prepared,{...proposal,lines:prepared.changes.slice(0,1)}).matches,false);
 assert.equal(checkAllocationTargets(prepared,{...proposal,lines:prepared.changes.map(l=>({...l,after:l.after+1}))}).matches,false);
});
test('native allocation state supplies exact matching period rows and version; stale period is excluded',async()=>{
 const {allocationStateRows}=await loadTargets();
 const state={period:{startDate:'2026-10-19',endDateExclusive:'2026-10-26'},unit:'USD',stateVersion:9,allocations:[{teamId:'research',amount:'65000.25'},{teamId:'product',amount:'74999.75'}]};
 const rows=allocationStateRows(state,period,'usd');
 assert.equal(rows[0].allocated,65000.25);assert.equal(rows[0].version,'9');
 assert.equal(allocationStateRows({...state,period:{...state.period,endDateExclusive:'2026-10-27'}},period,'usd'),undefined);
 assert.equal(allocationStateRows(state,period,'credits'),undefined);
});
