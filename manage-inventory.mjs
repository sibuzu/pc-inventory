import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {parseImport,mergeComputers} from './dist/inventory.mjs';
const input=process.argv[2];
if(!input){console.error('Usage: node manage-inventory.mjs <computer-or-inventory.json>');process.exit(1);}
try{
  const computers=parseImport(JSON.parse(fs.readFileSync(input,'utf8').replace(/^\uFEFF/,'')));
  const dataDir=fileURLToPath(new URL('./dist/data/',import.meta.url));
  const indexPath=path.join(dataDir,'index.json');
  const files=new Set(JSON.parse(fs.readFileSync(indexPath,'utf8')));
  for(const pc of computers){const file=`${pc.id}.json`,target=path.join(dataDir,file);const previous=fs.existsSync(target)?parseImport(JSON.parse(fs.readFileSync(target,'utf8'))):[];const merged=mergeComputers(previous,[pc])[0];fs.writeFileSync(target,JSON.stringify(merged,null,2)+'\n');files.add(file);}
  fs.writeFileSync(indexPath,JSON.stringify([...files],null,2)+'\n');
  console.log(`已更新網站內建資料：${computers.map(x=>x.id).join(', ')}`);
}catch(error){console.error(`更新失敗：${error.message}`);process.exit(1);}
