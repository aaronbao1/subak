import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { stripTypeScriptTypes } from 'node:module';
const source=stripTypeScriptTypes(fs.readFileSync(new URL('./thread-merge.ts',import.meta.url),'utf8'));
const {mergeThreadMessages}=await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);
test('live reload preserves replies received after its thread fetch without duplicating ids',()=>{
 const old={id:'m1',createdAt:'2026-10-26T12:00:00Z'}, user={id:'m2',createdAt:'2026-10-26T12:00:01Z'},reply={id:'m3',createdAt:'2026-10-26T12:00:02Z'};
 assert.deepEqual(mergeThreadMessages([old],[old,user,reply]),[old,user,reply]);
 assert.deepEqual(mergeThreadMessages([old,user,reply],[old,user,reply]),[old,user,reply]);
});
test('send completion deduplicates the user and reply already observed by live reload',()=>{
 const user={id:'user',createdAt:'2026-10-26T12:00:00Z'}, reply={id:'reply',createdAt:'2026-10-26T12:00:01Z'};
 assert.deepEqual(mergeThreadMessages([user,reply],[user]),[user,reply]);
 assert.deepEqual(mergeThreadMessages([user,reply],[user,reply]),[user,reply]);
});

test('backend user echo replaces its pending local message by stable client identity',()=>{
 const pending={id:'pending:request-1',clientMessageId:'request-1',role:'user',content:'Explain',createdAt:'2026-10-25T12:00:00Z',delivery:'sending'};
 const accepted={id:'server-1',clientMessageId:'request-1',role:'user',content:'Explain',createdAt:'2026-10-25T12:00:01Z'};
 assert.deepEqual(mergeThreadMessages([accepted],[pending]),[accepted]);
});

test('same-clock consecutive send responses append after established conversation order',()=>{
 const at='2026-10-25T12:00:00Z';
 const pair1=[{id:'u1',role:'user',createdAt:at},{id:'a1',role:'assistant',createdAt:at}];
 const pair2=[{id:'u2',role:'user',createdAt:at},{id:'a2',role:'assistant',createdAt:at}];
 assert.deepEqual(mergeThreadMessages(pair2,pair1,'append').map(m=>m.id),['u1','a1','u2','a2']);
});
test('same-clock full and stale snapshots preserve server sequence and newer messages',()=>{
 const at='2026-10-25T12:00:00Z';
 const full=['u1','a1','u2','a2'].map(id=>({id,createdAt:at}));
 assert.deepEqual(mergeThreadMessages(full,[full[2],full[3]]).map(m=>m.id),['u1','a1','u2','a2']);
 assert.deepEqual(mergeThreadMessages(full.slice(0,2),full).map(m=>m.id),['u1','a1','u2','a2']);
});
test('a recovered older reply inserts next to its pending user before a newer pair',()=>{
 const at='2026-10-25T12:00:00Z';
 const pending={id:'pending:r1',clientMessageId:'r1',role:'user',createdAt:at,delivery:'unknown'};
 const newer=[{id:'u2',role:'user',createdAt:at},{id:'a2',role:'assistant',createdAt:at}];
 const recovered=[{id:'u1',clientMessageId:'r1',role:'user',createdAt:at},{id:'a1',role:'assistant',createdAt:at}];
 assert.deepEqual(mergeThreadMessages(recovered,[pending,...newer],'append').map(m=>m.id),['u1','a1','u2','a2']);
});
