/* eslint-disable @typescript-eslint/no-require-imports -- This standalone SSR harness loads product TSX through CommonJS. */
/**
 * Render the real forecast components with backend-generated synthetic artifacts.
 * No product module is stubbed. This does not test browser hydration, interaction,
 * layout, CSS, fonts, transport, or live providers. Run with --help for inputs.
 */
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const fs = require('node:fs');
const Module = require('node:module');
const path = require('node:path');
const { parseArgs } = require('node:util');

const root = path.resolve(__dirname, '../..');
const { values } = parseArgs({
  options: {
    bundle: { type: 'string' },
    'evidence-payload': { type: 'string' },
    'unavailable-bundle': { type: 'string' },
    'frontend-root': { type: 'string' },
    'output-dir': { type: 'string' },
    report: { type: 'string' },
    html: { type: 'boolean', default: false },
    help: { type: 'boolean', default: false },
  },
});
if (values.help) {
  console.log(`Usage: node frontend/tests/render-forecast.cjs [options]

--bundle PATH              Published synthetic demo bundle. Defaults to
                           artifacts/northstar-integration/published-forecast.json
                           relative to the repository root.
--evidence-payload PATH    Optional backend fixture containing bundle, evidence,
                           context, teams, people, source_id, driver_id,
                           queued_driver_id, and context_driver_id. Expects five
                           included drivers, two frozen context-only exclusions,
                           one later queued driver and one later context-only
                           driver, with no legacy context and a shared residual.
--unavailable-bundle PATH  Optional real API bundle with unavailable current_actuals.
--frontend-root PATH       Alternative frontend source tree for regression checks.
                           Defaults to this repository's frontend directory.
--output-dir PATH          Output directory; defaults to artifacts/forecast-ui-render
                           relative to the repository root.
--report PATH              JSON report path; defaults to OUTPUT_DIR/report.json.
--html                     Also save rendered HTML in OUTPUT_DIR/html (no styling).
--help                     Print this help without loading dependencies.

Explicit paths resolve against the current working directory. Optional cases
omitted from the command are reported as not_requested, never as passing.
The current frontend dependencies must be installed. Runtime versions and source
hashes are recorded; this command is SSR evidence, not a production/browser check.`);
  process.exit(0);
}

const frontend = values['frontend-root'] ? path.resolve(values['frontend-root']) : path.join(root, 'frontend');
const sourceRoot = path.join(frontend, 'src');
const out = values['output-dir'] ? path.resolve(values['output-dir']) : path.join(root, 'artifacts/forecast-ui-render');
const reportPath = values.report ? path.resolve(values.report) : path.join(out, 'report.json');
const bundlePath = values.bundle ? path.resolve(values.bundle) : path.join(root, 'artifacts/northstar-integration/published-forecast.json');
const localRequire = Module.createRequire(path.join(frontend, 'package.json'));
const ts = localRequire('typescript');
const sha256 = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const relative = filename => path.relative(root, filename).split(path.sep).join('/');
function readArtifact(filename) {
  const absolute = path.resolve(filename);
  assert.ok(fs.existsSync(absolute), `Artifact missing: ${relative(absolute)}. Generate it first or provide an explicit path; see --help.`);
  const bytes = fs.readFileSync(absolute);
  return { data: JSON.parse(bytes), artifact: relative(absolute), sha256: sha256(bytes) };
}
function saveHtml(name, html) {
  if (!values.html) return null;
  const filename = path.join(out, 'html', name);
  fs.mkdirSync(path.dirname(filename), { recursive: true });
  fs.writeFileSync(filename, `<!doctype html><meta charset="utf-8">${html}`);
  return relative(filename);
}
const amount = (value, unit = 'usd') => `${unit.toUpperCase()} ${new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 }).format(value)}`;
const text = html => html.replace(/<[^>]*>/g, '').replace(/&amp;/g, '&').replace(/&gt;/g, '>').replace(/&lt;/g, '<').replace(/&#x27;/g, "'").replace(/&quot;/g, '"');

// Transpile product TS/TSX verbatim and resolve its normal @/ alias. React,
// Zustand, Next, Base UI, and Recharts implementations remain genuine modules.
const resolve = Module._resolveFilename;
Module._resolveFilename = function(request, parent, ...rest) {
  return resolve.call(this, request.startsWith('@/') ? path.join(sourceRoot, request.slice(2)) : request, parent, ...rest);
};
for (const ext of ['.ts', '.tsx']) require.extensions[ext] = function(module, filename) {
  const { outputText } = ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
    fileName: filename,
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true },
  });
  module._compile(outputText, filename);
};
const React = localRequire('react');
const { renderToStaticMarkup } = localRequire('react-dom/server');
const { useAppStore } = require(path.join(sourceRoot, 'lib/store.ts'));
const { ForecastPanel } = require(path.join(sourceRoot, 'components/forecast/forecast-panel.tsx'));
const initial = useAppStore.getInitialState();
const originalState = { ...initial };
function setSsrState(patch) {
  // Zustand's actual SSR snapshot is supplied with the provided backend JSON.
  // Methods/effects are not invoked; this is not a mock API or network test.
  Object.assign(initial, originalState, patch);
}
const renderPanel = props => renderToStaticMarkup(React.createElement(ForecastPanel, props));

function verifyScopes(artifact) {
  const bundle = artifact.data;
  assert.ok(Array.isArray(bundle.views) && bundle.views.length, 'published bundle has views');
  setSsrState({ forecastBundle: bundle, forecastEvidence: [], people: [] });
  const scopes = [];
  for (const view of bundle.views.filter(v => ['company', 'team', 'person'].includes(v.scope.type))) {
    assert.equal(view.daily.length, 7, `${view.scope.id}: complete demo fixture has seven daily points`);
    assert.equal(view.weekly.length, 4, `${view.scope.id}: complete demo fixture has four weekly buckets`);
    assert.ok(view.weekly.every(point => Number.isFinite(point.base)), `${view.scope.id}: demo weekly totals are available`);
    assert.ok(Number.isFinite(view.quarter_outlook.base), `${view.scope.id}: demo quarter total is available`);
    const html = renderPanel({ scopeType: view.scope.type, scopeId: view.scope.id });
    const visible = text(html);
    const title = `${view.scope.type === 'company' ? 'Company' : view.scope.name ?? view.scope.type} forecast`;
    const money = value => amount(value, view.target.unit);
    assert.ok(visible.includes(title), `${view.scope.id}: scoped title`);
    assert.ok(visible.includes(`Run ${view.run_id}`), `${view.scope.id}: immutable run`);
    assert.ok(visible.includes('Synthetic demo'), `${view.scope.id}: synthetic qualification`);
    assert.ok(visible.includes('no confidence or coverage level'), `${view.scope.id}: descriptive scenario qualification`);
    assert.ok(visible.includes('Insufficient matching mature issued outcomes; no coverage claim.'), `${view.scope.id}: unavailable historical error`);
    assert.ok(visible.includes(money(view.weekly.reduce((sum, point) => sum + point.base, 0))), `${view.scope.id}: four-week total`);
    assert.ok(visible.includes(money(view.quarter_outlook.base)), `${view.scope.id}: separate quarter total`);
    const tables = [...html.matchAll(/<tbody>([\s\S]*?)<\/tbody>/g)];
    assert.equal(tables.length, 1, `${view.scope.id}: one daily detail table`);
    const renderedRows = [...tables[0][1].matchAll(/<tr\b[^>]*>([\s\S]*?)<\/tr>/g)]
      .map(row => [...row[1].matchAll(/<td\b[^>]*>([\s\S]*?)<\/td>/g)].map(cell => text(cell[1]).trim()));
    assert.equal(renderedRows.length, view.daily.length, `${view.scope.id}: row per supplied daily point`);
    for (const [index, point] of view.daily.entries()) {
      assert.ok([point.base, point.low, point.high].every(Number.isFinite), `${view.scope.id}: demo daily values are available`);
      const cells = renderedRows[index];
      assert.equal(cells.length, 4, `${view.scope.id}: date/base/band/coverage columns`);
      assert.equal(cells[0].split(' · ')[0], point.date, `${view.scope.id}: daily date/order ${point.date}`);
      assert.equal(cells[1], money(point.base), `${view.scope.id}: daily amount ${point.date}`);
      assert.equal(cells[2], `${money(point.low)} – ${money(point.high)}`, `${view.scope.id}: daily scenario ${point.date}`);
    }
    if (view.scope.type === 'company') for (const team of bundle.views.filter(v => v.scope.type === 'team')) {
      assert.ok(html.includes(`href="/teams/${team.scope.id}"`), `company: team link ${team.scope.id}`);
    }
    const filename = `${view.scope.type}-${encodeURIComponent(view.scope.id)}.html`;
    scopes.push({ scope: view.scope, run_id: view.run_id, daily_rows: view.daily.length, included_drivers: view.included_drivers.length, html: saveHtml(filename, html), bytes: Buffer.byteLength(html), passed: true });
  }
  assert.ok(scopes.length, 'at least one supported scope was rendered');
  const missing = renderPanel({ scopeType: 'person', scopeId: 'nonexistent-render-test-scope' });
  assert.ok(text(missing).includes('No forecast has been published for this scope.'));
  assert.ok(!text(missing).includes('USD 0'));
  initial.forecastRefresh = { id: 'render-test-pending', status: 'running' };
  const pending = renderPanel({ scopeType: 'person', scopeId: 'nonexistent-render-test-scope' });
  assert.ok(pending.includes('disabled=""'));
  assert.ok(text(pending).includes('Refresh render-test-pending: running'));
  saveHtml('unavailable-pending.html', pending);
  return { artifact: artifact.artifact, sha256: artifact.sha256, scopes, unavailable_scope_passed: true, pending_refresh_passed: true };
}

function verifyEvidence(artifact) {
  const evidence = artifact.data;
  assert.equal(evidence.context.length, 0, 'fixture has canonical evidence without legacy context');
  const { quarterForecasts } = require(path.join(sourceRoot, 'components/dashboard/forecast-derive.ts'));
  const adapted = quarterForecasts(evidence.bundle);
  setSsrState({ loaded: true, forecastBundle: evidence.bundle, forecastEvidence: evidence.evidence.items, context: evidence.context, teams: evidence.teams, people: evidence.people, forecasts: adapted.filter(f => !f.personId), personForecasts: adapted.filter(f => !!f.personId) });
  const { EvidencePage } = require(path.join(sourceRoot, 'components/evidence/evidence-page.tsx'));
  const { AppRouterContext } = localRequire('next/dist/shared/lib/app-router-context.shared-runtime');
  const { PathnameContext, SearchParamsContext } = localRequire('next/dist/shared/lib/hooks-client-context.shared-runtime');
  // Real Next contexts supply routing state. SSR creates callbacks but cannot
  // prove browser event behavior; an accidental navigation call must fail.
  const router = new Proxy({}, { get: (_, key) => () => { throw new Error(`Unexpected navigation during SSR: ${String(key)}`); } });
  const element = React.createElement(AppRouterContext.Provider, { value: router },
    React.createElement(PathnameContext.Provider, { value: '/evidence' },
      React.createElement(SearchParamsContext.Provider, { value: new URLSearchParams() }, React.createElement(EvidencePage))));
  const html = renderToStaticMarkup(element);
  const visible = text(html);
  const htmlPath = saveHtml('evidence-page.html', html);
  const company = evidence.bundle.views.find(view => view.scope.type === 'company');
  const teamSum = evidence.bundle.views.filter(view => view.scope.type === 'team').reduce((sum, view) => sum + view.quarter_outlook.base, 0);
  const money = value => amount(value, company.target.unit);
  assert.ok(Math.abs(company.quarter_outlook.base - teamSum) > 1, 'shared residual distinguishes company from team sum');
  assert.ok(visible.includes(money(company.quarter_outlook.base)), 'evidence page shows authoritative company quarter');
  assert.ok(!visible.includes(money(teamSum)), 'team sum is not substituted for company quarter');
  assert.ok(visible.includes(`Run ${company.run_id}`), 'evidence retains exact run');
  for (const phrase of ['Company context', 'No company context linked yet', 'Current actuals received through', 'Shared / unallocated']) assert.ok(visible.includes(phrase), `evidence page: ${phrase}`);
  assert.ok(!visible.includes('No evidence yet'), 'empty legacy context does not claim no forecast evidence');
  const drivers = evidence.evidence.items.flatMap(item => item.drivers ?? []);
  const included = drivers.find(driver => driver.id === evidence.driver_id);
  assert.ok(included && company.included_drivers.some(driver => driver.id === included.id), 'new source is included in publication');
  assert.ok(visible.includes(included.title ?? included.kind.replaceAll('_', ' ')), 'canonical driver label renders');
  // Independent fixture facts, not the component's own classification helper:
  // five included, two frozen exclusions, one later queued, one later context-only.
  assert.equal(company.included_drivers.length, 5);
  assert.equal(company.queued_changes.filter(driver => driver.status === 'context_only' && driver.publication_status === 'excluded').length, 2);
  assert.equal(drivers.find(driver => driver.id === evidence.queued_driver_id)?.queue_status, 'queued');
  assert.equal(drivers.find(driver => driver.id === evidence.context_driver_id)?.queue_status, 'context_only');
  const expected = { Included: 5, Queued: 1, 'Context only': 3 };
  const counts = {};
  for (const [status, count] of Object.entries(expected)) {
    counts[status] = (html.match(new RegExp(`>\\s*${status}\\s*</span>`, 'g')) ?? []).length;
    assert.equal(counts[status], count, `evidence accurately renders ${status}`);
  }
  const context = drivers.find(driver => driver.id === evidence.context_driver_id);
  assert.ok(visible.includes(context.publication_reason ?? context.reason), 'context-only reason renders');
  return { status: 'passed', artifact: artifact.artifact, sha256: artifact.sha256, canonical_evidence_items: evidence.evidence.items.length, legacy_context_items: evidence.context.length, company_quarter: company.quarter_outlook.base, team_sum: teamSum, shared_residual: company.quarter_outlook.base - teamSum, rendered_status_counts: counts, new_canonical_source: evidence.source_id, new_canonical_driver: evidence.driver_id, queued_driver: evidence.queued_driver_id, context_only_driver: evidence.context_driver_id, html: htmlPath };
}

function verifyUnavailableActuals(artifact) {
  const bundle = artifact.data;
  setSsrState({ forecastBundle: bundle, forecastEvidence: [] });
  assert.equal(bundle.current_actuals.status, 'unavailable');
  assert.ok(bundle.current_actuals.reason, 'actual unavailable response includes a reason');
  const html = renderPanel();
  assert.ok(text(html).includes(bundle.current_actuals.reason), 'backend outage reason renders');
  assert.ok(text(html).includes(`Run ${bundle.run_id}`), 'frozen publication remains visible during current-actuals outage');
  assert.ok(!text(html).includes('Current actuals received through unknown'), 'unavailable actuals does not masquerade as unknown success');
  return { status: 'passed', artifact: artifact.artifact, sha256: artifact.sha256, run_id: bundle.run_id, actuals_status: bundle.current_actuals.status, reason: bundle.current_actuals.reason, html: saveHtml('current-actuals-unavailable.html', html) };
}

const publication = verifyScopes(readArtifact(bundlePath));
const evidencePage = values['evidence-payload'] ? verifyEvidence(readArtifact(values['evidence-payload'])) : { status: 'not_requested' };
const unavailableActuals = values['unavailable-bundle'] ? verifyUnavailableActuals(readArtifact(values['unavailable-bundle'])) : { status: 'not_requested' };
const sourceSha256 = Object.fromEntries(Object.keys(require.cache)
  .filter(filename => filename.startsWith(`${sourceRoot}${path.sep}`))
  .sort().map(filename => [relative(filename), sha256(fs.readFileSync(filename))]));
const manifest = JSON.parse(fs.readFileSync(path.join(frontend, 'package.json'), 'utf8'));
const runtime = Object.fromEntries(['next', 'react', 'react-dom', 'zustand', 'recharts', 'typescript'].map(name => [name, {
  installed: localRequire(`${name}/package.json`).version,
  requested: manifest.dependencies?.[name] ?? manifest.devDependencies?.[name],
}]));
const report = {
  status: 'passed', generated_at: new Date().toISOString(), harness: relative(__filename), harness_sha256: sha256(fs.readFileSync(__filename)), frontend: relative(frontend), node: process.version,
  runtime, sourceSha256, publication, evidence_page: evidencePage, current_actuals_unavailable: unavailableActuals,
  limitations: [
    'Backend-generated synthetic fixture inputs do not establish enterprise accuracy or live-provider behavior.',
    'Actual store initial snapshot and real Next contexts supplied for SSR; navigation forbidden.',
    'No browser, hydration, effects, event-handler, network, chart geometry, CSS, font, or production-build verification.',
    'Recharts has no layout dimensions during SSR; its dimension warnings are expected and do not verify charts.',
    'Installed versus requested dependency versions are recorded; a successful run does not prove compatibility with other versions.',
    'Optional cases reported not_requested were not exercised.',
  ],
};
fs.mkdirSync(path.dirname(reportPath), { recursive: true });
fs.writeFileSync(reportPath, `${JSON.stringify(report, null, 2)}\n`);
console.log(JSON.stringify({ status: 'passed', scopes: publication.scopes.length, evidence_page: evidencePage.status, current_actuals_unavailable: unavailableActuals.status, report: relative(reportPath) }));
