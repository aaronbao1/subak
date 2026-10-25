import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { stripTypeScriptTypes } from 'node:module';

const source = stripTypeScriptTypes(fs.readFileSync(new URL('./forecast-derive.ts', import.meta.url), 'utf8'));
const { evidenceDrivers } = await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);

test('issued inclusion takes precedence over current evidence queue status', () => {
  const issued = { id: 'included', status: 'eligible', publication_status: 'included', source_revision: 1 };
  const rows = evidenceDrivers(
    { included_drivers: [issued], queued_changes: [] },
    [{ drivers: [{ ...issued, queue_status: 'queued' }] }],
  );
  assert.deepEqual(rows.map(row => [row.driver.id, row.status]), [['included', 'Included']]);
  assert.equal(rows[0].driver, issued);
});

test('frozen context-only exclusion is not labeled as awaiting numerical inclusion', () => {
  const excluded = {
    id: 'vendor-benchmark', status: 'context_only', publication_status: 'excluded',
    publication_reason: 'Context only; no supported numerical effect.',
  };
  const rows = evidenceDrivers({ included_drivers: [], queued_changes: [excluded] }, []);
  assert.deepEqual(rows.map(row => [row.driver.id, row.status]), [['vendor-benchmark', 'Context only']]);
});

test('frozen unsupported exclusion overrides a live queue marker for the same driver', () => {
  const excluded = {
    id: 'unsupported', status: 'eligible', publication_status: 'excluded',
    publication_reason: 'Unsupported driver kind.',
  };
  const rows = evidenceDrivers(
    { included_drivers: [], queued_changes: [excluded] },
    [{ drivers: [{ ...excluded, queue_status: 'queued' }] }],
  );
  assert.deepEqual(rows.map(row => [row.driver.id, row.status]), [['unsupported', 'Context only']]);
});

test('new evidence with an explicit queued marker is awaiting a future issuance', () => {
  const rows = evidenceDrivers(
    { included_drivers: [], queued_changes: [] },
    [{ drivers: [{ id: 'new-source', status: 'eligible', queue_status: 'queued' }] }],
  );
  assert.deepEqual(rows.map(row => [row.driver.id, row.status]), [['new-source', 'Queued']]);
});

test('an otherwise eligible driver excluded only by the frozen cutoff remains queued', () => {
  const afterCutoff = {
    id: 'late-arrival', status: 'eligible', publication_status: 'excluded',
    publication_reason: 'Available after this publication information cutoff.',
    available_at: '2026-10-26T00:00:00Z',
  };
  const rows = evidenceDrivers({ included_drivers: [], queued_changes: [afterCutoff] }, []);
  assert.deepEqual(rows.map(row => [row.driver.id, row.status]), [['late-arrival', 'Queued']]);
});
