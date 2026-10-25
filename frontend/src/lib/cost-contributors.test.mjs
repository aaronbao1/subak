import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { stripTypeScriptTypes } from 'node:module';
const moduleUrl = source => `data:text/javascript;base64,${Buffer.from(source).toString('base64')}`;
const finance = moduleUrl(stripTypeScriptTypes(fs.readFileSync(new URL('./finance-summary.ts', import.meta.url), 'utf8')));
const source = stripTypeScriptTypes(fs.readFileSync(new URL('./cost-contributors.ts', import.meta.url), 'utf8')).replace('"./finance-summary"', JSON.stringify(finance));
const { selectCostContributors } = await import(moduleUrl(source));
const period = { start: '2026-10-19', end: '2026-10-25' };
let nextId = 0;
const record = (extra = {}) => ({ id: `r-${nextId++}`, teamId: 'research', personId: 'p1', date: '2026-10-20', provider: 'anthropic', model: 'Model', component: 'api', amount: 10, unit: 'usd', provenance: 'reported_charge', source: 'Provider export', complete: true, ...extra });
const select = (records, extra = {}) => selectCostContributors({ records, period, ...extra });

test('provider and model identify one additive partition, including provider-only financial rows', () => {
  const result = select([
    record({ provider: 'provider-a', model: 'Same model', amount: 30 }),
    record({ provider: 'provider-b', model: 'Same model', amount: 20 }),
    record({ provider: 'provider-a', model: undefined, component: 'subscription', amount: 10 }),
    record({ provider: 'provider-a', model: undefined, component: 'extra_usage', amount: 5 }),
  ]);
  assert.equal(result.status, 'available');
  assert.equal(result.total, 65);
  assert.deepEqual(result.contributors.map(row => [row.provider, row.model, row.amount]), [
    ['provider-a', 'Same model', 30], ['provider-b', 'Same model', 20], ['provider-a', undefined, 15],
  ]);
  assert.equal(new Set(result.contributors.map(row => row.key)).size, 3);
  assert.equal(result.other, null);
});

test('top five plus Other reconciles exactly and Other contains only actual tail rows', () => {
  const result = select([7, 6, 5, 4, 3, 2, 1].map(amount => record({ provider: `provider-${amount}`, amount })));
  assert.equal(result.contributors.length, 5);
  assert.equal(result.other.amount, 3);
  assert.equal(result.other.groupCount, 2);
  assert.equal(result.other.recordCount, 2);
  assert.equal(result.total, 28);
  assert.equal(result.contributors.reduce((sum, row) => sum + row.amount, result.other.amount), result.total);
  assert.ok(Math.abs(result.contributors.reduce((sum, row) => sum + row.share, result.other.share) - 1) < 1e-12);
  assert.equal(select([1, 2, 3, 4, 5].map(amount => record({ provider: `${amount}`, amount }))).other, null);
});

test('included notional and usage-only amounts never enter the monetary denominator or provenance', () => {
  const result = select([
    record({ amount: 0.1 }), record({ amount: 0.2 }),
    record({ amount: 999, component: 'included_usage', provenance: 'estimate' }),
    record({ amount: 888, provenance: 'usage_only' }),
    record({ amount: 777, unit: 'tokens' }),
    record({ amount: 666, component: 'unpriced_usage', provenance: 'measured' }),
  ]);
  assert.equal(result.total, 0.3);
  assert.deepEqual(result.contributors[0].byProvenance, { reported_charge: 0.3 });
  assert.equal(result.contributors[0].recordCount, 2);
});

test('reported, estimated, measured and simulated records retain their source kinds', () => {
  const result = select(['reported_charge', 'estimate', 'measured', 'simulated'].map((provenance, index) => record({ provenance, amount: index + 1 })));
  assert.equal(result.total, 10);
  assert.deepEqual(result.contributors[0].byProvenance, { reported_charge: 1, estimate: 2, measured: 3, simulated: 4 });
});

test('exact period, team, person and unit scope exclude unrelated charges', () => {
  const result = select([
    record({ date: period.start, amount: 10 }), record({ date: period.end, amount: 20 }),
    record({ date: '2026-10-18', amount: 100 }), record({ date: '2026-10-26', amount: 100 }),
    record({ teamId: 'product', amount: 100 }), record({ personId: 'p2', amount: 100 }),
    record({ unit: 'credits', amount: 100 }), record({ personId: undefined, amount: 100 }),
  ], { teamId: 'research', personId: 'p1', unit: 'usd' });
  assert.equal(result.total, 30);
  assert.equal(result.unit, 'usd');
  assert.equal(result.contributors[0].recordCount, 2);
});

test('mixed financial currencies are unavailable, never silently combined', () => {
  const result = select([record(), record({ unit: 'credits' })]);
  assert.equal(result.status, 'mixed_units');
  assert.equal(result.total, null);
  assert.equal(result.contributors.length, 0);
  assert.equal(result.other, null);
  assert.equal(select([record(), record({ unit: 'credits' })], { unit: 'usd' }).total, 10);
});

test('empty, zero-charge, partial and invalid financial records keep distinct coverage', () => {
  assert.equal(select([]).status, 'no_records');
  assert.equal(select([]).total, null);
  assert.equal(select([record({ provenance: 'usage_only' })]).status, 'no_financial_records');
  const zero = select([record({ amount: 0 })]);
  assert.equal(zero.status, 'available');
  assert.equal(zero.total, 0);
  assert.equal(zero.contributors[0].share, null);
  assert.equal(zero.coverage, 'unknown');
  assert.equal(select([record({ complete: false })]).coverage, 'partial');
  const invalid = select([record({ amount: Infinity }), record({ amount: 5 })]);
  assert.equal(invalid.total, 5);
  assert.equal(invalid.invalidAmountCount, 1);
  assert.equal(invalid.coverage, 'partial');
  assert.equal(select([record({ amount: NaN })]).total, null);
});

test('refunds remain in the partition and a nonpositive total has no percentage', () => {
  const result = select([record({ amount: 10 }), record({ provider: 'refund', amount: -15 })]);
  assert.equal(result.total, -5);
  assert.deepEqual(result.contributors.map(row => row.amount), [10, -15]);
  assert.ok(result.contributors.every(row => row.share === null));
});
