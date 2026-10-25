/** Real TypeScript client/store -> FastAPI -> SQLite/worker/engine -> Droid.
 * Run: FORECAST_TEST_PYTHON=.venv/bin/python node --test frontend/tests/forecast-backend.integration.mjs
 * Only fetch's network transport is replaced with a TestClient IPC bridge.
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawn } from 'node:child_process';
import { createInterface } from 'node:readline';
import { stripTypeScriptTypes } from 'node:module';

const root = fileURLToPath(new URL('../../', import.meta.url));
const dataUrl = source => `data:text/javascript;base64,${Buffer.from(source).toString('base64')}`;
const sourceAt = relative => stripTypeScriptTypes(fs.readFileSync(path.join(root, relative), 'utf8'), { mode: 'transform' });
const moduleAt = relative => dataUrl(sourceAt(relative));
const { HttpDataClient } = await import(moduleAt('frontend/src/lib/data/http-client.ts'));
const { scopeView, omissionDrivers, companyQuarterProjection } = await import(moduleAt('frontend/src/components/dashboard/forecast-derive.ts'));
const { completeScenario } = await import(moduleAt('frontend/src/lib/data/scenario-job.ts'));

function bridge() {
  const python = process.env.FORECAST_TEST_PYTHON ?? path.join(root, '.venv/bin/python');
  const child = spawn(python, ['backend/tests/forecast_frontend_bridge.py'], {
    cwd: root, env: { ...process.env, PYTHONPATH: ['src', 'backend', 'agent', process.env.PYTHONPATH].filter(Boolean).join(path.delimiter) },
    stdio: ['pipe', 'pipe', 'pipe'],
  });
  let sequence = 0, stderr = '';
  const pending = new Map();
  const fail = error => { for (const request of pending.values()) request.reject(error); pending.clear(); };
  child.stderr.on('data', chunk => { stderr = (stderr + chunk).slice(-12000); });
  child.on('error', fail);
  child.on('exit', code => fail(new Error(`Backend bridge exited ${code}\n${stderr}`)));
  createInterface({ input: child.stdout }).on('line', line => {
    try {
      const message = JSON.parse(line), request = pending.get(message.id);
      if (!request) throw new Error(`Unexpected bridge reply ${line}`);
      pending.delete(message.id);
      if (message.error) request.reject(new Error(message.error)); else request.resolve(message.result);
    } catch (error) { fail(error); }
  });
  return {
    call(operation, args = {}) {
      const id = ++sequence;
      return new Promise((resolve, reject) => {
        pending.set(id, { resolve, reject });
        child.stdin.write(`${JSON.stringify({ id, operation, ...args })}\n`);
      });
    },
    async close() {
      child.stdin.end();
      if (child.exitCode === null) await new Promise(resolve => child.once('exit', resolve));
    },
  };
}

async function actualStore(client) {
  globalThis.__forecastIntegrationClient = client;
  let source = sourceAt('frontend/src/lib/store.ts');
  source = source.replace('from "zustand"', `from ${JSON.stringify(import.meta.resolve('zustand'))}`)
    .replace('from "@/components/dashboard/forecast-derive"', `from ${JSON.stringify(moduleAt('frontend/src/components/dashboard/forecast-derive.ts'))}`)
    .replace('from "@/lib/data/thread-merge"', `from ${JSON.stringify(moduleAt('frontend/src/lib/data/thread-merge.ts'))}`)
    .replace('import { getDataClient } from "@/lib/data";', 'const getDataClient = () => globalThis.__forecastIntegrationClient;');
  return (await import(dataUrl(source))).useAppStore;
}

test('frontend publication, evidence, Droid, scenario and current-actuals journey uses the real backend', { timeout: 180000 }, async t => {
  const transport = bridge(), originalFetch = globalThis.fetch;
  const calls = [];
  let workOnPoll = false;
  globalThis.fetch = async (url, init = {}) => {
    const parsed = new URL(url);
    assert.equal(parsed.origin, 'http://forecast.test');
    calls.push(`${init.method ?? 'GET'} ${parsed.pathname}`);
    if (workOnPoll && parsed.pathname.startsWith('/compat/api/forecast-refreshes/')) {
      await transport.call('work', { job_id: decodeURIComponent(parsed.pathname.split('/').at(-1)) });
    }
    const response = await transport.call('request', { path: parsed.pathname + parsed.search,
      method: init.method ?? 'GET', headers: init.headers, body: init.body });
    return new Response(response.body, { status: response.status, headers: response.headers });
  };
  t.after(async () => { globalThis.fetch = originalFetch; delete globalThis.__forecastIntegrationClient; await transport.close(); });
  const client = new HttpDataClient('http://forecast.test/compat');
  const store = await actualStore(client);
  const initialJob = await client.refreshForecast('frontend-initial');
  assert.equal((await client.refreshForecast('frontend-initial')).id, initialJob.id);
  assert.equal(await transport.call('work', { job_id: initialJob.id }), true);
  await store.getState().load();
  assert.equal(store.getState().loaded, true);
  assert.equal(store.getState().forecastError, undefined);
  const initial = store.getState().forecastBundle;
  assert.equal(initial.publication.run_id, initialJob.run_id);
  const company = scopeView(initial, 'company');
  assert.equal(company.daily.length, 7);
  assert.equal(company.weekly.length, 4);
  assert.equal(companyQuarterProjection(initial), company.quarter_outlook.base);
  // Dashboard selection and the native directory used by Droid must resolve
  // the same IDs, rather than exposing disjoint fixture and seeded people.
  const nativePeopleResponse = await fetch('http://forecast.test/api/people');
  assert.equal(nativePeopleResponse.status, 200);
  const nativePeople = await nativePeopleResponse.json();
  assert.deepEqual(nativePeople.map(person => person.id).sort(), store.getState().people.map(person => person.id).sort());
  for (const person of store.getState().people) {
    assert.equal((await fetch(`http://forecast.test/api/people/${encodeURIComponent(person.id)}`)).status, 200);
  }
  assert.ok(store.getState().forecasts.every(forecast => forecast.daily?.length === 7));
  for (const type of ['team', 'person']) {
    const views = initial.views.filter(view => view.scope.type === type);
    assert.ok(views.length);
    for (const view of views) {
      const filtered = await client.getForecastViews({ scope_type: type, scope_id: view.scope.id, run_id: initialJob.run_id });
      assert.equal(filtered.views.length, 1);
      assert.equal(filtered.views[0].id, view.id);
    }
  }
  const recordedViews = JSON.stringify(initial.views);
  const events = await transport.call('events');
  for (const envelope of events) {
    const response = await fetch('http://forecast.test/compat/api/forecast-evidence', {
      method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(envelope),
    });
    assert.equal(response.status, 201, await response.text());
  }
  await store.getState().loadForecastViews();
  assert.equal(JSON.stringify(store.getState().forecastBundle.views), recordedViews);
  assert.equal(store.getState().forecastBundle.current_actuals.revision, initial.current_actuals.revision);
  assert.ok(store.getState().forecastEvidence.some(item => item.drivers.some(driver => driver.queue_status === 'queued')));
  workOnPoll = true;
  await store.getState().refreshForecast();
  assert.equal(store.getState().forecastRefresh.status, 'succeeded');
  assert.equal(store.getState().forecastError, undefined);
  const issued = store.getState().forecastBundle, current = scopeView(issued, 'company');
  const runId = issued.publication.run_id;
  assert.notEqual(runId, initialJob.run_id);
  assert.notEqual(current.quarter_outlook.base, company.quarter_outlook.base);
  const driver = current.included_drivers.find(item => item.kind === 'project_schedule');
  assert.ok(driver);
  store.getState().askForecastAssistant('Why did this forecast change?', {
    action: 'explain', run_id: runId, scope_type: 'company', scope_id: current.scope.id, driver_id: driver.id,
  });
  const messages = await store.getState().sendMessage('main', store.getState().composer);
  const answer = messages.at(-1);
  assert.ok(answer.content.includes(runId));
  assert.ok(answer.content.includes(driver.id));
  assert.ok(answer.content.includes(driver.citations[0].quote));
  assert.ok(answer.toolCalls.some(tool => tool.name === 'explain_forecast'));
  const explanation = await client.getForecastExplanation(runId);
  assert.ok(explanation.calculations.some(calculation => calculation.driver_id === driver.id && answer.content.includes(String(calculation.base_delta))));
  const scenario = await completeScenario(await client.previewForecastScenario(runId, omissionDrivers(issued, current, driver.id)), runId, client, () => {}, { delay: async () => {} });
  assert.equal(scenario.parent_run_id, runId);
  assert.notEqual(scopeView(scenario, 'company').quarter_outlook.base, current.quarter_outlook.base);
  assert.equal((await client.getForecastViews()).publication.run_id, runId);
  assert.equal(JSON.stringify((await client.getForecastViews({ run_id: initialJob.run_id })).views), recordedViews);
  await transport.call('advance', { days: 7 });
  const later = await client.getForecastViews({ run_id: runId });
  assert.deepEqual(later.views, issued.views);
  assert.notEqual(later.current_actuals.revision, issued.current_actuals.revision);
  assert.notEqual(later.current_actuals.history_complete_through, issued.current_actuals.history_complete_through);
  await assert.rejects(client.getForecastExplanation('missing-run'), /404/);
  assert.ok(calls.includes('GET /compat/api/people'));
  assert.ok(calls.includes('POST /compat/api/threads/main/messages'));
});
