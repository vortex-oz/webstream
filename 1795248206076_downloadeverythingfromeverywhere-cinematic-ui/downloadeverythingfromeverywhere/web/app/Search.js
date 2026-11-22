"use client";

import { useEffect, useRef, useState } from "react";
import { isBlocked } from "../lib/blocked.js";
import { searchTitles } from "../lib/tmdb-client.js";

function routeFor(item) {
  return item.media_type === "movie" ? "m" : item.media_type === "anime" ? "a" : "s";
}

function PosterCard({ item, index = 0 }) {
  const route = routeFor(item);
  const blocked = isBlocked(route, item.id);
  const href = `/${route}/${item.id}`;
  return (
    <a
      href={blocked ? undefined : href}
      className={`zyron-poster-card${blocked ? " is-blocked" : ""}`}
      aria-label={`${item.name}${item.year ? ` (${item.year})` : ""}`}
      style={{ "--card-index": index }}
      onClick={blocked ? (e) => e.preventDefault() : undefined}
    >
      {item.poster ? <img src={item.poster.replace("w342", "w500")} alt="" loading="lazy" /> : <span className="poster-fallback">ZYRON</span>}
      <span className="poster-gradient" />
      <span className="poster-copy">
        <b>{item.name}</b>
        <small>{item.year || "Discover"} <i>·</i> {item.media_type === "movie" ? "Movie" : item.media_type === "anime" ? "Anime" : "Series"}</small>
      </span>
      <span className="poster-play" aria-hidden="true">▶</span>
    </a>
  );
}

function PosterRail({ title, subtitle, items, id }) {
  const rail = useRef(null);
  if (!items?.length) return null;
  return (
    <section className="zyron-rail" id={id}>
      <div className="zyron-rail-heading">
        <div><h2>{title}</h2>{subtitle ? <p>{subtitle}</p> : null}</div>
        <div className="rail-arrows">
          <button type="button" aria-label={`Scroll ${title} left`} onClick={() => rail.current?.scrollBy({ left: -600, behavior: "smooth" })}>‹</button>
          <button type="button" aria-label={`Scroll ${title} right`} onClick={() => rail.current?.scrollBy({ left: 600, behavior: "smooth" })}>›</button>
        </div>
      </div>
      <div className="zyron-rail-track" ref={rail}>
        {items.map((item, i) => <PosterCard key={`${item.media_type}-${item.id}`} item={item} index={i} />)}
      </div>
    </section>
  );
}

export default function Search({ trending = [], q = "" }) {
  const [query, setQuery] = useState(q);
  const [results, setResults] = useState([]);
  const [searched, setSearched] = useState(!!q);
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(!!q);
  const [slide, setSlide] = useState(0);
  const primed = useRef(false);
  const featured = trending.slice(0, 8);

  useEffect(() => {
    if (featured.length < 2) return;
    const timer = window.setInterval(() => setSlide((v) => (v + 1) % featured.length), 5500);
    return () => window.clearInterval(timer);
  }, [featured.length]);

  useEffect(() => {
    const t = query.trim();
    if (!t) {
      setResults([]);
      setSearched(false);
      setErr(null);
      setBusy(false);
      if (typeof location !== "undefined" && location.search) history.replaceState(null, "", "/");
      return;
    }
    let gone = false;
    const delay = !primed.current && t === String(q).trim() ? 0 : 250;
    primed.current = true;
    const id = setTimeout(() => {
      history.replaceState(null, "", `/?q=${encodeURIComponent(t)}`);
      setSearched(true);
      setBusy(true);
      setErr(null);
      searchTitles(t).then((r) => { if (!gone) setResults(r); })
        .catch((ex) => { if (!gone) { setResults([]); setErr(String(ex.message || ex)); } })
        .finally(() => { if (!gone) setBusy(false); });
    }, delay);
    return () => { gone = true; clearTimeout(id); };
  }, [query]);

  const current = featured[slide];
  const movieItems = trending.filter((x) => x.media_type === "movie");
  const seriesItems = trending.filter((x) => x.media_type === "tv");
  const animeItems = trending.filter((x) => x.media_type === "anime");

  return (
    <div id="wrap" className="zyron-app">
      <header id="header" className="zyron-topbar">
        <a className="zyron-wordmark" href="/" aria-label="ZYRON home">ZYRON<span>+</span></a>
        <nav className="zyron-main-nav" aria-label="Main navigation">
          <a className="active" href="/">Home</a>
          <a href="#movies">Movies</a>
          <a href="#series">Series</a>
          <a href="#anime">Anime</a>
        </nav>
        <a className="zyron-search-shortcut" href="#search-box" aria-label="Search">⌕</a>
      </header>

      {!searched && current ? (
        <section className="zyron-slider" aria-label="Featured titles">
          {featured.map((item, i) => {
            const route = routeFor(item);
            return (
              <div className={`zyron-slide${i === slide ? " is-active" : ""}`} key={`${item.media_type}-${item.id}`}>
                {item.backdrop ? <img className="zyron-slide-image" src={item.backdrop} alt="" /> : item.poster ? <img className="zyron-slide-image" src={item.poster.replace("w342", "w1280")} alt="" /> : null}
                <div className="zyron-slide-shade" />
                <div className="zyron-slide-content">
                  <span className="zyron-overline"><i /> THE ZYRON COLLECTION</span>
                  <span className="zyron-slide-type">{item.media_type === "movie" ? "FEATURED FILM" : "FEATURED SERIES"} · {item.year || "NOW DISCOVERING"}</span>
                  <h1>{item.name}</h1>
                  <p>Find your next world to get lost in.</p>
                  <a className="zyron-watch-button" href={`/${route}/${item.id}`}><span>▶</span> Explore title</a>
                </div>
              </div>
            );
          })}
          <div className="zyron-slider-controls">
            <span>{String(slide + 1).padStart(2, "0")} <i>/</i> {String(featured.length).padStart(2, "0")}</span>
            <div>{featured.map((_, i) => <button key={i} className={i === slide ? "active" : ""} onClick={() => setSlide(i)} aria-label={`Show featured title ${i + 1}`} />)}</div>
          </div>
        </section>
      ) : null}

      <section className="zyron-search-area" id="search-box">
        <div><span className="zyron-overline">YOUR NEXT WATCH STARTS HERE</span><h2>What are you in the mood for?</h2></div>
        <form className="zyron-search-form" role="search" action="/" method="get" onSubmit={(e) => e.preventDefault()}>
          <span>⌕</span>
          <input type="search" name="q" placeholder="Search movies, series and anime..." aria-label="Search movies, series and anime" autoComplete="off" spellCheck={false} value={query} onChange={(e) => setQuery(e.target.value)} />
          {query ? <button type="button" onClick={() => setQuery("")} aria-label="Clear search">×</button> : null}
        </form>
      </section>

      {searched ? (
        <section className="zyron-search-results">
          <div className="zyron-rail-heading"><div><h2>Search results</h2><p>{results.length ? `${results.length} titles found` : "Explore something new"}</p></div></div>
          {err ? <p className="status">{err}</p> : busy ? <p className="zyron-empty">Searching the collection…</p> : results.length ? <div className="zyron-poster-grid">{results.map((item, i) => <PosterCard key={`${item.media_type}-${item.id}`} item={item} index={i} />)}</div> : <p className="zyron-empty">No titles found. Try another search.</p>}
        </section>
      ) : (
        <>
          <PosterRail title="Trending now" subtitle="The titles everyone is talking about" items={trending.slice(0, 18)} id="trending" />
          <PosterRail title="Movies" subtitle="Big-screen stories, ready to discover" items={movieItems} id="movies" />
          <PosterRail title="Series to binge" subtitle="Your next all-night watch" items={seriesItems} id="series" />
          {animeItems.length ? <PosterRail title="Anime worlds" subtitle="Step into another universe" items={animeItems} id="anime" /> : null}
        </>
      )}

      <footer className="zyron-footer"><a className="zyron-wordmark" href="/">ZYRON<span>+</span></a><p>Stories worth staying up for.</p><small>Discover • Explore • Enjoy</small></footer>
      <nav className="zyron-bottom-nav" aria-label="Bottom navigation">
        <a className="selected" href="/"><span>⌂</span><small>Home</small></a>
        <a href="#search-box"><span>⌕</span><small>Search</small></a>
        <a href="#movies"><span>▣</span><small>Movies</small></a>
        <a href="#series"><span>▤</span><small>Series</small></a>
      </nav>
    </div>
  );
}
