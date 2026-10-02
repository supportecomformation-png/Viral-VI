/* Copy Trade — service worker : affiche les notifications push et ouvre la bonne page au clic. */
self.addEventListener("install", function () { self.skipWaiting(); });
self.addEventListener("activate", function (e) { e.waitUntil(self.clients.claim()); });

self.addEventListener("push", function (event) {
  var data = {};
  try { data = event.data ? event.data.json() : {}; } catch (e) {}
  var title = data.title || "Copy Trade";
  event.waitUntil(self.registration.showNotification(title, {
    body: data.body || "",
    tag: data.tag || undefined,
    icon: "/static/icons/icon-192.png",
    badge: "/static/icons/icon-192.png",
    data: { url: data.url || "/app" },
  }));
});

self.addEventListener("notificationclick", function (event) {
  event.notification.close();
  var url = (event.notification.data && event.notification.data.url) || "/app";
  event.waitUntil(self.clients.matchAll({ type: "window", includeUncontrolled: true }).then(function (list) {
    for (var i = 0; i < list.length; i++) {
      var c = list[i];
      if ("focus" in c) {
        if ("navigate" in c) c.navigate(url);
        return c.focus();
      }
    }
    return self.clients.openWindow(url);
  }));
});
