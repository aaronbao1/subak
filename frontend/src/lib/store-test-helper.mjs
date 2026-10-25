import fs from 'node:fs';
import { stripTypeScriptTypes } from 'node:module';
const dataUrl=source=>`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`;
const fromTs=path=>dataUrl(stripTypeScriptTypes(fs.readFileSync(new URL(path,import.meta.url),'utf8')));
let storeNumber=0;
export async function makeStore(client) {
 const key=`__actionStoreClient${++storeNumber}`;
 globalThis[key]=client;
 let source=stripTypeScriptTypes(fs.readFileSync(new URL('./store.ts',import.meta.url),'utf8'));
 source=source.replace('from "zustand"',`from ${JSON.stringify(import.meta.resolve('zustand'))}`)
  .replace('from "@/components/dashboard/forecast-derive"',`from ${JSON.stringify(fromTs('../components/dashboard/forecast-derive.ts'))}`)
  .replace('from "@/lib/planning-drafts"',`from ${JSON.stringify(fromTs('./planning-drafts.ts'))}`)
  .replace('from "@/lib/data/thread-merge"',`from ${JSON.stringify(fromTs('./data/thread-merge.ts'))}`)
  .replace('import { getDataClient } from "@/lib/data";', `const getDataClient = () => globalThis[${JSON.stringify(key)}];`);
 const imported=await import(dataUrl(source+`\n// isolated-store-${storeNumber}`));
 return imported.useAppStore;
}
export function fixtureClient() {
 return {getBudgetRequests:async()=>[],getAllocationState:async()=>({stateVersion:1,envelopeTotal:"0",allocatedTotal:"0",unallocatedAmount:"0",allocations:[]}),getCompany:async()=>({currentPeriod:{start:'2026-10-01',end:'2026-12-31'}}),
 getTeams:async()=>[],getPeople:async()=>[],getSpending:async()=>[],getBudgets:async()=>[],getForecasts:async()=>[],getContext:async()=>[],getProposals:async()=>[],getDecisions:async()=>[],getThread:async()=>[],getForecastViews:async()=>({views:[]}),getForecastEvidence:async()=>({items:[]})};
}
export function deferred() {let resolve,reject;const promise=new Promise((yes,no)=>{resolve=yes;reject=no;});return {promise,resolve,reject};}
