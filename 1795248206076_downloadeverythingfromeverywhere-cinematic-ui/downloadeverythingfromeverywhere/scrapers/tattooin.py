import re
from urllib.parse import unquote, urljoin, urlparse

from bs4 import BeautifulSoup
from scrapers import _http as requests
from scrapers._tags import format_size, tags_from

BASE = "https://tattooin.ru"
ROOT = BASE + "/ftp/upload/"
TIMEOUT = 20
VIDEO_EXT = (".mkv", ".mp4", ".avi", ".m4v", ".ts", ".iso", ".m2ts")
SKIP = re.compile(r"(^|[._-])sample([._-]|$)", re.I)
# next token after the title in a scene/release name
NEXT = re.compile(
    r"^(?:(?:19|20)\d{2}|s\d{1,2}(?:e\d{1,3})?|\d{1,2}x\d{2,3}|\d{3,4}p|4k|uhd|"
    r"hdr\d*|sdr|hlg|dv|dovi?|web|webdl|webrip|bluray|blu|bdrip|brrip|bdremux|"
    r"remux|hdtv|hdrip|x265|x264|h265|h264|hevc|avc|av1|season|complete|"
    r"extended|uncut|hybrid|proper|repack|truehd|atmos|dts)$"
)


def _tok(s):
    return re.sub(r"[^a-z0-9]+", " ", unquote(s or "").lower()).split()


def _title_hit(name, title, year=None, need_year=False):
    want, have = _tok(title), _tok(name)
    if not want or len(have) < len(want):
        return False
    if need_year and year is not None and str(year) not in have:
        return False
    year_ok = year is None or str(year) in have
    n = len(want)
    for i in range(len(have) - n + 1):
        if have[i : i + n] != want:
            continue
        if i and not NEXT.match(have[i - 1]):
            continue
        nxt = i + n >= len(have) or NEXT.match(have[i + n])
        if nxt or (year is not None and year_ok):
            return True
    return False


def _seasons(name):
    found = {int(x) for x in re.findall(r"(?:^|[^a-z0-9])s(\d{1,2})(?!\d)", name, re.I)}
    found.update(int(x) for x in re.findall(r"season\s*(\d{1,2})\b", name, re.I))
    return found


def _is_video(name):
    low = (name or "").lower()
    return low.endswith(VIDEO_EXT) and not SKIP.search(name)


def _is_single_ep(name):
    if re.search(r"s\d{1,2}[\s._-]*e\d{1,3}[\s._-]*(?:-|–|to)[\s._-]*e?\d", name, re.I):
        return False
    return bool(
        re.search(r"s\d{1,2}[\s._-]*e\d{1,3}", name, re.I)
        or re.search(r"(?<![a-z0-9])\d{1,2}x\d{2,3}(?![a-z0-9])", name, re.I)
    )


def _ep_hit(name, season, episode):
    s, e = int(season), int(episode)
    return bool(
        re.search(
            rf"(?:^|[^a-z0-9])(?:s0*{s}[\s._-]*e0*{e}|0*{s}x0*{e})(?:[^a-z0-9]|$)",
            name,
            re.I,
        )
    )


def _sz(v):
    m = re.search(r"([\d.]+)\s*(Ki?B|Mi?B|Gi?B|Ti?B)", str(v or ""), re.I)
    if not m:
        return None
    n = float(m.group(1).replace(",", "."))
    u = m.group(2).upper()
    if u in ("KB", "KIB") and n >= 1024:
        return format_size(n * 1024)
    ts = tags_from(m.group(0))
    return next((t for t in ts if re.search(r"(KB|MB|GB|TB)$", t)), None)


def _item(name, url, size=None):
    st = _sz(size)
    return {"url": url, "name": name, "tags": tags_from(name, st or "")}


def _parse(html, page_url):
    soup = BeautifulSoup(html, "html.parser")
    out = []
    seen = set()
    for a in soup.select("#fallback a[href], table a[href]"):
        href = a.get("href") or ""
        name = a.get_text(strip=True)
        if not href or href in (".", "..", "../") or name in ("Parent Directory", ".."):
            continue
        if href.startswith("?") or "/_h5ai/" in href:
            continue
        url = urljoin(page_url if page_url.endswith("/") else page_url + "/", href)
        if url in seen:
            continue
        seen.add(url)
        fname = name or unquote(urlparse(url).path.rstrip("/").split("/")[-1])
        size = ""
        tr = a.find_parent("tr")
        if tr:
            tds = tr.find_all("td")
            if tds:
                size = tds[-1].get_text(" ", strip=True)
        out.append((fname, url, href.endswith("/"), size))
    return out


_cache = {}


def _fetch(url):
    if url not in _cache:
        r = requests.get(url, timeout=TIMEOUT)
        _cache[url] = _parse(r.text, url) if r.status_code == 200 else []
    return _cache[url]


def _videos(url):
    return [_item(n, u, sz) for n, u, d, sz in _fetch(url) if not d and _is_video(n)]


def _hits(title, year=None, need_year=False, season=None):
    out = []
    for name, url, is_dir, size in _fetch(ROOT):
        if not _title_hit(name, title, year=year, need_year=need_year):
            continue
        seas = _seasons(name)
        if season is None:
            if seas:
                continue
        elif seas and int(season) not in seas:
            continue
        elif not seas and not is_dir:
            continue
        out.append((name, url, is_dir, size))
    return out


def dlmovie(title, year=None, tmdb_id=None, imdb_id=None):
    try:
        found = []
        for name, url, is_dir, size in _hits(title, year=year, need_year=year is not None):
            if is_dir:
                found.extend(_videos(url))
            elif _is_video(name):
                found.append(_item(name, url, size))
        return found
    except Exception:
        return []


def dlseries(title, season, year=None, tmdb_id=None, imdb_id=None):
    try:
        found = []
        for name, url, is_dir, size in _hits(title, year=year, season=season):
            if is_dir:
                found.extend(it for it in _videos(url) if not _is_single_ep(it["name"]))
            elif _is_video(name) and not _is_single_ep(name):
                found.append(_item(name, url, size))
        return found
    except Exception:
        return []


def dlseriesepisode(title, season, episode, year=None, tmdb_id=None, imdb_id=None):
    try:
        found = []
        for name, url, is_dir, size in _hits(title, year=year, season=season):
            if is_dir:
                for it in _videos(url):
                    if _ep_hit(it["name"], season, episode):
                        found.append(it)
            elif _is_video(name) and _ep_hit(name, season, episode):
                found.append(_item(name, url, size))
        return found
    except Exception:
        return []


if __name__ == "__main__":
    import json
    from pathlib import Path

    base = Path(__file__).resolve().parent
    avatar = json.loads((base / "avatar.json").read_text())
    bb = json.loads((base / "breaking_bad.json").read_text())
    bb_s1 = json.loads((base / "breaking_bad_s1.json").read_text())
    print(
        "avatar",
        dlmovie(avatar["title"], year=int(avatar["release_date"][:4]), tmdb_id=avatar["id"], imdb_id=avatar.get("imdb_id")),
    )
    print(
        "breaking_bad_s1",
        dlseries(
            bb["name"],
            1,
            year=int(bb["first_air_date"][:4]),
            tmdb_id=bb["id"],
            imdb_id=(bb.get("external_ids") or {}).get("imdb_id"),
        ),
    )
    print(
        "breaking_bad_s1e5",
        dlseriesepisode(
            bb["name"],
            1,
            5,
            year=int(bb["first_air_date"][:4]),
            tmdb_id=bb["id"],
            imdb_id=(bb.get("external_ids") or {}).get("imdb_id"),
        ),
    )
