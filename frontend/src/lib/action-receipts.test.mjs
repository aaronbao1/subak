import test from 'node:test';
import assert from 'node:assert/strict';
import {makeStore,fixtureClient,deferred} from './store-test-helper.mjs';
const proposal={id:'p1',status:'proposed',kind:'redistribute',unit:'usd',lines:[{teamId:'t1',before:500,after:450},{teamId:'t2',before:500,after:550}],totalBefore:1000,totalAfter:1000,createdAt:'2026-10-25T12:00:00Z',rationale:'Move $50',citations:[],period:{start:'2026-10-19',end:'2026-10-25'},version:2};
const receipt={id:'d1',proposalId:'p1',action:'applied',kind:'redistribute',unit:'usd',lines:proposal.lines,appliedAt:'2026-10-25T12:01:00Z',appliedBy:'Finance'};
test('confirmed apply survives repeated totals-refresh failures and later recovery',async()=>{
 const client=fixtureClient();let applications=0;client.applyProposal=async()=>{applications++;return receipt;};
 client.getBudgets=async()=>{throw new Error('Totals offline');};
 const store=await makeStore(client);store.setState({proposals:[proposal]});
 assert.deepEqual(await store.getState().applyProposal('p1'),receipt);
 assert.equal(store.getState().proposalActions.p1.mutation,'confirmed');
 assert.equal(store.getState().proposalActions.p1.sync,'failed');
 assert.equal(store.getState().proposals[0].status,'applied');
 assert.deepEqual(store.getState().decisions,[receipt]);
 assert.equal(await store.getState().refreshBudgets(),false);
 assert.equal(store.getState().proposalActions.p1.mutation,'confirmed');
 assert.deepEqual(await store.getState().applyProposal('p1'),receipt);assert.equal(applications,1);
 client.getBudgets=async()=>[{teamId:'t1',allocated:450},{teamId:'t2',allocated:550}];
 assert.equal(await store.getState().refreshBudgets(),true);
 assert.equal(store.getState().proposalActions.p1.sync,'synced');
 assert.deepEqual(store.getState().decisions,[receipt]);
});
test('timeout after acceptance reconciles the receipt without repeating mutation',async()=>{
 const client=fixtureClient();let applications=0;
 client.applyProposal=async()=>{applications++;throw new TypeError('Connection lost');};
 client.getDecisions=async()=>[receipt];
 const store=await makeStore(client);store.setState({proposals:[proposal]});
 assert.deepEqual(await store.getState().applyProposal('p1'),receipt);
 assert.equal(store.getState().proposalActions.p1.mutation,'confirmed');assert.equal(applications,1);
});
test('unknown apply outcome blocks repetition and read-only reconciliation retains uncertainty',async()=>{
 const client=fixtureClient();let applications=0;
 client.applyProposal=async()=>{applications++;throw new TypeError('Connection lost');};
 client.getDecisions=async()=>{throw new Error('Lookup offline');};
 const store=await makeStore(client);store.setState({proposals:[proposal]});
 await assert.rejects(store.getState().applyProposal('p1'));
 assert.equal(store.getState().proposalActions.p1.mutation,'unknown');
 await store.getState().reconcileProposal('p1');
 assert.equal(store.getState().proposalActions.p1.mutation,'unknown');
 await assert.rejects(store.getState().applyProposal('p1'));assert.equal(applications,1);
 client.getDecisions=async()=>[receipt];
 assert.deepEqual(await store.getState().reconcileProposal('p1'),receipt);
 assert.equal(store.getState().proposalActions.p1.mutation,'confirmed');
});
test('core data loads when optional assistant/history fails, and a failed reload preserves spending',async()=>{
 const client=fixtureClient();client.getThread=async()=>{throw new Error('Thread offline');};
 client.getDecisions=async()=>{throw new Error('History offline');};
 client.getSpending=async()=>[{id:'s1',date:'2026-10-20',amount:12}];
 const store=await makeStore(client);await store.getState().load();
 assert.equal(store.getState().loaded,true);assert.equal(store.getState().loadState,'ready');
 assert.equal(store.getState().spending[0].amount,12);assert.match(store.getState().optionalErrors.assistant,/offline/);
 client.getSpending=async()=>{throw new Error('Spending offline');};await store.getState().load();
 assert.equal(store.getState().loadState,'stale');assert.equal(store.getState().spending[0].amount,12);
});
test('initial load failure has a recoverable error state',async()=>{
 const client=fixtureClient();client.getCompany=async()=>{throw new Error('Offline');};
 const store=await makeStore(client);await store.getState().load();
 assert.equal(store.getState().loadState,'error');assert.equal(store.getState().loaded,false);
 client.getCompany=fixtureClient().getCompany;await store.getState().load();assert.equal(store.getState().loadState,'ready');
});
test('send appears immediately and a failed request preserves a newer composer draft',async()=>{
 const client=fixtureClient(), response=deferred();let options;
 client.sendMessage=(_thread,_content,_context,sentOptions)=>{options=sentOptions;return response.promise;};
 const store=await makeStore(client);store.setState({composer:'Move $50'});
 const sending=store.getState().sendMessage('main','Move $50');
 const pending=store.getState().threads.main[0];assert.equal(pending.content,'Move $50');assert.equal(pending.delivery,'sending');
 assert.ok(options.clientMessageId);assert.equal(store.getState().composer,'');
 store.getState().setComposer('My next question');response.reject(new TypeError('Connection lost'));await assert.rejects(sending);
 assert.equal(store.getState().composer,'My next question');assert.equal(store.getState().threads.main[0].delivery,'unknown');
});
test('reply identity deduplicates pending message and assistant refresh failure does not fail send',async()=>{
 const client=fixtureClient(), response=deferred();let options;
 client.sendMessage=(_thread,_content,_context,sentOptions)=>{options=sentOptions;return response.promise;};
 client.getBudgets=async()=>{throw new Error('Totals offline');};
 const store=await makeStore(client);const sending=store.getState().sendMessage('main','Explain');
 response.resolve([{id:'u1',threadId:'main',role:'user',content:'Explain',createdAt:'2026-10-25T12:00:00Z',clientMessageId:options.clientMessageId},{id:'a1',threadId:'main',role:'assistant',content:'Answer',createdAt:'2026-10-25T12:00:01Z'}]);
 await sending;assert.deepEqual(store.getState().threads.main.map(m=>m.id),['u1','a1']);
});
test('revise carries exact selected identity and an assistant clarification preserves pending slot',async()=>{
 const client=fixtureClient();let options;
 client.sendMessage=async(_thread,_content,_context,sendOptions)=>{options=sendOptions;return [{id:'a1',threadId:'main',role:'assistant',content:'How much?',createdAt:'2026-10-25T12:00:01Z',conversationContext:{intent:'allocation',selected_proposal_id:'p1',selected_proposal_version:2,pending_slot:'amount'}}];};
 const store=await makeStore(client);store.setState({proposals:[proposal]});store.getState().reviseProposal('p1');
 await store.getState().sendMessage('main','Make it bigger');assert.equal(options.conversationContext.selected_proposal_id,'p1');assert.equal(options.conversationContext.selected_proposal_version,2);
 assert.equal(store.getState().conversationContext.pending_slot,'amount');
});

test('an older dashboard reload cannot overwrite refreshed budgets after a confirmed apply',async()=>{
 const client=fixtureClient(),oldBudgets=deferred();let reads=0;
 client.getBudgets=()=>++reads===1?oldBudgets.promise:Promise.resolve([{teamId:'t1',allocated:450}]);
 client.applyProposal=async()=>receipt;
 const store=await makeStore(client);store.setState({proposals:[proposal]});
 const loading=store.getState().load();
 await store.getState().applyProposal('p1');
 assert.equal(store.getState().budgets[0].allocated,450);
 oldBudgets.resolve([{teamId:'t1',allocated:500}]);await loading;
 assert.equal(store.getState().budgets[0].allocated,450);
 assert.equal(store.getState().proposalActions.p1.mutation,'confirmed');
});
test('message reconciliation replaces uncertain delivery without creating another request',async()=>{
 const client=fixtureClient();let requestId;let sends=0;
 client.sendMessage=async(_t,_c,_f,options)=>{sends++;requestId=options.clientMessageId;throw new TypeError('Connection lost');};
 const store=await makeStore(client);await assert.rejects(store.getState().sendMessage('main','Add $50'));
 client.reconcileMessage=async(_t,id)=>{assert.equal(id,requestId);return {status:'completed',messages:[{id:'user1',clientMessageId:id,threadId:'main',role:'user',content:'Add $50',createdAt:'2026-10-25T12:00:00Z'},{id:'reply1',threadId:'main',role:'assistant',content:'Review draft',createdAt:'2026-10-25T12:00:01Z'}]};};
 await store.getState().reconcileMessage('main',requestId);
 assert.equal(sends,1);assert.deepEqual(store.getState().threads.main.map(m=>m.id),['user1','reply1']);
});

test('clearing visible context sends an explicit empty context instead of restoring backend pending slots',async()=>{
 const client=fixtureClient();let options;
 client.sendMessage=async(_t,_c,_f,sent)=>{options=sent;return [];};
 const store=await makeStore(client);store.setState({conversationContext:{intent:'allocation',selected_proposal_id:'p1',pending_slot:'amount'}});
 store.getState().clearAssistantContext();await store.getState().sendMessage('main','Why?');
 assert.deepEqual(options.conversationContext,{});
 store.setState({conversationContext:{intent:'allocation',selected_proposal_id:'p1'}});
 store.getState().askAssistant('Explain spending');await store.getState().sendMessage('main','Explain spending');
 assert.deepEqual(options.conversationContext,{});
});

test('dashboard load bounds compatibility spending to the selected planning period',async()=>{
 const client=fixtureClient();let received;
 client.getSpending=async(filter)=>{received=filter;return [];};
 const store=await makeStore(client);await store.getState().load();
 assert.deepEqual(received,{from:'2026-10-01',to:'2026-12-31'});
});

test('selected pinned plan date replies create and revise the same scenario card',async()=>{
 const client=fixtureClient();let sequence=0;
 client.sendMessage=async(_t,content)=>[{id:`reply${++sequence}`,threadId:'main',role:'assistant',content:'Preview a scenario',createdAt:`2026-10-25T12:00:0${sequence}Z`,conversationContext:{intent:'scenario',effective_date_text:content}}];
 const driver={id:'launch',kind:'project_schedule',title:'Research launch',scope:{project_id:'project1'},parameters:{from_start:'2026-10-20',from_end:'2026-11-03',to_start:'2026-10-27'}};
 const view={run_id:'issued-1',scope:{type:'company',id:'co'},included_drivers:[driver],daily:[],weekly:[],cumulative:[],queued_changes:[],limitations:[]};
 const store=await makeStore(client);store.setState({forecastBundle:{views:[view]}});
 store.getState().askForecastAssistant('Explain',{action:'explain',run_id:'issued-1',scope_type:'company',scope_id:'co',driver_id:'launch'});
 const first=(await store.getState().sendMessage('main','Move the project start to November 10')).at(-1).actionDraft;
 assert.equal(first.proposedStart,'2026-11-10');assert.equal(first.parentRunId,'issued-1');
 const next=(await store.getState().sendMessage('main','Make it two weeks later')).at(-1).actionDraft;
 assert.equal(next.id,first.id);assert.equal(next.proposedStart,'2026-11-24');assert.equal(next.revision,first.revision+1);
});

test('reconciling an older reply preserves a newer deliberately selected proposal and composer',async()=>{
 const client=fixtureClient();let requestId;
 client.sendMessage=async(_t,_c,_f,options)=>{requestId=options.clientMessageId;throw new TypeError('Lost reply');};
 const store=await makeStore(client);store.setState({conversationContext:{intent:'allocation',selected_proposal_id:'proposal-a'}});
 await assert.rejects(store.getState().sendMessage('main','Make it $50'));
 store.getState().askAssistant('Make it $40 instead',{intent:'allocation',selected_proposal_id:'proposal-b'});
 client.reconcileMessage=async()=>({status:'completed',messages:[{id:'reply-a',threadId:'main',role:'assistant',content:'Draft A',createdAt:'2026-10-25T12:00:01Z',conversationContext:{intent:'allocation',selected_proposal_id:'proposal-a'}}]});
 await store.getState().reconcileMessage('main',requestId);
 assert.equal(store.getState().conversationContext.selected_proposal_id,'proposal-b');
 assert.equal(store.getState().composer,'Make it $40 instead');
 assert.equal(store.getState().threads.main.at(-1).id,'reply-a');
});

test('confirmed apply clears the matching selected draft with an explicit empty backend context',async()=>{
 const client=fixtureClient();client.applyProposal=async()=>receipt;let sentOptions;
 client.sendMessage=async(_t,_c,_f,options)=>{sentOptions=options;return [];};
 const store=await makeStore(client);store.setState({proposals:[proposal],conversationContext:{intent:'allocation',selected_proposal_id:'p1',selected_proposal_version:2,pending_slot:'change'}});
 await store.getState().applyProposal('p1');assert.deepEqual(store.getState().conversationContext,{});
 await store.getState().sendMessage('main','Move $50 from Product to Research');assert.deepEqual(sentOptions.conversationContext,{});
});
test('confirmed rejection clears its selected draft but an in-flight older decision preserves a newer selection',async()=>{
 const client=fixtureClient();client.rejectProposal=async()=>({...proposal,status:'rejected'});
 const store=await makeStore(client);store.setState({proposals:[proposal],conversationContext:{intent:'allocation',selected_proposal_id:'p1'}});
 await store.getState().rejectProposal('p1');assert.deepEqual(store.getState().conversationContext,{});
 const accepted=deferred();client.applyProposal=()=>accepted.promise;
 const newerStore=await makeStore(client);newerStore.setState({proposals:[proposal],conversationContext:{intent:'allocation',selected_proposal_id:'p1'}});
 const applying=newerStore.getState().applyProposal('p1');
 newerStore.getState().askAssistant('Make this $40',{intent:'allocation',selected_proposal_id:'p2'});
 accepted.resolve(receipt);await applying;
 assert.equal(newerStore.getState().conversationContext.selected_proposal_id,'p2');assert.equal(newerStore.getState().composer,'Make this $40');
});

test('request-scoped workbench messages preserve unrelated composer, selection and pinned forecast',async()=>{
 const client=fixtureClient();let sentForecast,sentOptions;
 client.sendMessage=async(_t,_c,forecast,options)=>{sentForecast=forecast;sentOptions=options;return [{id:'budget-answer',threadId:'main',role:'assistant',content:'Draft ready',createdAt:'2026-10-25T12:00:00Z',conversationContext:{intent:'allocation',selected_proposal_id:'new-budget'}}];};
 const store=await makeStore(client);const selected={intent:'allocation',selected_proposal_id:'unrelated-draft'};const pinned={action:'explain',run_id:'issued-1',scope_type:'team',scope_id:'research'};
 store.setState({composer:'Move $50',conversationContext:selected,forecastQuestionContext:pinned});
 await store.getState().sendMessage('main','Move $50',{conversationContext:{intent:'allocation',selected_proposal_id:'workbench-draft'}});
 assert.equal(sentForecast,undefined);assert.equal(sentOptions.conversationContext.selected_proposal_id,'workbench-draft');
 assert.equal(store.getState().composer,'Move $50');assert.equal(store.getState().conversationContext,selected);assert.equal(store.getState().forecastQuestionContext,pinned);
});
test('reconciled isolated request does not take over the assistant context and later empty-context sends are explicit',async()=>{
 const client=fixtureClient();let requestId;let laterContext;
 client.sendMessage=async(_t,_c,_f,options)=>{requestId=options.clientMessageId;throw new TypeError('Lost reply');};
 const store=await makeStore(client);store.setState({composer:'My unrelated draft'});
 await assert.rejects(store.getState().sendMessage('main','Move $50',{conversationContext:{intent:'allocation'}}));
 client.reconcileMessage=async()=>({status:'completed',messages:[{id:'workbench-answer',threadId:'main',role:'assistant',content:'Prepared',createdAt:'2026-10-25T12:00:00Z',conversationContext:{intent:'allocation',selected_proposal_id:'workbench-only'}}]});
 await store.getState().reconcileMessage('main',requestId);
 assert.equal(store.getState().conversationContext,undefined);assert.equal(store.getState().composer,'My unrelated draft');
 client.sendMessage=async(_t,_c,_f,options)=>{laterContext=options.conversationContext;return [];};
 await store.getState().sendMessage('main','New conversation question');assert.deepEqual(laterContext,{});
});
