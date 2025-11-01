// qBitrr Service Worker
// Update cache version on every deployment to force refresh
const CACHE_VERSION = Date.now();
const CACHE_NAME = `qbitrr-v${CACHE_VERSION}`;
const RUNTIME_CACHE = `qbitrr-runtime-v${CACHE_VERSION}`;

// Assets to cache on install
// Keep this empty to avoid installation failures in various deployment scenarios
const PRECACHE_URLS = [];

// Install event - precache essential assets
self.addEventListener('install', (event) => {
  // Force immediate activation, don't wait for caching
  self.skipWaiting();

  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => {
        // Try to cache each URL individually, don't fail if one fails
        if (PRECACHE_URLS.length === 0) {
          return Promise.resolve();
        }
        return Promise.allSettled(
          PRECACHE_URLS.map((url) =>
            cache.add(url).catch((err) => {
              console.warn(`Failed to cache ${url}:`, err);
              return null;
            })
          )
        );
      })
      .catch((err) => {
        console.error('ServiceWorker install failed:', err);
        // Don't throw - allow installation to complete
        return Promise.resolve();
      })
  );
});

// Activate event - clean up old caches
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames
          .filter((cacheName) => cacheName !== CACHE_NAME && cacheName !== RUNTIME_CACHE)
          .map((cacheName) => caches.delete(cacheName))
      );
    }).then(() => self.clients.claim())
  );
});

// Fetch event - network-first strategy for API calls, cache-first for assets
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Skip non-GET requests
  if (request.method !== 'GET') {
    return;
  }

  // Network-first for API calls
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(
      fetch(request)
        .then((response) => {
          // Clone the response before caching
          const responseToCache = response.clone();
          caches.open(RUNTIME_CACHE).then((cache) => {
            cache.put(request, responseToCache);
          });
          return response;
        })
        .catch(() => {
          // Return cached response if network fails
          return caches.match(request);
        })
    );
    return;
  }

  // Cache-first for static assets
  event.respondWith(
    caches.match(request).then((cachedResponse) => {
      if (cachedResponse) {
        return cachedResponse;
      }

      return fetch(request).then((response) => {
        // Don't cache non-successful responses
        if (!response || response.status !== 200 || response.type === 'error') {
          return response;
        }

        const responseToCache = response.clone();
        caches.open(RUNTIME_CACHE).then((cache) => {
          cache.put(request, responseToCache);
        });

        return response;
      });
    })
  );
});
