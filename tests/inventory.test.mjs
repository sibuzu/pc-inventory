import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {normalizeComputer,parseImport,mergeComputers,withPlanned,filterSoftware,escapeHtml,capacity,primaryGpu} from '../dist/inventory.mjs';
const pc=JSON.parse(fs.readFileSync(new URL('../dist/data/pc_china.json',import.meta.url),'utf8'));
test('real pc_china snapshot preserves physical hardware and software',()=>{
  const result=normalizeComputer(pc);assert.equal(result.id,'pc_china');assert.equal(result.hardware.memoryGB,48);assert.equal(result.software.length,138);assert.equal(primaryGpu(result).vramMB,11264);assert.match(result.hardware.cpu[0].name,/9700F/);assert.equal(result.hardware.disks.length,4);
});
test('planned devices stay pending until real data is imported',()=>{const all=withPlanned([normalizeComputer(pc)]);assert.equal(all.length,9);assert.deepEqual(all.slice(1).map(x=>x.id),['pc_sdl','pc_data','pc_rtx','rtx_5090','pc_one','pc_andy','pc_david','pc_nas']);assert.ok(all.slice(1).every(x=>x.status==='pending'&&!x.hardware));});
test('single and exported bundle imports round-trip and replace by id',()=>{
  const next={...pc,id:'pc_sdl',name:'pc_sdl'};const merged=mergeComputers([normalizeComputer(pc)],parseImport(next));assert.equal(merged.length,2);assert.equal(withPlanned(merged)[1].status,'collected');assert.equal(mergeComputers(merged,[next]).length,2);assert.deepEqual(parseImport({computers:merged}),merged);
});
test('invalid bulk imports fail before modifying existing data',()=>{
  const original=[normalizeComputer(pc)];assert.throws(()=>mergeComputers(original,[{...pc,id:'pc_sdl'},{...pc,id:'../invalid'}]));assert.equal(original.length,1);assert.throws(()=>parseImport({...pc,hardware:{...pc.hardware,memoryGB:-1}}));assert.throws(()=>parseImport({...pc,collectedAt:'invalid'}));assert.throws(()=>parseImport({...pc,software:'bad'}));assert.throws(()=>parseImport({...pc,hardware:{...pc.hardware,gpu:[{name:'x',vramMB:'bad'}]}}));assert.throws(()=>parseImport({schemaVersion:2}));
});
test('software search matches names, versions, and publishers regardless of case',()=>{const items=[{name:'Python',version:'3.12.3',publisher:'Python Foundation'},{name:'Node.js',version:'24.14',publisher:'OpenJS'}];assert.equal(filterSoftware(items,'PYTHON').length,1);assert.equal(filterSoftware(items,'24.14')[0].name,'Node.js');assert.equal(filterSoftware(items,'openjs')[0].name,'Node.js');assert.equal(filterSoftware(items,'not found').length,0);assert.equal(filterSoftware(items,'',false)[0].name,'Python');});
test('untrusted imported text is escaped and capacity conversion is deterministic',()=>{assert.equal(escapeHtml('<img src=x onerror="alert(1)">'), '&lt;img src=x onerror=&quot;alert(1)&quot;&gt;');assert.equal(capacity(48),'48 GB');assert.equal(capacity(2048),'2.00 TB');assert.equal(capacity(null),'—');});
