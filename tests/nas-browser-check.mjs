import {chromium} from 'playwright';
import assert from 'node:assert/strict';
const browser=await chromium.launch({channel:'msedge',headless:true});
const page=await browser.newPage({viewport:{width:1440,height:950}}),errors=[];
page.on('pageerror',error=>errors.push(error.message));
try{
  await page.goto('http://127.0.0.1:4173/#pc_nas');
  await page.getByRole('heading',{name:'pc_nas',exact:true}).waitFor();
  assert.match(await page.locator('#deviceView').innerText(),/TS-253D/);
  await page.getByRole('tab',{name:'儲存空間',exact:true}).click();
  assert.match(await page.locator('.nas-storage').innerText(),/最大 RAID 陣列容量/);
  await page.getByText('RAID 陣列明細',{exact:true}).click();
  assert.match(await page.locator('.nas-storage table').innerText(),/md1 · RAID1/);
  const volume=page.locator('.volume-node').filter({hasText:'/share/CACHEDEV1_DATA'});
  await volume.locator(':scope > summary').click();assert.ok(await volume.locator('.folder-node').count()>0);
  await page.locator('#compareNav').click();
  const rows=page.locator('.compare-table tbody tr');
  assert.equal(await rows.first().locator('td').first().innerText(),'工作用途');
  assert.deepEqual(await rows.first().locator('td').allTextContents(),['工作用途','模型訓練','深度沖模型回測','歷史資料整理','程式開發機1','程式開發機2','信嘉/大尾備援','宸宇工作機','NAS']);
  const labels=await rows.locator('td:first-child').allTextContents();
  assert.equal(labels[labels.indexOf('實體儲存')+1],'已用儲存');
  const used=rows.filter({has:page.getByText('已用儲存',{exact:true})});
  assert.equal(await used.locator('td').count(),9);assert.doesNotMatch(await used.locator('td').last().innerText(),/待匯入/);
  assert.deepEqual(errors,[]);console.log('NAS, assigned work purposes, and used-storage comparison browser checks passed.');
}finally{await browser.close();}
