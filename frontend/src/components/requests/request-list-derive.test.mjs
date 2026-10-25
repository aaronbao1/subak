import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {stripTypeScriptTypes} from 'node:module';
const source=stripTypeScriptTypes(fs.readFileSync(new URL('./request-list-derive.ts',import.meta.url),'utf8'));
const {pendingRequestSummary,requestMatchesPeriod}=await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);
const period={start:'2026-10-19',end:'2026-10-25'};
const request=(id,extra={})=>({id,status:'submitted',periodStart:'2026-10-19',periodEndExclusive:'2026-10-26',requestedAmount:'100.00',remainingRequestedAmount:'100.00',...extra});
test('pending request total uses remaining explicit amounts for only the selected period',()=>{
 const result=pendingRequestSummary([request('a'),request('partial',{status:'partially_funded',requestedAmount:'500.00',remainingRequestedAmount:'25.25'}),request('future',{periodStart:'2026-10-26',periodEndExclusive:'2026-11-02'}),request('applied',{status:'approved_applied',remainingRequestedAmount:'0.00'}),request('rejected',{status:'rejected'})],period);
 assert.equal(result.total,'125.25');assert.equal(result.open.length,3);assert.equal(result.matching.length,2);
});
test('unknown amounts remain counted as unknown and never become estimated funding',()=>{
 const result=pendingRequestSummary([request('unknown',{requestedAmount:null,remainingRequestedAmount:null}),request('known',{remainingRequestedAmount:'0.10'}),request('known2',{remainingRequestedAmount:'0.20'})],period);
 assert.equal(result.total,'0.30');assert.equal(result.unknownCount,1);
 assert.equal(pendingRequestSummary([request('unknown',{remainingRequestedAmount:null})],period).total,null);
});
test('no selected period means no cross-period monetary comparison',()=>{
 const result=pendingRequestSummary([request('a')]);assert.equal(result.total,null);assert.equal(result.matching.length,0);assert.equal(result.open.length,1);
 assert.equal(requestMatchesPeriod(request('a'),period),true);assert.equal(requestMatchesPeriod(request('a'),{start:period.start,end:'2026-10-26'}),false);
});
