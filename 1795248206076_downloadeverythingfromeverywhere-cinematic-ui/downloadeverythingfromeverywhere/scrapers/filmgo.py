import re
from urllib.parse import quote_plus, urljoin

from scrapers import _http as requests
from scrapers._tags import tags_from
from bs4 import BeautifulSoup

BASE = "https://www.filmgo.live"
UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
TIMEOUT = 20


def _session():
    s = requests.Session()
    s.headers.update(UA)
    return s


def _norm(s):
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def _search(s, q):
    r = s.get(f"{BASE}/search/?q={quote_plus(q)}", timeout=TIMEOUT)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    out = []
    seen = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/film/" not in href:
            continue
        full = urljoin(BASE, href)
        if full in seen:
            continue
        t = a.get_text(strip=True)
        if not t or len(t) < 3 or t.replace(".", "").isdigit():
            continue
        seen.add(full)
        out.append((t, full))
    return out


def _match_movie(t, href, title, year=None):
    blob = _norm(f"{t} {href}")
    wt = _norm(title)
    if wt not in blob:
        return False
    if year and str(year) not in f"{t} {href}":
        return False
    if re.search(r"\bs0?\d+\b|\bcomplete\s*s|\bseason\b", blob):
        return False
    if wt == "avatar" and re.search(r"\b(fire|way|airbender|aang|korra)\b", blob):
        return False
    return True


def _match_season(t, href, title, season):
    blob = _norm(f"{t} {href}")
    wt = _norm(title)
    if wt not in blob:
        return False
    if "el camino" in blob or "bad guys" in blob:
        return False
    if not re.search(rf"\bs0*{int(season)}\b|\bseason\s*0*{int(season)}\b", blob):
        return False
    if re.search(rf"s0*{int(season)}e\d+", blob):
        return False
    return True


def _match_episode(t, href, title, season, episode):
    blob = _norm(f"{t} {href}")
    wt = _norm(title)
    if wt not in blob:
        return False
    if not re.search(rf"s0*{int(season)}e0*{int(episode)}\b", blob):
        return False
    return True


def _hidden_hosts(s, film_url, name="", limit=6):
    r = s.get(film_url, timeout=TIMEOUT)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    fs = soup.select_one(".file-size")
    sz = fs.get_text(" ", strip=True) if fs else ""
    dn = None
    for a in soup.find_all("a", href=True):
        if a.get_text(strip=True) == "Download Now" or "/film/download/?id=" in a["href"]:
            dn = urljoin(BASE, a["href"])
            break
    if not dn:
        return []
    r2 = s.get(dn, headers={**UA, "Referer": film_url}, timeout=TIMEOUT)
    soup2 = BeautifulSoup(r2.text, "html.parser")
    out = []
    for a in soup2.find_all("a", href=True):
        if "/film/download/r/" not in a["href"]:
            continue
        redir = urljoin(BASE, a["href"])
        try:
            r3 = s.get(redir, headers={**UA, "Referer": dn}, timeout=TIMEOUT, allow_redirects=False)
            loc = r3.headers.get("Location")
            if loc:
                out.append(urljoin(redir, loc))
            else:
                r4 = s.get(redir, headers={**UA, "Referer": dn}, timeout=TIMEOUT, allow_redirects=True)
                if r4.url and "filmgo" not in r4.url:
                    out.append(r4.url)
        except Exception:
            pass
        if len(out) >= limit:
            break
    items, seen = [], set()
    for u in out:
        if not u or "filmgo" in u or u in seen:
            continue
        seen.add(u)
        items.append({"url": u, "name": name or "download", "tags": tags_from(name, sz)})
    return items


def dlmovie(title, year=None, tmdb_id=None, imdb_id=None):
    try:
        s = _session()
        q = f"{title} {year}" if year else title
        results = _search(s, q)
        hits = [(t, h) for t, h in results if _match_movie(t, h, title, year)]
        if not hits:
            return []
        out = []
        for t, u in hits[:3]:
            out.extend(_hidden_hosts(s, u, name=t))
        return out
    except Exception:
        return []


def dlseries(title, season, year=None, tmdb_id=None, imdb_id=None):
    try:
        s = _session()
        for q in (f"{title} S{int(season):02d}", f"{title} Complete S{int(season):02d}", title):
            results = _search(s, q)
            hits = [(t, h) for t, h in results if _match_season(t, h, title, season)]
            if hits:
                t, u = hits[0]
                return _hidden_hosts(s, u, name=t, limit=3) or []
        return []
    except Exception:
        return []


def dlseriesepisode(title, season, episode, year=None, tmdb_id=None, imdb_id=None):
    try:
        s = _session()
        q = f"{title} S{int(season):02d}E{int(episode):02d}"
        results = _search(s, q)
        hits = [(t, h) for t, h in results if _match_episode(t, h, title, season, episode)]
        if not hits:
            hits = [(t, h) for t, h in _search(s, title) if _match_episode(t, h, title, season, episode)]
        out = []
        for t, u in hits[:6]:
            out.extend(_hidden_hosts(s, u, name=t))
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
