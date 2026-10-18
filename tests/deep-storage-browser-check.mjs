import {chromium} from 'playwright';
import assert from 'node:assert/strict';
import fs from 'node:fs';
const threshold=5*1024**3;
const browser=await chromium.launch({channel:'msedge',headless:true});
const page=await browser.newPage({viewport:{width:1440,height:950}}),errors=[];
page.on('pageerror',error=>errors.push(error.message));
try{
  await page.goto('http://127.0.0.1:4173');
  await page.getByRole('heading',{name:'pc_china',exact:true}).waitFor();
  for(const id of ['pc_china','pc_sdl','pc_data','pc_rtx','rtx_5090']){
    const pc=JSON.parse(fs.readFileSync(new URL(`../dist/data/${id}.json`,import.meta.url),'utf8'));
    const latest=pc.storageSnapshots.at(-1);
    assert.equal(latest.expandThresholdBytes,threshold);
    assert.equal(latest.optionalDetailLevels,1);
    let deepest=[],optionalBranch;
    function audit(node,path=[],volume){
      if(node.kind==='directory'&&node.bytes>=threshold){
        assert.ok(node.children.length,`${id}: ${path.join('/')} must expand`);
        if(path.length>deepest.length)deepest=path;
      }
      if(path.length&&node.kind==='directory'&&node.bytes<threshold&&node.children.length&&(!optionalBranch||node.bytes>optionalBranch.bytes))optionalBranch={volume,path,bytes:node.bytes};
      if(node.children.length)assert.equal(node.children.reduce((n,c)=>n+c.bytes,0),node.bytes);
      for(const child of node.children)audit(child,[...path,child.name],volume);
    }
    let selectedVolume;
    for(const volume of latest.volumes.filter(v=>v.physical&&v.tree)){
      assert.equal(volume.tree.partial,false);
      const before=deepest;audit(volume.tree,[],volume);
      if(deepest!==before)selectedVolume=volume;
    }
    assert.ok(deepest.length>4,`${id}: a real branch beyond the old depth limit`);
    await page.getByRole('button',{name:new RegExp(id)}).click();
    await page.getByRole('tab',{name:'儲存空間',exact:true}).click();
    await page.getByText(/本次依 5 GB 門檻保留深層明細/).waitFor();
    async function expand(record,path){
      await page.locator('#collapseStorage').click();
      const volume=page.locator('.volume-node').filter({has:page.locator('.volume-name b').getByText(record.drive,{exact:true})});
      await volume.locator(':scope > summary').click();
      let container=volume.locator('.folder-list'),node=record.tree;
      for(const name of path){
        const index=node.children.findIndex(child=>child.name===name);
        const row=container.locator(':scope > .folder-node, :scope > .folder-leaf').nth(index);
        assert.ok((await row.innerText()).includes(name));
        await row.locator(':scope > summary').click();
        container=row.locator(':scope > .folder-children');
        await container.locator(':scope > .folder-node, :scope > .folder-leaf').first().waitFor();
        node=node.children[index];
      }
      assert.ok((await container.innerText()).includes(node.children[0].name.replace('[smaller folders / files]','較小檔案與資料夾合計')));
    }
    await expand(selectedVolume,deepest);
    assert.ok(optionalBranch,`${id}: smaller folders remain expandable`);
    await expand(optionalBranch.volume,optionalBranch.path);
    await page.setViewportSize({width:390,height:844});
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    await page.setViewportSize({width:1440,height:950});
    console.log(`${id}: expanded ${deepest.length} levels, plus a folder below 5 GB; mobile layout passed.`);
  }
  assert.deepEqual(errors,[]);
}finally{await browser.close();}
