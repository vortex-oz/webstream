import re

from scrapers import _http as requests

FEED = "https://feed.animetosho.org/json"
TIMEOUT = 20
UA = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    )
}


def _norm(s):
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def _head(title):
    t = re.split(r"\s+-", (title or "").strip(), 1)[0].strip(" -:").strip()
    return t or (title or "").strip()


def _blob(it):
    return f"{it.get('title') or ''} {it.get('torrent_name') or ''}"


def _has_title(blob, title):
    short = _norm(_head(title))
    words = [w for w in short.split() if len(w) >= 2]
    if not words:
        return False
    n = _norm(blob)
    tn = _norm(title)
    if re.search(r"\bbreak time\b|\bfrom petit\b", n) and not re.search(r"\bbreak time\b|\bfrom petit\b", tn):
        return False
    if all(re.search(rf"\b{re.escape(w)}\b", n) for w in words):
        return True
    compact = re.sub(r"[^a-z0-9]+", "", short)
    return len(compact) >= 4 and compact in re.sub(r"[^a-z0-9]+", "", n)


def _has_year(blob, year):
    return year is None or bool(re.search(rf"\b{int(year)}\b", blob or ""))


def _is_ep(blob):
    b = blob or ""
    return bool(
        re.search(r"\bs\d{1,2}\s*e\d{1,3}\b|\b\d{1,2}x\d{2,3}\b", b, re.I)
        or re.search(r"(?:^|[\s\[(])-\s*\d{1,3}(?:\s|$|\.|\[)", b)
    )


def _has_ep(blob, season, episode):
    s, e = int(season), int(episode)
    b = blob or ""
    if re.search(rf"\bs0*{s}\s*e0*{e}\b|\b0*{s}x0*{e}\b", b, re.I):
        return True
    if re.search(r"\bs\d{1,2}\s*e\d{1,3}\b|\b\d{1,2}x\d{2,3}\b", b, re.I):
        return False
    if re.search(rf"\bs0*{s}\s*-\s*0*{e}\b", b, re.I):
        return True
    if re.search(r"\bs\d{1,2}\s*-\s*\d+", b, re.I):
        return False
    # "4th Season - 05" is cour numbering, not absolute episode 5
    if re.search(r"\b(?:\d+(?:st|nd|rd|th)\s+season|season\s*\d+)\b", b, re.I):
        return False
    return bool(re.search(rf"(?:^|[\s\[(])-\s*0*{e}(?:\s|$|\.|\[)", b))


def _has_season(blob, season):
    s = int(season)
    b = blob or ""
    if re.search(r"\bs\d{1,2}\s*e\d{1,2}\s*[-~]", b, re.I):
        return bool(re.search(rf"\bs0*{s}\s*e", b, re.I))
    if _is_ep(b):
        return False
    if re.search(rf"\bs0*{s}\b", b, re.I) or re.search(rf"\bseason\s*0*{s}\b", b, re.I):
        return True
    if re.search(r"\ball\s*seasons?|\bfull\s+\d+\s+seasons?", b, re.I):
        return True
    if not re.search(r"\b(?:complete|batch)\b", b, re.I):
        return False
    other = [int(x) for x in re.findall(r"\bs0*(\d+)\b", b, re.I)]
    return not other or s in other


def _q(title):
    t = (title or "").strip()
    return f'"{t}"' if " " in t else t


def _search(q):
    r = requests.get(FEED, params={"q": q}, headers=UA, timeout=TIMEOUT)
    if r.status_code != 200:
        return []
    data = r.json()
    return data if isinstance(data, list) else []


def _size_tag(n):
    try:
        n = float(n)
    except (TypeError, ValueError):
        return None
    if n <= 0:
        return None
    units = ("B", "KB", "MB", "GB", "TB")
    i = 0
    while n >= 1024 and i < 4:
        n /= 1024
        i += 1
    if i == 0:
        return None
    s = f"{n:.2f}".rstrip("0").rstrip(".")
    return f"{s}{units[i]}"


def _item(url, name, size=None):
    row = {"url": url, "name": name}
    st = _size_tag(size)
    if st:
        row["tags"] = [st]
    return row


def _http_links(links):
    if not isinstance(links, dict):
        return []
    prefer, rest = [], []
    for v in links.values():
        xs = v if isinstance(v, list) else [v]
        for x in xs:
            if not isinstance(x, str) or not x.startswith("http"):
                continue
            if re.search(r"gofile\.io|buzzheavier|akirabox|mdiaload", x, re.I):
                prefer.append(x)
            else:
                rest.append(x)
    return prefer + rest


def _detail(tid):
    r = requests.get(FEED, params={"show": "torrent", "id": tid}, headers=UA, timeout=TIMEOUT)
    if r.status_code != 200:
        return None
    j = r.json()
    return j if isinstance(j, dict) else None


def _row(it, want_files=False, ep=None):
    name = (it.get("torrent_name") or it.get("title") or "download").strip()
    url = it.get("torrent_url") or it.get("magnet_uri")
    tid = it.get("id")
    tot = it.get("total_size")
    if want_files and tid:
        det = _detail(tid)
        if det:
            url = det.get("torrent_url") or url
            name = (det.get("torrent_name") or name).strip()
            tot = det.get("total_size") or tot
            rows = []
            for f in det.get("files") or []:
                fn = (f.get("filename") or name).strip()
                if ep and not _has_ep(fn, ep[0], ep[1]) and not _has_ep(name, ep[0], ep[1]):
                    continue
                hrefs = _http_links(f.get("links") or {})
                if hrefs:
                    rows.append(_item(hrefs[0], fn, f.get("size")))
            if rows:
                return rows
    if not url:
        h = (it.get("info_hash") or "").lower()
        if h:
            url = f"https://storage.animetosho.org/torrent/{h}/torrent.torrent"
    if not url:
        return []
    return [_item(url, name, tot)]


def _collect(items, ok, want_files=False, ep=None, limit=4):
    out, seen = [], set()
    n = 0
    for it in items:
        if not ok(_blob(it)):
            continue
        use_files = want_files and n < limit
        if use_files:
            n += 1
        for row in _row(it, want_files=use_files, ep=ep):
            if row["url"] in seen:
                continue
            seen.add(row["url"])
            out.append(row)
    return out


def _find(title, ok, extra="", **kw):
    head = _head(title)
    extras = extra if isinstance(extra, (list, tuple)) else ([extra] if extra else [])
    qs = []
    for ex in extras:
        qs.append(f"{head} {ex}")
    qs.append(head)
    if (title or "").strip() != head:
        qs.append(_q(title))
    seen_q, out, seen_u = set(), [], set()
    for q in qs:
        if not q or q in seen_q:
            continue
        seen_q.add(q)
        for row in _collect(_search(q), ok, **kw):
            if row["url"] in seen_u:
                continue
            seen_u.add(row["url"])
            out.append(row)
        if out:
            break
    return out


def dlmovie(title, year=None, tmdb_id=None, imdb_id=None):
    try:
        return _find(
            title,
            lambda b: _has_title(b, title) and _has_year(b, year) and not _is_ep(b),
            want_files=True,
        )
    except Exception:
        return []


def dlseries(title, season, year=None, tmdb_id=None, imdb_id=None):
    try:
        s = int(season)
        return _find(title, lambda b: _has_title(b, title) and _has_season(b, s), extra=f"S{s:02d}")
    except Exception:
        return []


def dlseriesepisode(title, season, episode, year=None, tmdb_id=None, imdb_id=None):
    try:
        s, e = int(season), int(episode)
        return _find(
            title,
            lambda b: _has_title(b, title) and _has_ep(b, s, e),
            extra=[f"S{s:02d}E{e:02d}", f"- {e:02d}"],
            want_files=True,
            ep=(s, e),
        )
    except Exception:
        return []


if __name__ == "__main__":
    import json
    from pathlib import Path
    base = Path(__file__).resolve().parent
    avatar = json.loads((base / "avatar.json").read_text())
    bb = json.loads((base / "breaking_bad.json").read_text())
    print("avatar", dlmovie(avatar["title"], year=int(avatar["release_date"][:4]), tmdb_id=avatar["id"], imdb_id=avatar.get("imdb_id")))
    print("breaking_bad_s1", dlseries(bb["name"], 1, year=int(bb["first_air_date"][:4]), tmdb_id=bb["id"], imdb_id=(bb.get("external_ids") or {}).get("imdb_id")))
    print("breaking_bad_s1e5", dlseriesepisode(bb["name"], 1, 5, year=int(bb["first_air_date"][:4]), tmdb_id=bb["id"], imdb_id=(bb.get("external_ids") or {}).get("imdb_id")))
