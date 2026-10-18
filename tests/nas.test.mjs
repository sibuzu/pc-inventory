import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {normalizeComputer,mergeComputers} from '../dist/inventory.mjs';
import {usedStorageBytes} from '../dist/usage.mjs';
const raw=JSON.parse(fs.readFileSync(new URL('../dist/data/pc_nas.json',import.meta.url),'utf8'));
test('QNAP inventory distinguishes DIMMs, mirrored disks, RAID and mounted filesystems',()=>{
  const pc=normalizeComputer(raw);
  assert.equal(pc.nas.model,'TS-253D');assert.equal(pc.hardware.memoryGB,4);
  assert.equal(pc.hardware.memory[0].speedUnit,'MT/s');assert.equal(pc.software.length,13);
  assert.equal(pc.hardware.disks.filter(d=>d.mediaType==='HDD').length,2);
  const raid=pc.nas.arrays.find(a=>a.name==='md1');assert.equal(raid.level,'raid1');assert.equal(raid.members.length,2);
  const latest=pc.storageSnapshots.at(-1),volume=latest.volumes.find(v=>v.drive==='/share/CACHEDEV1_DATA');
  assert.ok(raid.sizeBytes>volume.sizeBytes);assert.ok(volume.tree.children.length>0);
  assert.ok(usedStorageBytes(pc)>=volume.usedBytes);assert.ok(usedStorageBytes(pc)<raid.sizeBytes);
});
test('used storage selects newest snapshot and excludes virtual and unknown volumes',()=>{
  const snapshots=[{capturedAt:'2026-10-18T01:00:00Z',volumes:[{physical:true,usedBytes:20},{physical:false,usedBytes:1000},{physical:true,usedBytes:null}]},{capturedAt:'2026-10-17T01:00:00Z',volumes:[{physical:true,usedBytes:99}]}];
  assert.equal(usedStorageBytes({storageSnapshots:snapshots}),20);
  assert.equal(usedStorageBytes({}),null);
});
test('work purpose starts blank and survives rescans, while an explicit blank can clear it',()=>{
  assert.equal(raw.workPurpose,'');const prior=normalizeComputer({...raw,workPurpose:'資料備份'});
  const incoming={...raw};delete incoming.workPurpose;
  assert.equal(mergeComputers([prior],[incoming])[0].workPurpose,'資料備份');
  assert.equal(mergeComputers([prior],[raw])[0].workPurpose,'');
});
