import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { stripTypeScriptTypes } from 'node:module';
const path = new URL('./driver-insights.ts', import.meta.url);
const source = fs.existsSync(path) ? stripTypeScriptTypes(fs.readFileSync(path, 'utf8')) : '';
const selectors = await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);
const rank = input => { assert.equal(typeof selectors.rankForecastInsights, 'function', 'A scoped forecast insight selector is required'); return selectors.rankForecastInsights(input); };
const scope = { type:'team', id:'research', name:'Research' };
const target = { unit:'USD', quantity:'spend', basis:'planning', timezone:'UTC' };
const driver = (id, extra = {}) => ({ id, title:id, scope:{team_id:'research'}, ...extra });
const effect = (driver_id, base_delta, extra = {}) => ({driver_id,scope,available:true,base_delta,with_base:1000,without_base:1000-base_delta,...extra});
const view = extra => ({run_id:'issued-7',scope,target,quarter_outlook:{start:'2026-10-01',end:'2027-01-01',base:1000},daily:[],weekly:[],cumulative:[],included_drivers:[],queued_changes:[],limitations:[],...extra});

test('ranks available signed effects by magnitude and shows five without adding them', () => {
  const ids = ['small','decrease','increase','zero','fourth','fifth','sixth'];
  const result = rank({view:view({included_drivers:ids.map(id=>driver(id)),driver_effects:ids.map((id,i)=>effect(id,[10,-300,200,0,80,60,20][i]))}),limit:5});
  assert.deepEqual(result.map(row=>[row.driver.id,row.delta]),[['decrease',-300],['increase',200],['fourth',80],['fifth',60],['sixth',20]]);
  assert.ok(result.every(row=>row.status==='modeled'));
});

test('zero remains modeled while missing, nonfinite or unavailable comparisons do not rank', () => {
  const ids = ['zero','missing','invalid','unavailable'];
  const result = rank({view:view({included_drivers:ids.map(id=>driver(id)),driver_effects:[effect('zero',0),effect('missing',null),effect('invalid',Infinity),effect('unavailable',40,{available:false})]})});
  assert.deepEqual(result.map(row=>[row.driver.id,row.status,row.delta]),[['zero','modeled',0],['invalid','included',null],['missing','included',null],['unavailable','included',null]]);
});

test('rejects wrong scope, wrong run, conflicting target and a different horizon', () => {
  const ids = ['scope','run','unit','horizon','unknown','correct'];
  const result = rank({view:view({included_drivers:ids.map(id=>driver(id)),driver_effects:[effect('scope',900,{scope:{type:'team',id:'product'}}),effect('run',800,{run_id:'newer-8'}),effect('unit',700,{target:{...target,unit:'tokens'}}),effect('horizon',600,{horizon:{kind:'quarter',start:'2026-11-01',end:'2027-01-01'}}),effect('unknown',500,{scope:undefined}),effect('correct',100)]})});
  assert.deepEqual(result.filter(row=>row.status==='modeled').map(row=>row.driver.id),['correct']);
  assert.ok(result.filter(row=>row.driver.id!=='correct').every(row=>row.delta===null));
});

test('unavailable target does not borrow a driver effect or turn into zero', () => {
  const result = rank({view:view({quarter_outlook:{start:'2026-10-01',end:'2027-01-01',base:null},included_drivers:[driver('d')],driver_effects:[effect('d',30)]})});
  assert.equal(result[0].status,'included');
  assert.equal(result[0].delta,null);
});

test('excludes Product context from Research while retaining explicit cross-team and unknown applicability', () => {
  const result = rank({view:view({included_drivers:[driver('cross-team',{scope:{team_id:'product'}})],driver_effects:[effect('cross-team',-75)]}),evidence:[{drivers:[driver('unrelated',{scope:{team_id:'product'},status:'context_only'}),driver('research-note',{status:'context_only'}),driver('unknown',{scope:undefined,status:'context_only'})]}]});
  assert.deepEqual(result.map(row=>[row.driver.id,row.status]),[['cross-team','modeled'],['research-note','context'],['unknown','unknown_scope']]);
  assert.ok(result.filter(row=>row.status!=='modeled').every(row=>row.delta===null));
});

test('queued evidence never inherits a numerical effect and duplicate identity retains issued source', () => {
  const issued = driver('same',{source_revision:1});
  const result = rank({view:view({included_drivers:[issued,issued],queued_changes:[driver('queued')],driver_effects:[effect('same',40),effect('same',40),effect('queued',900)]}),evidence:[{drivers:[driver('same',{source_revision:2}),driver('queued'),driver('note',{status:'context_only',paired_effect:{base_delta:500}})]}]});
  assert.deepEqual(result.map(row=>[row.driver.id,row.status,row.delta]),[['same','modeled',40],['queued','queued',null],['note','context',null]]);
  assert.equal(result[0].driver.source_revision,1);
});

test('conflicting duplicate effects cannot silently select an arbitrary value', () => {
  const result = rank({view:view({included_drivers:[driver('d')],driver_effects:[effect('d',40),effect('d',80)]})});
  assert.equal(result[0].status,'included');
  assert.equal(result[0].delta,null);
});

test('context with another run is excluded and forecast follow-up stays pinned to original view', () => {
  const issued = view({included_drivers:[driver('d')],driver_effects:[effect('d',40)]});
  assert.deepEqual(rank({view:issued,evidence:[{run_id:'newer-8',drivers:[driver('new-note')]}]}).map(row=>row.driver.id),['d']);
  assert.equal(typeof selectors.driverQuestion,'function');
  const question = selectors.driverQuestion(rank({view:issued})[0]);
  assert.deepEqual(question.context,{action:'explain',run_id:'issued-7',scope_type:'team',scope_id:'research',driver_id:'d'});
  assert.match(question.prompt,/2026-10-01.*2027-01-01/);
});

test('context-only records stay nonnumerical even when mistakenly present among included drivers', () => {
  const result = rank({view:view({included_drivers:[driver('note',{status:'context_only'})],driver_effects:[effect('note',500)]})});
  assert.equal(result[0].status,'context');
  assert.equal(result[0].delta,null);
});

test('rejects a comparison whose issued baseline contradicts the selected quarter', () => {
  const result = rank({view:view({included_drivers:[driver('stale')],driver_effects:[effect('stale',70,{with_base:900,without_base:830})]})});
  assert.equal(result[0].status,'included');
  assert.equal(result[0].delta,null);
});
