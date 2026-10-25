import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {stripTypeScriptTypes} from 'node:module';
const source=stripTypeScriptTypes(fs.readFileSync(new URL('./weekly-spend-derive.ts',import.meta.url),'utf8'));
const {weeklyChartRows,defaultReviewWeek,weeklyNumber,comparisonLabel,weeklyMoney}=await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);
const week={start:'2026-10-12',endExclusive:'2026-10-19',state:'closed',actual:{amount:'110.25',status:'mature',datasetId:'d'},priorForecast:{amount:'100.00',start:'2026-10-12',endExclusive:'2026-10-19',datasetId:'d',issuedAt:'2026-10-11T23:59:00Z'},outlook:null,variance:{amount:'10.25',status:'available'}};
const history=weeks=>({datasetId:'d',weeks});
test('closed full-week comparisons preserve supplied amounts and original forecasts',()=>{
 const [row]=weeklyChartRows(history([week]));assert.equal(row.actual,110.25);assert.equal(row.forecast,100);assert.equal(row.variance,10.25);assert.equal(row.forecastKind,'original');assert.equal(comparisonLabel(row),'+$10.25 over');
 const [under]=weeklyChartRows(history([{...week,actual:{...week.actual,amount:'90.00'},variance:{amount:'-10.00',status:'available'}}]));assert.equal(comparisonLabel(under),'−$10 under');
});
test('current partial actuals never become a final overrun and remainder is not a whole-week forecast',()=>{
 const current={...week,state:'current',actual:{...week.actual,status:'partial',amount:'120.00'},priorForecast:null,outlook:{amount:'50.00',datasetId:'d',start:'2026-10-15',endExclusive:week.endExclusive,partial:true}};
 const [row]=weeklyChartRows(history([current]));assert.equal(row.actual,120);assert.equal(row.forecast,null);assert.equal(row.variance,null);assert.equal(comparisonLabel(row),'In progress');
});
test('a newer or partial-period prediction cannot masquerade as original history',()=>{
 for(const prior of [{...week.priorForecast,issuedAt:'2026-10-12T00:00:01Z'},{...week.priorForecast,start:'2026-10-13'}]) {
  const [row]=weeklyChartRows(history([{...week,priorForecast:prior,outlook:{...prior,partial:false}}]));assert.equal(row.forecast,null);assert.equal(row.variance,null);
 }
});
test('future observations stay absent and exact full-week outlook is shown without final variance',()=>{
 const [row]=weeklyChartRows(history([{...week,state:'future',priorForecast:null,outlook:{amount:'90.00',start:week.start,endExclusive:week.endExclusive,datasetId:'d',partial:false}}]));
 assert.equal(row.actual,null);assert.equal(row.forecast,90);assert.equal(row.forecastKind,'outlook');assert.equal(row.variance,null);
});
test('default review prefers latest comparable completed week and zero stays distinct from missing',()=>{
 const rows=weeklyChartRows(history([{...week,actual:{...week.actual,amount:'0'},priorForecast:{...week.priorForecast,amount:'0'},variance:{amount:'0',status:'available'}},{...week,start:'2026-10-19',endExclusive:'2026-10-26',state:'current'}]));
 assert.equal(defaultReviewWeek(rows).start,'2026-10-12');assert.equal(rows[0].actual,0);assert.equal(comparisonLabel(rows[0]),'On forecast');assert.equal(weeklyNumber(''),null);assert.equal(weeklyNumber(null),null);
});

test('forecast issued exactly at Monday midnight remains the original weekly forecast',()=>{
 const [row]=weeklyChartRows(history([{...week,priorForecast:{...week.priorForecast,issuedAt:'2026-10-12T00:00:00Z'}}]));
 assert.equal(row.forecast,100);assert.equal(row.variance,10.25);
});

test('future weeks prefer current full-week outlook and never label it a retrospective original',()=>{
 const [row]=weeklyChartRows(history([{...week,state:'future',outlook:{amount:'140.00',datasetId:'d',start:week.start,endExclusive:week.endExclusive,partial:false}}]));
 assert.equal(row.forecast,140);assert.equal(row.forecastKind,'outlook');assert.equal(row.variance,null);
});

test('current week prefers supplied full-week outlook but keeps final variance unavailable',()=>{
 const [row]=weeklyChartRows(history([{...week,state:'current',outlook:{amount:'200.00',datasetId:'target-v2',start:week.start,endExclusive:week.endExclusive,partial:false}}]));
 assert.equal(row.forecast,200);assert.equal(row.forecastKind,'outlook');assert.equal(row.variance,null);
});
test('envelope identity may differ from source targets; comparable forecast and actual datasets must match each other',()=>{
 const valid={...week,actual:{...week.actual,datasetId:'forecast-targets:tenant'},priorForecast:{...week.priorForecast,datasetId:'forecast-targets:tenant'}};
 const [row]=weeklyChartRows({datasetId:'forecast-weekly:tenant',weeks:[valid]});assert.equal(row.forecast,100);assert.equal(row.variance,10.25);
 const [mismatch]=weeklyChartRows({datasetId:'forecast-weekly:tenant',weeks:[{...valid,actual:{...valid.actual,datasetId:'repository-ledger:tenant'}}]});assert.equal(mismatch.forecast,100);assert.equal(mismatch.variance,null);
});
test('adapted native wire retains archived forecast and mature variance with distinct envelope identity',async()=>{
 const {tsModuleUrl}=await import('../../../tests/load-ts-module.mjs');
 const {adaptWeeklyHistory}=await import(tsModuleUrl(new URL('../../lib/data/weekly-history.ts',import.meta.url)));
 const native={scope:{type:'company',id:'northstar'},start_date:'2026-10-12',end_date_exclusive:'2026-10-19',timezone:'UTC',unit:'USD',basis:'planning',quantity:'spend',dataset_id:'forecast-weekly:northstar',as_of:'2026-10-25T00:00:00Z',synthetic:true,actuals_revision:'r1',selection_policy:'latest_published_before_week_start',notes:[],weeks:[{start:'2026-10-12',end_exclusive:'2026-10-19',state:'closed',actual:{amount:'110.00',status:'mature',source:'observed_outcome',dataset_id:'forecast-targets:northstar',revision:'truth-1',corrected:false,source_refs:[]},prior_forecast:{amount:'100.00',run_id:'r1',target_id:'t1',dataset_id:'forecast-targets:northstar',issued_at:'2026-10-12T00:00:00Z',information_cutoff:'2026-10-11T00:00:00Z',start:'2026-10-12',end_exclusive:'2026-10-19'},outlook:null,variance:{amount:'10.00',status:'available',reason:null}}]};
 const [row]=weeklyChartRows(adaptWeeklyHistory(native));assert.equal(row.forecast,100);assert.equal(row.variance,10);
});

test('compact dollar labels below one thousand preserve cents',()=>{assert.equal(weeklyMoney('167.76',true),'$167.76');assert.equal(weeklyMoney('0.06',true),'$0.06');assert.equal(weeklyMoney(null,true),'—');});
