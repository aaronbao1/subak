import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import Module, {createRequire} from 'node:module';
const require=createRequire(new URL('../../../package.json',import.meta.url));
const React=require('react'),ts=require('typescript');
const filename=new URL('./source-sheet.tsx',import.meta.url).pathname;
const js=ts.transpileModule(fs.readFileSync(filename,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}}).outputText;
function harness(getDocument){
 const values=[];let cursor=0,effect;
 const part=({children})=>children;
 const overrides={react:{useState(initial){const index=cursor++;if(!(index in values))values[index]=initial;return [values[index],next=>{values[index]=typeof next==='function'?next(values[index]):next;}];},useEffect(callback){effect=callback;}},'react-markdown':part,'@/lib/data':{getDataClient:()=>({getDocument})},'@/lib/display-copy':{displayCopy:v=>v,displayReference:v=>v,displaySourceText:v=>v},'@/components/ui/scroll-area':{ScrollArea:part},'@/components/ui/sheet':{Sheet:part,SheetContent:part,SheetDescription:part,SheetHeader:part,SheetTitle:part},'@/components/ui/skeleton':{Skeleton:part},'./labels':{fmtDate:v=>v,KIND_LABEL:{plan:'Plan'}},'@/components/context/source-brand':{SourceBadge:part}};
 const loaded=new Module(filename);loaded.require=specifier=>overrides[specifier]??require(specifier);loaded._compile(js,filename);
 return {values,render(id){cursor=0;return loaded.exports.SourceSheet({documentId:id,onClose(){}});},start(){return effect();}};
}
const flush=()=>new Promise(resolve=>setImmediate(resolve));
const find=(node,predicate)=>{if(!React.isValidElement(node))return; if(predicate(node))return node;for(const child of React.Children.toArray(node.props.children)){const found=find(child,predicate);if(found)return found;}};
test('failed source open reaches a retryable state rather than an endless loading sheet',async()=>{
 const h=harness(async()=>{throw new Error('unavailable');});h.render('a');h.start();await flush();assert.deepEqual(h.values[0],{id:'a',status:'error'});
 const retry=find(h.render('a'),node=>node.props.children==='Retry source');assert.ok(retry);retry.props.onClick();assert.equal(h.values[0],undefined);assert.equal(h.values[1],1);
});
test('late result from a closed source cannot overwrite a newer source',async()=>{
 let resolveFirst;const newer={id:'b',title:'B',body:'Raw quotation',kind:'plan'};
 const h=harness(id=>id==='a'?new Promise(resolve=>{resolveFirst=resolve;}):Promise.resolve(newer));h.render('a');const cancel=h.start();cancel();h.render('b');h.start();await flush();resolveFirst({id:'a'});await flush();assert.equal(h.values[0].id,'b');assert.equal(h.values[0].doc,newer);
});
test('failed superseding-version lookup preserves the received original text',async()=>{
 const original={id:'a',title:'Original demo planning message',body:'Synthetic-biology team: original quoted text.',kind:'plan',supersededBy:'b'};
 const h=harness(id=>id==='a'?Promise.resolve(original):Promise.reject(new Error('missing newer')));h.render('a');h.start();await flush();assert.equal(h.values[0].status,'ready');assert.equal(h.values[0].doc,original);assert.equal(h.values[0].doc.body,original.body);assert.equal(h.values[0].newer,undefined);
});
