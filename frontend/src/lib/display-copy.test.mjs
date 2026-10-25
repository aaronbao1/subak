import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { stripTypeScriptTypes } from 'node:module';
const code = stripTypeScriptTypes(fs.readFileSync(new URL('./display-copy.ts', import.meta.url), 'utf8'), { mode: 'transform' });
const { displayCopy, displaySourceText, displayReference, safeDisplayMetadata } = await import(`data:text/javascript;base64,${Buffer.from(code).toString('base64')}`);
test('presentation removes origin labels without inventing real-world verification', () => {
 assert.equal(displayCopy('Synthetic Northstar Fixture'), 'Northstar');
 assert.equal(displayCopy('Demo data · Scripted assistant'), 'Data · Assistant');
 assert.equal(displayCopy('Source has incomplete coverage and stale forecast.'), 'Source has incomplete coverage and stale forecast.');
 assert.equal(displayCopy('Synthetic usage. Category details unavailable.'), 'Usage. Category details unavailable.');
 assert.equal(displayCopy('Product demo starts November 10.'), 'Product demo starts November 10.');
 assert.equal(displayCopy('Synthetic fixture assessment against matching team allocation and issued full-period forecast.'), 'Assessment against matching team allocation and issued full-period forecast.');
});
test('technical origin identifiers are hidden while clean audit references survive', () => {
 assert.equal(displayReference('synthetic-ui-run-1','Saved forecast'),'Saved forecast');
 assert.equal(displayReference('forecast-demo-2026','Saved forecast'),'Saved forecast');
 assert.equal(displayReference('run-123','Saved forecast'),'run-123');
 assert.equal(displayReference('synthetic-outcome-v1:abcd1234','Loaded revision'),'Loaded revision');
});
test('unattributed person fallback preserves the missing-ledger warning', () => {
 assert.equal(displayCopy('This forecast-demo person has no repository ledger identity: unavailable attribution, not zero spend.'), 'This person has no repository ledger identity: unavailable attribution, not zero spend.');
});
test('known company coverage limitations use exact presentation copy without rewriting source text', () => {
 const cases = [
  ['Explicit simulated company source manifest; completeness applies only to exact received source rows.', 'Coverage is complete only for the source rows received.'],
  ['The regenerated source explicitly attests its full as-of day; later days are unknown and no holdout truth is used.', 'The source is complete through its stated as-of day. Later days remain unknown; future outcomes are not used.'],
  ['Historical replay requires chronological native receipts; issued ForecastService snapshots preserve prior vintages.', 'Historical comparisons require records received in time order. Published forecasts remain fixed.'],
 ];
 for (const [original, expected] of cases) {
  assert.equal(displayCopy(original), expected);
  assert.equal(displaySourceText(original), original);
  assert.equal(displayCopy(`Quoted limitation: ${original}`), `Quoted limitation: ${original}`);
 }
});
test('display metadata is a new view with flags omitted and coverage untouched', () => {
 const original={is_synthetic:true,dataset_id:'synthetic:demo',amount:'1.25',coverage:'partial',notes:['Synthetic demo data', 'Missing source coverage.'], nested:{status:'stale',isDemo:true}};
 const snapshot=structuredClone(original);
 const shown=safeDisplayMetadata(original);
 assert.deepEqual(shown,{amount:'1.25',coverage:'partial',notes:['Data','Missing source coverage.'],nested:{status:'stale'}});
 assert.deepEqual(original,snapshot);
});
test('source prefixes and parenthesized origin markers do not leak through expanded details',()=>{
 assert.equal(displayCopy('Synthetic demo: Anthropic cost report'), 'Anthropic cost report');
 assert.equal(displayCopy('Source (simulated)'), 'Source');
 assert.deepEqual(safeDisplayMetadata({fixture_note:'Missing source coverage.',isDemo:true}),{note:'Missing source coverage.'});
});
test('domain terms and source formatting are not origin labels', () => {
 for (const source of [
  'The synthetic biology team needs more capacity for test fixtures.',
  'Synthetic data generation is the research objective.',
  'Replace lighting fixtures and order synthetic fabric.',
  'Product demo starts November 10.',
  '  > Synthetic biology\n\n    Test fixtures retain their indentation.  ',
 ]) assert.equal(displayCopy(source), source);
});
test('source text remains verbatim even when it discusses development labels', () => {
 const source = '  “Synthetic demo data” is the document title.\n\n    We discussed scripted assistant test fixtures.';
 assert.equal(displaySourceText(source), source);
 assert.equal(displaySourceText('', 'No excerpt supplied.'), 'No excerpt supplied.');
 assert.equal(displaySourceText(null, 'No excerpt supplied.'), 'No excerpt supplied.');
});
test('source references and metadata do not erase legitimate domain identities', () => {
 for (const source of ['synthetic-biology', 'test-fixtures', 'synthetic Biology planning', 'product-demo-videos']) {
  assert.equal(displayReference(source), source);
  assert.deepEqual(safeDisplayMetadata({reference:source}), {reference:source});
 }
 assert.deepEqual(safeDisplayMetadata({synthetic_biology:'test fixtures'}), {synthetic_biology:'test fixtures'});
});
