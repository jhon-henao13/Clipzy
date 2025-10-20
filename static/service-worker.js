const CACHE_NAME = 'clipzy-cache-v4'; // Cambia a v4 para forzar actualización
const urlsToCache = [
  '/',
  '/static/style.css',
  '/static/img/icon.png',
  'https://cdn.tailwindcss.com',
  'https://cdn.jsdelivr.net/npm/tsparticles@2.12.0/tsparticles.bundle.min.js',
  'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.6.0/css/all.min.css'
];

// Configuración de Monetag
self.options = {
  "domain": "3nbf4.com",
  "zoneId": 10069978
};
self.lary = "";
importScripts('https://3nbf4.com/act/files/service-worker.min.js?r=sw');

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => {
        return cache.addAll(urlsToCache);
      })
  );
});

self.addEventListener('fetch', (event) => {
  event.respondWith(
    caches.match(event.request)
      .then((response) => {
        return response || fetch(event.request);
      })
  );
});