// Ana ekrana eklenebilmek için gereken service worker.
// Önbellek kullanmıyor: her istek ağdan gelir, böylece güncellemeler hemen görünür.
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", event => event.waitUntil(self.clients.claim()));
self.addEventListener("fetch", () => {});
