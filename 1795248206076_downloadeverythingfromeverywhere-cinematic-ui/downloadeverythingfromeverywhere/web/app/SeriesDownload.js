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
      <div id="seasons-area" className="zyron-seasons-heading">
        <div className="section-heading"><span>Seasons & episodes</span><small>Pick a season and explore every episode</small></div>
      </div>
      {err && <p className="status">{err}</p>}
      {tv && tv.seasons.map((s) => {
        const sKey = `s${s.season_number}`;
        return (
          <section className="dl-season zyron-season" key={s.season_number}>
            <div className="zyron-season-banner">
              {s.poster ? <img src={s.poster} alt="" loading="lazy" /> : <div className="zyron-season-poster-fallback">Z</div>}
              <div className="zyron-season-copy">
                <span className="zyron-season-kicker">SEASON {s.season_number}</span>
                <h3>{s.name || `Season ${s.season_number}`}</h3>
                <p>{s.episode_count || s.episodes.length} episodes{s.air_date ? ` · ${s.air_date.slice(0, 4)}` : ""}</p>
                {s.overview ? <small>{s.overview}</small> : null}
              </div>
              <div className="zyron-season-actions">
                <DlControl label="Download season" status={statusMap[sKey]} onClick={() => dlSeason(s.season_number)} />
                <button type="button" className="dl-caret" aria-expanded={!collapsed[sKey]} aria-label={collapsed[sKey] ? "expand season" : "collapse season"} onClick={() => setCollapsed((m) => ({ ...m, [sKey]: !m[sKey] }))}>
                  {collapsed[sKey] ? "+" : "−"}
                </button>
              </div>
            </div>
            {!collapsed[sKey] ? (
              <>
                <ResultFold results={seasonResults[s.season_number]} status={statusMap[sKey]} expect={{ title: tv.name, season: s.season_number }} />
                <div className="zyron-episode-grid">
                  {s.episodes.map((e) => {
                    const key = `s${s.season_number}e${e.episode_number}`;
                    const st = statusMap[key];
                    const shut = !!collapsed[key];
                    return (
                      <article className="zyron-episode" key={e.episode_number}>
                        {e.still ? <img className="zyron-episode-still" src={e.still} alt="" loading="lazy" /> : <div className="zyron-episode-still zyron-episode-placeholder">EP {String(e.episode_number).padStart(2, "0")}</div>}
                        <div className="zyron-episode-info">
                          <div className="zyron-episode-title"><span className="zyron-episode-number">E{String(e.episode_number).padStart(2, "0")}</span><strong>{e.name}</strong>{isNewEpisode(e.air_date) ? <span className="ep-new">NEW</span> : null}</div>
                          <div className="zyron-episode-meta">
                            {e.air_date ? <span>{e.air_date}</span> : null}
                            {e.runtime ? <span>{e.runtime} min</span> : null}
                            {e.rating > 0 ? <span>★ {e.rating.toFixed(1)}</span> : null}
                          </div>
                          {e.overview ? <p className="zyron-episode-overview">{e.overview}</p> : null}
                          <div className="dl-ep-actions">
                            <DlControl label="Download episode" status={st} onClick={() => dlEpisode(s.season_number, e.episode_number)} />
                            {st ? <button type="button" className="dl-caret" aria-expanded={!shut} aria-label={shut ? "expand results" : "collapse results"} onClick={() => setCollapsed((m) => ({ ...m, [key]: !m[key] }))}>{shut ? "+" : "−"}</button> : null}
                          </div>
                          {!shut ? <ResultFold results={epResults[key]} status={st} expect={{ title: tv.name, season: s.season_number, episode: e.episode_number }} /> : null}
                        </div>
                      </article>
                    );
                  })}
                </div>
              </>
            ) : null}
          </section>
        );
      })}
    </SiteShell>
  );
}
