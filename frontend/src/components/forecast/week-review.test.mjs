import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import Module, { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

const frontend=path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../..');
const require=createRequire(path.join(frontend,'package.json'));
const React=require('react');
const {renderToStaticMarkup}=require('react-dom/server');
const ts=require('typescript');
const originalResolve=Module._resolveFilename;
const originalLoad=Module._load;
const extensions=Object.fromEntries(['.ts','.tsx'].map(ext=>[ext,require.extensions[ext]]));
let WeekReview;
try {
  Module._resolveFilename=function(request,parent,...rest){return originalResolve.call(this,request.startsWith('@/')?path.join(frontend,'src',request.slice(2)):request,parent,...rest);};
  Module._load=function(request,parent,...rest){
    if(request==='@/components/ui/sheet') {
      const part=tag=>function SheetPart({children}) { return React.createElement(tag,null,children); };
      return {Sheet:({open,children})=>open?React.createElement('div',null,children):null,SheetContent:part('aside'),SheetHeader:part('header'),SheetTitle:part('h2'),SheetDescription:part('p')};
    }
    return originalLoad.call(this,request,parent,...rest);
  };
  for(const ext of ['.ts','.tsx']) require.extensions[ext]=(module,filename)=>module._compile(ts.transpileModule(fs.readFileSync(filename,'utf8'),{fileName:filename,compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}}).outputText,filename);
  ({WeekReview}=require(path.join(frontend,'src/components/forecast/week-review.tsx')));
} finally {
  Module._resolveFilename=originalResolve; Module._load=originalLoad;
  for(const ext of ['.ts','.tsx']) {if(extensions[ext])require.extensions[ext]=extensions[ext];else delete require.extensions[ext];}
}
const history={scope:{type:'team',id:'research',name:'Research'},startDate:'2026-10-05',endDateExclusive:'2026-11-02',timezone:'UTC',unit:'usd',basis:'planning',quantity:'spend',asOf:'2026-10-25T12:00:00Z',synthetic:true,datasetId:'demo',actualsRevision:'rev-2',selectionPolicy:'latest_published_before_week_start',weeks:[],notes:[]};
const prior={amount:'100.25',datasetId:'demo',runId:'original-run',targetId:'original-target',issuedAt:'2026-10-04T12:00:00Z',informationCutoff:'2026-10-04T00:00:00Z',start:'2026-10-05',endExclusive:'2026-10-12'};
const closed={start:'2026-10-05',endExclusive:'2026-10-12',state:'closed',actual:{amount:'120.75',status:'mature',source:'observed_outcome',datasetId:'demo',revision:'rev-2',corrected:false,sourceRefs:['ledger-1']},priorForecast:prior,outlook:null,variance:{amount:'20.50',status:'available',reason:null}};
const render=(week,extra={})=>renderToStaticMarkup(React.createElement(WeekReview,{week,history:{...history,...extra},onClose(){}}));

test('closed comparable week shows supplied original forecast and exact overrun',()=>{
  const html=render(closed);
  assert.match(html,/Original forecast/); assert.match(html,/\$100\.25/);
  assert.match(html,/\$120\.75/); assert.match(html,/\$20\.50 over forecast/);
  assert.match(html,/Oct 5/); assert.match(html,/Oct 11/);
  assert.match(html,/original-run/); assert.match(html,/Oct 4/);
});

test('current partial week never presents a completed overrun and keeps remaining outlook separate',()=>{
  const html=render({...closed,state:'current',actual:{...closed.actual,status:'partial'},outlook:{amount:'35.00',runId:'latest-run',issuedAt:'2026-10-09T00:00:00Z',start:'2026-10-09',endExclusive:'2026-10-12',partial:true}});
  assert.match(html,/Spend so far/); assert.match(html,/Week in progress/);
  assert.match(html,/Forecast remaining/); assert.match(html,/\$35/); assert.match(html,/\$100\.25/);
  assert.doesNotMatch(html,/\$20\.50 over forecast/);
});

test('missing original forecast stays unavailable and usage link retains selected scope and exact week',()=>{
  const html=render({...closed,priorForecast:null,variance:{amount:null,status:'unavailable',reason:'No forecast was saved before this week.'}});
  assert.match(html,/No forecast was saved before this week/);
  assert.match(html,/scope_type=team/); assert.match(html,/scope_id=research/);
  assert.match(html,/start_date=2026-10-05/); assert.match(html,/end_date_exclusive=2026-10-12/);
  assert.match(html,/metric=spend/);
});

test('unmatched forecast periods and incomplete actuals cannot display overrun',()=>{
  assert.doesNotMatch(render({...closed,priorForecast:{...prior,endExclusive:'2026-10-11'}}),/\$20\.50 over forecast/);
  assert.doesNotMatch(render({...closed,actual:{...closed.actual,status:'pending'}}),/\$20\.50 over forecast/);
});

test('a supplied variance cannot cross dataset identities',()=>{
  const html=render({...closed,actual:{...closed.actual,datasetId:'different-dataset'}});
  assert.doesNotMatch(html,/\$20\.50 over forecast/);
});

test('zero verified actuals are shown as zero and future actuals are not invented',()=>{
  const zero=render({...closed,actual:{...closed.actual,amount:'0.00'},priorForecast:{...prior,amount:'0.00'},variance:{status:'available',amount:'0.00',reason:null}});
  assert.match(zero,/\$0\.00/); assert.match(zero,/Matched the original forecast/);
  const future=render({...closed,state:'future',actual:{...closed.actual,status:'future',amount:null},variance:{status:'unavailable',amount:null,reason:null}});
  assert.match(future,/Not started/); assert.doesNotMatch(future,/\$20\.50 over forecast/);
});

test('Monday 00:00 UTC issuance qualifies and a forecast issued after the boundary does not',()=>{
  const atStart=render({...closed,priorForecast:{...prior,issuedAt:'2026-10-05T00:00:00Z',informationCutoff:'2026-10-05T00:00:00Z'}});
  assert.match(atStart,/\$20\.50 over forecast/);
  const afterStart=render({...closed,priorForecast:{...prior,issuedAt:'2026-10-05T00:00:00.001Z'}});
  assert.doesNotMatch(afterStart,/\$20\.50 over forecast/);
});

test('future week leads with exact full-week outlook and otherwise falls back to saved forecast',()=>{
  const future={...closed,state:'future',actual:{...closed.actual,status:'future',amount:null},outlook:{amount:'300.00',runId:'future-outlook',datasetId:'demo',issuedAt:'2026-10-04T18:00:00Z',informationCutoff:'2026-10-04T12:00:00Z',start:closed.start,endExclusive:closed.endExclusive,partial:false},variance:{status:'unavailable',amount:null,reason:null}};
  const latest=render(future);
  assert.match(latest,/Forecast<\/dt><dd[^>]*>\$300\.00<\/dd>/);
  assert.doesNotMatch(latest,/Original forecast<\/dt>/);
  assert.doesNotMatch(latest,/aria-label="Latest outlook"/);
  const noOutlook=render({...future,outlook:null});
  assert.match(noOutlook,/Forecast<\/dt><dd[^>]*>\$100\.25<\/dd>/);
  const partial=render({...future,outlook:{...future.outlook,start:'2026-10-08',partial:true}});
  assert.match(partial,/Forecast<\/dt><dd[^>]*>\$100\.25<\/dd>/);
  assert.match(partial,/Forecast remaining/);
});

test('native envelope identity does not suppress matching actual and forecast source datasets',()=>{
  const nativeHistory={datasetId:'forecast-weekly:northstar'};
  const native={...closed,actual:{...closed.actual,datasetId:'forecast-targets:northstar'},priorForecast:{...prior,datasetId:'forecast-targets:northstar'}};
  assert.match(render(native,nativeHistory),/\$20\.50 over forecast/);
  const future={...native,state:'future',actual:{...native.actual,status:'future',amount:null},outlook:{amount:'300.00',runId:'future-outlook',datasetId:'forecast-targets:northstar',issuedAt:'2026-10-04T18:00:00Z',informationCutoff:'2026-10-04T12:00:00Z',start:closed.start,endExclusive:closed.endExclusive,partial:false}};
  assert.match(render(future,nativeHistory),/Forecast<\/dt><dd[^>]*>\$300\.00<\/dd>/);
});

test('current week leads with latest exact full-week forecast while original stays in details',()=>{
  const current={...closed,state:'current',actual:{...closed.actual,status:'partial'},outlook:{amount:'200000.00',runId:'current-outlook',datasetId:'forecast-targets:northstar',issuedAt:'2026-10-09T00:00:00Z',informationCutoff:'2026-10-09T00:00:00Z',start:closed.start,endExclusive:closed.endExclusive,partial:false}};
  const html=render(current,{datasetId:'forecast-weekly:northstar'});
  assert.match(html,/Latest forecast<\/dt><dd[^>]*>\$200,000\.00<\/dd>/);
  assert.match(html,/Original forecast amount \(exact\)<\/dt><dd[^>]*>USD 100\.25<\/dd>/);
  assert.doesNotMatch(html,/\$20\.50 over forecast/);
});

test('details preserve exact decimal values and explain rounded displayed comparisons',()=>{
 const html=render({...closed,actual:{...closed.actual,amount:'167.755'},priorForecast:{...prior,amount:'162.290'},variance:{amount:'5.465',status:'available',reason:null}});
 assert.match(html,/USD 167\.755/);assert.match(html,/USD 162\.290/);assert.match(html,/USD 5\.465/);
 assert.match(html,/may differ by a cent from subtracting rounded amounts/);
});


test('week detail uses neutral dataset copy without losing missing-input warnings or exact values',()=>{
  const week={...closed,actual:{...closed.actual,status:'partial',revision:'synthetic-revision',sourceRefs:['synthetic-observed-outcome:research:2026-10-05']},priorForecast:{...prior,runId:'synthetic-weekly-v1:research',targetId:'demo-target:research'},variance:{amount:null,status:'unavailable',reason:'Inputs are incomplete; some actuals are still missing.'}};
  const html=render(week,{actualsRevision:'fixture-revision'});
  assert.doesNotMatch(html,/demo|scripted|synthetic|fixture|verified/i);
  assert.match(html,/some actuals are still missing/i);
  assert.match(html,/USD 120\.75/);
  assert.match(html,/Source record 1/);
});
