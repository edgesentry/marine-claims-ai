// Service Worker for MarineClaims AI Executive Demo (PWA)
// Implements offline-first caching for static assets & network-first with cache fallback for pages.

const CACHE_NAME = 'marine-claims-v1';

const PRECACHE_ASSETS = [
  '/',
  '/uc2',
  '/uc3',
  '/manifest.webmanifest',
  '/static/demo.css',
  '/static/vendor/htmx.min.js',
  '/static/vendor/chart.umd.min.js',
  '/static/icons/icon.svg'
];

// Install: precache core shell assets & take control immediately
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(PRECACHE_ASSETS).catch((err) => {
        console.warn('[SW] Some precache assets failed:', err);
      });
    }).then(() => self.skipWaiting())
  );
});

// Activate: clean up old caches & claim clients
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.map((key) => {
          if (key !== CACHE_NAME) {
            console.log('[SW] Removing old cache:', key);
            return caches.delete(key);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

// Fetch: route according to request type
self.addEventListener('fetch', (event) => {
  const req = event.request;
  const url = new URL(req.url);

  // Only handle same-origin GET requests
  if (req.method !== 'GET' || url.origin !== self.location.origin) {
    return;
  }

  // 1. Navigation requests (HTML pages) -> Network-First with Cache Fallback
  if (req.mode === 'navigate') {
    event.respondWith(
      fetch(req)
        .then((response) => {
          if (response.status === 200) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(req, clone));
          }
          return response;
        })
        .catch(async () => {
          // Offline fallback: try matched page from cache, then fallback to cached home or /uc2
          const cached = await caches.match(req);
          if (cached) return cached;
          const fallback = await caches.match('/uc2') || await caches.match('/');
          if (fallback) return fallback;
          return new Response(
            '<html><body><h1>Offline</h1><p>MarineClaims AI is running offline without cached pages.</p></body></html>',
            { headers: { 'Content-Type': 'text/html; charset=utf-8' } }
          );
        })
    );
    return;
  }

  // 2. Static assets (/static/ & manifest) -> Stale-While-Revalidate
  if (url.pathname.startsWith('/static/') || url.pathname === '/manifest.webmanifest') {
    event.respondWith(
      caches.match(req).then((cached) => {
        const fetchPromise = fetch(req)
          .then((networkResponse) => {
            if (networkResponse && networkResponse.status === 200) {
              const clone = networkResponse.clone();
              caches.open(CACHE_NAME).then((cache) => cache.put(req, clone));
            }
            return networkResponse;
          })
          .catch(() => cached);

        return cached || fetchPromise;
      })
    );
    return;
  }

  // 3. Other GET requests -> Network-First
  event.respondWith(
    fetch(req)
      .then((response) => {
        if (response.status === 200) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(req, clone));
        }
        return response;
      })
      .catch(() => caches.match(req))
  );
});
