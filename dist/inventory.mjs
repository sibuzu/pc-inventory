import {normalizeStorageSnapshots,normalizeSubsystems,mergeSnapshots} from './usage.mjs';
import {normalizeAi,mergeAi} from './ai.mjs';
import {normalizeNas} from './nas.mjs';
export const plannedNames = ['pc_china','pc_sdl','pc_data','pc_rtx','rtx_5090','pc_one','pc_andy','pc_david','pc_nas'];
const record = value => value !== null && typeof value === 'object' && !Array.isArray(value);
function text(value, fallback = '') { if(value == null)return fallback;if(typeof value !== 'string')throw new Error('文字欄位格式錯誤');return value.slice(0,1500); }
function number(value) {if(value == null)return null;if(typeof value !== 'number'||!Number.isFinite(value)||value<0)throw new Error('數值欄位格式錯誤');return value;}
function object(value) {if(value == null)return {};if(!record(value))throw new Error('規格欄位必須為物件');return value;}
function list(value,mapper,max=5000) {if(value == null)return [];if(!Array.isArray(value)||value.length>max)throw new Error('清單格式錯誤或筆數過多');return value.map(v=>mapper(object(v)));}
export function normalizeComputer(value) {
  if(!record(value)||value.schemaVersion!==1)throw new Error('不支援的規格檔案，請使用 collect-pc.ps1 產生 JSON');
  const id=text(value.id);
  if(!/^[a-zA-Z0-9_-]{1,48}$/.test(id))throw new Error('電腦名稱僅可使用英文字母、數字、底線與連字號');
  if(!record(value.hardware)||!record(value.os))throw new Error('規格檔案缺少硬體或系統資料');
  const h=value.hardware,os=value.os,bios=object(h.bios);
  if(typeof value.collectedAt!=='string'||!Number.isFinite(Date.parse(value.collectedAt)))throw new Error('擷取時間格式錯誤');
  return {schemaVersion:1,id,name:id,status:'collected',collectedAt:value.collectedAt,source:text(value.source,'匯入 JSON'),workPurpose:value.workPurpose==null?null:text(value.workPurpose),
    hardware:{manufacturer:text(h.manufacturer),model:text(h.model),memoryGB:number(h.memoryGB),memorySource:text(h.memorySource),
      cpu:list(h.cpu,x=>({name:text(x.name),cores:number(x.cores),threads:number(x.threads),maxClockMHz:number(x.maxClockMHz)}),32),
      memory:list(h.memory,x=>({capacityGB:number(x.capacityGB),speedMHz:number(x.speedMHz),configuredMHz:number(x.configuredMHz),speedUnit:text(x.speedUnit),manufacturer:text(x.manufacturer),partNumber:text(x.partNumber),slot:text(x.slot)}),128),
      gpu:list(h.gpu,x=>({name:text(x.name),driver:text(x.driver),vramMB:number(x.vramMB),virtual:x.virtual===true}),64),
      motherboard:list(h.motherboard,x=>({manufacturer:text(x.manufacturer),product:text(x.product),version:text(x.version)}),16),
      bios:{manufacturer:text(bios.manufacturer),version:text(bios.version)},
      disks:list(h.disks,x=>({name:text(x.name),sizeGB:number(x.sizeGB),interface:text(x.interface),mediaType:text(x.mediaType)}),256),
      volumes:list(h.volumes,x=>({drive:text(x.drive),fileSystem:text(x.fileSystem),sizeGB:number(x.sizeGB),freeGB:number(x.freeGB)}),256),
      network:list(h.network,x=>({name:text(x.name),connected:x.connected===true,speedMbps:number(x.speedMbps)}),256)},
    os:{name:text(os.name),version:text(os.version),build:text(os.build),architecture:text(os.architecture)},
    software:list(value.software,x=>({name:text(x.name),version:text(x.version),publisher:text(x.publisher)})),
    tools:list(value.tools,x=>({name:text(x.name),version:text(x.version)}),256),
    storageSnapshots:normalizeStorageSnapshots(value.storageSnapshots),subsystems:normalizeSubsystems(value.subsystems),ai:normalizeAi(value.ai),nas:normalizeNas(value.nas),
    warnings:Array.isArray(value.warnings)?value.warnings.filter(x=>typeof x==='string').slice(0,50):[]};
}
export function parseImport(payload) {
  const values=Array.isArray(payload)?payload:payload?.computers??[payload];
  if(!Array.isArray(values)||!values.length||values.length>100)throw new Error('請匯入 1 至 100 台電腦的規格');
  return values.map(normalizeComputer);
}
export function mergeComputers(existing,incoming) {const validated=parseImport(incoming);const map=new Map(existing.map(x=>[x.id,x]));for(const pc of validated){const prior=map.get(pc.id);const subsystems=!pc.subsystems||(prior?.subsystems&&Date.parse(prior.subsystems.capturedAt)>Date.parse(pc.subsystems.capturedAt))?prior?.subsystems??null:pc.subsystems;map.set(pc.id,{...pc,workPurpose:pc.workPurpose??prior?.workPurpose??'',storageSnapshots:mergeSnapshots(prior?.storageSnapshots,pc.storageSnapshots),subsystems,ai:mergeAi(prior?.ai,pc.ai)});}return [...map.values()];}
export function withPlanned(computers) {const map=new Map(computers.map(x=>[x.id,x]));return [...plannedNames.map(id=>map.get(id)??{id,name:id,status:'pending'}),...computers.filter(x=>!plannedNames.includes(x.id))];}
export function filterSoftware(items,query,ascending=true) {const q=query.toLocaleLowerCase().trim();return items.filter(x=>[x.name,x.version,x.publisher].some(s=>(s||'').toLocaleLowerCase().includes(q))).sort((a,b)=>(ascending?1:-1)*a.name.localeCompare(b.name,'zh-Hant'));}
export function escapeHtml(value) {return String(value??'—').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
export function capacity(value) {if(value==null)return '—';return value>=1024?`${(value/1024).toFixed(2)} TB`:`${Number(value.toFixed(1))} GB`;}
export function primaryGpu(pc) {return pc.hardware?.gpu.find(g=>!g.virtual&&/nvidia|geforce|quadro|tesla/i.test(g.name))??pc.hardware?.gpu.find(g=>!g.virtual)??pc.hardware?.gpu[0];}
