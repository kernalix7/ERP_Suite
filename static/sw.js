const CACHE_NAME = 'erp-v1';
const STATIC_ASSETS = [
  '/',
  '/static/manifest.json',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET') return;
  event.respondWith(
    fetch(event.request)
      .then((response) => {
        if (response.ok && event.request.url.includes('/static/')) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
        }
        return response;
      })
      .catch(() => caches.match(event.request))
  );
});

// ── Push Notification Handlers ──────────────────────────────

self.addEventListener('push', (event) => {
  let data = { title: 'ERP Suite', body: '새로운 알림이 있습니다.', url: '/' };
  try {
    if (event.data) {
      data = Object.assign(data, event.data.json());
    }
  } catch (e) {
    if (event.data) {
      data.body = event.data.text();
    }
  }

  const options = {
    body: data.body,
    icon: '/static/icons/icon-192x192.png',
    badge: '/static/icons/badge-72x72.png',
    tag: data.tag || 'erp-notification',
    data: { url: data.url || '/' },
    actions: [
      { action: 'open', title: '열기' },
      { action: 'dismiss', title: '닫기' },
    ],
    vibrate: [200, 100, 200],
  };

  event.waitUntil(
    self.registration.showNotification(data.title, options)
  );
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();

  if (event.action === 'dismiss') return;

  const url = event.notification.data?.url || '/';
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((windowClients) => {
      for (const client of windowClients) {
        if (client.url.includes(url) && 'focus' in client) {
          return client.focus();
        }
      }
      return clients.openWindow(url);
    })
  );
});

self.addEventListener('notificationclose', (event) => {
  // Analytics: notification dismissed
});

// ── Offline Barcode Scan Cache ──────────────────────────────

const BARCODE_CACHE = 'erp-barcode-v1';

self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'CACHE_BARCODE_SCAN') {
    event.waitUntil(
      caches.open(BARCODE_CACHE).then((cache) => {
        const scanData = event.data.payload;
        const blob = new Blob([JSON.stringify(scanData)], { type: 'application/json' });
        const response = new Response(blob);
        return cache.put('/offline-scans/' + Date.now(), response);
      })
    );
  }

  if (event.data && event.data.type === 'SYNC_BARCODE_SCANS') {
    event.waitUntil(syncBarcodeScanCache());
  }
});

async function syncBarcodeScanCache() {
  try {
    const cache = await caches.open(BARCODE_CACHE);
    const keys = await cache.keys();
    for (const request of keys) {
      const response = await cache.match(request);
      const data = await response.json();
      try {
        await fetch('/api/barcode/scan/', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(data),
        });
        await cache.delete(request);
      } catch (e) {
        // Will retry on next sync
      }
    }
  } catch (e) {
    // Cache not available
  }
}
