import test from "node:test";
import assert from "node:assert/strict";
import { tsModuleUrl } from "../../../tests/load-ts-module.mjs";
const { snapshotForecastBundle, selectSnapshotWeeklyHistory, previewSnapshotScenario } = await import(tsModuleUrl(new URL("./snapshot-read.ts", import.meta.url)));
const driver = { id: "d1", kind: "workload", parameters: { exposure: 10 }, citations: [{ excerpt: "Original source" }] };
function bundle() {
  const view = { id: "view-issued", run_id: "issued-7", scope: { type: "company", id: "acme" }, target: { unit: "USD", quantity: "spend", basis: "planning" }, daily: [{ date: "2026-10-25", base: 0.10499999999999998, complete: false }], weekly: [], cumulative: [], quarter_outlook: { start: "2026-10-01", end: "2027-01-01", base: 125.25, low: 100, high: 150 }, included_drivers: [structuredClone(driver)], queued_changes: [], driver_effects: [{ driver_id: "d1", available: true, base_delta: 25, with_base: 125.25, without_base: 100.25 }], limitations: ["Coverage partial"], is_synthetic: true };
  return { views: [view, { ...structuredClone(view), id: "team-view", scope: { type: "team", id: "research" } }], publication: { run_id: "issued-7", sequence: 3, published_at: "2026-10-25T00:00:00Z" }, current_actuals: { revision: "r1" }, driver_effects: view.driver_effects };
}
function history() {
  const week = (start, endExclusive, state, amount) => ({ start, endExclusive, state, actual: { amount, status: state === "closed" ? "mature" : "partial", source: "observed_outcome", datasetId: "targets", revision: "truth-2", corrected: true, sourceRefs: ["receipt-1"] }, priorForecast: { amount: "100.00000001", runId: "old-issue", targetId: `t:${start}`, datasetId: "targets", issuedAt: `${start}T00:00:00Z`, informationCutoff: `${start}T00:00:00Z`, start, endExclusive }, outlook: null, variance: { amount: state === "closed" ? "25.00000001" : null, status: state === "closed" ? "available" : "unavailable", reason: state === "closed" ? null : "Week open" } });
  return { scope: { type: "team", id: "research", name: "Research" }, startDate: "2026-10-05", endDateExclusive: "2026-10-26", timezone: "UTC", unit: "USD", basis: "planning", quantity: "spend", datasetId: "response-id", asOf: "2026-10-25T12:00:00Z", synthetic: true, actualsRevision: "actuals-r2", selectionPolicy: "latest_published_before_week_start", notes: ["Saved source coverage"], weeks: [week("2026-10-05", "2026-10-12", "closed", "125.00000002"), week("2026-10-12", "2026-10-19", "closed", "0.00"), week("2026-10-19", "2026-10-26", "current", null)] };
}
const query = { scopeType: "team", scopeId: "research", startDate: "2026-10-12", endDateExclusive: "2026-10-26" };

test("snapshot reads retain issued identities and exact values with caller mutation isolation", () => {
  const input = bundle(), result = snapshotForecastBundle(input);
  assert.deepEqual(result, input);
  result.views[0].included_drivers[0].parameters.exposure = 999;
  result.current_actuals.revision = "changed";
  assert.equal(input.views[0].included_drivers[0].parameters.exposure, 10);
  assert.equal(input.current_actuals.revision, "r1");
  assert.deepEqual(snapshotForecastBundle(input, "issued-7"), input);
  assert.throws(() => snapshotForecastBundle(input, "invented-refresh"), /unavailable|saved/i);
});

test("history selection slices only saved complete week boundaries and retains decimals, nulls and as-of", () => {
  const input = history(), result = selectSnapshotWeeklyHistory([input], query);
  assert.deepEqual(result, { ...input, startDate: query.startDate, endDateExclusive: query.endDateExclusive, weeks: input.weeks.slice(1) });
  assert.equal(result.weeks[0].actual.amount, "0.00");
  assert.equal(result.weeks[1].actual.amount, null);
  assert.equal(result.weeks[0].priorForecast.amount, "100.00000001");
  result.weeks[0].actual.sourceRefs.push("new");
  assert.deepEqual(input.weeks[1].actual.sourceRefs, ["receipt-1"]);
});

test("missing scopes, ranges, gaps and conflicting saved histories fail instead of synthesizing weeks", () => {
  const input = history();
  for (const q of [{ ...query, scopeId: "other" }, { ...query, startDate: "2026-09-28" }, { ...query, endDateExclusive: "2026-11-02" }, { ...query, startDate: "2026-10-13" }]) assert.throws(() => selectSnapshotWeeklyHistory([input], q));
  assert.throws(() => selectSnapshotWeeklyHistory(undefined, query), /unavailable|saved/i);
  assert.throws(() => selectSnapshotWeeklyHistory([{ ...input, weeks: input.weeks.filter(row => row.start !== query.startDate) }], query), /week|unavailable/i);
  assert.throws(() => selectSnapshotWeeklyHistory([input, { ...input, actualsRevision: "different" }], query), /conflict|ambiguous/i);
  assert.deepEqual(selectSnapshotWeeklyHistory([input, structuredClone(input)], query).weeks, input.weeks.slice(1));
});

test("saved scenario edits preserve money and source data without asserting calculated effects or a new issuance", () => {
  const input = bundle(), before = structuredClone(input), proposed = [{ ...structuredClone(driver), parameters: { exposure: 20 } }];
  const preview = previewSnapshotScenario(input, "issued-7", proposed);
  assert.equal(preview.recalculation_required, true);
  assert.equal(preview.parent_run_id, "issued-7");
  assert.equal(preview.is_scenario, true);
  assert.equal(preview.publication, null);
  assert.deepEqual(preview.driver_effects, []);
  for (const view of preview.views) {
    assert.equal(view.run_id, "issued-7");
    assert.equal(view.quarter_outlook.base, 125.25);
    assert.equal(view.daily[0].base, 0.10499999999999998);
    assert.equal(view.included_drivers[0].parameters.exposure, 20);
    assert.deepEqual(view.driver_effects, []);
    assert.ok(view.limitations.some(line => /require.*forecast run|recalculat/i.test(line)));
  }
  assert.deepEqual(input, before);
  preview.views[0].included_drivers[0].parameters.exposure = 77;
  assert.equal(proposed[0].parameters.exposure, 20);
  assert.equal(preview.views[1].included_drivers[0].parameters.exposure, 20);
  assert.throws(() => previewSnapshotScenario(input, "unknown", proposed), /unavailable|saved/i);
});

test("scenario removal keeps the full company replacement without inventing applicability in other scopes", () => {
  const input = bundle();
  const replacement = [{ id: "new", kind: "pricing", parameters: { rate: 2 } }];
  const result = previewSnapshotScenario(input, "issued-7", replacement);
  assert.deepEqual(result.views[0].included_drivers, replacement);
  assert.deepEqual(result.views[1].included_drivers, []);
  assert.throws(() => previewSnapshotScenario(input, "issued-7", [driver, driver]), /duplicate/i);
});
