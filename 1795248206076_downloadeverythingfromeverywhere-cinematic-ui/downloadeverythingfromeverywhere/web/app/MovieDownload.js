"use client";

import { useEffect, useRef, useState } from "react";
import { DlControl, MediaHero, ResultFold, SiteShell, huntIds, runDownloadStream, gateHunt } from "./dl.js";
import { loadMovie } from "../lib/tmdb-client.js";

export default function MovieDownload({ id, initial = null, error: initialError = null, load = loadMovie }) {
  const [movie, setMovie] = useState(initial);
  const [results, setResults] = useState([]);
  const [status, setStatus] = useState(null);
  const [err, setErr] = useState(initialError);
  const runId = useRef(0);
  const job = useRef(null);

  useEffect(() => {
    const my = ++runId.current;
    const ac = new AbortController();
    job.current?.abort();
    job.current = null;
    setResults([]);
    setStatus(null);

    (async () => {
      try {
        let data = initial && String(initial.id) === String(id) ? initial : null;
        if (!data) {
          setMovie(null);
          setErr(null);
          data = await load(id);
        } else {
          setMovie(data);
          setErr(initialError);
        }
        if (ac.signal.aborted || my !== runId.current) return;
        setMovie(data);
      } catch (e) {
        if (!ac.signal.aborted && my === runId.current) setErr(String(e.message || e));
      }
    })();
    return () => {
      ac.abort();
      job.current?.abort();
      job.current = null;
    };
  }, [id, initial, initialError, load]);

  async function findDownloads() {
    if (!movie || (status && status.phase !== "done")) return;
    const token = await gateHunt();
    if (token === null) return;
    const my = runId.current;
    const ac = new AbortController();
    job.current = ac;
    await runDownloadStream(
      { mode: "movie", title: movie.query || movie.name, year: movie.year, ...huntIds(movie), turnstile: token },
      {
        signal: ac.signal,
        setStatus: (st) => {
          if (!ac.signal.aborted && my === runId.current) setStatus(st);
        },
        setResults: (rows) => {
          if (!ac.signal.aborted && my === runId.current) setResults(rows);
        },
      },
    );
    if (job.current === ac) job.current = null;
  }

  return (
    <SiteShell>
      <MediaHero item={movie} />
      {err && <p className="status">{err}</p>}
      {movie ? (
        <p className="dl-status">
          <DlControl label="find downloads" status={status} onClick={findDownloads} />
        </p>
      ) : null}
      <ResultFold results={results} status={status} />
    </SiteShell>
  );
}
