import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { stripTypeScriptTypes } from 'node:module';
const source=stripTypeScriptTypes(fs.readFileSync(new URL('./allocation-session.ts',import.meta.url),'utf8'));
const {createAllocationSession}=await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);
test('an accepted or uncertain operation survives subscribers leaving and rejects another preparation',()=>{
 const session=createAllocationSession();let notifications=0;
 const unsubscribe=session.subscribe(()=>notifications++);
 assert.equal(session.begin({id:'a',kind:'message',request:{content:'first'},status:'preparing'}),true);
 session.update('a',{clientMessageId:'message-a',status:'unknown'});unsubscribe();
 assert.equal(session.getSnapshot().operation.clientMessageId,'message-a');
 assert.equal(session.begin({id:'b',kind:'message',request:{content:'second'},status:'preparing'}),false);
 assert.equal(session.clear(),false);
 assert.equal(notifications,2);
});
test('only the same durable operation can settle and a confirmed result permits a new adjustment',()=>{
 const session=createAllocationSession();
 session.begin({id:'a',kind:'targets',request:{},status:'preparing'});
 assert.equal(session.update('old',{status:'prepared',proposalId:'wrong'}),false);
 session.update('a',{status:'prepared',proposalId:'p'});
 assert.equal(session.getSnapshot().operation.proposalId,'p');
 assert.equal(session.clear(),true);assert.equal(session.getSnapshot().operation,undefined);
 assert.equal(session.begin({id:'b',kind:'targets',request:{},status:'preparing'}),true);
});
test('a prepared draft cannot be cleared or replaced while its application outcome is unresolved',()=>{
 const session=createAllocationSession();
 session.begin({id:'a',kind:'targets',request:{},status:'prepared',proposalId:'p'});
 assert.equal(session.clear(true),false);
 assert.equal(session.begin({id:'b',kind:'targets',request:{},status:'preparing'},true),false);
 assert.equal(session.getSnapshot().operation.proposalId,'p');
 assert.equal(session.clear(false),true);
});
