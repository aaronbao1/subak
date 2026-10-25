import test from 'node:test';
import assert from 'node:assert/strict';
import { tsModuleUrl } from '../../../tests/load-ts-module.mjs';
const { syntheticWeeklyHistory } = await import(tsModuleUrl(new URL('./mock-weekly-history.ts', import.meta.url)));
const offset = (date, n) => new Date(Date.parse(`${date}T00:00:00Z`) + n * 86400000).toISOString().slice(0, 10);
const query = {scopeType:'company',startDate:'2026-09-21',endDateExclusive:'2026-11-16'};
const rows = Array.from({length:63},(_,i)=>offset('2026-08-24',i)).flatMap(date=>[
 {id:`${date}:seat`,date,teamId:'t',personId:'p',component:'subscription',provider:'one',unit:'usd',amount:0.1,provenance:'simulated',complete:date<'2026-10-25',source:'Synthetic seat'},
 {id:`${date}:api`,date,teamId:'t',personId:'p',component:'api',provider:'one',model:'A',unit:'usd',amount:0.2,provenance:'simulated',complete:date<'2026-10-25',source:'Synthetic API'},
 {id:`${date}:included`,date,teamId:'t',personId:'p',component:'included_usage',provider:'one',unit:'usd',amount:1000,provenance:'usage_only',complete:date<'2026-10-25',source:'Synthetic inclusion'},
]);
const fx={company:{id:'fixture',name:'Fixture',budgetUnit:'usd',currentPeriod:{start:'2026-10-19',end:'2026-10-25'}},teams:[{id:'t',name:'Team'}],people:[{id:'p',teamId:'t',name:'Person'}],spending:rows,forecasts:[]};
const bundle={views:[{run_id:'current',scope:{type:'company',id:'fixture'},dataset_id:'fixture',target:{unit:'usd',basis:'planning',quantity:'spend',timezone:'UTC'},publication:{generated_at:'2026-10-25T12:00:00Z',information_cutoff:'2026-10-25T00:00:00Z'},planning_period_outlook:{start:'2026-10-19',end:'2026-10-26',base:10},weekly:[{start:'2026-10-25',end:'2026-10-26',calendar_start:'2026-10-19',partial:true,base:5},{start:'2026-10-26',end:'2026-11-02',partial:false,base:7}]}]};
const run=(fixture=fx,q=query,b=bundle)=>syntheticWeeklyHistory(fixture,q,b);

test('synthetic historical issues and complete outcomes use exact billable amounts independently',()=>{
 const r=run();const week=r.weeks[0];
 assert.equal(r.synthetic,true);assert.equal(r.datasetId,'fixture');assert.equal(r.weeks.length,8);
 assert.equal(week.actual.amount,'2.10');assert.equal(week.actual.status,'mature');assert.equal(week.actual.source,'observed_outcome');assert.equal(week.actual.datasetId,'fixture');
 assert.ok(week.actual.sourceRefs[0].startsWith('synthetic-observed-outcome:'));
 assert.equal(week.priorForecast.amount,'2.10');assert.equal(week.priorForecast.issuedAt,'2026-09-21T00:00:00Z');assert.equal(week.priorForecast.informationCutoff,week.priorForecast.issuedAt);
 assert.equal(week.variance.amount,'0.00');assert.equal(week.variance.status,'available');
 const altered=run({...fx,spending:rows.map(r=>r.date>='2026-09-21'&&r.date<'2026-09-28'&&r.component==='api'?{...r,amount:0.21}:r)}).weeks[0];
 assert.equal(altered.priorForecast.amount,week.priorForecast.amount);assert.equal(altered.actual.amount,'2.17');assert.equal(altered.variance.amount,'0.07');
});

test('held-out and future values cannot alter a prior issue or its identity',()=>{
 const before=run().weeks[0].priorForecast;
 const changed=rows.map(r=>r.date>='2026-09-21'?{...r,amount:r.amount*999}:r);
 changed.push({...rows[1],id:'future',date:'2026-12-01',amount:999999,complete:true});
 assert.deepEqual(run({...fx,spending:changed}).weeks[0].priorForecast,before);
 const laterRoster={...fx,people:[...fx.people,{id:'later',teamId:'later-team'}],teams:[...fx.teams,{id:'later-team'}],spending:[...rows,{...rows[1],id:'later-row',date:'2026-10-20',personId:'later',teamId:'later-team'}]};
 assert.deepEqual(run(laterRoster).weeks[0].priorForecast,before);
 assert.deepEqual(run(laterRoster).weeks[0].actual,run().weeks[0].actual);
 const sameThroughNow=run({...fx,spending:[...rows,{...rows[1],id:'future',date:'2026-12-01',amount:999999,complete:true}]});
 assert.equal(sameThroughNow.actualsRevision,run().actualsRevision);
});

test('earliest history is not backfilled and query bounds are enforced',()=>{
 const r=run(fx,{...query,startDate:'2026-08-24'});
 assert.ok(r.weeks.slice(0,4).every(w=>w.priorForecast===null&&w.variance.status==='unavailable'));
 assert.ok(r.weeks[4].priorForecast);
 for(const q of [{...query,startDate:'2026-09-22'},{...query,endDateExclusive:'2026-09-21'},{...query,endDateExclusive:'2027-04-05'}]) assert.throws(()=>run(fx,q));
});

test('missing days, missing streams and incomplete records cannot create mature outcomes',()=>{
 for(const missing of [r=>r.date!=='2026-09-23',r=>r.id!=='2026-09-23:api',r=>!(r.date>='2026-09-21'&&r.date<'2026-09-28'&&r.component==='api')]) {
  const week=run({...fx,spending:rows.filter(missing)}).weeks[0];
  assert.equal(week.actual.status,'partial');assert.equal(week.actual.source,'repository_ledger');assert.equal(week.variance.amount,null);
 }
 const incomplete=run({...fx,spending:rows.map(r=>r.id==='2026-09-23:api'?{...r,complete:false}:r)}).weeks[0];
 assert.equal(incomplete.actual.status,'partial');
 const trainingGap=run({...fx,spending:rows.filter(r=>r.id!=='2026-09-01:api')}).weeks[0];
 assert.equal(trainingGap.priorForecast,null);
});

test('current week stays partial, future actuals absent, and only canonical outlook targets appear',()=>{
 const r=run();const current=r.weeks.find(w=>w.state==='current');const future=r.weeks.filter(w=>w.state==='future');
 assert.equal(current.actual.status,'partial');assert.equal(current.variance.amount,null);assert.equal(current.outlook.amount,'10.00');assert.equal(current.outlook.partial,false);
 assert.ok(future.every(w=>w.actual.status==='future'&&w.actual.amount===null&&w.priorForecast===null));
 assert.equal(future[0].outlook.amount,'7.00');assert.equal(future[1].outlook,null);
 const incomplete=run(fx,query,{views:[{...bundle.views[0],weekly:bundle.views[0].weekly.map(p=>({...p,complete:false}))}]});
 assert.equal(incomplete.weeks.find(w=>w.state==='future').outlook,null);
 const remainder=run(fx,query,{views:[{...bundle.views[0],planning_period_outlook:undefined}]}).weeks.find(w=>w.state==='current');
 assert.equal(remainder.outlook.amount,'5.00');assert.equal(remainder.outlook.start,'2026-10-25');assert.equal(remainder.outlook.partial,true);
});

test('known zero differs from empty scopes and non-dollar rows do not inflate spending',()=>{
 const zero=run({...fx,spending:rows.map(r=>({...r,amount:0}))}).weeks[0];assert.equal(zero.actual.amount,'0.00');assert.equal(zero.actual.status,'mature');assert.equal(zero.priorForecast.amount,'0.00');
 const empty=run({...fx,teams:[],people:[],spending:[]});assert.ok(empty.weeks.every(w=>w.actual.amount===null&&w.priorForecast===null));
 const extra={...rows[1],id:'tokens',unit:'tokens',amount:100000};assert.equal(run({...fx,spending:[...rows,extra]}).weeks[0].actual.amount,'2.10');
});

test('Northstar and generated fixtures retain independently observed amounts and unavailable canonical scope',async()=>{
 const {northstar,generateCompany}=await import(tsModuleUrl(new URL('../../fixtures/index.ts',import.meta.url)));
 const {syntheticForecastBundle}=await import(tsModuleUrl(new URL('./mock-forecast.ts',import.meta.url)));
 const north=run(northstar,query,syntheticForecastBundle(northstar));
 assert.equal(north.weeks.find(w=>w.state==='current').actual.amount,'95000.00');assert.equal(north.weeks.find(w=>w.state==='current').outlook.amount,'200000.00');
 assert.ok(north.weeks.slice(0,4).every(w=>w.actual.status==='mature'&&w.variance.status==='available'));
 const generated=generateCompany(8);const history=run(generated,query,syntheticForecastBundle(generated));
 assert.equal(history.weeks.find(w=>w.state==='current').actual.amount,'208330.00');assert.equal(history.weeks.find(w=>w.state==='current').outlook,null);
 const companyPrior=Number(history.weeks[0].priorForecast.amount);
 const teamPrior=generated.teams.reduce((total,team)=>total+Number(run(generated,{...query,scopeType:'team',scopeId:team.id},syntheticForecastBundle(generated)).weeks[0].priorForecast.amount),0);
 assert.ok(Math.abs(companyPrior-teamPrior)<0.000001);
});
