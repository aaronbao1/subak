import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import Module, { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
const frontend = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../..');
const require = createRequire(path.join(frontend, 'package.json'));
const React = require('react');
const {renderToStaticMarkup} = require('react-dom/server');
const ts = require('typescript');
const originalResolve = Module._resolveFilename;
const extensions = Object.fromEntries(['.ts','.tsx'].map(ext=>[ext,require.extensions[ext]]));
let DayDetail;
try {
 Module._resolveFilename=function(request,parent,...rest){return originalResolve.call(this,request.startsWith('@/')?path.join(frontend,'src',request.slice(2)):request,parent,...rest);};
 for(const ext of ['.ts','.tsx'])require.extensions[ext]=(loaded,filename)=>loaded._compile(ts.transpileModule(fs.readFileSync(filename,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}}).outputText,filename);
 ({DayDetail}=require(path.join(frontend,'src/components/usage/day-detail.tsx')));
} finally {
 Module._resolveFilename=originalResolve;
 for(const ext of ['.ts','.tsx']){if(extensions[ext])require.extensions[ext]=extensions[ext];else delete require.extensions[ext];}
}
test('usage detail keeps values and incomplete coverage without origin labels or technical identifiers',()=>{
 const row={date:'2026-10-25',coverage:'partial',recordedSpend:'12.3456',costsByValueKind:{reported:null,estimated:null,measured:null,simulated:'12.3456'},includedUsageNotional:'3.00',tokens:{input:10,output:5,total:15,cachedInput:2,reasoning:1},tokenObservedRecordCounts:{input:1,output:1,total:1,cachedInput:1,reasoning:1},recordCount:1,revision:'synthetic-revision-2',sourceRefs:['Synthetic Northstar Fixture'],breakdowns:[]};
 const before=structuredClone(row);
 const html=renderToStaticMarkup(React.createElement(DayDetail,{buckets:[row],selectedDate:row.date,metric:'spend',synthetic:true}));
 assert.doesNotMatch(html,/demo|scripted|synthetic|fixture/i);
 assert.match(html,/\$12\.3456/);assert.match(html,/incomplete coverage/);assert.match(html,/subset/);assert.match(html,/1 of 1 records/);
 assert.deepEqual(row,before);
});
