import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {stripTypeScriptTypes} from 'node:module';
const source=stripTypeScriptTypes(fs.readFileSync(new URL('./usage-link.ts',import.meta.url),'utf8'));
const {usageActivityHref}=await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);
test('person and team recorded-spend drilldowns retain exact selected week and metric',()=>{
 for(const type of ['person','team']) {
  const query=new URL(usageActivityHref({type,id:'entity-1'},{start:'2026-10-19',end:'2026-10-25'}),'https://local').searchParams;
  assert.equal(query.get('scope_type'),type);assert.equal(query.get('scope_id'),'entity-1');assert.equal(query.get('metric'),'spend');
  assert.equal(query.get('start_date'),'2026-10-19');assert.equal(query.get('end_date_exclusive'),'2026-10-26');
 }
});
test('inclusive period end converts correctly across month/year boundaries',()=>{
 assert.equal(new URL(usageActivityHref({type:'company'},{start:'2026-12-01',end:'2026-12-31'},'tokens'),'https://local').searchParams.get('end_date_exclusive'),'2027-01-01');
});
