import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {stripTypeScriptTypes} from 'node:module';
const source=stripTypeScriptTypes(fs.readFileSync(new URL('./request-session.ts',import.meta.url),'utf8'));
const {createRequestSession}=await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);
test('uncertain ingestion survives consumers and retries the exact original body',()=>{
 const session=createRequestSession(), input={clientRequestId:'stable-key',requestedAmount:'50.25',narrative:'Original evidence'};
 let changes=0;const unsubscribe=session.subscribe(()=>changes++);
 assert.equal(session.begin(input),true);unsubscribe();
 input.narrative='Edited after submission';
 session.unknown('stable-key');
 assert.equal(session.begin({...input,clientRequestId:'new-key'}),false);
 assert.deepEqual(session.retry(),{clientRequestId:'stable-key',requestedAmount:'50.25',narrative:'Original evidence'});
 assert.equal(session.retry(),undefined);
 session.resolve('unrelated');assert.ok(session.getSnapshot());
 session.resolve('stable-key');assert.equal(session.getSnapshot(),undefined);assert.equal(changes,1);
 assert.equal(session.begin({...input,clientRequestId:'new-key'}),true);
});
