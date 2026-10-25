import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {stripTypeScriptTypes} from 'node:module';
import {tsModuleUrl} from '../../../tests/load-ts-module.mjs';
let source=stripTypeScriptTypes(fs.readFileSync(new URL('./derive.ts',import.meta.url),'utf8'));
source=source.replace('import { COMPONENT_ORDER } from "@/components/team/labels";',`const COMPONENT_ORDER=['subscription','included_usage','extra_usage','api','unpriced_usage'];`)
.replace('from "./status"',`from ${JSON.stringify(tsModuleUrl(new URL('./status.ts',import.meta.url)))}`)
.replace('from "@/lib/finance-summary"',`from ${JSON.stringify(tsModuleUrl(new URL('../../lib/finance-summary.ts',import.meta.url)))}`);
const {summarizeTeams,buildDailyRows,modelTotals,componentTotals}=await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);
const period={start:'2026-10-19',end:'2026-10-25'},teams=[{id:'t',name:'Team'}];
const row=(extra={})=>({teamId:'t',date:'2026-10-23',component:'api',amount:10,unit:'usd',complete:true,provenance:'simulated',provider:'a',model:'Same model',...extra});
test('dashboard sums billable records and keeps duplicate provider model names separate',()=>{
 const records=[row(),row({component:'included_usage',amount:900}),row({component:'unpriced_usage',amount:700}),row({provider:'b',amount:5})];
 assert.equal(summarizeTeams(teams,records,[],[])[0].spent,15);
 assert.equal(buildDailyRows(teams,records,[],period)[0].t_t,null);
 assert.equal(buildDailyRows(teams,records,[],period).find(r=>r.date==='2026-10-23').t_t,15);
 assert.equal(componentTotals(records).find(r=>r.component==='included_usage').amount,0);
 assert.equal(modelTotals(records).length,2);
});
test('team summary selects matching identity and period and never compares a quarter forecast with a week budget',()=>{
 const budget={teamId:'t',period,unit:'usd',allocated:100};
 const q={teamId:'t',period:{start:'2026-10-01',end:'2026-12-31'},status:'available',projected:999,unit:'usd'};
 const summary=summarizeTeams(teams,[row()], [budget],[q])[0];
 assert.equal(summary.projected,undefined);
 assert.equal(summary.budget,budget);
});
