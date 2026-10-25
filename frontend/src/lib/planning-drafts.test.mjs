import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { stripTypeScriptTypes } from 'node:module';
const source=stripTypeScriptTypes(fs.readFileSync(new URL('./planning-drafts.ts',import.meta.url),'utf8'));
const {resolvePlanningDate,buildScenarioDrivers,validateAllocationDraft,createScenarioDraft,scenarioComparison,scenarioDraftFromConversation}=await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);
const schedule={id:'launch',kind:'project_schedule',title:'Research launch',scope:{project_id:'p'},effective_from:'2026-10-20',parameters:{from_start:'2026-10-20',from_end:'2026-11-03',to_start:'2026-10-27'},citations:[{source_id:'doc'}]};
const unrelated={id:'price',kind:'pricing',scope:{billing_pool:'api'},effective_from:'2026-10-20',parameters:{rate:2,unit:'tokens',currency:'USD'}};
const view={run_id:'issued-1',scope:{type:'company',id:'co'},target:{unit:'usd'},included_drivers:[schedule,unrelated],daily:[],weekly:[],cumulative:[],queued_changes:[],limitations:[],quarter_outlook:{start:'2026-10-01',end:'2027-01-01',base:100}};
const bundle={views:[view]};
test('date resolution is concrete UTC, rejects ambiguous and invalid dates, and revises relative to the draft',()=>{
 assert.equal(resolvePlanningDate('November 10, 2026'),'2026-11-10');
 assert.equal(resolvePlanningDate('two weeks later','2026-11-10'),'2026-11-24');
 assert.equal(resolvePlanningDate('2026-11-10'),'2026-11-10');
 assert.throws(()=>resolvePlanningDate('11/10'),/year|YYYY/);
 assert.throws(()=>resolvePlanningDate('2026-02-30'),/valid/);
 assert.throws(()=>resolvePlanningDate('tomorrow'),/reference|year|YYYY/);
});
test('a schedule edit preserves every unrelated driver and the original source window without mutating the publication',()=>{
 const before=JSON.stringify(bundle);
 const draft={...createScenarioDraft(view,schedule),proposedStart:'2026-11-10'};
 const drivers=buildScenarioDrivers(bundle,draft);
 assert.equal(drivers.length,2);assert.deepEqual(drivers[1],unrelated);
 assert.equal(drivers[0].parameters.to_start,'2026-11-10');
 assert.equal(drivers[0].parameters.from_start,'2026-10-20');assert.equal(drivers[0].parameters.from_end,'2026-11-03');
 assert.equal(JSON.stringify(bundle),before);
});
test('scenario patches reject wrong parent, invalid ordering and unsupported fields',()=>{
 const workload={id:'load',kind:'workload',effective_from:'2026-10-25',effective_to:'2026-11-01',parameters:{exposure:2,unit:'work_units'}};
 const base={...view,included_drivers:[workload]}; const draft=createScenarioDraft(base,workload);
 assert.throws(()=>buildScenarioDrivers({views:[{...base,run_id:'new-issued'}]},draft),/same issued|parent/i);
 assert.throws(()=>buildScenarioDrivers({views:[base]},{...draft,proposedStart:'2026-11-02'}),/after|before/);
 assert.throws(()=>buildScenarioDrivers({views:[base]},{...draft,parameters:{increment:99}}),/supported/);
 assert.throws(()=>buildScenarioDrivers({views:[base]},{...draft,parameters:{exposure:-1}}),/nonnegative/);
});
test('scenario parameters preserve supplied bounds and require a supported scoped assumption',()=>{
 const driver={id:'bounded',kind:'workload',effective_from:'2026-10-25',parameters:{exposure:2,exposure_low:1,exposure_high:3,unit:'work_units'}};
 const base={...view,included_drivers:[driver]}; const draft=createScenarioDraft(base,driver);
 assert.throws(()=>buildScenarioDrivers({views:[base]},{...draft,parameters:{exposure:4}}),/bounds|range/);
 const updated=buildScenarioDrivers({views:[base]},{...draft,parameters:{exposure:4,exposure_high:5}});
 assert.equal(updated[0].parameters.exposure_low,1);assert.equal(updated[0].parameters.exposure_high,5);
 assert.throws(()=>buildScenarioDrivers({views:[base]},{...draft,scope:{type:'team',id:'other'}}),/scope/);
});
test('exact allocation transfer validates cents, source availability and matching period without applying it',()=>{
 const draft={kind:'allocation',id:'a',sourceTeamId:'a',destinationTeamId:'b',amount:'5000.25',unit:'usd',period:{start:'2026-10-01',end:'2026-10-31'}};
 const budgets=['a','b'].map(teamId=>({teamId,unit:'usd',allocated:10000,period:draft.period}));
 assert.equal(validateAllocationDraft(draft,budgets).amount,5000.25);
 assert.equal(validateAllocationDraft(draft,budgets).companyChange,0);
 assert.throws(()=>validateAllocationDraft({...draft,amount:'5,000.255'},budgets),/decimal|amount/);
 assert.throws(()=>validateAllocationDraft({...draft,destinationTeamId:'a'},budgets),/different/);
 assert.throws(()=>validateAllocationDraft({...draft,amount:'10000.01'},budgets),/available/);
 assert.throws(()=>validateAllocationDraft({...draft,period:{start:'2026-11-01',end:'2026-11-30'}},budgets),/period/);
});
test('scenario comparison never substitutes a different scope, target, horizon or issued parent',()=>{
 const scenario={...view,run_id:'scenario-1',quarter_outlook:{...view.quarter_outlook,base:80}};
 assert.equal(scenarioComparison(view,{parent_run_id:'issued-1',views:[scenario]}).delta,-20);
 assert.throws(()=>scenarioComparison(view,{parent_run_id:'issued-2',views:[scenario]}),/parent/);
 assert.equal(scenarioComparison(view,{views:[{...scenario,scope:{type:'team',id:'t'}}]}).available,false);
 assert.equal(scenarioComparison(view,{views:[{...scenario,target:{unit:'tokens'}}]}).available,false);
 assert.equal(scenarioComparison(view,{views:[{...scenario,quarter_outlook:{...scenario.quarter_outlook,end:'2026-11-01'}}]}).available,false);
});
test('selected forecast assumption produces a dated card and relative follow-up revises the same draft',()=>{
 const forecastContext={action:'explain',run_id:'issued-1',scope_type:'company',scope_id:'co',driver_id:'launch'};
 const draft=scenarioDraftFromConversation({bundle,forecastContext,context:{intent:'scenario',effective_date_text:'Move the project start to November 10'}});
 assert.equal(draft.proposedStart,'2026-11-10');assert.equal(draft.driverId,'launch');assert.equal(draft.parentRunId,'issued-1');
 const revised=scenarioDraftFromConversation({bundle,forecastContext,context:{intent:'scenario',effective_date_text:'make it two weeks later'},previousDraft:draft});
 assert.equal(revised.proposedStart,'2026-11-24');assert.equal(revised.id,draft.id);assert.equal(revised.revision,draft.revision+1);
 assert.equal(scenarioDraftFromConversation({bundle,forecastContext:{...forecastContext,driver_id:undefined},context:{intent:'scenario',effective_date_text:'November 10'}}),undefined);
 assert.equal(scenarioDraftFromConversation({bundle,forecastContext:{...forecastContext,run_id:'new-run'},context:{intent:'scenario',effective_date_text:'November 10'}}),undefined);
 assert.equal(scenarioDraftFromConversation({bundle,forecastContext,context:{intent:'allocation',effective_date_text:'November 10'}}),undefined);
});
