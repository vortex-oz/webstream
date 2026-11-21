import json
import re

from scrapers import _http as requests
from scrapers._tags import tags_from, format_size

BASE = "https://thecinefy.site"
UA = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    )
}
TIMEOUT = 20
TG = re.compile(r"(?:t\.me|telegram\.me|telegram\.dog)/", re.I)
EP = re.compile(r"(?:^|[^a-z0-9])s0*(\d{1,2})e0*(\d{1,3})(?:[^a-z0-9]|$)", re.I)


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


def _get(url, params=None):
    r = requests.get(url, headers=UA, timeout=TIMEOUT, params=params)
    if int(getattr(r, "status_code", 0) or 0) != 200:
        return None
    t = r.text or ""
    if "Just a moment" in t[:2000]:
        return None
    return r


def _search(q, kind="all"):
    r = _get(f"{BASE}/api/search", params={"query": q, "itemType": kind, "limit": 10, "page": 1})
    if not r:
        return []
    try:
        data = r.json()
    except Exception:
        return []
    rows = data.get("results") if isinstance(data, dict) else None
    return rows if isinstance(rows, list) else []


def _pick(title, year=None, tv=False):
    wt = _norm(title)
    kind = "series" if tv else "movie"
    rows = _search(title, kind) or _search(title, "all")
    for it in rows:
        if _norm(it.get("title")) != wt:
            continue
        typ = (it.get("type") or "").lower()
        if tv and typ == "movie":
            continue
        if not tv and typ != "movie":
            continue
        if year and str(year) not in str(it.get("year") or ""):
            continue
        slug = it.get("slug")
        if slug:
            return f"{BASE}/{'show' if tv else 'movie'}/{slug}"
    if year:
        slug = re.sub(r"[^a-z0-9]+", "-", (title or "").lower()).strip("-") + f"-{year}"
        return f"{BASE}/{'show' if tv else 'movie'}/{slug}"
    return None


def _brace(s, j):
    depth, in_str, esc = 0, False, False
    for k in range(j, len(s)):
        c = s[k]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            continue
        if c == '"':
            in_str = True
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return s[j : k + 1], k + 1
    return None, j + 1


def _files(html):
    t = (html or "").replace('\\"', '"')
    best, start = {}, 0
    while True:
        i = t.find('"files":', start)
        if i < 0:
            break
        j = t.find("{", i)
        if j < 0:
            break
        blob, start = _brace(t, j)
        if not blob:
            break
        try:
            data = json.loads(blob)
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        groups = {
            k: v
            for k, v in data.items()
            if isinstance(v, dict) and (v.get("msg_ids") or v.get("download_link"))
        }
        if groups:
            best = groups
    return best


def _page(title, year=None, tv=False):
    url = _pick(title, year=year, tv=tv)
    if not url:
        return {}
    r = _get(url)
    return _files(r.text) if r else {}


def _season_n(key, group):
    n = group.get("season_number")
    if n is not None:
        try:
            return int(n)
        except Exception:
            pass
    m = re.search(r"season\s*(\d+)", key or "", re.I)
    return int(m.group(1)) if m else None


def _ep_hit(name, season, episode):
    m = EP.search(name or "")
    return bool(m and int(m.group(1)) == int(season) and int(m.group(2)) == int(episode))


def _from_group(key, group, episode=None):
    url = (group.get("download_link") or "").strip()
    if not url:
        return []
    msgs = group.get("msg_ids") or []
    if episode is not None:
        out = []
        for m in msgs:
            name = m.get("file_name") or key
            if _ep_hit(name, episode[0], episode[1]):
                out.append(_item(url, name, m.get("file_size"), key))
        return out
    if len(msgs) == 1:
        m = msgs[0]
        return [_item(url, m.get("file_name") or key, m.get("file_size"), key)]
    size = sum(int(m.get("file_size") or 0) for m in msgs) or None
    return [_item(url, key, size, key)]


def dlmovie(title, year=None, tmdb_id=None, imdb_id=None):
    try:
        files = _page(title, year=year, tv=False)
        out, seen = [], set()
        for key, group in files.items():
            if _season_n(key, group) is not None:
                continue
            for it in _from_group(key, group):
                k = (it["url"], it["name"])
                if k in seen:
                    continue
                seen.add(k)
                out.append(it)
        return out
    except Exception:
        return []


def dlseries(title, season, year=None, tmdb_id=None, imdb_id=None):
    try:
        files = _page(title, year=year, tv=True)
        sn = int(season)
        out, seen = [], set()
        for key, group in files.items():
            if _season_n(key, group) != sn:
                continue
            for it in _from_group(key, group):
                k = (it["url"], it["name"])
                if k in seen:
                    continue
                seen.add(k)
                out.append(it)
        return out
    except Exception:
        return []


def dlseriesepisode(title, season, episode, year=None, tmdb_id=None, imdb_id=None):
    try:
        files = _page(title, year=year, tv=True)
        sn, en = int(season), int(episode)
        out, seen = [], set()
        for key, group in files.items():
            if _season_n(key, group) not in (None, sn):
                continue
            for it in _from_group(key, group, episode=(sn, en)):
                k = (it["url"], it["name"])
                if k in seen:
                    continue
                seen.add(k)
                out.append(it)
        return out
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
