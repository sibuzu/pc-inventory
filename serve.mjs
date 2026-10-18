import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
const root = path.resolve('dist');
const types = {'.html':'text/html; charset=utf-8','.css':'text/css; charset=utf-8','.js':'text/javascript; charset=utf-8','.mjs':'text/javascript; charset=utf-8','.json':'application/json; charset=utf-8','.ps1':'text/plain; charset=utf-8','.svg':'image/svg+xml'};
http.createServer((req,res)=>{
  let file;
  try { file=path.resolve(root,'.'+decodeURIComponent(new URL(req.url,'http://localhost').pathname)); } catch {res.writeHead(400).end();return;}
  if(file!==root && !file.startsWith(root+path.sep)){res.writeHead(403).end();return;}
  if(file===root)file=path.join(root,'index.html');
  fs.readFile(file,(error,data)=>{if(error){res.writeHead(404).end('Not found');return;}res.writeHead(200,{'Content-Type':types[path.extname(file)]||'application/octet-stream','Cache-Control':'no-cache'});res.end(data);});
}).listen(4173,'127.0.0.1',()=>console.log('PC Atlas: http://127.0.0.1:4173'));
