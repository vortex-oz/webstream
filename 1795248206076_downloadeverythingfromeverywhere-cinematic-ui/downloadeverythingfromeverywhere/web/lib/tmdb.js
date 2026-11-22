import { cache } from "react";
import { loadAnime as fetchAnime } from "./tenrai.js";

const TMDB = "https://api.themoviedb.org/3";
const IMG = "https://image.tmdb.org/t/p";

function token() {
  const t = process.env.TMDB_TOKEN || process.env.NEXT_PUBLIC_TMDB_TOKEN;
  if (!t) throw new Error("TMDB_TOKEN missing");
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

async function tmdb(path, query = {}) {
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

export const loadMovie = cache(async function loadMovie(id) {
  const movie = await tmdb(`/movie/${id}`, { append_to_response: "external_ids,images,credits" });
    return {
      id: movie.id,
      name: movie.title,
      year: (movie.release_date || "").slice(0, 4) || null,
      imdb_id: movie.external_ids?.imdb_id || null,
      original_language: movie.original_language || null,
      origin_country: movie.origin_country || movie.production_countries?.map((c) => c.iso_3166_1).filter(Boolean) || [],
      backdrop: pickBackdrop(movie),
      poster: imgUrl(movie.poster_path, "w500"),
      tagline: movie.tagline || "",
      overview: movie.overview || "",
      rating: Number(movie.vote_average || 0),
      voteCount: Number(movie.vote_count || 0),
      runtime: movie.runtime || null,
      cast: (movie.credits?.cast || []).slice(0, 10).map((p) => ({ id: p.id, name: p.name, character: p.character || "", photo: imgUrl(p.profile_path, "w185") })),
      tags: tmdbTags(movie, "movie"),
    };
});

export const loadTv = cache(async function loadTv(id) {
  const show = await tmdb(`/tv/${id}`, { append_to_response: "external_ids,images,credits" });
  const seasonMetas = (show.seasons || []).filter((s) => s.season_number > 0);
  const settled = await Promise.allSettled(
    seasonMetas.map(async (s) => {
      const detail = await tmdb(`/tv/${id}/season/${s.season_number}`);
      return {
        season_number: s.season_number,
        name: s.name || `Season ${s.season_number}`,
        overview: s.overview || "",
        poster: imgUrl(s.poster_path || detail.poster_path, "w500"),
        air_date: s.air_date || null,
        episode_count: s.episode_count || (detail.episodes || []).length,
        episodes: (detail.episodes || []).map((e) => ({
          episode_number: e.episode_number,
          name: e.name,
          overview: e.overview || "",
          air_date: e.air_date,
          still: imgUrl(e.still_path, "w500"),
          rating: Number(e.vote_average || 0),
          runtime: e.runtime || null,
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
      poster: imgUrl(show.poster_path, "w500"),
      tagline: show.tagline || "",
      overview: show.overview || "",
      rating: Number(show.vote_average || 0),
      voteCount: Number(show.vote_count || 0),
      status: show.status || "",
      cast: (show.credits?.cast || []).slice(0, 10).map((p) => ({ id: p.id, name: p.name, character: p.character || "", photo: imgUrl(p.profile_path, "w185") })),
      tags: tmdbTags(show, "tv"),
      seasons,
    };
});

export const loadAnime = cache(fetchAnime);

/** Top trending movies + TV (SSR into the home page HTML). */
export const loadTrending = cache(async function loadTrending(limit = 50) {
  const out = [];
  let page = 1;
  while (out.length < limit && page <= 3) {
    const data = await tmdb("/trending/all/day", { page });
    for (const r of data.results || []) {
      if (r.media_type !== "movie" && r.media_type !== "tv") continue;
      out.push({
        id: r.id,
        media_type: r.media_type,
        name: r.media_type === "movie" ? r.title : r.name,
        year: (r.release_date || r.first_air_date || "").slice(0, 4) || null,
        poster: imgUrl(r.poster_path, "w342"),
      });
      if (out.length >= limit) break;
    }
    if (!(data.results || []).length) break;
    page += 1;
  }
  return out;
});
