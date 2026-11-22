"use client";

import { useState } from "react";
import QueueMark from "../QueueMark.js";

const IDLE = "hover an element to see what it is.";
const AVATAR_BACKDROP = "https://image.tmdb.org/t/p/w1280/Antz70VlRI2yU3iwYxyYUknzfz9.jpg";
const BB_BACKDROP = "https://image.tmdb.org/t/p/w1280/ycFcYYnzVc8mWw41neszGPMyKc3.jpg";

function Mark({ tip, setTip, as: Tag = "span", className, children, ...rest }) {
  return (
    <Tag
      className={className}
      onMouseEnter={() => setTip(tip)}
      onMouseLeave={() => setTip(IDLE)}
      {...rest}
    >
      {children}
    </Tag>
  );
}

function MovieDemo({ m }) {
  return (
    <>
      <div className="panel">
        <Mark
          {...m("backdrop")}
          as="img"
          className="backdrop"
          src={AVATAR_BACKDROP}
          alt=""
          width={1280}
          height={720}
        />
        <div className="hero-title-row">
          <Mark {...m("title and year")} as="h2">
            Avatar (2009)
          </Mark>
          <Mark {...m("tagline")} as="p" className="hero-tagline">
            Enter the world of Pandora.
          </Mark>
        </div>
        <Mark {...m("overview")} as="p" className="hero-overview">
          In the 22nd century, a paraplegic Marine is dispatched to the moon Pandora on a unique
          mission, but becomes torn between following orders and protecting an alien civilization.
        </Mark>
        <Mark {...m("title tags")} as="p" className="hero-tags">
          Action • Adventure • Fantasy • Science Fiction • 162 min • English
        </Mark>
      </div>

      <div className="dl-filters">
        <Mark {...m("provider filter")} as="span" className="guide-hit">
          <select className="dl-filter-select" disabled>
            <option>provider</option>
          </select>
        </Mark>
        <Mark {...m("quality filter")} as="span" className="guide-hit">
          <select className="dl-filter-select" disabled>
            <option>quality</option>
          </select>
        </Mark>
        <Mark {...m("method filter")} as="span" className="guide-hit">
          <select className="dl-filter-select" disabled>
            <option>method</option>
          </select>
        </Mark>
        <Mark {...m("tag filter")} as="button" type="button" className="dl-tag dl-filter">
          English
        </Mark>
        <Mark {...m("another tag filter")} as="button" type="button" className="dl-tag dl-filter on">
          x265
        </Mark>
      </div>

      <ul className="dl-links">
        <li>
          <div className="dl-box">
            <Mark {...m("download name")} as="span" className="dl-site">
              Avatar.2009.1080p.BluRay.x265
            </Mark>
            <div className="dl-meta-row">
              <span className="dl-tags">
                <Mark {...m("tag describing the download")} as="button" type="button" className="dl-tag dl-filter">
                  hindz
                </Mark>
                <Mark {...m("another tag")} as="button" type="button" className="dl-tag dl-filter">
                  1080p
                </Mark>
                <Mark {...m("another tag")} as="button" type="button" className="dl-tag dl-filter">
                  BluRay
                </Mark>
              </span>
              <span className="dl-hosters">
                <Mark
                  {...m("a link to download this file")}
                  as="a"
                  className="dl-hoster"
                  href="#guide"
                  onClick={(e) => e.preventDefault()}
                >
                  Gdrive
                </Mark>
                <Mark
                  {...m("another link")}
                  as="a"
                  className="dl-hoster"
                  href="#guide"
                  onClick={(e) => e.preventDefault()}
                >
                  Filepress
                </Mark>
              </span>
            </div>
          </div>
        </li>
      </ul>
    </>
  );
}

function TvDemo({ m }) {
  return (
    <>
      <div className="panel">
        <Mark
          {...m("backdrop")}
          as="img"
          className="backdrop"
          src={BB_BACKDROP}
          alt=""
          width={1280}
          height={720}
        />
        <div className="hero-title-row">
          <Mark {...m("title and year")} as="h2">
            Breaking Bad (2008)
          </Mark>
          <Mark {...m("tagline")} as="p" className="hero-tagline">
            Change the equation.
          </Mark>
        </div>
        <Mark {...m("overview")} as="p" className="hero-overview">
          Walter White, a New Mexico chemistry teacher, is diagnosed with Stage III cancer and given
          a prognosis of only two years left to live. He becomes filled with a sense of fearlessness
          and an unrelenting desire to secure his family's financial future at any cost as he enters
          the dangerous world of drugs and crime.
        </Mark>
        <Mark {...m("title tags")} as="p" className="hero-tags">
          Crime • Drama • Thriller • 5 seasons • English
        </Mark>
      </div>

      <section className="dl-season panel">
        <div className="dl-season-head">
          <Mark {...m("season")} as="h3">
            season 1
          </Mark>
          <span className="dl-ep-actions">
            <Mark {...m("download season")} as="span" className="guide-hit">
              <button type="button" className="dl-btn" disabled>
                done - 3 sites
              </button>
            </Mark>
            <Mark {...m("collapse / expand results")} as="button" type="button" className="dl-caret">
              v
            </Mark>
          </span>
        </div>
        <ul className="dl-links">
          <li>
            <div className="dl-box">
              <Mark {...m("download name")} as="span" className="dl-site">
                Breaking.Bad.S01.COMPLETE.1080p
              </Mark>
              <div className="dl-meta-row">
                <span className="dl-tags">
                  <Mark {...m("tag describing the download")} as="button" type="button" className="dl-tag dl-filter">
                    1080p
                  </Mark>
                </span>
                <span className="dl-hosters">
                  <Mark
                    {...m("a link to download this file")}
                    as="a"
                    className="dl-hoster"
                    href="#guide"
                    onClick={(e) => e.preventDefault()}
                  >
                    Pixeldrain
                  </Mark>
                </span>
              </div>
            </div>
          </li>
        </ul>
      </section>

      <ul className="dl-eps">
        <li>
          <div className="dl-ep-row">
            <Mark {...m("episode")} as="span" className="ep-title">
              E01 Pilot
            </Mark>
            <span className="dl-ep-actions">
              <Mark {...m("download episode")} as="span" className="guide-hit">
                <button type="button" className="dl-btn" disabled>
                  checking pahe... (2/8)
                </button>
              </Mark>
              <Mark {...m("collapse / expand results")} as="button" type="button" className="dl-caret">
                v
              </Mark>
            </span>
          </div>
          <ul className="dl-links">
            <li>
              <div className="dl-box">
                <Mark {...m("download name")} as="span" className="dl-site">
                  Breaking.Bad.S01E01.1080p.WEB-DL
                </Mark>
                <div className="dl-meta-row">
                  <span className="dl-tags">
                    <Mark {...m("tag describing the download")} as="button" type="button" className="dl-tag dl-filter">
                      WEB-DL
                    </Mark>
                    <Mark {...m("another tag")} as="button" type="button" className="dl-tag dl-filter">
                      1080p
                    </Mark>
                  </span>
                  <span className="dl-hosters">
                    <Mark
                      {...m("a link to download this file")}
                      as="a"
                      className="dl-hoster"
                      href="#guide"
                      onClick={(e) => e.preventDefault()}
                    >
                      Mega
                    </Mark>
                    <Mark
                      {...m("another link")}
                      as="a"
                      className="dl-hoster"
                      href="#guide"
                      onClick={(e) => e.preventDefault()}
                    >
                      Gdrive
                    </Mark>
                  </span>
                </div>
              </div>
            </li>
          </ul>
        </li>
      </ul>
    </>
  );
}

export default function GuidePage() {
  const [tip, setTip] = useState(IDLE);
  const [kind, setKind] = useState("movie");
  const m = (t) => ({ tip: t, setTip });

  return (
    <div id="wrap" className="guide-page">
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

      <div className="guide-tabs">
        <button type="button" className={kind === "movie" ? "on" : ""} onClick={() => setKind("movie")}>
          movie
        </button>
        <button type="button" className={kind === "tv" ? "on" : ""} onClick={() => setKind("tv")}>
          tv
        </button>
      </div>

      {kind === "movie" ? <MovieDemo m={m} /> : <TvDemo m={m} />}

      <div className="guide-tip" aria-live="polite">
        {tip}
      </div>
    </div>
  );
}
