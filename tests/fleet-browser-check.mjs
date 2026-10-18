import {chromium} from 'playwright';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {plannedNames} from '../dist/inventory.mjs';
const files=JSON.parse(fs.readFileSync(new URL('../dist/data/index.json',import.meta.url),'utf8'));
const browser=await chromium.launch({channel:'msedge',headless:true});
const page=await browser.newPage({viewport:{width:1440,height:950}}),errors=[];
page.on('pageerror',error=>errors.push(error.message));
try{
  await page.goto('http://127.0.0.1:4173/#rtx_5090');await page.getByRole('heading',{name:'rtx_5090',exact:true}).waitFor();
  assert.match(await page.locator('#readyCount').innerText(),new RegExp(String(files.length).padStart(2,'0')));
  assert.equal(await page.locator('.machine-dot.ready').count(),files.length);
  assert.deepEqual(await page.locator('.machine-name').allTextContents(),plannedNames);
  assert.deepEqual(plannedNames.slice(-3),['pc_one','pc_andy','pc_nas']);
  assert.match(await page.locator('.hardware-grid').innerText(),/RTX 5090/);
  await page.getByRole('tab',{name:'系統環境',exact:true}).click();
  assert.match(await page.locator('.ai-inventory').innerText(),/13\.2/);
  assert.match(await page.locator('.ai-inventory').innerText(),/12\.8/);
  assert.match(await page.locator('.ai-table').innerText(),/2\.11\.0\+cu130/);
  await page.getByRole('tab',{name:'子系統',exact:true}).click();
  await page.locator('.branch-title').filter({hasText:/^容器$/}).click();
  assert.match(await page.locator('#tabPanel').innerText(),/26 個/);
  for(const name of ['pc_china','pc_sdl','pc_data','pc_rtx','pc_nas']){
    await page.getByRole('button',{name:new RegExp(name)}).click();await page.getByRole('heading',{name,exact:true}).waitFor();
    await page.getByRole('tab',{name:'系統環境',exact:true}).click();assert.ok(await page.locator('.ai-inventory').innerText());
  }
  await page.getByRole('button',{name:/pc_one/}).click();await page.getByRole('heading',{name:'pc_one',exact:true}).waitFor();
  if(files.includes('pc_one.json')){
    await page.getByRole('tab',{name:'總覽',exact:true}).click();
    assert.match(await page.locator('.hardware-grid').innerText(),/i7-4790/);
    assert.match(await page.locator('.hardware-grid').innerText(),/GTX 1080 Ti/);
    await page.getByRole('tab',{name:'系統環境',exact:true}).click();
    assert.match(await page.locator('.ai-inventory').innerText(),/12\.6/);
    await page.getByText('盤點範圍與限制',{exact:true}).click();
    assert.match(await page.locator('.ai-inventory').innerText(),/temporary Python runtime/);
    await page.getByRole('tab',{name:'儲存空間',exact:true}).click();
    await page.getByText(/本次依 5 GB 門檻保留深層明細/).waitFor();
    await page.getByRole('tab',{name:'硬體規格',exact:true}).click();
    assert.match(await page.locator('.expansion-section').innerText(),/DDR3 UDIMM/);
  }
  else await page.getByText('尚未匯入',{exact:true}).waitFor();
  await page.getByRole('button',{name:/pc_andy/}).click();await page.getByRole('heading',{name:'pc_andy',exact:true}).waitFor();
  if(files.includes('pc_andy.json')){
    await page.getByRole('tab',{name:'總覽',exact:true}).click();
    assert.ok(await page.locator('.hardware-grid').count());
    await page.getByRole('tab',{name:'系統環境',exact:true}).click();
    assert.ok(await page.locator('.ai-inventory').innerText());
    await page.getByRole('tab',{name:'儲存空間',exact:true}).click();
    await page.getByText(/本次依 5 GB 門檻保留深層明細/).waitFor();
  }else await page.getByText('尚未匯入',{exact:true}).waitFor();
  await page.locator('#compareNav').click();assert.equal(await page.locator('.compare-table thead th').count(),plannedNames.length+1);
  assert.match(await page.locator('.compare-table').innerText(),/rtx_5090/);
  assert.deepEqual(errors,[]);console.log('Fleet browser check passed: device count, pc_one / pc_andy / pc_nas order, CUDA/PyTorch, Docker and comparison.');
}finally{await browser.close();}
