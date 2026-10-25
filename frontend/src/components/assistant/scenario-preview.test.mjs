import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import Module, { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const frontend = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../..");
const require = createRequire(path.join(frontend, "package.json"));
const React = require("react");
const { renderToStaticMarkup } = require("react-dom/server");
const ts = require("typescript");
const resolve = Module._resolveFilename;
const extensions = Object.fromEntries([".ts", ".tsx"].map(extension => [extension, require.extensions[extension]]));
let ScenarioPreview;
try {
  Module._resolveFilename = function(request, parent, ...rest) { return resolve.call(this, request.startsWith("@/") ? path.join(frontend, "src", request.slice(2)) : request, parent, ...rest); };
  for (const extension of [".ts", ".tsx"]) require.extensions[extension] = (module, filename) => module._compile(ts.transpileModule(fs.readFileSync(filename, "utf8"), { fileName: filename, compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true } }).outputText, filename);
  ({ ScenarioPreview } = require(path.join(frontend, "src/components/assistant/scenario-preview.tsx")));
} finally {
  Module._resolveFilename = resolve;
  for (const extension of [".ts", ".tsx"]) {
    if (extensions[extension]) require.extensions[extension] = extensions[extension]; else delete require.extensions[extension];
  }
}
const baseline = { run_id: "issued-7", scope: { type: "company", id: "acme", name: "Acme" }, target: { unit: "USD", quantity: "spend", basis: "planning" }, daily: [], quarter_outlook: { start: "2026-10-01", end: "2027-01-01", base: 125.25 } };
const render = (scenario, before = baseline) => renderToStaticMarkup(React.createElement(ScenarioPreview, { baseline: before, scenario }));

test("saved-data preview displays the issued amount and recalculation notice without a fake zero impact", () => {
  const html = render({ parent_run_id: "issued-7", recalculation_required: true, views: [structuredClone(baseline)] });
  assert.match(html, /Assumptions saved/);
  assert.match(html, /Recalculation needs a connected forecast service/);
  assert.match(html, /125\.25/);
  assert.doesNotMatch(html, /Difference|Scenario range|\$0(?:\.00)?(?:<|\s)/);
});

test("ordinary calculated scenarios keep their real financial difference", () => {
  const html = render({ parent_run_id: "issued-7", views: [{ ...baseline, quarter_outlook: { ...baseline.quarter_outlook, base: 150.50 } }] });
  assert.match(html, /Difference/);
  assert.match(html, /\+\$25\.25/);
  assert.doesNotMatch(html, /Recalculation needs/);
});

test("saved preview does not turn an unavailable baseline into zero or accept a different parent", () => {
  const unknown = { ...baseline, quarter_outlook: { ...baseline.quarter_outlook, base: null } };
  assert.match(render({ parent_run_id: "issued-7", recalculation_required: true, views: [unknown] }, unknown), /Unavailable/);
  assert.match(render({ parent_run_id: "another-run", recalculation_required: true, views: [baseline] }), /different parent/);
});
