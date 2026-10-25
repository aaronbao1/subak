import test from 'node:test';
import assert from 'node:assert/strict';
import {tsModuleUrl} from '../../tests/load-ts-module.mjs';
const fixture=await import(tsModuleUrl(new URL('./generate.ts',import.meta.url)));
test('demo calendar uses a fixed UTC clock with valid Sunday Monday and quarter boundaries',()=>{
 assert.equal(fixture.asOf,'2026-10-25');
 for(const [now,start,end] of [['2026-10-25T12:00:00Z','2026-10-19','2026-10-25'],['2026-10-26T00:00:00Z','2026-10-26','2026-11-01'],['2026-12-31T23:59:59Z','2026-12-28','2027-01-03'],['2027-01-01T00:00:00Z','2026-12-28','2027-01-03']]) {
  const c=fixture.demoCalendar(now); assert.equal(c.period.start,start);assert.equal(c.period.end,end);assert.equal(c.asOf,now.slice(0,10));assert.ok(c.leaveEnd>=c.leaveStart);
 }
});
test('generated spending target counts billable money only and retains explicit synthetic provenance',()=>{
 const rows=fixture.dailySeries('t',1000,{subscription:1,included_usage:2,extra_usage:1,api:1},'openai');
 const current=rows.filter(r=>r.date>=fixture.period.start);
 assert.equal(current.filter(r=>r.component!=='included_usage').reduce((a,r)=>a+r.amount,0),1000);
 assert.ok(current.some(r=>r.component==='included_usage'&&r.amount>0));
 assert.ok(rows.every(r=>r.provenance===(r.component==='included_usage'?'usage_only':'simulated')));
});
test('generated welcome joins forecasts by identity and follows fixed clock monotonic ordering',()=>{
 const fx=fixture.generateCompany(8);
 const expected=fx.teams.filter(t=>(fx.forecasts.find(f=>f.teamId===t.id&&!f.personId)?.projected??0)>fx.budgets.find(b=>b.teamId===t.id).allocated).map(t=>t.name);
 const welcome=fx.threads.main[0];
 for(const name of expected) assert.ok(welcome.content.includes(name));
 assert.ok(welcome.createdAt<=fixture.DEMO_NOW);
 assert.ok(fixture.nextDemoTimestamp()>welcome.createdAt);
 for(const c of fx.context) if(c.effectiveFrom&&c.effectiveTo) assert.ok(c.effectiveFrom<=c.effectiveTo, c.id);
});
