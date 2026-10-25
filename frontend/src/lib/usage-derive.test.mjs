import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {stripTypeScriptTypes} from 'node:module';
const source = stripTypeScriptTypes(fs.readFileSync(new URL('./usage-derive.ts', import.meta.url), 'utf8'), {mode:'transform'});
const {sumUsageMoney, summarizeUsage, aggregateUsageBreakdowns, usageIntensity, usageValue, mockDailyUsage} = await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);
const query = {scopeType:'company',startDate:'2026-10-23',endDateExclusive:'2026-10-27'};
const options = {asOf:'2026-10-25T12:00:00Z',datasetId:'synthetic-test'};
const row = (overrides={}) => ({id:'a',teamId:'a',personId:'p',date:'2026-10-24',component:'api',provider:'alpha',model:'same',amount:0.1,unit:'usd',provenance:'simulated',source:'synthetic',complete:true,tokens:12,...overrides});
test('exact sums never use float arithmetic and absence never becomes zero',()=>{
 assert.equal(sumUsageMoney(['0.1','0.2']), '0.30');
 assert.equal(sumUsageMoney([null,null]),null);
 assert.equal(sumUsageMoney(['0.000001','-0.000001']),'0.000000');
});
test('synthetic calendar preserves missing, known zero, partial and future independently',()=>{
 const r=mockDailyUsage([row({amount:0}),row({id:'b',date:'2026-10-25',amount:0.2,complete:false})],query,options);
 assert.deepEqual(r.buckets.map(b=>b.coverage),['missing','complete','partial','future']);
 assert.equal(r.buckets[0].recordedSpend,null); assert.equal(r.buckets[1].recordedSpend,'0.00');
 assert.equal(r.buckets[3].tokens.total,null); assert.equal(r.synthetic,true);
 assert.equal(r.buckets[1].tokens.input,null); assert.equal(r.buckets[1].tokens.total,12);
 assert.equal(r.availableStartDate,'2026-10-24');
});
test('all provenance and informational included costs are retained without billing twice',()=>{
 const r=mockDailyUsage([
 row({id:'a',provenance:'reported_charge',amount:0.1}),
 row({id:'b',provenance:'estimate',amount:0.2}),
 row({id:'c',provenance:'measured',amount:0.3}),
 row({id:'d',provenance:'simulated',amount:0.4}),
 row({id:'e',component:'included_usage',provenance:'usage_only',amount:50,tokens:20}),
 row({id:'f',component:'unpriced_usage',provenance:'measured',amount:0,tokens:10}),
 ],query,options);
 const b=r.buckets[1]; assert.equal(b.recordedSpend,'1.00'); assert.equal(b.includedUsageNotional,'50.00');
 assert.deepEqual(b.costsByValueKind,{reported:'0.10',estimated:'0.20',measured:'0.30',simulated:'0.40'});
 assert.equal(b.tokens.total,78); assert.equal(b.recordCount,6);
 assert.throws(()=>mockDailyUsage([row({provenance:'unknown'})],query,options),/provenance/);
});
test('scope partitions, duplicate identities and provider/model collisions remain distinct',()=>{
 const rows=[row(),row({id:'b',teamId:'b',personId:'q',provider:'beta',amount:0.2}),row({id:'c',teamId:'',personId:undefined,amount:0.3})];
 const company=mockDailyUsage(rows,query,options), a=mockDailyUsage(rows,{...query,scopeType:'team',scopeId:'a'},options);
 const shared=mockDailyUsage(rows,{...query,scopeType:'shared'},options), person=mockDailyUsage(rows,{...query,scopeType:'person',scopeId:'q'},options);
 assert.equal(summarizeUsage(company.buckets).recordedSpend,'0.60');
 assert.equal(summarizeUsage(a.buckets).recordedSpend,'0.10'); assert.equal(summarizeUsage(person.buckets).recordedSpend,'0.20');
 assert.equal(summarizeUsage(shared.buckets).recordedSpend,'0.30');
 assert.equal(aggregateUsageBreakdowns(company.buckets).length,2);
 assert.equal(mockDailyUsage([row(),row({amount:0.7})],query,options).buckets[1].recordedSpend,'0.70');
});
test('fixed thresholds compare the same units across teams and future never has an actual value',()=>{
 assert.equal(usageIntensity(999,'spend'),2); assert.equal(usageIntensity(1000,'spend'),3);
 assert.equal(usageIntensity(1000000,'tokens'),3); assert.equal(usageIntensity(0,'tokens'),0);
 assert.equal(usageValue({coverage:'future',recordedSpend:'12.00',tokens:{total:3}},'spend'),null);
});
test('native paired token categories exclude cache and reasoning from total',()=>{
 const native=row({tokens:999,inputTokens:100,outputTokens:25,cachedInputTokens:30,reasoningTokens:10});
 const b=mockDailyUsage([native],query,options).buckets[1];
 assert.deepEqual(b.tokens,{input:100,cachedInput:30,output:25,reasoning:10,total:125});
});
test('exact currency labels retain precision beyond cents and large integer digits',async()=>{
 const usageModule=await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);
 assert.equal(usageModule.formatExactUsd('9007199254740993.123456'),'$9,007,199,254,740,993.123456');
 assert.equal(usageModule.formatExactUsd('-0.10'),'−$0.10');assert.equal(usageModule.formatExactUsd(null),'Not available');
});
test('incomplete category rows cannot become a seemingly complete total when ranges combine',()=>{
 const rows=[row({id:'paired',inputTokens:100,outputTokens:20}),row({id:'unpaired',date:'2026-10-25',inputTokens:7,tokens:undefined})];
 const r=mockDailyUsage(rows,query,options);
 assert.equal(summarizeUsage(r.buckets).tokens.total,null);
 assert.equal(summarizeUsage(r.buckets).tokens.input,107);
 assert.equal(mockDailyUsage(rows.map(x=>({...x,date:'2026-10-24'})),query,options).buckets[1].tokens.total,null);
});
test('category corrections invalidate the synthetic day revision',()=>{
 const a=mockDailyUsage([row({inputTokens:10,outputTokens:2})],query,options);
 const b=mockDailyUsage([row({inputTokens:11,outputTokens:2})],query,options);
 assert.notEqual(a.buckets[1].revision,b.buckets[1].revision);
});
test('compat shared pseudo-team maps to the explicit shared scope without inventing a team',async()=>{
 const usageModule=await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);
 assert.deepEqual(usageModule.normalizeUsageScope({type:'team',id:'unattributed'}),{type:'shared'});
 assert.deepEqual(usageModule.normalizeUsageScope({type:'team',id:'research'}),{type:'team',id:'research'});
});
