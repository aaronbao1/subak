import test from 'node:test';
import assert from 'node:assert/strict';
import {makeStore,fixtureClient,deferred} from './store-test-helper.mjs';
const query={scopeType:'team',scopeId:'research',startDate:'2026-09-21',endDateExclusive:'2026-11-16'};
const response=q=>({scope:{type:q.scopeType,id:q.scopeId},startDate:q.startDate,endDateExclusive:q.endDateExclusive,weeks:[],actualsRevision:'r1'});
test('weekly history failure retains valid same-scope data with retryable stale state',async()=>{
 const client=fixtureClient();client.getWeeklyForecastHistory=async q=>response(q);
 const store=await makeStore(client);await store.getState().loadWeeklyHistory(query);
 assert.equal(store.getState().weeklyHistoryState,'ready');assert.equal(store.getState().weeklyHistory.scope.id,'research');
 client.getWeeklyForecastHistory=async()=>{throw new Error('History offline');};await store.getState().loadWeeklyHistory(query);
 assert.equal(store.getState().weeklyHistoryState,'stale');assert.match(store.getState().weeklyHistoryError,/offline/);assert.equal(store.getState().weeklyHistory.scope.id,'research');
 client.getWeeklyForecastHistory=async q=>({...response(q),actualsRevision:'r2'});await store.getState().loadWeeklyHistory(query);
 assert.equal(store.getState().weeklyHistoryState,'ready');assert.equal(store.getState().weeklyHistory.actualsRevision,'r2');
});
test('failed new-scope query never leaves old-scope actuals under the new heading',async()=>{
 const client=fixtureClient();client.getWeeklyForecastHistory=async q=>response(q);
 const store=await makeStore(client);await store.getState().loadWeeklyHistory(query);
 client.getWeeklyForecastHistory=async()=>{throw new Error('Scope unavailable');};await store.getState().loadWeeklyHistory({...query,scopeId:'product'});
 assert.equal(store.getState().weeklyHistoryState,'error');assert.equal(store.getState().weeklyHistory,undefined);
});
test('a late older-scope response cannot replace the latest selected weekly history',async()=>{
 const client=fixtureClient(),first=deferred();client.getWeeklyForecastHistory=q=>q.scopeId==='research'?first.promise:Promise.resolve(response(q));
 const store=await makeStore(client);const older=store.getState().loadWeeklyHistory(query);
 await store.getState().loadWeeklyHistory({...query,scopeId:'product'});first.resolve(response(query));await older;
 assert.equal(store.getState().weeklyHistory.scope.id,'product');assert.equal(store.getState().weeklyHistoryState,'ready');
});
test('updating canonical forecast views refreshes the same weekly query without changing its window',async()=>{
 const client=fixtureClient();const calls=[];client.getWeeklyForecastHistory=async q=>{calls.push(q);return response(q);};
 const store=await makeStore(client);await store.getState().loadWeeklyHistory(query);await store.getState().loadForecastViews();
 assert.deepEqual(calls,[query,query]);
});
