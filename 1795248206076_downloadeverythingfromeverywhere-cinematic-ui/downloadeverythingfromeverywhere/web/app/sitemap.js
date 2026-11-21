import { isBlocked } from "../lib/blocked.js";
import { loadTrending } from "../lib/tmdb.js";
import { SITE_URL } from "../lib/seo.js";

export const revalidate = 3600;

export default async function sitemap() {
  let trending = [];
  try {
    trending = await loadTrending(50);
  } catch {
    trending = [];
  }
  return [
    { url: SITE_URL, changeFrequency: "daily", priority: 1 },
    { url: `${SITE_URL}/guide`, changeFrequency: "monthly", priority: 0.4 },
    ...trending
      .filter((r) => !isBlocked(r.media_type === "movie" ? "m" : "s", r.id))
      .map((r) => ({
        url: `${SITE_URL}${r.media_type === "movie" ? "/m/" : "/s/"}${r.id}`,
        changeFrequency: "weekly",
        priority: 0.8,
      })),
  ];
}
