// M8550 dashboard service worker — minimal: just handles Web Push.

self.addEventListener("install", (event) => {
  event.waitUntil(self.skipWaiting())
})

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim())
})

self.addEventListener("push", (event) => {
  if (!event.data) return
  let payload = {}
  try { payload = event.data.json() } catch { payload = { title: "M8550", body: event.data.text() } }
  const title = payload.title || "M8550"
  const options = {
    body: payload.body || "",
    tag: payload.tag,
    data: payload.data || {},
    badge: "/icon",
    icon: "/icon",
  }
  event.waitUntil(self.registration.showNotification(title, options))
})

self.addEventListener("notificationclick", (event) => {
  event.notification.close()
  event.waitUntil((async () => {
    const all = await self.clients.matchAll({ type: "window", includeUncontrolled: true })
    for (const c of all) {
      if (c.url.endsWith("/") || c.url.includes(self.registration.scope)) {
        return c.focus()
      }
    }
    return self.clients.openWindow("/")
  })())
})
