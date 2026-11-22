"use client";

import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { sortDownloadResults, sortDownloadGroups, siteLabel, SITE_RANK, isDirectLink, isSemiDirectLink, isTelegramLink } from "../lib/scrapers/_rank.js";
import { groupDownloadLinks, possibleWrongFile } from "../lib/scrapers/_tags.js";
import { SCRAPE_API } from "../lib/scrape-api.js";
import QueueMark from "./QueueMark.js";

const QUALITY_ORDER = ["2160p", "1080p", "720p", "540p", "480p", "400p", "360p"];
const METHOD_ORDER = ["REMUX", "BluRay", "WEB-DL", "WEBRip", "HDTV", "HDRip", "DVDRip", "Hybrid"];
const LANG_ORDER = ["English", "Hindi", "Tamil", "Telugu", "Indonesian", "Dual", "Multi"];
const LANG_SET = new Set(LANG_ORDER);
const QUALITY_SET = new Set([...QUALITY_ORDER, "4K", "UHD"]);
const METHOD_SET = new Set(METHOD_ORDER);
const PROVIDER_SET = new Set(Object.keys(SITE_RANK));

function isProvider(t) {
  return PROVIDER_SET.has(t);
}

function isQuality(t) {
  return QUALITY_SET.has(t) || /^\d{3,4}p$/i.test(t);
}

function isMethod(t) {
  return METHOD_SET.has(t);
}

function isLang(t) {
  return LANG_SET.has(t);
}

function SiteName({ name, href }) {
  const ref = useRef(null);
  const n = String(name || "");
  const [text, setText] = useState(n);

  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ctx = document.createElement("canvas").getContext("2d");
    const fit = () => {
      ctx.font = getComputedStyle(el).font;
      const w = el.clientWidth;
      const tw = (s) => ctx.measureText(s).width;
      if (tw(n) <= w || n.length <= 3) {
        setText((t) => (t === n ? t : n));
        return;
      }
      const tail = n.slice(-3);
      let lo = 0;
      let hi = n.length - 3;
      while (lo < hi) {
        const mid = (lo + hi + 1) >> 1;
        if (tw(n.slice(0, mid) + "..." + tail) <= w) lo = mid;
        else hi = mid - 1;
      }
      const next = n.slice(0, lo) + "..." + tail;
      setText((t) => (t === next ? t : next));
    };
    fit();
    const ro = new ResizeObserver(fit);
    ro.observe(el);
    return () => ro.disconnect();
  }, [n]);

  const inner = text;
  return href ? (
    <a ref={ref} href={href} target="_blank" rel="noreferrer" className="dl-site" title={n}>
      {inner}
    </a>
  ) : (
    <span ref={ref} className="dl-site" title={n}>
      {inner}
    </span>
  );
}

const GENERIC_TAG = /^(Movie|Episode|Pack|Subs|Condensed Audio|Telegram)$/i;
const SIZE_TAG = /^\d+(?:\.\d+)?(KB|MB|GB|TB)$/i;

function isSizeTag(t) {
  return SIZE_TAG.test(t);
}

function sortByOrder(arr, order) {
  return arr.sort((a, b) => {
    const ia = order.indexOf(a);
    const ib = order.indexOf(b);
    return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib) || a.localeCompare(b);
  });
}

function organizeTags(tags) {
  const quals = [];
  const methods = [];
  const langs = [];
  const other = [];
  const providers = [];
  const sizes = [];
  const seen = new Set();
  for (const t of tags || []) {
    if (!t || seen.has(t) || GENERIC_TAG.test(t)) continue;
    seen.add(t);
    if (isProvider(t)) providers.push(t);
    else if (isQuality(t)) quals.push(t);
    else if (isMethod(t)) methods.push(t);
    else if (isLang(t)) langs.push(t);
    else if (isSizeTag(t)) sizes.push(t);
    else other.push(t);
  }
  sortByOrder(quals, QUALITY_ORDER);
  sortByOrder(methods, METHOD_ORDER);
  sortByOrder(langs, LANG_ORDER);
  providers.sort((a, b) => (SITE_RANK[a] ?? 999) - (SITE_RANK[b] ?? 999) || a.localeCompare(b));
  other.sort((a, b) => a.localeCompare(b));
  return { providers, qualities: quals, methods, tags: [...langs, ...other], sizes };
}

function displayTag(t) {
  return isProvider(t) ? siteLabel(t) : t;
}

const TURNSTILE_SITEKEY = process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY;
const HUNT_CLICKS = 5;

let huntClicks = 0;
const capListeners = new Set();
let openTurnstile = null;
let turnstileBusy = false;

function notifyCap() {
  for (const fn of capListeners) fn(huntClicks);
}

function useHuntCap() {
  const [n, setN] = useState(huntClicks);
  useEffect(() => {
    capListeners.add(setN);
    return () => capListeners.delete(setN);
  }, []);
  return n >= HUNT_CLICKS;
}

function loadTurnstile() {
  if (typeof window === "undefined") return Promise.reject();
  if (window.turnstile) return Promise.resolve();
  if (window.__defeTurnstile) return window.__defeTurnstile;
  window.__defeTurnstile = new Promise((resolve, reject) => {
    const s = document.createElement("script");
    s.src = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";
    s.async = true;
    s.onload = () => resolve();
    s.onerror = reject;
    document.head.appendChild(s);
  });
  return window.__defeTurnstile;
}

function TurnstileHost() {
  const [open, setOpen] = useState(false);
  const box = useRef(null);
  const pending = useRef(null);

  useEffect(() => {
    openTurnstile = () =>
      new Promise((resolve) => {
        pending.current = resolve;
        setOpen(true);
      });
    return () => {
      openTurnstile = null;
      pending.current?.(null);
      pending.current = null;
    };
  }, []);

  useEffect(() => {
    if (!open) return;
    let gone = false;
    (async () => {
      try {
        await loadTurnstile();
      } catch {
        pending.current?.(null);
        pending.current = null;
        setOpen(false);
        return;
      }
      await new Promise((r) => setTimeout(r, 50));
      if (gone || !box.current || !window.turnstile) return;
      window.turnstile.render(box.current, {
        sitekey: TURNSTILE_SITEKEY,
        theme: "dark",
        callback(token) {
          pending.current?.(token);
          pending.current = null;
          setOpen(false);
        },
      });
    })();
    return () => {
      gone = true;
    };
  }, [open]);

  function cancel() {
    pending.current?.(null);
    pending.current = null;
    setOpen(false);
  }

  if (!open) return null;
  return (
    <div className="cf-box">
      <div ref={box} />
      <p>
        <button type="button" onClick={cancel}>
          cancel
        </button>
      </p>
    </div>
  );
}

export async function gateHunt() {
  if (huntClicks >= HUNT_CLICKS || turnstileBusy) return null;
  let token;
  if (TURNSTILE_SITEKEY) {
    if (!openTurnstile) return null;
    turnstileBusy = true;
    try {
      token = await openTurnstile();
      if (!token) return null;
    } catch {
      return null;
    } finally {
      turnstileBusy = false;
    }
  }
  huntClicks += 1;
  notifyCap();
  return token;
}

async function streamDownloads(body, { onEvent, signal }) {
  const leave = new AbortController();
  const onGone = () => {
    try {
      leave.abort();
    } catch {}
  };
  if (typeof window !== "undefined") {
    window.addEventListener("pagehide", onGone);
    window.addEventListener("beforeunload", onGone);
  }
  if (signal) {
    if (signal.aborted) onGone();
    else signal.addEventListener("abort", onGone, { once: true });
  }
  try {
    const r = await fetch(SCRAPE_API, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/x-ndjson", "X-Defe-Manual": "1" },
      body: JSON.stringify(body),
      signal: leave.signal,
      cache: "no-store",
    });
    if (r.status === 429) {
      onEvent({ t: "busy" });
      return;
    }
    if (!r.ok || !r.body) throw new Error("download failed");
    const reader = r.body.getReader();
    const dec = new TextDecoder();
    let buf = "";
    while (true) {
      if (leave.signal.aborted) {
        try {
          await reader.cancel();
        } catch {}
        throw new DOMException("Aborted", "AbortError");
      }
      const { value, done } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      const parts = buf.split("\n");
      buf = parts.pop() || "";
      for (const line of parts) {
        if (!line.trim()) continue;
        onEvent(JSON.parse(line));
      }
    }
    buf += dec.decode();
    if (buf.trim()) onEvent(JSON.parse(buf));
  } finally {
    if (typeof window !== "undefined") {
      window.removeEventListener("pagehide", onGone);
      window.removeEventListener("beforeunload", onGone);
    }
    try {
      leave.abort();
    } catch {}
    if (signal) signal.removeEventListener("abort", onGone);
  }
}

function statusLabel(st) {
  if (!st) return null;
  if (st.phase === "queue") return `${st.n || 0} in queue`;
  if (st.phase === "done") {
    if (st.msg) return st.msg;
    return st.found ? `done - ${st.found} site${st.found === 1 ? "" : "s"}` : "done - no links";
  }
  if (st.site) return `getting ${siteLabel(st.site)}... (${st.done || 0}/${st.total || "?"})`;
  return `getting... (${st.done || 0}/${st.total || "?"})`;
}

export function MediaHero({ item }) {
  const [ok, setOk] = useState(true);
  useEffect(() => setOk(true), [item?.backdrop]);
  if (!item) return <div className="zyron-detail-loading"><p className="status">Loading title…</p></div>;
  const isSeries = Array.isArray(item.seasons) && item.seasons.length > 0;
  const score = Number(item.rating || 0);
  return (
    <section className="zyron-detail-hero">
      {item.backdrop && ok ? <img className="zyron-detail-backdrop" src={item.backdrop} alt="" onError={() => setOk(false)} /> : null}
      <div className="zyron-detail-vignette" />
      <div className="zyron-detail-layout">
        {item.poster ? <img className="zyron-detail-poster" src={item.poster} alt={`${item.name} poster`} /> : null}
        <div className="zyron-detail-copy">
          <span className="zyron-overline">ZYRON ORIGINAL DISCOVERY</span>
          <h1>{item.name} <span>{item.year || ""}</span></h1>
          <div className="zyron-detail-meta">
            {score > 0 ? <span className="zyron-score">★ {score.toFixed(1)} <small>TMDB</small></span> : null}
            {item.voteCount > 0 ? <span>{Number(item.voteCount).toLocaleString()} ratings</span> : null}
            {item.runtime ? <span>{item.runtime} min</span> : null}
            {item.status ? <span>{item.status}</span> : null}
            <span>{isSeries ? `${item.seasons.length} seasons` : "Movie"}</span>
          </div>
          {item.tags?.length ? <div className="zyron-genres">{item.tags.filter((t) => !/^\d+ min$/.test(t) && !/season/.test(t)).slice(0, 4).map((tag) => <span key={tag}>{tag}</span>)}</div> : null}
          {item.tagline ? <p className="zyron-detail-tagline">{item.tagline}</p> : null}
          {item.overview ? <p className="zyron-detail-overview">{item.overview}</p> : null}
          <div className="zyron-detail-links">
            <a href={isSeries ? "#seasons-area" : "#download-area"} className="zyron-watch-button"><span>▶</span> {isSeries ? "Explore seasons" : "Find downloads"}</a>
            <a href="/" className="zyron-detail-home">← Back to browse</a>
          </div>
        </div>
      </div>
      {item.cast?.length ? (
        <div className="zyron-cast-section">
          <div className="zyron-rail-heading"><div><h2>Cast & characters</h2><p>Meet the people behind the story</p></div></div>
          <div className="zyron-cast-rail">
            {item.cast.slice(0, 10).map((person) => (
              <div className="zyron-cast-card" key={person.id || person.name}>
                {person.photo ? <img src={person.photo} alt={person.name} loading="lazy" /> : <span className="zyron-cast-avatar">{person.name?.slice(0,1)}</span>}
                <b>{person.name}</b><small>{person.character || "Cast"}</small>
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </section>
  );
}

function FilterSelect({ label, value, options, onChange }) {
  if (options.length < 2) return null;
  return (
    <select className="dl-filter-select" value={value} onChange={(e) => onChange(e.target.value)}>
      <option value="">{label}</option>
      {options.map((t) => (
        <option key={t} value={t}>
          {displayTag(t)}
        </option>
      ))}
    </select>
  );
}

function Links({ results, expect }) {
  const rows = sortDownloadResults(results);
  const groups = groupDownloadLinks(rows);
  const [provider, setProvider] = useState("");
  const [quality, setQuality] = useState("");
  const [method, setMethod] = useState("");
  const [selected, setSelected] = useState([]);
  if (!groups.length) return null;

  const allTags = [];
  const seen = new Set();
  for (const g of groups) {
    for (const t of [g.site, ...g.tags]) {
      if (!t || seen.has(t) || isSizeTag(t)) continue;
      seen.add(t);
      allTags.push(t);
    }
  }
  const filterOrg = organizeTags(allTags);
  const showFilters =
    filterOrg.providers.length > 1 ||
    filterOrg.qualities.length > 1 ||
    filterOrg.methods.length > 1 ||
    filterOrg.tags.length > 0;

  const filtered = groups.filter((g) => {
    const tags = new Set([g.site, ...g.tags]);
    if (provider && !tags.has(provider)) return false;
    if (quality && !tags.has(quality)) return false;
    if (method && !tags.has(method)) return false;
    return selected.every((t) => tags.has(t));
  });

  const list = sortDownloadGroups(filtered);

  function isOn(t) {
    if (isProvider(t)) return provider === t;
    if (isQuality(t)) return quality === t;
    if (isMethod(t)) return method === t;
    return selected.includes(t);
  }

  function toggle(tag) {
    if (isProvider(tag)) {
      setProvider((cur) => (cur === tag ? "" : tag));
      return;
    }
    if (isQuality(tag)) {
      setQuality((cur) => (cur === tag ? "" : tag));
      return;
    }
    if (isMethod(tag)) {
      setMethod((cur) => (cur === tag ? "" : tag));
      return;
    }
    setSelected((cur) => (cur.includes(tag) ? cur.filter((t) => t !== tag) : [...cur, tag]));
  }

  function boxTags(org) {
    return [...org.providers, ...org.qualities, ...org.methods, ...org.tags, ...org.sizes];
  }

  function renderList(list) {
    if (!list.length) return null;
    return (
      <ul className="dl-links">
        {list.map((g) => {
          const org = organizeTags([g.site, ...g.tags]);
          const tags = boxTags(org);
          const warn = possibleWrongFile(g, expect);
          const primary = g.hosters[0]?.url;
          const urls = (g.hosters || []).map((h) => h.url);
          const tg = urls.some(isTelegramLink);
          const ads = urls.some((u) => u && !isTelegramLink(u) && !isDirectLink(u) && !isSemiDirectLink(u));
          const semi = !ads && !tg && urls.some(isSemiDirectLink);
          const direct = !ads && !tg && !semi && urls.some(isDirectLink);
          const hasTags = tags.length > 0 || warn || direct || semi || ads || tg;
          const hasHosters = g.hosters.length > 1;
          return (
            <li key={`${g.site}-${g.name}-${g.hosters.map((h) => h.url).join("|")}`}>
              <div className="dl-box">
                <SiteName name={g.name} href={primary} />
                {hasTags || hasHosters ? (
                  <div className="dl-meta-row">
                    {hasTags ? (
                      <span className="dl-tags">
                        {direct ? <span className="dl-tag direct">Direct</span> : null}
                        {semi ? <span className="dl-tag semi">Semi-direct</span> : null}
                        {tg ? <span className="dl-tag telegram">Telegram</span> : null}
                        {ads ? <span className="dl-tag ads">Ads</span> : null}
                        {warn ? (
                          <span className="dl-tag warn" title="name/url looks like a different show, season, or episode">
                            Possible wrong file
                          </span>
                        ) : null}
                        {tags.map((t) =>
                          isSizeTag(t) ? (
                            <span key={t} className="dl-tag">
                              {displayTag(t)}
                            </span>
                          ) : (
                            <button
                              key={t}
                              type="button"
                              className={`dl-tag dl-filter${isOn(t) ? " on" : ""}`}
                              onClick={() => toggle(t)}
                            >
                              {displayTag(t)}
                            </button>
                          ),
                        )}
                      </span>
                    ) : null}
                    {hasHosters ? (
                      <span className="dl-hosters">
                        {g.hosters.map((h) => (
                          <a key={h.url} href={h.url} target="_blank" rel="noreferrer" className="dl-hoster">
                            {h.label}
                          </a>
                        ))}
                      </span>
                    ) : null}
                  </div>
                ) : null}
              </div>
            </li>
          );
        })}
      </ul>
    );
  }

  return (
    <div className="dl-results">
      {showFilters ? (
        <div className="dl-filters">
          <FilterSelect label="provider" value={provider} options={filterOrg.providers} onChange={setProvider} />
          <FilterSelect label="quality" value={quality} options={filterOrg.qualities} onChange={setQuality} />
          <FilterSelect label="method" value={method} options={filterOrg.methods} onChange={setMethod} />
          {filterOrg.tags.map((t) => (
            <button
              key={t}
              type="button"
              className={`dl-tag dl-filter${isOn(t) ? " on" : ""}`}
              onClick={() => toggle(t)}
            >
              {displayTag(t)}
            </button>
          ))}
        </div>
      ) : null}
      {!filtered.length ? (
        <p className="status">no downloads match those tags.</p>
      ) : (
        renderList(list)
      )}
    </div>
  );
}

export function ResultFold({ results, status, expect }) {
  const n = results?.length || 0;
  if (!n && status?.phase === "done") return <p className="status">{status.msg || "no links found."}</p>;
  if (!n) return null;
  return <Links results={results} expect={expect} />;
}

function fillDurationMs() {
  return 3000 + Math.floor(Math.random() * 2001);
}

function statusKey(st) {
  if (!st) return "";
  return `${st.phase}:${st.site || ""}:${st.done || 0}:${st.total || ""}`;
}

export function DlControl({ label, status, onClick, locked }) {
  const capped = useHuntCap();
  const running = !!(status && status.phase !== "done");
  const key = statusKey(status);
  const [pct, setPct] = useState(0);

  useEffect(() => {
    if (!running) {
      setPct(0);
      return;
    }
    setPct(0);
    const totalMs = fillDurationMs();
    const t0 = performance.now();
    let timer = 0;
    const tick = () => {
      const elapsed = performance.now() - t0;
      if (elapsed >= totalMs) {
        setPct(100);
        return;
      }
      // sharp random jumps toward the linear target, never above it much
      const target = (elapsed / totalMs) * 100;
      const jump = 4 + Math.random() * 18;
      setPct((p) => Math.min(100, Math.max(p, Math.min(target + jump * 0.15, p + jump))));
      timer = window.setTimeout(tick, 80 + Math.random() * 220);
    };
    timer = window.setTimeout(tick, 60 + Math.random() * 120);
    return () => clearTimeout(timer);
  }, [running, key]);

  return (
    <button
      type="button"
      className={`dl-btn${running ? " dl-btn-run" : ""}`}
      disabled={running || locked || capped}
      onClick={onClick}
    >
      {running ? <span className="dl-btn-fill" style={{ width: `${pct}%` }} /> : null}
      <span className="dl-btn-label">{status ? statusLabel(status) : label}</span>
    </button>
  );
}

export function SiteShell({ children }) {
  return (
    <div id="wrap" className="zyron-app zyron-detail-page">
      <header id="header" className="zyron-topbar">
        <a className="zyron-wordmark" href="/" aria-label="ZYRON home">ZYRON<span>+</span></a>
        <nav className="zyron-main-nav" aria-label="Main navigation">
          <a href="/">Home</a><a href="/#movies">Movies</a><a href="/#series">Series</a><a href="/#anime">Anime</a>
        </nav>
        <a className="zyron-search-shortcut" href="/#search-box" aria-label="Search">⌕</a>
      </header>
      {TURNSTILE_SITEKEY && <TurnstileHost />}
      {children}
      <footer className="zyron-footer"><a className="zyron-wordmark" href="/">ZYRON<span>+</span></a><p>Stories worth staying up for.</p><small>Discover • Explore • Enjoy</small></footer>
      <nav className="zyron-bottom-nav" aria-label="Bottom navigation">
        <a href="/"><span>⌂</span><small>Home</small></a>
        <a href="/#search-box"><span>⌕</span><small>Search</small></a>
        <a href="/#movies"><span>▣</span><small>Movies</small></a>
        <a href="/#series"><span>▤</span><small>Series</small></a>
      </nav>
    </div>
  );
}

function isTmdbAnime(item) {
  if (item?.mal_id != null) return true;
  const tags = (item?.tags || []).map((t) => String(t).toLowerCase());
  const ja =
    item?.original_language === "ja" ||
    (item?.origin_country || []).includes("JP") ||
    tags.includes("japanese");
  return ja && tags.some((t) => t === "animation");
}

export function huntIds(item) {
  if (item?.mal_id != null) {
    return { tmdb_id: null, mal_id: item.mal_id, imdb_id: item.imdb_id || null };
  }
  const out = { tmdb_id: item.id, imdb_id: item.imdb_id || null };
  if (isTmdbAnime(item)) out.anime = true;
  return out;
}

export async function runDownloadStream(body, { setStatus, setResults, signal }) {
  setResults([]);
  setStatus({ phase: "start", done: 0, total: "?" });
  const acc = [];
  let sawDone = false;
  try {
    await streamDownloads(body, {
      signal,
      onEvent(ev) {
        if (signal?.aborted) return;
        if (ev.t === "queue") setStatus({ phase: "queue", n: ev.n });
        else if (ev.t === "start") setStatus({ phase: "run", done: 0, total: ev.total });
        else if (ev.t === "check" || ev.t === "miss" || ev.t === "status") {
          setStatus({ phase: "run", site: ev.site, done: ev.done, total: ev.total });
        } else if (ev.t === "hit") {
          acc.push({ site: ev.site, links: ev.links });
          setResults([...acc]);
          setStatus({ phase: "run", site: ev.site, done: ev.done, total: ev.total, found: acc.length });
        } else if (ev.t === "done") {
          sawDone = true;
          setStatus({ phase: "done", found: acc.length, total: ev.total });
        } else if (ev.t === "busy") {
          sawDone = true;
          setStatus({ phase: "done", msg: "busy - try again" });
        } else if (ev.t === "error") {
          sawDone = true;
          setStatus({ phase: "done", msg: ev.msg, found: acc.length });
        }
      },
    });
    if (!signal?.aborted && !sawDone) setStatus({ phase: "done", found: acc.length });
  } catch (e) {
    if (e?.name === "AbortError" || signal?.aborted) return;
    setStatus({ phase: "done", msg: String(e.message || e), found: acc.length });
  }
}
