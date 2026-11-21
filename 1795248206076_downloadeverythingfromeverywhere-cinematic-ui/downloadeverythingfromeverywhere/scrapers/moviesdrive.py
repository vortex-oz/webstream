import re
from urllib.parse import quote_plus, urljoin

from bs4 import BeautifulSoup

from scrapers import _http as requests
from scrapers._tags import tags_from

BASE = "https://mdrive.lol"
UA = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    )
}
TIMEOUT = 20
HOST_RE = re.compile(r"hubcloud|gdflix|hubdrive|pixeldrain", re.I)
EP_IN_TITLE = re.compile(r"s\d{1,2}e\d{1,3}", re.I)


def _session():
    s = requests.Session()
    s.headers.update(UA)
    return s


def _tok(s):
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).split()


def _title_hit(name, title):
    want, have = _tok(title), _tok(name)
    n = len(want)
    if not n or len(have) < n:
        return False
    return any(have[i : i + n] == want for i in range(len(have) - n + 1))


def _season_hit(name, season):
    n = int(season)
    if re.search(rf"\bseason\s*0*{n}\b", name, re.I):
        return True
    if re.search(rf"(?:^|[^a-z0-9])s0*{n}(?:[^a-z0-9e]|$)", name, re.I):
        return True
    if re.search(rf"s0*{n}\s*[-–to]+\s*s?\d+", name, re.I):
        return True
    return False


def _single_ep(name):
    return bool(EP_IN_TITLE.search(name or "")) and not re.search(
        r"s\d{1,2}e\d{1,3}\s*[-–to]", name or "", re.I
    )


def _item(url, name=""):
    return {"url": url, "name": name or "download", "tags": tags_from(name, url)}


def _search(s, q):
    r = s.get(f"{BASE}/?s={quote_plus(q)}", timeout=TIMEOUT)
    if r.status_code != 200 or "Just a moment" in r.text:
        return []
    soup = BeautifulSoup(r.text, "html.parser")
    out, seen = [], set()
    for a in soup.select("h1 a, h2 a, h3 a, .entry-title a, article a"):
        href, t = a.get("href"), a.get_text(" ", strip=True)
        if not href or not t or len(t) < 8:
            continue
        full = urljoin(BASE, href)
        if "/archive/" not in full or full in seen:
            continue
        seen.add(full)
        out.append((t, full))
    return out


def _pick(rows, title, year=None, season=None, episode=None):
    hit = []
    for t, u in rows:
        if not _title_hit(t, title):
            continue
        if episode is not None:
            if not re.search(rf"s0*{int(season)}e0*{int(episode)}\b", t, re.I):
                continue
        elif season is not None:
            if not _season_hit(t, season):
                continue
            if _single_ep(t):
                continue
        else:
            if re.search(r"\bseason\b|s\d{1,2}", t, re.I):
                continue
            if year and str(year) not in t:
                continue
        zippy = 0 if re.search(r"zip\s*file", t, re.I) else 1
        hit.append((zippy, t, u))
    hit.sort()
    return [(t, u) for _, t, u in hit]


def _hosts(html, fallback=""):
    soup = BeautifulSoup(html, "html.parser")
    out, seen = [], set()
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not HOST_RE.search(href) or href in seen:
            continue
        seen.add(href)
        parent = a.find_parent(["li", "p", "div", "tr", "h2", "h3", "h4"])
        blob = parent.get_text(" ", strip=True) if parent else ""
        ep = re.search(r"(EP\s*\d+|S\d{2}E\d{2}|Episode\s*\d+)", blob, re.I)
        name = fallback
        if ep and ep.group(0) not in (fallback or ""):
            name = f"{fallback} {ep.group(0)}".strip()
        out.append(_item(href, name))
    return out


def _from_posts(s, posts):
    out, seen = [], set()
    for t, u in posts[:3]:
        try:
            r = s.get(u, timeout=TIMEOUT)
        except Exception:
            continue
        if r.status_code != 200:
            continue
        for it in _hosts(r.text, t):
            if it["url"] in seen:
                continue
            seen.add(it["url"])
            out.append(it)
    return out


def dlmovie(title, year=None, tmdb_id=None, imdb_id=None):
    try:
        s = _session()
        q = f"{title} {year}" if year else title
        posts = _pick(_search(s, q), title, year=year)
        if not posts:
            posts = _pick(_search(s, title), title, year=year)
        return _from_posts(s, posts) if posts else []
    except Exception:
        return []


def dlseries(title, season, year=None, tmdb_id=None, imdb_id=None):
    try:
        s = _session()
        posts = []
        for q in (f"{title} Season {int(season)}", f"{title} S{int(season):02d}", title):
            posts = _pick(_search(s, q), title, season=season)
            if posts:
                break
        return _from_posts(s, posts) if posts else []
    except Exception:
        return []


def dlseriesepisode(title, season, episode, year=None, tmdb_id=None, imdb_id=None):
    try:
        s = _session()
        posts = _pick(
            _search(s, f"{title} S{int(season):02d}E{int(episode):02d}"),
            title,
            season=season,
            episode=episode,
        )
        if posts:
            return _from_posts(s, posts)
        posts = []
        for q in (f"{title} Season {int(season)}", title):
            posts = _pick(_search(s, q), title, season=season)
            if posts:
                break
        ep_re = re.compile(rf"(?:EP\s*|E|Episode\s*)0*{int(episode)}\b|S0*{int(season)}E0*{int(episode)}\b", re.I)
        out = []
        for it in _from_posts(s, posts):
            blob = f"{it.get('name') or ''} {it.get('url') or ''}"
            if ep_re.search(blob):
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
    print(
        "avatar",
        dlmovie(avatar["title"], year=int(avatar["release_date"][:4]), tmdb_id=avatar["id"], imdb_id=avatar.get("imdb_id")),
    )
    print(
        "breaking_bad_s1",
        dlseries(bb["name"], 1, year=int(bb["first_air_date"][:4]), tmdb_id=bb["id"], imdb_id=(bb.get("external_ids") or {}).get("imdb_id")),
    )
    print(
        "breaking_bad_s1e5",
        dlseriesepisode(bb["name"], 1, 5, year=int(bb["first_air_date"][:4]), tmdb_id=bb["id"], imdb_id=(bb.get("external_ids") or {}).get("imdb_id")),
    )
