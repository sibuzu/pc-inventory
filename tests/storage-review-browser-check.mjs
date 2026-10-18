import {chromium} from 'playwright';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {bytes,usedStorageBytes,storageUsageLabel} from '../dist/usage.mjs';
const browser=await chromium.launch({channel:'msedge',headless:true});
const page=await browser.newPage({viewport:{width:1440,height:950}}),errors=[];
page.on('pageerror',error=>errors.push(error.message));
try{
  await page.goto('http://127.0.0.1:4173');await page.getByRole('heading',{name:'pc_china',exact:true}).waitFor();
  for(const id of ['pc_china','pc_sdl','pc_data','pc_rtx','rtx_5090']){
    const pc=JSON.parse(fs.readFileSync(new URL(`../dist/data/${id}.json`,import.meta.url),'utf8'));
    await page.getByRole('button',{name:new RegExp(id)}).click();
    await page.getByRole('tab',{name:'儲存空間',exact:true}).click();
    assert.match(await page.locator('.usage-metrics').innerText(),new RegExp(bytes(usedStorageBytes(pc)).replace('.','\\.')));
    const latest=pc.storageSnapshots.at(-1);assert.ok(latest.volumes.filter(v=>v.physical).every(v=>!v.tree.partial));
    await page.locator('.volume-node > summary').first().click();
    assert.match(await page.locator('.volume-node[open]').innerText(),/已掃描可讀檔案（邏輯大小）/);
    assert.equal(await page.locator('.usage-alert').count(),0);
    if(id==='pc_china'){
      const d=page.locator('.volume-node').filter({has:page.locator('.volume-name b').getByText('D:',{exact:true})});
      await d.locator(':scope > summary').click();
      const dSnapshot=latest.volumes.find(volume=>volume.drive==='D:');
      for(const child of dSnapshot.tree.children.slice(0,3)){
        assert.ok((await d.innerText()).includes(child.name));
      }
      assert.match(await page.locator('.volume-node[open]').first().innerText(),/部分項目無法讀取/);
      assert.ok(await page.locator('#storageSnapshot option').count()>=2);
    }
  }
  await page.locator('#compareNav').click();
  const used=page.locator('.compare-table tbody tr').filter({has:page.getByText('已用儲存',{exact:true})});
  const cells=await used.locator('td').allTextContents();assert.equal(cells.length,7);
  const china=JSON.parse(fs.readFileSync(new URL('../dist/data/pc_china.json',import.meta.url),'utf8'));
  assert.equal(cells[1],storageUsageLabel(china));assert.ok(cells.slice(1).every(value=>/\(\d+%\)$/.test(value)));
  assert.deepEqual(errors,[]);console.log('Five-PC storage review: latest snapshots, system used totals, no timeout, top folders, restricted items and history passed.');
}finally{await browser.close();}
