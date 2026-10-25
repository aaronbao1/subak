import test from 'node:test';
import assert from 'node:assert/strict';
import {tsModuleUrl} from '../../../tests/load-ts-module.mjs';
const {syntheticForecastBundle} = await import(tsModuleUrl(new URL('./mock-forecast.ts',import.meta.url)));
const fx={company:{id:'c',name:'C',budgetUnit:'usd',currentPeriod:{start:'2026-10-01',end:'2026-12-31'}},teams:[{id:'t',name:'T'}],people:[{id:'p',teamId:'t',name:'P'}],spending:[{date:'2026-10-22',teamId:'t',personId:'p',complete:true,amount:20},{date:'2026-10-23',teamId:'t',complete:true,amount:10},{date:'2026-10-23',complete:true,amount:5}]};
test('synthetic UI scopes reconcile without inventing person allocation',()=>{
 const {views}=syntheticForecastBundle(fx);
 const base=(type,id)=>views.find(v=>v.scope.type===type && v.scope.id===id).planning_period_outlook.base;
 assert.equal(base('company','c'),base('team','t')+base('shared','shared'));
 assert.equal(base('company','c'),base('person','p')+base('shared','shared')+base('shared','people_unallocated'));
 assert.equal(views[0].is_synthetic,true); assert.equal(views[0].historical_error_interval,null);
});
test('manual Sunday run has one-day partial first week and seven daily details',()=>{
 const view=syntheticForecastBundle(fx).views[0];
 assert.equal(view.daily.length,7);assert.equal(view.weekly.length,4);
 assert.equal(view.weekly[0].start,'2026-10-25');assert.equal(view.weekly[0].end,'2026-10-26');assert.equal(view.weekly[0].partial,true);
 assert.equal(view.weekly[0].base,view.daily[0].base);
 assert.equal(view.cumulative.at(-1).base,view.components.recorded+view.weekly.reduce((a,p)=>a+p.base,0));
});

test('published history excludes all complete records at or beyond its UTC information cutoff',()=>{
 const company=syntheticForecastBundle({...fx,spending:[...fx.spending,{date:'2026-10-26',teamId:'t',personId:'p',complete:true,component:'api',amount:90000}]}).views[0];
 assert.equal(company.components.recorded,35);
 assert.equal(company.publication.history_complete_through,'2026-10-24');
});
test('weekly published total exactly matches reviewed fixture forecast and excludes included notional',()=>{
 const period={start:'2026-10-19',end:'2026-10-25'};
 const fixture={...fx,company:{...fx.company,currentPeriod:period},forecasts:[{teamId:'t',period,status:'available',projected:100,daily:[{date:'2026-10-25',projected:65}]},{teamId:'t',personId:'p',period,status:'available',projected:60,daily:[{date:'2026-10-25',projected:40}]}],spending:[...fx.spending,{date:'2026-10-23',teamId:'t',personId:'p',complete:true,component:'included_usage',provenance:'usage_only',amount:99999}]};
 const views=syntheticForecastBundle(fixture).views;
 const team=views.find(v=>v.scope.type==='team');
 assert.equal(team.planning_period_outlook.base,100);
 assert.equal(team.components.recorded,30);
 assert.equal(team.cumulative[0].base,100);
 const company=views.find(v=>v.scope.type==='company');
 const shared=views.find(v=>v.scope.type==='shared'&&v.scope.id==='shared');
 assert.equal(company.planning_period_outlook.base,team.planning_period_outlook.base+shared.planning_period_outlook.base);
});
test('Northstar publication, summary and approval inputs agree on one weekly target',async()=>{
 const {northstar}=await import(tsModuleUrl(new URL('../../fixtures/index.ts',import.meta.url)));
 const {selectScopeSummary}=await import(tsModuleUrl(new URL('../finance-summary.ts',import.meta.url)));
 const bundle=syntheticForecastBundle(northstar);
 const company=bundle.views.find(v=>v.scope.type==='company');
 const summary=selectScopeSummary({scope:company.scope,period:northstar.company.currentPeriod,unit:'usd',datasetId:northstar.company.id,spending:northstar.spending,budgets:northstar.budgets,forecastView:company});
 assert.equal(summary.observed.amount,95000);
 assert.equal(summary.observed.byProvenance.simulated,95000);
 assert.equal(summary.issued.amount,200000);
 assert.equal(summary.allocation,200000);
 assert.equal(summary.variance,0);
 assert.equal(company.quarter_outlook.start,'2026-10-01');
 assert.equal(company.cumulative.find(p=>p.date==='2026-10-25').base,200000);
 for(const legacy of northstar.forecasts) {
  const canonical=bundle.views.find(v=>legacy.personId ? v.scope.type==='person'&&v.scope.id===legacy.personId : v.scope.type==='team'&&v.scope.id===legacy.teamId);
  assert.equal(canonical.planning_period_outlook.base,legacy.projected);
 }
});
test('quarter prefix absence is unknown and unavailable team outlook propagates to company',()=>{
 const company=syntheticForecastBundle({...fx,forecasts:[{teamId:'t',period:fx.company.currentPeriod,status:'unavailable'}]}).views.find(v=>v.scope.type==='company');
 assert.equal(company.quarter_outlook.base,null);
 assert.equal(company.planning_period_outlook.base,null);
});
test('mock scenario drivers stay in their affected scopes while company retains the complete set',()=>{
 const fixture={...fx,teams:[{id:'t',name:'Product'},{id:'t2',name:'Research'}],people:[{id:'p',teamId:'t',name:'One'},{id:'p2',teamId:'t2',name:'Two'}]};
 const drivers=[
  {id:'product-only',scope:{team_id:'t'}},
  {id:'person-only',scope:{person_id:'p'}},
  {id:'company-plan',scope:{type:'company'}},
  {id:'unknown-plan'},
  {id:'move-person',kind:'membership',scope:{person_id:'p'},parameters:{team_id:'t2'}},
  {id:'mapped-shared',scope:{project_id:'unresolved'},affected_scopes:[{type:'shared',id:'shared'}]},
 ];
 const views=syntheticForecastBundle(fixture,'scenario',drivers).views;
 const ids=(type,id)=>views.find(v=>v.scope.type===type&&v.scope.id===id).included_drivers.map(d=>d.id);
 assert.deepEqual(ids('company','c'),drivers.map(d=>d.id));
 assert.deepEqual(ids('team','t'),['product-only','person-only','company-plan','move-person']);
 assert.deepEqual(ids('team','t2'),['company-plan','move-person']);
 assert.deepEqual(ids('person','p'),['product-only','person-only','company-plan','move-person']);
 assert.deepEqual(ids('person','p2'),['company-plan']);
 assert.deepEqual(ids('shared','shared'),['company-plan','mapped-shared']);
});
