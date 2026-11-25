'use strict';
(() => {
  const base = new URL('../', document.currentScript.src);
  const form = document.querySelector('#login-form');
  const button = document.querySelector('#open');
  const status = document.querySelector('#message');
  const contextKey = 'czarter-preview:' + base.pathname;
  const toB64 = bytes => btoa(String.fromCharCode(...new Uint8Array(bytes)));
  const fromB64 = text => Uint8Array.from(atob(text), char => char.charCodeAt(0));
  let active, meta;

  function readSession() {
    try { return sessionStorage.getItem(contextKey); } catch { return null; }
  }
  function remember(key) {
    try {
      if (key) sessionStorage.setItem(contextKey, key);
      else sessionStorage.removeItem(contextKey);
    } catch { /* Access can be limited in private browsing. */ }
  }
  async function getWorker() {
    const expected = new URL('preview-sw.js', base).href;
    await navigator.serviceWorker.register(expected, {scope:base.pathname, updateViaCache:'none'});
    if (navigator.serviceWorker.controller?.scriptURL !== expected) {
      await new Promise((resolve, reject) => {
        const timer = setTimeout(() => { navigator.serviceWorker.removeEventListener('controllerchange', changed); reject(new Error('control')); }, 15000);
        function changed() {
          if (navigator.serviceWorker.controller?.scriptURL !== expected) return;
          navigator.serviceWorker.removeEventListener('controllerchange', changed);
          clearTimeout(timer);
          resolve();
        }
        navigator.serviceWorker.addEventListener('controllerchange', changed);
        changed();
      });
    }
    return navigator.serviceWorker.controller;
  }
  function authenticate(key) {
    return new Promise((resolve, reject) => {
      const channel = new MessageChannel();
      const timer = setTimeout(() => { channel.port1.close(); reject(new Error('timeout')); }, 20000);
      channel.port1.onmessage = e => {
        clearTimeout(timer);
        channel.port1.close();
        resolve(e.data);
      };
      active.postMessage({type:'open', key}, [channel.port2]);
    });
  }
  let ready;
  async function prepare() {
    if (!navigator.serviceWorker || !globalThis.crypto?.subtle) throw new Error('support');
    active = await getWorker();
    const response = await fetch(new URL('_gate/settings.json', base), {cache:'no-store'});
    if (!response.ok) throw new Error('metadata');
    meta = await response.json();
  }
  function infrastructureError() {
    status.textContent = 'Podgląd wymaga aktualnej przeglądarki z obsługą szyfrowania. Sprawdź połączenie i odśwież stronę.';
  }
  form.addEventListener('submit', async event => {
    event.preventDefault();
    if (button.disabled) return;
    button.disabled = true;
    status.textContent = 'Otwieranie podglądu…';
    try {
      await ready;
      const login = document.querySelector('#login').value.trim();
      const password = document.querySelector('#password');
      const material = await crypto.subtle.importKey('raw', new TextEncoder().encode(login+'\0'+password.value), 'PBKDF2', false, ['deriveBits']);
      const bits = await crypto.subtle.deriveBits({name:'PBKDF2',hash:'SHA-256',salt:fromB64(meta.salt),iterations:meta.iterations}, material, 256);
      const key = toB64(bits);
      const result = await authenticate(key);
      if (result === 'ok') {
        remember(key);
        password.value = '';
        location.reload();
        return;
      }
      if (result === 'denied') {
        remember(null);
        status.textContent = 'Login lub hasło są nieprawidłowe.';
        password.select();
      } else infrastructureError();
    } catch { infrastructureError(); }
    button.disabled = false;
  });
  ready = prepare();
  ready.then(async () => {
    const key = readSession();
    if (!key) return;
    if (await authenticate(key) === 'ok') location.reload();
    else remember(null);
  }).catch(infrastructureError);
})();
