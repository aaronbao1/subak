import test from 'node:test';
import assert from 'node:assert/strict';
import { tsModuleUrl } from '../../../tests/load-ts-module.mjs';
const { createSnapshotDataClient, readDemoSnapshot } = await import(tsModuleUrl(new URL('./demo-snapshot.ts', import.meta.url)));
const { MockDataClient } = await import(tsModuleUrl(new URL('./mock-client.ts', import.meta.url)));
const { northstar } = await import(tsModuleUrl(new URL('../../fixtures/index.ts', import.meta.url)));
const { syntheticForecastBundle } = await import(tsModuleUrl(new URL('./mock-forecast.ts', import.meta.url)));
const { syntheticWeeklyHistory } = await import(tsModuleUrl(new URL('./mock-weekly-history.ts', import.meta.url)));
const query = { scopeType: 'company', scopeId: 'northstar', startDate: '2026-09-21', endDateExclusive: '2026-11-16' };

async function fixture() {
  const client = new MockDataClient();
  const bundle = syntheticForecastBundle(northstar, 'saved-run-7');
  for (const view of bundle.views) view.dataset_id = 'forecast-targets:northstar';
  bundle.publication = { run_id: 'saved-run-7' };
  return { dataset: northstar, bundle, weeklyHistory: [syntheticWeeklyHistory(northstar, query, bundle)], evidence: { items: [] }, requests: [], allocationState: await client.getAllocationState(), asOf: '2026-10-25T12:00:00Z' };
}

test('one lazy session load supports concurrent reads and retries a failed download without a fallback dataset', async () => {
  const snapshot = await fixture();
  let loads = 0;
  const client = createSnapshotDataClient(async () => { loads++; if (loads === 1) throw new Error('snapshot unavailable'); return snapshot; });
  await assert.rejects(client.getCompany(), /snapshot unavailable/);
  const [company, teams, people] = await Promise.all([client.getCompany(), client.getTeams(), client.getPeople()]);
  assert.equal(loads, 2); assert.equal(company.id, snapshot.dataset.company.id);
  assert.equal(teams.length, snapshot.dataset.teams.length); assert.equal(people.length, snapshot.dataset.people.length);
  assert.equal(client.then, undefined);
});

test('saved forecasts and historical receipts remain unchanged after refresh and session-local allocation approval', async () => {
  const snapshot = await fixture();
  const first = createSnapshotDataClient(async () => snapshot), other = createSnapshotDataClient(async () => snapshot);
  const before = await first.getForecastViews();
  assert.deepEqual(before, snapshot.bundle);
  const history = await first.getWeeklyForecastHistory(query);
  const refreshed = await first.refreshForecast('refresh-1');
  assert.equal(refreshed.run_id, 'saved-run-7');
  assert.deepEqual(await first.getForecastViews(), before); assert.deepEqual(await first.getWeeklyForecastHistory(query), history);
  const state = await first.getAllocationState();
  const targets = Object.fromEntries(state.allocations.map(item => [item.teamId, item.amount]));
  targets.research = (Number(targets.research) + 123.45).toFixed(2);
  const receipt = await first.prepareAllocationProposal({ baseVersion: state.stateVersion, periodStart: state.period.startDate, periodEndExclusive: state.period.endDateExclusive, unit: 'USD', allocations: targets, rationale: 'Session-only demonstration' }, 'local-change');
  await first.applyProposal(receipt.proposalId);
  assert.equal(Number((await first.getAllocationState()).envelopeTotal), Number(state.envelopeTotal) + 123.45);
  assert.equal((await first.getBudgets()).find(item => item.teamId === 'research').allocated, 60123.45);
  assert.equal((await other.getBudgets()).find(item => item.teamId === 'research').allocated, 60000);
  assert.equal(snapshot.dataset.budgets.find(item => item.teamId === 'research').allocated, 60000);
  assert.deepEqual(await first.getForecastViews(), before);
});

test('saved forecast caller mutations cannot change the next read and scenarios never claim recalculated amounts', async () => {
  const snapshot = await fixture(), client = createSnapshotDataClient(async () => snapshot);
  const before = await client.getForecastViews();
  const modified = await client.getForecastViews(); modified.views[0].weekly[0].base = 999;
  assert.deepEqual(await client.getForecastViews(), before);
  const scenario = await client.previewForecastScenario('saved-run-7', []);
  assert.equal(scenario.recalculation_required, true);
  assert.deepEqual(scenario.views.map(view => view.weekly), before.views.map(view => view.weekly));
  await assert.rejects(client.getForecastExplanation('unavailable-run'), /unavailable/);
  const explanation = await client.getForecastExplanation('saved-run-7');
  explanation.publication.run_id = 'mutated';
  assert.equal((await client.getForecastExplanation('saved-run-7')).publication.run_id, 'saved-run-7');
});

test('snapshot download failures and invalid public paths are explicit instead of silently showing another company', async () => {
  let fetched = 0;
  await assert.rejects(readDemoSnapshot('https://external.invalid/demo', async () => { fetched++; return new Response('{}'); }), /path/);
  assert.equal(fetched, 0);
  await assert.rejects(readDemoSnapshot('/demo', async () => new Response('{}', { status: 404 })), /saved demo could not load/);
});
