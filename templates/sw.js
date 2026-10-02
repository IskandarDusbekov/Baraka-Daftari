{% load static %}/* Baraka Daftari — service worker (core/pwa.py). Versiya: {{ version }}

   Qoidalar:
   - Faqat shu saytning GET so'rovlari. Boshqa saytlar (shriftlar, Telegram) — brauzerning o'ziga.
   - /api/, /boshqaruv/, /admin/ — hech qachon keshlanmaydi (shaxsiy ma'lumot).
   - /static/ — avval keshdan (fayl nomida xesh bor, o'zgarsa nomi ham o'zgaradi).
   - Sahifalar — avval tarmoqdan; internet bo'lmasa oflayn sahifa.
*/
const CACHE = 'baraka-v{{ version|escapejs }}';
const OFFLINE = '/oflayn/';
const PRECACHE = [OFFLINE, '{% static "css/app.css" %}', '{% static "img/logo.svg" %}', '{% static "img/icon-192.png" %}'];
const PRIVATE = ['/api/', '/boshqaruv/', '/admin/'];
const CACHE_STATIC = {{ cache_static|yesno:"true,false" }};

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(CACHE).then((c) => c.addAll(PRECACHE)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k.startsWith('baraka-') && k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;
  if (PRIVATE.some((p) => url.pathname.startsWith(p))) return;

  if (CACHE_STATIC && url.pathname.startsWith('/static/')) {
    event.respondWith(
      caches.match(req).then((hit) => hit || fetch(req).then((res) => {
        if (res.ok) {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(req, copy));
        }
        return res;
      })),
    );
    return;
  }

  if (req.mode === 'navigate') {
    event.respondWith(fetch(req).catch(() => caches.match(OFFLINE)));
  }
});
