import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import Module, { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

const frontend = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../..');
const require = createRequire(path.join(frontend, 'package.json'));
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');
const ts = require('typescript');
const originalResolve = Module._resolveFilename;
const originalLoad = Module._load;
const extensions = Object.fromEntries(['.ts', '.tsx'].map(ext => [ext, require.extensions[ext]]));
let ForecastSummary, CalculationDetails, DriverDetail, DriverOverview, PlanningCalendar, ProvenanceBadge;
try {
  Module._resolveFilename = function(request, parent, ...rest) { return originalResolve.call(this, request.startsWith('@/') ? path.join(frontend, 'src', request.slice(2)) : request, parent, ...rest); };
  Module._load = function(request, parent, ...rest) {
    if (request === '@/lib/store') return { useAppStore: select => select({ askForecastAssistant() {} }) };
    if (request === '@/components/ui/sheet') {
      const part = tag => function SheetPart({ children }) { return React.createElement(tag, null, children); };
      return { Sheet: ({ open, children }) => open ? React.createElement('div', null, children) : null, SheetContent: part('aside'), SheetHeader: part('header'), SheetTitle: part('h2'), SheetDescription: part('p') };
    }
    return originalLoad.call(this, request, parent, ...rest);
  };
  for (const ext of ['.ts', '.tsx']) require.extensions[ext] = (module, filename) => module._compile(ts.transpileModule(fs.readFileSync(filename, 'utf8'), { fileName: filename, compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true } }).outputText, filename);
  ({ ForecastSummary } = require(path.join(frontend, 'src/components/forecast/forecast-summary.tsx')));
  ({ CalculationDetails } = require(path.join(frontend, 'src/components/forecast/calculation-details.tsx')));
  ({ DriverDetail } = require(path.join(frontend, 'src/components/forecast/driver-detail.tsx')));
  ({ DriverOverview } = require(path.join(frontend, 'src/components/forecast/driver-overview.tsx')));
  ({ PlanningCalendar } = require(path.join(frontend, 'src/components/forecast/planning-calendar.tsx')));
  ({ ProvenanceBadge } = require(path.join(frontend, 'src/components/team/labels.tsx')));
} finally {
  Module._resolveFilename = originalResolve; Module._load = originalLoad;
  for (const ext of ['.ts', '.tsx']) { if (extensions[ext]) require.extensions[ext] = extensions[ext]; else delete require.extensions[ext]; }
}
const render = (Component, props) => renderToStaticMarkup(React.createElement(Component, props));
const forbiddenCopy = /demo|scripted|synthetic|fixture|verified/i;

test('usage value badge and spend summary are neutral without changing monetary values', () => {
  const badge = render(ProvenanceBadge, { provenance: 'simulated' });
  assert.match(badge, /Usage value/); assert.match(badge, /from the loaded dataset/); assert.doesNotMatch(badge, forbiddenCopy);
  const summary = { observed: { amount: 123.45, complete: false, byProvenance: { simulated: 123.45, estimate: 0 } }, issued: { synthetic: true, amount: 200 }, allocation: 300, variance: -100, target: { unit: 'usd' } };
  const html = render(ForecastSummary, { summary, periodLabel: 'This week' });
  assert.match(html, /Recorded spend/); assert.match(html, /partial day/); assert.match(html, /\$123\.45/); assert.doesNotMatch(html, forbiddenCopy);
  assert.equal(summary.issued.synthetic, true);
});

test('calculation details omit developer copy and retain missing coverage, calibration and error warnings', () => {
  const view = { run_id: 'synthetic-ui-run-1', target: { unit: 'usd', quantity: 'spend', basis: 'planning' }, scope: { type: 'company', id: null }, weekly: [], quarter_outlook: { base: null, assumptions: ['Supplied synthetic planning totals, then constant observed-rate continuation. No numerical forecast engine or calibration has run.'] }, limitations: ['Synthetic illustration with supplied weekly totals; no forecast engine or calibration has run.', 'Earlier quarter observations are unavailable, so the quarter total is withheld.'], historical_error_interval: null };
  const evidence = [{ id: 'fixture-source-1', status: 'failed', last_error: 'Source unavailable: missing coverage.', drivers: [] }];
  const before = JSON.stringify({ view, evidence });
  const html = render(CalculationDetails, { view, evidence });
  assert.doesNotMatch(html, forbiddenCopy); assert.match(html, /Earlier quarter observations are unavailable/); assert.match(html, /No numerical forecast engine or calibration has run/); assert.match(html, /missing coverage/); assert.match(html, /failed/);
  assert.equal(JSON.stringify({ view, evidence }), before);
});

test('expanded assumption details retain exact comparisons and omit raw internal metadata', () => {
  const insight = { title: 'Workload change', reason: 'Synthetic source context has no measured financial effect.', sourceSummary: 'Research plan', runId: 'synthetic-run-1', scope: { type: 'company', id: null }, target: { unit: 'usd' }, horizon: { start: '2026-10-01', end: '2027-01-01' }, inSnapshot: false, status: 'context', delta: 10.125, driver: { id: 'synthetic-driver', source_id: 'fixture-source', source_revision: 'demo-revision', parameters: { is_synthetic: true, multiplier: 1.25, note: 'Timing information unavailable.' }, citations: [{ title: 'Research plan', excerpt: 'Missing timing information.' }] }, effect: { available: true, driver_id: 'synthetic-driver', run_id: 'synthetic-run-1', with_base: 110.125, without_base: 100, base_delta: 10.125, qualification: 'No causal effect established.' } };
  const before = JSON.stringify(insight);
  const html = render(DriverDetail, { insight, onClose() {} });
  assert.doesNotMatch(html, forbiddenCopy); assert.match(html, /110\.125/); assert.match(html, /1\.25/); assert.match(html, /Missing timing information/); assert.match(html, /has no measured financial effect/); assert.match(html, /No causal effect established/);
  assert.equal(JSON.stringify(insight), before);
});


test('source passages preserve domain language and whitespace exactly', () => {
  const passage = 'Synthetic biology uses test fixtures.\n  Preserve the original research wording.';
  const insight = { title: 'Research workload', reason: 'Source context; no modeled financial effect is supplied.', sourceSummary: passage, runId: 'run-1', scope: { type: 'company', id: null }, target: { unit: 'usd' }, horizon: { start: '2026-10-01', end: '2027-01-01' }, inSnapshot: false, status: 'context', delta: null, driver: { id: 'driver-1', citations: [{ title: 'Research plan', excerpt: passage }] } };
  const html = render(DriverDetail, { insight, onClose() {} });
  assert.ok(html.includes(passage), 'the cited source passage is displayed verbatim');
  assert.equal(insight.driver.citations[0].excerpt, passage);
});


test('overview and planning source excerpts retain business terminology', () => {
  const passage = 'Synthetic biology uses test fixtures.';
  const scope = { type: 'company', id: null };
  const driver = { id: 'research-workload', title: 'Research workload', scope, effective_from: '2026-11-01', citations: [{ excerpt: passage }] };
  const view = { run_id: 'run-1', scope, target: { unit: 'usd' }, quarter_outlook: { start: '2026-10-01', end: '2027-01-01', base: 100 }, included_drivers: [driver], queued_changes: [], driver_effects: [{ scope, driver_id: driver.id, available: true, with_base: 100, without_base: 90, base_delta: 10 }] };
  for (const [Component, props] of [[DriverOverview, { view }], [PlanningCalendar, { view, onSelect() {} }]]) {
    assert.ok(render(Component, props).includes(passage), 'source summary keeps the original domain language');
  }
});
