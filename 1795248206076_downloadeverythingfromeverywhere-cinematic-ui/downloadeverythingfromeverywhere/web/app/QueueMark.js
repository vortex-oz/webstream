"use client";

import { useEffect, useState } from "react";
import { SCRAPE_API } from "../lib/scrape-api.js";

export default function QueueMark() {
  const [n, setN] = useState(null);
  useEffect(() => {
    let gone = false;
    const tick = () => {
      fetch(`${SCRAPE_API}/queue`, { cache: "no-store" })
        .then((r) => r.json())
        .then((d) => {
          if (!gone) setN(Number(d.shortest) || 0);
        })
        .catch(() => {});
    };
    tick();
    const id = setInterval(tick, 2000);
    return () => {
      gone = true;
      clearInterval(id);
    };
  }, []);
  if (n == null) return null;
  return <span>{n} in queue</span>;
}
