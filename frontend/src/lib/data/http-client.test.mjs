import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { stripTypeScriptTypes } from 'node:module';
const weeklySource=stripTypeScriptTypes(fs.readFileSync(new URL('./weekly-history.ts',import.meta.url),'utf8'));
const weeklyUrl=`data:text/javascript;base64,${Buffer.from(weeklySource).toString('base64')}`;
const requestSource=stripTypeScriptTypes(fs.readFileSync(new URL('./budget-requests.ts',import.meta.url),'utf8'));
const requestUrl=`data:text/javascript;base64,${Buffer.from(requestSource).toString('base64')}`;
const forecastSource=stripTypeScriptTypes(fs.readFileSync(new URL('./forecast-dashboard.ts',import.meta.url),'utf8'));
const forecastUrl=`data:text/javascript;base64,${Buffer.from(forecastSource).toString('base64')}`;
const source=stripTypeScriptTypes(fs.readFileSync(new URL('./http-client.ts',import.meta.url),'utf8'),{mode:'transform'}).replace('from "./weekly-history"',`from ${JSON.stringify(weeklyUrl)}`).replace('from "./budget-requests"',`from ${JSON.stringify(requestUrl)}`).replace('from "./forecast-dashboard"',`from ${JSON.stringify(forecastUrl)}`);
const {HttpDataClient}=await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);
test('canonical transport keeps scope and immutable run identity exact',async()=>{
 const calls=[]; const original=globalThis.fetch;
 globalThis.fetch=async(url,init)=>{calls.push({url,init});return new Response(JSON.stringify({views:[]}));};
 try {
  const client=new HttpDataClient('http://fixture.invalid');
  await client.getForecastViews({scope_type:'person',scope_id:'person / 1',run_id:'run-7'});
  const q=new URL(calls[0].url).searchParams;
  assert.equal(q.get('scope_type'),'person');assert.equal(q.get('scope_id'),'person / 1');assert.equal(q.get('run_id'),'run-7');
  assert.equal(q.get('compact'),'true');
  assert.equal(calls[0].init.cache,'no-store');
 }finally{globalThis.fetch=original;}
});
test('forecast transport hydrates compact drivers before exposing a full replacement scenario input',async()=>{
 const original=globalThis.fetch;
 const driver={id:'driver-1',parameters:{amount:'1.00000000001'},citations:[{quote:'Exact source quote',source_id:'source-1'}],extra:{untouched:true}};
 globalThis.fetch=async()=>new Response(JSON.stringify({transport:'forecast-dashboard-v1',driver_pool:{d0:driver},views:[{run_id:'r1',included_driver_refs:['d0'],queued_change_refs:[]}]}));
 try {
  const client=new HttpDataClient('http://fixture.invalid');
  const result=await client.getForecastViews();
  assert.deepEqual(result,{views:[{run_id:'r1',included_drivers:[driver],queued_changes:[]}]});
  globalThis.fetch=async()=>new Response(JSON.stringify({transport:'forecast-dashboard-v1',driver_pool:{},views:[{included_driver_refs:['missing']}]}));
  await assert.rejects(client.getForecastViews(),/driver reference/i);
 }finally{globalThis.fetch=original;}
});
test('refresh uses idempotency header; scenario and Ask Droid retain issued ids',async()=>{
 const calls=[];const original=globalThis.fetch;
 globalThis.fetch=async(url,init)=>{calls.push({url,init});return new Response('{}');};
 try {
  const client=new HttpDataClient('http://fixture.invalid');
  await client.refreshForecast('operation-123');
  assert.equal(calls[0].init.headers['Idempotency-Key'],'operation-123');
  await client.previewForecastScenario('issued / 7',[]);
  assert.match(calls[1].url,/forecast-runs\/issued%20%2F%207\/scenarios$/);
  assert.deepEqual(JSON.parse(calls[1].init.body),{drivers:[]});
  const context={action:'explain',run_id:'issued-7',scope_type:'team',scope_id:'t1',driver_id:'d1'};
  await client.sendMessage('main','Explain this',context);
  assert.deepEqual(JSON.parse(calls[2].init.body),{content:'Explain this',forecast_context:context});
 }finally{globalThis.fetch=original;}
});

test('chat transports stable request identity, selected revision, and read-only reconciliation',async()=>{
 const calls=[];const original=globalThis.fetch;
 globalThis.fetch=async(url,init)=>{calls.push({url,init});return new Response(JSON.stringify({status:'completed',messages:[]}));};
 try {
  const client=new HttpDataClient('http://fixture.invalid');
  const context={intent:'allocation',selected_proposal_id:'proposal-1',selected_proposal_version:2};
  await client.sendMessage('main','Make it $50',undefined,{clientMessageId:'request-1',conversationContext:context});
  assert.deepEqual(JSON.parse(calls[0].init.body),{content:'Make it $50',client_message_id:'request-1',conversation_context:context});
  await client.reconcileMessage('main','request / 1');
  assert.match(calls[1].url,/threads\/main\/messages\/request%20%2F%201$/);assert.equal(calls[1].init.method,undefined);
 }finally{globalThis.fetch=original;}
});
test('transport distinguishes explicit refusal from an uncertain server failure',async()=>{
 const original=globalThis.fetch;
 try {
  const client=new HttpDataClient('http://fixture.invalid');
  globalThis.fetch=async()=>new Response(JSON.stringify({detail:'Stale proposal'}),{status:409});
  await assert.rejects(client.applyProposal('p1'),e=>e.definiteFailure===true);
  globalThis.fetch=async()=>new Response(JSON.stringify({detail:'Gateway error'}),{status:502});
  await assert.rejects(client.applyProposal('p1'),e=>e.definiteFailure===false);
 }finally{globalThis.fetch=original;}
});

test('weekly history transport sends bounded scoped query and retains exact decimal outcomes',async()=>{
 const calls=[];const original=globalThis.fetch;
 globalThis.fetch=async(url,init)=>{calls.push({url,init});return new Response(JSON.stringify({scope:{type:'company',id:'northstar'},start_date:'2026-10-19',end_date_exclusive:'2026-10-26',timezone:'UTC',unit:'USD',basis:'planning',quantity:'spend',dataset_id:'weekly:northstar',as_of:'2026-10-25T12:00:00Z',synthetic:true,actuals_revision:'actual-r1',selection_policy:'latest_published_before_week_start',notes:[],weeks:[{start:'2026-10-19',end_exclusive:'2026-10-26',state:'current',actual:{amount:'95000.00000001',status:'partial',source:'repository_ledger',dataset_id:'ledger',revision:'1',corrected:false,source_refs:[]},prior_forecast:null,outlook:null,variance:{amount:null,status:'unavailable',reason:'Week is open'}}]}));};
 try {
  const client=new HttpDataClient('http://fixture.invalid');
  const result=await client.getWeeklyForecastHistory({scopeType:'company',scopeId:'northstar',startDate:'2026-10-19',endDateExclusive:'2026-10-26'});
  const params=new URL(calls[0].url).searchParams;assert.equal(params.get('scope_type'),'company');assert.equal(params.get('scope_id'),'northstar');assert.equal(params.get('start_date'),'2026-10-19');assert.equal(params.get('end_date_exclusive'),'2026-10-26');
  assert.equal(calls[0].init.cache,'no-store');assert.equal(result.weeks[0].actual.amount,'95000.00000001');assert.equal(result.weeks[0].variance.amount,null);
  await assert.rejects(client.getWeeklyForecastHistory({scopeType:'company',startDate:'2026-10-20',endDateExclusive:'2026-10-26'}));assert.equal(calls.length,1);
 }finally{globalThis.fetch=original;}
});

test('manual and request drafts preserve durable receipt without coupling to a followup detail read',async()=>{
 const calls=[];const original=globalThis.fetch;
 globalThis.fetch=async(url,init)=>{calls.push({url,init});return new Response(JSON.stringify({id:'native-p1'}));};
 try {
  const client=new HttpDataClient('http://fixture.invalid');
  assert.deepEqual(await client.prepareAllocationProposal({baseVersion:3,periodStart:'2026-10-19',periodEndExclusive:'2026-10-26',unit:'USD',allocations:{research:'0.0000000001'},rationale:'Review'},'stable key'),{proposalId:'native-p1'});
  assert.equal(calls.length,1);assert.equal(calls[0].init.headers['Idempotency-Key'],'stable key');assert.equal(JSON.parse(calls[0].init.body).allocations.research,'0.0000000001');
  assert.deepEqual(await client.reconcileAllocationProposal('stable / key'),{proposalId:'native-p1'});assert.match(calls[1].url,/allocation-drafts\/stable%20%2F%20key$/);assert.equal(calls[1].init.method,undefined);
  globalThis.fetch=async()=>new Response('{}',{status:404});assert.equal(await client.reconcileAllocationProposal('absent'),undefined);
 }finally{globalThis.fetch=original;}
});
test('budget request submission carries stable request ID and explicit null amount',async()=>{
 const original=globalThis.fetch;let body;
 globalThis.fetch=async(url,init)=>{body=JSON.parse(init.body);return new Response(JSON.stringify({detail:'No budget'}),{status:422});};
 try {const client=new HttpDataClient('http://fixture.invalid');await assert.rejects(client.ingestTeamUpdate({clientRequestId:'r1',teamId:'research',title:'Update',requestKind:'team',narrative:'Need $50 eventually',requestedAmount:null,unit:'USD',periodStart:'2026-10-19',periodEndExclusive:'2026-10-26'}),e=>e.definiteFailure===true);assert.equal(body.requested_amount,null);assert.equal(body.client_request_id,'r1');}
 finally{globalThis.fetch=original;}
});

test('native request error envelopes expose the meaningful message and definite refusal',async()=>{
 const original=globalThis.fetch;globalThis.fetch=async()=>new Response(JSON.stringify({error:{code:'stale_budget',message:'The approved allocation changed; review again.',details:{}}}),{status:409});
 try{await assert.rejects(new HttpDataClient('http://fixture.invalid').prepareAllocationProposal({},'key'),error=>error.message==='The approved allocation changed; review again.'&&error.definiteFailure===true);}finally{globalThis.fetch=original;}
});

test('request-linked draft carries the chosen action and recovers the saved native proposal receipt',async()=>{
 const original=globalThis.fetch;const calls=[];
 const request={id:'request / 1',client_request_id:'intake-1',team_id:'research',title:'Review',request_kind:'team',narrative:'Explicit request',requested_amount:'50.25',unit:'USD',period_start:'2026-10-19',period_end_exclusive:'2026-10-26',evidence_refs:[],period:{id:'p',label:'Week',start_date:'2026-10-19',end_date_exclusive:'2026-10-26'},source:{reference:null,submitted_by:'actor',submitted_at:'now'},status:'pending_review',linked_proposal_ids:['p1'],decision_ids:[],approved_amount:'0',remaining_requested_amount:'50.25',assessment:{assessed_at:'now',budget_version:1,envelope_total:'200000',team_allocation:'60000',recorded_spend:'100',forecast_amount:null,forecast_run_id:null,forecast_status:'unavailable',forecast_unit:'USD',forecast_basis:'full_period_total',projected_headroom:null,requested_allocation:'60050.25',available_donors:[],qualification:'No forecast',amount_included_in_forecast:false}};
 globalThis.fetch=async(url,init)=>{calls.push({url,init});return new Response(JSON.stringify({request,proposal:{id:'p1',status:'pending_review'}}));};
 try{const value=await new HttpDataClient('http://fixture.invalid').prepareBudgetRequestDraft('request / 1',{baseVersion:1,actionType:'transfer',sourceTeamId:'product'},'request-draft-key');assert.equal(value.proposalId,'p1');assert.equal(value.request.requestedAmount,'50.25');assert.equal(value.request.status,'pending_review');assert.match(calls[0].url,/budget-requests\/request%20%2F%201\/draft$/);assert.equal(calls[0].init.headers['Idempotency-Key'],'request-draft-key');assert.deepEqual(JSON.parse(calls[0].init.body),{base_version:1,action_type:'transfer',source_team_id:'product'});assert.equal(calls.length,1);}finally{globalThis.fetch=original;}
});
