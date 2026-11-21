// Lower = better: direct files, reliable scrape, few/no ads.
export const SITE_RANK = {
  phonofilm: 10,
  "111477": 11,
  moviebox: 12,
  hindmoviez: 14,
  nkiri: 16,
  "4khdhub": 18,
  moviesdrive: 19,
  filmgo: 20,
  filmvault: 21,
  cinefy: 22,
  hdmoviez: 24,
  tvsboy: 26,
  vadapav: 28,
  todaytvseries: 34,
  fzmovies: 36,
  katmoviehd: 38,
  uhdmovies: 40,
  tattooin: 42,
  rapidmoviez: 44,
  subsl: 46,
  moviesmod: 48,
  hdmovieshub: 50,
  lightdl: 52,
  pahe: 54,
  animeout: 60,
  anime7: 62,
  animetosho: 70,
  kayoanime: 72,
  kusonime: 74,
  animerss: 76,
  animesalt: 78,
  tsukihime: 84,
  mynimeku: 86,
  rlsxtvt: 200,
  multishows: 210,
};

/** Short display names for provider tags. */
const SITE_LABEL = {
  "111477": "one",
  "4khdhub": "4khub",
  moviesdrive: "mdrive",
  filmgo: "figo",
  fzmovies: "fzie",
  hdmoviez: "hdmz",
  hdmovieshub: "hdhub",
  katmoviehd: "kat",
  lightdl: "light",
  moviebox: "mbox",
  nkiri: "nkiri",
  rapidmoviez: "rmz",
  rlsxtvt: "rlsx",
  subsl: "subsl",
  todaytvseries: "ttv",
  tvsboy: "tboy",
  kayoanime: "kayo",
  kusonime: "kuso",
  tsukihime: "tsuki",
  animesalt: "salt",
  animerss: "arss",
  anime7: "a7",
  animeout: "aout",
  mynimeku: "myni",
  pahe: "pahe",
  uhdmovies: "uhdm",
  tattooin: "tat",
  animetosho: "tosho",
  phonofilm: "phono",
  cinefy: "cfy",
  filmvault: "fvault",
  vadapav: "vada",
  hindmoviez: "hind",
  moviesmod: "mod",
  multishows: "multi",
};

export function siteLabel(name) {
  return SITE_LABEL[name] || name;
}

const DIRECT_RE =
  /(r2\.dev|workers\.dev|foxcloud\.rest|neetflixcdn|drive\.google\.com\/uc|video-downloads\.googleusercontent|vikingfile\.com\/download|download\d*\.mediafire|111477|sermoviedown|highxhd|archive\.org|uupload\.ir|hakunaymatata\.com|vadapav\.mov|tattooin\.ru|public\.animeout|nimbus\.animeout|mydriveku|dl\.anime7\.download|\.mkv($|\?)|\.mp4($|\?)|\.rar($|\?))/i;

const SEMI_RE =
  /(mega\.nz|gofile\.io|pixeldrain|hubcloud|hubdrive|gdflix|firefiles|clicknupload|fileditch|mediafire\.com|vikingfile\.com|krakenfiles|buzzheavier|drive\.google\.com)/i;

function siteRank(name) {
  return SITE_RANK[name] ?? 500;
}

function asUrl(item) {
  return typeof item === "string" ? item : item?.url || "";
}

export function isDirectLink(item) {
  const url = asUrl(item);
  if (/hubcloud|hubdrive|pixeldrain/i.test(url)) return false;
  return DIRECT_RE.test(url);
}

export function isTelegramLink(item) {
  return /(?:t\.me|telegram\.(?:me|dog))\//i.test(asUrl(item));
}

/** File-host page: download button, no ad wall. Mega, Gofile, HubCloud, HubDrive, Pixeldrain, Mediafire, Drive. */
export function isSemiDirectLink(item) {
  const url = asUrl(item);
  if (!url || isDirectLink(url) || isTelegramLink(url)) return false;
  return SEMI_RE.test(url);
}

/** 0 direct, 1 semi-direct, 2 telegram, 3 ads. */
function kindRank(item) {
  if (isDirectLink(item)) return 0;
  if (isSemiDirectLink(item)) return 1;
  if (isTelegramLink(item)) return 2;
  return 3;
}

function worstKind(items) {
  let w = 0;
  for (const it of items || []) {
    const k = kindRank(it);
    if (k > w) w = k;
  }
  return w;
}

export function sortDownloadResults(results) {
  return [...(results || [])]
    .map((r) => ({
      ...r,
      links: [...(r.links || [])].sort(
        (a, b) => kindRank(a) - kindRank(b) || asUrl(a).localeCompare(asUrl(b)),
      ),
    }))
    .sort(
      (a, b) =>
        worstKind(a.links) - worstKind(b.links) ||
        siteRank(a.site) - siteRank(b.site) ||
        a.site.localeCompare(b.site),
    );
}

function qualityRank(g) {
  const blob = `${g.name || ""} ${(g.tags || []).join(" ")}`;
  let best = 0;
  if (/\b(4k|uhd)\b/i.test(blob)) best = 2160;
  for (const m of blob.matchAll(/\b(\d{3,4})p+\b/gi)) {
    const n = +m[1];
    if (n > best) best = n;
  }
  for (const m of blob.matchAll(/\b\d{3,4}\s*[x×]\s*(2160|1080|720|540|480|400|360)\b/gi)) {
    const n = +m[1];
    if (n > best) best = n;
  }
  return best ? -best : 1;
}

export function sortDownloadGroups(groups) {
  return [...(groups || [])]
    .map((g) => ({
      ...g,
      hosters: [...(g.hosters || [])].sort(
        (a, b) => kindRank(a) - kindRank(b) || asUrl(a).localeCompare(asUrl(b)),
      ),
    }))
    .sort(
      (a, b) =>
        worstKind(a.hosters) - worstKind(b.hosters) ||
        siteRank(a.site) - siteRank(b.site) ||
        qualityRank(a) - qualityRank(b) ||
        a.site.localeCompare(b.site) ||
        (a.name || "").localeCompare(b.name || ""),
    );
}
