import { loadAnime as fetchAnime, searchAnime } from "./tenrai.js";

const TMDB = "https://api.themoviedb.org/3";
const IMG = "https://image.tmdb.org/t/p";
const TTL_MS = 24 * 60 * 60 * 1000;
const mem = new Map();

function token() {
  const t = process.env.NEXT_PUBLIC_TMDB_TOKEN;
  if (!t) throw new Error("TMDB token missing");
  return t;
}

function imgUrl(path, size = "w500") {
  return path ? `${IMG}/${size}${path}` : null;
}

function pickBackdrop(detail) {
  const lang = detail?.spoken_languages?.[0]?.iso_639_1 || null;
  const backs = detail?.images?.backdrops || [];
  const hit =
    backs.find((b) => b.iso_639_1 === "en") ||
    (lang && lang !== "en" && backs.find((b) => b.iso_639_1 === lang)) ||
    backs.find((b) => b.iso_639_1 == null) ||
    backs[0];
  if (hit?.file_path) return imgUrl(hit.file_path, "w1280");
  return imgUrl(detail?.backdrop_path, "w1280");
}

function tmdbTags(d, kind) {
  const tags = (d.genres || []).map((g) => g.name).filter(Boolean);
  if (kind === "movie" && d.runtime) tags.push(`${d.runtime} min`);
  if (kind === "tv" && d.number_of_seasons) {
    tags.push(d.number_of_seasons === 1 ? "1 season" : `${d.number_of_seasons} seasons`);
  }
  const lang = d.spoken_languages?.[0]?.english_name;
  if (lang) tags.push(lang);
  return tags;
}

async function cached(key, loader) {
  const now = Date.now();
  const hit = mem.get(key);
  if (hit && hit.exp > now) return hit.data;
  const data = await loader();
  mem.set(key, { exp: now + TTL_MS, data });
  return data;
}

async function tmdbClient(path, query = {}) {
  const url = new URL(TMDB + path);
  for (const [k, v] of Object.entries(query)) {
    if (v != null) url.searchParams.set(k, String(v));
  }
  const r = await fetch(url.href, {
    headers: { Authorization: `Bearer ${token()}`, Accept: "application/json" },
    signal: AbortSignal.timeout(25_000),
  });
  if (!r.ok) throw new Error(`tmdb ${r.status}`);
  return r.json();
}

export async function searchTitles(q) {
  const raw = String(q || "").trim();
  const query = raw.toLowerCase();
  if (!query) return [];
  return cached(`search:v3:${query}`, async () => {
    const data = await tmdbClient("/search/multi", { query: raw, include_adult: "false" });
    const rows = (data.results || [])
      .filter(
        (r) =>
          (r.media_type === "movie" || r.media_type === "tv") &&
          (r.poster_path || r.vote_count > 0),
      )
      .map((r) => ({
        id: r.id,
        media_type: r.media_type,
        name: r.media_type === "movie" ? r.title : r.name,
        year: (r.release_date || r.first_air_date || "").slice(0, 4) || null,
        poster: imgUrl(r.poster_path, "w342"),
      }));
    if (rows.length) return rows;
    try {
      return await searchAnime(raw);
    } catch {
      return [];
    }
  });
}

export async function loadAnime(id) {
  return cached(`anime:v2:${id}`, () => fetchAnime(id));
}

export async function loadMovie(id) {
  return cached(`movie:${id}`, async () => {
    const movie = await tmdbClient(`/movie/${id}`, { append_to_response: "external_ids,images" });
    return {
      id: movie.id,
      name: movie.title,
      year: (movie.release_date || "").slice(0, 4) || null,
      imdb_id: movie.external_ids?.imdb_id || null,
      original_language: movie.original_language || null,
      origin_country: movie.origin_country || movie.production_countries?.map((c) => c.iso_3166_1).filter(Boolean) || [],
      backdrop: pickBackdrop(movie),
      tagline: movie.tagline || "",
      overview: movie.overview || "",
      tags: tmdbTags(movie, "movie"),
    };
  });
}

export async function loadTv(id) {
  return cached(`tv:${id}`, async () => {
    const show = await tmdbClient(`/tv/${id}`, { append_to_response: "external_ids,images" });
    const seasonMetas = (show.seasons || []).filter((s) => s.season_number > 0);
    const settled = await Promise.allSettled(
      seasonMetas.map(async (s) => {
        const detail = await tmdbClient(`/tv/${id}/season/${s.season_number}`);
        return {
          season_number: s.season_number,
          episodes: (detail.episodes || []).map((e) => ({
            episode_number: e.episode_number,
            name: e.name,
            air_date: e.air_date,
          })),
        };
      }),
    );
    const seasons = settled.map((r, i) =>
      r.status === "fulfilled"
        ? r.value
        : {
            season_number: seasonMetas[i].season_number,
            episodes: [],
          },
    );
    return {
      id: show.id,
      name: show.name,
      year: (show.first_air_date || "").slice(0, 4) || null,
      imdb_id: show.external_ids?.imdb_id || null,
      original_language: show.original_language || null,
      origin_country: show.origin_country || [],
      backdrop: pickBackdrop(show),
      tagline: show.tagline || "",
      overview: show.overview || "",
      tags: tmdbTags(show, "tv"),
      seasons,
    };
  });
}
