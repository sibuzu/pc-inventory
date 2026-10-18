import {escapeHtml as e,capacity} from './inventory.mjs';

// Manufacturer limits are separate from detected hardware. No free disk port
// count is inferred from disk count: controllers, shared lanes and bays differ.
export const assessedAt='2026-10-18';
const source=(title,url)=>({title,url});
const profiles={
  china:{board:'MAG Z390M MORTAR (MS-7C00)',cpu:/i7-9700F/i,type:'DDR4 UDIMM',slots:4,maxGB:128,targets:[64,128],
    memoryOptions:['目前若仍為 16＋8＋16＋8 GB，可將兩條 8 GB 換成 16 GB，達到 64 GB。','128 GB 需換為 4×32 GB；購買前核對 BIOS 與記憶體 QVL。'],
    storageSummary:'2×M.2＋4×SATA；可換大 SSD 或評估加裝 SATA 硬碟。',
    storageOptions:['現有 Kingston A2000 與 Intel SSD 型號推估為兩顆 M.2 SSD；實際插槽位置待確認。','若 SATA 接孔、機殼硬碟架與電源有餘裕，可新增 SATA SSD／HDD；M.2／SATA 共用限制依手冊確認。','整併時可考慮將兩顆 8 TB HDD 移至 pc_rtx，先確認接孔、硬碟架、供電與資料備份。'],
    sources:[source('MSI 主機板規格','https://www.msi.com/Motherboard/MAG-Z390M-MORTAR/Specification'),source('Intel i7-9700F 規格','https://www.intel.com/content/www/us/en/products/sku/193738/intel-core-i79700f-processor-12m-cache-up-to-4-70-ghz/specifications.html')]},
  sdl:{board:'X99-DELUXE',cpu:/i7-5960X/i,type:'DDR4 UDIMM',slots:8,maxGB:64,targets:[],
    memoryOptions:['目前 CPU 官方規格與原廠手冊均列 64 GB 上限；不將更高容量列為已確認選項。','若要超過 64 GB，需另行驗證 CPU、BIOS、QVL；整併情境優先沿用其他工作站。'],
    storageSummary:'1×板載 M.2；另有 SATA，可新增資料碟或換大 NVMe。',
    storageOptions:['手冊列 8 個獨立 SATA 接孔及 2 個 SATA Express 接座（各可作 2 個 SATA）；實際可用接孔與硬碟架未盤點。','現有 1 顆 NVMe，尚未確認裝在板載 M.2 或 PCIe 轉接卡；可換大 NVMe 或評估 PCIe 轉接卡。','PCIe 轉接卡需核對插槽通道、顯示卡遮擋與開機支援；部分 SATA 接孔的 RAID 支援不同。'],
    sources:[source('ASUS X99-DELUXE 手冊','https://dlcdnets.asus.com/pub/ASUS/mb/LGA2011/X99-DELUXE/t9504_X99-DELUXE.pdf'),source('Intel i7-5960X 規格','https://www.intel.com/content/www/us/en/products/sku/82930/intel-core-i75960x-processor-extreme-edition-20m-cache-up-to-3-50-ghz/specifications.html')]},
  data:{model:'Inspiron 3891',cpu:/i7-11700/i,type:'DDR4 UDIMM',slots:2,maxGB:64,targets:[32,64],
    memoryOptions:['32 GB：換成 2×16 GB；64 GB：換成 2×32 GB。','目前兩條 8 GB 已占滿插槽，擴充需換條；此 i7 配置原廠列 DDR4-2933，非保證以模組標示的 3200 運作。'],
    storageSummary:'1×M.2 SSD＋1×3.5 吋 HDD 為官方配置；優先換大 SSD。',
    storageOptions:['現有 512 GB NVMe 與 2 TB HDD；可評估換大 M.2 2230／2280 NVMe。','原廠列出單顆 3.5 吋 HDD 搭配單顆 M.2 SSD；額外 SATA 裝置需查機殼支架、排線與電源。','原廠出貨容量清單不視為所有大容量硬碟的相容保證；購買前確認支援。'],
    sources:[source('Dell 記憶體規格','https://www.dell.com/support/manuals/en-us/inspiron-3891-desktop/inspiron-3891-setup-and-specifications/memory?guid=guid-e9d2ea83-38a4-431d-803c-96d63c1dbc34'),source('Dell 儲存配置','https://www.dell.com/support/manuals/en-uk/inspiron-3891-desktop/inspiron-3891-setup-and-specifications/storage?guid=guid-d79f17ca-e619-43e7-82a5-a0b0e7fb5c0a&lang=en-us')]},
  rtx:{board:'TUF GAMING Z490-PLUS',cpu:/i9-10900/i,type:'DDR4 UDIMM',slots:4,maxGB:128,targets:[],
    memoryOptions:['目前 4×32 GB 已達主機板官方 128 GB 上限；整併後可直接承接資料處理與多容器工作。','增加到 128 GB 以上需更換支援更大容量的平台。'],
    storageSummary:'2×M.2；可評估 PCIe 轉接卡或 SATA 擴充。',
    storageOptions:['兩顆 Samsung 970 PRO 推估占用兩個 M.2；可換大 NVMe，或新增 SATA SSD／HDD。','第二個長 PCIe 插槽為 Gen3 x4，可評估單顆 NVMe 轉接卡以保留原 SSD；是否空閒及被 RTX 3090 遮擋尚未確認。','6 個 SATA 接孔：M.2_2 有裝置時 SATA6G_5／6 停用；M.2_1 使用 SATA 模式時 SATA6G_2 停用。','若兩個 M.2 均使用 NVMe，依手冊推估可用 SATA 1–4；接線、其他裝置、機殼硬碟架與供電仍需現場確認。可評估接收 pc_china 的 8 TB HDD。'],
    sources:[source('ASUS Z490 規格','https://www.asus.com/us/motherboards-components/motherboards/tuf-gaming/tuf-gaming-z490-plus/techspec/'),source('ASUS 通道共用手冊','https://dlcdnets.asus.com/pub/ASUS/mb/LGA1200/TUF_GAMING_Z490-PLUS/E17046_TUF_GAMING_Z490-PLUS_UM_v3_WEB.pdf')]},
  flagship:{board:'X870 AORUS ELITE WIFI7 ICE',cpu:/Ryzen 7 9700X/i,type:'DDR5 UDIMM',slots:4,maxGB:256,targets:[128,192,256],conditional:true,
    memoryOptions:['整併優先評估 128 GB（2×64 GB 套組），購買前確認 CPU、BIOS 與 QVL。','192 GB（4×48 GB）或 256 GB（4×64 GB）屬較高容量選項；不代表目前 BIOS F4 已驗證支援。','4 條 DDR5 可能需要降低資料速率；不要假設維持目前 5600。DDR4 記憶體無法移用到此 DDR5 平台。'],
    storageSummary:'4×M.2＋4×SATA；部分 M.2 會使 GPU 改為 x8。',
    storageOptions:['優先確認現有兩顆 SSD 是否位於 M2A_CPU 與 M2D_SB，以避免使用與顯示卡共用的 M2B_CPU／M2C_CPU。Windows 控制器路徑已取得，但韌體插槽名稱無法直接對應 M.2 絲印。','M2B_CPU 或 M2C_CPU 安裝裝置時，主顯示卡插槽最高改為 x8；M2D_SB 占用時 PCIEX4 停用。','2026-10-18 NVIDIA 查詢回報 PCIe 目前 x8、硬體最大 x16；這是當次連線狀態，尚不能據此確認原因。','2026-10-18 Windows 只偵測兩顆 NVMe SSD，未偵測 SATA 磁碟或光碟機；4 個 SATA 接孔可評估新增 2.5 吋 SATA SSD／3.5 吋 HDD，但仍需確認固定位置、排線與供電。','主機板回報板本為 x.x；通道配置依 Rev.1.0／1.1 官方規格評估，採購前需核對實體板本與對應手冊。'],
    sources:[source('GIGABYTE X870 規格／通道配置','https://www.gigabyte.com/Motherboard/X870-AORUS-ELITE-WIFI7-ICE-rev-10-11/sp'),source('AMD 9700X 記憶體規格','https://www.amd.com/en/products/processors/desktops/ryzen/9000-series/amd-ryzen-7-9700X.html')]},
  one:{board:'Z97-C',cpu:/i7-4790\b/i,type:'DDR3 UDIMM',slots:4,maxGB:32,targets:[32],
    memoryOptions:['目前為 2×8 GB，推估尚有兩個插槽；可評估新增兩條相容的 8 GB DDR3，達到 32 GB。','此平台使用非 ECC、Unbuffered DDR3，無法沿用其他機器的 DDR4／DDR5；混插前核對電壓、時序與 QVL。'],
    storageSummary:'1×M.2＋6×SATA；M.2 與 SATA Express 共用頻寬。',
    storageOptions:['現有 Crucial MX500 1 TB SATA SSD 與 Seagate 1 TB HDD；未依磁碟數推定空閒接孔。','手冊列 4 個獨立 SATA 接孔及 1 個 SATA Express 接座（可作 2 個 SATA），新增磁碟前需確認接線、機殼硬碟架與供電。','板載 M.2 與 SATA Express 共用頻寬；NVMe 開機支援仍需確認 BIOS 與實際 SSD，不以 M.2 外觀保證相容。'],
    sources:[source('ASUS Z97-C 官方手冊','https://dlcdnet.asus.com/pub/ASUS/mb/LGA1150/Z97-C/E9184_Z97-C.pdf'),source('ASUS Z97-C 記憶體 QVL','https://www.asus.com/supportonly/z97-c/helpdesk_qvl/')]},
  nas:{nas:'TS-253D',cpu:/J4125/i,type:'DDR4 SO-DIMM',slots:2,maxGB:8,targets:[8],
    memoryOptions:['目前 1×4 GB，可加裝相同規格且符合 QNAP 相容要求的 4 GB，達到 2×4 GB。','官方上限 8 GB；未經官方驗證的 16／32 GB 不列為保證可用選項。'],
    storageSummary:'2 個硬碟槽；可換大硬碟，M.2 需另購相容 PCIe 卡。',
    storageOptions:['現有兩顆 8 TB HDD 組 RAID1，兩個槽位均已占用；沒有第三個內建硬碟槽。','先查儲存池配置：md1 約 7.27 TB，但主要已掛載磁碟區僅約 1.98 TB；未分配空間、快照保留與其他用途仍待確認。','需要增加實體容量時，可依 QTS「逐一更換硬碟」流程換成兩顆較大且相容的硬碟；每顆重建完成後再換下一顆，最後擴充容量，事前先備份。','沒有內建 M.2；可評估相容的 PCIe M.2 擴充卡（PCIe Gen2 x4，是否已有卡尚未盤點）。外接 USB 可作獨立儲存／備份，並不直接等同擴大原 RAID1。'],
    sources:[source('QNAP TS-253D 官方規格','https://www.qnap.com/en-us/product/ts-253d/specs/hardware'),source('QNAP 逐一換碟擴容','https://www.qnap.com/en/how-to/faq/article/how-do-i-expand-the-storage-pool-static-volume-by-replacing-disks-with-higher-capacity-drives-in-qts-443-or-later')]}
};
const canonical=value=>(value??'').trim().toUpperCase();
export function expansionAssessment(pc){
  const h=pc.hardware;if(!h)return null;
  const board=canonical(h.motherboard[0]?.product),model=canonical(h.model),cpu=h.cpu.map(x=>x.name).join(' ');
  const p=Object.values(profiles).find(p=>(p.board?board===canonical(p.board):p.nas?canonical(pc.nas?.model)===canonical(p.nas):model===canonical(p.model))&&p.cpu.test(cpu));
  if(!p)return {known:false,memorySummary:'待查：需確認主機板／CPU 的官方支援規格。',storageSummary:'待查：需確認主機板接孔與機殼配置。'};
  const installed=h.memory.filter(x=>x.capacityGB>0),complete=installed.length>0&&installed.reduce((n,x)=>n+x.capacityGB,0)===h.memoryGB;
  const free=complete&&installed.length<=p.slots?p.slots-installed.length:null;
  const targets=p.targets.filter(n=>n>h.memoryGB),atLimit=h.memoryGB>=p.maxGB;
  const memorySummary=atLimit?`${capacity(h.memoryGB)}，已達官方 ${p.maxGB} GB 上限。`:`${capacity(h.memoryGB)} → ${targets.length?targets.join(' / ')+' GB':'需核對配置'}；官方最高 ${p.maxGB} GB${p.conditional?'（需核對 BIOS／QVL）':''}。`;
  return {known:true,...p,installed:installed.length,free,atLimit,targets,memorySummary,storageSummary:p.storageSummary,
    slotSummary:`${p.slots} 槽 ${p.type} · 已偵測 ${installed.length} 條${free==null?' · 空槽未確認':` · 推估 ${free} 空槽`}`};
}
export function expansionSummary(pc,kind){const a=expansionAssessment(pc);return a?.[kind==='memory'?'memorySummary':'storageSummary']??'待盤點';}
export function expansionDetails(pc){
  const a=expansionAssessment(pc);if(!a?.known)return `<section class="expansion-section"><h3>擴充評估</h3><p>${e(a?.memorySummary??'待盤點')}</p></section>`;
  const list=items=>`<ul>${items.map(x=>`<li>${e(x)}</li>`).join('')}</ul>`;
  return `<section class="expansion-section"><div class="block-heading"><h3>擴充評估</h3><small>官方規格核對 ${assessedAt}</small></div><p class="compare-note">依目前盤點配置與原廠規格評估；空槽為模組數推估。儲存接孔的實際占用、機殼硬碟架及供電尚未完整確認。</p><div class="expansion-grid"><article><h4>記憶體擴充</h4><strong>${e(a.memorySummary)}</strong><p>${e(a.slotSummary)}</p>${list(a.memoryOptions)}</article><article><h4>儲存擴充</h4><strong>${e(a.storageSummary)}</strong><p>已盤點 ${pc.hardware.disks.filter(x=>x.mediaType!=='eMMC').length} 顆資料磁碟；不據此判定接孔空閒。</p>${list(a.storageOptions)}</article></div><details class="expansion-sources"><summary>官方依據與購買前確認</summary><p>上限為原廠規格，並非目前 BIOS 與所有模組組合均已實測。先核對實體板本、BIOS、QVL 與通道共用限制。</p><ul>${a.sources.map(s=>`<li><a href="${e(s.url)}" target="_blank" rel="noopener noreferrer">${e(s.title)} ↗</a></li>`).join('')}</ul></details></section>`;
}
