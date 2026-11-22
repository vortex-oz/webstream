"use client";

import { useEffect, useRef, useState } from "react";
import { isBlocked } from "../lib/blocked.js";
import { searchTitles } from "../lib/tmdb-client.js";
import QueueMark from "./QueueMark.js";

function ResultList({ items }) {
  if (!items?.length) return null;
  return (
    <ul className="results">
      {items.map((r) => {
        const route = r.media_type === "movie" ? "m" : r.media_type === "anime" ? "a" : "s";
        const blocked = isBlocked(route, r.id);
        const kind = r.media_type === "anime" ? "anime" : r.media_type === "movie" ? "movie" : "tv";
        const inner = (
          <>
            {r.poster ? (
              <img src={r.poster} alt={`Free download ${r.name}${r.year ? ` (${r.year})` : ""}`} width={56} height={84} loading="lazy" />
            ) : null}
            <span className="result-info">
              <span className="name">
                {r.name} ({r.year || "?"})
              </span>
              <span className="meta">{kind} · {r.year || "New"}</span>
            </span>
          </>
        );
        return (
          <li key={`${r.media_type}-${r.id}`}>
            {blocked ? (
              <div className="result-card blocked">{inner}</div>
            ) : (
              <a href={`/${route}/${r.id}`} className="result-card">
                {inner}
              </a>
            )}
          </li>
        );
      })}
    </ul>
  );
}

export default function Search({ trending = [], q = "" }) {
  const [query, setQuery] = useState(q);
  const [results, setResults] = useState([]);
  const [searched, setSearched] = useState(!!q);
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(!!q);
  const primed = useRef(false);

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
    const delay = !primed.current && t === String(q).trim() ? 0 : 200;
    primed.current = true;
    const id = setTimeout(() => {
      history.replaceState(null, "", `/?q=${encodeURIComponent(t)}`);
      setSearched(true);
      setBusy(true);
      setErr(null);
      searchTitles(t)
        .then((r) => {
          if (!gone) setResults(r);
        })
        .catch((ex) => {
          if (gone) return;
          setResults([]);
          setErr(String(ex.message || ex));
        })
        .finally(() => {
          if (!gone) setBusy(false);
        });
    }, delay);
    return () => {
      gone = true;
      clearTimeout(id);
    };
  }, [query]);

  return (
    <div id="wrap">
      <header id="header">
        <h1>
          <a href="/">ZYRON</a>
          {" • "}
          <a href="/suggest">suggest</a>
        </h1>
        <a href="/guide" className="site-guide-link">
          site guide
        </a>
        <QueueMark />
      </header>

      {!searched && trending.length ? (() => {
        const featured = trending[0];
        const route = featured.media_type === "movie" ? "m" : featured.media_type === "anime" ? "a" : "s";
        return (
          <section className="zyron-featured" aria-label="Featured title">
            {featured.poster ? <img src={featured.poster.replace("w342", "w780")} alt="" /> : null}
            <div className="zyron-featured-shade" />
            <div className="zyron-featured-copy">
              <span className="zyron-featured-kicker"><b>Z</b> FEATURED ON ZYRON</span>
              <h2>{featured.name}</h2>
              <p>{featured.media_type === "movie" ? "FEATURED MOVIE" : "FEATURED SERIES"} · {featured.year || "DISCOVER NOW"}</p>
              <a href={`/${route}/${featured.id}`} className="zyron-primary">Explore title <span>›</span></a>
            </div>
          </section>
        );
      })() : null}

      <section className="search-intro" aria-label="Discover movies and shows">
        <p className="search-eyebrow">A universe of stories</p>
        <h2 className="search-title">Stories worth <span>staying up for.</span></h2>
        <p className="search-subtitle">Discover movies, series and anime. Find your next obsession on ZYRON.</p>
      </section>

      <form className="search" role="search" action="/" method="get" onSubmit={(e) => e.preventDefault()}>
        <input
          type="text"
          name="q"
          placeholder="Search movies, series and anime…"
          aria-label="Search movies, TV shows, and anime"
          autoComplete="off"
          autoFocus
          spellCheck={false}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </form>

      {searched ? (
        <>
          {err && <p className="status">{err}</p>}
          {!err && busy && <p className="status">searching...</p>}
          {!err && !busy && !results.length && <p className="status">no matches.</p>}
          {!err && !busy && <ResultList items={results} />}
        </>
      ) : (
        <>
          {trending.length ? (
            <section aria-label="trending movies and TV">
              <h2 className="section-heading"><span>Trending now</span><small>Popular across ZYRON</small></h2>
              <ResultList items={trending} />
            </section>
          ) : null}
        </>
      )}
    </div>
  );
}
