import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { stripTypeScriptTypes } from 'node:module';

const file = new URL('./team-list-filters.ts', import.meta.url);
const source = fs.readFileSync(file, 'utf8');
const { parseTeamFilters, teamFilterQuery, filterTeamRows } = await import(`data:text/javascript;base64,${Buffer.from(stripTypeScriptTypes(source)).toString('base64')}`);
const rows = [
  { team: { name: 'Product', lead: 'Ada', description: 'Customer applications' }, spent: 10, projected: null, variance: null },
  { team: { name: 'Research', lead: 'Grace', description: 'Experiments' }, spent: 40, projected: 60, variance: 8 },
  { team: { name: 'Engineering', lead: 'Lin', description: 'Platform' }, spent: 40, projected: 80, variance: -5 },
];

test('team filters accept shared links and fall back safely for unknown sorts', () => {
  assert.deepEqual(parseTeamFilters(new URLSearchParams('q=research&sort=variance')), { query: 'research', sort: 'variance' });
  assert.deepEqual(parseTeamFilters(new URLSearchParams('sort=invalid')), { query: '', sort: 'spend' });
});

test('changing search retains existing period and sort query state', () => {
  const next = new URLSearchParams(teamFilterQuery(new URLSearchParams('period=week&sort=name'), { query: 'Grace', sort: 'name' }));
  assert.equal(next.get('period'), 'week');
  assert.equal(next.get('sort'), 'name');
  assert.equal(next.get('q'), 'Grace');
});

test('team search matches names, leads and descriptions without changing original rows', () => {
  assert.deepEqual(filterTeamRows(rows, { query: '  ADA ', sort: 'spend' }).map(r => r.team.name), ['Product']);
  assert.deepEqual(filterTeamRows(rows, { query: 'platform', sort: 'spend' }).map(r => r.team.name), ['Engineering']);
  assert.equal(filterTeamRows(rows, { query: 'absent', sort: 'spend' }).length, 0);
  assert.equal(rows[0].team.name, 'Product');
});

test('descending financial sorts keep unavailable values last and break ties by name', () => {
  assert.deepEqual(filterTeamRows(rows, { query: '', sort: 'spend' }).map(r => r.team.name), ['Engineering', 'Research', 'Product']);
  assert.deepEqual(filterTeamRows(rows, { query: '', sort: 'variance' }).map(r => r.team.name), ['Research', 'Engineering', 'Product']);
  assert.deepEqual(filterTeamRows(rows, { query: '', sort: 'name' }).map(r => r.team.name), ['Engineering', 'Product', 'Research']);
});
