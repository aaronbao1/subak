import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {stripTypeScriptTypes} from 'node:module';
const root=fileURLToPath(new URL('../src/',import.meta.url));
const cache=new Map();
/** Pure TS test modules only; runtime imports resolve recursively without build artifacts. */
export function tsModuleUrl(filename) {
 const filenamePath=filename instanceof URL ? fileURLToPath(filename) : filename;
 if(cache.has(filenamePath))return cache.get(filenamePath);
 let source=stripTypeScriptTypes(fs.readFileSync(filenamePath,'utf8'));
 source=source.replace(/(from\s+)(["'])([^"']+)\2/g,(full,prefix,quote,specifier)=>{
  if(!specifier.startsWith('.')&&!specifier.startsWith('@/'))return full;
  const candidate=specifier.startsWith('@/')?path.join(root,specifier.slice(2)):path.resolve(path.dirname(filenamePath),specifier);
  const resolved=[candidate,`${candidate}.ts`,path.join(candidate,'index.ts')].find(p=>fs.existsSync(p)&&fs.statSync(p).isFile());
  if(!resolved)throw new Error(`Unresolved test module ${candidate}`);
  return `${prefix}${JSON.stringify(tsModuleUrl(resolved))}`;
 });
 const url=`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`;
 cache.set(filenamePath,url);return url;
}
