"use client";

import { useEffect } from "react";

/** Drop any installed worker and Cache Storage so stale shells/images cannot stick. */
export default function Pwa() {
  useEffect(() => {
    if ("serviceWorker" in navigator) {
      navigator.serviceWorker.getRegistrations().then((regs) => {
        for (const r of regs) r.unregister();
      });
    }
    if (typeof caches !== "undefined") {
      caches.keys().then((keys) => Promise.all(keys.map((k) => caches.delete(k))));
    }
  }, []);
  return null;
}
