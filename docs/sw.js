/* Service worker de la app móvil (PWA).
 * Estrategia: primero la red (respeta la caché HTTP de GitHub Pages) y, sin
 * conexión, la última copia guardada. Solo se guardan las páginas y datos que
 * la persona ya abrió; no se descarga por adelantado todo el sitio (~200 MB). */
const VERSION = 'v1';
const CACHE = 'direccion-escolar-' + VERSION;
const SHELL = [
  './', 'index.html', 'manifest.webmanifest', 'pwa.js', 'mobile.css',
  'icons/icon-192.png', 'icons/icon-512.png', 'icons/apple-touch-icon.png'
];
const CDN_HOSTS = ['cdnjs.cloudflare.com', 'cdn.jsdelivr.net', 'unpkg.com'];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE)
      .then(cache => Promise.all(SHELL.map(url => cache.add(url).catch(() => null))))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k.startsWith('direccion-escolar-') && k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', event => {
  const req = event.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  const sameOrigin = url.origin === self.location.origin;
  if (!sameOrigin && !CDN_HOSTS.includes(url.hostname)) return;
  // Las APIs externas (p. ej., Gemini) y los rangos parciales no se guardan.
  if (req.headers.has('range')) return;

  event.respondWith(
    fetch(req)
      .then(res => {
        if (res && (res.ok || res.type === 'opaque')) {
          const copy = res.clone();
          caches.open(CACHE).then(cache => cache.put(req, copy)).catch(() => null);
        }
        return res;
      })
      .catch(async () => {
        const cached = await caches.match(req, { ignoreSearch: req.mode === 'navigate' });
        if (cached) return cached;
        if (req.mode === 'navigate') {
          return new Response(
            '<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' +
            '<body style="font-family:system-ui;background:#0D1117;color:#C9D1D9;padding:24px">' +
            '<h1>Sin conexión</h1><p>Esta sección todavía no se abrió con conexión, por eso no está guardada en el teléfono.</p>' +
            '<p><a style="color:#58A6FF" href="index.html">Volver al tablero</a></p></body>',
            { headers: { 'Content-Type': 'text/html; charset=utf-8' } }
          );
        }
        return Response.error();
      })
  );
});
