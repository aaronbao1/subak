import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { stripTypeScriptTypes } from 'node:module';
const source = stripTypeScriptTypes(fs.readFileSync(new URL('./finance-summary.ts',import.meta.url),'utf8'));
const {billableAmount, canCompareTargets, comparisonTarget, selectScopeSummary} = await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);
const scope={type:'company',id:'c'}, period={start:'2026-10-19',end:'2026-10-25'};
const target=comparisonTarget({scope,period,unit:'usd',datasetId:'c'});
const row=(extra={})=>({teamId:'t',date:'2026-10-23',component:'api',amount:10,unit:'usd',complete:true,provenance:'reported_charge',...extra});
const view=(extra={})=>({run_id:'r',scope,target:{unit:'USD',basis:'planning',timezone:'UTC'},planning_period_outlook:{start:period.start,end:'2026-10-26',base:100},...extra});
const input={scope,period,unit:'usd',datasetId:'c',spending:[row()],budgets:[{teamId:'t',period,unit:'usd',allocated:80}],forecastView:view()};
test('included notional and usage-only records add no billable dollars; every cost provenance retained',()=>{
 assert.equal(billableAmount(row({component:'included_usage',amount:999})),0);
 assert.equal(billableAmount(row({component:'unpriced_usage',amount:999})),0);
 assert.equal(billableAmount(row({provenance:'usage_only',amount:999})),0);
 for(const provenance of ['reported_charge','estimate','measured','simulated']) assert.equal(billableAmount(row({provenance})),10);
 const summary=selectScopeSummary({...input,spending:['reported_charge','estimate','measured','simulated'].map(provenance=>row({provenance})).concat(row({component:'included_usage',amount:999,provenance:'usage_only'}))});
 assert.equal(summary.observed.amount,40);assert.equal(summary.observed.includedNotional,999);assert.equal(summary.observed.byProvenance.simulated,10);
});
test('variance requires exact target including date scope unit basis dataset; absent allocation remains unknown',()=>{
 assert.equal(canCompareTargets(target,{...target,endDateExclusive:'2027-01-01'}),false);
 for(const change of [{scope:{type:'team',id:'t'}},{unit:'tokens'},{basis:'reported'},{datasetId:'other'},{startDate:''}]) assert.equal(canCompareTargets(target,{...target,...change}),false);
 assert.equal(selectScopeSummary(input).variance,20);
 assert.equal(selectScopeSummary({...input,budgets:[]}).allocation,null);
 assert.equal(selectScopeSummary({...input,budgets:[{...input.budgets[0],period:{start:'2026-10-01',end:'2026-12-31'}}]}).variance,null);
 assert.equal(selectScopeSummary({...input,forecastView:view({planning_period_outlook:undefined,quarter_outlook:{start:'2026-10-01',end:'2027-01-01',base:1000}})}).issued.amount,null);
});
test('company view is authoritative and unmatched or unknown values never become zero',()=>{
 assert.equal(selectScopeSummary({...input,forecastView:view({planning_period_outlook:{start:period.start,end:'2026-10-26',base:null}})}).issued.amount,null);
 assert.equal(selectScopeSummary({...input,forecastView:view({scope:{type:'team',id:'t'}})}).issued.amount,null);
 assert.equal(selectScopeSummary({...input,spending:[]}).observed.amount,null);
 assert.equal(selectScopeSummary({...input,spending:[row({amount:0})]}).observed.amount,0);
 assert.equal(selectScopeSummary({...input,scope:{type:'person',id:'p'},spending:[row({personId:'p'})]}).allocation,null);
});
test('observations are scoped to exact period and currency and rounded only at money precision',()=>{
 const summary=selectScopeSummary({...input,spending:[row({amount:0.1}),row({amount:0.2}),row({date:'2026-10-26',amount:50}),row({unit:'credits',amount:50})]});
 assert.equal(summary.observed.amount,0.3);
});
