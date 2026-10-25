import test from "node:test";
import assert from "node:assert/strict";
import { tsModuleUrl } from "../../../tests/load-ts-module.mjs";
const { selectApiSpend } = await import(tsModuleUrl(new URL("./api-spend-derive.ts", import.meta.url)));
const period = { start: "2026-10-19", end: "2026-10-25" };
let sequence = 0;
const record = (extra = {}) => ({ id: `r-${sequence++}`, teamId: "research", date: "2026-10-20", component: "api", provider: "anthropic", model: "Model", amount: 10, unit: "usd", tokens: 100, provenance: "reported_charge", source: "Provider export", complete: true, ...extra });
const select = (records, unit = "usd") => selectApiSpend({ records, period, unit });

test("only API financial rows in the exact period and unit enter spend and tokens", () => {
  const result = select([
    record({ date: period.start, amount: 0.1, tokens: 11 }),
    record({ date: period.end, amount: 0.2, tokens: 22 }),
    record({ date: "2026-10-18", amount: 500 }),
    record({ date: "2026-10-26", amount: 500 }),
    record({ unit: "credits", amount: 500 }),
    record({ unit: "tokens", amount: 500 }),
    record({ component: "subscription", amount: 500 }),
    record({ component: "extra_usage", amount: 500 }),
    record({ component: "included_usage", amount: 500, includedUsageNotional: 500 }),
    record({ component: "unpriced_usage", amount: 500 }),
    record({ provenance: "usage_only", amount: 500 }),
  ]);
  assert.equal(result.total, 0.3);
  assert.equal(result.tokens, 33);
  assert.equal(result.recordCount, 2);
  assert.equal(result.unpricedRecordCount, 2);
  assert.equal(result.providers[0].amount, 0.3);
  assert.equal(select([record({ unit: "credits", amount: 12 })], "credits").total, 12);
  assert.equal(select([record({ unit: "tokens", amount: 120 })], "tokens").total, null);
});

test("same model at different providers stays separate and missing attribution stays missing", () => {
  const result = select([
    record({ provider: "one", model: "Shared name", amount: 30 }),
    record({ provider: "two", model: "Shared name", amount: 20 }),
    record({ provider: "one", model: undefined, amount: 10 }),
    record({ provider: "", model: undefined, amount: 5 }),
  ]);
  assert.equal(result.total, 65);
  assert.deepEqual(result.models.map(row => [row.provider, row.model, row.amount]), [
    ["one", "Shared name", 30], ["two", "Shared name", 20], ["one", undefined, 10], [undefined, undefined, 5],
  ]);
  assert.equal(new Set(result.models.map(row => row.key)).size, 4);
  assert.deepEqual(result.providers.map(row => [row.provider, row.amount]), [["one", 40], ["two", 20], [undefined, 5]]);
});

test("a subset of reported tokens is never presented as complete model or provider usage", () => {
  const result = select([
    record({ amount: 5, tokens: 100 }),
    record({ amount: 4, tokens: undefined }),
    record({ provider: "openai", amount: 3, tokens: 0 }),
    record({ provider: "google", amount: 2, tokens: NaN }),
    record({ provider: "google", amount: 1, tokens: -1 }),
  ]);
  assert.equal(result.tokens, null);
  assert.equal(result.reportedTokens, 100);
  assert.equal(result.missingTokenCount, 3);
  assert.equal(result.models[0].tokens, null);
  assert.equal(result.models[0].reportedTokens, 100);
  assert.equal(result.providers[0].tokens, null);
  assert.equal(result.models.find(row => row.provider === "openai").tokens, 0);
  assert.equal(select([record({ tokens: undefined })]).reportedTokens, null);
});

test("absent, zero and unusable charges have distinct outcomes and invalid rows never affect totals", () => {
  const absent = select([]);
  assert.equal(absent.total, null);
  assert.equal(absent.status, "no_records");
  const zero = select([record({ amount: 0, tokens: 0 })]);
  assert.equal(zero.status, "available");
  assert.equal(zero.total, 0);
  assert.equal(zero.tokens, 0);
  assert.equal(zero.models[0].share, null);
  const invalid = select([record({ amount: Infinity }), record({ amount: NaN }), record({ amount: 2, complete: false })]);
  assert.equal(invalid.total, 2);
  assert.equal(invalid.invalidAmountCount, 2);
  assert.equal(invalid.recordCount, 1);
  assert.equal(invalid.coverage, "partial");
  assert.equal(select([record({ amount: NaN })]).status, "unavailable_amounts");
  assert.equal(select([record({ amount: NaN })]).total, null);
  assert.equal(select([record({ component: "unpriced_usage" })]).total, null);
});

test("refunds reconcile and nonpositive totals never produce spend shares", () => {
  const result = select([
    record({ provider: "anthropic", amount: 10 }),
    record({ provider: "openai", amount: -15, tokens: 0 }),
  ]);
  assert.equal(result.total, -5);
  assert.equal(result.hasRefunds, true);
  assert.deepEqual(result.models.map(row => row.amount), [10, -15]);
  assert.ok(result.models.every(row => row.share === null));
  assert.ok(result.providers.every(row => row.share === null));
  assert.equal(select([record({ amount: 10 }), record({ amount: -10 })]).total, 0);
});

test("all model rows and provider totals reconcile, including rows beyond the visible five", () => {
  const result = select([7, 6, 5, 4, 3, 2, 1].map(amount => record({ model: `Model ${amount}`, amount })));
  assert.equal(result.models.length, 7);
  assert.deepEqual(result.models.slice(0, 5).map(row => row.amount), [7, 6, 5, 4, 3]);
  assert.equal(result.models.slice(5).reduce((sum, row) => sum + row.amount, 0), 3);
  assert.equal(result.total, 28);
  assert.equal(result.providers[0].amount, 28);
});

test("source provenance remains available without relabeling financial records", () => {
  const result = select(["reported_charge", "estimate", "measured", "simulated"].map((provenance, index) => record({ provenance, amount: index + 1 })));
  assert.deepEqual(result.models[0].byProvenance, { reported_charge: 1, estimate: 2, measured: 3, simulated: 4 });
  assert.equal(result.coverage, "unknown");
  assert.equal(result.total, 10);
});
