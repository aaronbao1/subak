import test from 'node:test';
import assert from 'node:assert/strict';
import { tsModuleUrl } from '../../tests/load-ts-module.mjs';
const { selectCompanyOverview } = await import(tsModuleUrl(new URL('./company-overview.ts', import.meta.url)));
const period = { start: '2026-10-01', end: '2026-12-31' };
const company = { id: 'northstar', name: 'Uber', isDemo: true, currentPeriod: period, budgetUnit: 'usd' };
const view = (extra = {}) => ({ run_id: 'issued', scope: { type: 'company', id: 'northstar' }, dataset_id: 'northstar', target: { unit: 'USD', basis: 'planning', timezone: 'UTC' }, quarter_outlook: { start: period.start, end: '2027-01-01', base: 464485.19875 }, ...extra });
const state = (extra = {}) => ({ period: { id: 'q4', label: 'Q4', startDate: period.start, endDateExclusive: '2027-01-01' }, unit: 'USD', envelopeTotal: '430000.00', ...extra });
const spending = [
  { teamId: 'research', date: '2026-10-24', amount: 100, unit: 'usd', component: 'api', provenance: 'simulated', complete: true },
  { teamId: '', date: '2026-10-24', amount: 23.08, unit: 'usd', component: 'api', provenance: 'simulated', complete: true },
  { teamId: '', date: '2026-10-24', amount: 50, unit: 'usd', component: 'included_usage', provenance: 'simulated', complete: true },
  { teamId: 'research', date: '2026-09-30', amount: 99, unit: 'usd', component: 'api', provenance: 'simulated', complete: true },
];
const select = (extra = {}) => selectCompanyOverview({ company, spending, forecastBundle: { views: [view()] }, allocationState: state(), allocationStateStatus: 'ready', ...extra });

test('company recorded spend includes shared billable cost and full issued outlook uses native envelope', () => {
  assert.deepEqual(select(), { recorded: 123.08, expected: 464485.19875, gap: 34485.2 });
});

test('missing company, records and forecast stay unknown while exact zero remains known', () => {
  assert.deepEqual(select({ company: undefined }), { recorded: null, expected: null, gap: null });
  assert.deepEqual(select({ spending: [], forecastBundle: undefined }), { recorded: null, expected: null, gap: null });
  for (const row of [{ ...spending[0], component: 'unpriced_usage', provenance: 'usage_only', amount: 0 }, { ...spending[0], amount: NaN }]) assert.equal(select({ spending: [row] }).recorded, null);
  assert.deepEqual(select({ spending: [{ ...spending[0], amount: 0 }], forecastBundle: { views: [view({ quarter_outlook: { start: period.start, end: '2027-01-01', base: 0 } })] }, allocationState: state({ envelopeTotal: '0.00' }) }), { recorded: 0, expected: 0, gap: 0 });
});

test('company forecast cannot be substituted with team rollups or a different company target', () => {
  for (const scope of [{ type: 'team', id: 'research' }, { type: 'company', id: 'other' }]) {
    assert.deepEqual(select({ forecastBundle: { views: [view({ scope })] } }), { recorded: 123.08, expected: null, gap: null });
  }
  for (const extra of [{ quarter_outlook: { start: '2026-10-19', end: '2026-10-26', base: 123 } }, { dataset_id: 'other' }, { target: { unit: 'credits', basis: 'planning', timezone: 'UTC' } }, { target: { unit: 'USD', basis: 'billing', timezone: 'UTC' } }, { target: { unit: 'USD', quantity: 'tokens', basis: 'planning', timezone: 'UTC' } }, { quarter_outlook: { start: period.start, end: '2027-01-01', base: 123, complete: false } }, { quarter_outlook: { start: period.start, end: '2027-01-01', base: 123, partial: true } }]) {
    assert.equal(select({ forecastBundle: { views: [view(extra)] } }).expected, null);
  }
});

test('gap requires ready native allocation with exactly matching period and currency', () => {
  for (const status of [undefined, 'idle', 'loading', 'stale', 'error']) assert.equal(select({ allocationStateStatus: status }).gap, null);
  for (const allocationState of [undefined, state({ unit: 'credits' }), state({ period: { startDate: period.start, endDateExclusive: '2026-12-31' } }), state({ period: { startDate: '2026-09-01', endDateExclusive: '2027-01-01' } })]) {
    const result = select({ allocationState });
    assert.equal(result.expected, 464485.19875);
    assert.equal(result.gap, null);
  }
});

test('invalid and unsafe money is withheld instead of presenting a misleading comparison', () => {
  for (const envelopeTotal of ['NaN', '-1', '1e3', '', '9007199254740991', '99999999999999999999999999999999999999999999999']) assert.equal(select({ allocationState: state({ envelopeTotal }) }).gap, null);
  for (const base of [NaN, Infinity, Number.MAX_SAFE_INTEGER]) assert.equal(select({ forecastBundle: { views: [view({ quarter_outlook: { start: period.start, end: '2027-01-01', base } })] } }).expected, null);
});

test('negative gap is headroom with stable cents while the issued expected value is retained', () => {
  const result = select({ forecastBundle: { views: [view({ quarter_outlook: { start: period.start, end: '2027-01-01', base: 100.1 } })] }, allocationState: state({ envelopeTotal: '100.25' }) });
  assert.equal(result.expected, 100.1);
  assert.equal(result.gap, -0.15);
});
