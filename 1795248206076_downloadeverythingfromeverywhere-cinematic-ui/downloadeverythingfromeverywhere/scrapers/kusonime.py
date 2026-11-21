import re
from urllib.parse import quote_plus

from scrapers import _http as requests
from bs4 import BeautifulSoup

BASE = "https://kusonime.com"
UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
}
TIMEOUT = 20
HOST = re.compile(r"mega\.nz|acefile\.co|hxfile\.co|drive\.google|mediafire\.com", re.I)
INDO = re.compile(r"\bsubtitle\s+indonesia\b|\bsub(?:title)?\s*indo(?:nesia)?\b", re.I)
QUAL = re.compile(r"(\d{3,4})\s*p", re.I)
SIZE = re.compile(r"(?<![A-Za-z0-9.])(\d{1,4}(?:\.\d{1,2})?)\s*(KB|MB|GB|TB)\b", re.I)
QSIZE = re.compile(r"(\d{3,4})\s*p\s*[:\-–|]?\s*(\d{1,4}(?:\.\d{1,2})?)\s*(KB|MB|GB|TB)\b", re.I)


def _canon(num, unit):
    n = str(num)
    if "." in n:
        n = n.rstrip("0").rstrip(".")
    return f"{n}{unit.upper()}"


def _size_tag(text):
    m = SIZE.search(text or "")
    return _canon(m.group(1), m.group(2)) if m else None


def _qmap(html):
    out = {}
    for q, n, u in QSIZE.findall(html or ""):
        out[q] = _canon(n, u)
    return out


def _session():
    s = requests.Session()
    s.headers.update(UA)
    return s


def _norm(s):
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def _head(title):
    t = re.split(r"\s+-", (title or "").strip(), 1)[0].strip(" -:").strip()
    return t or (title or "").strip()


def _title_ok(post, title, year=None):
    nt, short = _norm(post), _norm(_head(title))
    words = [w for w in short.split() if len(w) >= 2]
    if not words:
        return False
    hit = all(re.search(rf"\b{re.escape(w)}\b", nt) for w in words)
    if not hit:
        compact = re.sub(r"[^a-z0-9]+", "", short)
        hit = len(compact) >= 8 and compact in re.sub(r"[^a-z0-9]+", "", nt)
    if not hit:
        return False
    if len(words) == 1:
        return year is not None and bool(re.search(rf"\b{int(year)}\b", nt))
    return True


def _season_ok(post, season):
    t = post or ""
    nth = re.search(r"(\d+)(?:st|nd|rd|th)\s+season", t, re.I)
    m = re.search(r"season\s*(\d+)", t, re.I)
    n = int(nth.group(1) if nth else m.group(1)) if (nth or m) else None
    s = int(season)
    if n is None:
        return s == 1
    return n == s


def _search(s, q):
    items = []
    try:
        r = s.get(f"{BASE}/wp-json/wp/v2/posts", params={"search": q, "per_page": 20}, timeout=TIMEOUT)
        if r.ok:
            for p in r.json():
                items.append(
                    {
                        "title": re.sub(r"<[^>]+>", "", (p.get("title") or {}).get("rendered") or ""),
                        "url": p.get("link"),
                    }
                )
            return items
    except Exception:
        pass
    try:
        r = s.get(f"{BASE}/?s={quote_plus(q)}", timeout=TIMEOUT)
        soup = BeautifulSoup(r.text, "html.parser")
        for a in soup.select("h2.entry-title a, .episodeye a, .detpost a"):
            href, t = a.get("href"), a.get_text(strip=True)
            if href and t and BASE in href:
                items.append({"title": t, "url": href})
    except Exception:
        pass
    return items


def _pick(items, title, season=None, year=None):
    out = []
    for it in items:
        t = it.get("title") or ""
        if not _title_ok(t, title, year=year):
            continue
        if season is not None and not _season_ok(t, season):
            continue
        out.append(it["url"])
    return out


def _label(title, quality=""):
    t = INDO.sub("", title or "")
    t = re.sub(r"^download\s+", "", t, flags=re.I)
    t = re.sub(r"\s+", " ", t).strip(" :-")
    q = (quality or "").lower()
    if q and q not in t.lower():
        t = f"{t} {q}".strip()
    return t


def _row(url, name, size=None):
    tags = ["Indonesian"]
    if re.search(r"\bbatch\b", name, re.I):
        tags.append("Pack")
    m = QUAL.search(name)
    if m:
        tags.append(f"{m.group(1)}p")
    if size:
        tags.append(size)
        if size.lower() not in name.lower().replace(" ", ""):
            name = f"{name} [{size}]"
    return {"url": url, "name": name, "tags": tags}


def _hosts(html):
    soup = BeautifulSoup(html, "html.parser")
    el = soup.select_one(".jdlz")
    title = el.get_text(" ", strip=True) if el else ""
    qmap = _qmap(html)
    out, seen = [], set()
    for b in soup.select('[class*="smokeurl"]'):
        strong = b.find("strong")
        q = ""
        blob = b.get_text(" ", strip=True)
        size = _size_tag(blob)
        if strong:
            m = QUAL.search(strong.get_text(" ", strip=True))
            if m:
                q = f"{m.group(1)}p"
                size = size or qmap.get(m.group(1))
        name = _label(title, q)
        for a in b.find_all("a", href=True):
            u = a["href"].strip()
            if not HOST.search(u) or u in seen:
                continue
            seen.add(u)
            out.append(_row(u, name, size))
    if out:
        return out
    for a in soup.find_all("a", href=True):
        u = a["href"].strip()
        if not HOST.search(u) or u in seen:
            continue
        seen.add(u)
        q = ""
        m = QUAL.search(u)
        if m:
            q = f"{m.group(1)}p"
        lab = a.get_text(" ", strip=True)
        size = _size_tag(lab) or (qmap.get(m.group(1)) if m else None)
        out.append(_row(u, _label(title or lab, q), size))
    return out


def _collect(s, urls):
    out, seen = [], set()
    for u in urls[:4]:
        try:
            r = s.get(u, timeout=TIMEOUT)
            for row in _hosts(r.text):
                if row["url"] in seen:
                    continue
                seen.add(row["url"])
                out.append(row)
        except Exception:
            continue
    return out


def _run(title, season=None, year=None):
    s = _session()
    q = _head(title)
    posts = _pick(_search(s, q), title, season=season, year=year)
    if not posts and q != title:
        posts = _pick(_search(s, title), title, season=season, year=year)
    return _collect(s, posts)


def dlmovie(title, year=None, tmdb_id=None, imdb_id=None):
    try:
        return _run(title, year=year) or []
    except Exception:
        return []


def dlseries(title, season, year=None, tmdb_id=None, imdb_id=None):
    try:
        return _run(title, season=season, year=year) or []
    except Exception:
        return []


def dlseriesepisode(title, season, episode, year=None, tmdb_id=None, imdb_id=None):
    try:
        return _run(title, season=season, year=year) or []
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
