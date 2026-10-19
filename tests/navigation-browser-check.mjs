import {chromium} from 'playwright';
import assert from 'node:assert/strict';
const browser=await chromium.launch({channel:'msedge',headless:true});
const page=await browser.newPage(),errors=[];
page.on('pageerror',error=>errors.push(error.message));
const base=process.env.TEST_BASE_URL??'http://127.0.0.1:4173/';
async function goto(route){await page.goto(base+route);}
async function selected(id,tab){await page.getByRole('heading',{name:id,exact:true}).waitFor();await page.locator(`#tab-${tab}[aria-selected="true"]`).waitFor();}
try{
  await goto('');await page.locator('.compare-table').waitFor();
  const purposes=await page.locator('.compare-table tbody tr').first().locator('td').allTextContents();
  assert.equal(purposes[6],'信嘉/大尾備援');assert.equal(purposes[7],'宸宇工作機');
  await goto('#pc_china/storage');await selected('pc_china','storage');
  await page.reload();await selected('pc_china','storage');
  await goto('?pc=PC-CHINA&tab=storage');await selected('pc_china','storage');
  await goto('#PC-CHINA/storage');await selected('pc_china','storage');
  for(const tab of ['overview','hardware','software','subsystems','system']){await goto('#pc_andy/'+tab);await selected('pc_andy',tab);}
  await goto('#pc_one');await selected('pc_one','overview');
  await page.locator('#tab-storage').click();assert.ok(page.url().endsWith('#pc_one/storage'));
  await page.locator('#compareNav').click();assert.ok(page.url().endsWith('#compare'));await page.locator('.compare-table').waitFor();
  await page.goBack();await selected('pc_one','storage');
  await page.goBack();await selected('pc_one','overview');
  await page.goForward();await selected('pc_one','storage');
  await goto('?view=compare');await page.locator('.compare-table').waitFor();
  await page.getByRole('button',{name:/pc_andy/}).click();await selected('pc_andy','overview');
  assert.ok(page.url().endsWith('#pc_andy'));assert.ok(!new URL(page.url()).searchParams.has('view'));
  assert.deepEqual(errors,[]);console.log('Navigation passed: default comparison, work purposes, all tabs, query/hash links, reload and back/forward.');
}finally{await browser.close();}
