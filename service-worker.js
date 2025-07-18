const CACHE_NAME = 'busiloo-shell-v1';
const DATA_CACHE = 'busiloo-data-v1';
const SHELL_FILES = [
  '/',                // make sure your server serves index.html on “/”
  '/static/home.css',
  '/static/busiloo.svg',
  '/static/translater.js',
  // list all your other assets...
];

self.addEventListener('install', evt => {
  // Pre-cache app shell
  evt.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(SHELL_FILES))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', evt => {
  // Clean up old caches
  evt.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.map(key => {
        if (![CACHE_NAME, DATA_CACHE].includes(key)) {
          return caches.delete(key);
        }
      }))
    ).then(() => self.clients.claim())
  );
});

// Helper for API caching
async function fetchAndCache(request) {
  const cache = await caches.open(DATA_CACHE);
  try {
    const response = await fetch(request);
    cache.put(request, response.clone());
    return response;
  } catch (err) {
    console.warn('🗄️ Fetch failed; returning cache or fallback:', request.url, err);

    const cached = await cache.match(request);
    if (cached) {
      return cached;
    }

    // FINAL FALLBACK: empty JSON (or whatever shape your app expects)
    const fallbackBody = request.url.includes('/find_route_results')
      ? JSON.stringify({ type: 'none', results: [] })
      : JSON.stringify([]);
    return new Response(fallbackBody, {
      status: 200,
      headers: { 'Content-Type': 'application/json' }
    });
  }
}


self.addEventListener('fetch', evt => {
  const url = new URL(evt.request.url);

  // 1) API calls: network-first, then cache
  if (url.pathname.startsWith('/union/stops') ||
      url.pathname.startsWith('/api/')) {
    evt.respondWith(fetchAndCache(evt.request));
    return;
  }

  // 2) App shell & assets: cache-first
  evt.respondWith(
    caches.match(evt.request)
      .then(resp => resp || fetch(evt.request))
  );
});
