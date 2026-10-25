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
const httpSource = sourceAt('frontend/src/lib/data/http-client.ts')
  .replace('from "./forecast-dashboard"', `from ${JSON.stringify(moduleAt('frontend/src/lib/data/forecast-dashboard.ts'))}`)
  .replace('from "./weekly-history"', `from ${JSON.stringify(moduleAt('frontend/src/lib/data/weekly-history.ts'))}`)
  .replace('from "./budget-requests"', `from ${JSON.stringify(moduleAt('frontend/src/lib/data/budget-requests.ts'))}`);
const { HttpDataClient } = await import(dataUrl(httpSource));
const { scopeView, omissionDrivers, companyQuarterProjection } = await import(moduleAt('frontend/src/components/dashboard/forecast-derive.ts'));
const { completeScenario } = await import(moduleAt('frontend/src/lib/data/scenario-job.ts'));
const { fetchDailyUsage } = await import(moduleAt('frontend/src/lib/data/usage-client.ts'));
const { createScenarioDraft, buildScenarioDrivers, resolvePlanningDate, scenarioComparison } = await import(moduleAt('frontend/src/lib/planning-drafts.ts'));
const { prepareAllocationRequest, checkPreparedAllocation } = await import(moduleAt('frontend/src/lib/allocation-workbench.ts'));
const { prepareAllocationTargets, checkAllocationTargets } = await import(moduleAt('frontend/src/lib/allocation-targets.ts'));

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
    .replace('from "@/lib/planning-drafts"', `from ${JSON.stringify(moduleAt('frontend/src/lib/planning-drafts.ts'))}`)
    .replace('import { getDataClient } from "@/lib/data";', 'const getDataClient = () => globalThis.__forecastIntegrationClient;');
  return (await import(dataUrl(source))).useAppStore;
}

test('frontend publication, evidence, Droid, scenario and current-actuals journey uses the real backend', { timeout: 180000 }, async t => {
  const transport = bridge(), originalFetch = globalThis.fetch;
  const calls = [];
  let workOnPoll = false;
  let failBudgetReads = 0;
  let dropApplyResponse = false;
  let dropMessageResponse = false;
  let dropDraftResponse = false;
  globalThis.fetch = async (url, init = {}) => {
    const parsed = new URL(url);
    assert.equal(parsed.origin, 'http://forecast.test');
    calls.push(`${init.method ?? 'GET'} ${parsed.pathname}`);
    if (parsed.pathname === '/compat/api/budgets' && failBudgetReads > 0) {
      failBudgetReads--;
      return new Response('Injected refresh transport failure', { status: 503 });
    }
    if (workOnPoll && parsed.pathname.startsWith('/compat/api/forecast-refreshes/')) {
      await transport.call('work', { job_id: decodeURIComponent(parsed.pathname.split('/').at(-1)) });
    }
    const response = await transport.call('request', { path: parsed.pathname + parsed.search,
      method: init.method ?? 'GET', headers: init.headers, body: init.body });
    if (dropApplyResponse && parsed.pathname.endsWith('/apply')) {
      dropApplyResponse = false;
      throw new TypeError('Injected connection loss after the apply committed');
    }
    if (dropMessageResponse && init.method === 'POST' && parsed.pathname.endsWith('/messages')) {
      dropMessageResponse = false;
      throw new TypeError('Injected connection loss after the message committed');
    }
    if (dropDraftResponse && init.method === 'POST' && (parsed.pathname.endsWith('/allocation-drafts') || parsed.pathname.endsWith('/draft'))) {
      dropDraftResponse = false;
      throw new TypeError('Injected connection loss after the allocation draft committed');
    }
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

  // The actual editing adapter submits a full same-run driver set to the engine.
  const issuedBeforeEditing = JSON.stringify(issued.views);
  let editedDraft = { ...createScenarioDraft(current, driver), proposedStart: resolvePlanningDate('one week later', String(driver.parameters.to_start)) };
  const editedDrivers = buildScenarioDrivers(issued, editedDraft);
  assert.deepEqual(editedDrivers.filter(item => item.id !== driver.id), current.included_drivers.filter(item => item.id !== driver.id));
  const editedScenario = await completeScenario(await client.previewForecastScenario(runId, editedDrivers), runId, client, () => {}, { delay: async () => {} });
  assert.equal(scenarioComparison(current, editedScenario).available, true);
  editedDraft = { ...editedDraft, proposedStart: resolvePlanningDate('one week later', editedDraft.proposedStart), revision: 2 };
  const revisedScenario = await completeScenario(await client.previewForecastScenario(runId, buildScenarioDrivers(issued, editedDraft)), runId, client, () => {}, { delay: async () => {} });
  assert.equal(revisedScenario.parent_run_id, runId);
  assert.notEqual(revisedScenario.scenario_id, editedScenario.scenario_id);
  assert.equal(JSON.stringify(issued.views), issuedBeforeEditing);
  assert.equal((await client.getForecastViews()).publication.run_id, runId);

  // Natural-language edits keep the selected issued driver and revise its card.
  store.getState().setAssistantIntent('scenario');
  const datedReply = (await store.getState().sendMessage('main', 'Move the project start to November 10, 2026.')).at(-1);
  assert.equal(datedReply.actionDraft?.kind, 'scenario', datedReply.content);
  assert.equal(datedReply.actionDraft.parentRunId, runId);
  assert.equal(datedReply.actionDraft.driverId, driver.id);
  assert.equal(datedReply.actionDraft.proposedStart, '2026-11-10');
  const dateRevision = (await store.getState().sendMessage('main', 'Make it one week later.')).at(-1);
  assert.equal(dateRevision.actionDraft?.id, datedReply.actionDraft.id);
  assert.equal(dateRevision.actionDraft.proposedStart, '2026-11-17');
  assert.equal(dateRevision.actionDraft.revision, datedReply.actionDraft.revision + 1);
  const conversationScenario = await completeScenario(await client.previewForecastScenario(runId, buildScenarioDrivers(issued, dateRevision.actionDraft)), runId, client, () => {}, { delay: async () => {} });
  assert.equal(conversationScenario.parent_run_id, runId);
  assert.equal((await client.getForecastViews()).publication.run_id, runId);

  // Selected-draft revision does not require copying a raw proposal identity.
  store.getState().clearAssistantContext();
  store.getState().setAssistantIntent('allocation');
  const baselineBudget = store.getState().budgets.reduce((total, budget) => total + budget.allocated, 0);
  const additionRequest = prepareAllocationRequest({ mode: 'addition', targetTeamId: 'research', amount: '50.00', unit: 'usd', period: store.getState().company.currentPeriod }, store.getState());
  const allocation = (await store.getState().sendMessage('main', additionRequest.content)).at(-1);
  assert.ok(allocation.proposalId, allocation.content);
  const addedProposal = await client.getProposal(allocation.proposalId);
  assert.equal(addedProposal.addedAmount, 50);
  assert.equal(checkPreparedAllocation(additionRequest, addedProposal).matches, true);
  store.getState().reviseProposal(allocation.proposalId);
  const revision = (await store.getState().sendMessage('main', 'Make it $40 instead.')).at(-1);
  assert.ok(revision.proposalId, revision.content);
  const revisedProposal = await client.getProposal(revision.proposalId);
  assert.equal(revisedProposal.revisesProposalId, allocation.proposalId);
  assert.equal(revisedProposal.addedAmount, 40);
  assert.equal((await client.getProposal(allocation.proposalId)).status, 'revised');
  await assert.rejects(client.applyProposal(allocation.proposalId), error => error.status === 409);

  // A persisted receipt survives a failed summary refresh; refresh retries never reapply.
  failBudgetReads = 1;
  const receipt = await store.getState().applyProposal(revisedProposal.id, 'Deterministic integration approval');
  assert.equal(receipt.action, 'applied');
  assert.equal(store.getState().proposalActions[revisedProposal.id].mutation, 'confirmed');
  assert.equal(store.getState().proposalActions[revisedProposal.id].sync, 'failed');
  assert.equal(store.getState().budgetSync, 'stale');
  assert.equal((await store.getState().applyProposal(revisedProposal.id)).id, receipt.id);
  assert.equal(await store.getState().refreshBudgets(), true);
  assert.equal(store.getState().proposalActions[revisedProposal.id].sync, 'synced');
  assert.equal(store.getState().budgets.reduce((total, budget) => total + budget.allocated, 0), baselineBudget + 40);
  assert.equal(calls.filter(call => call === `POST /compat/api/proposals/${revisedProposal.id}/apply`).length, 1);

  // Lost mutation responses reconcile persisted receipts before any repeat approval.
  store.getState().clearAssistantContext();
  const nextAllocation = (await store.getState().sendMessage('main', 'Add $25 prioritizing research.')).at(-1);
  assert.ok(nextAllocation.proposalId, nextAllocation.content);
  dropApplyResponse = true;
  const recoveredReceipt = await store.getState().applyProposal(nextAllocation.proposalId);
  assert.equal(recoveredReceipt.action, 'applied');
  assert.equal(store.getState().proposalActions[nextAllocation.proposalId].mutation, 'confirmed');
  assert.equal(calls.filter(call => call === `POST /compat/api/proposals/${nextAllocation.proposalId}/apply`).length, 1);

  // A lost chat response is resolved by its stable message receipt, not replayed.
  store.getState().clearAssistantContext();
  dropMessageResponse = true;
  await assert.rejects(store.getState().sendMessage('main', 'Why did you add funding?'), /connection loss/);
  const pending = store.getState().threads.main.find(message => message.delivery === 'unknown');
  assert.ok(pending?.clientMessageId);
  const proposalCount = (await client.getProposals()).length;
  await store.getState().reconcileMessage('main', pending.clientMessageId);
  assert.equal(store.getState().threads.main.some(message => message.id === pending.id), false);
  assert.equal((await client.getProposals()).length, proposalCount);
  assert.equal((await client.reconcileMessage('main', pending.clientMessageId)).status, 'completed');

  // The guided allocation form submits exact named teams and returns a reviewable draft.
  const transferRequest = prepareAllocationRequest({ mode: 'transfer', sourceTeamId: 'product', targetTeamId: 'research', amount: '50.25', unit: 'usd', period: store.getState().company.currentPeriod }, store.getState());
  const beforeTransfer = JSON.stringify(await client.getBudgets());
  store.getState().clearAssistantContext();
  const transferReply = (await store.getState().sendMessage('main', transferRequest.content)).at(-1);
  assert.ok(transferReply.proposalId, transferReply.content);
  const transferProposal = await client.getProposal(transferReply.proposalId);
  assert.equal(transferProposal.status, 'proposed');
  assert.equal(checkPreparedAllocation(transferRequest, transferProposal).matches, true);
  assert.equal(transferProposal.totalBefore, transferProposal.totalAfter);
  assert.equal(JSON.stringify(await client.getBudgets()), beforeTransfer);

  // Durable team intake automatically reads financial context without changing it.
  const curvesBeforeRequests = JSON.stringify((await client.getForecastViews()).views);
  const allocationStateBefore = await client.getAllocationState();
  const decisionsBeforeRequests = await client.getDecisions();
  const requestInput = { clientRequestId: 'integration-research-expansion', teamId: 'research', title: 'Additional evaluation capacity',
    requestKind: 'project', projectName: 'Atlas', narrative: 'Synthetic team request for $75 of additional Q4 allocation, subject to finance review.',
    requestedAmount: '75.00', unit: 'USD', periodStart: '2026-10-01', periodEndExclusive: '2027-01-01', sourceRef: 'Synthetic integration intake' };
  const budgetRequest = await client.ingestTeamUpdate(requestInput);
  assert.equal((await client.ingestTeamUpdate(requestInput)).id, budgetRequest.id);
  assert.equal(budgetRequest.status, 'submitted');
  assert.equal(budgetRequest.requestedAmount, '75.00');
  assert.equal(budgetRequest.assessment.amountIncludedInForecast, false);
  assert.equal(budgetRequest.assessment.forecastRunId, runId);
  assert.equal(budgetRequest.assessment.budgetVersion, allocationStateBefore.stateVersion);
  assert.equal(budgetRequest.source.reference, requestInput.sourceRef);
  const projectUpdate = await client.ingestTeamUpdate({ ...requestInput, clientRequestId: 'integration-engineering-timing', teamId: 'engineering',
    title: 'Migration timing update', requestedAmount: null, narrative: 'Synthetic project timing update. No additional funding amount supplied.' });
  assert.equal(projectUpdate.requestedAmount, null);
  assert.equal(projectUpdate.assessment.requestedAllocation, null);
  assert.equal(projectUpdate.remainingRequestedAmount, null);
  assert.deepEqual(await client.getAllocationState(), allocationStateBefore);
  assert.deepEqual(await client.getDecisions(), decisionsBeforeRequests);
  await assert.rejects(client.prepareBudgetRequestDraft(projectUpdate.id, { baseVersion: allocationStateBefore.stateVersion, actionType: 'addition' }, 'no-invented-request-amount'));

  // A complete edited team map can fund only part of a request, with recoverable submission.
  const targets = Object.fromEntries(allocationStateBefore.allocations.map(row => [row.teamId, row.amount]));
  targets.research = (Number(targets.research) + 50.25).toFixed(2);
  targets.product = (Number(targets.product) - 50.25).toFixed(2);
  const editedTargets = prepareAllocationTargets(targets, { budgets: await client.getBudgets(), teams: store.getState().teams,
    period: store.getState().company.currentPeriod, unit: 'usd' });
  const targetInput = { ...editedTargets.input, requestIds: [budgetRequest.id] };
  const targetOperation = 'integration-partial-request-targets';
  dropDraftResponse = true;
  await assert.rejects(client.prepareAllocationProposal(targetInput, targetOperation), /connection loss/);
  const recoveredDraft = await client.reconcileAllocationProposal(targetOperation);
  assert.ok(recoveredDraft?.proposalId);
  assert.equal((await client.prepareAllocationProposal(targetInput, targetOperation)).proposalId, recoveredDraft.proposalId);
  const targetProposal = await client.getProposal(recoveredDraft.proposalId);
  assert.equal(checkAllocationTargets(editedTargets, targetProposal).matches, true);
  assert.equal((await client.getBudgetRequest(budgetRequest.id)).status, 'pending_review');
  assert.deepEqual(await client.getAllocationState(), allocationStateBefore);
  const partialReceipt = await store.getState().applyProposal(recoveredDraft.proposalId, 'Partial synthetic request funding');
  const partiallyFunded = await client.getBudgetRequest(budgetRequest.id);
  assert.equal(partiallyFunded.status, 'partially_funded');
  assert.equal(Number(partiallyFunded.approvedAmount), 50.25);
  assert.equal(Number(partiallyFunded.remainingRequestedAmount), 24.75);
  assert.ok(partiallyFunded.decisionIds.includes(partialReceipt.id));
  const partiallyAllocated = await client.getAllocationState();
  assert.equal(partiallyAllocated.stateVersion, allocationStateBefore.stateVersion + 1);
  assert.equal(partiallyAllocated.envelopeTotal, allocationStateBefore.envelopeTotal);

  // Drafting the remaining request uses its current remaining amount and a new budget version.
  const remainderOperation = 'integration-request-remainder';
  const remainder = await client.prepareBudgetRequestDraft(budgetRequest.id, { baseVersion: partiallyAllocated.stateVersion,
    actionType: 'transfer', sourceTeamId: 'product' }, remainderOperation);
  assert.equal((await client.reconcileAllocationProposal(remainderOperation)).proposalId, remainder.proposalId);
  const nativeRemainderResponse = await fetch(`http://forecast.test/api/proposals/${encodeURIComponent(remainder.proposalId)}`);
  assert.equal(nativeRemainderResponse.status, 200);
  const nativeRemainder = await nativeRemainderResponse.json();
  assert.ok(nativeRemainder.evidence_refs.some(ref => ref.kind === 'budget_request' && ref.id === budgetRequest.id));
  assert.ok(nativeRemainder.evidence_refs.some(ref => ref.kind === 'forecast_snapshot'));
  const finalRequestReceipt = await store.getState().applyProposal(remainder.proposalId, 'Remaining synthetic request funding');
  assert.equal((await store.getState().applyProposal(remainder.proposalId)).id, finalRequestReceipt.id);
  const fullyFunded = await client.getBudgetRequest(budgetRequest.id);
  assert.equal(fullyFunded.status, 'approved_applied');
  assert.equal(Number(fullyFunded.approvedAmount), 75);
  assert.equal(Number(fullyFunded.remainingRequestedAmount), 0);
  assert.equal(new Set(fullyFunded.decisionIds).size, 2);
  assert.equal(fullyFunded.narrative, requestInput.narrative);
  assert.deepEqual(fullyFunded.source, budgetRequest.source);
  assert.equal((await client.getAllocationState()).stateVersion, allocationStateBefore.stateVersion + 2);
  assert.equal(JSON.stringify((await client.getForecastViews()).views), curvesBeforeRequests);

  // Native observed usage travels through the actual snake_case→TypeScript adapter.
  const query = { scopeType: 'company', startDate: '2026-10-01', endDateExclusive: '2026-10-28' };
  const beforeTokens = await fetchDailyUsage('http://forecast.test/compat', query);
  const moneyCents = value => value === null ? 0 : Math.round(Number(value) * 100);
  const usageCents = response => response.buckets.reduce((total, day) => total + moneyCents(day.recordedSpend), 0);
  const expectedCents = (await client.getSpending()).filter(row => row.date >= query.startDate && row.date < query.endDateExclusive).reduce((total, row) => total + Math.round(row.amount * 100), 0);
  assert.equal(usageCents(beforeTokens), expectedCents);
  const tokenImport = await transport.call('token_examples');
  assert.equal((await transport.call('token_examples')).status, 'duplicate');
  const usage = await fetchDailyUsage('http://forecast.test/compat', query);
  assert.notEqual(usage.datasetRevision, beforeTokens.datasetRevision);
  assert.equal(usage.synthetic, true);
  assert.equal(usageCents(usage), expectedCents);
  const tokenDay = usage.buckets.find(day => day.date === '2026-10-24');
  assert.deepEqual(tokenDay.tokens, { input: 300, output: 50, cachedInput: 230, reasoning: 25, total: 350 });
  assert.ok(tokenDay.sourceRefs.includes(tokenImport.id));
  assert.equal(tokenDay.coverage, 'partial');
  assert.equal(tokenDay.breakdowns.filter(row => row.model === 'example-model').length, 2);
  assert.equal(usage.buckets.find(day => day.date === '2026-10-25').tokens.total, 0);
  assert.equal(usage.buckets.find(day => day.date === '2026-10-26').recordedSpend, null);
  assert.equal(usage.buckets.find(day => day.date === '2026-10-26').coverage, 'missing');
  assert.equal(usage.buckets.find(day => day.date === '2026-10-27').coverage, 'future');
  const personUsage = await fetchDailyUsage('http://forecast.test/compat', { ...query, scopeType: 'person', scopeId: 'maya' });
  assert.equal(personUsage.buckets.find(day => day.date === '2026-10-24').tokens.total, 350);
  const teamUsage = await fetchDailyUsage('http://forecast.test/compat', { ...query, scopeType: 'team', scopeId: 'research' });
  assert.ok(usageCents(personUsage) > 0);
  assert.ok(usageCents(personUsage) < usageCents(teamUsage));
  const partitions = await Promise.all(store.getState().teams.filter(team => team.id !== 'unattributed').map(team => fetchDailyUsage('http://forecast.test/compat', { ...query, scopeType: 'team', scopeId: team.id })));
  const shared = await fetchDailyUsage('http://forecast.test/compat', { ...query, scopeType: 'shared' });
  assert.equal(partitions.reduce((total, part) => total + usageCents(part), 0) + usageCents(shared), usageCents(usage));
  for (const team of store.getState().teams.filter(team => team.id !== 'unattributed')) {
    const members = store.getState().people.filter(person => person.teamId === team.id);
    const people = await Promise.all(members.map(person => fetchDailyUsage('http://forecast.test/compat', { ...query, scopeType: 'person', scopeId: person.id })));
    const teamShared = await fetchDailyUsage('http://forecast.test/compat', { ...query, scopeType: 'shared', scopeId: team.id });
    const teamTotal = partitions.find(part => part.scope.id === team.id);
    assert.equal(people.reduce((total, part) => total + usageCents(part), 0) + usageCents(teamShared), usageCents(teamTotal));
  }
  const filtered = await fetchDailyUsage('http://forecast.test/compat', { ...query, provider: 'Synthetic provider A', model: 'example-model' });
  assert.equal(filtered.buckets.find(day => day.date === '2026-10-24').tokens.total, 120);
  assert.equal(usageCents(filtered), 0);
  assert.equal(JSON.stringify((await client.getForecastViews({ run_id: runId })).views), issuedBeforeEditing);

  // Weekly history keeps past actuals without inventing a retrospective forecast.
  const weeklyQuery = { scopeType: 'company', scopeId: 'northstar', startDate: '2026-10-19', endDateExclusive: '2026-11-23' };
  const weekly = await client.getWeeklyForecastHistory(weeklyQuery);
  assert.equal(weekly.weeks.length, 5);
  assert.equal(weekly.synthetic, true);
  assert.equal(weekly.weeks[0].priorForecast, null);
  assert.equal(weekly.weeks[0].actual.status, 'partial');
  assert.equal(weekly.weeks[0].variance.amount, null);
  const openWeek = weekly.weeks.find(week => week.start === '2026-10-26');
  assert.equal(openWeek.state, 'current');
  assert.equal(openWeek.outlook.runId, runId);
  assert.equal(openWeek.variance.status, 'unavailable');
  assert.ok(openWeek.priorForecast);
  assert.ok(weekly.weeks.filter(week => week.state === 'future').every(week => week.actual.amount === null && week.variance.amount === null));
  await transport.call('advance', { days: 7 });
  const unconfirmed = (await client.getWeeklyForecastHistory(weeklyQuery)).weeks.find(week => week.start === '2026-10-26');
  assert.equal(unconfirmed.state, 'closed');
  assert.equal(unconfirmed.actual.status, 'partial');
  assert.equal(unconfirmed.variance.amount, null);
  const mature = await transport.call('mature_company_week', { run_id: openWeek.priorForecast.runId });
  const settled = (await client.getWeeklyForecastHistory(weeklyQuery)).weeks.find(week => week.start === '2026-10-26');
  assert.equal(settled.actual.status, 'mature');
  assert.equal(settled.actual.source, 'observed_outcome');
  assert.equal(Number(settled.actual.amount), Number(mature.actual));
  const settledDaily = await fetchDailyUsage('http://forecast.test/compat', {
    scopeType: 'company', startDate: '2026-10-26', endDateExclusive: '2026-11-02',
  });
  assert.equal(Math.round(Number(settled.actual.amount) * 100), usageCents(settledDaily));
  assert.match(settled.actual.amount, /^\d+(?:\.\d{1,2})?$/);
  assert.equal(settled.priorForecast.targetId, mature.target_id);
  assert.equal(settled.variance.status, 'available');
  assert.ok(Math.abs(Number(settled.variance.amount) - (Number(mature.actual) - mature.prediction)) < 1e-10);
  assert.equal(settled.priorForecast.runId, openWeek.priorForecast.runId);
  const later = await client.getForecastViews({ run_id: runId });
  assert.deepEqual(later.views, issued.views);
  assert.notEqual(later.current_actuals.revision, issued.current_actuals.revision);
  assert.notEqual(later.current_actuals.history_complete_through, issued.current_actuals.history_complete_through);
  await assert.rejects(client.getForecastExplanation('missing-run'), /404/);
  assert.ok(calls.includes('GET /compat/api/people'));
  assert.ok(calls.includes('POST /compat/api/threads/main/messages'));
});
