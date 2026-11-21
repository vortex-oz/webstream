import re
from urllib.parse import quote_plus, urljoin

from scrapers import _http as requests
from bs4 import BeautifulSoup

BASE = "https://hindmovie.icu"
UA = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    )
}
TIMEOUT = 25


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


def _get(s, url):
    r = s.get(url, timeout=TIMEOUT)
    if r.status_code != 200 or "Just a moment" in r.text:
        return None
    return BeautifulSoup(r.text, "html.parser")


def _search(s, title):
    soup = _get(s, f"{BASE}/?s={quote_plus(title)}")
    if soup is None:
        return []
    items = []
    seen = set()
    for a in soup.select("h1 a, h2 a, h3 a, .entry-title a"):
        href, t = a.get("href"), a.get_text(strip=True)
        if not href or not t:
            continue
        href = urljoin(BASE + "/", href)
        if href in seen:
            continue
        seen.add(href)
        items.append({"title": t, "url": href})
    return items


def _pick(items, title, year=None):
    wt = _norm(title)
    best = None
    for it in items:
        nt = _norm(it["title"])
        slug = _norm(it["url"].replace("-", " "))
        blob = nt + " " + slug
        if wt not in blob:
            continue
        if wt == "avatar" and re.search(r"airbender|aang|way of water|ramana", blob):
            continue
        if year and str(year) not in it["title"] and str(year) not in it["url"] and wt not in nt:
            continue
        if wt == nt or (year and str(year) in it["title"]):
            return it["url"]
        if best is None:
            best = it["url"]
    return best


def _dl_links(soup):
    urls = []
    seen = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        t = a.get_text(" ", strip=True)
        if not href.startswith("http") or "hindmoviez" in href:
            continue
        if re.search(r"download|drive|mega|mediafire|nitroflare|rapidgator|katfile|ddownload|keep2share|1fichier|gofile|turbobit|filefactory|uploadgig|alfafile|hitfile|rapidrar|clicknupload|megaup|krakenfiles|pixeldrain|dropbox|uload|filepress|filebee|vcloud|hubcloud|gdflix|goflix|vikingfile|keeplinks|filecrypt|linkcrypt|multiup|mvlink", href + t, re.I):
            if href in seen:
                continue
            seen.add(href)
            prev = a.find_previous(["h2", "h3", "h4", "strong", "b"])
            ctx = prev.get_text(" ", strip=True) if prev else ""
            if ctx.lower() in {"download links", "download", "links"}:
                ctx = ""
            name = ctx or t or href.split("/")[-1]
            st = _size_tag(ctx) or _size_tag(t)
            urls.append({"url": href, "name": name, "tags": [st] if st else []})
    return urls


def dlmovie(title, year=None, tmdb_id=None, imdb_id=None):
    try:
        s = _session()
        url = _pick(_search(s, title), title, year=year)
        if not url:
            return []
        soup = _get(s, url)
        if soup is None:
            return []
        return _dl_links(soup) or []
    except Exception:
        return []


def dlseries(title, season, year=None, tmdb_id=None, imdb_id=None):
    try:
        s = _session()
        url = _pick(_search(s, title), title, year=year)
        if not url:
            return []
        soup = _get(s, url)
        if soup is None:
            return []
        return _dl_links(soup) or []
    except Exception:
        return []


def dlseriesepisode(title, season, episode, year=None, tmdb_id=None, imdb_id=None):
    return dlseries(title, season, year=year, tmdb_id=tmdb_id, imdb_id=imdb_id)


if __name__ == "__main__":
    import json
    from pathlib import Path
    base = Path(__file__).resolve().parent
    avatar = json.loads((base / "avatar.json").read_text())
    bb = json.loads((base / "breaking_bad.json").read_text())
    print("avatar", dlmovie(avatar["title"], year=int(avatar["release_date"][:4]), tmdb_id=avatar["id"], imdb_id=avatar.get("imdb_id")))
    print("breaking_bad_s1", dlseries(bb["name"], 1, year=int(bb["first_air_date"][:4]), tmdb_id=bb["id"], imdb_id=(bb.get("external_ids") or {}).get("imdb_id")))
