import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import Module, {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';

const frontend=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../../..');
const require=createRequire(path.join(frontend,'package.json'));
const React=require('react');
const {renderToStaticMarkup}=require('react-dom/server');
const ts=require('typescript');
const originalResolve=Module._resolveFilename,originalLoad=Module._load;
const extensions=Object.fromEntries(['.ts','.tsx'].map(ext=>[ext,require.extensions[ext]]));
let DailySpendByTeam,chartRows,lines,xAxis;
try {
 Module._resolveFilename=function(request,parent,...rest){return originalResolve.call(this,request.startsWith('@/')?path.join(frontend,'src',request.slice(2)):request,parent,...rest);};
 Module._load=function(request,parent,...rest){
  if(request==='recharts'){
   const Empty=function Empty(){return null;};
   return {
    ResponsiveContainer:function ResponsiveContainer({children}){return React.createElement('div',null,children);},
    LineChart:function LineChart({data,children}){chartRows=data;return React.createElement('div',null,children);},
    Line:function Line(props){lines.push(props);return null;},
    Tooltip:function Tooltip({content}){const row=chartRows.find(row=>row.kind==='recorded');return row?content({active:true,payload:[{payload:row}],label:row.ts}):null;},
    XAxis:function XAxis(props){xAxis=props;return null;},
    CartesianGrid:Empty,ReferenceArea:Empty,ReferenceLine:Empty,YAxis:Empty,
   };
  }
  if(request==='./team-picker')return {TeamPicker:function TeamPicker(){return React.createElement('button',null,'Teams');}};
  return originalLoad.call(this,request,parent,...rest);
 };
 for(const ext of ['.ts','.tsx'])require.extensions[ext]=(module,filename)=>module._compile(ts.transpileModule(fs.readFileSync(filename,'utf8'),{fileName:filename,compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}}).outputText,filename);
 ({DailySpendByTeam}=require(path.join(frontend,'src/components/dashboard/daily-spend-by-team.tsx')));
} finally {
 Module._resolveFilename=originalResolve;Module._load=originalLoad;
 for(const ext of ['.ts','.tsx']){if(extensions[ext])require.extensions[ext]=extensions[ext];else delete require.extensions[ext];}
}
const teams=[{id:'a',name:'Research',color:'var(--chart-1)'},{id:'b',name:'Product',color:'var(--chart-2)'}];
const period={start:'2026-10-01',end:'2026-12-31',label:'Q4 2026'};
const record=(id,amount,extra={})=>({id,amount,teamId:'a',date:'2026-10-24',component:'api',unit:'usd',provider:'x',provenance:'reported_charge',source:'ledger',complete:false,...extra});
function render(records){chartRows=[];lines=[];xAxis=null;return renderToStaticMarkup(React.createElement(DailySpendByTeam,{records,teams,period}));}

test('compact daily panel keeps exact period, visible series, partial actuals and a precise daily table',()=>{
 const html=render([record('a',12.34)]);
 assert.match(html,/Daily spend by team/);assert.match(html,/Oct 1/);assert.match(html,/Dec 31/);assert.match(html,/Q4 2026/);
 assert.match(html,/Research/);assert.match(html,/Product/);assert.match(html,/View daily amounts/);assert.match(html,/\$12\.34/);
 assert.match(html,/partial day/);assert.doesNotMatch(html,/full day, projected/);assert.doesNotMatch(html,/role="group" aria-label="Range"/);
 assert.equal(chartRows.length,1);assert.equal(chartRows[0].date,'2026-10-24');assert.equal(chartRows[0].t_a,12.34);
 assert.equal(xAxis.domain[1]-xAxis.domain[0],86_400_000,'one day has a finite, non-zero chart domain');
 assert.deepEqual(xAxis.ticks,[chartRows[0].ts]);
 assert.ok(lines.every(line=>line.connectNulls===false));
 const actual=lines.find(line=>line.dataKey==='t_a'&&typeof line.dot==='function');
 assert.equal(actual.dot({cx:100,cy:40,index:0}).type,'circle');
});

test('plot stops at the latest record and retains gaps inside the recorded range',()=>{
 const html=render([record('first',0,{date:'2026-10-01'}),record('last',12.34)]);
 assert.match(html,/Oct 1/);assert.match(html,/Dec 31/);assert.match(html,/Q4 2026/);
 assert.equal(chartRows.length,24);assert.equal(chartRows[0].t_a,0);assert.equal(chartRows[1].t_a,null);
 assert.equal(chartRows.at(-1).date,'2026-10-24');assert.equal(chartRows.at(-1).partial,true);
 const actual=lines.find(line=>line.dataKey==='t_a'&&typeof line.dot==='function');
 assert.equal(actual.dot({cx:100,cy:40,index:0}).type,'circle');
 assert.equal(actual.dot({cx:100,cy:40,index:1}).type,'g');
});

test('informational and invalid amounts show an honest empty state with coverage reasons',()=>{
 const html=render([record('unpriced',0,{provenance:'usage_only'}),record('invalid',NaN)]);
 assert.match(html,/No spending recorded for this period/);
 assert.match(html,/Oct 1/);assert.match(html,/Dec 31/);assert.match(html,/Q4 2026/);
 assert.match(html,/Usage without a dollar price is excluded/);assert.match(html,/1 record has no valid dollar amount/);
 assert.doesNotMatch(html,/View daily amounts/);assert.doesNotMatch(html,/\$0\.00/);
});
