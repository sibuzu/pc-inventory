import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {normalizeComputer} from '../dist/inventory.mjs';
import {expansionAssessment,expansionDetails,expansionSummary} from '../dist/expansion.mjs';
const pc=id=>normalizeComputer(JSON.parse(fs.readFileSync(new URL(`../dist/data/${id}.json`,import.meta.url),'utf8')));
test('six machines use exact board/CPU limits, rather than generic chipset limits',()=>{
  const expected=[['pc_china',128,0],['pc_sdl',64,0],['pc_data',64,0],['pc_rtx',128,0],['rtx_5090',256,2],['pc_nas',8,1]];
  for(const [id,maxGB,free] of expected){const a=expansionAssessment(pc(id));assert.equal(a.known,true,id);assert.equal(a.maxGB,maxGB,id);assert.equal(a.free,free,id);assert.ok(a.sources.every(s=>s.url.startsWith('https://')));}
  assert.equal(expansionAssessment(pc('pc_sdl')).atLimit,true);
  assert.equal(expansionAssessment(pc('pc_rtx')).atLimit,true);
  assert.match(expansionSummary(pc('rtx_5090'),'memory'),/BIOS／QVL/);
});
test('incomplete DIMM inventory does not invent free slots and changed platforms lose the assessment',()=>{
  const incomplete=pc('pc_china');incomplete.hardware.memory=[];assert.equal(expansionAssessment(incomplete).free,null);
  const changed=pc('pc_rtx');changed.hardware.motherboard[0].product='Different board';assert.equal(expansionAssessment(changed).known,false);
  changed.hardware.motherboard[0].product='TUF GAMING Z490-PLUS';changed.hardware.cpu[0].name='Different CPU';assert.equal(expansionAssessment(changed).known,false);
  assert.equal(expansionSummary({status:'pending'},'storage'),'待盤點');
});
test('expansion details expose lane conflicts and NAS capacity uncertainty',()=>{
  assert.match(expansionDetails(pc('pc_rtx')),/SATA6G_5／6 停用/);
  assert.match(expansionDetails(pc('rtx_5090')),/M2B_CPU.*M2C_CPU/);
  assert.match(expansionDetails(pc('rtx_5090')),/最高改為 x8/);
  assert.match(expansionDetails(pc('pc_nas')),/7.27 TB.*1.98 TB/);
  assert.match(expansionDetails(pc('pc_nas')),/沒有第三個內建硬碟槽/);
});
