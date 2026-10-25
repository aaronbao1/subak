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
let state;
let BudgetRequestsOverview;
try {
  Module._resolveFilename = function(request, parent, ...rest) { return originalResolve.call(this, request.startsWith('@/') ? path.join(frontend, 'src', request.slice(2)) : request, parent, ...rest); };
  Module._load = function(request, parent, ...rest) {
    if (request === '@/lib/store') return { useAppStore: () => state };
    if (request === './request-dialogs') return { RequestDialogs: () => null };
    return originalLoad.call(this, request, parent, ...rest);
  };
  for (const ext of ['.ts', '.tsx']) require.extensions[ext] = (loaded, filename) => loaded._compile(ts.transpileModule(fs.readFileSync(filename, 'utf8'), { fileName: filename, compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true } }).outputText, filename);
  ({ BudgetRequestsOverview } = require(path.join(frontend, 'src/components/requests/budget-requests-overview.tsx')));
} finally {
  Module._resolveFilename = originalResolve;
  Module._load = originalLoad;
  for (const ext of ['.ts', '.tsx']) { if (extensions[ext]) require.extensions[ext] = extensions[ext]; else delete require.extensions[ext]; }
}
const request = (id, amount) => ({ id, teamId: 'research', title: `Request ${id}`, status: 'submitted', requestedAmount: amount, remainingRequestedAmount: amount, periodStart: '2026-10-19', periodEndExclusive: '2026-10-26', source: { submittedAt: '2026-10-25T12:00:00Z' } });
function render(requests) {
  state = { company: { currentPeriod: { start: '2026-10-19', end: '2026-10-25' } }, teams: [{ id: 'research', name: 'Research' }], requests, requestState: 'ready', loadRequests() {} };
  return renderToStaticMarkup(React.createElement(BudgetRequestsOverview));
}
function requestedSummary(html) {
  const match = html.match(/Still requested<\/dt><dd class="([^"]*)">([^<]+)<\/dd>/);
  assert.ok(match, 'Still requested summary is rendered');
  return { className: match[1], text: match[2] };
}
test('all amountless updates show a compact unknown total and preserve input amounts', () => {
  const requests = [request('one', null), request('two', null), request('three', null)];
  const before = structuredClone(requests);
  const html = render(requests);
  const summary = requestedSummary(html);
  assert.equal(summary.text, 'Not specified');
  assert.match(summary.className, /text-base/);
  assert.doesNotMatch(summary.className, /text-2xl/);
  assert.match(html, /3 without an amount/);
  assert.deepEqual(requests, before);
});
test('an explicit zero is a known monetary total', () => {
  const html = render([request('zero', '0.00')]);
  assert.equal(requestedSummary(html).text, '$0');
  assert.match(requestedSummary(html).className, /text-2xl/);
  assert.doesNotMatch(html, /without an amount/);
});
test('mixed updates retain the explicit subtotal and unknown count', () => {
  const html = render([request('unknown', null), request('known', '50.25')]);
  assert.equal(requestedSummary(html).text, '$50.25');
  assert.match(html, /1 without an amount/);
});
test('an empty inbox may show zero with no unknown amount warning', () => {
  const html = render([]);
  assert.equal(requestedSummary(html).text, '$0');
  assert.match(html, /No open requests for this period/);
  assert.doesNotMatch(html, /without an amount/);
});
