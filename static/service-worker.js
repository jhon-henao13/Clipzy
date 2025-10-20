const CACHE_NAME = 'clipzy-cache-v1';
const urlsToCache = [
  '/',
  '/static/style.css',
  '/static/img/icon.png',  // Añade más archivos si necesitas (ej. particles.js si lo descargas localmente)
  'https://cdn.tailwindcss.com',  // Cachea Tailwind si es necesario
  'https://cdn.jsdelivr.net/npm/tsparticles@2.12.0/tsparticles.bundle.min.js'  // Cachea particles.js
];

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