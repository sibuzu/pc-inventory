import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {hardwareYearAssessment,hardwareYearLabel} from '../dist/hardware-year.mjs';
const pc=id=>JSON.parse(fs.readFileSync(new URL(`../dist/data/${id}.json`,import.meta.url),'utf8'));
test('configuration years include newer GPUs while preserving the older platform year',()=>{
  const expected=[['pc_china',2019,2019],['pc_sdl',2016,2014],['pc_data',2021,2021],['pc_rtx',2020,2020],['rtx_5090',2025,2024],['pc_one',2017,2014],['pc_andy',2019,2019],['pc_nas',2020,2020]];
  for(const [id,year,platformYear] of expected){const a=hardwareYearAssessment(pc(id));assert.equal(a.year,year,id);assert.equal(a.platformYear,platformYear,id);assert.ok(a.parts.every(x=>x.url.startsWith('https://')));}
});
test('unknown components do not reuse a machine ID estimate; virtual displays are ignored',()=>{
  const machine=pc('pc_andy');machine.hardware.gpu.push({name:'Unknown remote GPU',virtual:true});assert.equal(hardwareYearAssessment(machine).year,2019);
  machine.hardware.gpu.push({name:'Unknown physical GPU',virtual:false});assert.equal(hardwareYearAssessment(machine).year,null);
  const changed=pc('pc_one');changed.hardware.motherboard[0].product='Unknown board';assert.equal(hardwareYearAssessment(changed).year,null);
  assert.equal(hardwareYearLabel({status:'pending'}),'待確認');
});
