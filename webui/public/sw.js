// qBitrr Service Worker
// Cache version is injected at Vite build time (deploy-tied); fallback for raw public/ copies.
const CACHE_VERSION = "__QBITRR_CACHE_VERSION__";
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

function pathIncludesApi(pathname) {
  return pathname === '/api' || pathname.startsWith('/api/') || pathname.includes('/api/');
}

function pathIncludesWeb(pathname) {
  return pathname === '/web' || pathname.startsWith('/web/') || pathname.includes('/web/');
}

function pathIncludesWebLogs(pathname) {
  return pathname.includes('/web/logs/');
}

function isStaticAssetPath(pathname) {
  // Cache-first only for hashed assets; never for /web/* or /api/* JSON endpoints.
  if (pathIncludesWeb(pathname) || pathIncludesApi(pathname)) {
    return false;
  }
  // HTML shells must stay network-first — they reference deploy-hashed JS/CSS.
  if (pathname.endsWith(".html") || pathname.endsWith("/")) {
    return false;
  }
  return (
    /\.(?:js|css|mjs|map|woff2?|ttf|otf|eot|png|jpe?g|gif|svg|webp|ico|wasm|json)$/i.test(
      pathname
    ) || pathname.includes("/assets/")
  );
}

async function networkFirstNoStore(request) {
  try {
    return await fetch(request);
  } catch (error) {
    const cached = await caches.match(request);
    if (cached) {
      return cached;
    }
    throw error;
  }
}

async function cacheFirst(request) {
  const cachedResponse = await caches.match(request);
  if (cachedResponse) {
    return cachedResponse;
  }

  const response = await fetch(request);
  // Don't cache non-successful responses
  if (!response || response.status !== 200 || response.type === 'error') {
    return response;
  }

  const responseToCache = response.clone();
  caches.open(RUNTIME_CACHE).then((cache) => {
    cache.put(request, responseToCache);
  });

  return response;
}

// Fetch event - network-first for /web/* and /api/*, cache-first for static assets only
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Skip non-GET requests
  if (request.method !== 'GET') {
    return;
  }

  // Skip log file requests - they can be very large and shouldn't be cached
  if (pathIncludesWebLogs(url.pathname) && !url.pathname.endsWith('/download')) {
    return;
  }

  // Network-first (do not cache dynamic JSON) for all /web/* and /api/*
  if (pathIncludesWeb(url.pathname) || pathIncludesApi(url.pathname)) {
    event.respondWith(networkFirstNoStore(request));
    return;
  }

  // Cache-first for static assets only
  if (isStaticAssetPath(url.pathname)) {
    event.respondWith(cacheFirst(request));
    return;
  }

  // Default: network-first without caching (HTML shells, unknown paths)
  event.respondWith(networkFirstNoStore(request));
});
