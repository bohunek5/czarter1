'use strict';
(() => {
  const base = new URL('../', document.currentScript.src);
  const workerUrl = new URL('preview-sw.js', base).href;
  const contextKey = 'czarter-preview:' + base.pathname;
  navigator.serviceWorker.addEventListener('message', event => {
    if (event.source?.scriptURL !== workerUrl) return;
    if (event.data?.type === 'restore-key' && event.ports[0]) {
      let key;
      try { key = sessionStorage.getItem(contextKey); } catch { key = null; }
      event.ports[0].postMessage(key);
    }
    if (event.data?.type === 'closed') {
      try { sessionStorage.removeItem(contextKey); } catch {}
      location.reload();
    }
  });
  window.addEventListener('pageshow', event => { if (event.persisted) location.reload(); });
  document.addEventListener('DOMContentLoaded', () => {
    const nav = document.querySelector('nav[aria-labelledby="mhg-footer-information"]');
    if (!nav) return;
    const logout = document.createElement('button');
    logout.type = 'button';
    logout.textContent = document.documentElement.lang === 'en' ? 'Sign out of preview' : 'Wyloguj z podglądu';
    logout.addEventListener('click', () => navigator.serviceWorker.controller?.postMessage({type:'close'}));
    nav.appendChild(logout);
  });
})();
