// Release years describe the detected configuration, never purchase dates.
const item=(match,year,url)=>({match,year,url});
const cpus=[
  item(/\bi7-9700F\b/i,2019,'https://www.intel.com/content/www/us/en/ark/products/series/134907/9th-generation-intel-core-i7-processors.html'),
  item(/\bi7-5960X\b/i,2014,'https://www.intel.com/content/www/us/en/ark/products/codename/79427/products-formerly-haswell-e.html'),
  item(/\bi7-11700\b/i,2021,'https://www.intel.com/content/www/us/en/products/sku/212279/intel-core-i711700-processor-16m-cache-up-to-4-90-ghz/specifications.html'),
  item(/\bi9-10900\b/i,2020,'https://www.intel.com/content/www/us/en/ark/products/series/195735/10th-generation-intel-core-i9-processors.html'),
  item(/\bRyzen 7 9700X\b/i,2024,'https://www.amd.com/en/products/processors/desktops/ryzen/9000-series/amd-ryzen-7-9700X.html'),
  item(/\bi7-4790\b/i,2014,'https://www.intel.com/content/www/us/en/products/sku/80806/intel-core-i74790-processor-8m-cache-up-to-4-00-ghz/specifications.html'),
  item(/\bRyzen 7 3700X\b/i,2019,'https://www.amd.com/en/newsroom/press-releases/2019-5-26-amd-announces-next-generation-leadership-products.html'),
  item(/\bJ4125\b/i,2019,'https://www.intel.com/content/www/us/en/products/sku/197305/intel-celeron-processor-j4125-4m-cache-up-to-2-70-ghz/specifications.html')
];
const boards=[
  item(/^MAG Z390M MORTAR \(MS-7C00\)$/i,2018,'https://uk.msi.com/Landing/intel-z390-gaming-motherboard'),
  item(/^X99-DELUXE$/i,2014,'https://rog.asus.com/articles/product-news/press-release-asus-announces-x99-deluxe-x99-pro-and-x99-a-motherboards/'),
  item(/^TUF GAMING Z490-PLUS$/i,2020,'https://www.asus.com/us/news/ksccz0nd7qdmlads/'),
  item(/^X870 AORUS ELITE WIFI7 ICE$/i,2024,'https://www.gigabyte.com/eu/press/news/2225'),
  item(/^Z97-C$/i,2014,'https://rog.asus.com/articles/product-news/asus-unveils-full-range-of-z97-and-h97-motherboards/'),
  item(/^ROG CROSSHAIR VIII HERO \(WI-FI\)$/i,2019,'https://rog.asus.com/in/articles/gaming-motherboards/ryzen-to-the-challenge-the-rog-x570-motherboard-guide/')
];
const gpus=[
  item(/\bGTX 1080 Ti\b/i,2017,'https://nvidianews.nvidia.com/news/nvidia-introduces-the-beastly-geforce-gtx-1080-ti-fastest-gaming-gpu-ever'),
  item(/\bGTX 1080$/i,2016,'https://nvidianews.nvidia.com/news/a-quantum-leap-in-gaming%3A-nvidia-introduces-geforce-gtx-1080'),
  item(/\bGTX 1050 Ti\b/i,2016,'https://nvidianews.nvidia.com/news/nvidia-powers-new-class-of-sup?page=440'),
  item(/\bRTX 3090\b/i,2020,'https://nvidianews.nvidia.com/news/nvidia-delivers-greatest-ever-generational-leap-in-performance-with-geforce-rtx-30-series-gpus?page=1'),
  item(/\bRTX 5090\b/i,2025,'https://nvidianews.nvidia.com/news/nvidia-blackwell-geforce-rtx-50-series-opens-new-world-of-ai-computer-graphics')
];
const identify=(catalog,name,kind)=>{const found=catalog.find(x=>x.match.test(name));return {kind,name,year:found?.year??null,url:found?.url??''};};
export function hardwareYearAssessment(pc){
  if(!pc.hardware)return {year:null,platformYear:null,parts:[]};
  const h=pc.hardware,parts=h.cpu.map(x=>identify(cpus,x.name,'CPU'));
  if(h.model==='Inspiron 3891')parts.push({kind:'主機板／機型',name:h.model,year:2021,url:'https://www.dell.com/support/product-details/en-us/product/inspiron-3891-desktop/resources/manuals'});
  else if(pc.nas?.model==='TS-253D')parts.push({kind:'主機板／機型',name:'QNAP TS-253D',year:2020,url:'https://www.qnap.com/en-us/news/2020/qnap-launches-quad-core-intel-based-ts-x53d-2-5gbe-nas-series-featuring-pcie-expansion-for-10-gbps-or-m-2-ssd-cache-acceleration'});
  else for(const board of h.motherboard)parts.push(identify(boards,board.product,'主機板'));
  const platform=parts.map(x=>x.year).filter(Boolean);
  for(const gpu of h.gpu.filter(x=>!x.virtual)){
    const integrated=parts.find(x=>x.kind==='CPU'&&((/i7-11700\b/i.test(x.name)&&/UHD Graphics 750/i.test(gpu.name))||(/Ryzen 7 9700X\b/i.test(x.name)&&/Radeon.*Graphics/i.test(gpu.name))||(/J4125\b/i.test(x.name)&&/Intel display controller/i.test(gpu.name))));
    parts.push(integrated?{kind:'GPU（內顯）',name:gpu.name,year:integrated.year,url:integrated.url}:identify(gpus,gpu.name,'GPU'));
  }
  return {year:parts.length&&parts.every(x=>x.year)?Math.max(...parts.map(x=>x.year)):null,platformYear:platform.length?Math.max(...platform):null,parts};
}
export const hardwareYearLabel=pc=>{const a=hardwareYearAssessment(pc);return a.year?String(a.year):'待確認';};
