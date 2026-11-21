import re
from urllib.parse import quote_plus, urljoin

from scrapers import _http as requests
from scrapers._tags import tags_from
from bs4 import BeautifulSoup

BASE = "https://www.todaytvseries1.com"
UA = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    )
}
TIMEOUT = 25

HOST_RE = re.compile(
    r"(renewyep|renewback|uupload|archive\.org|207\.241\.)",
    re.I,
)


def _session():
    s = requests.Session()
    s.headers.update(UA)
    return s


def _norm(s):
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def _get(s, url):
    r = s.get(url, timeout=TIMEOUT)
    if r.status_code != 200 or "Just a moment" in r.text:
        return None
    return BeautifulSoup(r.text, "html.parser")


def _search_json(s, title):
    url = (
        f"{BASE}/search-series?tmpl=raw&type=json&searchphrase=all"
        f"&searchword={quote_plus(title)}"
    )
    r = s.get(
        url,
        timeout=TIMEOUT,
        headers={"X-Requested-With": "XMLHttpRequest", "Accept": "application/json"},
    )
    if r.status_code != 200:
        return []
    try:
        data = r.json()
    except Exception:
        return []
    items = []
    for row in data.get("results") or []:
        href = urljoin(BASE + "/", row.get("url") or "")
        t = (row.get("title") or "").strip()
        if href and t:
            items.append({"title": t, "url": href})
    return items


def _search(s, title):
    items = _search_json(s, title)
    if items:
        return items
    seen = set()
    for q in (title, f'"{title}"'):
        soup = _get(s, f"{BASE}/search-series?searchword={quote_plus(q)}&searchphrase=all")
        if soup is None:
            continue
        for a in soup.find_all("a", href=True):
            href = urljoin(BASE + "/", a["href"])
            if "/tv-series/" not in href:
                continue
            t = a.get_text(" ", strip=True)
            if not t or href in seen:
                continue
            seen.add(href)
            items.append({"title": t, "url": href})
        if items:
            break
    return items


def _pick(items, title):
    if not items:
        return None
    wt = _norm(title)
    exact, soft = [], []
    for it in items:
        nt = _norm(it["title"])
        if nt == wt:
            exact.append(it["url"])
        elif wt in nt or nt in wt or any(w in nt for w in wt.split() if len(w) > 2):
            soft.append(it["url"])
    # if no match, return first result as fallback
    return (exact or soft or [None])[0]


def _episode_links(soup, season, episode=None):
    sn = int(season)
    ep = int(episode) if episode is not None else None
    html = str(soup)
    # accordion block for this season
    m = re.search(
        rf"Download\s+Season\s*0*{sn}\s*</h[0-9]>(.*?)(?=Download\s+Season\s*\d+\s*</h[0-9]>|$)",
        html,
        re.I | re.S,
    )
    chunk = m.group(1) if m else html
    urls, seen = [], set()
    # rows: cell2 SxxExx … <a href="...">
    for row in re.finditer(
        r'cell2">\s*(S\d+E\d+)\s*</div>.*?href="(https?://[^"]+)"',
        chunk,
        re.I | re.S,
    ):
        label, href = row.group(1), row.group(2)
        if ep is not None:
            if not re.search(rf"S0*{sn}E0*{ep}\b", label, re.I):
                continue
        elif not re.search(rf"S0*{sn}E\d+", label, re.I):
            continue
        if href not in seen:
            seen.add(href)
            from urllib.parse import unquote

            fname = unquote(href.rstrip("/").split("/")[-1])
            name = fname if fname and "." in fname else label
            urls.append({"url": href, "name": name, "tags": tags_from(name, href, row.group(0))})
    if urls:
        return urls
    # fallback on href filenames
    for a in BeautifulSoup(chunk, "html.parser").find_all("a", href=True):
        href = a["href"]
        if not href.startswith("http"):
            continue
        blob = href
        if ep is not None:
            if not re.search(rf"S0*{sn}E0*{ep}\b", href, re.I):
                continue
        elif not re.search(rf"S0*{sn}E\d+", href, re.I):
            continue
        if href not in seen:
            seen.add(href)
            from urllib.parse import unquote

            fname = unquote(href.rstrip("/").split("/")[-1])
            urls.append({"url": href, "name": fname, "tags": tags_from(fname, href)})
    return urls


def dlmovie(title, year=None, tmdb_id=None, imdb_id=None):
    return


def dlseries(title, season, year=None, tmdb_id=None, imdb_id=None):
    return


def dlseriesepisode(title, season, episode, year=None, tmdb_id=None, imdb_id=None):
    try:
        s = _session()
        url = _pick(_search(s, title), title)
        if not url:
            return []
        soup = _get(s, url)
        if soup is None:
            return []
        return _episode_links(soup, season, episode=episode) or []
    except Exception:
        return []


if __name__ == "__main__":
    import json
    from pathlib import Path
    base = Path(__file__).resolve().parent
    bb = json.loads((base / "breaking_bad.json").read_text())
    bb_s1 = json.loads((base / "breaking_bad_s1.json").read_text())
    print("breaking_bad_s1e5", dlseriesepisode(bb["name"], 1, 5, year=int(bb["first_air_date"][:4]), tmdb_id=bb["id"], imdb_id=(bb.get("external_ids") or {}).get("imdb_id")))
