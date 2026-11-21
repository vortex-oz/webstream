import re
from urllib.parse import urljoin, quote_plus

from scrapers import _http as requests
from bs4 import BeautifulSoup

BASE = "https://tvsboy.com"
UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
}
TIMEOUT = 20


def _session():
    s = requests.Session()
    s.headers.update(UA)
    return s


def _norm(s):
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def _size_tag(n):
    m = re.search(r"([\d.,]+)\s*(TiB|GiB|MiB|KiB|TB|GB|MB|KB)", str(n or ""), re.I)
    if not m:
        return None
    num = m.group(1).replace(",", "")
    if "." in num:
        num = num.rstrip("0").rstrip(".")
    if not num:
        return None
    return f"{num}{m.group(2).upper().replace('IB', 'B')}"


def _find_season(s, title, season):
    want = _norm(title)
    r = s.get(f"{BASE}/?s={quote_plus(title)}", timeout=TIMEOUT)
    soup = BeautifulSoup(r.text, "html.parser")
    season_re = re.compile(rf"season[_-]?0*{int(season)}\b", re.I)
    for a in soup.select("h2 a, h3 a, .entry-title a, article a"):
        href = a.get("href") or ""
        text = a.get_text(" ", strip=True)
        if want not in _norm(text) and want.replace(" ", "-") not in href.lower():
            continue
        if season_re.search(href) or season_re.search(text):
            return urljoin(BASE + "/", href)
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    guess = f"{BASE}/{slug}-season-{int(season)}/"
    try:
        r = s.get(guess, timeout=TIMEOUT)
        if r.status_code == 200 and "go.php" in r.text:
            return r.url
    except Exception:
        pass
    return None


def _resolve_go(s, go_url):
    try:
        r = s.get(go_url, timeout=TIMEOUT, allow_redirects=False)
        loc = r.headers.get("Location")
        if loc:
            return urljoin(go_url, loc)
        r = s.get(go_url, timeout=TIMEOUT, allow_redirects=True)
        if r.url and "tvsboy.com" not in r.url:
            return r.url
    except Exception:
        pass
    return go_url


def dlmovie(title, year=None, tmdb_id=None, imdb_id=None):
    return


def dlseries(title, season, year=None, tmdb_id=None, imdb_id=None):
    return


def dlseriesepisode(title, season, episode, year=None, tmdb_id=None, imdb_id=None):
    try:
        s = _session()
        page = _find_season(s, title, season)
        if not page:
            return []
        r = s.get(page, timeout=TIMEOUT)
        soup = BeautifulSoup(r.text, "html.parser")
        urls = []
        ep = int(episode)
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "go.php" not in href:
                continue
            if re.search(rf"[?&]episode={ep}(?:&|$)", href):
                go = urljoin(page, href)
                lab = a.get_text(" ", strip=True)
                st = _size_tag(lab)
                tags = [st] if st else []
                q = re.search(r"(\d{3,4})\s*p", lab, re.I)
                if q:
                    tags.append(f"{q.group(1)}p")
                urls.append({"url": _resolve_go(s, go), "name": lab or f"E{ep:02d}", "tags": tags})
        seen, out = set(), []
        for u in urls:
            if u["url"] not in seen:
                seen.add(u["url"])
                out.append(u)
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
