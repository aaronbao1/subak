import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {stripTypeScriptTypes} from 'node:module';
import {tsModuleUrl} from '../../../tests/load-ts-module.mjs';

const usageUrl=tsModuleUrl(new URL('../usage-derive.ts',import.meta.url));
const source=stripTypeScriptTypes(fs.readFileSync(new URL('./demo-usage.ts',import.meta.url),'utf8'),{mode:'transform'})
 .replace(/from ["']\.\.\/usage-derive["']/,`from ${JSON.stringify(usageUrl)}`)
 .replace(/import \{ loadDemoSnapshot \} from ["']\.\/demo-snapshot["'];/, 'const loadDemoSnapshot = () => globalThis.__loadUsageSnapshot();');
const {demoUsageFromSnapshot,fetchDemoUsage}=await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);
const {summarizeUsage}=await import(usageUrl);
const row=(id,amount,extra={})=>({id,amount,date:'2026-10-24',teamId:'research',personId:'person-1',provider:'alpha',model:'same',unit:'usd',component:'api',provenance:'measured',source:'Saved report',complete:true,...extra});
const snapshot={asOf:'2026-10-25T12:00:00Z',dataset:{company:{id:'saved-company',currentPeriod:{start:'2026-10-19',end:'2026-10-25'}},spending:[row('old',1,{date:'2026-10-01'}),row('a',0.1),row('b',0.2,{teamId:'product',personId:'person-2',provider:'beta'}),row('shared',0.3,{teamId:'unattributed',personId:undefined}),row('future',99,{date:'2026-10-26'})]}};
const query={scopeType:'company',startDate:'2026-10-01',endDateExclusive:'2026-10-28'};
const total=response=>summarizeUsage(response.buckets).recordedSpend;

test('saved usage uses exported history and fixed as-of without inventing gaps or future actuals',()=>{
 const result=demoUsageFromSnapshot(snapshot,query);
 assert.equal(result.datasetId,'saved-company');assert.equal(result.asOf,snapshot.asOf);
 assert.equal(result.availableStartDate,'2026-10-01');assert.equal(total(result),'1.60');
 assert.equal(result.buckets[1].coverage,'missing');assert.equal(result.buckets[1].recordedSpend,null);
 assert.equal(result.buckets.at(-1).coverage,'future');assert.equal(result.buckets.at(-1).recordedSpend,null);
 assert.equal(result.buckets[0].coverage,'partial');assert.match(result.notes.join(' '),/completion receipts are unavailable/);
});

test('team, person, shared and provider/model filters use saved identities exactly',()=>{
 assert.equal(total(demoUsageFromSnapshot(snapshot,{...query,scopeType:'team',scopeId:'research'})),'1.10');
 assert.equal(total(demoUsageFromSnapshot(snapshot,{...query,scopeType:'person',scopeId:'person-2'})),'0.20');
 assert.equal(total(demoUsageFromSnapshot(snapshot,{...query,scopeType:'shared'})),'0.30');
 assert.equal(total(demoUsageFromSnapshot(snapshot,{...query,scopeType:'team',scopeId:'unattributed'})),'0.30');
 assert.equal(total(demoUsageFromSnapshot(snapshot,{...query,provider:'beta',model:'same'})),'0.20');
 assert.equal(total(demoUsageFromSnapshot(snapshot,{...query,provider:'beta',model:'missing'})),null);
 assert.throws(()=>demoUsageFromSnapshot(snapshot,{...query,scopeType:'person'}),/Choose a team or person/);
});

test('nullable compatibility tokens and missing included notional remain unknown',()=>{
 const records=[row('unknown',0,{inputTokens:null,outputTokens:null,tokens:null,component:'included_usage',provenance:'usage_only',includedUsageNotional:null})];
 const copy=structuredClone(records);const result=demoUsageFromSnapshot({...snapshot,dataset:{...snapshot.dataset,spending:records}},query);
 const bucket=result.buckets.find(bucket=>bucket.date==='2026-10-24');
 assert.equal(bucket.tokens.total,null);assert.equal(bucket.tokens.input,null);assert.equal(bucket.includedUsageNotional,null);
 assert.equal(bucket.breakdowns[0].includedUsageNotional,null);assert.deepEqual(records,copy);
 const paired=demoUsageFromSnapshot({...snapshot,dataset:{...snapshot.dataset,spending:[row('paired',0.1,{inputTokens:100,outputTokens:25,cachedInputTokens:30,reasoningTokens:5})]}},query);
 assert.equal(paired.buckets.find(bucket=>bucket.date==='2026-10-24').tokens.total,125);
});

test('snapshot helper loads only the saved source and respects cancellation',async()=>{
 const oldFetch=globalThis.fetch;let loads=0;
 globalThis.fetch=()=>{throw Error('Unexpected live API request');};
 globalThis.__loadUsageSnapshot=async()=>{loads++;return snapshot;};
 try {
  assert.equal(total(await fetchDemoUsage(query)),'1.60');assert.equal(loads,1);
  const controller=new AbortController();controller.abort();
  await assert.rejects(fetchDemoUsage(query,controller.signal),{name:'AbortError'});assert.equal(loads,1);
  const delayed=new AbortController();globalThis.__loadUsageSnapshot=async()=>{delayed.abort();return snapshot;};
  await assert.rejects(fetchDemoUsage(query,delayed.signal),{name:'AbortError'});
 }finally{globalThis.fetch=oldFetch;delete globalThis.__loadUsageSnapshot;}
});
