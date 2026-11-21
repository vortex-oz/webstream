const TENRAI = "https://api.tenrai.org/v1";
const MOVIE_TYPES = new Set(["Movie", "Music", "CM", "PV"]);

async function tenrai(path, query = {}) {
  const url = new URL(TENRAI + path);
  for (const [k, v] of Object.entries(query)) {
    if (v != null && v !== "") url.searchParams.set(k, String(v));
  }
  let last = { status: 0, data: {} };
  for (let i = 0; i < 4; i++) {
    const r = await fetch(url.href, {
      headers: { Accept: "application/json" },
      signal: AbortSignal.timeout(25_000),
    });
    const data = await r.json().catch(() => ({}));
    last = { status: r.status, data };
    if (r.status === 429) {
      const n = Number(r.headers.get("retry-after"));
      const wait = Number.isFinite(n) && n > 0 ? n : 1 + i;
      await new Promise((ok) => setTimeout(ok, Math.min(8, wait) * 1000));
      continue;
    }
    if (!r.ok) throw new Error(data.message || `tenrai ${r.status}`);
    return data;
  }
  throw new Error(last.data.message || `tenrai ${last.status}`);
}

function posterOf(d) {
  return (
    d?.images?.jpg?.large_image_url ||
    d?.images?.jpg?.image_url ||
    d?.images?.webp?.large_image_url ||
    null
  );
}

function backdropOf(d) {
  const imgs = d?.trailer?.images || {};
  return imgs.maximum_image_url || imgs.large_image_url || imgs.medium_image_url || posterOf(d);
}

function yearOf(d) {
  const y = d.year || d.aired?.prop?.from?.year || String(d.aired?.from || "").slice(0, 4);
  return y ? String(y) : null;
}

function displayName(d) {
  return d.title_english || d.title || "";
}

function seasonOf(title) {
  const t = String(title || "");
  const nth = t.match(/(\d+)(?:st|nd|rd|th)\s+season/i);
  if (nth) return Number(nth[1]);
  const s = t.match(/\bseason\s+(\d+)\b/i);
  if (s) return Number(s[1]);
  return 1;
}

function isMovie(d) {
  if (MOVIE_TYPES.has(d.type)) return true;
  if (d.type === "TV") return false;
  return !d.episodes || d.episodes <= 1;
}

function mapEpisode(e) {
  const n = e.mal_id;
  return {
    episode_number: n,
    name: e.title || `Episode ${n}`,
    air_date: e.aired ? String(e.aired).slice(0, 10) : null,
  };
}

async function loadEpisodes(id) {
  const first = await tenrai(`/anime/${id}/episodes`);
  const last = Math.min(first.pagination?.last_visible_page || 1, 20);
  let rows = first.data || [];
  for (let page = 2; page <= last; page++) {
    const p = await tenrai(`/anime/${id}/episodes`, { page });
    rows = rows.concat(p.data || []);
  }
  return rows;
}

export async function searchAnime(q) {
  const query = String(q || "").trim();
  if (!query) return [];
  const data = await tenrai("/anime", { q: query, limit: 25, sfw: "true" });
  return (data.data || [])
    .filter(
      (r) =>
        r?.mal_id &&
        (posterOf(r) || r.scored_by > 0) &&
        r.type !== "Hentai" &&
        !String(r.rating || "")
          .toLowerCase()
          .startsWith("rx"),
    )
    .map((r) => ({
      id: r.mal_id,
      media_type: "anime",
      name: displayName(r),
      year: yearOf(r),
      poster: posterOf(r),
    }));
}

export async function loadAnime(id) {
  const detail = await tenrai(`/anime/${id}`);
  const d = detail.data;
  if (!d) throw new Error("anime not found");
  const movie = isMovie(d);
  let episodes = [];
  if (!movie) {
    const episodeRows = await loadEpisodes(id).catch(() => []);
    episodes = (episodeRows || []).map(mapEpisode);
    if (!episodes.length && d.episodes > 0) {
      episodes = Array.from({ length: d.episodes }, (_, i) => ({
        episode_number: i + 1,
        name: `Episode ${i + 1}`,
        air_date: null,
      }));
    }
  }
  const tags = [
    ...(d.genres || []).map((g) => g.name).filter(Boolean),
    d.type,
    movie ? d.duration : d.episodes ? (d.episodes === 1 ? "1 episode" : `${d.episodes} episodes`) : null,
    movie ? null : d.duration,
  ].filter(Boolean);
  return {
    id: d.mal_id,
    mal_id: d.mal_id,
    kind: movie ? "movie" : "tv",
    name: displayName(d),
    query: d.title || displayName(d),
    year: yearOf(d),
    imdb_id: null,
    backdrop: backdropOf(d),
    tagline: "",
    overview: d.synopsis || "",
    tags,
    seasons: movie ? [] : [{ season_number: seasonOf(`${d.title_english || ""} ${d.title || ""}`), episodes }],
  };
}
