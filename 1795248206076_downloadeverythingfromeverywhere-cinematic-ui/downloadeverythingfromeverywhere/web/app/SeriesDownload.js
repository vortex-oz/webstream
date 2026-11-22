"use client";

import { useEffect, useRef, useState } from "react";
import { DlControl, MediaHero, ResultFold, SiteShell, huntIds, runDownloadStream, gateHunt } from "./dl.js";
import { loadTv } from "../lib/tmdb-client.js";

const NEW_MS = 48 * 60 * 60 * 1000;

function isNewEpisode(airDate) {
  if (!airDate) return false;
  const t = Date.parse(airDate);
  if (!Number.isFinite(t)) return false;
  const age = Date.now() - t;
  return age >= 0 && age <= NEW_MS;
}

export default function SeriesDownload({ id, initial = null, error: initialError = null, load = loadTv }) {
  const [tv, setTv] = useState(initial);
  const [err, setErr] = useState(initialError);
  const [seasonResults, setSeasonResults] = useState({});
  const [epResults, setEpResults] = useState({});
  const [statusMap, setStatusMap] = useState({});
  const [collapsed, setCollapsed] = useState({});
  const [seasonSheetOpen, setSeasonSheetOpen] = useState(false);
  const [selectedSeason, setSelectedSeason] = useState(null);
  const runId = useRef(0);
  const alive = useRef(true);
  const jobs = useRef(new Map());

  useEffect(() => {
    const my = ++runId.current;
    alive.current = true;
    setSeasonResults({});
    setEpResults({});
    setStatusMap({});
    setCollapsed({});
    for (const ac of jobs.current.values()) ac.abort();
    jobs.current.clear();

    if (initial && String(initial.id) === String(id)) {
      setTv(initial);
      setErr(initialError);
      setSelectedSeason(initial.seasons?.[0]?.season_number ?? null);
      return () => {
        alive.current = false;
        for (const ac of jobs.current.values()) ac.abort();
        jobs.current.clear();
      };
    }

    setTv(null);
    setErr(null);
    (async () => {
      try {
        const data = await load(id);
        if (!alive.current || my !== runId.current) return;
        setTv(data);
        setSelectedSeason(data.seasons?.[0]?.season_number ?? null);
      } catch (e) {
        if (alive.current && my === runId.current) setErr(String(e.message || e));
      }
    })();
    return () => {
      alive.current = false;
      for (const ac of jobs.current.values()) ac.abort();
      jobs.current.clear();
    };
  }, [id, initial, initialError, load]);

  async function dlSeason(season) {
    const key = `s${season}`;
    if ((statusMap[key] && statusMap[key].phase !== "done") || !tv) return;
    const token = await gateHunt();
    if (token === null) return;
    const my = runId.current;
    const ac = new AbortController();
    jobs.current.get(key)?.abort();
    jobs.current.set(key, ac);
    try {
      await runDownloadStream(
        {
          mode: "series",
          title: tv.query || tv.name,
          year: tv.year,
          ...huntIds(tv),
          season,
          turnstile: token,
        },
        {
          signal: ac.signal,
          setStatus: (st) => {
            if (alive.current && my === runId.current) setStatusMap((m) => ({ ...m, [key]: st }));
          },
          setResults: (rows) => {
            if (alive.current && my === runId.current) setSeasonResults((d) => ({ ...d, [season]: rows }));
          },
        },
      );
    } finally {
      jobs.current.delete(key);
    }
  }

  async function dlEpisode(season, episode) {
    const key = `s${season}e${episode}`;
    if ((statusMap[key] && statusMap[key].phase !== "done") || !tv) return;
    const token = await gateHunt();
    if (token === null) return;
    const my = runId.current;
    const ac = new AbortController();
    jobs.current.get(key)?.abort();
    jobs.current.set(key, ac);
    try {
      await runDownloadStream(
        {
          mode: "episode",
          title: tv.query || tv.name,
          year: tv.year,
          ...huntIds(tv),
          season,
          episode,
          turnstile: token,
        },
        {
          signal: ac.signal,
          setStatus: (st) => {
            if (alive.current && my === runId.current) setStatusMap((m) => ({ ...m, [key]: st }));
          },
          setResults: (rows) => {
            if (alive.current && my === runId.current) setEpResults((d) => ({ ...d, [key]: rows }));
          },
        },
      );
    } finally {
      jobs.current.delete(key);
    }
  }

  return (
    <SiteShell>
      <MediaHero item={tv} />
      <div id="seasons-area" className="zyron-seasons-section">
        <div className="zyron-rail-heading"><div><h2>Seasons & episodes</h2><p>Choose a season and explore every chapter</p></div></div>
      </div>
      {err && <p className="status">{err}</p>}
      {tv && tv.seasons.map((s) => {
        const sKey = `s${s.season_number}`;
        const isOpen = !collapsed[sKey];
        return (
          <section className="zyron-season-block" key={s.season_number}>
            <button type="button" className="zyron-season-heading" onClick={() => setCollapsed((m) => ({ ...m, [sKey]: !m[sKey] }))} aria-expanded={isOpen}>
              {s.poster ? <img src={s.poster} alt="" loading="lazy" /> : <span className="zyron-season-fallback">Z</span>}
              <span className="zyron-season-heading-copy">
                <small>SEASON {String(s.season_number).padStart(2, "0")}</small>
                <b>{s.name || `Season ${s.season_number}`}</b>
                <em>{s.episode_count || s.episodes.length} episodes{s.air_date ? ` · ${s.air_date.slice(0, 4)}` : ""}</em>
                {s.overview ? <span>{s.overview}</span> : null}
              </span>
              <span className="zyron-season-chevron">{isOpen ? "−" : "+"}</span>
            </button>
            {isOpen ? (
              <div className="zyron-episode-list">
                <ResultFold results={seasonResults[s.season_number]} status={statusMap[sKey]} expect={{ title: tv.name, season: s.season_number }} />
                {s.episodes.map((e) => {
                  const key = `s${s.season_number}e${e.episode_number}`;
                  const st = statusMap[key];
                  const shut = !!collapsed[key];
                  return (
                    <article className="zyron-episode-row" key={e.episode_number}>
                      {e.still ? <img className="zyron-episode-thumb" src={e.still} alt="" loading="lazy" /> : <div className="zyron-episode-thumb zyron-episode-placeholder">EP {String(e.episode_number).padStart(2, "0")}</div>}
                      <div className="zyron-episode-details">
                        <div className="zyron-episode-title"><span>E{String(e.episode_number).padStart(2, "0")}</span><b>{e.name}</b>{isNewEpisode(e.air_date) ? <i>NEW</i> : null}</div>
                        <div className="zyron-episode-meta">
                          {e.air_date ? <span>{e.air_date}</span> : null}
                          {e.runtime ? <span>{e.runtime} min</span> : null}
                          {e.rating > 0 ? <span>★ {e.rating.toFixed(1)}</span> : null}
                        </div>
                        {e.overview ? <p>{e.overview}</p> : null}
                        {st ? <button type="button" className="zyron-show-links" onClick={() => setCollapsed((m) => ({ ...m, [key]: !m[key] }))}>{shut ? "Show download links" : "Hide download links"}</button> : null}
                      </div>
                      <div className="zyron-episode-download">
                        <DlControl label="Download" status={st} onClick={() => dlEpisode(s.season_number, e.episode_number)} />
                      </div>
                      {!shut && st ? <div className="zyron-episode-results"><ResultFold results={epResults[key]} status={st} expect={{ title: tv.name, season: s.season_number, episode: e.episode_number }} /></div> : null}
                    </article>
                  );
                })}
              </div>
            ) : null}
          </section>
        );
      })}

      {tv?.seasons?.length ? (
        <>
          <div className="zyron-bottom-action zyron-series-dock">
            <div><b>Season downloads</b><small>Find all available links for a full season.</small></div>
            <button type="button" className="zyron-watch-button" onClick={() => setSeasonSheetOpen(true)}>Choose season <span>⌃</span></button>
          </div>
          {seasonSheetOpen ? (
            <div className="zyron-sheet-backdrop" role="presentation" onClick={() => setSeasonSheetOpen(false)}>
              <section className="zyron-season-sheet" role="dialog" aria-modal="true" aria-label="Choose a season" onClick={(e) => e.stopPropagation()}>
                <div className="zyron-sheet-handle" />
                <div className="zyron-sheet-title"><div><small>ZYRON DOWNLOADS</small><h2>Choose your season</h2></div><button type="button" onClick={() => setSeasonSheetOpen(false)} aria-label="Close">×</button></div>
                <div className="zyron-season-options">
                  {tv.seasons.map((s) => (
                    <button type="button" key={s.season_number} className={selectedSeason === s.season_number ? "selected" : ""} onClick={() => setSelectedSeason(s.season_number)}>
                      <span>Season {s.season_number}</span><small>{s.episode_count || s.episodes.length} episodes</small><b>{selectedSeason === s.season_number ? "✓" : "›"}</b>
                    </button>
                  ))}
                </div>
                <DlControl label="Find season downloads" status={selectedSeason != null ? statusMap[`s${selectedSeason}`] : null} locked={selectedSeason == null} onClick={() => { dlSeason(selectedSeason); setSeasonSheetOpen(false); }} />
              </section>
            </div>
          ) : null}
        </>
      ) : null}
    </SiteShell>
  );
}
