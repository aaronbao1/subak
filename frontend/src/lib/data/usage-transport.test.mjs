import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {stripTypeScriptTypes} from 'node:module';
const source=stripTypeScriptTypes(fs.readFileSync(new URL('./usage-client.ts',import.meta.url),'utf8'),{mode:'transform'});
const {adaptDailyUsage,fetchDailyUsage}=await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);
const aggregate={recorded_spend:'0.30',costs_by_value_kind:{reported:'0.10',estimated:'0.20',measured:'0.00',simulated:'0.00'},included_usage_notional:'12.00',tokens:{input_tokens:100,cached_input_tokens:40,output_tokens:20,reasoning_tokens:5,total_tokens:120},record_count:2,token_observed_record_counts:{input_tokens:1,output_tokens:1,total_tokens:1}};
const wire={scope:{type:'company'},start_date:'2026-10-24',end_date_exclusive:'2026-10-25',timezone:'UTC',unit:'USD',dataset_id:'native',dataset_revision:'7',synthetic:false,as_of:'2026-10-25T12:00:00Z',available_start_date:'2026-10-24',available_end_date_exclusive:'2026-10-25',filters:{},buckets:[{date:'2026-10-24',...aggregate,coverage:'partial',revision:'7',source_refs:['batch-1'],breakdowns:[{provider:'alpha',model:'same',...aggregate},{provider:'beta',model:'same',...aggregate}]}],source_coverage:[],notes:[]};
test('snake-case transport retains exact money, tokens, provenance and provider/model identities',()=>{
 const response=adaptDailyUsage(wire), b=response.buckets[0];
 assert.equal(b.recordedSpend,'0.30'); assert.equal(b.includedUsageNotional,'12.00'); assert.equal(b.tokens.total,120);assert.equal(b.tokens.cachedInput,40);
 assert.equal(b.tokenObservedRecordCounts.input,1);assert.deepEqual(b.breakdowns.map(r=>r.provider),['alpha','beta']);
 assert.equal(response.datasetRevision,'7');assert.equal(response.timezone,'UTC');
 assert.throws(()=>adaptDailyUsage({...wire,buckets:[{...wire.buckets[0],costs_by_value_kind:{...aggregate.costs_by_value_kind,unknown:'1.00'}}]}),/value kind/);
});
test('bounded UTC query encodes scope and model with an abortable request',async()=>{
 const original=globalThis.fetch,calls=[];globalThis.fetch=async(url,options)=>{calls.push({url,options});return new Response(JSON.stringify(wire));};
 try {
  const controller=new AbortController();await fetchDailyUsage('http://fixture.invalid/compat/',{scopeType:'person',scopeId:'person / 1',startDate:'2026-10-24',endDateExclusive:'2026-10-25',provider:'alpha',model:'same / model'},controller.signal);
  const u=new URL(calls[0].url);assert.equal(u.pathname,'/compat/api/usage/daily');assert.equal(u.searchParams.get('scope_id'),'person / 1');assert.equal(u.searchParams.get('end_date_exclusive'),'2026-10-25');assert.equal(calls[0].options.signal,controller.signal);
  await assert.rejects(()=>fetchDailyUsage('http://fixture.invalid',{scopeType:'company',startDate:'2025-01-01',endDateExclusive:'2026-10-25'}),/366/);
 }finally{globalThis.fetch=original;}
});
