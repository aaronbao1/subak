import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import Module,{createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../../..');const require=createRequire(path.join(root,'package.json'));const React=require('react');const {renderToStaticMarkup}=require('react-dom/server');const ts=require('typescript');
let state;const hook=()=>state;hook.getState=()=>state;
const resolve=Module._resolveFilename,load=Module._load,extensions=Object.fromEntries(['.ts','.tsx'].map(ext=>[ext,require.extensions[ext]]));let AssistantDrawer;
try{
 Module._resolveFilename=function(request,parent,...rest){return resolve.call(this,request.startsWith('@/')?path.join(root,'src',request.slice(2)):request,parent,...rest)};
 Module._load=function(request,parent,...rest){
  if(request==='@/lib/store')return {useAppStore:hook};
  if(request==='@/components/allocation/proposal-review')return {ProposalReview:()=>null};
  if(request==='@/components/team/source-sheet')return {SourceSheet:()=>null};
  if(request==='@/components/ui/sheet'){const part=tag=>function SheetPart({children}){return React.createElement(tag,null,children)};return {Sheet:({open,children})=>open?React.createElement('div',null,children):null,SheetContent:part('aside'),SheetHeader:part('header'),SheetTitle:part('h2'),SheetDescription:part('p')}}
  return load.call(this,request,parent,...rest);
 };
 for(const ext of ['.ts','.tsx'])require.extensions[ext]=(module,filename)=>module._compile(ts.transpileModule(fs.readFileSync(filename,'utf8'),{fileName:filename,compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}}).outputText,filename);
 ({AssistantDrawer}=require(path.join(root,'src/components/assistant/assistant-drawer.tsx')));
}finally{Module._resolveFilename=resolve;Module._load=load;for(const ext of ['.ts','.tsx'])if(extensions[ext])require.extensions[ext]=extensions[ext];else delete require.extensions[ext]}
const noop=()=>{};
const base={assistantOpen:true,setAssistantOpen:noop,threads:{main:[]},sendMessage:noop,proposals:[],teams:[{id:'research',name:'Research'}],people:[],company:{name:'Northstar',currentPeriod:{start:'2026-10-19',end:'2026-10-25',label:'Current week'}},composer:'New draft remains here',setComposer:noop,loaded:true,loadState:'ready',composerFocus:0,clearAssistantContext:noop,setAssistantIntent:noop,reconcileMessage:noop,optionalErrors:{},retryOptional:noop,requests:[],requestState:'ready',proposalActions:{}};
const render=extra=>{state={...base,...extra};return renderToStaticMarkup(React.createElement(AssistantDrawer))};
test('drawer uses Droid Assistant identity and keeps pending recovery and a newer composer draft visible',()=>{const html=render({threads:{main:[{id:'pending',threadId:'main',role:'user',createdAt:'2026-10-25T12:00:00Z',content:'Earlier request',delivery:'unknown',clientMessageId:'stable'}]}});assert.match(html,/Droid Assistant/);assert.match(html,/Message Droid Assistant/);assert.match(html,/Check status/);assert.match(html,/New draft remains here/);assert.match(html,/Budget changes require your review and approval/)});
test('current request context is scoped to the current period and never relabels it approved',()=>{const request={id:'request-1',teamId:'research',title:'New evaluation work',status:'submitted',periodStart:'2026-10-19',periodEndExclusive:'2026-10-26',remainingRequestedAmount:'50.25'};const html=render({requests:[request,{...request,id:'old',title:'Past request',periodStart:'2026-10-12',periodEndExclusive:'2026-10-19'},{...request,id:'done',title:'Closed request',status:'approved_applied'}]});assert.match(html,/1 open team request/);assert.match(html,/\$50\.25 requested/);assert.match(html,/requests\?request=request-1/);assert.doesNotMatch(html,/Past request|Closed request/)});
test('unsized request remains a clarification need and failed history remains retryable',()=>{const html=render({optionalErrors:{assistant:'offline'},requests:[{id:'update',teamId:'research',title:'Unsized update',status:'submitted',periodStart:'2026-10-19',periodEndExclusive:'2026-10-26',remainingRequestedAmount:null}]});assert.match(html,/Amount needed/);assert.match(html,/Earlier messages are unavailable/);assert.match(html,/Try again/);assert.doesNotMatch(html,/\$0\.00 requested/)});

test('missing request context is explicit instead of implying that no requests exist',()=>{const html=render({requestState:'error'});assert.match(html,/Team request context is unavailable/);assert.match(html,/href="\/requests"/)});

test('selected draft period scopes request context instead of borrowing the current company week',()=>{const request={id:'old-request',teamId:'research',title:'Earlier period request',status:'submitted',periodStart:'2026-10-12',periodEndExclusive:'2026-10-19',remainingRequestedAmount:'75'};const html=render({conversationContext:{selected_proposal_id:'older'},proposals:[{id:'older',period:{start:'2026-10-12',end:'2026-10-18'},version:1}],requests:[request,{...request,id:'current-request',title:'Current period request',periodStart:'2026-10-19',periodEndExclusive:'2026-10-26'}]});assert.match(html,/Earlier period request/);assert.doesNotMatch(html,/Current period request/)});
