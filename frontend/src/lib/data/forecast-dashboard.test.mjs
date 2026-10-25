import test from 'node:test';
import assert from 'node:assert/strict';
import { tsModuleUrl } from '../../../tests/load-ts-module.mjs';

const { hydrateForecastDashboard } = await import(tsModuleUrl(new URL('./forecast-dashboard.ts', import.meta.url)));

function wire() {
  return {
    transport: 'forecast-dashboard-v1',
    driver_pool: {
      d0: { id: 'same-id', parameters: { z: '0.00000000001', a: null }, citations: [{ quote: 'Original source text', span: [0, 20] }] },
      d1: { id: 'same-id', parameters: { z: '8.500000001', a: false }, citations: [{ quote: 'Revised source text' }] },
    },
    publication: { run_id: 'issued / 7', sequence: 0 },
    current_actuals: { status: 'partial', revision: 'truth-2', reason: 'Missing source', as_of: '2026-10-25' },
    views: [{
      run_id: 'issued / 7', scope: { type: 'company', id: 'tenant' },
      target: { unit: 'USD', quantity: 'spend', basis: 'planning', timezone: 'UTC' },
      daily: [{ date: '2026-10-25', base: 0, low: null, high: '125.0000000001', complete: false, partial: true }],
      weekly: [], cumulative: [], scenario_range: { complete: false }, limitations: ['Unsettled source'],
      included_driver_refs: ['d1', 'd0', 'd1'], queued_change_refs: ['d0'],
      future_metadata: { preserved: ['all', 'values'] },
    }, {
      run_id: 'issued / 7', scope: { type: 'team', id: 'research' },
      included_driver_refs: ['d0'], queued_change_refs: [],
    }],
  };
}

test('compact hydration restores complete ordered drivers and preserves every other field and precision', () => {
  const input = wire();
  const result = hydrateForecastDashboard(input);
  const { driver_pool, ...expected } = structuredClone(input);
  delete expected.transport;
  expected.views = expected.views.map(({ included_driver_refs, queued_change_refs, ...view }) => ({
    ...view,
    included_drivers: included_driver_refs.map(ref => driver_pool[ref]),
    queued_changes: queued_change_refs.map(ref => driver_pool[ref]),
  }));
  assert.deepEqual(result, expected);
  assert.deepEqual(Object.keys(result.views[0].included_drivers[1].parameters), ['z', 'a']);
  assert.deepEqual(input, wire());
});

test('each driver occurrence is isolated from the pool, duplicate references, other lists, and other views', () => {
  const input = wire();
  const result = hydrateForecastDashboard(input);
  result.views[0].included_drivers[1].citations[0].span[0] = 99;
  result.views[0].included_drivers[0].parameters.z = 'edited';
  assert.equal(input.driver_pool.d0.citations[0].span[0], 0);
  assert.equal(result.views[0].queued_changes[0].citations[0].span[0], 0);
  assert.equal(result.views[1].included_drivers[0].citations[0].span[0], 0);
  assert.equal(result.views[0].included_drivers[2].parameters.z, '8.500000001');
});

test('missing, null, and empty driver arrays retain distinct original representations', () => {
  const input = { transport: 'forecast-dashboard-v1', driver_pool: {}, views: [
    { id: 'absent' },
    { id: 'null', included_driver_refs: null, queued_change_refs: null },
    { id: 'empty', included_driver_refs: [], queued_change_refs: [] },
  ] };
  assert.deepEqual(hydrateForecastDashboard(input), { views: [
    { id: 'absent' }, { id: 'null', included_drivers: null, queued_changes: null },
    { id: 'empty', included_drivers: [], queued_changes: [] },
  ] });
});

test('legacy bundles are returned unchanged, including native audit fields', () => {
  const legacy = { views: [], calculations: { detailed: true }, current_actuals: { observations: [1] } };
  assert.equal(hydrateForecastDashboard(legacy), legacy);
});

test('invalid compact envelopes and missing or malformed references fail closed', () => {
  for (const input of [
    null, [],
    { ...wire(), transport: 'forecast-dashboard-v2' },
    { ...wire(), driver_pool: null },
    { ...wire(), views: null },
    { ...wire(), views: [null] },
    { ...wire(), views: [{ included_driver_refs: 'd0' }] },
    { ...wire(), views: [{ included_driver_refs: [null] }] },
    { ...wire(), views: [{ included_driver_refs: ['missing'] }] },
    { ...wire(), views: [{ included_driver_refs: ['__proto__'] }] },
    { ...wire(), driver_pool: { d0: null } },
    { ...wire(), driver_pool: { d0: { parameters: {} }, d1: { id: 'same-id' } } },
    { ...wire(), views: [{ included_drivers: [], included_driver_refs: ['d0'] }] },
  ]) assert.throws(() => hydrateForecastDashboard(input), /forecast|driver|transport/i);
});
