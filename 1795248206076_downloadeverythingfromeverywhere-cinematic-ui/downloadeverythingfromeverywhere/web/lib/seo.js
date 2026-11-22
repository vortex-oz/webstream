import { isBlocked } from "./blocked.js";

export const SITE_URL = new URL(process.env.SITE_URL || "http://localhost:3000").origin;
export const SITE_NAME = "ZYRON";
export const HOME_TITLE = "Discover Movies, Series & Anime | ZYRON";
export const SITE_DESC =
  "Free download movies, TV shows & anime in 720p, 1080p & 4K. Direct WEB-DL, BluRay, x265 HEVC, dual audio, small size episodes & season packs from many hosts.";
export const SITE_KEYWORDS = [
  "free movie download",
  "download free movies",
  "free tv shows download",
  "download movies",
  "download tv shows",
  "free anime download",
  "download anime",
  "direct download",
  "direct download links",
  "ddl",
  "single link",
  "google drive download",
  "1080p",
  "720p",
  "480p",
  "4K",
  "x264",
  "x265",
  "HEVC",
  "10bit",
  "WEB-DL",
  "WEBRip",
  "BluRay",
  "BRRip",
  "HDTV",
  "mkv",
  "mp4",
  "dual audio",
  "hindi dubbed",
  "english subtitles",
  "small size",
  "300mb movies",
  "latest movies",
  "latest episodes",
  "full movie download",
  "episode download",
  "season pack",
  "complete season",
  "hollywood movies download",
  "bollywood movies download",
];

export function absUrl(path = "/") {
  if (!path || path === "/") return SITE_URL;
  const href = new URL(path, SITE_URL + "/").href;
  return href.endsWith("/") ? href.slice(0, -1) : href;
}

export const OG_IMAGE = {
  url: absUrl("/wide.png"),
  width: 2560,
  height: 540,
  alt: HOME_TITLE,
  type: "image/png",
};

function clip(s, n) {
  const t = String(s || "").replace(/\s+/g, " ").trim();
  if (t.length <= n) return t;
  return t.slice(0, n - 1).replace(/\s+\S*$/, "") + "…";
}

function namedTitle(item) {
  return item.year ? `${item.name} (${item.year})` : item.name;
}

function kindLabel(kind) {
  if (kind === "movie") return "movie";
  if (kind === "anime") return "anime";
  return "TV series";
}

function genreTags(tags) {
  return (tags || []).filter((t) => !/^\d| min$|seasons?$|episodes?$/i.test(t));
}

export function socialMeta({ title, description, path, type = "website", keywords, images }) {
  const url = absUrl(path);
  const titleText =
    typeof title === "string" ? title : title?.absolute || title?.default || SITE_NAME;
  const imgs = images?.length ? images : [OG_IMAGE];
  return {
    title,
    description,
    ...(keywords?.length ? { keywords } : {}),
    alternates: { canonical: url },
    openGraph: {
      title: titleText,
      description,
      url,
      siteName: SITE_NAME,
      locale: "en_US",
      type,
      images: imgs,
    },
    twitter: {
      card: "summary_large_image",
      title: titleText,
      description,
      images: imgs,
    },
  };
}

export function websiteJsonLd() {
  return {
    "@context": "https://schema.org",
    "@type": "WebSite",
    name: SITE_NAME,
    url: SITE_URL,
    description: SITE_DESC,
    inLanguage: "en",
    publisher: {
      "@type": "Organization",
      name: SITE_NAME,
      url: SITE_URL,
      logo: absUrl("/favicon.png"),
    },
    potentialAction: {
      "@type": "SearchAction",
      target: {
        "@type": "EntryPoint",
        urlTemplate: `${SITE_URL}/?q={search_term_string}`,
      },
      "query-input": "required name=search_term_string",
    },
  };
}

export function itemListJsonLd(items) {
  const rows = items.filter((r) => {
    const kind = r.media_type === "movie" ? "m" : r.media_type === "anime" ? "a" : "s";
    return !isBlocked(kind, r.id);
  });
  return {
    "@context": "https://schema.org",
    "@type": "ItemList",
    name: "Trending free movie and TV downloads",
    numberOfItems: rows.length,
    itemListElement: rows.map((r, i) => ({
      "@type": "ListItem",
      position: i + 1,
      url: absUrl(
        r.media_type === "movie" ? `/m/${r.id}` : r.media_type === "anime" ? `/a/${r.id}` : `/s/${r.id}`,
      ),
      name: r.year ? `${r.name} (${r.year})` : r.name,
      image: r.poster || undefined,
    })),
  };
}

function mediaJsonLd(type, item, path) {
  const url = absUrl(path);
  const name = namedTitle(item);
  const genres = genreTags(item.tags);
  const sameAs = [
    item.imdb_id ? `https://www.imdb.com/title/${item.imdb_id}` : null,
    item.mal_id ? `https://myanimelist.net/anime/${item.mal_id}` : null,
  ].filter(Boolean);
  return {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": type,
        name: item.name,
        alternateName: name,
        url,
        description: item.overview || undefined,
        image: item.backdrop || undefined,
        datePublished: item.year || undefined,
        genre: genres.length ? genres : undefined,
        sameAs: sameAs.length === 1 ? sameAs[0] : sameAs.length ? sameAs : undefined,
      },
      {
        "@type": "BreadcrumbList",
        itemListElement: [
          { "@type": "ListItem", position: 1, name: SITE_NAME, item: SITE_URL },
          { "@type": "ListItem", position: 2, name, item: url },
        ],
      },
    ],
  };
}

export function movieJsonLd(item) {
  return mediaJsonLd("Movie", item, `/m/${item.id}`);
}

export function tvJsonLd(item) {
  return mediaJsonLd("TVSeries", item, `/s/${item.id}`);
}

export function animeJsonLd(item) {
  return mediaJsonLd(item.kind === "movie" ? "Movie" : "TVSeries", item, `/a/${item.id}`);
}

export function mediaSocialMeta(item, kind, path) {
  const named = namedTitle(item);
  const label = kindLabel(kind);
  const isSeries = kind !== "movie" && item.kind !== "movie";
  const title = `${named} Free Download`;
  const lead = `Free download ${named} ${label} in 480p, 720p, 1080p & 4K WEB-DL/BluRay x265 10bit, direct links, small size.`;
  const description = item.overview ? clip(`${lead} ${item.overview}`, 160) : clip(lead, 160);
  const keywords = [
    `${item.name} free download`,
    `download ${item.name}`,
    named,
    `${named} download`,
    `free ${label} download`,
    "1080p",
    "720p",
    "480p",
    "4K",
    "x265",
    "HEVC",
    "10bit",
    "WEB-DL",
    "BluRay",
    "WEBRip",
    "mkv",
    "mp4",
    "dual audio",
    "small size",
    "direct download",
    "single link",
    ...(isSeries
      ? ["episode download", "season pack", "complete series"]
      : ["full movie download"]),
    ...genreTags(item.tags),
  ];
  const images = item.backdrop ? [{ url: item.backdrop, alt: title }] : [OG_IMAGE];
  const ogType =
    kind === "movie" || (kind === "anime" && item.kind === "movie") ? "video.movie" : "video.tv_show";
  return socialMeta({ title, description, path, type: ogType, keywords, images });
}
