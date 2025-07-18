const SHELL_FILES = [
  '/', 
  '/static/home.css',
  '/static/busiloo.svg',
  '/static/translater.js',
  '/static/trip.css',
  // …any other static assets…
];
const CACHE_NAME  = 'busiloo-shell-v1';
const DATA_CACHE  = 'busiloo-data-v1';
const HTML_CACHE  = 'busiloo-html-v1';  // ← new

// Pre‑cache shell
self.addEventListener('install', evt => {
  evt.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(SHELL_FILES))
      .then(() => self.skipWaiting())
  );
});

// Clean up old caches
self.addEventListener('activate', evt => {
  evt.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.map(key => {
        if (![CACHE_NAME, DATA_CACHE, HTML_CACHE].includes(key)) {
          return caches.delete(key);
        }
      }))
    ).then(() => self.clients.claim())
  );
});

// Helper: fetch & cache API JSON
async function fetchAndCache(request) {
  const cache = await caches.open(DATA_CACHE);
  try {
    const response = await fetch(request);
    cache.put(request, response.clone());
    return response;
  } catch {
    const cached = await cache.match(request);
    if (cached) return cached;
    // fallback JSON
    const fallbackBody = request.url.includes('/find_route_results')
      ? JSON.stringify({ type: 'none', results: [] })
      : JSON.stringify([]);
    return new Response(fallbackBody, {
      status: 200,
      headers: { 'Content-Type': 'application/json' }
    });
  }
}

// Helper: fetch & cache HTML pages (dynamic caching)
async function cacheHtml(request) {
  const cache = await caches.open(HTML_CACHE);
  try {
    const response = await fetch(request);
    cache.put(request, response.clone());
    return response;
  } catch {
    const cached = await cache.match(request);
    if (cached) return cached;
    // final fallback to shell
    return caches.match('/');
  }
}

// Main fetch handler
self.addEventListener('fetch', evt => {
  const url = new URL(evt.request.url);

  // 1) HTML navigations → dynamic cacheHtml()
  if (evt.request.mode === 'navigate') {
    evt.respondWith(cacheHtml(evt.request));
    return;
  }

  // 2) API calls: network‑first, then DATA_CACHE
  if (url.pathname.startsWith('/union/stops') ||
      url.pathname.startsWith('/api/')) {
    evt.respondWith(fetchAndCache(evt.request));
    return;
  }

  // 3) App shell & static assets: cache‑first
  evt.respondWith(
    caches.match(evt.request)
      .then(resp => resp || fetch(evt.request))
  );
});
