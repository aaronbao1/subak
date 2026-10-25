import test from 'node:test';
import assert from 'node:assert/strict';
import {makeStore,fixtureClient,deferred} from './store-test-helper.mjs';
const user={id:'user-1',role:'user',threadId:'main',content:'Explain',createdAt:'2026-10-26T12:00:00Z'};
const reply={id:'reply-1',role:'assistant',threadId:'main',content:'Explanation',createdAt:'2026-10-26T12:00:01Z'};
test('real store live reload observes committed user before send completes without duplicate ids',async()=>{
 const client=fixtureClient(), sent=deferred();
 client.sendMessage=(_thread,_content,_forecast,options)=>{user.clientMessageId=options.clientMessageId;return sent.promise;};
 const store=await makeStore(client);
 await store.getState().load();
 const sending=store.getState().sendMessage('main','Explain');
 client.getThread=async()=>[user];
 await store.getState().load();
 assert.deepEqual(store.getState().threads.main,[user]);
 sent.resolve([user,reply]);
 await sending;
 assert.deepEqual(store.getState().threads.main,[user,reply]);
});
test('real store stale in-flight thread fetch cannot erase completed send reply',async()=>{
 const client=fixtureClient(), sent=deferred(), fetched=deferred();
 client.sendMessage=(_thread,_content,_forecast,options)=>{user.clientMessageId=options.clientMessageId;return sent.promise;};
 const store=await makeStore(client);
 await store.getState().load();
 client.getThread=()=>fetched.promise;
 const loading=store.getState().load();
 const sending=store.getState().sendMessage('main','Explain');
 sent.resolve([user,reply]);
 await sending;
 fetched.resolve([user]);
 await loading;
 assert.deepEqual(store.getState().threads.main,[user,reply]);
});

test('real store keeps two FrozenClock response pairs ordered across sends and subsequent reloads',async()=>{
 const client=fixtureClient();const accepted=[];let sequence=0;
 client.sendMessage=async(threadId,content,_forecast,options)=>{
  const n=++sequence;const pair=[{id:`u${n}`,threadId,role:'user',content,clientMessageId:options.clientMessageId,createdAt:'2026-10-25T12:00:00Z'},{id:`a${n}`,threadId,role:'assistant',content:`Reply ${n}`,createdAt:'2026-10-25T12:00:00Z'}];
  accepted.push(...pair);return pair;
 };
 client.getThread=async()=>[...accepted];
 const store=await makeStore(client);await store.getState().load();
 await store.getState().sendMessage('main','Move $50');await store.getState().sendMessage('main','Add $50');
 assert.deepEqual(store.getState().threads.main.map(m=>m.id),['u1','a1','u2','a2']);
 await store.getState().load();assert.deepEqual(store.getState().threads.main.map(m=>m.id),['u1','a1','u2','a2']);
 client.getThread=async()=>accepted.slice(0,2);await store.getState().load();assert.deepEqual(store.getState().threads.main.map(m=>m.id),['u1','a1','u2','a2']);
});
