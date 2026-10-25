import test from 'node:test';
import assert from 'node:assert/strict';
import {tsModuleUrl} from '../../../tests/load-ts-module.mjs';
const {selectCostComponents}=await import(tsModuleUrl(new URL('./cost-components-derive.ts',import.meta.url)));
const period={start:'2026-10-19',end:'2026-10-25'};
const record=(extra={})=>({id:'r',teamId:'t',date:'2026-10-20',component:'api',provider:'a',amount:10,unit:'usd',provenance:'reported_charge',source:'ledger',complete:true,...extra});
const select=records=>selectCostComponents({records,period,unit:'usd'});
test('component financial totals reconcile without included or unpriced usage',()=>{
 const result=select([record({component:'subscription',amount:20}),record({component:'extra_usage',amount:3}),record(),record({component:'included_usage',amount:900,includedUsageNotional:850,provenance:'usage_only'}),record({component:'unpriced_usage',amount:700,provenance:'usage_only'}),record({amount:99,provenance:'usage_only'})]);
 assert.equal(result.total,33);assert.equal(result.components.reduce((sum,row)=>sum+(row.amount??0),0),33);
 assert.equal(result.included.notional,850);assert.equal(result.included.recordCount,1);assert.equal(result.unpricedRecordCount,2);
});
test('selected period and financial unit are exact, including shared or unknown team records',()=>{
 const result=select([record({date:'2026-10-18',amount:999}),record({date:'2026-10-26',amount:999}),record({unit:'credits',amount:999}),record({teamId:'',amount:4}),record({teamId:'missing-team',amount:6})]);
 assert.equal(result.total,10);assert.equal(result.recordCount,2);
});
test('missing financial amounts and known zeros remain different',()=>{
 const empty=select([]);assert.equal(empty.total,null);assert.ok(empty.components.every(row=>row.amount===null));
 const zero=select([record({amount:0})]);assert.equal(zero.total,0);assert.equal(zero.components.find(row=>row.component==='api').amount,0);assert.equal(zero.components.find(row=>row.component==='subscription').amount,null);
 const invalid=select([record({amount:NaN}),record({amount:Infinity})]);assert.equal(invalid.total,null);assert.equal(invalid.invalidAmountCount,2);
});
test('refunds and partial records remain explicit without misleading positive shares',()=>{
 const result=select([record({amount:-2,complete:false}),record({component:'subscription',amount:10})]);
 assert.equal(result.total,8);assert.equal(result.hasPartialRecords,true);assert.equal(result.canShowShares,false);assert.equal(result.components.find(row=>row.component==='api').amount,-2);
});
test('coverage and notional metadata do not become a second financial charge',()=>{
 const result=select([record({component:'included_usage',amount:0}),record({component:'included_usage',amount:0,includedUsageNotional:0})]);
 assert.equal(result.total,null);assert.equal(result.included.notional,0);assert.equal(result.included.recordCount,2);assert.equal(result.unpricedRecordCount,0);
});
test('API cost component and API model partition use the same financial boundary',async()=>{
 const {selectApiSpend}=await import(tsModuleUrl(new URL('./api-spend-derive.ts',import.meta.url)));
 const records=[record({amount:12.34}),record({provider:'b',model:'Model',amount:-2.34}),record({provenance:'usage_only',amount:200}),record({component:'subscription',amount:90}),record({component:'included_usage',amount:900}),record({amount:NaN}),record({unit:'credits',amount:999})];
 assert.equal(select(records).components.find(row=>row.component==='api').amount,selectApiSpend({records,period,unit:'usd'}).total);
});
