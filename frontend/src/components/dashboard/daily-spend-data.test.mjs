import test from 'node:test';
import assert from 'node:assert/strict';
import {tsModuleUrl} from '../../../tests/load-ts-module.mjs';
const {buildDailySpendData,foldDailySeries,isIsolatedDailyAmount,recordedDailyExtent}=await import(tsModuleUrl(new URL('./daily-spend-data.ts',import.meta.url)));
const period={start:'2026-10-19',end:'2026-10-25',label:'Week of Oct 19'};
const teams=[{id:'a',name:'A',color:'var(--chart-1)'},{id:'b',name:'B',color:'var(--chart-2)'}];
const record=(id,amount,extra={})=>({id,teamId:'a',date:'2026-10-19',amount,unit:'usd',component:'api',provenance:'reported_charge',provider:'x',complete:true,source:'records',...extra});

test('daily USD data uses only current period charges and preserves cents without projections',()=>{
 const input=[record('a',0.1),record('b',0.2),record('old',999,{date:'2026-10-18'}),record('next',999,{date:'2026-10-26'}),record('tokens',999,{unit:'tokens'}),record('credits',999,{unit:'credits'})];
 const snapshot=structuredClone(input);const result=buildDailySpendData(input,teams,period);
 assert.equal(result.rows.length,7);assert.equal(result.rows[0].date,period.start);assert.equal(result.rows.at(-1).date,period.end);
 assert.equal(result.rows[0].t_a,0.3);assert.equal(result.rows[0].t_b,null);
 assert.ok(result.rows.every(row=>row.p_a===null&&row.p_b===null));assert.deepEqual(input,snapshot);
});

test('a known zero is distinct from missing, informational, unpriced and invalid values',()=>{
 const result=buildDailySpendData([record('zero',0),record('included',900,{teamId:'b',component:'included_usage'}),record('usage',20,{date:'2026-10-20',provenance:'usage_only'}),record('unknown',0,{date:'2026-10-21',component:'unpriced_usage'}),record('invalid',NaN,{date:'2026-10-22'})],teams,period);
 assert.equal(result.rows[0].t_a,0);assert.equal(result.rows[0].t_b,null);
 assert.equal(result.rows[1].t_a,null);assert.equal(result.rows[2].t_a,null);assert.equal(result.rows[3].t_a,null);
 assert.equal(result.hasUnpricedUsage,true);
 assert.equal(result.invalidAmountCount,1);
 assert.equal(buildDailySpendData([record('usage-only',0,{provenance:'usage_only'})],teams,period).hasUnpricedUsage,true);
 assert.equal(buildDailySpendData([record('included-only',0,{provenance:'usage_only',component:'included_usage'})],teams,period).hasUnpricedUsage,false);
});

test('partial records retain partial dates and unknown team costs stay accounted for',()=>{
 const result=buildDailySpendData([record('partial',12.34,{complete:false}),record('unassigned',5,{teamId:''}),record('unknown-team',7,{teamId:'missing-directory-team'}),record('estimate',2,{teamId:'b',provenance:'estimate'})],teams,period);
 const unassigned=result.teams.find(team=>!['a','b'].includes(team.id));assert.ok(unassigned);
 assert.equal(result.rows[0][`t_${unassigned.id}`],12);assert.equal(result.rows[0].partial,true);
 assert.deepEqual(result.partialDates,['2026-10-19']);assert.equal(result.hasEstimates,true);
});

test('team colors stay distinct and stable across directory reordering',()=>{
 const many=Array.from({length:16},(_,i)=>({id:`team-${i}`,name:`Team ${i}`,color:`var(--chart-${i%5+1})`}));
 const first=buildDailySpendData([],many,period).teams;const reordered=buildDailySpendData([],many.toReversed(),period).teams;
 assert.equal(new Set(first.map(team=>team.color)).size,16);
 for(const team of first) assert.equal(reordered.find(other=>other.id===team.id).color,team.color);
 assert.equal(first[0].color,many[0].color);
 const hues=first.map(team=>team.color.match(/^hsl\((\d+)/)?.[1]).filter(Boolean).map(Number);
 assert.ok(Math.max(...hues)-Math.min(...hues)>180,'fallback hues must spread across the color wheel');
});

test('isolated zero and positive amounts remain visible in long ranges while gaps stay empty',()=>{
 const rows=buildDailySpendData([record('zero',0),record('later',5,{date:'2026-10-24'})],teams,{start:'2026-10-01',end:'2026-12-31'}).rows;
 assert.equal(rows.length,92);
 assert.equal(isIsolatedDailyAmount(rows,18,'t_a'),true);
 assert.equal(isIsolatedDailyAmount(rows,23,'t_a'),true);
 assert.equal(isIsolatedDailyAmount(rows,19,'t_a'),false);
 const adjacent=[{t_a:null},{t_a:1},{t_a:2},{t_a:null}];
 assert.equal(isIsolatedDailyAmount(adjacent,1,'t_a'),false);
});

test('folded recorded subtotals preserve known amounts and explicitly retain missing coverage',()=>{
 assert.deepEqual(foldDailySeries({t_a:0,t_b:null},['a','b'],'t_'),{amount:0,missingTeams:1});
 assert.deepEqual(foldDailySeries({t_a:0.1,t_b:0.2},['a','b'],'t_'),{amount:0.3,missingTeams:0});
 assert.deepEqual(foldDailySeries({p_a:null,p_b:null},['a','b'],'p_'),{amount:null,missingTeams:2});
});

test('recorded extent trims empty edges while retaining interior gaps and a single known zero',()=>{
 const data=buildDailySpendData([record('first',1,{date:'2026-10-20'}),record('last',2,{date:'2026-10-24'})],teams,period);
 const rows=recordedDailyExtent(data.rows);
 assert.equal(rows[0].date,'2026-10-20');assert.equal(rows.at(-1).date,'2026-10-24');assert.equal(rows.length,5);
 assert.equal(rows[1].t_a,null);assert.equal(rows[1].kind,'empty');assert.equal(rows.at(-1).t_a,2);
 const zero=recordedDailyExtent(buildDailySpendData([record('zero',0)],teams,period).rows);
 assert.equal(zero.length,1);assert.equal(zero[0].t_a,0);
 assert.deepEqual(recordedDailyExtent(buildDailySpendData([],teams,period).rows),[]);
});
