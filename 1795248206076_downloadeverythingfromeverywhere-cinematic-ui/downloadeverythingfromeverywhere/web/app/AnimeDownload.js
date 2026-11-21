"use client";

import MovieDownload from "./MovieDownload";
import SeriesDownload from "./SeriesDownload";
import { MediaHero, SiteShell } from "./dl.js";
import { loadAnime } from "../lib/tmdb-client.js";

export default function AnimeDownload({ id, initial = null, error: initialError = null }) {
  if (initialError && !initial) {
    return (
      <SiteShell>
        <MediaHero item={null} />
        <p className="status">{initialError}</p>
      </SiteShell>
    );
  }
  const Comp = initial?.kind === "movie" ? MovieDownload : SeriesDownload;
  return <Comp id={id} initial={initial} error={initialError} load={loadAnime} />;
}
