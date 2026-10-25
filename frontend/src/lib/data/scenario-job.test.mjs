import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { stripTypeScriptTypes } from 'node:module';
const source=stripTypeScriptTypes(fs.readFileSync(new URL('./scenario-job.ts',import.meta.url),'utf8'));
const {completeScenario}=await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);
const receipt={scenario_id:'isolated-9',parent_run_id:'issued-7',job_id:'job-9',status:'queued',views:[]};
const bundle={parent_run_id:'issued-7',run_id:'isolated-9',status:'succeeded',views:[{run_id:'isolated-9',scope:{type:'team',id:'t1'}}]};
test('pending scenario receipt polls same job then retrieves completed isolated bundle',async()=>{
 const calls=[],progress=[];let n=0;
 const client={getForecastRefresh:async id=>{calls.push(['job',id]);return {id,status:++n===1?'running':'succeeded',run_id:'isolated-9'};},getForecastScenario:async id=>{calls.push(['scenario',id]);return bundle;}};
 const result=await completeScenario(receipt,'issued-7',client,p=>progress.push(p.status),{delay:async()=>{}});
 assert.equal(result,bundle);assert.deepEqual(progress,['queued','running']);
 assert.deepEqual(calls,[['job','job-9'],['job','job-9'],['scenario','isolated-9']]);
 assert.equal(result.views[0].scope.id,'t1');assert.equal(receipt.status,'queued');assert.equal(receipt.views.length,0);
});
test('failed or still pending scenarios remain receipts rather than empty published forecasts',async()=>{
 const client={getForecastRefresh:async()=>{throw Error('should not poll');},getForecastScenario:async()=>{throw Error('should not fetch');}};
 await assert.rejects(()=>completeScenario({...receipt,status:'failed',last_error:'Retry limit reached'},'issued-7',client,()=>{}),/Retry limit reached/);
 await assert.rejects(()=>completeScenario(receipt,'issued-7',client,()=>{},{maxPolls:0}),/Check scenario status/);
});
test('scenario completion rejects changed parent run or unexpected job scenario id',async()=>{
 const client={getForecastRefresh:async()=>({id:'job-9',status:'succeeded',run_id:'different-scenario'}),getForecastScenario:async()=>bundle};
 await assert.rejects(()=>completeScenario(receipt,'new-issued-run',client,()=>{}),/different issued run/);
 await assert.rejects(()=>completeScenario(receipt,'issued-7',client,()=>{},{delay:async()=>{}}),/different scenario identity/);
});
