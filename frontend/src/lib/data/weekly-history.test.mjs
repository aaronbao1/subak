import test from 'node:test';
import assert from 'node:assert/strict';
import {tsModuleUrl} from '../../../tests/load-ts-module.mjs';
const {adaptWeeklyHistory,validateWeeklyHistoryQuery,defaultWeeklyHistoryQuery}=await import(tsModuleUrl(new URL('./weekly-history.ts',import.meta.url)));
const query={scopeType:'team',scopeId:'research',startDate:'2026-10-12',endDateExclusive:'2026-10-19'};
function wire() { return {scope:{type:'team',id:'research'},start_date:'2026-10-12',end_date_exclusive:'2026-10-19',timezone:'UTC',unit:'USD',basis:'planning',quantity:'spend',dataset_id:'weekly:tenant',as_of:'2026-10-25T12:00:00Z',synthetic:true,actuals_revision:'actuals-r2',selection_policy:'latest_published_before_week_start',notes:[],weeks:[{start:'2026-10-12',end_exclusive:'2026-10-19',state:'closed',actual:{amount:'125.0000001',status:'mature',source:'observed_outcome',dataset_id:'targets:tenant',revision:'truth-v2',corrected:true,source_refs:['observed:week1']},prior_forecast:{amount:'100.0000001',run_id:'issued-1',target_id:'target-1',dataset_id:'targets:tenant',issued_at:'2026-10-12T00:00:00Z',information_cutoff:'2026-10-11T23:00:00Z',start:'2026-10-12',end_exclusive:'2026-10-19'},outlook:null,variance:{amount:'25',status:'available',reason:null}}]}; }
test('adapter preserves immutable vintage identity and precise corrected observed outcome separately',()=>{
 const result=adaptWeeklyHistory(wire(),query),week=result.weeks[0];
 assert.equal(week.priorForecast.amount,'100.0000001');assert.equal(week.priorForecast.runId,'issued-1');assert.equal(week.priorForecast.informationCutoff,'2026-10-11T23:00:00Z');
 assert.equal(week.actual.amount,'125.0000001');assert.equal(week.actual.revision,'truth-v2');assert.equal(week.actual.corrected,true);
 assert.equal(week.variance.amount,'25');assert.equal(result.actualsRevision,'actuals-r2');assert.equal(result.datasetId,'weekly:tenant');
});
test('adapter withholds false final comparisons and refuses future actuals or post-week historical forecasts',()=>{
 const current=wire();current.as_of='2026-10-14T12:00:00Z';current.weeks[0].state='current';current.weeks[0].actual.status='partial';
 assert.throws(()=>adaptWeeklyHistory(current,query),/mature|closed/i);
 const future=wire();future.as_of='2026-10-11T12:00:00Z';future.weeks[0].state='future';future.weeks[0].actual.status='future';future.weeks[0].variance={status:'unavailable',amount:null,reason:'Not complete'};
 assert.throws(()=>adaptWeeklyHistory(future,query),/future/i);
 const hindsight=wire();hindsight.weeks[0].prior_forecast.issued_at='2026-10-13T00:00:00Z';
 assert.throws(()=>adaptWeeklyHistory(hindsight,query),/issued|start/i);
 const differentBasis=wire();differentBasis.weeks[0].actual.dataset_id='ledger';assert.throws(()=>adaptWeeklyHistory(differentBasis,query),/dataset|target/i);
});
test('partial outlook keeps its remainder target without becoming the full week',()=>{
 const value=wire();value.as_of='2026-10-14T12:00:00Z';const week=value.weeks[0];week.state='current';week.actual.status='partial';week.actual.source='repository_ledger';week.actual.dataset_id='ledger';week.variance={status:'unavailable',amount:null,reason:'Week is open'};
 week.outlook={amount:'40.25',run_id:'latest',dataset_id:'targets:tenant',issued_at:'2026-10-14T12:00:00Z',information_cutoff:'2026-10-14T00:00:00Z',start:'2026-10-15',end_exclusive:'2026-10-19',partial:true};
 const result=adaptWeeklyHistory(value,query).weeks[0];assert.equal(result.outlook.start,'2026-10-15');assert.equal(result.outlook.partial,true);assert.equal(result.variance.amount,null);
});
test('history query enforces real Monday dates and at most26weeks',()=>{
 for(const invalid of [{...query,startDate:'2026-10-13'},{...query,endDateExclusive:'2026-10-12'},{...query,startDate:'2026-02-30'},{...query,startDate:'2026-01-05'},{...query,scopeId:undefined}]) assert.throws(()=>validateWeeklyHistoryQuery(invalid));
 assert.deepEqual(defaultWeeklyHistoryQuery('2026-10-25T12:00:00Z',{type:'company',id:'northstar'},4,3),{scopeType:'company',scopeId:'northstar',startDate:'2026-09-21',endDateExclusive:'2026-11-16'});
});
test('adapter rejects another scope or a missing week instead of showing mislabeled old data',()=>{
 const other=wire();other.scope.id='product';assert.throws(()=>adaptWeeklyHistory(other,query),/scope/i);
 const missing=wire();missing.weeks=[];assert.throws(()=>adaptWeeklyHistory(missing,query),/week|range/i);
});
