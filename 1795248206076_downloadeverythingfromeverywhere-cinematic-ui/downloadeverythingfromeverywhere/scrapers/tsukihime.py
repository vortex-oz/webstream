import re

from scrapers import _http as requests

API = "https://api.tsukihime.org/v1"
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
    t = re.split(r"\s+-", (title or "").strip(), maxsplit=1)[0].strip(" -:").strip()
    return t or (title or "").strip()


def _nth(n):
    n = int(n)
    if n % 100 in (11, 12, 13):
        return f"{n}th"
    return {1: "1st", 2: "2nd", 3: "3rd"}.get(n % 10, f"{n}th")


def _blob(it):
    return f"{it.get('name') or ''} {it.get('filename') or ''}"


def _heads(title):
    head = _head(title)
    n = _norm(head)
    out = [head]
    if n == "your name":
        out.append("Kimi no Na wa")
    if n in ("re zero", "rezero"):
        out.append("Re:Zero kara Hajimeru Isekai Seikatsu")
    seen, qs = set(), []
    for q in out:
        if q and q not in seen:
            seen.add(q)
            qs.append(q)
    return qs


def _has_title(blob, title):
    short = _norm(_head(title))
    words = [w for w in short.split() if len(w) >= 2]
    if not words:
        return False
    n = _norm(blob)
    if short == "your name" and "kimi no na wa" in n:
        return True
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
        or re.search(r"(?:^|[\s\[(_])[-–—][_.\s]*\d{1,3}(?:[\s\[\(\._]|$)", b)
    )


def _has_ep(blob, season, episode):
    s, e = int(season), int(episode)
    b = blob or ""
    if re.search(rf"\bs0*{s}\s*e0*{e}\b|\b0*{s}x0*{e}\b", b, re.I):
        return True
    if re.search(r"\bs\d{1,2}\s*e\d{1,3}\b|\b\d{1,2}x\d{2,3}\b", b, re.I):
        return False
    if re.search(rf"\b{_nth(s)}\s+season\b", b, re.I):
        return bool(re.search(rf"[-–—][_.\s]*0*{e}(?:[\s\[\(\._]|$)", b))
    if re.search(r"\b(?:\d+(?:st|nd|rd|th)\s+season|season\s*\d+)\b", b, re.I):
        return False
    return bool(re.search(rf"(?:^|[\s\[(_])[-–—][_.\s]*0*{e}(?:v\d+)?(?:[\s\[\(\._]|$)", b))


def _has_season(blob, season):
    s = int(season)
    b = blob or ""
    if re.search(rf"\b{_nth(s)}\s+season\b", b, re.I):
        return True
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


def _json(path, params=None):
    r = requests.get(API + path, params=params, headers=UA, timeout=TIMEOUT)
    if r.status_code != 200:
        return None
    try:
        j = r.json()
    except Exception:
        return None
    return j if isinstance(j, dict) else None


def _search(q):
    j = _json("/search/torrents", {"q": q, "limit": 50})
    if not j:
        return []
    rows = j.get("results")
    return rows if isinstance(rows, list) else []


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


def _http_links(links):
    if not isinstance(links, dict):
        return []
    prefer, rest = [], []
    for v in links.values():
        xs = v if isinstance(v, list) else [v]
        for x in xs:
            if not isinstance(x, str) or not x.startswith("http"):
                continue
            if re.search(r"gofile\.io|buzzheavier|fileditch|akirabox|mdiaload", x, re.I):
                prefer.append(x)
            else:
                rest.append(x)
    return prefer + rest


def _detail(tid):
    return _json(f"/torrents/{tid}")


def _row(it, want_files=False, ep=None):
    name = (it.get("name") or "download").strip()
    tid = it.get("id")
    if not want_files or not tid:
        return []
    det = _detail(tid)
    if not det:
        return []
    name = (det.get("name") or name).strip()
    rows = []
    for f in det.get("files") or []:
        fn = (f.get("filename") or name).strip()
        if ep and not _has_ep(fn, ep[0], ep[1]) and not _has_ep(name, ep[0], ep[1]):
            continue
        hrefs = _http_links(f.get("links") or {})
        if hrefs:
            row = {"url": hrefs[0], "name": fn}
            st = _size_tag(f.get("size"))
            if st:
                row["tags"] = [st]
            rows.append(row)
    return rows


def _collect(items, ok, want_files=False, ep=None, limit=4):
    out, seen = [], set()
    n = 0
    for it in items:
        if not ok(_blob(it)):
            continue
        if n >= limit:
            break
        n += 1
        for row in _row(it, want_files=want_files, ep=ep):
            if row["url"] in seen:
                continue
            seen.add(row["url"])
            out.append(row)
    return out


def _find(title, ok, extra="", **kw):
    extras = extra if isinstance(extra, (list, tuple)) else ([extra] if extra else [])
    qs = []
    for head in _heads(title):
        for ex in extras:
            qs.append(f"{head} {ex}")
        qs.append(head)
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
        return _find(
            title,
            lambda b: _has_title(b, title) and _has_season(b, s),
            extra=[f"S{s:02d}", "batch"],
            want_files=True,
        )
    except Exception:
        return []


def dlseriesepisode(title, season, episode, year=None, tmdb_id=None, imdb_id=None):
    try:
        s, e = int(season), int(episode)
        return _find(
            title,
            lambda b: _has_title(b, title) and _has_ep(b, s, e),
            extra=[f'"{e:02d}"', f"S{s:02d}E{e:02d}"],
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
    rz, y = "Re:ZERO -Starting Life in Another World-", 2016
    print("rezero_s1", dlseries(rz, 1, year=y, tmdb_id=65942, imdb_id="tt5607616"))
    print("rezero_s1e1", dlseriesepisode(rz, 1, 1, year=y, tmdb_id=65942, imdb_id="tt5607616"))
    print("rezero_s1e78", dlseriesepisode(rz, 1, 78, year=y, tmdb_id=65942, imdb_id="tt5607616"))
    print("your_name", dlmovie("Your Name", year=2016, tmdb_id=372058))
