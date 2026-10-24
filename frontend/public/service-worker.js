self.addEventListener("push", (event) => {
  let payload = {};
  try {
    payload = event.data ? event.data.json() : {};
  } catch {
    payload = {};
  }

  event.waitUntil(
    self.registration.showNotification(payload.title || "CuraMind reminder", {
      body: payload.body || "A scheduled reminder is due. Open CuraMind to view it.",
      icon: "/curamind-logo.jpeg",
      tag: `curamind-reminder-${payload.reminder_id || "due"}`,
      data: { url: payload.url || "/reminders" },
    }),
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const target = new URL(event.notification.data?.url || "/reminders", self.location.origin).href;

  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then(async (clients) => {
      for (const client of clients) {
        if (client.url.startsWith(self.location.origin)) {
          await client.focus();
          if ("navigate" in client) await client.navigate(target);
          return;
        }
      }
      return self.clients.openWindow(target);
    }),
  );
});
