import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {normalizeStorageSnapshots,normalizeSubsystems,mergeSnapshots,bytes} from '../dist/usage.mjs';
import {normalizeComputer,mergeComputers} from '../dist/inventory.mjs';
const pc=JSON.parse(fs.readFileSync(new URL('../dist/data/pc_china.json',import.meta.url),'utf8'));
const snapshot=pc.storageSnapshots[0];
test('real storage tree preserves usage and explicit partial/unscanned states',()=>{
  const result=normalizeStorageSnapshots([snapshot])[0];assert.equal(result.volumes.length,8);
  const c=result.volumes.find(v=>v.drive==='C:');assert.ok(c.tree.files>0);assert.equal(c.status,'partial');assert.ok(c.tree.children.length>0);
  const virtual=result.volumes.find(v=>v.drive==='H:');assert.equal(virtual.status,'not-scanned');assert.equal(virtual.tree,null);
  for(const volume of result.volumes){assert.ok(volume.usedBytes<=volume.sizeBytes);assert.ok(volume.freeBytes>=0);}
});
test('stopped WSL and offline Docker remain unknown instead of fabricated zero usage',()=>{
  const result=normalizeSubsystems(pc.subsystems);assert.equal(result.wsl.distributions.length,3);assert.equal(result.docker.status,'engine-unavailable');
  assert.ok(result.wsl.distributions.every(d=>d.state==='stopped'&&d.filesystem===null));assert.ok(result.wsl.distributions.every(d=>d.disks[0].allocatedBytes>0));
  assert.equal(result.docker.summary.length,0);assert.equal(result.wsl.distributions[0].osName,'Ubuntu-22.04');
});
test('old specification imports do not discard newer usage records',()=>{
  const baseline=normalizeComputer(pc),old={...pc};delete old.storageSnapshots;delete old.subsystems;
  const merged=mergeComputers([baseline],[old])[0];assert.equal(merged.storageSnapshots.length,1);assert.equal(merged.subsystems.id,baseline.subsystems.id);
});
test('snapshot histories de-duplicate by ID and retain latest twenty records',()=>{
  const values=Array.from({length:22},(_,index)=>({id:`s${index}`,capturedAt:new Date(Date.UTC(2026,9,18,index)).toISOString()}));
  const result=mergeSnapshots(values.slice(0,10),values.slice(5));assert.equal(result.length,20);assert.equal(result[0].id,'s2');assert.equal(result.at(-1).id,'s21');
});
test('malformed usage values and excessive depth are rejected before import',()=>{
  assert.throws(()=>normalizeStorageSnapshots([{...snapshot,volumes:[{...snapshot.volumes[0],sizeBytes:-1}]}]));
  let tree={name:'end',bytes:1,children:[]};for(let i=0;i<12;i++)tree={name:'folder',bytes:1,children:[tree]};
  assert.throws(()=>normalizeStorageSnapshots([{...snapshot,volumes:[{...snapshot.volumes[0],tree}]}]));
  assert.throws(()=>normalizeSubsystems({...pc.subsystems,capturedAt:'yesterday'}));assert.equal(bytes(1024**3),'1 GB');assert.equal(bytes(null),'未取得');
});
