/* Public presentation assets only. Conversations and credentials never enter Cache Storage. */
const CACHE_NAME = 'harbor-public-shell-v1';
const CACHE_PREFIX = 'harbor-public-shell-';
const PUBLIC_ASSETS = new Set([
  '/offline.html', '/manifest.webmanifest', '/favicon.svg',
  '/icons/harbor.svg', '/icons/harbor-192.png',
  '/icons/harbor-512.png', '/icons/harbor-maskable-512.png',
]);

function isPublicAsset(url, request) {
  if (url.origin !== self.location.origin || url.search || request.headers.has('Authorization')) return false;
  if (PUBLIC_ASSETS.has(url.pathname)) return true;
  // Vite emits hashed JS/CSS into this public directory. Never match API or arbitrary file paths.
  return /^\/assets\/[A-Za-z0-9_-]+-[A-Za-z0-9_-]+\.(js|css)$/.test(url.pathname);
}

self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE_NAME).then(cache => cache.addAll([...PUBLIC_ASSETS]))
    .then(() => self.skipWaiting()));
});

self.addEventListener('activate', event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(keys
    .filter(key => key.startsWith(CACHE_PREFIX) && key !== CACHE_NAME)
    .map(key => caches.delete(key)))).then(() => self.clients.claim()));
});

self.addEventListener('fetch', event => {
  const request = event.request;
  const url = new URL(request.url);
  if (request.method !== 'GET' || url.origin !== self.location.origin
      || url.pathname === '/api' || url.pathname.startsWith('/api/')
      || request.headers.has('Authorization')) return;

  // Navigation always uses the network, without caching personalized HTML or stale app versions.
  if (request.mode === 'navigate') {
    event.respondWith(fetch(request).catch(async () => {
      const offline = await caches.match('/offline.html');
      return offline || new Response('Harbor is offline. Reconnect to continue.', {
        status: 503, headers: {'Content-Type': 'text/plain; charset=utf-8'},
      });
    }));
    return;
  }

  if (!isPublicAsset(url, request)) return;
  event.respondWith((async () => {
    try {
      const response = await fetch(request);
      if (response.ok && response.type === 'basic'
          && !/no-store|private/i.test(response.headers.get('Cache-Control') || '')) {
        const cache = await caches.open(CACHE_NAME);
        await cache.put(request, response.clone());
      }
      return response;
    } catch (error) {
      const cached = await caches.match(request);
      if (cached) return cached;
      throw error;
    }
  })());
});
