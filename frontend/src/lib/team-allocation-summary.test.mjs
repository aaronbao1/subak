import test from 'node:test';
import assert from 'node:assert/strict';
import { tsModuleUrl } from '../../tests/load-ts-module.mjs';
const { selectTeamAllocationRows, selectTeamAllocationSummary } = await import(tsModuleUrl(new URL('./team-allocation-summary.ts', import.meta.url)));
const period = { start: '2026-10-19', end: '2026-10-25' };
const company = { id: 'company', currentPeriod: period, budgetUnit: 'usd' };
const team = (id) => ({ id, name: id, color: 'var(--brand)' });
const budget = (id, allocated, extra = {}) => ({ teamId: id, allocated, unit: 'usd', period, ...extra });
const view = (id, projected, extra = {}) => ({
  run_id: 'issued', scope: { type: 'team', id }, dataset_id: 'company',
  target: { unit: 'USD', basis: 'planning', timezone: 'UTC' },
  planning_period_outlook: { start: period.start, end: '2026-10-26', base: projected }, ...extra,
});
const select = (extra = {}) => selectTeamAllocationRows({ company, teams: [team('Research')], budgets: [budget('Research', 100)], spending: [], forecastBundle: { views: [view('Research', 125)] }, ...extra });

test('exact matching team target shows projection, allocation and signed expected gap', () => {
  const rows = select();
  assert.equal(rows.length, 1);
  assert.equal(rows[0].projected, 125);
  assert.equal(rows[0].allocation, 100);
  assert.equal(rows[0].gap, 25);
  assert.equal(rows[0].gapState, 'over');
  assert.equal(rows[0].team.id, 'Research');
});

test('quarter outlook and observed spend cannot substitute for the selected weekly projection', () => {
  const rows = select({
    spending: [{ teamId: 'Research', date: period.start, amount: 250, unit: 'usd', component: 'api', provenance: 'reported_charge', complete: true }],
    forecastBundle: { views: [view('Research', null, { planning_period_outlook: undefined, quarter_outlook: { start: '2026-10-01', end: '2027-01-01', base: 1000 } })] },
  });
  assert.equal(rows[0].projected, null);
  assert.equal(rows[0].allocation, 100);
  assert.equal(rows[0].gap, null);
  assert.equal(rows[0].gapState, 'unavailable');
});

test('forecast lookup uses exact team scope and rejects incompatible dataset, currency and basis', () => {
  assert.equal(select({ forecastBundle: { views: [view('Research', 999, { scope: { type: 'person', id: 'Research' } }), view('Research', 120)] } })[0].projected, 120);
  for (const extra of [{ dataset_id: 'other' }, { target: { unit: 'credits', basis: 'planning', timezone: 'UTC' } }, { target: { unit: 'USD', basis: 'other', timezone: 'UTC' } }]) {
    const row = select({ forecastBundle: { views: [view('Research', 999, extra)] } })[0];
    assert.equal(row.projected, null);
    assert.equal(row.gap, null);
  }
});

test('allocation requires exact team, period and currency without defaulting unknown to zero', () => {
  const row = select({ budgets: [budget('Product', 100), budget('Research', 100, { unit: 'credits' }), budget('Research', 100, { period: { start: '2026-10-01', end: '2026-12-31' } })] })[0];
  assert.equal(row.projected, 125);
  assert.equal(row.allocation, null);
  assert.equal(row.gap, null);
});

test('zero remains balanced, negative gap is headroom, and cents are retained', () => {
  const zero = select({ budgets: [budget('Research', 0)], forecastBundle: { views: [view('Research', 0)] } })[0];
  assert.equal(zero.projected, 0);
  assert.equal(zero.allocation, 0);
  assert.equal(zero.gap, 0);
  assert.equal(zero.gapState, 'balanced');
  const headroom = select({ budgets: [budget('Research', 100.25)], forecastBundle: { views: [view('Research', 100.1)] } })[0];
  assert.equal(headroom.gap, -0.15);
  assert.equal(headroom.gapState, 'headroom');
});

test('comparison prioritizes known overruns and material headroom while preserving all teams', () => {
  const cases = [['Unknown projection', null, 100], ['Balanced', 100, 100], ['Small headroom', 90, 100], ['Large headroom', 50, 100], ['Small over', 105, 100], ['Large over', 125, 100]];
  const teams = cases.map(([id]) => team(id));
  const rows = select({ teams, budgets: cases.map(([id, , amount]) => budget(id, amount)), forecastBundle: { views: cases.map(([id, projected]) => view(id, projected)) } });
  assert.deepEqual(rows.map(row => row.team.id), ['Large over', 'Small over', 'Large headroom', 'Small headroom', 'Balanced', 'Unknown projection']);
  assert.equal(teams[0].id, 'Unknown projection');
});

test('without company target no team inherits an arbitrary first budget period', () => {
  assert.deepEqual(select({ company: undefined }), []);
});

const overview = (extra = {}) => selectTeamAllocationSummary({ company, teams: [team('Research')], budgets: [budget('Research', 100)], spending: [], forecastBundle: { views: [view('Research', 125)] }, ...extra });

test('overall allocation uses every matching company budget, including amounts outside listed teams', () => {
  const result = overview({
    teams: [team('Research'), team('Product')],
    budgets: [budget('Research', 100), budget('Product', 50), budget('unlisted', 25), budget('old', 1000, { period: { start: '2026-10-01', end: '2026-12-31' } }), budget('credits', 1000, { unit: 'credits' })],
  });
  assert.equal(result.totalAllocation, 175);
  assert.equal(result.unlistedAllocation, 25);
  assert.equal(result.missingTeamCount, 0);
  assert.equal(result.rows.find(row => row.team.id === 'Research').allocationShare, 100 / 175);
  assert.equal(result.rows.find(row => row.team.id === 'Product').allocationShare, 50 / 175);
});

test('allocation denominator includes teams beyond the compact five-row table', () => {
  const teams = Array.from({ length: 7 }, (_, index) => team(`Team ${index}`));
  const result = overview({ teams, budgets: teams.map(team => budget(team.id, 100)) });
  assert.equal(result.totalAllocation, 700);
  assert.equal(result.unlistedAllocation, 0);
  assert.equal(result.rows.length, 7);
  assert.ok(result.rows.every(row => row.allocationShare === 1 / 7));
});

test('unknown team allocations remain missing and cannot acquire a share of the known total', () => {
  const result = overview({ teams: [team('Research'), team('Missing')] });
  assert.equal(result.totalAllocation, 100);
  assert.equal(result.missingTeamCount, 1);
  const missing = result.rows.find(row => row.team.id === 'Missing');
  assert.equal(missing.allocation, null);
  assert.equal(missing.allocationShare, null);
  assert.equal(result.unlistedAllocation, 0);
});

test('missing budget and known zero envelope stay distinct without invented allocation percentages', () => {
  const missing = overview({ budgets: [] });
  assert.equal(missing.totalAllocation, null);
  assert.equal(missing.unlistedAllocation, null);
  assert.equal(missing.rows[0].allocationShare, null);
  const zero = overview({ budgets: [budget('Research', 0)] });
  assert.equal(zero.totalAllocation, 0);
  assert.equal(zero.unlistedAllocation, 0);
  assert.equal(zero.rows[0].allocation, 0);
  assert.equal(zero.rows[0].allocationShare, null);
  assert.equal(overview({ company: undefined }).totalAllocation, null);
});

test('overall allocation arithmetic preserves cents independently from projected spend', () => {
  const result = overview({ teams: [team('Research'), team('Product')], budgets: [budget('Research', 0.1), budget('Product', 0.2)] });
  assert.equal(result.totalAllocation, 0.3);
  assert.equal(result.unlistedAllocation, 0);
  assert.equal(result.rows.find(row => row.team.id === 'Research').projected, 125);
});

test('Adjust is available only for a real team with a finite matching allocation, including known zero', () => {
  assert.equal(select()[0].canAdjust, true);
  assert.equal(select({ budgets: [budget('Research', 0)] })[0].canAdjust, true);
  for (const budgets of [[], [budget('Research', 100, { unit: 'credits' })], [budget('Research', 100, { period: { start: '2026-10-01', end: '2026-12-31' } })], [budget('Research', NaN)]]) {
    assert.equal(select({ budgets })[0].canAdjust, false);
  }
});

test('shared and unattributed sentinels remain outside editable team allocation rows', () => {
  for (const id of ['unattributed', 'shared', 'unknown', 'unassigned', 'people_unallocated', 'teams_unallocated', '']) {
    const result = overview({ teams: [team('Research'), team(id)], budgets: [budget('Research', 100)] });
    assert.deepEqual(result.rows.map(row => row.team.id), ['Research']);
    assert.equal(result.hasSharedScope, true);
    assert.equal(result.missingTeamCount, 0);
    assert.equal(result.totalAllocation, 100);
  }
  assert.equal(overview().hasSharedScope, false);
});

const nativeState = (extra = {}) => ({
  period: { id: 'week', label: 'Week', startDate: period.start, endDateExclusive: '2026-10-26' },
  unit: 'USD', stateVersion: 4, envelopeTotal: '125.123456', allocatedTotal: '100.00', unallocatedAmount: '25.123456',
  allocations: [], updatedAt: '2026-10-25T12:00:00Z', lastDecisionId: null, ...extra,
});

test('ready matching native state supplies exact overall budget and unallocated amount without recomputing either', () => {
  const result = overview({ allocationState: nativeState(), allocationStateStatus: 'ready' });
  assert.equal(result.overallBudget, '125.123456');
  assert.equal(result.unallocatedAmount, '25.123456');
  assert.equal(result.nativeAllocatedTotal, '100.00');
  assert.equal(result.totalAllocation, 100);
  assert.equal(result.rows[0].allocationShare, 1);
});

test('stale, loading, absent and wrong-target native state cannot label a row sum as overall budget', () => {
  for (const status of ['idle', 'loading', 'stale', 'error', undefined]) {
    const result = overview({ allocationState: nativeState(), allocationStateStatus: status });
    assert.equal(result.overallBudget, null);
    assert.equal(result.unallocatedAmount, null);
    assert.equal(result.totalAllocation, 100);
  }
  for (const state of [undefined, nativeState({ unit: 'credits' }), nativeState({ period: { startDate: '2026-10-01', endDateExclusive: '2027-01-01' } }), nativeState({ period: { startDate: period.start, endDateExclusive: period.end } })]) {
    assert.equal(overview({ allocationState: state, allocationStateStatus: 'ready' }).overallBudget, null);
  }
});

test('native zero envelope remains known and zero unallocated amount has no extra warning', () => {
  const result = overview({ allocationState: nativeState({ envelopeTotal: '0.00', allocatedTotal: '0.00', unallocatedAmount: '0.0000' }), allocationStateStatus: 'ready' });
  assert.equal(result.overallBudget, '0.00');
  assert.equal(result.nativeAllocatedTotal, '0.00');
  assert.equal(result.unallocatedAmount, null);
});

test('native matching period end is converted in UTC across a year boundary', () => {
  const crossYear = { ...company, currentPeriod: { start: '2026-12-28', end: '2027-01-03' } };
  const result = overview({ company: crossYear, allocationState: nativeState({ period: { startDate: '2026-12-28', endDateExclusive: '2027-01-04' } }), allocationStateStatus: 'ready' });
  assert.equal(result.overallBudget, '125.123456');
  assert.equal(overview({ company: { ...company, budgetUnit: 'credits' }, allocationState: nativeState(), allocationStateStatus: 'ready' }).overallBudget, null);
});

test('invalid native money cannot be formatted as a budget or unallocated amount', () => {
  for (const extra of [{ envelopeTotal: 'NaN' }, { envelopeTotal: '-1' }, { allocatedTotal: '' }, { unallocatedAmount: '1e3' }]) {
    assert.equal(overview({ allocationState: nativeState(extra), allocationStateStatus: 'ready' }).overallBudget, null);
  }
});
