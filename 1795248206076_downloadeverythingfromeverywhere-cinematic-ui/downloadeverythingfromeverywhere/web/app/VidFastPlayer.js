"use client";

import { useEffect, useMemo } from "react";

function buildVidFastUrl({ id, type = "movie", season, episode }) {
  const mediaId = String(id || "").trim();
  if (!mediaId) return null;
  const base = type === "tv"
    ? `https://vidfast.vc/tv/${encodeURIComponent(mediaId)}/${Number(season)}/${Number(episode)}`
    : `https://vidfast.vc/movie/${encodeURIComponent(mediaId)}`;
  const params = new URLSearchParams({
    title: "true",
    poster: "true",
    autoPlay: "true",
    theme: "7C9CFF",
    hideServer: "true",
    fullscreenButton: "true",
    chromecast: "true",
  });
  if (type === "tv") {
    params.set("nextButton", "true");
    params.set("autoNext", "true");
  }
  return `${base}?${params.toString()}`;
}

export default function VidFastPlayer({ id, type = "movie", season, episode, title, onClose }) {
  const src = useMemo(() => buildVidFastUrl({ id, type, season, episode }), [id, type, season, episode]);

  useEffect(() => {
    if (!src) return undefined;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onKey = (event) => { if (event.key === "Escape") onClose?.(); };
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = previous;
      window.removeEventListener("keydown", onKey);
    };
  }, [src, onClose]);

  if (!src) return null;
  return (
    <div className="zyron-player-overlay" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose?.(); }}>
      <section className="zyron-player-dialog" role="dialog" aria-modal="true" aria-label={`Watch ${title || "video"}`}>
        <header className="zyron-player-bar">
          <div><span className="zyron-player-brand">ZYRON<span>+</span></span><b>{title || "Now Playing"}</b>{type === "tv" ? <small>Season {season} · Episode {episode}</small> : <small>Movie</small>}</div>
          <button type="button" className="zyron-player-close" onClick={onClose} aria-label="Close player">×</button>
        </header>
        <div className="zyron-player-frame-wrap">
          <iframe
            key={src}
            src={src}
            title={`VidFast player - ${title || "ZYRON"}`}
            allow="autoplay; encrypted-media; picture-in-picture; fullscreen; clipboard-write; web-share"
            allowFullScreen
            referrerPolicy="origin"
          />
        </div>
        <div className="zyron-player-foot"><span>Streaming powered by VidFast</span><span>Playback availability depends on the provider.</span></div>
      </section>
    </div>
  );
}
