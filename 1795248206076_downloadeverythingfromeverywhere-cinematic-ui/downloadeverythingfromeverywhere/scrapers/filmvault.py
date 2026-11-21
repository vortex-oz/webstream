import re

from scrapers import _http as requests
from scrapers._tags import tags_from, format_size

BASE = "https://filmvault.xyz"
UA = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Referer": BASE + "/",
    "Accept": "application/json",
}
TIMEOUT = 20
TG = re.compile(r"(?:t\.me|telegram\.me|telegram\.dog)/", re.I)
EP = re.compile(r"(?:^|[^a-z0-9])s0*(\d{1,2})e0*(\d{1,3})(?:[^a-z0-9]|$)", re.I)
SEASON = re.compile(r"season\s*0*(\d{1,2})\b", re.I)
SKIP_FILE = re.compile(r"\.(mka|mks|srt|ass|idx|sub)$", re.I)


def _norm(s):
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def _size_tag(n):
    if n is None or n == "":
        return None
    if isinstance(n, str):
        m = re.search(r"([\d.,]+)\s*(TiB|GiB|MiB|KiB|TB|GB|MB|KB)", n, re.I)
        if m:
            num = m.group(1).replace(",", "")
            if "." in num:
                num = num.rstrip("0").rstrip(".")
            if not num:
                return None
            return f"{num}{m.group(2).upper().replace('IB', 'B')}"
        try:
            n = float(n.replace(",", "").strip())
        except Exception:
            return None
    try:
        n = float(n)
    except Exception:
        return None
    return format_size(n)


def _item(url, name, size=None, *extra):
    tags = []
    if TG.search(url or ""):
        tags.append("Telegram")
    st = _size_tag(size)
    if st:
        tags.append(st)
    more = tags_from(name, *extra, url)
    if st:
        more = [t for t in more if not re.fullmatch(r"\d+(?:\.\d+)?(?:KB|MB|GB|TB)", t, re.I)]
    tags.extend(more)
    seen, out = set(), []
    for t in tags:
        if t and t not in seen:
            seen.add(t)
            out.append(t)
    return {"url": url, "name": name, "tags": out}


def _json(path, params):
    r = requests.get(BASE + path, headers=UA, timeout=TIMEOUT, params=params)
    if int(getattr(r, "status_code", 0) or 0) != 200:
        return {}
    t = r.text or ""
    if "Just a moment" in t[:2000]:
        return {}
    try:
        data = r.json()
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _search(path, title):
    data = _json(path, {"title": title, "skip": 1, "limit": 20})
    rows = data.get("items")
    return rows if isinstance(rows, list) else []


def _imdb_ok(a, b):
    if not a or not b:
        return False
    na, nb = re.sub(r"^tt", "", str(a).lower()), re.sub(r"^tt", "", str(b).lower())
    return na == nb and na.isdigit()


def _pick(rows, title, year=None, tmdb_id=None, imdb_id=None, tv=False):
    want = _norm(title)
    fallback = None
    for it in rows:
        if not isinstance(it, dict):
            continue
        typ = (it.get("type") or "").lower()
        if tv and typ == "movie":
            continue
        if not tv and typ and typ != "movie":
            continue
        if tmdb_id and str(it.get("tmdbId") or "") == str(tmdb_id):
            return it
        if _imdb_ok(it.get("imdbId") or it.get("imdb_id"), imdb_id):
            return it
        blob = _norm(" ".join(str(it.get(k) or "") for k in ("title", "name", "tmdbTitle")))
        if not want or want not in blob:
            continue
        if want == "avatar" and re.search(r"way of water|fire and ash|airbender|aang", blob):
            continue
        ys = " ".join(str(it.get(k) or "") for k in ("year", "title", "tmdbReleaseDate", "tmdbFirstAirDate"))
        if year and str(year) not in ys:
            continue
        if fallback is None:
            fallback = it
    return fallback


def _tg_url(d):
    for k in ("url", "file_url", "file_link", "telegramLink"):
        u = (d.get(k) or "").strip()
        if u.startswith("http") and TG.search(u):
            return u
    return ""


def _tg_rows(it):
    out = []
    for td in it.get("telegramData") or []:
        if not isinstance(td, dict):
            continue
        for l in td.get("telegramLinks") or []:
            if isinstance(l, dict):
                out.append(l)
    for f in it.get("telegramFiles") or []:
        if isinstance(f, dict):
            out.append(f)
    return out


def _from_tg(row):
    url = _tg_url(row)
    name = row.get("file_name") or row.get("downloadTitle") or ""
    if not url or not name or SKIP_FILE.search(name):
        return None
    return _item(url, name, row.get("file_size") or row.get("downloadSize"), row.get("season") or "")


def _from_ddl(it):
    out = []
    for e in it.get("episodesDataBC") or []:
        if not isinstance(e, dict):
            continue
        url = (e.get("downloadLink") or "").strip()
        name = e.get("quality") or ""
        if not url.startswith("http") or not name or SKIP_FILE.search(name):
            continue
        out.append(_item(url, name, e.get("size")))
    return out


def _ep_hit(name, season, episode):
    m = EP.search(name or "")
    return bool(m and int(m.group(1)) == int(season) and int(m.group(2)) == int(episode))


def _season_n(row):
    m = SEASON.search(row.get("season") or "")
    if m:
        return int(m.group(1))
    m = EP.search(row.get("file_name") or "")
    return int(m.group(1)) if m else None


def _uniq(items):
    out, seen = [], set()
    for it in items:
        if not it:
            continue
        k = (it["url"], it["name"])
        if k in seen:
            continue
        seen.add(k)
        out.append(it)
    return out


def dlmovie(title, year=None, tmdb_id=None, imdb_id=None):
    try:
        it = _pick(_search("/api/search-am", title), title, year=year, tmdb_id=tmdb_id, imdb_id=imdb_id)
        if not it:
            return []
        found = [_from_tg(r) for r in _tg_rows(it)]
        found.extend(_from_ddl(it))
        return _uniq(found)
    except Exception:
        return []


def dlseries(title, season, year=None, tmdb_id=None, imdb_id=None):
    return


def dlseriesepisode(title, season, episode, year=None, tmdb_id=None, imdb_id=None):
    try:
        it = _pick(_search("/api/search-aiom", title), title, year=year, tmdb_id=tmdb_id, imdb_id=imdb_id, tv=True)
        if not it:
            return []
        sn, en = int(season), int(episode)
        found = []
        for row in _tg_rows(it):
            name = row.get("file_name") or ""
            if _season_n(row) not in (None, sn):
                continue
            if not _ep_hit(name, sn, en):
                continue
            found.append(_from_tg(row))
        return _uniq(found)
    except Exception:
        return []


if __name__ == "__main__":
    import json
    from pathlib import Path

    base = Path(__file__).resolve().parent
    avatar = json.loads((base / "avatar.json").read_text())
    bb = json.loads((base / "breaking_bad.json").read_text())
    bb_s1 = json.loads((base / "breaking_bad_s1.json").read_text())
    print("avatar", dlmovie(avatar["title"], year=int(avatar["release_date"][:4]), tmdb_id=avatar["id"], imdb_id=avatar.get("imdb_id")))
    print("breaking_bad_s1", dlseries(bb["name"], 1, year=int(bb["first_air_date"][:4]), tmdb_id=bb["id"], imdb_id=(bb.get("external_ids") or {}).get("imdb_id")))
    print("breaking_bad_s1e5", dlseriesepisode(bb["name"], 1, 5, year=int(bb["first_air_date"][:4]), tmdb_id=bb["id"], imdb_id=(bb.get("external_ids") or {}).get("imdb_id")))
