/** Quality / source / codec / audio / content-type tags from labels & URLs. No host names. */

const RULES = [
  [/\b(2160p+|4k|uhd)\b|\b\d{3,4}\s*[x×]\s*2160\b/i, "2160p"],
  [/\b1080p+\b|\b\d{3,4}\s*[x×]\s*1080\b/i, "1080p"],
  [/\b720p+\b|\b720\s*hc\b|\b720hc\b|\b\d{3,4}\s*[x×]\s*720\b/i, "720p"],
  [/\b540p+\b|\b\d{3,4}\s*[x×]\s*540\b/i, "540p"],
  [/\b480p+\b|\b480\s*hc\b|\b480hc\b|\b\d{3,4}\s*[x×]\s*480\b/i, "480p"],
  [/\b400p+\b|\b\d{3,4}\s*[x×]\s*400\b/i, "400p"],
  [/\b360p+\b|\b\d{3,4}\s*[x×]\s*360\b/i, "360p"],
  [/\bremux\b/i, "REMUX"],
  [/\bbluray|blu[-\s]?ray|bdrip|brrip\b/i, "BluRay"],
  [/\bweb[-\s]?dl\b/i, "WEB-DL"],
  [/\bwebrip\b/i, "WEBRip"],
  [/\bhdtv\b/i, "HDTV"],
  [/\bhdrip\b/i, "HDRip"],
  [/\bdvdrip\b/i, "DVDRip"],
  [/\bhybrid\b/i, "Hybrid"],
  [/\b(x265|h\.?265|hevc)\b/i, "x265"],
  [/\b(x264|h\.?264|avc)\b/i, "x264"],
  [/\bav1\b/i, "AV1"],
  [/\b10\s*-?\s*bit\b/i, "10bit"],
  [/\bhdr10?\+?\b/i, "HDR"],
  [/\bdolby\.?\s*vision|\bdv\b/i, "DV"],
  [/\batmos\b/i, "Atmos"],
  [/\bddp?5\.?1|truehd|dts[-\s]?hd|dts\b/i, "5.1"],
  [/\baac\b/i, "AAC"],
  [/\bdual(?:[_\s-]*audio)?\b/i, "Dual"],
  [/\bmulti(?:[_\s-]*audio)?\b/i, "Multi"],
  [/\bhindi\b/i, "Hindi"],
  [/\benglish\b/i, "English"],
  [/\bindonesian\b|\bsubtitle\s+indonesia\b|\bsub(?:title)?\s*indo(?:nesia)?\b/i, "Indonesian"],
  [/\btamil\b/i, "Tamil"],
  [/\btelugu\b/i, "Telugu"],
  [/\besub|e-?subs?\b/i, "Subs"],
  [/\bbatch\b|\bseason[_\s-]?pack\b|\bcomplete[_\s-]?(?:season|series|s\d)/i, "Pack"],
  [/\bper[_\s-]?episode\b|\bepisode\s*links?\b|\bS\d{1,2}E\d{1,2}\b|\b\d+x\d{2}\b/i, "Episode"],
  [/\b(\d+(?:[.,]\d+)?)\s*(KB|MB|GB|TB|KiB|MiB|GiB|TiB)\b/gi, null],
];

const QUALITY = new Set(["2160p", "1080p", "720p", "540p", "480p", "400p", "360p"]);

function decodeBlob(s) {
  let t = String(s || "");
  try {
    t = decodeURIComponent(t);
  } catch {}
  return t.replace(/[+_]/g, " ");
}

function tagsFromLabel(...parts) {
  const blob = decodeBlob(parts.filter(Boolean).join(" "));
  if (!blob.trim()) return [];
  const tags = [];
  const seen = new Set();
  const quals = [];
  for (const [re, tag] of RULES) {
    if (tag == null) {
      re.lastIndex = 0;
      for (const m of blob.matchAll(re)) {
        let num = m[1].replace(",", ".");
        if (num.includes(".")) num = num.replace(/0+$/, "").replace(/\.$/, "");
        const t = num + m[2].toUpperCase().replace("IB", "B");
        if (!seen.has(t)) {
          seen.add(t);
          tags.push(t);
        }
      }
      continue;
    }
    if (!re.test(blob) || seen.has(tag)) continue;
    seen.add(tag);
    if (QUALITY.has(tag)) quals.push(tag);
    else tags.push(tag);
  }
  // One blob with many resolutions is usually a post title listing all options — ignore them.
  if (quals.length === 1) tags.unshift(quals[0]);
  return tags;
}

function tagsFromUrl(url) {
  return tagsFromLabel(url);
}

function mergeTags(...lists) {
  const out = [];
  const seen = new Set();
  for (const list of lists) {
    for (const t of list || []) {
      if (!t || seen.has(t)) continue;
      seen.add(t);
      out.push(t);
    }
  }
  return out;
}

const HOST_LABEL =
  /^(?:[\p{Extended_Pictographic}\p{Emoji_Presentation}\uFE0F\u200D\s]*)*(?:v-?cloud|filepress|filebee|g-?drive|g-?direct|google\s*drive|pixel\s*drain|pixeldrain|hubcloud|hubdrive|gdflix|gdlink|gofile|mega(?:up)?|workers?|fastdl|zippyshare|mediafire|1fichier|krakenfiles|buzzheavier|streamtape|vikingfile|nexdrive|multicloud|instant(?:\s*dl)?|fast\s*server|server\s*\d+)\b/iu;

function stripEmoji(s) {
  return String(s || "")
    .replace(/[\p{Extended_Pictographic}\p{Emoji_Presentation}\uFE0F\u200D]/gu, "")
    .replace(/\s+/g, " ")
    .trim();
}

function isHostLabel(s) {
  const t = stripEmoji(cleanName(s) || s).replace(/\s+/g, " ").trim();
  if (!t) return true;
  if (HOST_LABEL.test(t)) return true;
  // "V-Cloud [Resumable]", "Filepress [G-Drive]"
  if (/^\S{1,24}\s*\[[^\]]{1,24}\]\s*$/.test(t) && /\b(cloud|press|drive|drain|flix|hub|server|bee|direct|link)\b/i.test(t))
    return true;
  if (t.length <= 28 && /\[(?:g-?drive|resumable|fast|server\s*\d+|mirror\s*\d+)\]/i.test(t)) return true;
  return false;
}

function nameFromUrl(url) {
  try {
    const u = new URL(url);
    const candidates = [];
    let base = decodeURIComponent(u.pathname).split("/").filter(Boolean).pop() || "";
    base = base.replace(/\+/g, " ").trim();
    if (base) candidates.push(base);
    for (const key of ["id", "name", "file", "filename", "title", "fn", "n"]) {
      const v = u.searchParams.get(key);
      if (!v) continue;
      try {
        candidates.push(decodeURIComponent(v).replace(/\+/g, " ").trim());
      } catch {
        candidates.push(v.replace(/\+/g, " ").trim());
      }
    }
    // Prefer release-like filenames (SxxExx / year / extension)
    const ranked = candidates
      .filter((s) => s && !/^(download|dl|file|get|index|embed|watch)$/i.test(s) && !isHostLabel(s))
      .filter((s) => !isOpaqueName(s))
      .sort((a, b) => nameScore(b) - nameScore(a));
    return ranked[0] || "";
  } catch {
    return "";
  }
}

/** True when the "name" is just a hoster id / hash / numeric slug. */
function isOpaqueName(s) {
  const t = String(s || "").trim();
  if (!t) return true;
  if (/^(download|dl|file|link|get|index|cloud|links)$/i.test(t)) return true;
  if (/^\d{5,}$/.test(t)) return true;
  if (/^[a-f0-9]{20,}$/i.test(t)) return true;
  // base64 / token blobs
  if (
    t.length >= 24 &&
    /^[A-Za-z0-9+/=_-]+$/.test(t) &&
    !/\s/.test(t) &&
    !/\d{3,4}p|S\d{1,2}E\d{1,3}|\.(mkv|mp4|zip|rar)$/i.test(t)
  ) {
    return true;
  }
  // drive / mirror ids: no spaces, no extension, no quality/scene markers
  if (
    /^[A-Za-z0-9_-]{3,48}$/.test(t) &&
    !/\./.test(t) &&
    !/\d{3,4}p/i.test(t) &&
    !/\bS\d{1,2}E\d{1,3}\b/i.test(t) &&
    !/\b(19|20)\d{2}\b/.test(t) &&
    !/\s/.test(t)
  ) {
    return true;
  }
  return false;
}

const SIZE_IN_NAME = /[\(\[]\s*\d+(?:[.,]\d+)?\s*(?:KB|MB|GB|TB|KiB|MiB|GiB|TiB)\s*[\)\]]/gi;

function stripSizeFromName(s) {
  SIZE_IN_NAME.lastIndex = 0;
  return String(s || "")
    .replace(SIZE_IN_NAME, " ")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/^[\s\-–—|]+|[\s\-–—|]+$/g, "");
}

function cleanName(s) {
  let t = stripEmoji(String(s || ""))
    .replace(/\s+/g, " ")
    .trim();
  // Already a filename — keep every token (spaces, codec, episode).
  if (/\.(mkv|mp4|avi|iso|m4v|m2ts|ts|zip|rar)(?:\s*\[|$)/i.test(t) && t.length < 400) {
    return stripSizeFromName(t);
  }
  // Age / note prefixes: [18+], (18+), etc.
  t = t.replace(/^(?:\[[^\]]*\]|\([^)]*\))\s*/g, "").trim();
  // Drop every standalone "Download(s)" (CTA fluff, not part of the title)
  t = t.replace(/\bdownloads?\b/gi, " ");
  t = t.replace(/\s+/g, " ").trim();
  // Drop leading leftover CTA words
  for (let i = 0; i < 4; i++) {
    const next = t
      .replace(/^(?:click\s+(?:here\s+)?(?:to\s+)?)/i, "")
      .replace(/^(?:(?:free|full|hd|watch|online|now|link|links|here)\s+)+/i, "")
      .replace(/^[:\-–|]\s*/, "")
      .trim();
    if (next === t) break;
    t = next;
  }
  // Leading site brand: "Waploaded – Title" (space around separator)
  t = t.replace(
    /^[A-Za-z][\w.-]*(?:moviez?|movies?|flix|hub|vault|loaded|rips?|pahe)\b\s+[~\-|–—]\s+/i,
    "",
  );
  // Trailing domain branding (~ HindMovie.cc.com, | UHDMovies.vip)
  t = t.replace(
    /\s+[~\-|–—]\s+[\w][\w.-]*\.(?:com|net|org|cc|in|xyz|info|to|me|app|blog|vip|fun|site|online|pk|ph|ng)(?:\.[\w.-]+)?\s*$/i,
    "",
  );
  // Trailing brand after spaced separator: – KatMovieHD, | MoviesNipiPay
  // (require spaces so scene tags like x264-YIFY / G-Direct stay intact)
  t = t.replace(
    /\s+[~\-|–—]\s+[A-Za-z][\w.-]*(?:moviez?|movies?|moviehd|flix|hub|vault|loaded|rips?|pahe|pay)\b[\w.-]*\s*$/i,
    "",
  );
  t = t.replace(/\s+[~\-|–—]\s+[A-Z][A-Za-z0-9._-]{2,}\s*$/g, "");
  // Trailing glued brand with no separator: ... Dual Audio WorldFree4U
  t = t.replace(
    /\s+(?:WorldFree\d*U|[A-Za-z0-9]*(?:Moviez?|Movies|MovieHD|Flix|Hub|Vault|Loaded|Rips?|Pahe|Pay))\s*$/i,
    "",
  );
  const file = t.match(/([A-Za-z0-9][A-Za-z0-9._()\[\]+'’\s,~&%#@!;–—-]{8,}\.(?:mkv|mp4|avi|iso|zip|rar))/i);
  if (file) t = file[1];
  t = t.replace(/\.html?$/i, "");
  t = t.replace(/\b(?:hubcloud|hubdrive|gdflix|filebee|v-?cloud|nexdrive)\b/gi, " ");
  return stripSizeFromName(t.replace(/\s+/g, " ").trim().replace(/^[\s\-–—|]+|[\s\-–—|]+$/g, ""));
}

function nameScore(s) {
  let score = Math.min(s.length, 80);
  if (/\b(19|20)\d{2}\b/.test(s)) score += 40;
  if (/\bS\d{1,2}E\d{1,3}\b/i.test(s)) score += 40;
  if (/\b(?:season|complete|dual|hindi|english|bluray|web-?dl|webrip)\b/i.test(s)) score += 20;
  if (/\b\d{3,4}p\b/i.test(s)) score += 15;
  if (/\.\w{2,5}$/i.test(s)) score += 25;
  if (isHostLabel(s)) score -= 200;
  if (s.length < 12) score -= 20;
  return score;
}

function linkUrl(item) {
  if (!item) return "";
  if (typeof item === "string") return item;
  return item.url || "";
}

function linkTags(item) {
  if (!item) return [];
  if (typeof item === "string") return tagsFromUrl(item);
  return mergeTags(item.tags, tagsFromLabel(item.name), tagsFromUrl(item.url));
}

function isFileName(s) {
  return !!(
    s &&
    /\.(mkv|mp4|avi|iso|m4v|m2ts|ts|zip|rar)(?:\s*\[|$)/i.test(s) &&
    !isHostLabel(s) &&
    !isOpaqueName(s)
  );
}

function linkName(item) {
  if (!item) return "download";
  if (typeof item === "string") {
    const fromUrl = nameFromUrl(item);
    if (fromUrl && !isOpaqueName(fromUrl)) return fromUrl;
    return hosterLabel(item);
  }
  const fromUrl = nameFromUrl(item.url);
  const n = cleanName(item.name);
  // URL basename wins when it's a fuller filename (API may have sliced to "7.1]-WiKi.mkv")
  if (isFileName(fromUrl) && (!isFileName(n) || fromUrl.length > n.length)) return fromUrl;
  if (n && !isHostLabel(n) && !isOpaqueName(n)) return n;
  if (fromUrl && !isOpaqueName(fromUrl)) return fromUrl;
  // Fall back to hoster + quality tags so boxes aren't cryptic ids
  const host = hosterLabel(item);
  const quals = (item.tags || []).filter((t) => QUALITY.has(t));
  if (quals.length === 1) return `${host} ${quals[0]}`;
  return host;
}

function normRelease(s) {
  return String(s || "")
    .toLowerCase()
    .replace(/\.(mkv|mp4|avi|m4v|ts|m2ts|zip|rar|7z)(\?.*)?$/i, "")
    .replace(/[._+]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

/** Stable id for the same encode/file across mirror hosts. */
function releaseKey(item) {
  if (item && typeof item === "object" && item.release && !isOpaqueName(item.release)) {
    return String(item.release);
  }
  const url = linkUrl(item);
  const fromUrl = nameFromUrl(url);
  const name = typeof item === "object" ? item.name : "";
  const best = [fromUrl, name]
    .filter((s) => s && !isHostLabel(s) && !isOpaqueName(s))
    .sort((a, b) => nameScore(b) - nameScore(a))[0];
  return normRelease(best || url);
}

const HOST_TAG =
  /^(?:v-?cloud|filepress|filebee|g-?drive|g-?direct|google-?drive|pixeldrain|pixel-?drain|hubcloud|hubdrive|gdflix|gdlink|gofile|mega(?:up)?|worker|fastdl|nexdrive|instant-?dl|moviebox)$/i;

function isHosterTag(t) {
  if (!t) return false;
  if (/^\d+(?:[.,]\d+)?\s*(KB|MB|GB|TB|KiB|MiB|GiB|TiB)$/i.test(String(t).trim())) return false;
  return HOST_TAG.test(String(t).replace(/\s+/g, "-")) || isHostLabel(t);
}

/** Friendly hoster label for a resolved URL / tagged item. */
function hosterLabel(item) {
  const tags = linkTags(item);
  for (const t of tags) {
    if (isHosterTag(t)) return String(t).replace(/-/g, " ");
  }
  const url = linkUrl(item);
  try {
    const host = new URL(url).hostname.replace(/^www\./i, "");
    if (/t\.me|telegram\.(?:me|dog)/i.test(host)) return "Telegram";
    if (/googleusercontent|googleapis|drive\.google/i.test(host)) return "G-Drive";
    if (/pixeldrain/i.test(host)) return "Pixeldrain";
    if (/workers\.dev|r2\.dev/i.test(host)) return "Worker";
    if (/hubdrive/i.test(host)) return "HubDrive";
    if (/hubcloud/i.test(host)) return "HubCloud";
    if (/gofile/i.test(host)) return "Gofile";
    if (/mega\./i.test(host)) return "Mega";
    if (/acefile/i.test(host)) return "Acefile";
    if (/hxfile/i.test(host)) return "Hxfile";
    if (/mydriveku/i.test(host)) return "MyNimeku";
    if (/hakunaymatata/i.test(host)) return "MovieBox";
    if (/gdshine|gdflix|gdlink/i.test(host)) return "GDFlix";
    if (/vikingfile/i.test(host)) return "Viking";
    if (/fileditch/i.test(host)) return "FileDitch";
    if (/public\.animeout|nimbus\.animeout/i.test(host)) return "AnimeOut";
    if (/clicknupload|clickndownload/i.test(host)) return "Clicknupload";
    if (/rapidrar/i.test(host)) return "RapidRAR";
    if (/firefiles/i.test(host)) return "Firefiles";
    if (/downloadwella|thenkiri|nkiri/i.test(host)) return "Nkiri";
    if (/xubster/i.test(host)) return "Xubster";
  if (/highxhd/i.test(host)) return "HDMoviez";
  if (/teknoasian/i.test(host)) return "Pahe";
  if (/driveseed|driveleech/i.test(host)) return "DriveSeed";
  if (/cloud\.unblockedgames/i.test(host)) return "UHDMovies";
  if (/cuty\.io|fc-lc/i.test(host)) return "DDLBase";
  if (/renewyep|renewback|uupload/i.test(host)) return "TodayTV";
  if (/dl\.dramasuki/i.test(host)) return "DramaSuki";
  const part = host.split(".")[0];
  return part ? part.charAt(0).toUpperCase() + part.slice(1) : "Link";
  } catch {
    return "Link";
  }
}

function normTitle(s) {
  return String(s || "")
    .toLowerCase()
    .replace(/&/g, " and ")
    .replace(/[^a-z0-9]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

/** Parse season/episode refs from a label blob. Ranges become {season, epFrom, epTo}. */
function parseAirRefs(blob) {
  const s = decodeBlob(blob);
  const out = [];
  const push = (season, episode, epFrom, epTo) => {
    const sn = season != null ? Number(season) : null;
    if (sn != null && (!Number.isFinite(sn) || sn < 0 || sn > 100)) return;
    if (episode != null) {
      const ep = Number(episode);
      if (!Number.isFinite(ep) || ep < 1 || ep > 999) return;
      out.push({ season: sn, episode: ep });
      return;
    }
    if (epFrom != null && epTo != null) {
      const a = Number(epFrom);
      const b = Number(epTo);
      if (!Number.isFinite(a) || !Number.isFinite(b)) return;
      out.push({ season: sn, epFrom: Math.min(a, b), epTo: Math.max(a, b) });
      return;
    }
    if (sn != null) out.push({ season: sn });
  };

  // S01E05-E10 / S01E05-10
  for (const m of s.matchAll(/\bS(\d{1,2})E(\d{1,3})\s*[-–to]+\s*E?(\d{1,3})\b/gi)) {
    push(m[1], null, m[2], m[3]);
  }
  // S01E05
  for (const m of s.matchAll(/\bS(\d{1,2})E(\d{1,3})\b/gi)) {
    push(m[1], m[2]);
  }
  // S01.E05 / S01 E05 / S01-E05
  for (const m of s.matchAll(/\bS(\d{1,2})[.\s_-]+E(\d{1,3})\b/gi)) {
    push(m[1], m[2]);
  }
  // 1x05
  for (const m of s.matchAll(/\b(\d{1,2})x(\d{1,3})\b/gi)) {
    push(m[1], m[2]);
  }
  // Season 3 Episode 5 / Season 3 Ep 5
  for (const m of s.matchAll(/\bSeasons?\s*(\d{1,2})\s*(?:[-–:]\s*)?(?:Episode|Episodes|Ep)\s*(\d{1,3})\b/gi)) {
    push(m[1], m[2]);
  }
  // Episode 1 – 10 (Complete) with season nearby
  for (const m of s.matchAll(/\bSeasons?\s*(\d{1,2})\b[^.\n]{0,40}?\b(?:Episode|Episodes|Ep)\s*(\d{1,3})\s*[-–to]+\s*(\d{1,3})\b/gi)) {
    push(m[1], null, m[2], m[3]);
  }
  // Season 1 / S01 (no episode) — skip if already captured as SxxEyy on same token
  for (const m of s.matchAll(/\bSeasons?\s*(\d{1,2})\b/gi)) {
    push(m[1]);
  }
  for (const m of s.matchAll(/\bS(\d{1,2})(?!\d|E\d)\b/gi)) {
    push(m[1]);
  }
  return out;
}

function titlePresent(blob, title) {
  const nt = normTitle(title);
  const nb = normTitle(blob);
  if (!nt || !nb) return false;
  if (nb.includes(nt)) return true;
  const words = nt.split(" ").filter((w) => w.length > 2);
  if (!words.length) return nb.includes(nt.replace(/\s/g, ""));
  // require most significant words
  const hits = words.filter((w) => nb.includes(w));
  return hits.length >= Math.ceil(words.length * 0.75);
}

function otherTitleStem(blob, title) {
  const m = String(blob || "").match(
    /([A-Za-z][A-Za-z0-9 .'_-]{1,48}?)(?:\s*[._-]?\s*)(?:S\d{1,2}|Seasons?\s*\d{1,2})\b/i,
  );
  if (!m) return "";
  const other = normTitle(m[1]);
  if (!other || other.length < 3) return "";
  if (
    /^(web|webdl|webrip|bluray|hdtv|hdrip|complete|pack|english|hindi|dual|multi|download|episode|season|series)$/i.test(
      other,
    )
  ) {
    return "";
  }
  if (titlePresent(other, title) || titlePresent(title, other)) return "";
  const tw = normTitle(title).split(" ").filter((w) => w.length > 3);
  if (tw.some((w) => other.includes(w))) return "";
  return other;
}

/**
 * True when name/url/tags look like a different season, episode, or show
 * than what the user asked to download.
 */
export function possibleWrongFile(item, expect) {
  if (!expect || (expect.season == null && expect.episode == null)) return false;
  const wantS = expect.season != null ? Number(expect.season) : null;
  const wantE = expect.episode != null ? Number(expect.episode) : null;
  const title = expect.title || "";
  const urls = [];
  if (item?.url) urls.push(item.url);
  for (const h of item?.hosters || []) if (h?.url) urls.push(h.url);
  const blob = [item?.name, ...(item?.tags || []), ...urls].filter(Boolean).join(" ");
  if (!blob.trim()) return false;

  const refs = parseAirRefs(blob);
  const epRefs = refs.filter((r) => r.episode != null || (r.epFrom != null && r.epTo != null));
  const seasonRefs = refs.filter((r) => r.season != null);

  const epMatches = (r) => {
    if (wantS != null && r.season != null && Number(r.season) !== wantS) return false;
    if (r.episode != null) return wantE == null || Number(r.episode) === wantE;
    if (r.epFrom != null && r.epTo != null) {
      if (wantE == null) return true;
      return wantE >= r.epFrom && wantE <= r.epTo;
    }
    return true;
  };

  if (wantE != null && epRefs.length) {
    if (!epRefs.some(epMatches)) return true;
  } else if (wantE != null && seasonRefs.length && !epRefs.length) {
    // Episode hunt got a season pack / season-only label, not SxxEyy
    return true;
  } else if (wantS != null && seasonRefs.length && !epRefs.length) {
    // season pack hunt: wrong season number
    if (!seasonRefs.some((r) => Number(r.season) === wantS)) return true;
  } else if (wantS != null && epRefs.length && wantE == null) {
    // downloading season pack but file is a single wrong-season episode
    if (epRefs.every((r) => r.season != null && Number(r.season) !== wantS)) return true;
  }

  // Wrong show: e.g. ReZero S01 while downloading Breaking Bad S1
  if (title && (wantS != null || wantE != null) && seasonRefs.length) {
    if (!titlePresent(blob, title) && otherTitleStem(blob, title)) return true;
  }

  return false;
}

/**
 * Merge mirrors of the same release into one row with multiple hoster links.
 * Groups per provider so different sites stay separate.
 */
export function groupDownloadLinks(results) {
  const groups = new Map();
  for (const row of results || []) {
    const site = row.site || "unknown";
    for (const item of row.links || []) {
      const url = linkUrl(item);
      if (!url) continue;
      const rel = releaseKey(item);
      const key = `${site}\0${rel}`;
      let g = groups.get(key);
      if (!g) {
        g = { site, name: linkName(item), release: rel, tags: [], hosters: [], _urls: new Set() };
        groups.set(key, g);
      }
      g.tags = mergeTags(g.tags, linkTags(item));
      if (nameScore(linkName(item)) > nameScore(g.name)) g.name = linkName(item);
      if (!g._urls.has(url)) {
        g._urls.add(url);
        g.hosters.push({ url, label: hosterLabel(item) });
      }
    }
  }
  const out = [];
  for (const g of groups.values()) {
    const used = new Set();
    for (const h of g.hosters) {
      let lab = h.label || "Link";
      if (used.has(lab)) {
        let i = 2;
        while (used.has(`${lab} ${i}`)) i++;
        lab = `${lab} ${i}`;
      }
      used.add(lab);
      h.label = lab;
    }
    out.push({
      site: g.site,
      name: g.name,
      tags: g.tags.filter((t) => t !== g.site && !isHosterTag(t)),
      hosters: g.hosters,
    });
  }
  return out;
}
