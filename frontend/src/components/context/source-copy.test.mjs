import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import Module, { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import ts from 'typescript';

const require = createRequire(import.meta.url);
const frontend = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../..');
const originalResolve = Module._resolveFilename;
const extensions = Object.fromEntries(['.ts', '.tsx'].map(ext => [ext, require.extensions[ext]]));
let SourceQuote, ContextCard, EvidenceCard;
try {
  Module._resolveFilename = function(request, parent, ...rest) {
    return originalResolve.call(this, request.startsWith('@/') ? path.join(frontend, 'src', request.slice(2)) : request, parent, ...rest);
  };
  for (const ext of ['.ts', '.tsx']) require.extensions[ext] = (loaded, filename) => loaded._compile(ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
    fileName: filename,
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true },
  }).outputText, filename);
  ({ SourceQuote, ContextCard } = require('./context-card.tsx'));
  ({ EvidenceCard } = require('../evidence/evidence-card.tsx'));
} finally {
  Module._resolveFilename = originalResolve;
  for (const ext of ['.ts', '.tsx']) {
    if (extensions[ext]) require.extensions[ext] = extensions[ext];
    else delete require.extensions[ext];
  }
}

const source = {
  documentId: 'document-source-1', integration: 'slack', title: 'Synthetic biology test fixtures',
  excerpt: 'Our synthetic biology team keeps test fixtures.\n  Preserve  spacing.',
  author: 'Fixture Labs', locator: 'synthetic-biology-fixture-review', date: '2026-10-21',
};
const item = {
  id: 'context-1', title: 'Synthetic biology test fixtures',
  summary: 'The synthetic biology team needs test fixtures for the product demo.',
  sources: [source], kind: 'message', teamIds: [], personIds: [], scope: 'company',
  expectedEffect: 'decrease', confidence: 'medium', claimType: 'interpretation',
  uncertainty: 'Test fixtures are incomplete; source coverage remains partial.',
};

test('source quotes preserve business words, source labels and whitespace without mutating records', () => {
  const before = JSON.stringify(source);
  const html = renderToStaticMarkup(React.createElement(SourceQuote, { source }));
  assert.ok(html.includes(source.excerpt));
  assert.ok(html.includes(source.author));
  assert.ok(html.includes(source.locator));
  assert.equal(JSON.stringify(source), before);
});

test('context and evidence preserve business descriptions, source titles and coverage caveats', () => {
  const before = JSON.stringify(item);
  const components = [
    [ContextCard, { item, allItems: [item], onViewSource() {} }],
    [EvidenceCard, { row: { item, superseded: false, teams: [], people: [], adjustments: [], scope: 'company', category: 'staffing' }, unit: 'usd', onViewSource() {} }],
  ];
  for (const [Component, props] of components) {
    const html = renderToStaticMarkup(React.createElement(Component, props));
    for (const text of [item.title, item.summary, item.uncertainty, source.title, source.excerpt]) assert.ok(html.includes(text), text);
  }
  assert.equal(JSON.stringify(item), before);
});
