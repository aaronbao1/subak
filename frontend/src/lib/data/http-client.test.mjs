import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { stripTypeScriptTypes } from 'node:module';
const source=stripTypeScriptTypes(fs.readFileSync(new URL('./http-client.ts',import.meta.url),'utf8'),{mode:'transform'});
const {HttpDataClient}=await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);
test('canonical transport keeps scope and immutable run identity exact',async()=>{
 const calls=[]; const original=globalThis.fetch;
 globalThis.fetch=async(url,init)=>{calls.push({url,init});return new Response(JSON.stringify({views:[]}));};
 try {
  const client=new HttpDataClient('http://fixture.invalid');
  await client.getForecastViews({scope_type:'person',scope_id:'person / 1',run_id:'run-7'});
  const q=new URL(calls[0].url).searchParams;
  assert.equal(q.get('scope_type'),'person');assert.equal(q.get('scope_id'),'person / 1');assert.equal(q.get('run_id'),'run-7');
  assert.equal(calls[0].init.cache,'no-store');
 }finally{globalThis.fetch=original;}
});
test('refresh uses idempotency header; scenario and Ask Droid retain issued ids',async()=>{
 const calls=[];const original=globalThis.fetch;
 globalThis.fetch=async(url,init)=>{calls.push({url,init});return new Response('{}');};
 try {
  const client=new HttpDataClient('http://fixture.invalid');
  await client.refreshForecast('operation-123');
  assert.equal(calls[0].init.headers['Idempotency-Key'],'operation-123');
  await client.previewForecastScenario('issued / 7',[]);
  assert.match(calls[1].url,/forecast-runs\/issued%20%2F%207\/scenarios$/);
  assert.deepEqual(JSON.parse(calls[1].init.body),{drivers:[]});
  const context={action:'explain',run_id:'issued-7',scope_type:'team',scope_id:'t1',driver_id:'d1'};
  await client.sendMessage('main','Explain this',context);
  assert.deepEqual(JSON.parse(calls[2].init.body),{content:'Explain this',forecast_context:context});
 }finally{globalThis.fetch=original;}
});
