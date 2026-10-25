import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { stripTypeScriptTypes } from 'node:module';
import Module, { createRequire } from 'node:module';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const load = async path => import(`data:text/javascript;base64,${Buffer.from(stripTypeScriptTypes(fs.readFileSync(new URL(path, import.meta.url), 'utf8'))).toString('base64')}`);
const { summarizePeople } = await load('./derive.ts');
const { quarterForecasts } = await load('../dashboard/forecast-derive.ts');
const period = { start: '2026-10-01', end: '2026-12-31' };
const person = { id: 'p', teamId: 't', name: 'Pat' };
const forecast = (projected, extra = {}) => ({ teamId: 't', period, projected, status: 'available', basis: 'full_period', unit: 'usd', assumptions: [], limitations: [], generatedAt: '2026-10-25T00:00:00Z', ...extra });
const summaries = (personForecast, teamForecast) => summarizePeople([person], 't', [], [], [personForecast], [], period, teamForecast);

test('person share includes the authoritative team residual instead of renormalizing attributed people', () => {
  const [row] = summaries(forecast(50, { personId: 'p' }), forecast(100));
  assert.equal(row.share, 0.5);
});

test('person total without frozen team attribution cannot become a current-directory team share', () => {
  const [row] = summaries(forecast(50, { personId: 'p', teamId: '' }), forecast(100));
  assert.equal(row.projected, 50);
  assert.equal(row.share, undefined);
});

test('missing or unavailable team total never turns one known person into 100 percent', () => {
  assert.equal(summaries(forecast(50, { personId: 'p' }), undefined)[0].share, undefined);
  assert.equal(summaries(forecast(50, { personId: 'p' }), forecast(undefined, { status: 'unavailable' }))[0].share, undefined);
});

test('canonical daily details survive quarter adaptation without extrapolation or unavailable days becoming zero', () => {
  const [result] = quarterForecasts({ views: [{
    id: 'v', run_id: 'r', scope: { type: 'team', id: 't' }, target: { unit: 'USD' },
    publication: {}, limitations: [], included_drivers: [], queued_changes: [], weekly: [], cumulative: [],
    quarter_outlook: { start: '2026-10-01', end: '2027-01-01', base: 1000 },
    daily: [{ date: '2026-10-26', base: 20 }, { date: '2026-10-27', base: null }, { date: '2026-10-28', base: 0 }],
  }] });
  assert.equal(result.projected, 1000);
  assert.deepEqual(result.daily, [{ date: '2026-10-26', projected: 20 }, { date: '2026-10-28', projected: 0 }]);
});

function withProductModules(run) {
  const frontend = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../..');
  const require = createRequire(path.join(frontend, 'package.json'));
  const ts = require('typescript');
  const resolve = Module._resolveFilename;
  const extensions = Object.fromEntries(['.ts', '.tsx'].map(ext => [ext, require.extensions[ext]]));
  Module._resolveFilename = function(request, parent, ...rest) {
    return resolve.call(this, request.startsWith('@/') ? path.join(frontend, 'src', request.slice(2)) : request, parent, ...rest);
  };
  for (const ext of ['.ts', '.tsx']) require.extensions[ext] = (module, filename) => {
    const { outputText } = ts.transpileModule(fs.readFileSync(filename, 'utf8'), { fileName: filename, compilerOptions: {
      module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true,
    } });
    module._compile(outputText, filename);
  };
  try {
    return run(require, frontend);
  } finally {
    Module._resolveFilename = resolve;
    for (const ext of ['.ts', '.tsx']) {
      if (extensions[ext]) require.extensions[ext] = extensions[ext];
      else delete require.extensions[ext];
    }
  }
}

test('published daily detail reaches real chart derivations with gaps and no quarter extrapolation', () => withProductModules((require, frontend) => {
    const { buildDailyRows, summarizeTeams, projectedDays } = require(path.join(frontend, 'src/components/dashboard/derive.ts'));
    const forecasts = quarterForecasts({ views: [{
      run_id: 'r', scope: { type: 'team', id: 't' }, target: { unit: 'USD' }, limitations: [],
      quarter_outlook: { start: '2026-10-01', end: '2027-01-01', base: 1000 },
      daily: [{ date: '2026-10-26', base: 20 }, { date: '2026-10-27', base: null }, { date: '2026-10-28', base: 0 }],
    }] });
    const teams = [{ id: 't', name: 'Team' }];
    const spending = [{ teamId: 't', date: '2026-10-25', amount: 5, complete: true, component: 'api', provider: 'a', unit: 'usd', provenance: 'estimate' }];
    const rows = buildDailyRows(teams, spending, forecasts, period);
    assert.equal(rows.find(r => r.date === '2026-10-26').p_t, 20);
    assert.equal(rows.find(r => r.date === '2026-10-27').p_t, null);
    assert.equal(rows.find(r => r.date === '2026-10-28').p_t, 0);
    assert.equal(rows.find(r => r.date === '2026-10-29').p_t, null);
    assert.equal(rows.find(r => r.date === '2026-12-31').p_t, null);
    assert.deepEqual(summarizeTeams(teams, spending, [], forecasts)[0].dailyProjected.map(d => [d.date, d.amount]), [['2026-10-26', 20], ['2026-10-28', 0]]);
    assert.deepEqual(projectedDays(forecasts[0], new Set(['2026-10-26'])), [{ date: '2026-10-28', projected: 0 }]);
}));

test('evidence interpretation receipts remain visible before the first forecast publication', () => withProductModules((require, frontend) => {
  const React = require('react');
  const { renderToStaticMarkup } = require('react-dom/server');
  const { ForecastPanel } = require(path.join(frontend, 'src/components/forecast/forecast-panel.tsx'));
  const { useAppStore } = require(path.join(frontend, 'src/lib/store.ts'));
  const initial = useAppStore.getInitialState();
  const previous = { forecastBundle: initial.forecastBundle, forecastEvidence: initial.forecastEvidence };
  try {
    Object.assign(initial, { forecastBundle: { views: [] }, forecastEvidence: [
      { id: 'j1', envelope: { source_id: 'pending-source' }, drivers: [], status: 'queued', queue_status: 'interpreting' },
      { id: 'j2', envelope: { source_id: 'failed-source' }, drivers: [], status: 'failed', queue_status: 'interpretation_failed', last_error: 'Invalid source date' },
    ] });
    const html = renderToStaticMarkup(React.createElement(ForecastPanel));
    assert.match(html, /pending-source/);
    assert.match(html, /queued/);
    assert.match(html, /failed-source/);
    assert.match(html, /Invalid source date/);
  } finally { Object.assign(initial, previous); }
}));

test('supported daily details remain chartable when the conditional quarter is unavailable', () => withProductModules((require, frontend) => {
  const { projectedDays } = require(path.join(frontend, 'src/components/dashboard/derive.ts'));
  const [result] = quarterForecasts({ views: [{
    run_id: 'r', scope: { type: 'team', id: 't' }, target: { unit: 'USD' }, limitations: [],
    quarter_outlook: { start: '2026-10-01', end: '2027-01-01', base: null },
    daily: [{ date: '2026-10-26', base: 20 }, { date: '2026-10-27', base: 30 }],
  }] });
  assert.equal(result.status, 'unavailable');
  assert.deepEqual(projectedDays(result, new Set()), [{ date: '2026-10-26', projected: 20 }, { date: '2026-10-27', projected: 30 }]);
  const unavailableLegacy = forecast(undefined, { status: 'unavailable', daily: [{ date: '2026-10-26', projected: 99 }] });
  assert.deepEqual(projectedDays(unavailableLegacy, new Set()), []);
}));

test('one team reporting complete actuals does not erase another team issued daily forecast', () => withProductModules((require, frontend) => {
  const { buildDailyRows, hasProjectedAmount } = require(path.join(frontend, 'src/components/dashboard/derive.ts'));
  const teams = [{ id: 't', name: 'T' }, { id: 'u', name: 'U' }];
  const forecasts = teams.map(team => forecast(100, { teamId: team.id, daily: [{ date: '2026-10-26', projected: 20 }, { date: '2026-10-27', projected: 30 }] }));
  const spending = [{ teamId: 't', date: '2026-10-26', amount: 7, complete: true, component: 'api', provider: 'a', unit: 'usd', provenance: 'estimate' }];
  const row = buildDailyRows(teams, spending, forecasts, period).find(r => r.date === '2026-10-26');
  assert.equal(row.t_t, 7);
  assert.equal(row.t_u, null);
  assert.equal(row.p_u, 20);
  assert.equal(hasProjectedAmount(row, 'u'), true);
  assert.equal(hasProjectedAmount(row, 't'), false);
  // The chart folds small teams into Other by summing their actual and projected keys.
  assert.equal(hasProjectedAmount({ ...row, t_other: 7, p_other: 27 }, 'other'), true);
  const React = require('react');
  const { renderToStaticMarkup } = require('react-dom/server');
  const { SpendByTeamChart } = require(path.join(frontend, 'src/components/dashboard/spend-by-team-chart.tsx'));
  const html = renderToStaticMarkup(React.createElement(SpendByTeamChart, { teams, rows: [row], partialDates: [], unit: 'usd', period, selectedId: null, onSelect() {} }));
  assert.match(html, /Dashed lines and hollow dots are projections/);
}));
