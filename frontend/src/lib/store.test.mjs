import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { stripTypeScriptTypes } from 'node:module';
const dataUrl=source=>`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`;
const fromTs=path=>dataUrl(stripTypeScriptTypes(fs.readFileSync(new URL(path,import.meta.url),'utf8')));
const deferred=()=>{let resolve;const promise=new Promise(r=>{resolve=r;});return {promise,resolve};};
let storeNumber=0;
async function makeStore(client) {
 globalThis.__forecastStoreRaceClient=client;
 let source=stripTypeScriptTypes(fs.readFileSync(new URL('./store.ts',import.meta.url),'utf8'));
 source=source.replace('from "zustand"',`from ${JSON.stringify(import.meta.resolve('zustand'))}`)
  .replace('from "@/components/dashboard/forecast-derive"',`from ${JSON.stringify(fromTs('../components/dashboard/forecast-derive.ts'))}`)
  .replace('from "@/lib/data/thread-merge"',`from ${JSON.stringify(fromTs('./data/thread-merge.ts'))}`)
  .replace('import { getDataClient } from "@/lib/data";', 'const getDataClient = () => globalThis.__forecastStoreRaceClient;');
 const importedStore=await import(dataUrl(source+`\n// independent-store-${++storeNumber}`));
 return importedStore.useAppStore;
}
function fixtureClient() {
 return {getCompany:async()=>({currentPeriod:{start:'2026-10-01',end:'2026-12-31'}}),
 getTeams:async()=>[],getPeople:async()=>[],getSpending:async()=>[],getBudgets:async()=>[],getForecasts:async()=>[],getContext:async()=>[],getProposals:async()=>[],getDecisions:async()=>[],getThread:async()=>[],getForecastViews:async()=>({views:[]}),getForecastEvidence:async()=>({items:[]})};
}
const user={id:'user-1',role:'user',threadId:'main',content:'Explain',createdAt:'2026-10-26T12:00:00Z'};
const reply={id:'reply-1',role:'assistant',threadId:'main',content:'Explanation',createdAt:'2026-10-26T12:00:01Z'};
test('real store live reload observes committed user before send completes without duplicate ids',async()=>{
 const client=fixtureClient(), sent=deferred();
 client.sendMessage=()=>sent.promise;
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
 client.sendMessage=()=>sent.promise;
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
