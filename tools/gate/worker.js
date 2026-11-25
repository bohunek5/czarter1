'use strict';
const scope = new URL(self.registration.scope);
const vaultIndex = new URL('_gate/__INDEX__', scope);
const encoder = new TextEncoder();
let unlocked = null;
let epoch = 0;

self.addEventListener('install', event => event.waitUntil(self.skipWaiting()));
self.addEventListener('activate', event => event.waitUntil(self.clients.claim()));

function inScope(url) {
  const input = new URL(url);
  return input.origin === scope.origin && input.pathname.startsWith(scope.pathname);
}
async function decrypt(key, bytes, name) {
  const data = new Uint8Array(bytes);
  return crypto.subtle.decrypt({name:'AES-GCM', iv:data.subarray(0,12), additionalData:encoder.encode(name)}, key, data.subarray(12));
}
async function openVault(encoded) {
  if (typeof encoded !== 'string' || encoded.length !== 44) return 'denied';
  const generation = epoch;
  let encrypted;
  try {
    const response = await fetch(vaultIndex);
    if (!response.ok) return 'unavailable';
    encrypted = await response.arrayBuffer();
  } catch { return 'unavailable'; }
  try {
    const key = await crypto.subtle.importKey('raw', Uint8Array.from(atob(encoded), char => char.charCodeAt(0)), {name:'AES-GCM'}, false, ['decrypt']);
    const index = JSON.parse(new TextDecoder().decode(await decrypt(key, encrypted, '@preview-index')));
    if (generation !== epoch) return 'denied';
    unlocked = {key, index:new Map(index)};
    return 'ok';
  } catch { return 'denied'; }
}
self.addEventListener('message', event => {
  if (!event.source?.url || !inScope(event.source.url)) return;
  if (event.data?.type === 'open' && event.ports[0]) {
    event.waitUntil(openVault(event.data.key).then(status => event.ports[0].postMessage(status)));
  }
  if (event.data?.type === 'close') {
    ++epoch;
    unlocked = null;
    event.waitUntil(self.clients.matchAll({type:'window'}).then(clients => {
      for (const client of clients) if (inScope(client.url)) client.postMessage({type:'closed'});
    }));
  }
});
async function restoreClientKey(clientId) {
  if (!clientId) return;
  const client = await self.clients.get(clientId);
  if (!client || !inScope(client.url)) return;
  const key = await new Promise(resolve => {
    const channel = new MessageChannel();
    const timer = setTimeout(() => { channel.port1.close(); resolve(null); }, 1600);
    channel.port1.onmessage = event => {
      clearTimeout(timer);
      channel.port1.close();
      resolve(event.data);
    };
    client.postMessage({type:'restore-key'}, [channel.port2]);
  });
  if (key && !unlocked) await openVault(key);
}
function gateResponse(status) {
  return new Response(null, {status,headers:{'Cache-Control':'no-store'}});
}
async function serve(event, url) {
  const request = event.request;
  if (request.method !== 'GET' && request.method !== 'HEAD') return gateResponse(405);
  if (!unlocked) await restoreClientKey(event.clientId);
  if (!unlocked) {
    if (request.mode === 'navigate' || request.destination === 'document') {
      const res = await fetch(new URL('_gate/locked.html', scope), {cache:'no-store'});
      if (!res.ok) return gateResponse(503);
      return new Response(await res.arrayBuffer(), {headers:{'Content-Type':'text/html; charset=utf-8','Cache-Control':'no-store'}});
    }
    return gateResponse(401);
  }
  const {key,index} = unlocked;
  let path;
  try { path = decodeURIComponent(url.pathname.slice(scope.pathname.length)); } catch { return gateResponse(400); }
  if (path && !path.endsWith('/') && !index.has(path) && index.has(path+'/index.html')) {
    url.pathname += '/';
    return Response.redirect(url.href, 301);
  }
  if (!path || path.endsWith('/')) path += 'index.html';
  const item = index.get(path);
  if (!item) return new Response('Nie znaleziono tej strony.', {status:404,headers:{'Content-Type':'text/plain; charset=utf-8','Cache-Control':'no-store'}});
  const [blob,type,length] = item;
  const headers = new Headers({'Content-Type':type,'Content-Length':String(length),'Cache-Control':'no-store','Referrer-Policy':'no-referrer','X-Content-Type-Options':'nosniff','Accept-Ranges':'bytes'});
  if (request.method === 'HEAD') return new Response(null,{headers});
  try {
    const response = await fetch(new URL('_gate/data/'+blob, scope));
    if (!response.ok) return gateResponse(503);
    const plain = await decrypt(key,await response.arrayBuffer(),path);
    const range = request.headers.get('Range');
    if (range) {
      const match = /^bytes=(\d*)-(\d*)$/.exec(range);
      if (match && (match[1] || match[2])) {
        const start = match[1] ? +match[1] : Math.max(0, length - Number(match[2]));
        const end = match[1] && match[2] ? Math.min(+match[2],length-1) : length-1;
        if (start > end || start >= length) return new Response(null,{status:416,headers:{'Content-Range':'bytes */'+length}});
        headers.set('Content-Range', 'bytes '+start+'-'+end+'/'+length);
        headers.set('Content-Length', String(end-start+1));
        return new Response(plain.slice(start, end+1),{status:206,headers});
      }
    }
    return new Response(plain,{headers});
  } catch { return gateResponse(503); }
}
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  if (!inScope(url.href)) return;
  const path = url.pathname.slice(scope.pathname.length);
  if (path === 'preview-sw.js' || path.startsWith('_gate/')) return;
  event.respondWith(serve(event,url));
});
