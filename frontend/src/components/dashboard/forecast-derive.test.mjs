import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { stripTypeScriptTypes } from 'node:module';
const source = stripTypeScriptTypes(fs.readFileSync(new URL('./forecast-derive.ts', import.meta.url),'utf8'));
const { finite, pointRange, scopeView, forecastPrompt, evidenceDrivers } = await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);
test('null, missing and nonfinite forecasts remain unavailable, never zero',()=>{
 assert.equal(finite(null),undefined); assert.equal(finite(Infinity),undefined); assert.equal(finite(0),0);
 assert.equal(pointRange({base:10,low:null,high:null}),undefined);
 assert.deepEqual(pointRange({base:10,low:0,high:20}),[0,20]);
});
test('scopes select exact entity and run prompts preserve exact identifiers',()=>{
 const person={run_id:'issued-7',scope:{type:'person',id:'p1'}};
 const team={run_id:'issued-7',scope:{type:'team',id:'t1'}};
 assert.equal(scopeView({views:[person,team]},'person','p1'),person);
 assert.equal(scopeView({views:[person,team]},'person','t1'),undefined);
 assert.match(forecastPrompt(person,{id:'d9'}),/run_id=issued-7, scope_type=person, scope_id=p1, driver_id=d9/);
});
test('inclusion follows publication ids; unseen eligible evidence remains context only',()=>{
 const rows=evidenceDrivers({included_drivers:[{id:'a'}],queued_changes:[{id:'b'}]},[{drivers:[{id:'a'},{id:'b'},{id:'c',status:'eligible'}]}]);
 assert.deepEqual(rows.map(r=>[r.driver.id,r.status]),[['a','Included'],['b','Queued'],['c','Context only']]);
});
test('legacy full-quarter adapter never relabels four-week subtotal as quarter',async()=>{
 const {quarterForecasts}=await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);
 const result=quarterForecasts({views:[{id:'v',run_id:'r',scope:{type:'team',id:'t'},target:{unit:'USD'},publication:{},quarter_outlook:{start:'2026-10-01',end:'2027-01-01',base:1000},weekly:[{base:50}],limitations:[]}]});
 assert.equal(result[0].projected,1000); assert.equal(result[0].basis,'full_period'); assert.equal(result[0].period.end,'2026-12-31');
});
test('new evidence is queued only with explicit backend queue status',()=>{
 assert.deepEqual(evidenceDrivers({included_drivers:[],queued_changes:[]},[{drivers:[{id:'incoming',queue_status:'queued'}]}]).map(r=>r.status),['Queued']);
});
test('historical errors use matching archived interval fields, never descriptive low/high',async()=>{
 const {historicalRange}=await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);
 assert.equal(historicalRange({low:1,high:100}),undefined);
 assert.equal(historicalRange({historical_error_interval:{'80':{status:'insufficient_evidence',lower:null,upper:null}}}),undefined);
 assert.deepEqual(historicalRange({historical_error_interval:{'80':{status:'available_assumption_conditional',lower:8,upper:12},'95':{status:'available_assumption_conditional',lower:5,upper:15}}},'95'),[5,15]);
});
test('empty or partially unavailable weekly horizons never become a zero subtotal',async()=>{
 const {sumPointBases}=await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);
 assert.equal(sumPointBases([]),undefined);assert.equal(sumPointBases([{base:4},{base:null}]),undefined);assert.equal(sumPointBases([{base:0},{base:4}]),4);
});
test('scoped omission preserves all unrelated company drivers from the exact issued run',async()=>{
 const {omissionDrivers}=await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);
 const target={id:'team-driver'}, unrelated={id:'other-team-pool-driver'};
 const team={run_id:'r7',scope:{type:'team',id:'t'},included_drivers:[target]};
 const company={run_id:'r7',scope:{type:'company',id:'c'},included_drivers:[target,unrelated]};
 assert.deepEqual(omissionDrivers({views:[company,team]},team,'team-driver'),[unrelated]);
 assert.throws(()=>omissionDrivers({views:[{...company,run_id:'newer'},team]},team,'team-driver'),/same-run/);
});
test('source drawer closes when publication or scope changes',async()=>{
 const {selectedDriverForView}=await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);
 const driver={id:'d',source_revision:1}, selection={driver,runId:'r7',scopeType:'team',scopeId:'t1'};
 assert.equal(selectedDriverForView(selection,{run_id:'r7',scope:{type:'team',id:'t1'}}),driver);
 assert.equal(selectedDriverForView(selection,{run_id:'r8',scope:{type:'team',id:'t1'}}),undefined);
 assert.equal(selectedDriverForView(selection,{run_id:'r7',scope:{type:'person',id:'p1'}}),undefined);
});
test('redesigned company hero preserves canonical unknown quarter and shared amount',async()=>{
 const {companyQuarterProjection}=await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);
 const company={run_id:'r',scope:{type:'company',id:'c'},quarter_outlook:{base:null}};
 assert.equal(companyQuarterProjection({views:[company]},900),undefined);
 assert.equal(companyQuarterProjection({views:[{...company,quarter_outlook:{base:1200}},{scope:{type:'team',id:'t'},quarter_outlook:{base:900}}]},900),1200);
 assert.equal(companyQuarterProjection(undefined,900),900);
});
test('target adapter withholds quarter-to-week comparison and retains exact supported week',async()=>{
 const {targetForecasts}=await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);
 const view={run_id:'r',scope:{type:'team',id:'t'},target:{unit:'USD'},publication:{},daily:[],limitations:[],quarter_outlook:{start:'2026-10-01',end:'2027-01-01',base:1000}};
 const period={start:'2026-10-19',end:'2026-10-25'};
 assert.equal(targetForecasts({views:[view]},period)[0].status,'unavailable');
 assert.equal(targetForecasts({views:[{...view,planning_period_outlook:{start:'2026-10-19',end:'2026-10-26',base:90}}]},period)[0].projected,90);
});
