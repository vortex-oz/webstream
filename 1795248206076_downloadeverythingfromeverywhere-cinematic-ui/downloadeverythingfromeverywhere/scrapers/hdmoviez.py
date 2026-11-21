import re
from urllib.parse import unquote, urljoin, urlparse, parse_qs

from scrapers import _http as requests
from scrapers._tags import format_size, tags_from
from bs4 import BeautifulSoup

BASE = "https://www.moviezmad.cc"
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


def _search(s, q):
    r = s.get(f"{BASE}/search", params={"q": q}, timeout=TIMEOUT)
    soup = BeautifulSoup(r.text, "html.parser")
    out = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/movie/" not in href:
            continue
        t = a.get_text(strip=True)
        if t:
            out.append((t, urljoin(BASE, href)))
    return out


def _pick(results, title, year=None, season=None):
    want = _norm(title)
    picked = []
    for t, href in results:
        nt = _norm(t)
        if want not in nt:
            continue
        if season is not None:
            if not re.search(rf"(?:season|s)\s*0*{int(season)}\b", t, re.I):
                continue
            if not re.search(r"complete|season", t, re.I):
                continue
        else:
            if re.search(r"\bseason\b", t, re.I):
                continue
            if year and str(year) not in t:
                # allow if exact title match
                rest = nt.replace(want, "", 1).strip()
                if year and str(year) not in rest and str(year) not in t:
                    if want == "avatar" and re.search(r"\b(way|water|fire|ash|airbender)\b", rest):
                        continue
                    if str(year) not in t:
                        continue
            if want == "avatar" and re.search(r"\b(way of water|fire and ash|airbender|aang)\b", nt):
                if year and str(year) not in t:
                    continue
        picked.append(href)
    return picked


def _cl_size(s, url):
    try:
        r = s.head(url, timeout=15, allow_redirects=True)
        cl = r.headers.get("content-length")
        if cl and int(cl) > 1024:
            return format_size(int(cl))
    except Exception:
        return None
    return None


def _dl_urls(s, movie_url, title=""):
    r = s.get(movie_url, timeout=TIMEOUT)
    soup = BeautifulSoup(r.text, "html.parser")
    dl_page = None
    for a in soup.find_all("a", href=True):
        if "/dl/" in a["href"]:
            dl_page = urljoin(movie_url, a["href"])
            break
    if not dl_page:
        return []
    r = s.get(dl_page, timeout=TIMEOUT)
    soup = BeautifulSoup(r.text, "html.parser")
    urls = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/download/dl/" not in href:
            continue
        full = urljoin(r.url, href)
        label = a.get_text(" ", strip=True)
        res = ""
        m = re.search(r"(\d{3,4}p)", f"{a.get('title') or ''} {label} {href}", re.I)
        if m:
            res = m.group(1)
        try:
            rr = s.get(full, timeout=TIMEOUT, allow_redirects=False)
            loc = rr.headers.get("Location")
            url = urljoin(full, loc) if loc else full
        except Exception:
            url = full
        qs = parse_qs(urlparse(url).query)
        fn = (qs.get("filename") or [None])[0]
        name = unquote(fn.replace("+", " ")) if fn else " ".join(x for x in (title, res) if x) or label or "download"
        if res and res not in name:
            name = f"{name} {res}"
        st = _cl_size(s, url)
        tags = tags_from(name, res)
        if st and st not in tags:
            tags.append(st)
        urls.append({"url": url, "name": name, "tags": tags})
    seen, out = set(), []
    for it in urls:
        if it["url"] not in seen:
            seen.add(it["url"])
            out.append(it)
    return out


def dlmovie(title, year=None, tmdb_id=None, imdb_id=None):
    try:
        s = _session()
        q = f"{title} {year}" if year else title
        results = _pick(_search(s, q), title, year=year)
        if not results:
            results = _pick(_search(s, title), title, year=year)
        if not results:
            return []
        return _dl_urls(s, results[0], title) or []
    except Exception:
        return []


def dlseries(title, season, year=None, tmdb_id=None, imdb_id=None):
    try:
        s = _session()
        q = f"{title} Season {int(season)}"
        results = _pick(_search(s, q), title, year=year, season=season)
        if not results:
            results = _pick(_search(s, title), title, year=year, season=season)
        if not results:
            return []
        return _dl_urls(s, results[0], title) or []
    except Exception:
        return []


def dlseriesepisode(title, season, episode, year=None, tmdb_id=None, imdb_id=None):
    return


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
