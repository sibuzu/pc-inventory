// Optional snapshot fields keep older PC specification files compatible.
const isObject=x=>x!==null&&typeof x==='object'&&!Array.isArray(x);
const obj=x=>{if(!isObject(x))throw new Error('快照物件格式錯誤');return x;};
const str=x=>{if(x==null)return '';if(typeof x!=='string')throw new Error('快照文字格式錯誤');return x.slice(0,1500);};
const num=x=>{if(x==null)return null;if(typeof x!=='number'||!Number.isFinite(x)||x<0)throw new Error('快照容量格式錯誤');return x;};
const array=(x,max=5000)=>{if(x==null)return [];if(!Array.isArray(x)||x.length>max)throw new Error('快照清單格式錯誤或過大');return x;};
const when=x=>{if(typeof x!=='string'||!Number.isFinite(Date.parse(x)))throw new Error('快照時間格式錯誤');return x;};
function metadata(x){obj(x);const id=str(x.id);if(!/^[a-zA-Z0-9_-]{1,80}$/.test(id))throw new Error('快照識別碼格式錯誤');return {id,capturedAt:when(x.capturedAt),completedAt:x.completedAt?when(x.completedAt):x.capturedAt};}
function disk(x){obj(x);return {fileName:str(x.fileName),fileBytes:num(x.fileBytes),allocatedBytes:num(x.allocatedBytes)};}
function node(x,depth,budget){obj(x);if(depth>64||--budget.count<0)throw new Error('快照樹狀清單過深或過大');return {name:str(x.name),...(['directory','file','aggregate'].includes(x.kind)?{kind:x.kind}:{}),bytes:num(x.bytes),files:num(x.files),directories:num(x.directories),errors:num(x.errors),skipped:num(x.skipped),partial:x.partial===true,truncated:x.truncated===true,...(x.durationSeconds==null?{}:{durationSeconds:num(x.durationSeconds)}),children:array(x.children,10000).map(c=>node(c,depth+1,budget))};}
export function normalizeStorageSnapshots(input){
  const budget={count:300000};
  return array(input,20).map(x=>({...metadata(x),maxDepth:num(x.maxDepth),...(x.optionalDetailLevels==null?{}:{optionalDetailLevels:num(x.optionalDetailLevels)}),...(x.expandThresholdBytes==null?{}:{expandThresholdBytes:num(x.expandThresholdBytes)}),volumes:array(x.volumes,256).map(v=>{obj(v);return {drive:str(v.drive),fileSystem:str(v.fileSystem),sizeBytes:num(v.sizeBytes),freeBytes:num(v.freeBytes),usedBytes:num(v.usedBytes),physical:v.physical===true,status:['complete','partial','not-scanned'].includes(v.status)?v.status:'not-scanned',tree:v.tree==null?null:node(v.tree,0,budget)};})}));
}
export function normalizeEnvironmentSnapshots(input){return array(input,20).map(x=>{
  const base=metadata(x),w=obj(x.wsl),d=obj(x.docker);
  return {...base,wsl:{available:w.available===true,status:str(w.status),distributions:array(w.distributions,256).map(v=>{obj(v);return {name:str(v.name),version:num(v.version),state:str(v.state),osName:str(v.osName||v.name),osSource:str(v.osSource),disks:array(v.disks,32).map(disk),filesystem:v.filesystem==null?null:{sizeBytes:num(obj(v.filesystem).sizeBytes),usedBytes:num(v.filesystem.usedBytes),freeBytes:num(v.filesystem.freeBytes)}};})},
    docker:{available:d.available===true,status:str(d.status),context:str(d.context),operatingSystem:str(d.operatingSystem),osType:str(d.osType),architecture:str(d.architecture),kernelVersion:str(d.kernelVersion),serverVersion:str(d.serverVersion),disks:array(d.disks,128).map(disk),
      summary:array(d.summary,32).map(v=>{obj(v);return {type:str(v.type),totalCount:str(v.totalCount),active:str(v.active),size:str(v.size),reclaimable:str(v.reclaimable)};}),
      containers:array(d.containers).map(v=>{obj(v);return {name:str(v.name),image:str(v.image),state:str(v.state),status:str(v.status),size:str(v.size)};}),
      images:array(d.images).map(v=>{obj(v);return {repository:str(v.repository),tag:str(v.tag),id:str(v.id),size:str(v.size),created:str(v.created),os:str(v.os),architecture:str(v.architecture),sizeBytes:num(v.sizeBytes)};}),
      volumes:array(d.volumes).map(v=>{obj(v);return {name:str(v.name),driver:str(v.driver),scope:str(v.scope),sizeBytes:num(v.sizeBytes),refCount:num(v.refCount)};}),warnings:array(d.warnings,50).map(str)}};
});}
export function normalizeSubsystems(value){return value==null?null:normalizeEnvironmentSnapshots([value])[0];}
export function mergeSnapshots(before=[],after=[]){const map=new Map(before.map(x=>[x.id,x]));for(const item of after)map.set(item.id,item);return [...map.values()].sort((a,b)=>Date.parse(a.capturedAt)-Date.parse(b.capturedAt)).slice(-20);}
export function bytes(value){if(value==null)return '未取得';if(value===0)return '0 B';const units=['B','KB','MB','GB','TB','PB'];const index=Math.min(units.length-1,Math.floor(Math.log(value)/Math.log(1024)));return `${Number((value/1024**index).toFixed(index>1?2:0))} ${units[index]}`;}
export function usedStorageBytes(pc){const snapshots=pc.storageSnapshots??[];if(!snapshots.length)return null;const latest=snapshots.reduce((a,b)=>Date.parse(a.capturedAt)>=Date.parse(b.capturedAt)?a:b);const volumes=latest.volumes.filter(x=>x.physical&&x.usedBytes!=null);return volumes.length?volumes.reduce((sum,x)=>sum+x.usedBytes,0):null;}
export function storageUsageLabel(pc){
  const snapshots=pc.storageSnapshots??[];if(!snapshots.length)return '未取得';
  const latest=snapshots.reduce((a,b)=>Date.parse(a.capturedAt)>=Date.parse(b.capturedAt)?a:b);
  const volumes=latest.volumes.filter(v=>v.physical),used=usedStorageBytes(pc);
  if(used==null)return '未取得';
  const total=volumes.reduce((n,v)=>n+(v.sizeBytes??0),0);
  const complete=volumes.every(v=>v.sizeBytes!=null&&v.usedBytes!=null);
  return `${bytes(used)}${complete&&total>0?` (${Math.round(used/total*100)}%)`:''}`;
}
export function storageReconciliation(volume){
  const tree=volume.tree;if(!tree)return null;
  const difference=volume.usedBytes==null||tree.bytes==null?null:volume.usedBytes-tree.bytes;
  return {state:tree.partial?'逾時，僅掃描部分目錄':tree.errors?'可讀目錄走訪結束，部分項目無法讀取':'可讀目錄走訪完成',
    label:difference==null?'系統已用與檔案合計差額':difference>=0?'系統已用減去檔案合計':'檔案合計超出系統已用',
    difference:difference==null?null:Math.abs(difference),timedOut:tree.partial===true};
}
