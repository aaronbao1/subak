import test from 'node:test';
import assert from 'node:assert/strict';
import {makeStore,fixtureClient,deferred} from './store-test-helper.mjs';
const request={id:'r1',clientRequestId:'stable',requestedAmount:null,status:'submitted'};
test('submitted update receipt survives failed refresh and never mutates approved budgets',async()=>{
 let mutations=0;const client={...fixtureClient(),ingestTeamUpdate:async()=>request,getBudgetRequests:async()=>{throw Error('offline')},applyProposal:async()=>{mutations++}};
 const store=await makeStore(client);store.setState({budgets:[{id:'b1',allocated:100}]});
 assert.equal((await store.getState().ingestTeamUpdate({clientRequestId:'stable',requestedAmount:null})).id,'r1');
 await store.getState().loadRequests();assert.equal(store.getState().requests[0].requestedAmount,null);assert.equal(store.getState().requestState,'stale');assert.equal(store.getState().budgets[0].allocated,100);assert.equal(mutations,0);
});
test('older list response cannot erase a newly accepted request receipt',async()=>{
 const pending=deferred();const client={...fixtureClient(),getBudgetRequests:()=>pending.promise,ingestTeamUpdate:async()=>request};const store=await makeStore(client);
 const load=store.getState().loadRequests();await store.getState().ingestTeamUpdate({clientRequestId:'stable'});pending.resolve([]);await load;assert.deepEqual(store.getState().requests,[request]);
});
test('budget refresh separately refreshes authoritative state and requests without changing receipt success',async()=>{
 const state={stateVersion:2,envelopeTotal:'123.00000000001',allocatedTotal:'100',unallocatedAmount:'23.00000000001'};
 const client={...fixtureClient(),getAllocationState:async()=>state,getBudgetRequests:async()=>[request]};const store=await makeStore(client);
 assert.equal(await store.getState().refreshBudgets(),true);assert.equal(store.getState().allocationState,state);assert.deepEqual(store.getState().requests,[request]);
 client.getAllocationState=async()=>{throw Error('state offline')};client.getBudgetRequests=async()=>{throw Error('request offline')};
 assert.equal(await store.getState().refreshBudgets(),true);assert.equal(store.getState().allocationState,state);assert.equal(store.getState().allocationStateStatus,'stale');assert.equal(store.getState().requestState,'stale');
});
