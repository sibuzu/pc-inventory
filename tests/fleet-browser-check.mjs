import {chromium} from 'playwright';
import assert from 'node:assert/strict';
const browser=await chromium.launch({channel:'msedge',headless:true});
const page=await browser.newPage({viewport:{width:1440,height:950}}),errors=[];
page.on('pageerror',error=>errors.push(error.message));
try{
  await page.goto('http://127.0.0.1:4173/#rtx_5090');await page.getByRole('heading',{name:'rtx_5090',exact:true}).waitFor();
  assert.match(await page.locator('#readyCount').innerText(),/05/);
  assert.equal(await page.locator('.machine-dot.ready').count(),5);
  assert.match(await page.locator('.hardware-grid').innerText(),/RTX 5090/);
  await page.getByRole('tab',{name:'系統環境',exact:true}).click();
  assert.match(await page.locator('.ai-inventory').innerText(),/13\.2/);
  assert.match(await page.locator('.ai-inventory').innerText(),/12\.8/);
  assert.match(await page.locator('.ai-table').innerText(),/2\.11\.0\+cu130/);
  await page.getByRole('tab',{name:'子系統',exact:true}).click();
  await page.locator('.branch-title').filter({hasText:/^容器$/}).click();
  assert.match(await page.locator('#tabPanel').innerText(),/26 個/);
  for(const name of ['pc_china','pc_sdl','pc_data','pc_rtx']){
    await page.getByRole('button',{name:new RegExp(name)}).click();await page.getByRole('heading',{name,exact:true}).waitFor();
    await page.getByRole('tab',{name:'系統環境',exact:true}).click();assert.ok(await page.locator('.ai-inventory').innerText());
  }
  await page.locator('#compareNav').click();assert.equal(await page.locator('.compare-table thead th').count(),7);
  assert.match(await page.locator('.compare-table').innerText(),/rtx_5090/);
  assert.deepEqual(errors,[]);console.log('Fleet browser check passed: five collected devices, CUDA/PyTorch, 5090 Docker inventory, six-device comparison.');
}finally{await browser.close();}
