import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { stripTypeScriptTypes } from 'node:module';
const source=stripTypeScriptTypes(fs.readFileSync(new URL('./overview-priorities-derive.ts',import.meta.url),'utf8'));
const {buildOverviewPriorities}=await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);
const period={start:'2026-10-19',end:'2026-10-25'};
const teams=[{id:'r',name:'Research'},{id:'e',name:'Engineering'},{id:'p',name:'Product'}];
const summary=(variance)=>({variance});
const item=(id,extra={})=>({id,title:id,summary:'Source-backed plan',teamIds:['p'],scope:'team',sources:[{documentId:id,title:id}],effectiveFrom:'2026-10-26',claimType:'stated_plan',category:'staffing',...extra});
const input={summaries:[{team:teams[0],summary:summary(25000)},{team:teams[1],summary:summary(5000)},{team:teams[2],summary:summary(-30000)}],proposals:[],context:[item('pricing',{scope:'company',category:'pricing',teamIds:[]}),item('absence')],teams,period,unit:'usd',asOf:'2026-10-25'};
test('Northstar-style priorities show exact-period overspend plus dated source context without inventing impacts',()=>{
 const priorities=buildOverviewPriorities(input);
 assert.equal(priorities.length,4);
 assert.deepEqual(priorities.map(p=>p.kind),['budget','budget','context','context']);
 assert.deepEqual(priorities.slice(0,2).map(p=>p.amount),[25000,5000]);
 assert.equal(priorities[2].sources[0].id,'pricing');
 assert.ok(priorities.slice(2).every(p=>p.amount===undefined));
});
test('unknown variance, old/undated/unknown-scope/superseded/interpretation context cannot become a priority',()=>{
 const priorities=buildOverviewPriorities({...input,summaries:[{team:teams[0],summary:summary(null)}],context:[item('old',{effectiveFrom:'2026-10-25'}),item('far',{effectiveFrom:'2026-12-01'}),item('unknown',{teamIds:[]}),item('superseded',{supersededBy:'new'}),item('inference',{claimType:'interpretation'}),item('undated',{effectiveFrom:undefined})]});
 assert.deepEqual(priorities,[]);
});
test('only actionable proposal statuses for the exact target add grouped review work',()=>{
 const proposal=(id,status,extra={})=>({id,status,period,unit:'usd',...extra});
 const priorities=buildOverviewPriorities({...input,proposals:[proposal('review','proposed'),proposal('saved','applied'),proposal('old','proposed',{period:{start:'2026-10-01',end:'2026-12-31'}})]});
 assert.equal(priorities.length,5);
 assert.deepEqual(priorities[2].proposals.map(p=>p.id),['review']);
 assert.match(priorities[2].title,/1 budget proposal needs review/);
});
test('related dated context is grouped; default never expands beyond five priorities',()=>{
 const priorities=buildOverviewPriorities({...input,context:[item('a'),item('b'),item('c',{category:'pricing'}),item('d',{category:'policy'}),item('e',{category:'model'})]});
 assert.equal(priorities.length,5);
 const staffing=priorities.find(p=>p.sources.some(s=>s.id==='a'));
 assert.equal(staffing.sources.length,2);
});
test('default Northstar fixture yields budget exceptions and two upcoming source-backed changes',async()=>{
 const {tsModuleUrl}=await import('../../../tests/load-ts-module.mjs');
 const {northstar}=await import(tsModuleUrl(new URL('../../fixtures/index.ts',import.meta.url)));
 const {syntheticForecastBundle}=await import(tsModuleUrl(new URL('../../lib/data/mock-forecast.ts',import.meta.url)));
 const {selectScopeSummary}=await import(tsModuleUrl(new URL('../../lib/finance-summary.ts',import.meta.url)));
 const bundle=syntheticForecastBundle(northstar);
 const period=northstar.company.currentPeriod;
 const summaries=northstar.teams.map(team=>({team,summary:selectScopeSummary({scope:{type:'team',id:team.id},period,unit:'usd',datasetId:northstar.company.id,spending:northstar.spending,budgets:northstar.budgets,forecastView:bundle.views.find(view=>view.scope.type==='team'&&view.scope.id===team.id)})}));
 const priorities=buildOverviewPriorities({summaries,teams:northstar.teams,context:northstar.context,proposals:northstar.proposals,period,unit:'usd',asOf:'2026-10-25'});
 assert.deepEqual(priorities.filter(p=>p.kind==='budget').map(p=>[p.team.id,p.amount]),[['research',25000],['engineering',5000]]);
 assert.deepEqual(priorities.filter(p=>p.kind==='context').flatMap(p=>p.sources.map(s=>s.id)),['ctx-company-pricing-update','ctx-product-theo-b-ooo']);
 assert.equal(priorities.length,4);
});
test('connected upcoming issued drivers fill remaining priorities with no inferred dollar amount',()=>{
 const insight=(id,status='included',inSnapshot=true)=>({driver:{id},title:id,status,inSnapshot});
 const priorities=buildOverviewPriorities({...input,summaries:[],context:[],scheduledDrivers:[{insight:insight('next'),start:'2026-10-28'},{insight:insight('queued','queued'),start:'2026-10-29'},{insight:insight('past'),start:'2026-10-24'},{insight:insight('unknown','unknown_scope'),start:'2026-10-28'},{insight:insight('outside','included',false),start:'2026-10-28'}]});
 assert.deepEqual(priorities.map(priority=>priority.id),['driver:next','driver:queued']);
 assert.ok(priorities.every(priority=>priority.amount===undefined));
});
