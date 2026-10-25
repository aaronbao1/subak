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
