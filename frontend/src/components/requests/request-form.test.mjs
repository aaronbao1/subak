import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {stripTypeScriptTypes} from 'node:module';
const source=stripTypeScriptTypes(fs.readFileSync(new URL('./request-form.ts',import.meta.url),'utf8'));
const {requestedAmount,prepareTeamUpdateForm,teamUpdateInput}=await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);
const values={teamId:'research',title:'New evaluation project',projectName:'Eval suite',summary:'We expect increased usage and may need $50k.',amount:'',start:'2026-10-19',end:'2026-10-25'};
test('unstated requested amount stays unknown even when narrative mentions money',()=>{assert.equal(prepareTeamUpdateForm(values,['research']).requestedAmount,null);});
test('explicit additional dollars are exact and never turn small amounts into thousands',()=>{assert.equal(requestedAmount('50'),'50.00');assert.equal(requestedAmount('5,000.25'),'5000.25');for(const value of ['-50','50k','0','1e3','50.251'])assert.throws(()=>requestedAmount(value));});
test('request dates retain a real inclusive selection as an exclusive end boundary',()=>{const result=prepareTeamUpdateForm({...values,start:'2026-12-28',end:'2026-12-31'},['research']);assert.equal(result.periodEndExclusive,'2027-01-01');for(const extra of [{start:'2026-02-30'},{end:'2026-10-18'},{teamId:'unknown'},{summary:''}])assert.throws(()=>prepareTeamUpdateForm({...values,...extra},['research']));});

test('clarifying an update requires explicit dollars and creates separate linked evidence',()=>{
 const original={id:'context-only-update',requestedAmount:null,narrative:values.summary};
 assert.throws(()=>teamUpdateInput(values,['research'],'project','new-operation',original),/explicit additional amount/);
 const result=teamUpdateInput({...values,amount:'50.25'},['research'],'project','new-operation',original);
 assert.equal(result.clientRequestId,'new-operation');assert.equal(result.requestedAmount,'50.25');
 assert.equal(result.sourceRef,'budget-request:context-only-update');
 assert.deepEqual(result.evidenceRefs,[{kind:'budget_request',id:'context-only-update'}]);
 assert.equal(original.requestedAmount,null);assert.equal(original.narrative,values.summary);
});
