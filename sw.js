/* Network-first service worker: always fresh when online, offline fallback, auto-update, and Web Push alerts */
const CACHE = "base-shell-v2";
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", e => e.waitUntil((async () => {
  for (const k of await caches.keys()) if (k !== CACHE) await caches.delete(k);
  await self.clients.claim();
})()));
self.addEventListener("fetch", e => {
  const r = e.request, u = new URL(r.url);
  if (r.method !== "GET" || u.origin !== location.origin) return;
  if (r.mode !== "navigate") return;
  e.respondWith((async () => {
    try {
      const res = await fetch(u.href, {cache: "no-cache", credentials: "same-origin"});
      if (res.ok) { const c = res.clone(); caches.open(CACHE).then(cc => cc.put(u.origin + u.pathname, c)).catch(() => {}); }
      return res;
    } catch (err) {
      const hit = await caches.match(u.origin + u.pathname) || await caches.match(new URL("index.html", self.registration.scope).href);
      if (hit) return hit;
      throw err;
    }
  })());
});
self.addEventListener("push", e => {
  let d = {};
  try { d = e.data ? e.data.json() : {}; } catch (_) { d = {title: "Base Tracker", body: e.data ? e.data.text() : ""}; }
  e.waitUntil(self.registration.showNotification(d.title || "Base Tracker", {
    body: d.body || "",
    tag: d.tag || undefined,
    icon: "icon-192.png",
    badge: "icon-192.png",
    data: {url: new URL(d.url || "index.html", self.registration.scope).href}
  }));
});
self.addEventListener("notificationclick", e => {
  e.notification.close();
  const url = (e.notification.data && e.notification.data.url) || self.registration.scope;
  e.waitUntil((async () => {
    if (url.startsWith(self.registration.scope)) {
      for (const c of await self.clients.matchAll({type: "window", includeUncontrolled: true})) {
        try { await c.navigate(url); return c.focus(); } catch (_) {}
      }
    }
    return self.clients.openWindow(url);
  })());
});
