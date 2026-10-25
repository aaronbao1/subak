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
let RequestReview;
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
  ({RequestReview}=require(path.join(frontend,'src/components/requests/request-review.tsx')));
} finally {
  Module._resolveFilename=originalResolve; Module._load=originalLoad;
  for(const ext of ['.ts','.tsx']) {if(extensions[ext])require.extensions[ext]=extensions[ext];else delete require.extensions[ext];}
}
const request={id:'request-1',clientRequestId:'client-1',teamId:'research',title:'Evaluation capacity',requestKind:'project',projectName:'Benchmark expansion',narrative:'Please allocate $50.25 for the added evaluation batch.',requestedAmount:'50.25',unit:'USD',periodStart:'2026-10-19',periodEndExclusive:'2026-10-26',sourceRef:null,evidenceRefs:[{kind:'document',id:'source-1'}],period:{id:'week-1',startDate:'2026-10-19',endDateExclusive:'2026-10-26',label:'Week of Oct 19'},source:{reference:null,submittedBy:'Finance',submittedAt:'2026-10-25T12:00:00Z'},status:'submitted',linkedProposalIds:[],decisionIds:[],approvedAmount:'0.00',remainingRequestedAmount:'50.25',assessment:{assessedAt:'2026-10-25T12:00:00Z',budgetVersion:1,envelopeTotal:'200000.00',teamAllocation:'60000.00',recordedSpend:'45000.00',forecastAmount:'85000.00',forecastRunId:'issued-1',forecastStatus:'available',forecastUnit:'USD',forecastBasis:'full_period_total',projectedHeadroom:'-25000.00',requestedAllocation:'60050.25',availableDonors:[{teamId:'product',headroom:'30000.00'}],qualification:'The request has not been added to this forecast.',amountIncludedInForecast:false}};
const render=(item=request,extra={})=>renderToStaticMarkup(React.createElement(RequestReview,{request:item,teamName:'Research',onClose(){},onPrepare(){},...extra}));
const findElement=(node,predicate)=>{
  if(!React.isValidElement(node)) return undefined;
  if(predicate(node)) return node;
  for(const child of React.Children.toArray(node.props.children)) {const found=findElement(child,predicate);if(found)return found;}
};

test('request review keeps exact requested amount distinct from forecast and budget assessment',()=>{
  const html=render();
  assert.match(html,/Requested amount/);assert.match(html,/\$50\.25/);assert.match(html,/Requested/);
  assert.match(html,/\$60,000\.00/);assert.match(html,/\$85,000\.00/);assert.match(html,/-\$25,000\.00/);
  assert.match(html,/The request has not been added to this forecast/);
  assert.match(html,/Prepare allocation review/);
});

test('unspecified request amount stays unspecified and cannot prepare funding',()=>{
  const missing={...request,requestedAmount:null,remainingRequestedAmount:null};
  const html=render(missing);
  assert.match(html,/Not specified/);
  let prepared;
  const tree=RequestReview({request:missing,teamName:'Research',onClose(){},onPrepare(value){prepared=value;}});
  const action=findElement(tree,node=>node.props.children==='Prepare allocation review');
  assert.equal(action,undefined); assert.equal(prepared,undefined);
  assert.match(html,/No funding amount specified\. This update remains planning context/);
  assert.match(html,/>Update<\/span>/);
  assert.doesNotMatch(html,/Enter the amount when preparing/);
});

test('partial funding exposes original approved and remaining amounts without claiming full approval',()=>{
  const html=render({...request,status:'partially_funded',approvedAmount:'20.00',remainingRequestedAmount:'30.25',linkedProposalIds:['proposal-1']});
  assert.match(html,/Partially funded/);assert.match(html,/Approved amount/);assert.match(html,/\$20\.00/);assert.match(html,/Still requested/);assert.match(html,/\$30\.25/);
});

test('approved or rejected requests cannot prepare another allocation review from this sheet',()=>{
  const approved=render({...request,status:'approved_applied',approvedAmount:'50.25',remainingRequestedAmount:'0.00'});
  assert.match(approved,/Approved/);assert.doesNotMatch(approved,/Prepare allocation review/);
  const rejected=render({...request,status:'rejected'});
  assert.match(rejected,/Rejected/);assert.doesNotMatch(rejected,/Prepare allocation review/);
});

test('source narrative and linked proposals stay separate and unavailable forecast stays unavailable',()=>{
  const html=render({...request,status:'pending_review',linkedProposalIds:['proposal-1'],assessment:{...request.assessment,forecastAmount:null,forecastStatus:'unavailable',projectedHeadroom:null,qualification:'No matching forecast for this period.'}}, {onReviewProposal(){}});
  assert.match(html,/Drafted/);assert.match(html,/Related allocation review/);assert.match(html,/Source and assessment details/);assert.match(html,/No matching forecast for this period/);
  assert.doesNotMatch(html,/\$85,000\.00/);
});

test('a drafted request opens its latest existing review and does not prepare a duplicate draft',()=>{
  const drafted={...request,status:'pending_review',linkedProposalIds:['proposal-older','proposal-latest']};
  let reviewed;
  const tree=RequestReview({request:drafted,teamName:'Research',onClose(){},onPrepare(){throw new Error('Unexpected duplicate draft');},onReviewProposal(id){reviewed=id;}});
  const action=findElement(tree,node=>node.props.children==='Review draft');
  assert.ok(action); action.props.onClick(); assert.equal(reviewed,'proposal-latest');
  const html=render(drafted,{onReviewProposal(){}});
  assert.match(html,/Drafted/);assert.doesNotMatch(html,/Prepare allocation review/);
});

test('related proposal loading failures are visible inside the request sheet',()=>{
  const html=render({...request,status:'pending_review',linkedProposalIds:['proposal-1']},{error:'The allocation review could not load. Try opening it again.',onReviewProposal(){}});
  assert.match(html,/role="alert"/);
  assert.match(html,/The allocation review could not load/);
});

test('missing assessment numbers and a pending request without a draft never invent zero or a ready draft',()=>{
  const html=render({...request,status:'pending_review',assessment:{...request.assessment,budgetVersion:null,envelopeTotal:null,teamAllocation:null,recordedSpend:null,forecastAmount:null,forecastStatus:'unavailable',projectedHeadroom:null}});
  assert.match(html,/Awaiting review/);assert.doesNotMatch(html,/Drafted/);assert.doesNotMatch(html,/\$0\.00/);
  assert.match(html,/Unavailable/);assert.doesNotMatch(html,/Prepare allocation review/);
});

test('only a positive finite remaining request can prepare an allocation review',()=>{
  for(const remaining of [null,'0.00','-10.00','NaN','Infinity']) {
    assert.doesNotMatch(render({...request,remainingRequestedAmount:remaining}),/Prepare allocation review/);
  }
  assert.doesNotMatch(render({...request,requestedAmount:null}),/Prepare allocation review/);
  assert.match(render({...request,remainingRequestedAmount:'0.01'}),/Prepare allocation review/);
});

test('unspecified amounts can create a separate budget request without funding or editing the source',()=>{
  const missing={...request,requestedAmount:null,remainingRequestedAmount:null};
  let created;
  const props={request:missing,teamName:'Research',onClose(){},onPrepare(){throw new Error('Funding must stay unavailable');},onCreateBudgetRequest(original){created=original;}};
  const action=findElement(RequestReview(props),node=>node.props.children==='Create budget request');
  assert.ok(action); action.props.onClick(); assert.equal(created,missing);
  const html=render(missing,{onCreateBudgetRequest(){}});
  assert.match(html,/Create budget request/); assert.doesNotMatch(html,/Prepare allocation review/);
});

test('a positive explicit remaining request only hands the unchanged request to prepare callback',()=>{
  let prepared;
  const action=findElement(RequestReview({request,teamName:'Research',onClose(){},onPrepare(original){prepared=original;}}),node=>node.props.children==='Prepare allocation review');
  assert.ok(action); action.props.onClick(); assert.equal(prepared,request);
});

test('full assessment moves to disclosure while coverage and stale warnings stay visible',()=>{
  const qualification='Recorded spend is a subtotal with incomplete source coverage. The issued forecast is stale because its source inputs changed; publish a new forecast before relying on headroom.';
  const html=render({...request,assessment:{...request.assessment,forecastStatus:'unavailable',forecastAmount:null,projectedHeadroom:null,qualification}});
  const visible=html.split('<details')[0];
  assert.match(visible,/Recorded spend has incomplete coverage/);
  assert.match(visible,/Forecast is stale; update it before using headroom/);
  assert.match(visible,/Funding request is separate from expected spend/);
  assert.doesNotMatch(visible,/The issued forecast is stale because/);
  assert.ok(html.slice(html.indexOf('<details')).includes(qualification));
});
test('unknown attribution offers a separate funding request without promising to fix the prior decision',()=>{
  const html=render({...request,remainingRequestedAmount:null},{onCreateBudgetRequest(){}});
  assert.match(html,/Funding attribution needs review/);assert.match(html,/Create separate funding request/);
  assert.doesNotMatch(html,/Prepare allocation review/);
});


test('request source names and quoted domain language remain exact while generated references stay neutral',()=>{
  const narrative='Synthetic biology researchers need test fixtures; “demo data” is a quoted customer phrase.';
  const source={...request.source,reference:'synthetic-biology-notes',submittedBy:'Demo Anderson'};
  const item={...request,title:'Synthetic biology capacity',projectName:'Test fixtures',narrative,sourceRef:'Product demo notes',source,evidenceRefs:[{kind:'document',id:'synthetic-source-1',note:'The source says “test fixtures”.'}],id:'mock-request:finance-demo:1',assessment:{...request.assessment,forecastRunId:'synthetic-ui-run-1'}};
  const before=structuredClone(item);
  const html=render(item);
  assert.ok(html.includes(narrative));
  assert.ok(html.includes('Synthetic biology capacity'));
  assert.ok(html.includes('Test fixtures'));
  assert.ok(html.includes('synthetic-biology-notes'));
  assert.ok(html.includes('Product demo notes'));
  assert.ok(html.includes('Demo Anderson'));
  assert.ok(html.includes('The source says “test fixtures”.'));
  assert.doesNotMatch(html,/synthetic-source-1|synthetic-ui-run-1|mock-request:finance-demo:1/);
  assert.deepEqual(item,before);
  const generated=render({...request,source:{...source,reference:'budget-request:mock-request:finance-demo:1',submittedBy:'finance-demo'}});
  assert.doesNotMatch(generated,/finance-demo|budget-request:mock-request/);
  assert.match(generated,/Saved source/);
  const generatedSource=render({...request,source:{...source,reference:'synthetic-source-1'}});
  assert.doesNotMatch(generatedSource,/synthetic-source-1/);
  assert.match(generatedSource,/Saved source/);
});
