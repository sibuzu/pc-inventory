export const pageTabs=['overview','hardware','software','storage','subsystems','system'];
const key=value=>String(value??'').toLowerCase().replaceAll('-','_');
export function readRoute(address,ids){
  const url=new URL(address,'https://inventory.local');
  const fallback={mode:'compare',selected:ids[0]??'pc_china',tab:'overview'};
  const findId=value=>ids.find(id=>id===value)??ids.find(id=>key(id)===key(value));
  const inventory=(id,tab)=>({mode:'inventory',selected:id,tab:pageTabs.includes(key(tab))?key(tab):'overview'});
  let hash='';try{hash=decodeURIComponent(url.hash.slice(1)).replace(/^\/+|\/+$/g,'');}catch{}
  if(key(hash)==='compare')return fallback;
  if(key(hash)==='inventory')return inventory(fallback.selected,'overview');
  const parts=hash.split('/'),id=findId(parts[0]);
  if(id&&parts.length<=2)return inventory(id,parts[1]);
  if(key(url.searchParams.get('view'))==='compare')return fallback;
  const queryId=findId(url.searchParams.get('pc'));
  if(queryId)return inventory(queryId,url.searchParams.get('tab'));
  if(key(url.searchParams.get('view'))==='inventory')return inventory(fallback.selected,url.searchParams.get('tab'));
  return fallback;
}
export function routeHash(route){
  if(route.mode==='compare')return '#compare';
  return '#'+encodeURIComponent(route.selected)+(route.tab==='overview'?'':'/'+encodeURIComponent(route.tab));
}
