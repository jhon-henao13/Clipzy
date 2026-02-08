const CACHE_NAME = 'clipzy-v5';
const urlsToCache = [
  '/',
  '/static/style.css',
  '/static/img/icon.png'
];

// Configuración Monetag (Mantener igual)
self.options = {"domain":"3nbf4.com","zoneId":10069978};
importScripts('https://3nbf4.com/act/files/service-worker.min.js?r=sw');

self.addEventListener('install', (event) => {
  self.skipWaiting(); // Fuerza al SW nuevo a tomar el control
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(urlsToCache))
  );
});

self.addEventListener('fetch', (event) => {
  // No cachear peticiones de la API ni de anuncios para evitar errores
  if (event.request.url.includes('/api/') || event.request.url.includes('3nbf4.com')) {
    return;
  }

  event.respondWith(
    caches.match(event.request).then((cachedResponse) => {
      const fetchPromise = fetch(event.request).then((networkResponse) => {
        caches.open(CACHE_NAME).then((cache) => {
          cache.put(event.request, networkResponse.clone());
        });
        return networkResponse;
      });
      return cachedResponse || fetchPromise;
    })
  );
});