import test from 'node:test';
import assert from 'node:assert/strict';
import {tsModuleUrl} from '../../../tests/load-ts-module.mjs';
const {deriveSourceLibrary,sourceTeamName,sourceDocumentDate}=await import(tsModuleUrl(new URL('./source-library-derive.ts',import.meta.url)));
const teams=[{id:'r',name:'Research',color:'blue'},{id:'p',name:'Product',color:'red'}];
const documents=[
 {id:'old',title:'Original plan',kind:'plan',date:'2026-10-01',teamIds:['r'],origin:'Slack export #planning',body:'Needs a larger inference cluster.',supersededBy:'new'},
 {id:'new',title:'Updated plan',kind:'plan',date:'2026-10-20',teamIds:['r','p'],origin:'Uploaded PDF',body:'Capacity shifted to product.'},
 {id:'unassessed',title:'Unreviewed receipt',kind:'plan',date:'2026-10-21',teamIds:['unknown-id'],origin:'Email',body:'Document-only evidence.'},
 {id:'no-team',title:'Company note',kind:'plan',date:'2026-10-22',origin:'Notion export',body:'A shared source.'},
];
test('counts every received document, including superseded and unassessed sources, newest first',()=>{
 const original=structuredClone(documents);const result=deriveSourceLibrary(documents,teams,'');
 assert.equal(result.total,4);assert.equal(result.filtered.length,4);
 assert.deepEqual(result.filtered.map(doc=>doc.id),['no-team','unassessed','new','old']);
 assert.equal(result.filtered.at(-1).supersededBy,'new');assert.deepEqual(documents,original);
});
test('search finds raw title, body, origin and team names with case-insensitive terms',()=>{
 for(const [q,expected] of [['original',['old']],['INFERENCE',['old']],['uploaded pdf',['new']],['Research',['new','old']],['research cluster',['old']]]){
  assert.deepEqual(deriveSourceLibrary(documents,teams,q).filtered.map(doc=>doc.id),expected);
 }
});
test('team filter uses document team IDs, keeps total corpus count, and leaves unscoped sources unassigned',()=>{
 const result=deriveSourceLibrary(documents,teams,'','r');assert.equal(result.total,4);
 assert.deepEqual(result.filtered.map(doc=>doc.id),['new','old']);
 assert.deepEqual(deriveSourceLibrary(documents,teams,'capacity','p').filtered.map(doc=>doc.id),['new']);
 assert.deepEqual(deriveSourceLibrary(documents,teams,'','unknown-id').filtered.map(doc=>doc.id),['unassessed']);
});
test('unknown team references and missing dates are labeled honestly',()=>{
 assert.equal(sourceTeamName('unknown-id',teams),'Unknown team (unknown-id)');
 const option=deriveSourceLibrary(documents,teams,'').teamOptions.find(team=>team.id==='unknown-id');
 assert.equal(option.name,'Unknown team (unknown-id)');
 assert.equal(sourceDocumentDate('not-a-date'),'Date unavailable');
 assert.equal(sourceDocumentDate('2026-10-01'),'Oct 1, 2026');
 assert.equal(deriveSourceLibrary([],teams,'').total,0);
});
