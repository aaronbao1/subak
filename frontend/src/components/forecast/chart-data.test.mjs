import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { stripTypeScriptTypes } from 'node:module';
const source = stripTypeScriptTypes(fs.readFileSync(new URL('./chart-data.ts', import.meta.url), 'utf8'));
const { forecastChartRows, chartDate, chartMoney } = await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);
const view = {
  daily: [{date:'2026-10-26',base:12}, {date:'2026-10-27',base:null}, {date:'2026-10-28',base:0}],
  weekly: [{start:'2026-10-26',end:'2026-11-02',base:84,partial:false}],
  cumulative: [{date:'2026-10-26',base:32,low:20,high:44,historical_error_interval:{80:{status:'available_assumption_conditional',lower:25,upper:39}}}],
};
test('chart preserves exact supplied horizon, gaps, zero and immutable publication', () => {
  const before = structuredClone(view);
  assert.deepEqual(forecastChartRows(view,'daily').map(row => [row.date,row.base]), [['2026-10-26',12],['2026-10-27',null],['2026-10-28',0]]);
  assert.equal(forecastChartRows(view,'weekly')[0].date,'2026-11-02');
  assert.equal(forecastChartRows(view,'cumulative')[0].base,32);
  assert.deepEqual(view,before);
});
test('scenario and historical ranges remain independent and unavailable bounds stay absent', () => {
  const row = forecastChartRows(view,'cumulative')[0];
  assert.deepEqual(row.scenario,[20,44]);
  assert.deepEqual(row.error,[25,39]);
  assert.equal(forecastChartRows(view,'cumulative','95')[0].error,undefined);
  assert.equal(forecastChartRows({...view,cumulative:[{date:'2026-10-26',base:32,low:null,high:44}]},'cumulative')[0].scenario,undefined);
});
test('finance chart labels use readable UTC dates and explicit compact currency', () => {
  assert.equal(chartDate('2026-10-26'),'Oct 26');
  assert.equal(chartMoney(250000,'USD',true),'$250K');
  assert.equal(chartMoney(null,'USD'),'Unavailable');
  assert.equal(chartMoney(0,'USD'),'$0');
});
