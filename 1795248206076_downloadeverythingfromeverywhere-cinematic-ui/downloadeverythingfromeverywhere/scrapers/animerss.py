import re
from urllib.parse import quote_plus

from bs4 import BeautifulSoup
from scrapers import _http as requests
from scrapers._tags import item as tag_item

BASE = "https://animerss.com"
TIMEOUT = 20
UA = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    )
}
HOST = re.compile(r"rapidgator\.net/file/", re.I)
SKIP = re.compile(r"account/|article/premium|/ref/", re.I)
JUNK = re.compile(r"\bova\b|soundtrack|cosplay", re.I)
SIZE = re.compile(r"(?<![A-Za-z0-9.])(\d{1,4}(?:\.\d{1,2})?)\s*(KB|MB|GB|TB)\b", re.I)


def _size_tag(text):
    m = SIZE.search(text or "")
    if not m:
        return None
    n = m.group(1)
    if "." in n:
        n = n.rstrip("0").rstrip(".")
    return f"{n}{m.group(2).upper()}"


def _with_size(row, *parts):
    sz = None
    for p in parts:
        sz = _size_tag(p)
        if sz:
            break
    if sz and sz not in (row.get("tags") or []):
        row = {**row, "tags": list(row.get("tags") or []) + [sz]}
    return row


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


def _queries(title):
    head = _head(title)
    out = [head]
    n = _norm(head)
    if n in ("re zero", "rezero") or n.startswith("re zero"):
        out.extend(["Re:Zero", "Re:Zero kara Hajimeru Isekai Seikatsu"])
    if n == "your name" or "kimi no na wa" in _norm(title):
        out.extend(["Kimi no Na wa", "君の名は"])
    seen, qs = set(), []
    for q in out:
        if q and q not in seen:
            seen.add(q)
            qs.append(q)
    return qs


def _title_hit(name, title):
    n, t = _norm(name), _norm(_head(title))
    if not t or not n:
        return False
    if t in n:
        return True
    words = [w for w in t.split() if len(w) >= 2]
    return bool(words) and all(re.search(rf"\b{re.escape(w)}\b", n) for w in words)


def _post_seasons(name):
    found = set()
    for i in range(1, 9):
        if re.search(rf"\b{_nth(i)}\s*season\b", name, re.I):
            found.add(i)
    if found:
        return found
    for i in range(1, 9):
        if re.search(rf"\bseason\s*0*{i}\b", name, re.I):
            found.add(i)
    m = re.search(r"第0*(\d+)\s*[-–~]\s*0*(\d+)話", name)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        if b - a > 30:
            found.update({1, 2, 3, 4})
        elif not found:
            found.add(1)
    if not found:
        found.add(1)
    return found


def _season_ok(name, season, episode=None):
    s = int(season)
    m = re.search(r"第0*(\d+)\s*[-–~]\s*0*(\d+)話", name)
    huge = bool(m and int(m.group(2)) - int(m.group(1)) > 30 and not re.search(r"\d(?:st|nd|rd|th)\s*season", name, re.I))
    if episode is not None and m and int(m.group(1)) <= int(episode) <= int(m.group(2)):
        return True
    if huge and episode is None:
        return False
    return s in _post_seasons(name)


def _ep_hit(name, season, episode):
    s, e = int(season), int(episode)
    if re.search(rf"(?:^|[^a-z0-9])s0*{s}[\s._-]*e0*{e}(?:[^a-z0-9]|$)", name, re.I):
        return True
    if re.search(r"s\d{1,2}[\s._-]*e\d{1,3}", name, re.I):
        return False
    if re.search(r"\d(?:st|nd|rd|th)\s*season", name, re.I):
        return bool(re.search(rf"{_nth(s)}\s*season\s*[-–—_]\s*0*{e}(?:\D|$)", name, re.I))
    return bool(re.search(rf"[-–—][_.\s]*0*{e}(?:v\d+)?(?:[\s\[\(\._]|$)", name))


def _get(url, params=None):
    r = requests.get(url, headers=UA, timeout=TIMEOUT, params=params)
    if int(getattr(r, "status_code", 0) or 0) != 200:
        return None
    if "Just a moment" in (r.text or "")[:2000]:
        return None
    return r


def _search(q):
    items, seen = [], set()
    r = _get(f"{BASE}/wp-json/wp/v2/posts", params={"search": q, "per_page": 20})
    if r is not None:
        try:
            rows = r.json()
        except Exception:
            rows = []
        if isinstance(rows, list):
            for p in rows:
                title = re.sub(r"<[^>]+>", "", (p.get("title") or {}).get("rendered") or "")
                url = p.get("link") or ""
                if not url or url in seen:
                    continue
                seen.add(url)
                items.append({"title": title, "url": url})
            if items:
                return items
    r = _get(f"{BASE}/?s={quote_plus(q)}")
    if r is None:
        return items
    soup = BeautifulSoup(r.text, "html.parser")
    for a in soup.find_all("a", href=True):
        href, t = a["href"], a.get_text(" ", strip=True)
        if not t or not href.startswith(BASE) or href in seen:
            continue
        if re.search(r"/category/|/author/|/feed|/dmca", href):
            continue
        if not re.search(r"tvrip-|bdmv-|bdrip-|dvdrip-|bdiso-", href):
            continue
        seen.add(href)
        items.append({"title": t, "url": href})
    return items


def _pick(items, title, year=None, season=None, episode=None, movie=False):
    out = []
    for it in items:
        t = it["title"]
        if not _title_hit(t, title):
            continue
        if JUNK.search(t) and not re.search(r"tvrip|bdmv|bdrip|bdiso", t, re.I):
            continue
        if movie:
            if re.search(r"第\d|season\s*\d|\d(?:st|nd|rd|th)\s*season", t, re.I) and not re.search(
                r"movie|劇場", t, re.I
            ):
                continue
            if year is not None and str(year) not in t and str(year) not in _norm(t):
                if not re.search(r"movie|劇場", t, re.I):
                    continue
        elif season is not None and not _season_ok(t, season, episode=episode):
            continue
        out.append(it)
    return out


def _links(html, post_title=""):
    soup = BeautifulSoup(html or "", "html.parser")
    out, seen = [], set()
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not HOST.search(href) or SKIP.search(href) or href in seen:
            continue
        seen.add(href)
        name = a.get_text(" ", strip=True) or post_title
        out.append(_with_size(tag_item(href, name, post_title), name))
    return out


def _collect(title, year=None, season=None, episode=None, movie=False):
    posts, seen = [], set()
    for q in _queries(title):
        for it in _pick(_search(q), title, year=year, season=season, episode=episode, movie=movie):
            if it["url"] in seen:
                continue
            seen.add(it["url"])
            posts.append(it)
        if posts:
            break
    out, seen_u = [], set()
    for it in posts[:6]:
        r = _get(it["url"])
        if r is None:
            continue
        for row in _links(r.text, it["title"]):
            blob = f"{row['name']} {it['title']} {row['url']}"
            if episode is not None:
                if not _ep_hit(blob, season, episode):
                    continue
            elif season is not None and re.search(r"\d(?:st|nd|rd|th)\s*season", blob, re.I):
                if not re.search(rf"{_nth(int(season))}\s*season", blob, re.I):
                    continue
            if row["url"] in seen_u:
                continue
            seen_u.add(row["url"])
            out.append(row)
    return out


def dlmovie(title, year=None, tmdb_id=None, imdb_id=None):
    try:
        return _collect(title, year=year, movie=True)
    except Exception:
        return []


def dlseries(title, season, year=None, tmdb_id=None, imdb_id=None):
    try:
        return _collect(title, year=year, season=season)
    except Exception:
        return []


def dlseriesepisode(title, season, episode, year=None, tmdb_id=None, imdb_id=None):
    try:
        return _collect(title, year=year, season=season, episode=episode)
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
